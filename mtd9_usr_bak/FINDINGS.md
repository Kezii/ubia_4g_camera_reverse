# mtd9 `usr_bak` (32K @ 0x7F0000) — backup of mtd6 `usr`

File: `partition.bin` (32768 B, md5 `074eb8231ac91ba62e5a747e913c6bf2`)

Byte-identical to mtd6 (same MD5): magic `5A A5 6E 3C` + u16 `0x00FF` +
zeros. The SDK keeps a backup copy of the user-data area for rollback;
neither partition is used by this firmware (see `mtd6_usr/FINDINGS.md`).
