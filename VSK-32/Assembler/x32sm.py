#!/usr/bin/env python3
"""
asm.py - Assembler for the cpu32 emulator (Emu/System.py, Emulator.py)

Usage:
    python asm.py input.asm -o output.bin

Instruction encoding (8 bytes, fixed width):
    [opcode:1] [a:1] [b:1] [imm16:2 LE] [extra:2 LE] [flags:1]

    imm32 is reconstructed by the CPU as:
        combined = bits_combine(extra, imm16, 16) = (extra << 16) | imm16
    So imm16 = imm32 & 0xFFFF, extra = (imm32 >> 16) & 0xFFFF.

Registers: r0-r23 (24 general purpose 32-bit registers, DwordArray(24))

See ASM_SYNTAX.md for the full instruction reference.
"""

import sys
import re
import argparse
import struct

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

INSTR_SIZE = 8  # bytes per encoded instruction

OPCODES = {
    "hlt":  1,
    "ldi":  2,
    "jmp":  3,
    "add":  4,
    "sub":  5,
    "div":  6,
    "mul":  7,
    "cmp":  8,
    "je":   9,
    "jne":  10,
    "jh":   11,
    "jl":   12,
    "mov":  13,
    "wb":   14,
    "ww":   15,
    "rb":   16,
    "rw":   17,
    "ssp":  18,
    "push": 19,
    "pop":  20,
    "call": 21,
    "ret":  22,
    "int":  23,
    "iret": 24,
    "out":  25,
    "in":   26,
    "cli":  27,
    "sti":  28,
    "xor":  29,
    "and":  30,
    "not":  31,
    "copy": 32,
    "clf":  33,
}

NUM_REGISTERS = 24


class AsmError(Exception):
    """Raised on any assembly-time error, carries line info."""
    def __init__(self, msg, line_no=None, line_text=None):
        self.line_no = line_no
        self.line_text = line_text
        if line_no is not None:
            msg = f"line {line_no}: {msg}"
            if line_text is not None:
                msg += f"\n    -> {line_text.strip()}"
        super().__init__(msg)


# --------------------------------------------------------------------------
# Tokenizing helpers
# --------------------------------------------------------------------------

REG_RE = re.compile(r"^[rR](\d+)$")


def is_register(tok):
    return bool(REG_RE.match(tok))


def reg_num(tok, line_no=None, line_text=None):
    m = REG_RE.match(tok)
    if not m:
        raise AsmError(f"Expected register, got '{tok}'", line_no, line_text)
    n = int(m.group(1))
    if not (0 <= n < NUM_REGISTERS):
        raise AsmError(
            f"Register out of range: r{n} (valid: r0-r{NUM_REGISTERS - 1})",
            line_no, line_text,
        )
    return n


def parse_int(tok, line_no=None, line_text=None):
    """Parses decimal, 0x-hex, or char-literal ('H') integers, with optional leading -."""
    t = tok.strip()

    m = CHAR_LIT_RE.match(t)
    if m:
        return ord(_unescape_char(m.group(1), line_no, line_text))

    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    try:
        if t.lower().startswith("0x"):
            val = int(t, 16)
        else:
            val = int(t, 10)
    except ValueError:
        raise AsmError(f"Invalid integer literal: '{tok}'", line_no, line_text)
    if neg:
        val = -val
    return val


CHAR_LIT_RE = re.compile(r"^'(\\.|[^'\\])'$")

_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0",
    "\\": "\\", "'": "'", '"': '"',
}


def _unescape_char(raw, line_no, line_text):
    """raw is either a single char, or a backslash-escape like \\n, \\t, \\\\, \\'."""
    if len(raw) == 1:
        return raw
    esc = raw[1]
    if esc not in _ESCAPES:
        raise AsmError(f"Unknown escape sequence '\\{esc}' in character literal", line_no, line_text)
    return _ESCAPES[esc]


def is_char_literal(tok):
    return bool(CHAR_LIT_RE.match(tok.strip()))


