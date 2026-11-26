#!/usr/bin/env python3
"""
vitals_reader.py - Minimal standalone reader for heart rate / breath rate from
the TI AWR6843AOP EVM running the "Vital Signs with People Tracking" demo.

STATUS: Written from reading TI's Industrial Visualizer source. NOT yet run
against real hardware. Treat the first hardware run as validation.

-------------------------------------------------------------------------------
BACKGROUND (for whoever picks this up)
-------------------------------------------------------------------------------
Source this was derived from (TI Radar Toolbox 4.20.00.07,
tools/visualizers/Applications_Visualizer/common/):
  - gui_parser.py   : opens the serial ports, sends the cfg, finds frames
                      (connectComPorts, sendCfg, readAndParseUartDoubleCOMPort)
  - parseFrame.py   : frame header + TLV loop (parseStandardFrame)
  - parseTLVs.py    : parseVitalSignsTLV  (the vitals payload layout)
  - tlv_defines.py  : MMWDEMO_OUTPUT_MSG_VITALSIGNS = 1040
  - Demo_Classes/vital_signs.py : how the GUI post-processes the values

How the sensor talks (two USB serial ports, both exposed by the on-board XDS110):
  - CLI port  @ 115200 baud : we send the .cfg text line by line; the sensor
                              echoes + replies "Done" per line.
  - DATA port @ 921600 baud : once configured, the sensor streams binary frames.
  Typically /dev/ttyACM0 and /dev/ttyACM1 on Linux (order can swap between
  boots - use a udev rule for stable names), /dev/cu.usbmodem* on macOS,
  COMn on Windows. Try swapping the two if no data arrives.

Frame layout (all little-endian):
  [magic 8B][version 4B][totalPacketLen 4B][platform 4B][frameNum 4B]
  [timeCpuCycles 4B][numDetectedObj 4B][numTLVs 4B][subFrameNum 4B]   <- 40B header
  then numTLVs x ( [tlvType 4B][tlvLength 4B][payload tlvLength bytes] )
  then padding up to a multiple of 32 bytes (counted in totalPacketLen).
  NOTE: tlvLength does NOT include the 8-byte TLV header.

Vitals TLV (type 1040) payload, struct '<2H33f' (136 bytes):
  [0] id             uint16  track/patient id
  [1] rangeBin       uint16
  [2] breathDeviation float  ~0 => no patient or breath held; <0.02 => holding breath
  [3] heartRate      float   bpm      (0 = no estimate yet)
  [4] breathRate     float   breaths/min (0 = no estimate yet)
  [5:20]  heartWaveform  15 floats
  [20:35] breathWaveform 15 floats

-------------------------------------------------------------------------------
USAGE
-------------------------------------------------------------------------------
  python3 vitals_reader.py <cli_port> <data_port> <cfg_file>
  python3 vitals_reader.py /dev/ttyACM0 /dev/ttyACM1 vital_signs.cfg

Requires: pip install pyserial
The cfg must be the one matching the vital-signs demo firmware flashed on the
board (from the Radar Toolbox demo's chirp configs). The sensor does not stream
until it has been configured and sensorStart has been sent.

Permissions on Linux: add your user to the 'dialout' group, then log out/in:
  sudo usermod -aG dialout $USER

-------------------------------------------------------------------------------
KNOWN GAPS / TODO (read before relying on the output)
-------------------------------------------------------------------------------
1. STALE DATA: the firmware stops sending the vitals TLV when the person leaves
   (tracker drops the track). This script then simply emits nothing, so any
   consumer MUST treat a gap as "no person" instead of reusing the last value.
   The TI GUI has the same flaw and freezes on the last numbers. Add a timeout
   (e.g. 1-2 s without a vitals update => publish "no patient").
2. VALIDITY CHECKS: the GUI treats breathDeviation == 0 as "no patient" and
   < 0.02 as "holding breath", and shows heart rate as the MEDIAN of the last 10
   readings (NUM_HEART_RATES_FOR_MEDIAN). Not implemented here.
3. MULTIPLE PEOPLE: each frame carries at most one vitals TLV with one id.
   Unknown whether the firmware measures every track or just one; log 'id' with
   two people present to find out. State should be kept per id.
4. ROS 2: replace the print() in main() with a publisher and run the serial loop
   in a thread (or timer) so it does not block rclpy.spin().
5. Error handling is minimal: no reconnect if the USB device drops.
"""

