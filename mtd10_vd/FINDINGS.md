# mtd10 `vd` (32K @ 0x7F8000) — vendor/device identity (factory-provisioned)

File: `partition.bin` (32768 B, md5 `555b9b3a35c09169a210918261d4561a`)
Format: fixed-layout struct, magic `A5 6E 3C 5A` (byte-reversed vs mtd6's
`5A A5 6E 3C`), little-endian, rest of the partition zero-filled.
Written at factory provisioning; read by the app at boot for identity/cloud
binding.

## Field map (confirmed values on this device)

| off | size | field | value |
|-----|------|-------|-------|
| 0x00 | 4 | magic | `A5 6E 3C 5A` |
| 0x04 | 4 | u32 version word | `0x0003050F` |
| 0x08 | 24 | **device UID** (NUL-padded) | `HSUNBJT4PMPVDO5UOPEQ` |
| 0x20 | 16 | factory code | `LEMNOI` |
| 0x30 | 16 | model code | `S106-4G-3MP-EU` |
| 0x40 | 4 | u32 | `0x01050596` |
| 0x44 | 4 | u32 | 8 |
| 0x48 | 4 | u32 **ModelNum** | `0x08CE` = 2254 (matches tag ENVI `ModelNum=2254`) |
| 0x4C | 4 | u32 | 49 |
| 0x6C | 4 | u32 | 49 |
| 0x8C | 8 | product tag | `ubia\nbox` |
| 0xA8 | 30 | **per-device secret** | `ZG639hsQu5czmruG28PbGjaw7g2zLlHC` |
| 0xCC | 16 | cloud portal | `portal.ubia.cn` |
| 0x11C | 4 | u32 | 110 |
| 0x120 | 4 | u32 | 120 |
| 0x124 | 4 | u32 | 220 |
| 0x128 | 4 | u32 | `0x05100900` |
| 0x12C | 4 | u32 | 1 |
| 0x138 | 4 | bytes | `01 01 01 01` |
| 0x13C | 4 | u32 | 1 |
| 0x140 | 4 | u32 | `0x329B` (12955) |
| 0x144 | 4 | u32 | 1 |
| 0x148 | 4 | u32 | `0x0095373A` |
| 0x154 | 4 | u32 | 3 |
| 0x164 | 4 | u32 | 1 |
| 0x168 | 4 | u32 | 1 |
| 0x16C | 4 | u32 | `0x9DB3D8FA` (hash-like) |
| 0x1A4 | 16 | product name | `UBox` |
| 0x1B8 | 16 | **default WiFi AP password** | `12345678` (matches AP `UBox_HSUN`/`12345678`) |
| 0x1D4 | 4 | u32 | 120 |
| 0x1D8 | 2 | u16 | 2 |
| 0x1DA | 2 | u16 | 3 |
| 0x1DC | 2 | u16 | 122 (matches tag ENVI `again=122`) |
| 0x264 | 4 | u32 | 3 |
| 0x268 | 4 | u32 | 384 (matches tag ENVI `sub_bitrate=384`) |
| 0x26C | 4 | u32 | `0x00303A25` |
| 0x27C | 4 | u32 | 2400 |
| 0x280 | 8 | bytes | `05 06 02 01 07 0E 20 00` |
| 0x288 | 4 | u32 | 1 |
| 0x294 | 4 | u32 | 1 |
| 0x2C4 | 2 | u16 | 20 |
| 0x2C6 | 2 | u16 | 20 |
| 0x2D0 | 2 | u16 | 537 |
| 0x2D2 | 2 | u16 | 1 |
| 0x2D4 | 2 | u16 | 2 |

## Key observations

- **UID** `HSUNBJT4PMPVDO5UOPEQ` is the device's identity for the cloud
  (replaces the `UID=xxxxxxxxxxxx` placeholder in
  `/config/profiles/IBT_Profiles.ini`).
- **Per-device secret @0xA8** (30 chars, base64-ish alphabet) — the prime
  candidate for the device's HMAC/cloud signing secret (pairs with
  `pjson_secret_array` / `cloud secret: %s` in `ubia_t31`). With it plus the
  request scheme, we can forge signed requests to the vendor cloud under
  this device's identity (or to a cloud we stand up with the same secret).
- Numeric tail fields mirror live product parameters (`sub_bitrate=384`,
  `again=122`) — the partition also caches device config state.
- Read-only from the app's perspective (no writer found); safe to copy for
  cloud-identity emulation in our own server.

## Untethering relevance

1. Our self-hosted P2P/cloud server should use **this UID + secret** to bind
   the camera to *our* infrastructure.
2. If the camera validates portal reachability, spoofing
   `portal.ubia.cn`-level responses with the correct HMAC signatures (scheme
   pending deep RE of `gen_signature`/`ubox_hmac_sha1`) keeps it "connected".
