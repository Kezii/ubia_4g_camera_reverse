# 4G trail camera — full flash dump and analysis

This repository is a full flash dump of a 4G trail camera, plus a written
analysis of every partition. The camera is a low-cost outdoor security
camera. The SoC is an Ingenic T31 (MIPS32). The vendor SDK is UBIA/UBox
(codename "Turret-ZL").

The camera sends all of its data to a vendor cloud over 4G. It also uses a
vendor SIM. The long-term goal of this work is to run the camera on your
own SIM and your own server. This repository is the evidence base for that
work: the raw dump, the unpacked partitions, the analysis, and the tools.

**Start here. Then read the `FINDINGS.md` of the partition you care
about.** The most interesting one is `mtd4_system/` (main app + the SD
auto-run hook).

## Device

| Item         | Value                                                        |
|--------------|--------------------------------------------------------------|
| Model        | S106-4G-3MP-EU (ModelNum 2254, package 149)                  |
| SoC          | Ingenic T31, MIPS32, "Turret-ZL"                             |
| Device UID   | `HSUNBJT4PMPVDO5UOPEQ` (stored in mtd10)                     |
| Firmware     | 1.0.19.23 (MCU 1.0.5.11)                                     |
| Bootloader   | U-Boot V027, build 20230830-Turret-ZL                        |
| Kernel       | 3.10.14-Archon                                               |
| Hostname     | `Zeratul` (vendor-set in `/etc/hostname`)                    |
| 4G module    | SIMCOM ASR Cat.1 (EC618); AT port `/dev/ttyUSB1`             |
| Serial console | UART `ttyS2` @ 115200 (visible on USB as `/dev/ttyACM0`)  |
| Wi-Fi        | Broadcom (`bcmdhd`); AP name `UBox_HSUN`, password `12345678`|
| Vendor APN   | `bicsapn`                                                    |

## How the dump was made

No open ports. No login. No exploit.

The vendor firmware has a debug feature. At boot, the main app checks for
a file named `ubia_test` in the root of the SD card. If the file exists,
the app runs it as root:

```sh
system("/tmp/mnt/sdcard/ubia_test  &")
```

The code proof is in `mtd4_system/FINDINGS.md`.

### Steps

1. Format a microSD card as FAT32.
2. Copy `dump/ubia_test` to the root of the card. Keep the name
   `ubia_test` (no extension).
3. Insert the card. Turn the camera on.
4. The app mounts the card at `/tmp/mnt/sdcard`, then runs the script.
   The script runs as root, about 3.5 s after boot.
5. The script writes `probe.log` (system information) to the card. It
   also copies the whole flash (`/dev/mtdblock11`, 8 MiB) to
   `flash.bin` on the card.
6. Turn the camera off. Remove the card. Copy `flash.bin` and
   `probe.log` to a computer.

The dump takes about 23 s (351 KB/s). The script only reads the device.
It only writes to the SD card. It never kills a process. It never
reboots. It never changes the config. All of the work runs in a
background subshell, so it blocks neither the boot path nor the 30 s
hardware watchdog.

### What the script found

Excerpts from `dump/probe.log` (the full output is that file).

Who ran the script:

```
invoked_as=/tmp/mnt/sdcard/ubia_test pid=230 ppid=1
parent_cmdline: init
uptime: 3.52 0.20
uid=0(root) gid=0(root)
```

`ppid=1` is the expected signature of `system("... &")`: the shell forks
the script and exits; the script attaches to init.

File systems at that moment:

```
/dev/mtdblock5   /config           jffs2    rw
/dev/mtdblock4   /system           squashfs ro
/dev/mmcblk0p1   /tmp/mnt/sdcard   vfat     rw
```

Running processes (the important ones):

```
    1 root {linuxrc} init
   49 root /bin/ubia_watchdog
   50 root ./ubia_first
  156 root /system/ubia_t31
  157 root /sbin/getty -L console 115200 vt100
  232 root {ubia_test} /bin/sh /tmp/mnt/sdcard/ubia_test
```

Accounts:

```
# /etc/passwd
root:ShRCX9PD3xxus:0:0:root:/:/bin/sh
# /etc/shadow
root::10933:0:99999:7:::
```

(shadow shows an empty password for root, but an empty-password login
fails — see "Key findings".)

The dump itself:

```
--- dumping /dev/mtdblock11 -> /tmp/mnt/sdcard/flash.bin ---
8388608 bytes (8.0MB) copied, 23.284592 seconds, 351.8KB/s
dd_exit=0
0b047e954b15153dc2d6b499467d580d  /tmp/mnt/sdcard/flash.bin
```

Useful facts from the same log: the busybox build has `tftp` and
`telnetd`, but no `nc`, no `curl`, no `wget`, no `awk`, no `head`. The
log date (2025-02-01) is the device clock fallback; the clock syncs after
NTP.

## Repository layout

| Path                  | Contents                                                              |
|-----------------------|-----------------------------------------------------------------------|
| `flash.bin`           | the full 8 MiB flash dump                                             |
| `mtd0_boot/` … `mtd10_vd/` | one directory per partition: `partition.bin` (raw copy), `FINDINGS.md` (analysis), extracted files where applicable |
| `dump/ubia_test`      | the SD card script that made the dump                                 |
| `dump/probe.log`      | the output of that script                                             |
| `tools/`              | the analysis and extraction tools (see `tools/README.md`)             |

## Flash map

Verified against the `mtdparts=` kernel parameter and the `/proc/mtd`
output in `dump/probe.log`.

