# mtd3 `rootfs` (3008K @ 0x2C8000) — initramfs (cpio in vendor LZOF)

Files:
- `partition.bin` (3080192 B, md5 `3dfe14b9870dabdfeeeadc466fd9cd44`)
- `rootfs_camera.cpio` (7435776 B) — newc cpio, 363 entries
- `rootfs/` — extracted tree

Layout: `[68B vendor hdr (lzo_size u32 LE)][3048192B LZO1X-999][31996B zero pad]`.
Patched header magic to `89 4C 5A 4F` and decoded with `lzop -dc`
(`tools/lzof_extract.py`). The cpio **is** the initramfs: kernel cmdline
`root=/dev/ram0 rw rdinit=/linuxrc`.

## Boot chain

```
U-Boot → kernel → /linuxrc (busybox init)
  inittab:
    ::sysinit:/bin/mount -a
    ::sysinit:/etc/init.d/rcS
    console::respawn:/sbin/getty -L console 115200 vt100
    ::shutdown:/bin/umount -a -r
```

`/etc/init.d/rcS` (full sequence):
1. `insmod_sfc` — insmod `jz_sfc.ko`, run **`ubia_unlock_flash`** (clears SPI
   flash write protection), insmod `jffs2.ko`, `squashfs.ko`
2. `/bin/ubia_watchdog &` (IPC watchdog daemon)
3. `cd /bin; ./ubia_first &` (first-boot/OTA daemon)
4. `echo /sbin/mdev > /proc/sys/kernel/hotplug; /sbin/mdev -s`
5. `bootup_timer start/prog_run` (hw-timing markers to `/tmp/bootup_time`)
6. env exports: `PATH=/system/bin:/bin:/sbin:/usr/bin:/usr/sbin`,
   `LD_LIBRARY_PATH=/system/lib:/usr/lib`, `TRANSFER_MODE=IIC`,
   `PRODUCT_MODE=SINGLE`, `CALLBACK_SCRIPT=` (empty), `SENSOR=mis2008`,
   `SOC_TYPE=SOC_T31Z` — also appended to `/etc/profile`
7. `hostname -F /etc/hostname`; `ifconfig lo up &`
8. `mount -t jffs2 /dev/mtdblock5 /config` — if no `/config/.tag`:
   `flash_eraseall /dev/mtd5` + reseed from `/config_bak/*` + `touch .tag`
   (the app `ubia_t31` has the same logic duplicated in C)
9. `mount -t squashfs /dev/mtdblock4 /system`, `mount -t squashfs
   /dev/mtdblock8 /audio`
10. `swappiness=100`; zram0 16MB `mkswap`+`swapon`
11. `insmod_mmc` (mmc_core, jzmmc, mmc_block, fat, vfat)
12. `bootup_timer all_done`
13. **`/system/ubia_t31 &`** — the product app
14. `#telnetd &` — **commented out** (no telnetd on stock boot)

## mdev rules (`/etc/mdev.conf`)

```
mmcblk[0-9]p[0-9]   0:0 666 @ /usr/bin/fsck_mount_mmc.sh   (mkdir /tmp/mnt/sdcard only)
mmcblk[0-9]         0:0 666 $ /usr/bin/umount_mmc.sh
```
The *actual* SD mount (`mount /dev/mmcblk0p1 /tmp/mnt/sdcard/`) is done by
`ubia_t31` in C (see mtd4 findings), not by the mdev script.

## Binaries

