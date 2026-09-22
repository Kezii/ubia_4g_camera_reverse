# mtd2 `kernel` (2240K @ 0x98000) — uImage, 3.10.14-Archon

Files:
- `partition.bin` (2293760 B, md5 `b5c45e7333d2bcc0e45e9d56c19f85e1`) — raw partition
- `kernel_payload.bin` (2238799 B) — LZOF container payload (after uImage header)
- `vmlinux.bin` (4798416 B) — decompressed kernel image

## Container

uImage (LZMA/LZOF wrapper) containing the vendor **LZOF container** with
**LZO1X-999** compressed data (see `artifacts/README.md` for the container
layout; name_len=0, data@0x32, comp=2238525, 224B payload tail). Decoded with
`lzop -dc` (C reference decoder; the pure-Rust `lzo` crate fails on these
streams with a spurious early EOM).

## Kernel

- `Linux 3.10.14-Archon` — vendor build of 3.10 (Ingenic "Archon" = T31 board
  name), PREEMPT, built `Thu Mar 6 18:29:09 CST 2025`, compiler
  `Ingenic r2.3.3 2016.12 GCC 4.7.2` (same toolchain as the userland).
- MIPS32, little-endian, `lpj=6955008` (~695 MHz).
- Memory: 64MB SoC RAM, `mem=42880K`, `rmem=22656K@0x29E0000` (reserved for
  ISP/codec DMA).

## Config facts relevant to untethering

- **No `CONFIG_KEXEC`** → kexec-based root escape is dead.
- Serial console on `ttyS2` @115200 (the UART we use; `/dev/ttyACM0` on the
  host is the same line via the USB-serial bridge — careful: the 4G module
  also claims `/dev/ttyACM0` at runtime, which is a *different* interface on
  the module, see mtd4 findings).
- Root is a ramdisk (`root=/dev/ram0 rdinit=/linuxrc`); the cpio initramfs
  comes from mtd3.
- `mtdparts=jz_sfc:...` defines the 11 partitions (map in `README.md`).
- `quiet` — boot log suppressed on the console by default.

## Status

Fully extracted. No further RE planned on the kernel itself (stock 3.10; no
interesting vendor modules in-tree — the proprietary ISP/codec drivers are
modules in the rootfs `/lib/modules/3.10.14-Archon/`).
