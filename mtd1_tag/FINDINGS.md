# mtd1 `tag` (352K @ 0x40000) — senv + firmware metadata

File: `partition.bin` (360448 B, md5 `e0b5cf174eee174f7131138654b6f773`)
Format: **senv** (Ingenic serial-env) — text key/value groups, two full sets
(A/B), followed by binary tables.

## Sections (set A = active, set B = backup)

### CMDL — kernel command line
```
console=ttyS2,115200n8 mem=42880K0x0 rmem=22656K@0x29E0000 root=/dev/ram0 rw
rdinit=/linuxrc mtdparts=jz_sfc:256K(boot),352K(tag),2240K(kernel),3008K(rootfs),
1728K(system),192K(config),32K(usr),64K(ae),256K(audio),32K(usr_bak),32K(vd),8M@0(all)
lpj=6955008 quiet
```
(U-Boot appends senv groups + `lzo_size/rd_start/rd_size/ubootV=V027` at boot;
see `sd_output/probe.log` for the live cmdline.)

### ENVI (senv variables) — set A (active)
```
[HW]
ae_auto_learn=1   init_vw=2304  init_vh=1296   nrvbs=1
mode=0            select_mode=1               is_h264=0   (H.265 pipeline)
pkg=149           uart1=1                     MoveRectNums_x=16  MoveRectNums_y=10
adc_value=110     ext_devfunction1=2          close_led=0  person_det=0
[UBIA]
main_bitrate=768  sub_bitrate=384             vide_flip=3
ai_vol=57         ao_vol=55                   md_level=4   battery_cam=1
debug
person_level=2    time_format=0               osd_show=1
ModelNum=2254     vi_notalk=50                ptz_tp=1     ac_freq=1
workmode=0        again=122
[IR]
ir_mode=auto
```
Set B (backup slot): `init_vw=1920 init_vh=1080`, `main_bitrate=512
sub_bitrate=256`, `vide_flip=0`, `ai_vol=65 ao_vol=80`, `md_level=0`,
`battery_cam=0` — a different (default) profile; the A/B pair lets OTA roll
product parameters back.

### BTIF (boot interface geometry)
`kernel=2240K@0x98000 rootfs=3008K@0x2C8000`

### GPIO/feature flags
`ATA`, `BB`, `RED_LED`, `HIGH_LIGHT`, `VBUS`, `BOOT` — board feature table
parsed by U-Boot/app.

### FWIF — firmware identity
```
ZRT_release_202012231043_root_dell-Precision-Tower-3431
[VERSION] ver=CAMERA_SOC_T31Z_mis2008_4.7.2_V111
```
Build string reveals the vendor's build farm (dell-Precision-Tower-3431) and
that the base release tree is a **ZRT** product line from 2020-12-23 (the
running app fw 1.0.19.23 is newer; FWIF text was evidently not rewritten by
the last OTA).

### Trailing binary tables
After `eenv;` the partition holds binary blobs (AE/ISP tuning tables and the
RISC-V coprocessor parameter block — strings `riscv_param_t` and `tiziano`
appear in the region). The T31's second-core "coprocessor" receives its init
parameters from here. Not yet parsed field-by-field (low priority: read-only
from the app's perspective).

## Notes

- `ModelNum=2254` matches mtd10 `vd` field @0x48 (u32 LE 0x08CE).
- `ae_auto_learn=1` enables the mtd7 `ae` auto-learn snapshot ring (see
  `mtd7_ae/FINDINGS.md`).
- This partition is **write-target of OTA** (`ubia_first` runs
  `flashcp /tmp/tag.bin /dev/mtd1`) — A/B slot flip happens here.