| file | size | role |
|------|------|------|
| `/bin/busybox` | 530924 | coreutils/init/getty/mdev/login/… (no head/tail/cksum/blockdev/nc/awk/curl/wget; has tftp, telnetd, dd, md5sum, tar, vi, top, devmem, flashcp) |
| `/bin/ubia_first` | 2883068 | first-boot/OTA daemon (see below) |
| `/bin/ubia_watchdog` | 31136 | SysV-IPC watchdog of the main app; `umount_tf_func` (SD unmount pre-reboot); `system()` reboot |
| `/bin/ubia_unlock_flash` | 5552 | reads `ubootV=` from `/proc/cmdline`, `ioctl(/dev/jz_sfc)` to clear flash write-protection |
| `/bin/to_t31` | 8638 | local admin tool: `./to_t31 <cmd>` → UDP `sendto` to main app. Commands: `clrCrc`, `showhal`, `reset_module`, `usb_update`, `setrtc`, `getrtc`, `setpirtask`, `getpirtask`, `testpirtask`, `testvpn`, `configapn` |
| `/bin/adownload-tiny` | 130748 | SIMCOM 4G module DFU loader (`aboot_tiny_*`, preamble start/stop, download file/data, callbacks) |
| `/bin/impdbg` | 174592 | Ingenic IMP (media pipeline) debug tool (semaphores, shm, `system()`) |
| `/bin/uvc_license` | 58 | UVC camera license blob |
| `/usr/bin/bootup_timer` | 4400 | hw timing markers via `/dev/mem` register reads (`%s:%d(ms)`) |
| `/usr/bin/logcat` | 26376 | vendor ULOG capture |
| `/usr/bin/tag_env_info` | 13392 | senv tag-partition reader/writer |
| `/usr/bin/{insmod_mmc,insmod_sfc,insmod_vfat,insmod_wifi,fsck_mount_mmc.sh,umount_mmc.sh,shutdown.sh}` | — | boot helper scripts (content verified: plain insmod/mkdir/killall) |
| `/sbin/flashcp` | 17588 | flash writer (used by OTA + our dump workflow) |
| `/sbin/reboot` | 65 | shell script |

`ubia_first` (OTA engine) `system()` commands — the vendor's self-update path:
```
killall -2 ubia_watchdog; touch /tmp/stopWdg
umount /system
flashcp -v /tmp/tag.bin /dev/mtd1
flashcp -v /tmp/uImage.zrt /dev/mtd2
flashcp -v /tmp/rootfs_camera.cpio.lzo /dev/mtd3
flashcp -v /tmp/system.bin /dev/mtd4
md5sum /config_bak/profiles/webrtc_profile.ini   (config drift check)
cp /config_bak/profiles/webrtc_profile.ini /config/profiles/webrtc_profile.ini
/tmp/setir 0 1 | 1 0   (IR LED control)
bootup_timer <marker> >> /tmp/bootup_time
```

## `/etc` security-relevant state

- `/etc/passwd`: `root` DES hash **`ShRCX9PD3xxus`** (salt `Sh`) — 65
  candidates tested (perl `crypt`), no match. Also a `messagebus` user (uid 0,
  shell `/bin/sh`).
- `/etc/shadow`: `root::` — **empty password field**, yet getty empty-password
  login failed in earlier probes (getty/login path discrepancy; unresolved —
  exploit-phase target).
- `/etc/profile`: standard; rcS appends the product env exports.
- `/config_bak/profiles/`: seed copy of `/config` — `IBT_Profiles.ini`
  (**P2P `USER=admin` `PASS=888888`**, `UID=xxxxxxxxxxxx` placeholder),
  `webrtc_profile.ini` (WebRTC APM: AEC v2.1.201201, AGC, HP, NS, VAD),
  `alarm.info` (24B), `ZRT_Profile_Wifi_Debug_bak.ini` (DTIM tuning).
- WiFi AP: `UBox_HSUN` / `12345678` (hostapd config for the single-camera AP
  mode).

## Modules (`/lib/modules/3.10.14-Archon/`)

`jz_sfc, jffs2, squashfs, mmc_core, jzmmc, mmc_block, fat, vfat, bcmdhd`
(Broadcom WiFi), `motor, z7682inf, gpio_spi`, alarm LED, UVC/camera stack
(cooked `videobuf2`, `configfs`, `libcomposite`, `usbcamera` — commented out
in rcS), plus unversioned copies in `/lib/modules/`.

## Runtime facts (from `sd_output/probe.log`)

- PID1 = `{linuxrc} init`; SD mounted `/dev/mmcblk0p1 /tmp/mnt/sdcard vfat
  fmask=0022 dmask=0022`; `/system` ro squashfs; `/config` rw jffs2.
- Device clock fallback `2025-02-01` until NTP sync.
- 30 s HW watchdog petted by the main app — never kill `ubia_t31`.
