# mtd6 `usr` (32K @ 0x798000) — empty vendor user-data area

File: `partition.bin` (32768 B, md5 `074eb8231ac91ba62e5a747e913c6bf2`)

```
00000000: 5aa5 6e3c 00ff 0000 ...  (all zero to end)
```

- Magic `5A A5 6E 3C` (4 bytes) + u16 LE `0x00FF` + 32 KB of zeros.
- No other non-zero bytes in the whole partition (verified by full scan).
- Purpose: user data area reserved by the vendor (SDK template); **unused on
  this device/firmware** — no strings in `ubia_t31`, `ubia_first` or any
  rootfs file reference a `usr` partition path.
- Possibly a legacy slot from the SDK's product template (the sibling `LSC`
  product uses similar scratch partitions).

## mtd9 `usr_bak`

Byte-identical to mtd6 (same MD5 `074eb8231ac91ba62e5a747e913c6bf2`) — the
"backup" copy the SDK keeps for rollback; equally empty.
