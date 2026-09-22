# tools/

Analysis/extraction tools used to produce the findings in this repo.
All Python tools are stdlib-only (no pip dependencies).

## lzof_extract.py

Extract the vendor "LZOF" container (magic `89 4C 5A 4F`, see `../README.md`
for the mapped header layout) into the underlying payload.

```
python3 lzof_extract.py mtd2_kernel/partition.bin /tmp/vmlinux.bin
python3 lzof_extract.py mtd3_rootfs/partition.bin /tmp/rootfs_camera.cpio
```

(plus `--data-off/--size/--expect` for manual offsets). Verified
byte-identical against `lzop -dc` (after patching the rootfs header magic to
`89 4C 5A 4F`).

## lzo_scan.c

Brute-force scanner for a raw LZO1X-999 stream starting at an unknown offset
inside a larger blob. Uses the C reference decoder (`lzo1x_decompress_safe`),
which is required — high-level Rust `lzo` crate decoders stop early on the
vendor streams (spurious EOM).

```
gcc -O2 -o lzo_scan lzo_scan.c -llzo2
./lzo_scan <file> [maxoff] [expectsize]
```

## mips_xref.py

Find references to an absolute vaddr in a non-PIE MIPS32 ELF (the `ubia_t31`
app binary in `mtd4_system/squashfs/`). Encodes the target as the unique
`lui`/`addiu`/`ori` pair and scans all instructions.

```
python3 mips_xref.py mtd4_system/squashfs/ubia_t31 0x83E440
```

**Known limitation**: it only sees references assembled from consecutive
instructions in program order. GCC emits function arguments using **branch
delay slots** (e.g. `lui` in the taken branch's delay slot, `addiu` in the
`jal`'s delay slot), which this scan misses — this caused an earlier
false-negative on the SD hook's `system()` strings. Always confirm with
`mips_dump.py`.

## mips_dump.py

Minimal MIPS32 disassembler with correct branch-target computation, for
targeted windows (radare2's MIPS support is unreliable on this binary).

```
python3 mips_dump.py mtd4_system/squashfs/ubia_t31 0x4B1810 0x4B1A80
```

`ubia_t31` layout: vaddr = paddr + 0x400000; no `$gp` (no `.reginfo`), so all
data references are absolute `lui` pairs — which is what makes `mips_xref.py`
work.
