# mtd8 `audio` (256K @ 0x7B0000) — squashfs, notification sounds

File: `partition.bin` (262144 B, md5 `9f619ccb39ce4647b052c138470c428d`)
Format: squashfs 4.0 (xz) → extracted to `squashfs/` (13 AAC files).

| file | event |
|------|-------|
| `ubiaring.aac` | incoming call / ring |
| `ubiaconnected.aac` | call connected |
| `ubiapairing.aac` / `ubiapaired.aac` | P2P pairing in-progress / done |
| `ubiawrongpsk.aac` | wrong pre-shared key |
| `ubiapiralert.aac` | PIR motion alert |
| `ubialowbattery.aac` | low battery |
| `ubiaplugout.aac` | power pulled |
| `poweroff.aac` | power off |
| `reset.aac` / `resetinformed.aac` | reset (with/without prior notice) |
| `wifiapmode.aac` | switched to WiFi AP mode |

## Notes

- Read-only product assets; `ubia_first` plays some via `AUDIO_StartAo` /
  `playRingToAoFun` (serial log: `playRingToAoFun[3646] pFirstProc->
  isBatteryca…`).
- Factory audio test: `ubia_t31` looks for `ubiafactorytest.aac` on the SD
  card to run the speaker self-test (mtd4 findings).
- No security relevance.
