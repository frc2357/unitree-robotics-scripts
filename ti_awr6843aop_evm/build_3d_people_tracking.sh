#!/usr/bin/env bash
# Command-line build of the TI Radar Toolbox "3D People Tracking" demo (xWR6843),
# replicating what CCS does with the .projectspec files.
# Meant to run INSIDE the ti-radar-env container.
#
#   TOOLBOX_DIR  radar toolbox root (default /toolbox)
#   OUT_DIR      where objects + final .bin go (default /workspace/out/3d_people_tracking)
set -euo pipefail

TB=${TOOLBOX_DIR:-/toolbox}
OUT=${OUT_DIR:-/workspace/out/3d_people_tracking}
TI=${TI_TOOLS_DIR:-/opt/ti}

SDK=$TI/mmwave_sdk_03_06_02_00-LTS
SDKP=$SDK/packages
R4F=$TI/ti-cgt-arm_16.9.6.LTS
C674=$TI/ti-cgt-c6000_8.3.3
XDC=$TI/xdctools_3_50_08_24_core
BIOS=$TI/bios_6_73_01_01/packages
MATHLIB=$TI/mathlib_c674x_3_1_2_1
DSPLIB64P=$TI/dsplib_c64Px_3_4_0_0
DSPLIB674=$TI/dsplib_c674x_3_4_0_0

EX=$TB/source/ti/examples/Industrial_and_Personal_Electronics/People_Tracking/3D_People_Tracking/src/6843
SDK3=$TB/source/ti/custom_sdk_files/sdk3

JOBS=${JOBS:-4}
mkdir -p "$OUT/mss" "$OUT/dss"

# ------------------------------------------------------------------ defines
COMMON_DEFS=(
  -DSOC_XWR68XX -DPLATFORMES2
  -DMMWAVE_L3RAM_NUM_BANK=6 -DMMWAVE_SHMEM_TCMA_NUM_BANK=0 -DMMWAVE_SHMEM_TCMB_NUM_BANK=0
  -DMMWAVE_SHMEM_BANK_SIZE=0x20000 -DMMWAVE_L3_CODEMEM_SIZE=0x100 -DMMWAVE_MSSUSED_L3RAM_SIZE=0x90000
  -DDOWNLOAD_FROM_CCS -DDebugP_ASSERT_ENABLED -D_LITTLE_ENDIAN
  -DOBJDET_NO_RANGE -DGTRACK_3D -DWALL_MOUNT_CONFIG
  "-DAPP_RESOURCE_FILE=<pcount3D_hwres.h>"
)
COMMON_INC=(
  -I"$EX" -I"$EX/common" -I"$TB/source/ti/common"
  -I"$SDKP" -I"$MATHLIB/packages" -I"$DSPLIB64P/packages"
  -I"$DSPLIB64P/packages/ti/dsplib/src/DSP_fft16x16_imre/c64P"
  -I"$DSPLIB64P/packages/ti/dsplib/src/DSP_fft32x32/c64P"
  -I"$SDK3" -I"$TB"
)

