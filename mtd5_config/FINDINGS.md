# mtd5 `config` (192K @ 0x768000) — JFFS2, rw product state

File: `partition.bin` (196608 B, md5 `6c29aa988149b9ba4ea5f10bd4025f04`)
Format: JFFS2 (little-endian, raw nodes). Extracted with `jefferson -d
mtd5_config/jffs2 mtd5_config/partition.bin` → 7 files.

## Contents (as found on this device)

| file | size | content |
|------|------|---------|
| `.tag` | 0 | existence marker — missing ⇒ rcS/app reformats + reseeds the whole partition from `/config_bak` |
| `profiles/alarm.info` | 24 | binary: u32[0]=1, u32[4]=1 (alarm/PIR enable flags) — **not** the all-zero config_bak seed |
| `profiles/IBT_Profiles.ini` | 125 | `[P2P] USER=admin PASS=888888 UID=xxxxxxxxxxxx` (UID placeholder — real UID lives in mtd10 `vd`), `[Audio] playVol=60`, `[POWER] PIR=off`, `[VIDEO] FILP=off FrameRate=middle IRCut=off` |
| `profiles/webrtc_profile.ini` | 863 | WebRTC APM: AEC (v2.1.201201, drift comp off), AGC (kFixedDigital, target -4 dBFS), HP on, LE off, NS kHigh, VAD off |
| `profiles/ZRT_Profile_Wifi_Debug_bak.ini` | 62 | `[WIFI] KEEPALIVE=60 ARP=60`, `[SUIT] DTIM=1000`, `[SINGLE] DTIM=600` (ZRT product-line leftover) |
| `UpdateCrc.ini` | 36 | `u32 LE 0x749F8A7A` + 32 zero bytes. The **firmware-update CRC** record; the SD `clr_crc.txt` hook does `rm -rf /config/UpdateCrc.ini` to reset the OTA acceptance check (see mtd4 findings) |
| `ubia-sec-apn.gz` | 21083 | **encrypted APN database** — see below |

## `ubia-sec-apn.gz` — secure APN DB

Text header (ASCII, then `\n\n`, then ciphertext):
```
version: 18
content-encoding: gzip-enc
alg: AES-CBC-128
keyid: 1
type: 0
len: 20960
sig: d36ca1fe68b87af071b4428435c65bbc
```
- `len: 20960` = ciphertext size (AES-128-CBC, IV handling TBD in deep RE).
- `sig` = integrity tag (scheme TBD — likely MD5/HMAC over plaintext or
  header).
- Pipeline: ciphertext → AES-128-CBC decrypt (key selected by `keyid: 1`
  from the key table inside `ubia_t31`) → gzip decompress → APN list text.
- The app can replace it from the SD: `cp /tmp/mnt/sdcard/ubia-sec-apn.gz
  /config/ubia-sec-apn.gz;sync` (mtd4 strings) — **a crafted file on the SD
  could inject APNs**, but only if we can produce a valid ciphertext/signature
  (needs the key + sig scheme from deep RE).
- Related: plain APN list `/system/ubia-4g-apn.txt` (114 KB, signature
  checked + versioned) is the fallback.

## Notes

- Partition is **wiped on factory reset / missing `.tag`** — anything stored
  here is not persistent across a reset.
- `jefferson` preserved odd JFFS2 mode bits on `UpdateCrc.ini`
  (`---xr----T`); chmod'd locally for reading (device semantics unchanged).
