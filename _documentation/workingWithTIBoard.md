## Installs (on the Mac)

1. Serial driver (not needed on recent macOS): https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers?tab=downloads
2. Demo visualizer: https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/
3. UniFlash (flash `.bin` images to the board): https://www.ti.com/tool/UNIFLASH
4. Radar Toolbox (source + prebuilt binaries + chirp configs): extract to `~/ti/radar_toolbox_4_20_00_07`.
   Plain files - no x86 needed to read, edit, or unzip them.

You do NOT need the mmWave SDK installed on the Mac (it is Windows/Linux only). It lives in the container.
Code Composer Studio (https://www.ti.com/tool/CCSTUDIO) is optional and not used by the container build; it is only
needed if you want TI's GUI or JTAG debugging.

## Building firmware (container)

The mmWave SDK 3.6.2 + TI compilers are 32-bit x86 Linux, so on Apple silicon they run under qemu-user
emulation. Use a podman machine / Docker Desktop with **QEMU** emulation (Rosetta can't run 32-bit).
Give the VM >= 4 GB RAM:

    podman machine stop qemu-machine && podman machine set --memory 6144 qemu-machine && podman machine start qemu-machine

Build the image once (~20-30 min under emulation; installers are slow):

    podman -c qemu-machine build --platform linux/amd64 -t ti-radar-env:4.20 -f Dockerfile.sdk .

Build the 3D People Tracking demo without compose (source is bind-mounted, output lands in `ti_awr6843aop_evm/out`):

    mkdir -p ti_awr6843aop_evm/out
    podman -c qemu-machine run --rm --platform linux/amd64 \
      -v ~/ti/radar_toolbox_4_20_00_07:/toolbox:ro \
      -v "$PWD/ti_awr6843aop_evm/out":/workspace/out \
      ti-radar-env:4.20 build_3d_people_tracking

Result: `ti_awr6843aop_evm/out/3d_people_tracking/3D_people_track_6843_demo.bin` -> flash with UniFlash
(see the demo's user guide for the flash-mode switch settings). The `out/` folder is gitignored.

Status: the build is reproducible (two clean builds give byte-identical output) and the radar front-end firmware
inside matches TI's prebuilt exactly, but the ARM/DSP code is ~0.6% larger than TI's prebuilt (embedded absolute
source paths and possibly a different SDK/XDC config) and it has NOT yet been tested on hardware.

### Day-to-day with compose (no rebuilds)

`compose.ti.yaml` keeps one long-running container so builds start instantly. The toolbox, the build script
and the output folder (`ti_awr6843aop_evm/out`) are bind-mounted, so editing any of them never needs an image rebuild.

    alias tic='podman -c qemu-machine compose -f compose.ti.yaml'
    tic up -d                                # starts it; only builds the image if it doesn't exist
    tic exec ti build_3d_people_tracking     # build the demo (edit source on the Mac between runs)
    tic exec ti bash                         # shell in the container
    tic down                                 # stop (the image stays)

Only run `tic build` when `Dockerfile.sdk` itself changes. Use `TOOLBOX_DIR=/path tic up -d` to point at a different toolbox copy.

`build_3d_people_tracking` stages: `dss`, `mss`, `image` (default `all`). `SKIP_COMPILE=1` relinks only.

To modify the demo, edit the C under `.../People_Tracking/3D_People_Tracking/src/6843/{mss,dss,common}` and
`source/ti/custom_sdk_files/sdk3/`. Note `compose.ti.yaml` mounts the toolbox read-write, so edits change your
original copy; to keep it pristine, copy it and start with `TOOLBOX_DIR=/path/to/copy tic up -d`.

## Notes / gotchas found

- The 32-bit installers exit 127 with no output unless the `:i386` libs are installed.
- The SDK installer itself installs the ARM compiler (16.9.6 LTS); only the C6000 8.3.3 compiler is a separate install.
- `MMWAVE_SDK_INSTALL_PATH` must end in `/packages`.
- XDC `configuro` writes generated files next to the `.cfg`, so the build script runs it on a copy.
- `out2rprc` only exists as a Windows .NET exe; the container uses `mono-runtime` to run it.
- Chirp configs for the AOP: `.../3D_People_Tracking/chirp_configs/AOP_*.cfg`.