# --------------------------------------------------------------------------
# Line preprocessing: strip comments, find labels, split mnemonic/operands
# --------------------------------------------------------------------------

LABEL_DEF_RE = re.compile(r"^([A-Za-z_.$][A-Za-z0-9_.$]*):$")


def strip_comment(line):
    """
    Strips a trailing ';' or '#' comment, but ignores comment chars that
    appear inside a single- or double-quoted literal (e.g. db ';', 0 or
    db "a # b" must not be truncated).
    """
    in_squote = False
    in_dquote = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and (in_squote or in_dquote) and i + 1 < n:
            i += 2  # skip escaped char, it can't close or open a quote
            continue
        if not in_dquote and ch == "'":
            in_squote = not in_squote
        elif not in_squote and ch == '"':
            in_dquote = not in_dquote
        elif not in_squote and not in_dquote and ch in (";", "#"):
            return line[:i]
        i += 1
    return line


def split_operands(s):
    """
    Splits a comma-separated operand string, respecting [ ] grouping and
    single-/double-quoted literals (so 'ldi r0, ','' and 'db "a, b", 0'
    split correctly instead of breaking on the comma inside the quotes).
    """
    parts = []
    depth = 0
    in_squote = False
    in_dquote = False
    cur = ""
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and (in_squote or in_dquote) and i + 1 < n:
            cur += ch + s[i + 1]
            i += 2
            continue
        if not in_dquote and ch == "'":
            in_squote = not in_squote
            cur += ch
        elif not in_squote and ch == '"':
            in_dquote = not in_dquote
            cur += ch
        elif in_squote or in_dquote:
            cur += ch
        elif ch == "[":
            depth += 1
            cur += ch
        elif ch == "]":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip() != "":
        parts.append(cur.strip())
    return parts


class Line:
    __slots__ = ("no", "raw", "label", "mnem", "operands")

    def __init__(self, no, raw, label, mnem, operands):
        self.no = no
        self.raw = raw
        self.label = label
        self.mnem = mnem
        self.operands = operands


