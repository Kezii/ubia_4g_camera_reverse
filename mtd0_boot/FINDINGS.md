# mtd0 `boot` (256K @ 0x0) — U-Boot V027

File: `partition.bin` (262144 B, md5 `902875b06d607b908ceb65cb7e69f9e8`)
Format: **raw U-Boot binary** (not a uImage — this is the first-stage bootloader).

## Identity (from strings)

- Version banner: `V027`, build date `20230830`, product `Turret-ZL`.
- `devname=volpi`.
- Ingenic T31 (JZT31) boot: loads senv from the `tag` partition, picks A/B
  slot, assembles the kernel command line, decompresses the kernel/rootfs
  LZOF containers.

## Behaviour relevant to untethering

- **A/B boot logic**: kernel/rootfs slot selection; a `kernel2`/`rootfs2`
  fallback set exists (U-Boot variables), used by the OTA flow (`ubia_first`
  writes `mtd1` tag + `mtd2` kernel + `mtd3` rootfs + `mtd4` system, then the
  tag A/B state is flipped on next boot).
- **cmdline assembly**: base from tag `CMDL` section + senv `[HW]/[UBIA]/[IR]`
  groups appended; `ubootV=V027` token added (read later by
  `ubia_unlock_flash` to decide unprotect behaviour).
- **LZOF decompression** with error string `lzok err` — the same vendor LZOF
  container format as rootfs/kernel (see `artifacts/README.md`).
- **BTIF** (Boot Interface) table: `kernel=2240K@0x98000 rootfs=3008K@0x2C8000`
  — partition geometry used to load+place the images in RAM.
- RAM layout: `mem=42880K`, `rmem=22656K@0x29E0000` (reserved/ISP memory),
  `rd_start=0x80600000 rd_size=0x717600 lzo_size=3048192` (rootfs ramdisk).

## Realistic "own OS" path

- `kexec` is impossible (no `CONFIG_KEXEC` in the 3.10.14 kernel).
- QEMU is impossible (no T31 machine; proprietary ISP/codec IP).
- The practical path is to **replace the kernel partition content** with a
  custom uImage (same LZOF container) — U-Boot only validates size/layout, and
  A/B slots (`kernel2`/`rootfs2`) give a safe fallback. The senv tag partition
  (mtd1) is where slot state and cmdline live.