import struct
import sys
import time

import serial  # pip install pyserial

# Marker that starts every frame. Used to resync after partial reads / garbage.
MAGIC = b"\x02\x01\x04\x03\x06\x05\x08\x07"

# Frame header: magic(Q), version, totalPacketLen, platform, frameNum,
# timeCpuCycles, numDetectedObj, numTLVs, subFrameNum  -> 40 bytes.
# Matches headerStruct = 'Q8I' in parseFrame.py (the '<' just makes endianness explicit).
HDR = struct.Struct("<Q8I")

# TLV type id for the vitals payload (tlv_defines.py: MMWDEMO_OUTPUT_MSG_VITALSIGNS).
TLV_VITALS = 1040

# Vitals payload: 2 x uint16 + 33 x float32. Matches '2H33f' in parseTLVs.py.
VITALS = struct.Struct("<2H33f")


def send_cfg(cli, path):
    """Send a .cfg file to the sensor's CLI port, one command per line.

    Mirrors sendCfg() in gui_parser.py: skip blank lines and '%' comments,
    pause between lines, and read the two reply lines (echo + 'Done') for each.
    Does not check the replies for errors - look at the sensor's output if the
    stream never starts.
    """
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            cli.write((line + "\n").encode())
            time.sleep(0.03)  # the sensor drops commands sent too quickly
            cli.readline()  # echo of the command
            cli.readline()  # "Done" or an error message
    cli.reset_input_buffer()


def read_frame(data):
    """Block until one full frame arrives on the DATA port; return its raw bytes.

    Scans byte-by-byte for the 8-byte magic word (so we resync after dropped
    bytes), then reads version + totalPacketLen, then the rest of the frame.
    Raises TimeoutError if the port times out (no data for 0.6 s).
    """
    buf = bytearray()
    while True:
        b = data.read(1)
        if not b:
            raise TimeoutError("no data on data port")
        buf += b
        if buf[-8:] == MAGIC:
            break
        if len(buf) > 8:
            del buf[:-8]  # keep only the last 8 bytes so the buffer stays small

    rest = data.read(8)  # version (4B) + totalPacketLen (4B)
    total_len = struct.unpack("<I", rest[4:8])[0]
    # totalPacketLen covers the whole frame; we've consumed magic(8) + 8 already = 16.
    return MAGIC + rest + data.read(total_len - 16)


def parse_vitals(frame):
    """Walk the TLVs in a frame; return a vitals dict, or None if there is none.

    Mirrors parseStandardFrame() + parseVitalSignsTLV(). Raises struct.error on a
    truncated/corrupt frame (caller should just skip that frame).
    """
    (_magic, _ver, _total, _plat, frame_num,
     _cycles, _num_obj, num_tlvs, _subframe) = HDR.unpack_from(frame)

    off = HDR.size
    for _ in range(num_tlvs):
        t_type, t_len = struct.unpack_from("<2I", frame, off)
        off += 8  # skip the TLV header; t_len counts payload bytes only
        if t_type == TLV_VITALS:
            v = VITALS.unpack_from(frame, off)
            return {
                "frame": frame_num,
                "id": v[0],             # track/patient id
                "range_bin": v[1],
                "breath_dev": v[2],     # ~0 => no patient / holding breath
                "heart_bpm": v[3],      # 0 => no estimate yet
                "breath_rpm": v[4],     # 0 => no estimate yet
                # v[5:20] heart waveform, v[20:35] breath waveform (15 samples each)
            }
        off += t_len  # not the vitals TLV: skip its payload
    return None


def main():
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <cli_port> <data_port> <cfg_file>")
    cli_port, data_port, cfg = sys.argv[1:4]

    cli = serial.Serial(cli_port, 115200, timeout=0.6)
    data = serial.Serial(data_port, 921600, timeout=0.6)
    send_cfg(cli, cfg)

    while True:
        try:
            v = parse_vitals(read_frame(data))
        except (TimeoutError, struct.error):
            continue  # no data or a corrupt frame: try the next one
        if v:
            print(v)  # <- publish to ROS 2 / MQTT / etc. here (see TODO 1, 2, 4)


if __name__ == "__main__":
    main()
