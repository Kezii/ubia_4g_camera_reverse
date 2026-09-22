# Flash dump artifacts — Ingenic T31 "Turret-ZL" 4G trail camera (UBIA/UBox)

Source: `artifacts/flash.bin` (8 MiB SPI NOR, dumped from the device via the SD
`ubia_test` hook, `dd if=/dev/mtdblock11`). Device UID `HSUNBJT4PMPVDO5UOPEQ`,
model `S106-4G-3MP-EU` (2254), fw 1.0.19.23, MCU 1.0.5.11, U-Boot V027.

## Flash map (from `mtdparts=jz_sfc:...` in the tag partition, verified)

| mtd | name      | size   | offset   | format                                        | extraction |
|-----|-----------|--------|----------|-----------------------------------------------|------------|
| 0   | boot      | 256K   | 0x000000 | raw U-Boot binary (V027 20230830-Turret-ZL)   | `mtd0_boot/partition.bin` |
| 1   | tag       | 352K   | 0x040000 | senv (CMDL/ENVI/BTIF/ATA/FWIF) + AE/ISP/coproc tables | `mtd1_tag/partition.bin` |
| 2   | kernel    | 2240K  | 0x098000 | uImage (LZOF / LZO1X-999)                     | `mtd2_kernel/kernel_payload.bin` → `vmlinux.bin` (3.10.14-Archon) |
| 3   | rootfs    | 3008K  | 0x2C8000 | [68B hdr][LZO1X-999][zero pad] → newc cpio (initramfs) | `mtd3_rootfs/rootfs_camera.cpio` → `rootfs/` (363 entries) |
| 4   | system    | 1728K  | 0x5B8000 | squashfs 4.0 xz                               | `mtd4_system/squashfs/` (13 files, incl. `ubia_t31`) |
| 5   | config    | 192K   | 0x768000 | JFFS2 (rw, reformatted if no `.tag`)          | `mtd5_config/jffs2/` (7 files) |
| 6   | usr       | 32K    | 0x798000 | vendor blob, magic `5A A5 6E 3C`, otherwise zero | `mtd6_usr/partition.bin` |
| 7   | ae        | 64K    | 0x7A0000 | 32×2KB `AUTO`…`AEND` AE auto-learn snapshots  | `mtd7_ae/partition.bin` |
| 8   | audio     | 256K   | 0x7B0000 | squashfs 4.0 xz (13 `.aac` notifications)     | `mtd8_audio/squashfs/` |
| 9   | usr_bak   | 32K    | 0x7F0000 | identical to usr (same MD5)                   | `mtd9_usr_bak/partition.bin` |
| 10  | vd        | 32K    | 0x7F8000 | vendor/device identity (UID, model, per-device secret) | `mtd10_vd/partition.bin` |
| 11  | all       | 8M     | 0x0      | whole device                                  | `flash.bin` |

## MD5 (partition.bin)

| mtd | size | md5 |
|-----|------|-----|
| 0 boot | 262144 | 902875b06d607b908ceb65cb7e69f9e8 |
| 1 tag | 360448 | e0b5cf174eee174f7131138654b6f773 |
| 2 kernel | 2293760 | b5c45e7333d2bcc0e45e9d56c19f85e1 |
| 3 rootfs | 3080192 | 3dfe14b9870dabdfeeeadc466fd9cd44 |
| 4 system | 1769472 | 1face44199a20df881eb8b0015e1558d |
| 5 config | 196608 | 6c29aa988149b9ba4ea5f10bd4025f04 |
| 6 usr | 32768 | 074eb8231ac91ba62e5a747e913c6bf2 |
| 7 ae | 65536 | 688694f043538db4c130dc329eca65c3 |
| 8 audio | 262144 | 9f619ccb39ce4647b052c138470c428d |
| 9 usr_bak | 32768 | 074eb8231ac91ba62e5a747e913c6bf2 (≡ usr) |
| 10 vd | 32768 | 555b9b3a35c09169a210918261d4561a |

## LZOF container layout (vendor, empirically mapped)

`[0x00] magic 89 4C 5A 4F` (rootfs: `lzo_size` u32 LE stored here instead)
`[0x04] 00 0d 0a 1a` `[0x08] 0a 10 XX 20` `[0x0c] YY 09 40 ZZ`
`[0x10..0x1f] misc/timestamp` `[0x20] name_len u16 BE` `[name]`
`[E+0..3]` `[E+4] orig_size u32 BE (vendor: 262144 = 256KB block hint)`
`[E+8] comp_size u32 BE` `[E+12..15]` — compressed data at `E+16`.