| mtd | name    | size  | offset   | Contents                                                        |
|-----|---------|-------|----------|-----------------------------------------------------------------|
| 0   | boot    | 256K  | 0x000000 | U-Boot (V027 20230830-Turret-ZL)                                |
| 1   | tag     | 352K  | 0x040000 | senv config (two A/B sets) + AE/ISP/coprocessor tables          |
| 2   | kernel  | 2240K | 0x098000 | uImage in a LZOF container → `kernel_payload.bin` → `vmlinux.bin` |
| 3   | rootfs  | 3008K | 0x2C8000 | LZOF container → `rootfs_camera.cpio` → `rootfs/` (363 entries) |
| 4   | system  | 1728K | 0x5B8000 | squashfs → `squashfs/` (13 files, including `ubia_t31`)         |
| 5   | config  | 192K  | 0x768000 | JFFS2 → `jffs2/` (7 files: profiles, secure APN database)       |
| 6   | usr     | 32K   | 0x798000 | vendor blob (magic `5A A5 6E 3C`), then zeros                   |
| 7   | ae      | 64K   | 0x7A0000 | 32 AE auto-learn snapshots (15 in use)                          |
| 8   | audio   | 256K  | 0x7B0000 | squashfs → `squashfs/` (13 `.aac` voice files)                  |
| 9   | usr_bak | 32K   | 0x7F0000 | identical to `usr`                                              |
| 10  | vd      | 32K   | 0x7F8000 | device identity: UID, model, per-device secret                  |
| 11  | all     | 8M    | 0x000000 | the whole flash (`flash.bin`)                                   |

## LZOF container (kernel + rootfs)

The vendor compresses the kernel and the rootfs in a custom container
("LZOF", magic `89 4C 5A 4F`). The rootfs partition stores a size (LZO
stream length, u32 little-endian) in place of the magic.

The layout, found from the containers in this dump:

```
[0x00] magic 89 4C 5A 4F   (rootfs: lzo_size u32 LE here instead)
[0x04] 00 0d 0a 1a
[0x08] 0a 10 XX 20         (XX: 0x40 stock lzop, 0x30 vendor 999)
[0x0c] YY 09 40 ZZ         (ZZ: 0x03 = LZO1X-999)
[0x20] name_len u16 BE, name, ...
[E+4]  orig_size u32 BE    (vendor: 262144 = 256 KB block hint)
[E+8]  comp_size u32 BE
[E+16] LZO1X data
```

Both streams decode with `lzop -dc` (return code 2, "trailing garbage",
means success). The pure-Rust `lzo` crate stops too early on these
streams. Use the C decoder. Tools: `tools/lzof_extract.py` and
`tools/lzo_scan.c` (see `tools/README.md`).

## Boot chain (summary)

U-Boot (mtd0) reads the config from mtd1 and decompresses the kernel
(mtd2). The kernel starts with `root=/dev/ram0 rdinit=/linuxrc`: the
initramfs from mtd3. busybox init runs `/etc/init.d/rcS`.

rcS does the following, in order:

1. Load kernel modules (including `ubia_unlock_flash`, which unlocks the
   SPI flash for writing).
2. Start `ubia_watchdog` (keeps the 30 s hardware watchdog alive) and
   `ubia_first` (OTA and first-boot daemon).
3. Start mdev (device nodes).
4. Mount `/config` (JFFS2, read-write). If `/config` has no `.tag` file,
   the system reformats it and copies in seed files.
5. Mount `/system` and `/audio` (squashfs, read-only).
6. Create 16 MB of swap on zram0.
7. Load the SD card drivers (mmc + vfat).
8. Start `/system/ubia_t31` — the main app.

`ubia_t31` loads its own modules, mounts the SD card, and runs the whole
product: video, motion detection, 4G, cloud, P2P. A `telnetd` exists in
busybox, but rcS does not start it.

## Key findings

1. **The SD auto-run hook is real, and it runs as root.** The app checks
   the SD card for `ubia_test` (and several other files) and runs
   them. That is the feature this dump used. Full code proof:
   `mtd4_system/FINDINGS.md`.
2. **Per-device secret in mtd10** (30 characters, offset 0xA8). It is
   probably the HMAC signing secret for the cloud.
3. **P2P credentials** `admin/888888` in `/config/profiles/
   IBT_Profiles.ini` (the UID field is a placeholder; the real UID is in
   mtd10).
4. **Secure APN database** `/config/ubia-sec-apn.gz`: AES-128-CBC,
   version 18, with a signature header. The key is inside `ubia_t31`.
5. **The vendor SIM expires** (service end about 2026-08-11). You must
   swap the SIM to free the camera from the vendor cloud.
6. **An OTA path exists**: `ubia_first` writes mtd1/2/3/4 with
   `flashcp`. The vendor can push updates while the camera is on their
   SIM.
7. **Login puzzle**: `/etc/shadow` shows an empty password for root, but
   an empty-password login fails. The DES hash `ShRCX9PD3xxus` (salt
   `Sh`) in `/etc/passwd` does not match. Not cracked yet (65 candidates
   tried).

## Tools

See `tools/README.md` for usage. Summary:

| Tool                   | Purpose                                                          |
|------------------------|------------------------------------------------------------------|
| `tools/lzof_extract.py`| unpacks the LZOF container (kernel/rootfs)                        |
| `tools/lzo_scan.c`     | finds a raw LZO1X stream at an unknown offset (needs liblzo2)    |
| `tools/mips_xref.py`   | finds references to an address inside `ubia_t31`                 |
| `tools/mips_dump.py`   | disassembles a window of `ubia_t31`                              |

## What is not in this repository

- The serial console tooling, the exploit payload, and the project plan
  stay private.
- The original `ubia_test` script also had an optional remote-shell
  part. The published `dump/ubia_test` contains only the probe and the
  dump.
- A sibling product (a UBIA "ubox" P4P camera) is documented in a
  separate project (`ubox-p4p`). The protocol and techniques transfer.
  The offsets do not.
