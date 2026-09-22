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

| Item           | Value                                                          |
|----------------|----------------------------------------------------------------|
| Model          | S106-4G-3MP-EU (ModelNum 2254, package 149)                    |
| SoC            | Ingenic T31, MIPS32 Xburst 1.08 GHz, "Turret-ZL"               |
| Companion MCU  | HiSilicon hi3861 (PMIC, PIR, BLE); UART `ttyS1`                |
| Sensor         | `mis2008`, 3 MP (2304×1296); I2C address 0x30 on `i2c0`        |
| Device UID     | `HSUNBJT4PMPVDO5UOPEQ` (stored in mtd10)                       |
| Firmware       | 1.0.19.23 (SoC "liteos"); MCU 1.0.5.11                         |
| Bootloader     | U-Boot V027, build 20230830-Turret-ZL                          |
| Kernel         | 3.10.14-Archon                                                 |
| Hostname       | `Zeratul` (vendor-set in `/etc/hostname`)                      |
| Memory         | 64 MB DDR (43 MB OS + 22 MB video reserve)                     |
| 4G module      | SIMCOM EC618 Cat.1, USB; AT port `/dev/ttyUSB1`                |
| Serial console | UART `ttyS2` @ 115200 (visible on USB as `/dev/ttyACM0`)       |
| Wi-Fi          | none on this variant (see "Wi-Fi leftovers" below)             |
| Vendor APN     | `bicsapn`                                                      |

## Hardware architecture

The camera is a multi-chip product. The 4G module is the only uplink on
this variant. The board has no Wi-Fi radio.

```
                 Ingenic T31 SoC
     MIPS32 Xburst 1.08 GHz + RISC-V Tiziano core
     (image pipeline, H.265, audio, 30 s WDT)
  I2C0     |       | ttyS1       | USB        | ttyS2
  --------+   +----+------+ +----+-------+  +-- console
  mis2008 |   | hi3861 MCU | | SIMCOM     |
  3 MP    |   | PMIC, PIR, | | EC618 4G   |
  sensor  |   | BLE, SoC   | | Cat.1      |
          |   | power gate | | module     |
          |   +------------+ +------------+
```

| Chip                        | Role                                                        | Evidence in this repo                                              |
|-----------------------------|-------------------------------------------------------------|--------------------------------------------------------------------|
| Ingenic T31 ("Turret-ZL")   | Video SoC: image pipeline, H.265 encoder, audio, main app   | `mtd2_kernel/`, `mtd4_system/`                                     |
| RISC-V "Tiziano" core (in SoC) | ISP 3A loops + person detection                          | `tx_isp_riscv_*`, "Riscv frame count" in `dump/dmesg.txt`          |
| `mis2008` CMOS sensor, 3 MP | Image capture at 2304×1296, ~30 fps                         | "mis2008 chip found @ 0x30 (i2c0)" in `dump/dmesg.txt`             |
| HiSilicon hi3861 MCU        | Battery + charging (PMIC), PIR motion input, BLE radio, SoC power gate | `HI3861`, `mcu_*` strings in `ubia_t31`; `/tmp/update_hi3861.bin` |
| SIMCOM EC618, 4G Cat.1      | Cellular uplink                                             | `cfg_ec618_usb.ini`, `agentboot.bin`, `format_ec618.json` in `mtd4_system/squashfs/` |
| XM25QH64C SPI NOR           | 8 MB flash, quad mode                                       | "the flash name is XM25QH64C" in `dump/dmesg.txt`                  |
| 64 MB DDR                   | 43 MB for the OS, 22 MB for video buffers                   | Kernel RAM map; `rmem=22656K@0x29E0000` in the kernel command line |

### Video path

1. U-Boot reads the newest AE auto-learn snapshot from mtd7 and applies
   the initial exposure, including the IR LED PWM duty, before the
   kernel starts.