def preprocess(text):
    """
    Returns a list of Line objects, one per real instruction.
    Label-only lines attach their label to the *next* instruction line;
    if a label is immediately followed by end-of-file with no instruction,
    it points one-past-the-end (rare, but we allow it and resolve later).
    """
    raw_lines = text.splitlines()
    lines = []
    pending_labels = []

    for i, raw in enumerate(raw_lines, start=1):
        working = strip_comment(raw).strip()
        if working == "":
            continue

        # A line may be "label:" alone, or "label: mnem ops", or just "mnem ops"
        # Support multiple labels stacked on separate lines before an instruction.
        m = LABEL_DEF_RE.match(working)
        if m:
            pending_labels.append(m.group(1))
            continue

        # Inline label form: "label: instr ops"
        if ":" in working:
            maybe_label, rest = working.split(":", 1)
            maybe_label = maybe_label.strip()
            rest = rest.strip()
            if re.match(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$", maybe_label) and rest != "":
                pending_labels.append(maybe_label)
                working = rest

        # Now split mnemonic from operands
        sp = working.split(None, 1)
        mnem = sp[0].lower()
        operand_str = sp[1] if len(sp) > 1 else ""
        operands = split_operands(operand_str) if operand_str.strip() else []

        lines.append(Line(i, raw, pending_labels, mnem, operands))
        pending_labels = []

    if pending_labels:
        # Labels dangling at EOF with nothing after them -> point past last instr
        lines.append(Line(raw_lines and len(raw_lines) + 1 or 1, "", pending_labels, "__end__", []))

    return lines


# --------------------------------------------------------------------------
# Operand classification
# --------------------------------------------------------------------------

def is_bracketed(tok):
    return tok.startswith("[") and tok.endswith("]")


def unbracket(tok):
    return tok[1:-1].strip()


def classify_mem_operand(tok, line_no, line_text):
    """
    For a bracketed operand [X], returns:
        ('reg', regnum)   - [r1]
        ('imm', value)    - [0x1000] / [1234] / ['H']
        ('label', name)   - [my_label]
    """
    inner = unbracket(tok)
    if is_register(inner):
        return ("reg", reg_num(inner, line_no, line_text))
    if is_char_literal(inner):
        return ("imm", parse_int(inner, line_no, line_text))
    if re.match(r"^-?(0[xX][0-9A-Fa-f]+|\d+)$", inner):
        return ("imm", parse_int(inner, line_no, line_text))
    if re.match(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$", inner):
        return ("label", inner)
    raise AsmError(f"Unrecognized memory operand: '{tok}'", line_no, line_text)


# --------------------------------------------------------------------------
# Encoder
# --------------------------------------------------------------------------

class Instr:
    """One encoded instruction awaiting label resolution for imm32 fields."""
    __slots__ = ("opcode", "a", "b", "imm32", "flags", "line_no", "line_text",
                 "label_ref")

    def __init__(self, opcode, a=0, b=0, imm32=0, flags=0,
                 line_no=None, line_text=None, label_ref=None):
        self.opcode = opcode
        self.a = a
        self.b = b
        self.imm32 = imm32
        self.flags = flags
        self.line_no = line_no
        self.line_text = line_text
        # label_ref: name of a label this instruction's imm32 should resolve to
        # (patched in pass 2), or None if imm32 is already a concrete literal.
        self.label_ref = label_ref

    def pack(self):
        imm32 = self.imm32 & 0xFFFFFFFF
        imm16 = imm32 & 0xFFFF
        extra = (imm32 >> 16) & 0xFFFF
        return struct.pack(
            "<BBBHHB",
            self.opcode & 0xFF,
            self.a & 0xFF,
            self.b & 0xFF,
            imm16,
            extra,
            self.flags & 0xFF,
        )


class DataField:
    """One value inside a db/dw/dd directive: either a resolved int or a
    deferred label reference, plus the byte-width to pack it as."""
    __slots__ = ("width", "value", "label_ref")

    def __init__(self, width, value=0, label_ref=None):
        self.width = width          # 1 (db), 2 (dw), or 4 (dd)
        self.value = value
        self.label_ref = label_ref  # name of label this resolves to, or None

    def pack(self):
        v = self.value & ((1 << (self.width * 8)) - 1)
        if self.width == 1:
            return struct.pack("<B", v)
        elif self.width == 2:
            return struct.pack("<H", v)
        else:
            return struct.pack("<I", v)


class DataItem:
    """A db/dw/dd directive: one or more DataFields emitted back-to-back."""
    __slots__ = ("fields", "line_no", "line_text")

    def __init__(self, fields, line_no=None, line_text=None):
        self.fields = fields
        self.line_no = line_no
        self.line_text = line_text

    @property
    def size(self):
        return sum(f.width for f in self.fields)

    def pack(self):
        return b"".join(f.pack() for f in self.fields)


class RegionMarker:
    """A `region <addr>` directive: sets the write cursor for what follows.
    Emits no bytes itself, but is not contiguous with what came before --
    the assembler must pad/jump the output buffer to match."""
    __slots__ = ("addr", "line_no", "line_text")

    def __init__(self, addr, line_no=None, line_text=None):
        self.addr = addr
        self.line_no = line_no
        self.line_text = line_text


def resolve_value_operand(tok, line_no, line_text):
    """
    A bare value operand that can be a register, a label, an immediate, or a
    character literal ('H').
    Returns one of:
        ('reg', n)
        ('imm', value)
        ('label', name)
    """
    if is_register(tok):
        return ("reg", reg_num(tok, line_no, line_text))
    if is_char_literal(tok):
        return ("imm", parse_int(tok, line_no, line_text))
    if re.match(r"^-?(0[xX][0-9A-Fa-f]+|\d+)$", tok):
        return ("imm", parse_int(tok, line_no, line_text))
    if re.match(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$", tok):
        return ("label", tok)
    raise AsmError(f"Unrecognized operand: '{tok}'", line_no, line_text)


DIRECTIVES = {"db", "dw", "dd", "region"}
DIRECTIVE_WIDTH = {"db": 1, "dw": 2, "dd": 4}


def assemble_directive_line(ln):
    """
    Handles db/dw/dd/region. Returns a DataItem or a RegionMarker.
    """
    mnem = ln.mnem
    ops = ln.operands
    n = ln.no
    raw = ln.raw

    if mnem == "region":
        if len(ops) != 1:
            raise AsmError(f"'region' expects 1 operand, got {len(ops)}", n, raw)
        val = resolve_value_operand(ops[0], n, raw)
        if val[0] != "imm":
            raise AsmError(
                "'region' requires an immediate/hex address (no labels or registers)",
                n, raw,
            )
        return RegionMarker(val[1], line_no=n, line_text=raw)

    # db / dw / dd
    width = DIRECTIVE_WIDTH[mnem]
    if not ops:
        raise AsmError(f"'{mnem}' requires at least one value", n, raw)

    fields = []
    for tok in ops:
        # String literal: "hello" -> one byte per character (db only, makes
        # sense for dw/dd too if you want wide chars, so we allow it generally)
        if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            s = tok[1:-1]
            s = (s.replace("\\n", "\n").replace("\\t", "\t")
                   .replace("\\r", "\r").replace("\\0", "\0")
                   .replace('\\"', '"').replace("\\\\", "\\"))
            for ch in s:
                fields.append(DataField(width, value=ord(ch)))
            continue

        val = resolve_value_operand(tok, n, raw)
        if val[0] == "reg":
            raise AsmError(f"'{mnem}' cannot take a register as a value", n, raw)
        elif val[0] == "imm":
            fields.append(DataField(width, value=val[1]))
        else:  # label
            fields.append(DataField(width, label_ref=val[1]))

    return DataItem(fields, line_no=n, line_text=raw)


def assemble_line(ln):
    """
    Turns a single Line into a list of Instr (normally length 1).
    Raises AsmError on malformed syntax.
    """
    mnem = ln.mnem
    ops = ln.operands
    n = ln.no
    raw = ln.raw

    if mnem not in OPCODES:
        raise AsmError(f"Unknown instruction '{mnem}'", n, raw)
    opcode = OPCODES[mnem]

    def need(count):
        if len(ops) != count:
            raise AsmError(
                f"'{mnem}' expects {count} operand(s), got {len(ops)}", n, raw
            )

    # ---- No-operand instructions ----
    if mnem in ("hlt", "ret", "iret", "cli", "sti", "clf"):
        need(0)
        return [Instr(opcode, line_no=n, line_text=raw)]

    # ---- ldi r0, imm32 ----
    if mnem == "ldi":
        need(2)
        dest = reg_num(ops[0], n, raw)
        src = resolve_value_operand(ops[1], n, raw)
        if src[0] == "reg":
            raise AsmError("'ldi' source must be an immediate, not a register", n, raw)
        instr = Instr(opcode, a=dest, line_no=n, line_text=raw)
        if src[0] == "imm":
            instr.imm32 = src[1]
        else:
            instr.label_ref = src[1]
        return [instr]

    # ---- jmp target  (label / addr / register) ----
    if mnem == "jmp":
        need(1)
        tgt = resolve_value_operand(ops[0], n, raw)
        if tgt[0] == "reg":
            return [Instr(opcode, a=tgt[1], flags=1, line_no=n, line_text=raw)]
        instr = Instr(opcode, flags=0, line_no=n, line_text=raw)
        if tgt[0] == "imm":
            instr.imm32 = tgt[1]
        else:
            instr.label_ref = tgt[1]
        return [instr]

    # ---- add/sub/div/mul  dest, reg|imm ----
    if mnem in ("add", "sub", "div", "mul"):
        need(2)
        dest = reg_num(ops[0], n, raw)
        src = resolve_value_operand(ops[1], n, raw)
        if src[0] == "reg":
            return [Instr(opcode, a=dest, b=src[1], flags=0, line_no=n, line_text=raw)]
        instr = Instr(opcode, a=dest, flags=1, line_no=n, line_text=raw)
        if src[0] == "imm":
            instr.imm32 = src[1]
        else:
            instr.label_ref = src[1]
        return [instr]

    # ---- cmp reg_main, reg|imm ----
    if mnem == "cmp":
        need(2)
        main = reg_num(ops[0], n, raw)
        src = resolve_value_operand(ops[1], n, raw)
        if src[0] == "reg":
            return [Instr(opcode, a=main, b=src[1], flags=0, line_no=n, line_text=raw)]
        instr = Instr(opcode, a=main, flags=1, line_no=n, line_text=raw)
        if src[0] == "imm":
            instr.imm32 = src[1]
        else:
            instr.label_ref = src[1]
        return [instr]

    # ---- je/jne/jh/jl label|addr ----
    if mnem in ("je", "jne", "jh", "jl"):
        need(1)
        tgt = resolve_value_operand(ops[0], n, raw)
        if tgt[0] == "reg":
            raise AsmError(f"'{mnem}' target must be a label or address, not a register", n, raw)
        instr = Instr(opcode, line_no=n, line_text=raw)
        if tgt[0] == "imm":
            instr.imm32 = tgt[1]
        else:
            instr.label_ref = tgt[1]
        return [instr]

    # ---- mov: 4 forms ----
    if mnem == "mov":
        need(2)
        dst_tok, src_tok = ops[0], ops[1]
        dst_brk = is_bracketed(dst_tok)
        src_brk = is_bracketed(src_tok)

        # mov [imm/reg/label], reg   -> flags 0 (imm addr) or 3 (reg addr)   Register -> Memory
        if dst_brk and not src_brk:
            if not is_register(src_tok):
                raise AsmError("mov [dest], src : src must be a register", n, raw)
            src_reg = reg_num(src_tok, n, raw)
            kind, val = classify_mem_operand(dst_tok, n, raw)
            if kind == "reg":
                # Register -> Memory Register: a=src_reg(value), b=dest_reg(addr), flags=3
                return [Instr(opcode, a=src_reg, b=val, flags=3, line_no=n, line_text=raw)]
            elif kind == "label":
                # Register -> Immediate Memory (address resolved from label), flags=0
                return [Instr(opcode, a=src_reg, flags=0, label_ref=val, line_no=n, line_text=raw)]
            else:
                # Register -> Immediate Memory: a=src_reg(value), imm32=addr, flags=0
                return [Instr(opcode, a=src_reg, imm32=val, flags=0, line_no=n, line_text=raw)]

        # mov reg, [imm/reg/label]   -> flags 1 (imm addr) or 2 (reg addr)   Memory -> Register
        if not dst_brk and src_brk:
            if not is_register(dst_tok):
                raise AsmError("mov dest, [src] : dest must be a register", n, raw)
            dst_reg = reg_num(dst_tok, n, raw)
            kind, val = classify_mem_operand(src_tok, n, raw)
            if kind == "reg":
                # Memory Register -> Register: a=src_reg(addr holder), b=dest_reg, flags=2
                return [Instr(opcode, a=val, b=dst_reg, flags=2, line_no=n, line_text=raw)]
            elif kind == "label":
                # Immediate Memory (address resolved from label) -> Register, flags=1
                return [Instr(opcode, a=dst_reg, flags=1, label_ref=val, line_no=n, line_text=raw)]
            else:
                # Immediate Memory -> Register: a=dest_reg, imm32=addr, flags=1
                return [Instr(opcode, a=dst_reg, imm32=val, flags=1, line_no=n, line_text=raw)]

        raise AsmError(
            "mov requires exactly one bracketed memory operand: "
            "'mov [dest], src' or 'mov dest, [src]'", n, raw
        )

    # ---- wb/ww  [imm/reg], reg ----
    if mnem in ("wb", "ww"):
        need(2)
        dst_tok, src_tok = ops[0], ops[1]
        if not is_bracketed(dst_tok) or not is_register(src_tok):
            raise AsmError(f"'{mnem}' syntax: {mnem} [addr], reg", n, raw)
        src_reg = reg_num(src_tok, n, raw)
        kind, val = classify_mem_operand(dst_tok, n, raw)
        if kind == "reg":
            # flags=1: reg=src_reg(value,a), rega=val(b) -> addr reg
            return [Instr(opcode, a=src_reg, b=val, flags=1, line_no=n, line_text=raw)]
        else:
            instr = Instr(opcode, a=src_reg, flags=0, line_no=n, line_text=raw)
            if isinstance(val, str):
                instr.label_ref = val
            else:
                instr.imm32 = val
            return [instr]

    # ---- rb/rw  reg, [imm]  OR  reg, [reg]  (memory operand always bracketed) ----
    if mnem in ("rb", "rw"):
        need(2)
        dst_tok, src_tok = ops[0], ops[1]
        if not is_register(dst_tok):
            raise AsmError(f"'{mnem}' dest must be a register", n, raw)
        dst_reg = reg_num(dst_tok, n, raw)

        if not is_bracketed(src_tok):
            raise AsmError(
                f"'{mnem}' source must be bracketed, e.g. '{mnem} {dst_tok}, [addr]' "
                f"or '{mnem} {dst_tok}, [r1]'", n, raw
            )

        kind, val = classify_mem_operand(src_tok, n, raw)
        if kind == "reg":
            return [Instr(opcode, a=dst_reg, b=val, flags=1, line_no=n, line_text=raw)]
        else:
            instr = Instr(opcode, a=dst_reg, flags=0, line_no=n, line_text=raw)
            if isinstance(val, str):
                instr.label_ref = val
            else:
                instr.imm32 = val
            return [instr]

    # ---- ssp reg|imm ----
    if mnem == "ssp":
        need(1)
        tgt = resolve_value_operand(ops[0], n, raw)
        if tgt[0] == "reg":
            return [Instr(opcode, a=tgt[1], flags=1, line_no=n, line_text=raw)]
        instr = Instr(opcode, flags=0, line_no=n, line_text=raw)
        if tgt[0] == "imm":
            instr.imm32 = tgt[1]
        else:
            instr.label_ref = tgt[1]
        return [instr]

    # ---- push reg|imm ----
    if mnem == "push":
        need(1)
        tgt = resolve_value_operand(ops[0], n, raw)
        if tgt[0] == "reg":
            return [Instr(opcode, a=tgt[1], flags=1, line_no=n, line_text=raw)]
        instr = Instr(opcode, flags=0, line_no=n, line_text=raw)
        if tgt[0] == "imm":
            instr.imm32 = tgt[1]
        else:
            instr.label_ref = tgt[1]
        return [instr]

    # ---- pop reg ----
    if mnem == "pop":
        need(1)
        reg = reg_num(ops[0], n, raw)
        return [Instr(opcode, a=reg, line_no=n, line_text=raw)]

    # ---- call label|addr ----
    if mnem == "call":
        need(1)
        tgt = resolve_value_operand(ops[0], n, raw)
        if tgt[0] == "reg":
            raise AsmError("'call' target must be a label or address, not a register", n, raw)
        instr = Instr(opcode, line_no=n, line_text=raw)
        if tgt[0] == "imm":
            instr.imm32 = tgt[1]
        else:
            instr.label_ref = tgt[1]
        return [instr]

    # ---- int imm8 (no label) ----
    if mnem == "int":
        need(1)
        val = resolve_value_operand(ops[0], n, raw)
        if val[0] != "imm":
            raise AsmError("'int' requires an immediate interrupt number (no labels)", n, raw)
        return [Instr(opcode, a=val[1], line_no=n, line_text=raw)]

    # ---- out reg, reg|imm ----
    if mnem == "out":
        need(2)
        val_reg = reg_num(ops[0], n, raw)
        port = resolve_value_operand(ops[1], n, raw)
        if port[0] == "reg":
            return [Instr(opcode, a=val_reg, b=port[1], flags=0, line_no=n, line_text=raw)]
        elif port[0] == "imm":
            if not (0 <= port[1] <= 0xFFFF):
                raise AsmError("'out' immediate port must fit in 16 bits", n, raw)
            return [Instr(opcode, a=val_reg, imm32=port[1], flags=1, line_no=n, line_text=raw)]
        else:
            raise AsmError("'out' port cannot be a label", n, raw)

    # ---- in reg, reg|imm ----
    if mnem == "in":
        need(2)
        dst_reg = reg_num(ops[0], n, raw)
        port = resolve_value_operand(ops[1], n, raw)
        if port[0] == "reg":
            return [Instr(opcode, a=dst_reg, b=port[1], flags=0, line_no=n, line_text=raw)]
        elif port[0] == "imm":
            if not (0 <= port[1] <= 0xFFFF):
                raise AsmError("'in' immediate port must fit in 16 bits", n, raw)
            return [Instr(opcode, a=dst_reg, imm32=port[1], flags=1, line_no=n, line_text=raw)]
        else:
            raise AsmError("'in' port cannot be a label", n, raw)

    # ---- xor dest, src  (both registers) ----
    if mnem == "xor":
        need(2)
        dest = reg_num(ops[0], n, raw)
        src = reg_num(ops[1], n, raw)
        return [Instr(opcode, a=dest, b=src, line_no=n, line_text=raw)]

    # ---- and dest, src  (both registers) ----
    if mnem == "and":
        need(2)
        dest = reg_num(ops[0], n, raw)
        src = reg_num(ops[1], n, raw)
        return [Instr(opcode, a=dest, b=src, line_no=n, line_text=raw)]

    # ---- not reg  (single register, in place) ----
    if mnem == "not":
        need(1)
        reg = reg_num(ops[0], n, raw)
        return [Instr(opcode, a=reg, line_no=n, line_text=raw)]

    # ---- copy dest, src  (both registers) ----
    if mnem == "copy":
        need(2)
        dest = reg_num(ops[0], n, raw)
        src = reg_num(ops[1], n, raw)
        return [Instr(opcode, a=dest, b=src, line_no=n, line_text=raw)]

    raise AsmError(f"No encoder implemented for '{mnem}'", n, raw)


# --------------------------------------------------------------------------
# Two-pass assembler driver
# --------------------------------------------------------------------------

def assemble(text, org=0):
    """
    Assembles source text into raw bytes.
    `org` is the base load address; all label addresses (and therefore all
    label-relative jump/call/mov/etc targets) are offset by this amount.

    Supports interleaved instructions and db/dw/dd data directives, plus a
    `region <addr>` directive that simply repositions the write pointer for
    whatever comes next (like a traditional ORG directive) -- it doesn't
    care what came before or after. Any gap this leaves in the output is
    zero-filled.

    Returns (code, listing, labels, base_addr) where:
      - code is the assembled bytes, covering [base_addr, highest address
        written + its size)
      - listing is a list of (address, item, encoded_bytes) for -l output,
        item being an Instr or a DataItem
      - base_addr is the lowest address anything was written to (equal to
        `org` unless a `region` directive moved below it)
    """
    lines = preprocess(text)

    # Pass 1: encode every instruction/directive, track byte addresses,
    # collect label defs. `region` repositions the cursor; it does not
    # itself occupy space.
    items = []            # list of (addr, item) where item is Instr or DataItem
    labels = {}           # name -> address
    addr = org

    for ln in lines:
        if ln.mnem == "__end__":
            for lbl in ln.label:
                if lbl in labels:
                    raise AsmError(f"Duplicate label '{lbl}'", ln.no, ln.raw)
                labels[lbl] = addr
            continue

        if ln.mnem == "region":
            # Any labels that were pending before this directive belong at
            # the CURRENT address -- region only affects what comes AFTER
            # it, never labels sitting above it. Resolve those first, then
            # move the cursor.
            for lbl in ln.label:
                if lbl in labels:
                    raise AsmError(f"Duplicate label '{lbl}'", ln.no, ln.raw)
                labels[lbl] = addr

            marker = assemble_directive_line(ln)
            addr = marker.addr
            continue

        for lbl in ln.label:
            if lbl in labels:
                raise AsmError(f"Duplicate label '{lbl}'", ln.no, ln.raw)
            labels[lbl] = addr

        if ln.mnem in DIRECTIVES:  # db / dw / dd
            item = assemble_directive_line(ln)
            items.append((addr, item))
            addr += item.size
        else:
            encoded = assemble_line(ln)
            for ins in encoded:
                items.append((addr, ins))
                addr += INSTR_SIZE

    # Pass 2: resolve label_ref -> concrete value(s)
    for a, item in items:
        if isinstance(item, Instr):
            if item.label_ref is not None:
                name = item.label_ref
                if name not in labels:
                    raise AsmError(
                        f"Undefined label '{name}'", item.line_no, item.line_text
                    )
                item.imm32 = labels[name]
        else:  # DataItem
            for field in item.fields:
                if field.label_ref is not None:
                    name = field.label_ref
                    if name not in labels:
                        raise AsmError(
                            f"Undefined label '{name}'", item.line_no, item.line_text
                        )
                    field.value = labels[name]

    # Emit into one flat buffer covering [base_addr, end_addr). `region`
    # jumps just move where the next bytes land; any gap left behind (or
    # before, if a region moved below `org`) is zero-filled.
    if items:
        base_addr = min(a for a, _ in items)
        end_addr = max(a + (item.size if isinstance(item, DataItem) else INSTR_SIZE)
                        for a, item in items)
    else:
        base_addr = org
        end_addr = org

    out = bytearray(end_addr - base_addr)
    listing = []
    for a, item in sorted(items, key=lambda t: t[0]):
        packed = item.pack()
        off = a - base_addr
        out[off:off + len(packed)] = packed
        listing.append((a, item, packed))

    return bytes(out), listing, labels, base_addr


def format_listing(listing):
    rows = []
    rows.append(f"{'ADDR':>8}  {'BYTES':<24} SOURCE")
    rows.append("-" * 70)
    for addr, item, packed in listing:
        hexstr = packed.hex()
        hexstr = " ".join(hexstr[i:i + 2] for i in range(0, len(hexstr), 2))
        src = item.line_text.strip() if item.line_text else ""
        rows.append(f"0x{addr:06X}  {hexstr:<24} {src}")
    return "\n".join(rows)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assembler for the cpu32 emulator ISA."
    )
    parser.add_argument("input", help="Path to .asm source file")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output binary path (default: <input>.bin)"
    )
    parser.add_argument(
        "-l", "--listing", action="store_true",
        help="Print an address/bytes/source listing to stdout"
    )
    parser.add_argument(
        "--org", type=lambda s: int(s, 0), default=0,
        help="Base address the program will be loaded at in memory "
             "(offsets label addresses accordingly). Default 0."
    )
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    try:
        code, listing, labels, base_addr = assemble(text, org=args.org)
    except AsmError as e:
        print(f"Assembly failed: {e}", file=sys.stderr)
        return 1

    out_path = args.output or (args.input.rsplit(".", 1)[0] + ".bin")
    with open(out_path, "wb") as f:
        f.write(code)

    print(f"Assembled {len(listing)} item(s), {len(code)} bytes -> {out_path}")
    if base_addr != args.org:
        print(
            f"NOTE: a 'region' directive moved below --org; load this file "
            f"at address 0x{base_addr:06X}, not 0x{args.org:06X}."
        )
    elif args.org:
        print(f"Load address: 0x{base_addr:06X}")

    if labels:
        print("\nLabels:")
        for name, a in sorted(labels.items(), key=lambda kv: kv[1]):
            print(f"  0x{a:06X}  {name}")

    if args.listing:
        print()
        print(format_listing(listing))

    return 0


if __name__ == "__main__":
    sys.exit(main())
