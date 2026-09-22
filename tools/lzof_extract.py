#!/usr/bin/env python3
"""
lzof_extract.py — extract Ingenic T31 (UBIA/Turret-ZL) "LZOF" containers.

FORMAT (reverse-engineered, verified against stock lzop 1.04 output):

    off   size  field
    0x00  4     LZOF magic 0x894c5a4f  (bytes 89 4c 5a 4f)
               *** vendor rootfs partition stores the LZO stream size here
                   (little-endian u32) instead of the magic ***
    0x04  4     version (00 0d 0a 1a)
    0x08  4     0a 10 XX 20   (XX: 0x40 stock lzop, 0x30 vendor 999)
    0x0c  4     YY 09 40 ZZ   (ZZ: 0x01 default, 0x03 LZO1X-999)
    0x10  4     09 03 00 00   (999) / 05 03 00 00 (default)
    0x14  4     misc
    0x18  4     misc (mtime-ish)
    0x1c  4     misc
    0x20  2     name_len (BIG-endian u16)
    0x22  var   name
    E     1     u8
    E+1   3     u8[3]
    E+4   4     u32 BE  (stock: orig size;  vendor: 262144 = 256 KB block hint)
    E+8   4     u32 BE  (stock: comp size;  vendor: ~first block comp size)
    E+12  4     u8[4]
    E+16  ...   LZO1X data stream (standard bitstream; decodes with plain
                lzo1x_decompress even when labeled "LZO1X-999" by lzop -l)

NOTE on decoders: the vendor streams are standard LZO1X at the bitstream
level; liblzo2's lzo1x_decompress (system `lzop`) decodes them fully. The
pure-Rust `lzo` crate (lzo_rust/) stops early on a spurious EOM and must
NOT be used for these streams — only for locating candidate block starts.

USAGE:
    lzof_extract.py FILE OUT [options]

    auto  (default)  detect: raw LZOF (magic) or size-prefixed rootfs variant
    --magic          force: treat FILE as a raw LZOF container (lzop -dc)
    --data-off N     force: LZO data starts at N (default: computed)
    --size N         force: LZO stream length (default: from u32 @0 or EOF)
    --expect N       warn if decompressed size != N

EXAMPLES:
    lzof_extract.py artifacts/mtd3_rootfs/partition.bin out.cpio --expect 7435776
    lzof_extract.py artifacts/mtd2_kernel/kernel_payload.bin out.vmlinux
"""
import argparse
import struct
import subprocess
import sys
import tempfile
import os

MAGIC = b"\x89LZO"
# common header bytes [4:20] shared by stock and vendor 999 containers
COMMON = bytes.fromhex("000d0a1a0a10")  # 0x04..0x09 prefix check


def parse_header(d: bytes):
    """Return (name_len, name, header_len, data_off) for a LZOF-style header."""
    name_len = struct.unpack_from(">H", d, 0x20)[0]
    name = d[0x22 : 0x22 + name_len]
    e = 0x22 + name_len
    data_off = e + 16
    return name_len, name, data_off


def extract(d: bytes, out: str, data_off=None, size=None, expect=None):
    # case 1: raw LZOF container (kernel payload, or anything lzop made)
    if d[:4] == MAGIC:
        blob = d
        mode = "raw LZOF"
    # case 2: vendor size-prefixed (rootfs partition)
    elif len(d) > 0x40 and d[4:10] == COMMON:
        lzo_size = struct.unpack_from("<I", d, 0)[0]
        name_len, name, hoff = parse_header(d)
        if data_off is None:
            data_off = hoff
        if size is None:
            size = lzo_size
        print(f"[i] size-prefixed container: name={name!r} lzo_size={lzo_size} "
              f"data_off={data_off} hdr={hoff}")
        blob = bytearray(d[:data_off] + d[data_off : data_off + size])
        blob[0:4] = MAGIC  # patch magic
        mode = "size-prefixed (magic patched)"
    else:
        # case 3: bare stream with forced offsets
        if data_off is None:
            sys.exit("unrecognized container; use --data-off/--size")
        if size is None:
            size = len(d) - data_off
        blob = bytearray(d)
        mode = "bare stream"

    with tempfile.NamedTemporaryFile(suffix=".lzo", delete=False) as f:
        f.write(bytes(blob))
        tmp = f.name
    try:
        with open(out, "wb") as o:
            r = subprocess.run(["lzop", "-dc", tmp], stdout=o,
                               stderr=subprocess.PIPE)
        err = r.stderr.decode(errors="replace").strip()
        if err:
            print(f"[i] lzop: {err}")
        # lzop rc 2 = decompressed OK with warnings (e.g. trailing garbage)
        if r.returncode not in (0, 2):
            sys.exit(f"lzop failed rc={r.returncode}")
    finally:
        os.unlink(tmp)

    got = os.path.getsize(out)
    print(f"[+] {mode}: wrote {out} ({got} bytes)")
    if expect is not None and got != expect:
        print(f"[!] size mismatch: got {got}, expected {expect}")
        return 1
    print(f"[+] head: {open(out,'rb').read(16).hex(' ')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("USAGE:")[0])
    ap.add_argument("file")
    ap.add_argument("out")
    ap.add_argument("--data-off", type=lambda s: int(s, 0))
    ap.add_argument("--size", type=lambda s: int(s, 0))
    ap.add_argument("--expect", type=lambda s: int(s, 0))
    a = ap.parse_args()
    d = open(a.file, "rb").read()
    print(f"[i] {a.file}: {len(d)} bytes")
    sys.exit(extract(d, a.out, a.data_off, a.size, a.expect))


if __name__ == "__main__":
    main()