2. The `mis2008` driver (build 2023-05-17) probes the sensor on `i2c0`,
   address 0x30. The sensor power enable is GPIO 17 ("Set vbus gpio
   17").
3. Raw frames enter the T31 VIC (video input controller). The VIC
   accepts MIPI CSI-2 (four channels, configurable lane count) and DVP
   (8/10-bit, including Sony mode). The firmware does not log which
   mode this sensor uses.
4. The ISP pipeline ("tx-isp", build H20220209a) runs on the RISC-V
   core, not on the MIPS core. It executes the 3A loops (AE, AWB, DPC,
   DRC, gamma) and the day/night switch.
5. At boot the kernel loads a 159 KB calibration blob (sensor library
   date 2023-04-28). The tail of the mtd1 tag partition holds the
   binary AE/ISP and RISC-V coprocessor tables (unparsed).
6. The H.265 encoder (config `is_h264=0`) produces the main (768 kbit)
   and sub (384 kbit) streams. The hardware nodes (`/dev/tx-isp`,
   `/dev/isp-m0`, `/dev/framechan%d`, `/dev/soc_vpu`, `/dev/ipu`) are
   owned by `ubia_first`.
7. Motion detection (16×10 grid) and the Ingenic person-detection
   library ("PersonDet v0.0.3", build 2024-10-24) gate the recording
   and the cloud reporting.

### MCU (HiSilicon hi3861)

- In deep sleep the SoC is off. The hi3861 stays on at low power and
  gates the power of the SoC and of the 4G module
  (`mcu_ctr_4gT31Power`).
- Wake sources: PIR motion, scheduled re-power
  (`mcu_set_delay_poweron`), charging, and the cloud relay knock.
- The "MCUHOST" thread in `ubia_t31` owns the UART (`ttyS1`). The
  frames start with 0x7B and end with 0x7A.
- The MCU has its own firmware (1.0.5.11 here). At boot the SoC reads
  the version and the CRC. The SoC can update the MCU from
  `/tmp/update_hi3861.bin` (`ubia_ota_update_hi3861`).
- The PIR mode exists in three synced copies: `vd.PirMode`,
  `usr.PirMode`, `mcu.PirMode`.
- The local admin tool `/bin/to_t31` sends 16-byte UDP messages to
  127.0.0.1:88; the MCUHOST thread relays them to the MCU. Commands:
  `clrCrc`, `showhal`, `reset_module`, `usb_update`, `setrtc`,
  `getrtc`, `setpirtask`, `getpirtask`, `testpirtask`, `testvpn`,
  `configapn`.

### 4G module (SIMCOM EC618)

- A USB-attached Cat.1 module. Ports: `ttyUSB0` (debug console; the
  `asrdebug` SD hook attaches here), `ttyUSB1` (AT commands),
  `ttyACM0` (DFU port).
- DFU toolchain in `/system`: `DownloadCLI`, `agentboot.bin`,
  `cfg_ec618_usb.ini`, `format_ec618.json`, `adownload-tiny`.
- The ASR voice model is updatable from the SD
  (`ubia-4g-asr.tmp` → `/tmp/asr-update.bin` + the DFU flow).
- The module reports the power and battery state. The SoC ADC channel
  17 reads the battery voltage divider (senv `adc_value=110`).

### SoC internals (T31)

- CPU: MIPS32 "Xburst" @ 1.08 GHz (CCLK 1080 MHz), with FPU.
- RISC-V "Tiziano" coprocessor: ISP 3A loops + person detection.
- DDR 64 MB: 0x0–0x29DFFFF (42880 K) for the OS; 22656 K @ 0x29E0000
  reserved for video buffers.
- 30-second hardware watchdog (`t31_wdt`); `ubia_watchdog` keeps it
  alive.
- Audio: I2S engine. The microphone feeds the recording and the
  built-in voice recognition (a `kiss_fft`-based engine in `ubia_t31`,
  plus a "wow" wake-word server). The speaker plays the 13 prompts
  from mtd8 and the siren.

### UART map

| Port  | Function                                                  |
|-------|-----------------------------------------------------------|
| `ttyS0` | `ubia_t31` opens it at boot ("uart0_init ok"); role not identified |
| `ttyS1` | hi3861 MCU (0x7B…0x7A frames)                           |
| `ttyS2` | Console @ 115200 = `/dev/ttyACM0` on USB                |

### Wi-Fi leftovers (no radio on this variant)

This variant has no Wi-Fi hardware. The image keeps files for sibling
variants:

- `insmod_wifi` (loads `bcmdhd.ko`) exists in `/usr/bin`, but rcS
  never calls it and the module is not in the image.
- `nvram.txt` for the AP6212A (a BCM43291-based 2.4 GHz chip) sits in
  `/lib/firmware`.
- `esp32_sdio.ko`, `btsdio.ko`, `bluetooth.ko` sit in `/system` — the
  T23 sibling line uses an ESP32 over SDIO.
- The BLE pairing code in `ubia_t31` refers to the hi3861 radio.
- The `UBox_HSUN`/`12345678` AP identity in mtd10 is a cached default
  for the Wi-Fi variants.

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
| `dump/dmesg.txt`      | U-Boot console tail + kernel boot log (serial capture)                |
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

## Related work

The protocol side of these cameras (P4P cloud, its cipher, NAT
traversal, LAN streaming) is documented in a separate open project for
the sibling product (Ingenic T23): `ubox-p4p`. Same SDK family, same
hi3861 MCU. Its docs decode the MCU UART opcode map and the cloud
protocol. Offsets differ between the T23 and the T31. This repository
stays on the hardware and the on-device reverse engineering.

## What is not in this repository

- The serial console tooling, the exploit payload, and the project plan
  stay private.
- The original `ubia_test` script also had an optional remote-shell
  part. The published `dump/ubia_test` contains only the probe and the
  dump.