# =================================================================== DSS (C674x)
build_dss() {
  local D=$OUT/dss; cd "$D"
  echo "=== DSS: configuro"
  # configuro writes generated files next to the .cfg, so run it on a copy
  cp "$EX/dss/pcount3D_dss.cfg" "$D/"
  if [ ! -f "$D/configPkg/linker.cmd" ]; then rm -rf "$D/configPkg"
  "$XDC/xs" --xdcpath="$BIOS;$SDKP;$MATHLIB/packages;$DSPLIB64P/packages;$DSPLIB674/packages" \
    xdc.tools.configuro -t ti.targets.elf.C674 -p ti.platforms.c6x:IWR68XX:false:600 \
    -r release -c "$C674" --compileOptions "--enum_type=int " \
    -o "$D/configPkg" "$D/pcount3D_dss.cfg"
  fi

  local CF=(-mv6740 -mf3 -mo -O3 --gcc -g --diag_warning=225 --diag_error=10015 --diag_wrap=off
            --display_error_number --abi=eabi --obj_extension .oe674 -DSUBSYS_DSS
            --cmd_file="$D/configPkg/compiler.opt"
            -I"$EX/dss" -I"$DSPLIB674/packages" -I"$C674/include" "${COMMON_INC[@]}" "${COMMON_DEFS[@]}")
  local SRC=(
    "$EX/dss/dss_main.c"
    "$SDK3/dpc/capon3d/src/objectdetection.c"
    "$SDK3/dpu/capon3d/src/radarProcess.c"
    "$SDK3/dpu/capon3d/src/copyTranspose.c"
    "$SDK3"/dpu/capon3d/modules/DoA/CaponBF2D/src/RADARDEMO_aoaEst2DCaponBF*.c
    "$SDK3/dpu/capon3d/modules/detection/CFAR/src/RADARDEMO_detectionCFAR.c"
    "$SDK3/dpu/capon3d/modules/detection/CFAR/src/RADARDEMO_detectionCFAR_priv.c"
    "$SDK3/dpu/capon3d/modules/utilities/cycle_measure.c"
    "$SDK3/dpu/capon3d/modules/utilities/radarOsal_malloc.c"
    "$SDK3/dpu/capon3d/modules/postProcessing/matrixFunc/src/MATRIX_cholesky.c"
    "$SDK3/dpu/capon3d/modules/postProcessing/matrixFunc/src/MATRIX_cholesky_dat.c"
  )
  echo "=== DSS: compile ${#SRC[@]} files"
  [ -n "${SKIP_COMPILE:-}" ] || printf '%s\0' "${SRC[@]}" | xargs -0 -P "$JOBS" -I{} sh -c \
    '"$0" "$@" --compile_only {}' \
    "$C674/bin/cl6x" "${CF[@]}"

  echo "=== DSS: link"
  local LIBP=()
  for p in control/mmwave control/mmwavelink control/dpm alg/mmwavelib drivers/crc drivers/soc drivers/osal \
           drivers/mailbox drivers/edma drivers/adcbuf drivers/cbuff utils/hsiheader utils/mathutils \
           datapath/dpc/dpu/dopplerproc datapath/dpc/dpu/cfarcaproc datapath/dpedma; do
    LIBP+=(-i"$SDKP/ti/$p/lib"); done
  "$C674/bin/cl6x" -mv6740 -mf3 -mo -O3 --abi=eabi --gcc -g --obj_extension .oe674 \
    -z -m3D_people_track_6843_dss.map -o 3D_people_track_6843_dss.xe674 \
    -i"$C674/lib" "${LIBP[@]}" -i"$DSPLIB64P/packages/ti/dsplib/lib" -i"$MATHLIB/packages/ti/mathlib/lib" \
    -i"$DSPLIB674/packages/ti/dsplib/lib" \
    --define=MMWAVE_L3RAM_NUM_BANK=6 --define=MMWAVE_SHMEM_TCMA_NUM_BANK=0 --define=MMWAVE_SHMEM_TCMB_NUM_BANK=0 --define=MMWAVE_SHMEM_BANK_SIZE=0x20000 --define=MMWAVE_MSSUSED_L3RAM_SIZE=0x90000 \
    --reread_libs --diag_warning=225 --diag_error=10015 --diag_wrap=off --display_error_number \
    --warn_sections --xml_link_info=dss_linkInfo.xml --ram_model --unused_section_elimination=on --disable_auto_rts \
    ./*.oe674 "$D/configPkg/linker.cmd" "$EX/dss/c674x_linker.cmd" "$EX/dss/pcount3D_dss_linker.cmd" \
    -ldsplib.ae64P -lmathlib.ae674 -llibmathutils.ae674 -llibsoc_xwr68xx.ae674 -llibosal_xwr68xx.ae674 \
    -llibcrc_xwr68xx.ae674 -llibmailbox_xwr68xx.ae674 -llibmmwavelink_xwr68xx.ae674 -llibmmwave_xwr68xx.ae674 \
    -llibedma_xwr68xx.ae674 -llibadcbuf_xwr68xx.ae674 -llibmmwavealg_xwr68xx.ae674 -llibcbuff_xwr68xx.ae674 \
    -llibhsiheader_xwr68xx.ae674 -llibmathutils.ae674 -llibdpm_xwr68xx.ae674 -llibdpedma_hwa_xwr68xx.ae674 \
    -lrts6740_elf.lib
  mono "$SDKP/scripts/ImageCreator/out2rprc/out2rprc.exe" 3D_people_track_6843_dss.xe674 3D_people_track_6843_dss.bin
}

# =================================================================== MSS (R4F)
build_mss() {
  local D=$OUT/mss; cd "$D"
  echo "=== MSS: configuro"
  cp "$EX/mss/pcount3D_mss.cfg" "$D/"
  if [ ! -f "$D/configPkg/linker.cmd" ]; then rm -rf "$D/configPkg"
  "$XDC/xs" --xdcpath="$BIOS;$SDKP;$MATHLIB/packages;$DSPLIB64P/packages" \
    xdc.tools.configuro -t ti.targets.arm.elf.R4Ft -p ti.platforms.cortexR:IWR68XX:false:200 \
    -r release -c "$R4F" --compileOptions "--enum_type=int " \
    -o "$D/configPkg" "$D/pcount3D_mss.cfg"
  fi

  local CF=(-mv7R4 --code_state=16 --float_support=VFPv3D16 -me -O3 -eo=.oer4f
            --gcc -g --diag_warning=225 --diag_wrap=off --display_error_number
            --gen_func_subsections=on --enum_type=int --abi=eabi
            -DSUBSYS_MSS -DTRACKERPROC_EN -DHEIGHT_DETECTION_ENABLED
            --cmd_file="$D/configPkg/compiler.opt"
            -I"$EX/mss" -I"$R4F/include" "${COMMON_INC[@]}" "${COMMON_DEFS[@]}")
  local SRC=(
    "$EX/mss/mss_main.c" "$EX/mss/pcount3D_cli.c" "$EX/mss/tracker_utils.c"
    "$EX/common/mmwdemo_adcconfig.c" "$EX/common/mmwdemo_rfparser.c"
    "$SDK3/dpc/objdetrangehwa/src/objdetrangehwa.c"
    "$SDK3/dpu/rangeprochwa/src/rangeprochwa.c"
    "$SDK3/dpu/trackerproc_overhead/src/trackerproc_3d.c"
    "$SDK3/dpu/trackerproc_overhead/src/height_detection.c"
  )
  echo "=== MSS: compile ${#SRC[@]} files"
  [ -n "${SKIP_COMPILE:-}" ] || printf '%s\0' "${SRC[@]}" | xargs -0 -P "$JOBS" -I{} sh -c \
    '"$0" "$@" --compile_only {}' \
    "$R4F/bin/armcl" "${CF[@]}"

  echo "=== MSS: link"
  local LIBP=()
  for p in control/mmwave control/mmwavelink control/dpm drivers/adcbuf drivers/crc drivers/dma drivers/edma \
           drivers/esm drivers/gpio drivers/hwa drivers/mailbox drivers/osal drivers/pinmux drivers/soc \
           drivers/uart utils/cli utils/mathutils datapath/dpedma drivers/cbuff utils/hsiheader; do
    LIBP+=(-i"$SDKP/ti/$p/lib"); done
  "$R4F/bin/armcl" -mv7R4 --code_state=16 --float_support=VFPv3D16 -me -O3 --abi=eabi -eo=.oer4f \
    -z -m3D_people_track_6843_mss.map -o 3D_people_track_6843_mss.xer4f \
    -i"$R4F/lib" "${LIBP[@]}" -i"$SDK3/dpu/trackerproc_overhead/packages/ti/alg/gtrack/lib" \
    --define=MMWAVE_L3RAM_NUM_BANK=6 --define=MMWAVE_SHMEM_TCMA_NUM_BANK=0 --define=MMWAVE_SHMEM_TCMB_NUM_BANK=0 --define=MMWAVE_SHMEM_BANK_SIZE=0x20000 --define=MMWAVE_MSSUSED_L3RAM_SIZE=0x90000 --define=MMWAVE_L3_CODEMEM_SIZE=0x100 \
    --reread_libs --diag_warning=225 --diag_error=10015 --diag_wrap=off --display_error_number \
    --warn_sections --xml_link_info=mss_linkInfo.xml --rom_model --unused_section_elimination=on --disable_auto_rts \
    ./*.oer4f "$D/configPkg/linker.cmd" "$EX/mss/r4f_linker.cmd" "$EX/mss/pcount3D_mss_linker.cmd" \
    -llibosal_xwr68xx.aer4f -llibesm_xwr68xx.aer4f -llibgpio_xwr68xx.aer4f -llibsoc_xwr68xx.aer4f \
    -llibpinmux_xwr68xx.aer4f -llibcrc_xwr68xx.aer4f -llibuart_xwr68xx.aer4f -llibmailbox_xwr68xx.aer4f \
    -llibmmwavelink_xwr68xx.aer4f -llibmmwave_xwr68xx.aer4f -llibadcbuf_xwr68xx.aer4f -llibdma_xwr68xx.aer4f \
    -llibedma_xwr68xx.aer4f -llibcli_xwr68xx.aer4f -llibhwa_xwr68xx.aer4f -llibdpm_xwr68xx.aer4f \
    -llibmathutils.aer4f -llibcbuff_xwr68xx.aer4f -llibhsiheader_xwr68xx.aer4f -llibdpedma_hwa_xwr68xx.aer4f \
    -llibgtrack3D.aer4f -lrtsv7R4_T_le_v3D16_eabi.lib
}

# ================================================================ image assembly
build_image() {
  cd "$OUT/mss"
  local IC=$SDKP/scripts/ImageCreator
  echo "=== image assembly"
  mono "$IC/out2rprc/out2rprc.exe" 3D_people_track_6843_mss.xer4f 3D_people_track_6843_mss.tmp
  "$IC/multicore_image_generator/MulticoreImageGen" LE 37 0x00000006 3D_people_track_6843_demo.bin \
    0x35510000 3D_people_track_6843_mss.tmp \
    0xb5510000 "$SDK/firmware/radarss/xwr6xxx_radarss_rprc.bin" \
    0xd5510000 "$OUT/dss/3D_people_track_6843_dss.bin"
  "$IC/crc_multicore_image/crc_multicore_image" 3D_people_track_6843_demo.bin 3D_people_track_6843_demo.tmp
  "$IC/append_bin_crc/gen_bincrc32" 3D_people_track_6843_demo.bin
  cp 3D_people_track_6843_demo.bin "$OUT/3D_people_track_6843_demo.bin"
  echo "=== DONE: $OUT/3D_people_track_6843_demo.bin"
}

case "${1:-all}" in
  dss) build_dss ;;
  mss) build_mss ;;
  image) build_image ;;
  all) build_dss; build_mss; build_image ;;
esac
