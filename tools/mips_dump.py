#!/usr/bin/env python3
"""Tiny MIPS32 disassembler for targeted windows (r2 MIPS output is flaky).
Usage: mips_dump.py ELF VADDR_START VADDR_END [VA_OFF]
"""
import re
import struct
import sys

REGS = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
        "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
        "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
        "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
VA_OFF = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x400000

d = open(sys.argv[1], "rb").read()
start, end = int(sys.argv[2], 16), int(sys.argv[3], 16)

LOADS = {32: "lb", 33: "lh", 34: "lwl", 35: "lwr", 36: "lw", 37: "lhu", 38: "lbu"}
STORES = {39: "sw", 41: "swl", 42: "swr", 40: "sh"}


def se16(v):
    return v - 0x10000 if v & 0x8000 else v


def dis(w, v):
    op = w >> 26
    rs = (w >> 21) & 0x1F
    rt = (w >> 16) & 0x1F
    rd = (w >> 11) & 0x1F
    sh = (w >> 6) & 0x1F
    f3 = w & 0x3F
    imm = w & 0xFFFF
    br = lambda: f"{(v + 4) + (se16(imm) << 2):#x}"
    if op == 0:  # R-type
        if w == 0:
            return "nop"
        if f3 == 0x21 and rs == 0:
            return f"move  {REGS[rd]}, {REGS[rt]}"
        if f3 == 0x25 and rs == 0:
            return f"move  {REGS[rd]}, {REGS[rt]}"
        if f3 == 0x24:
            return f"addu  {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x20:
            return f"add   {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x2a:
            return f"subu  {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x26:
            return f"sll   {REGS[rd]}, {REGS[rt]}, {sh}"
        if f3 == 0x3a:
            return f"sra   {REGS[rd]}, {REGS[rt]}, {sh}"
        if f3 == 0x30:
            return f"sllv  {REGS[rd]}, {REGS[rt]}, {REGS[rs]}"
        if f3 == 0x38:
            return f"srav  {REGS[rd]}, {REGS[rt]}, {REGS[rs]}"
        if f3 == 0x08:
            return f"jr    {REGS[rs]}" if rd == 0 else f"jr    {REGS[rd]}"
        if f3 == 0x09:
            return "jalr" + (f" {REGS[rd]}" if rd else "")
        if f3 == 0x0a:
            return "syscall"
        if f3 == 0x00:
            return "sll   zero (mult?) " + f"rs={REGS[rs]} rd={REGS[rd]} rt={REGS[rt]}"
        if f3 == 0x12:
            return "mult  " + f"{REGS[rs]}, {REGS[rt]}"
        if f3 == 0x1a:
            return "div   " + f"{REGS[rs]}, {REGS[rt]}"
        if f3 == 0x02:
            return "mfc0  " + f"{REGS[rd]}, $c0{rs}_{rt}"
        if f3 == 0x04:
            return "mthi  " + f"{REGS[rs]}"
        if f3 == 0x06:
            return "mtlo  " + f"{REGS[rs]}"
        if f3 == 0x32:
            return "xor   " + f"{REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x30:
            return "or    " + f"{REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x34:
            return "and   " + f"{REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x2c:
            return f"sltiu {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x2b:
            return f"sltu  {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if f3 == 0x01:
            return "break"
        return f"r-type f3={f3:#04x} rs={REGS[rs]} rd={REGS[rd]} rt={REGS[rt]}"
    if op == 1:
        return f"bltz  {REGS[rs]}, {br()}"
    if op == 2:
        return f"j     {(w & 0x3FFFFFF) << 2:#x}"
    if op == 3:
        return f"jal   {(w & 0x3FFFFFF) << 2:#x}"
    if op == 4:
        return f"beq   {REGS[rs]}, {REGS[rt]}, {br()}"
    if op == 5:
        return f"bne   {REGS[rs]}, {REGS[rt]}, {br()}"
    if op == 6:
        return f"blez  {REGS[rs]}, {br()}"
    if op == 7:
        return f"bgtz  {REGS[rs]}, {br()}"
    if op == 8:
        return f"addi  {REGS[rt]}, {REGS[rs]}, {se16(imm):#x}"
    if op == 9:
        return f"addiu {REGS[rt]}, {REGS[rs]}, {se16(imm):#x}"
    if op == 10:
        return f"slti  {REGS[rt]}, {REGS[rs]}, {se16(imm):#x}"
    if op == 11:
        return f"sltiu {REGS[rt]}, {REGS[rs]}, {se16(imm):#x}"
    if op == 12:
        return f"andi  {REGS[rt]}, {REGS[rs]}, {imm:#06x}"
    if op == 13:
        return f"ori   {REGS[rt]}, {REGS[rs]}, {imm:#06x}"
    if op == 14:
        return f"xori  {REGS[rt]}, {REGS[rs]}, {imm:#06x}"
    if op == 15:
        return f"lui   {REGS[rt]}, {imm:#06x}"
    if op in LOADS:
        return f"{LOADS[op]:5s} {REGS[rt]}, {se16(imm)}({REGS[rs]})"
    if op in STORES:
        return f"{STORES[op]:5s} {REGS[rt]}, {se16(imm)}({REGS[rs]})"
    if op == 44:
        return f"ll    {REGS[rt]}, {se16(imm)}({REGS[rs]})"
    if op == 49:
        return f"mfc0  {REGS[rt]}, $c0{rs}_{f3}"
    if op == 29:
        return f"jalr  {REGS[rs]}"
    if op == 30:
        return f"jr    {REGS[rs]}"
    return f"op={op:#05x} {w:#010x}"


pstart, pend = start - VA_OFF, end - VA_OFF
i = pstart
while i < pend and i + 4 <= len(d):
    w = struct.unpack_from("<I", d, i)[0]
    v = i + VA_OFF
    print(f"{v:#010x}: {w:#010x}  {dis(w, v)}")
    i += 4
