#!/usr/bin/env python3
"""
mips_xref.py — find references to an absolute vaddr in a non-PIE MIPS32 ELF.

The unique lui+addiu/ori encoding for target T is:
    hi = (T + 0x8000) >> 16          (rounds so se16(lo) completes T)
    lo = (T - (hi << 16)) & 0xFFFF
GCC may emit the addiu/ori up to many instructions AFTER the lui (register
liveness), so the scanner looks up to MAX_BACK instructions forward.

KNOWN LIMITATIONS (hit in the wild on ubia_t31 — read before trusting "NO pair"):
1. Branch delay slots. GCC splits a 32-bit argument load across a TAKEN
   branch's delay slot (lui a0, hi) and the call's delay slot (addiu a0, lo),
   e.g.:
       beq   v0, zero, L_call    ; if (exists)
       lui   a0, 0x84            ; [branch delay slot] high half
       ...
  L_call:
       jal   system
       addiu a0, a0, lo          ; [jal delay slot] low half
   The lui is hundreds of instructions from the addiu and program-order
   "liveness" between them is meaningless (the branch skips it all). This
   scanner reports such references only when the lui happens to be within
   MAX_BACK; the ubia_test/asrdebug system() strings in ubia_t31 were
   initially misjudged "dead" this way. ALWAYS verify negatives with
   tools/mips_dump.py over the suspicious region.
2. No control-flow awareness at all: any lui in range + any same-reg addiu
   in range is accepted → false POSITIVES are possible (e.g. a lui 0x81 from
   an unrelated path feeding the same immediate). Treat hits as candidates,
   confirm by disassembly.
3. lui+ori (op 13) with hi = T>>16 is an alternative encoding for targets
   where lo < 0x8000; this scanner only uses the (T+0x8000) form plus the
   matching addiu/ori low — both forms covered when lo has bit 15 set.

Usage: mips_xref.py ELF VADDR [VADDR ...]
Env:  MAX_BACK (default 300), TEXT_START, TEXT_END, VA_OFF
"""
import os
import struct
import sys

d = open(sys.argv[1], "rb").read()
TEXT_START = int(os.environ.get("TEXT_START", "0x7570"), 16)
TEXT_END = int(os.environ.get("TEXT_END", "0x409880"), 16)
VA_OFF = int(os.environ.get("VA_OFF", "0x400000"), 16)
MAX_BACK = int(os.environ.get("MAX_BACK", "300"))

words = [struct.unpack_from("<I", d, i)[0] for i in range(TEXT_START, TEXT_END, 4)]

for t in sys.argv[2:]:
    va = int(t, 16)
    hi = (va + 0x8000) >> 16
    lo = (va - (hi << 16)) & 0xFFFF
    hits = []
    for idx, w in enumerate(words):
        if (w >> 26) == 15 and (w & 0xFFFF) == hi:
            rs = (w >> 16) & 0x1F
            for j in range(1, min(MAX_BACK, len(words) - idx)):
                w2 = words[idx + j]
                op = w2 >> 26
                if op in (8, 9, 13) and ((w2 >> 21) & 0x1F) == rs \
                        and ((w2 >> 16) & 0x1F) == rs and (w2 & 0xFFFF) == lo:
                    hits.append(TEXT_START + (idx + j) * 4 + VA_OFF)
                    break
    if hits:
        for h in sorted(set(hits)):
            print(f"{t}: va={va:#x} xref at vaddr={h:#x}")
    else:
        print(f"{t}: va={va:#x} NO lui({hi:#06x})+addiu/ori({lo:#06x}) pair")
