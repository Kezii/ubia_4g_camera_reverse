# mtd7 `ae` (64K @ 0x7A0000) — AE auto-learn snapshot ring

File: `partition.bin` (65536 B, md5 `688694f043538db4c130dc329eca65c3`)
Format: **32 × 2 KB records**, each framed by magic `AUTO` (head) … `AEND`
(0xE4 tail). Records 0–14 are live; 15–31 are erased (`0xFF`) — a 15-slot
ring of Auto-Exposure learning snapshots, enabled by `ae_auto_learn=1` in
tag ENVI (mtd1) and exercised at boot (`UBIA_AE_AutoLearn_Init ok` in the
serial log; `AeUbiaDat_to_first_func` in `ubia_first`).

## Record layout (2 KB, little-endian)

| off | size | field | rec0 value |
|-----|------|-------|-----------|
| 0x00 | 4 | magic | `AUTO` |
| 0x04 | 4 | u32 (mode/id) | 0x0708 (1800) |
| 0x08 | 4 | u32 (entry count?) | 0x000A (10) |
| 0x0C | 4 | u32 | 0x0800 (2048) |
| 0x10 | 16 | entry 1 `{min u32, max u32, flag u32, val u32}` | {0, 0xFFFFFFFF, 1, 0x0718 (1816)} |
| 0x20 | 16 | entry 2 `{min, max, flag, val}` | rec0: {0, 0xFFFFFFFF, 1, 0}; rec1: {1, 0xFFFFFFFF, 2, 0} |
| 0x30 | 4 | **u32 timestamp (epoch)** | rec0 `0x697E978C` = 2026-02-01 00:00:12 UTC; rec1 6 s earlier |
| 0x34 | 0x28 | zeros | — |
| 0x5C | 4 | u32 flag | 1 |
| 0x60 | 0x44 | 7 × u32 (0xFFFFFFFF = unused) | — |
| 0xA8 | 4 | u32 flag | 1 |
| 0xAC | 0x38 | zeros | — |
| 0xE4 | 4 | tail magic | `AEND` |
| 0xE8 | 0x58 | zeros | — |
| 0x140 | 32 | **16 × u16 illuminance ladder** | `2866 1E4D 16BA 110C 1106 0E98 0C83 0A92 07FA 07FA 07FA 04A8 03E2 033D 0000 0000` (monotone-decreasing gain/illuminance curve) |
| 0x17C | 0x84 | zeros | — |

## Interpretation

- Each record = one learned AE state (scene condition → exposure params),
  timestamped. The two 0x10/0x20 entries look like day/night (or min/max
  brightness-band) conditions; `val` at 0x1C carries the learned parameter
  (1816 in rec0).
- The 16-step u16 table at 0x140 is the learned **illuminance → exposure
  curve** (identical in rec0/rec1 — the factory default ladder, not yet
  re-learned per scene).
- Timestamps sit on the device's default clock (2026-02-01 00:00:xx UTC) →
  snapshots were captured during factory first-boot before any NTP sync.
  15 snapshots ≈ a repeated factory test sequence.
- Written by the AE auto-learn path in `ubia_t31` (`UBIA_AE_AutoLearn_*`);
  consumed at startup to pre-seed exposure instead of re-converging.

## Notes

- Pure data partition — safe to ignore for untethering (worst case: camera
  re-learns AE after a wipe).
- Field semantics above are best-effort (structure inferred from values +
  vendor AE code symbols); exact bit meaning of the 0x04/0x08/0x0C words
  unconfirmed.
