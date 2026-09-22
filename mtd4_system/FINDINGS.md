# mtd4 `system` (1728K @ 0x5B8000) — squashfs, the product partition

File: `partition.bin` (1769472 B, md5 `1face44199a20df881eb8b0015e1558d`)
Format: squashfs 4.0 (xz) → extracted to `squashfs/` (13 files).

## File list

| file | size | role |
|------|------|------|
| `ubia_t31` | 5341968 | **the main product app** (all features) |
| `DownloadCLI` | 73016 | SIMCOM ASR Cat1 (EC618) 4G module flash tool |
| `adownload-tiny` | 130748 | symlink to `/bin/adownload-tiny` (DFU backend) |
| `agentboot.bin` | 35676 | 4G module bootloader image for DFU |
| `cfg_ec618_usb.ini` | 678 | DownloadCLI USB DFU config |
| `format_ec618.json` | 732 | 4G module partition/format table |
| `mkfs.vfat` | 82919 | FAT formatter (SD card reformat) |
| `ubia-4g-apn.txt` | 114390 | APN database (signature-checked, versioned) |
| `alarm_led.ko` | 6405 | alarm LED driver (insmod'd by the app) |
| `bluetooth.ko`, `btsdio.ko`, `esp32_sdio.ko` | — | BT (ESP32 over SDIO) drivers |

## `ubia_t31` — binary facts

- MIPS32 `ET_EXEC`, dynamic (uClibc), vaddr = paddr + `0x400000`, entry
  `0x40aff0`. **No `$gp`** (no `.reginfo`; uClibc `_start` never sets it) →
  all data references are absolute `lui`+`addiu` pairs.
- `.text` vaddr `0x407570..0x809880` (2.6 MB), `.rodata` vaddr `0x809940`,
  `.data` `0x926340`, `.plt` `0x914740..0x915C80`, `.got.plt` `0x925dec`
  (0x550).
- PLT: 338 imported symbols. Security-relevant: `system`, `popen`, `execl`,
  `dlopen`, `access`, `stat`, `socket`/`connect`/`send`/`recv`/`sendto`/
  `recvfrom`, `fopen`/`fread`/`fwrite`/`fscanf`, `opendir`/`readdir`,
  `shm_open`/`sem_open`, full pthread, C++ iostream, and an embedded
  **voice-recognition engine** (`kiss_fft_*`, `vrr_*`, `mmsq_*`,
  `_createVoiceRecognizer2`, `StartRecognition`, `_onMatchFrequency`,
  `ateVoiceRecognizer2` — wake-word/voice-command for the "wow" server).
- Log format: `printf`-based ULOG: `[%9lu][ULOG_INFO]%s[%d] msg`
  (`0x914880`=printf, `0x914ff0`=fflush, `0x915bb0`=**system**,
  `0x915810`=**access**, `0x914c90`=sleep, `0x914c30`=remove,
  `0x914ce0`=snprintf).

---

## ⭐ SD-card autorun hook — `ubia_get_sd_ah()` (THE untethering primitive)

Location: vaddr **`0x4B1810`** (one large HAL function), log source
`"src/ubia_hal.c"` (~line 701), banner string @`0x83E4EC`:
`ubia_get_sd_ah #######--------------`.

All checks are `access(path, 701)` — mode `701 & 7 = 5` = **R_OK|X_OK**
(file exists, readable, executable). Each hit runs a `system()` command; the
checks form a **cascade** (earlier hits do not suppress later ones):

| # | SD file (card root) | action (exact strings) |
|---|---------------------|------------------------|
| 0 | — (unconditional, after state counter ≥3) | `system("mount")` @`0x4B1878` (str `0x817354`) |
| 0 | — | `remove("/tmp/mnt/sdcard/video/record_file.tmp")` @`0x4B184C` (str `0x83E35C`) |
| 1 | `asrdebug` | `system("/tmp/mnt/sdcard/asrdebug /dev/ttyUSB0 &")` — check xref `0x4B18B8` → call `0x4B2008`; cmd str `0x83E3FC` |
| 2 | `ubia_test` | `system("/tmp/mnt/sdcard/ubia_test  &")` — check xref `0x4B18D0` → call `0x4B1FF8`; cmd str `0x83E440` |
| 3 | `ubia_record.db` | exists → skip DB-init call `0x4FDC9C` (called when **absent** and counter ≥4) |
| 4 | `clr_crc.txt` | `system("rm -rf /config/UpdateCrc.ini")` — str `0x83E654`; log `rm -rf /config/UpdateCrc.ini` (`0x83E606`/`0x83E63C`) / `no /tmp/mnt/sdcard/clr_crc.txt` (`0x83E676`/`0x83E6B0`) |
| 5 | `ubia-extlogo-hd` | if file-CRC(SD) ≠ file-CRC(`/config/ubia-extlogo-hd`) and state ≥3: `system("cp /tmp/mnt/sdcard/ubia-extlogo-hd /config/ubia-extlogo-hd")` — call `0x4B2140`, cmd str `0x83E794`; CRC fn `0x49E8F4`, log `main update crc1=%u,crc2=%u` (`0x83E726`/`0x83E75C`) |
| 6 | `ubia-extlogo-sd` | same for sub-logo: `system("cp /tmp/mnt/sdcard/ubia-extlogo-sd /config/ubia-extlogo-sd")` — call `0x4B2100`, cmd str `0x83E878`; log `sub update crc1=%u,crc2=%u` (`0x83E80A`/`0x83E840`) |
| 7 | `ubia-4g-asr.tmp` | 4G-module ASR voice-model update block `0x4B1A78..0x4B1C44` (pairs with `mv /tmp/mnt/sdcard/ubia-4g-asr.tmp /tmp/asr-update.bin` and the 4G DFU flow) |

### Control-flow proof (why the hook is real)

The `system()` command pointers are assembled with **branch delay slots**:
GCC split each 32-bit load across the taken branch's delay slot (`lui a0,
0x84`) and the `jal`'s delay slot (`addiu a0, a0, lo`):

```
0x4B18D0: addiu a0, a0, -0x1BDC      ; a0 = "/tmp/mnt/sdcard/ubia_test"
0x4B18D4: jal   0x915810             ; access
0x4B18DC: beq   v0, zero, 0x4B1FF8   ; access()==0 (exists) → jump
0x4B18E0: lui   a0, 0x84             ; [delay slot] high half for the call below
0x4B1FF8: jal   0x915BB0             ; system()
0x4B1FFC: addiu a0, a0, -0x1BC0      ; [delay slot] a0 = 0x83E440 = "/tmp/mnt/sdcard/ubia_test  &"
0x4B2000: beq   zero, zero, 0x4B18E4 ; fall through to the next check (cascade)
```
(and `0x4B18C4 → 0x4B2008` with `0x83E3FC` for `asrdebug`; `0x4B1A18 →
0x4B2018` with `0x83E654` for `clr_crc`).

**Tooling caveat**: a pure program-order liveness scan *misses* this pattern
(the `lui` sits in a branch delay slot far from the `addiu`), which is why an
earlier pass wrongly concluded the `&`-strings were dead. They are live and
executed. (`tools/mips_xref.py` documents this limitation; verify hook
strings with `tools/mips_dump.py`.)

### Runtime confirmation

`sd_output/probe.log` (single boot, SD inserted):
```
=== ubia_test probe run @ Sat Feb  1 00:00:01 UTC 2025 ===
invoked_as=/tmp/mnt/sdcard/ubia_test pid=230 ppid=1
parent_cmdline: init
uptime: 3.52 0.20
… 232 root 1444 S {ubia_test} /bin/sh /tmp/mnt/sdcard/ubia_test
```
ppid=1 is exactly the expected signature of `system("… &")` from a daemon:
sh forks the script, exits, script is reparented to init. Uptime 3.52 s sits
right after `ubia_t31` (pid 156) starts and mounts the SD. **The hook fires on
boot (and presumably on SD re-insertion) with root privileges.**

### Implications for the untethering plan

- `sd_payload/ubia_test` (probe + later: rshell/bind-mounts) is the primary
  persistence primitive — **confirmed, not assumed**.
- `asrdebug` on the SD gives a second, serial-bound script channel
  (`/dev/ttyUSB0` = 4G module AT port — caution: it talks to the modem).
- The hook runs as root from the app's context; keep it fast/backgrounded
  (30 s HW watchdog is petted by `ubia_t31`).

---

## Cloud / P2P / authentication surface

- Endpoints (`*.ubianet.com`): `v6ota`, `oam`, `oam-api-us`, `device-api`,
  `device-log`, `lite`, `ufront-eu`, `ufront-as`, `portal.cn`, `portal.us`,
  `m1..m6`, `a1..a5` (multi-cloud region list).
- OTA URL: `http://%s/%s/firmware/%s` (plain HTTP).
- Auth: `X-Ubia-Auth-Signature: type=hmac-sha1&sign=%s`; `OAM-SIGN`/`LITE-SIGN`
  headers; body `{"hmac":"%s","params":%s}`; `gen_signature` with
  base64/urlencode variants; `ubox_hmac_sha1`; S3-v2-style object auth
  (`x-amz-*` strings, "Invalid signing date in Authorization header").
- **Per-provider key/secret table**: `pjson_secret_array` (JSON array of
  provider key/secret pairs); log `cloud secret: %s`.
- Crypto lib: **PolarSSL** (not OpenSSL).
- `cloud_service_expiration=%d` gate — the vendor SIM service
  (`service_time=1786480481` ≈ 2026-08-11) expires; SIM swap mandatory.
- Alexa: `alexaID`, `loginID:admin` (voice-assistant pairing path).
- P4P tunneling symbols present (same technique as the sibling `ubox-p4p`
  product; offsets differ).
- `ubia_wow_loadserver` — loads "wow" (wake-word) servers from config.

## SD lifecycle (app-owned)

`insmod %s%s` (module list), `mkdir -p /tmp/mnt/sdcard`,
`mount /dev/mmcblk0p1   /tmp/mnt/sdcard/`, `mount -o remount,rw
/tmp/mnt/sdcard`, `umount /tmp/mnt/sdcard`, `ls /tmp/mnt/sdcard`,
`mkfs.vfat` (card reformat). File layout written by the app:
`video/%d%d%02d%02d*`, `snaps/%d%d%02d%02d*`, `HDPIC/…` (date-bucketed dirs),
`record.jpg`, `log/`, `logfile.txt`/`logfile.gz`, `wificonnected.aac`,
`ubiafactorytest.aac`, `ubia-extlogo-hd/sd`, `ubia-4g-apn.txt`,
`ubia-sec-apn.gz`, `ubia-4g-asr.tmp`, `ubia-4g.b`.

## 4G module (SIMCOM ASR Cat1, EC618 family)

- AT on `/dev/ttyUSB1`; DFU on `/dev/ttyACM0` via `DownloadCLI` +
  `adownload-tiny` + `agentboot.bin` + `cfg_ec618_usb.ini` +
  `format_ec618.json`.
- **App reboots if `/dev/ttyACM0` missing >30 s** (module watchdog).
- APN from `/system/ubia-4g-apn.txt` (apn_signature check, versioned);
  secure APN DB `/config/ubia-sec-apn.gz` (AES-128-CBC, header in mtd5
  findings). `to_t31 configapn` can reconfigure the APN live.
- Module update: `cp /system/DownloadCLI /tmp/; …; ./DownloadCLI -p
  /dev/ttyACM0 … -B "BL AP CP" -r` (full BL/AP/CP reflash).

## Other subsystems observed in strings

- MCU host protocol (I2C/UART, `TRANSFER_MODE=IIC`): `USART_Send_Data`,
  `Uart_CMD_Handle` (`READY RESP:81 02 0c f3`), `MCUHOST_Thread` — the
  front-end MCU (PIR, battery, LED, IR) is a co-processor.
- Day/night (`dayNightFirstState`), PIR tasks, PTZ (`ptztype 1`,
  `MoveRectNums`), battery, alarm LED, IR LED (`/tmp/setir`), temperature OSD.
- `ubia-sec-apn` / `ubia-4g-apn` management, `rm -rf /config/ubia-sec-apn.*`
  (APN DB reset feature).
- `killall`/`reboot` paths coordinated with `ubia_watchdog`
  (`/tmp/stopWdg`).

## Status / next

- ✅ SD hook fully resolved (above).
- ⬜ Deep RE still open: HMAC key material (per-provider table + vd secret),
  S3 key/secret handling, `cloud_service_expiration` gate logic, P4P protocol
  internals, MCU host opcodes, getty/login password path, AES key for
  `ubia-sec-apn.gz` (keyid 1).
- ⬜ `ubia_first` deep RE (OTA verify/CRC flow, `uImage.zrt` naming).