- kernel: name_len=0, data@0x32, comp=2238525, 224B payload tail.
- rootfs: name=`rootfs_camera.cpio` (18), data@0x44.
- Both decode with `lzop -dc` (rc=2 "trailing garbage" = success). The pure-Rust
  `lzo` crate fails on the vendor LZO1X-999 streams (spurious early EOM); the
  C reference decoder is required. See `tools/lzof_extract.py` (verified
  byte-identical re-extraction) and `tools/lzo_scan.c` (raw-stream
  candidate-start scanner).

## Boot chain (summary)

U-Boot (mtd0) → reads senv (mtd1, A/B sets) → decompresses kernel LZOF →
uImage → kernel 3.10.14-Archon, `root=/dev/ram0 rdinit=/linuxrc` (rootfs cpio,
mtd3) → `linuxrc` = busybox init → inittab: `sysinit mount -a`,
`sysinit /etc/init.d/rcS`, `respawn getty console 115200` → rcS:
`insmod_sfc` (jz_sfc + **ubia_unlock_flash** + jffs2 + squashfs) →
`ubia_watchdog &` → `ubia_first &` (OTA/first-boot daemon) → mdev → env exports
(TRANSFER_MODE=IIC, PRODUCT_MODE=SINGLE, SENSOR=mis2008, SOC_TYPE=SOC_T31Z) →
`/config` jffs2 mount (reformat+seed from `/config_bak` if no `.tag`) →
`/system` + `/audio` squashfs mounts → zram0 16MB swap → `insmod_mmc`
(mmc_core/jzmmc/mmc_block/fat/vfat) → **`/system/ubia_t31 &`** (telnetd is
commented out). The 4G module (SIMCOM ASR Cat1) comes up on ttyUSB0-2;
`ubia_t31` insmods its own modules, mounts the SD (`/dev/mmcblk0p1 →
/tmp/mnt/sdcard`) and runs the whole product.

## Key findings (cross-partition)

1. **SD autorun hook is REAL and in `ubia_t31`** (mtd4): function
   `ubia_get_sd_ah()` (`src/ubia_hal.c` ~line 701) runs
   `system("/tmp/mnt/sdcard/ubia_test  &")` when `ubia_test` exists on the SD
   root (also `asrdebug /dev/ttyUSB0 &`, plus `clr_crc.txt`, `ubia_record.db`,
   `ubia-extlogo-hd/sd`, `ubia-4g-asr.tmp` features). Full analysis:
   `mtd4_system/FINDINGS.md` (includes a boot-probe log excerpt as
   runtime proof).
2. **Login puzzle**: `/etc/shadow` `root::` (empty) but getty empty-password
   login failed; `/etc/passwd` root DES hash `ShRCX9PD3xxus` (salt `Sh`) not
   cracked (65 candidates). Planned bypass for exploit phase: bind-mount fake
   shadow/passwd from the `ubia_test` hook (busybox login re-reads per attempt).
3. **P2P credentials** `admin/888888` in `/config/profiles/IBT_Profiles.ini`
   (UID field is the placeholder `xxxxxxxxxxxx` — real UID in mtd10 `vd`).
4. **Per-device secret** (30 chars) stored in mtd10 `vd` @0xA8 — likely the
   HMAC/cloud signing secret for this device.
5. **Secure APN database** `/config/ubia-sec-apn.gz`: text header
   (`version: 18`, `alg: AES-CBC-128`, `keyid: 1`, `len: 20960`, `sig:
   d36ca1fe68b87af071b4428435c65bbc`) + 20960B ciphertext. Key lives in
   `ubia_t31` (deep-RE target).
6. **Vendor SIM expires** (`service_time=1786480481` ≈ 2026-08-11) → SIM swap
   mandatory for untethering. `cloud_service_expiration` gate in `ubia_t31`.
7. **OTA path exists** (ubia_first flashcp to mtd1/2/3/4; A/B slots) — expect
   possible vendor-pushed updates while tethered.

## Tools (`tools/`, see `tools/README.md`)

Analysis/extraction tools used for this dump (Python stdlib-only except
`lzo_scan.c`, which needs liblzo2):

- `lzof_extract.py` — vendor LZOF container extraction (kernel/rootfs).
- `lzo_scan.c` — raw LZO1X-999 candidate-start scanner.
- `mips_xref.py` — MIPS lui/addiu(+ori) vaddr xref scanner for `ubia_t31`
  (known limitation: cannot see arguments passed via **branch delay slots**;
  use `mips_dump.py` to confirm).
- `mips_dump.py` — minimal MIPS32 disassembler with correct branch-target
  computation (r2 MIPS support is unreliable on this binary).

Operational tooling (serial capture, SD payload, runbooks) belongs to the
private companion project and is intentionally not published here.
