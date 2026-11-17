"""Writes FONT.views.json for this chapter's fonts, for the `table` blocks.

usage: python3 views.py FONT.ttf ...

The `trak`, `ankr` and STAT views are fontTools' TTX, as in
tools/font-views.py. fontTools doesn't decode `kerx` (its TTX is a hex
dump), so the `kerx` view is a listing made here from the compiled bytes,
field by field, in the order and with the names of Apple's TrueType
Reference Manual. Nothing in either view is written by hand.
"""
import hashlib
import importlib.util
import json
import os
import struct
import sys

from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "font_views", os.path.join(HERE, "..", "..", "tools", "font-views.py"))
font_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font_views)

COVERAGE = [(0x80000000, "Vertical"), (0x40000000, "CrossStream"),
            (0x20000000, "Variation"), (0x10000000, "Backwards")]
ACTION_TYPES = {0: "control point actions", 1: "anchor point actions",
                2: "control point coordinate actions"}


def lookup(data, at, names):
    """An AAT lookup table; only format 8, the one these fonts use."""
    fmt, first, count = struct.unpack_from(">HHH", data, at)
    assert fmt == 8, fmt
    values = struct.unpack_from(f">{count}H", data, at + 6)
    return ", ".join(f"{names[first + i]}: {v}" for i, v in enumerate(values))


def kerx_view(font):
    data = font.reader["kerx"]
    names = font.getGlyphOrder()
    version, _, n = struct.unpack_from(">HHL", data, 0)
    out = [f"kerx version {version}, {n} subtable{'s' if n != 1 else ''}"]
    at = 8
    for i in range(n):
        length, coverage, tuples = struct.unpack_from(">LLL", data, at)
        fmt = coverage & 0xFF
        bits = [name for bit, name in COVERAGE if coverage & bit] or ["none"]
        out.append(f"subtable {i}: format {fmt}, length {length}")
        out.append(f"  coverage: {' '.join(bits)}")
        out.append(f"  tupleCount: {tuples}")
        st = at + 12
        if fmt == 0:
            npairs = struct.unpack_from(">L", data, st)[0]
            out.append(f"  nPairs: {npairs}  (then searchRange, entrySelector, rangeShift)")
            for j in range(npairs):
                l, r, v = struct.unpack_from(">HHh", data, st + 16 + 6 * j)
                if tuples:
                    vals = struct.unpack_from(f">{tuples}h", data, at + (v & 0xFFFF))
                    out.append(f"    {names[l]} {names[r]}: offset {v & 0xFFFF} → {list(vals)}")
                else:
                    out.append(f"    {names[l]} {names[r]}: {v}")
        elif fmt == 2:
            row_width, lo, ro, ao = struct.unpack_from(">LLLL", data, st)
            out.append(f"  rowWidth: {row_width}")
            out.append(f"  left classes:  {lookup(data, at + lo, names)}")
            out.append(f"  right classes: {lookup(data, at + ro, names)}")
            vals = struct.unpack_from(">9h", data, at + ao)
            out.append(f"  array: {list(vals)}")
        elif fmt == 6:
            flags, rows, cols, ro, co, ao, vo = struct.unpack_from(">LHHLLLL", data, st)
            out.append(f"  flags: {flags:#x}, rowCount: {rows}, columnCount: {cols}")
            out.append(f"  row indices:    {lookup(data, at + ro, names)}")
            out.append(f"  column indices: {lookup(data, at + co, names)}")
            vals = struct.unpack_from(f">{rows * cols}h", data, at + ao)
            out.append(f"  array: {list(vals)}")
        elif fmt == 4:
            nclasses, co, so, eo, flags = struct.unpack_from(">LLLLL", data, st)
            atype, aoff = flags >> 30, flags & 0xFFFFFF
            out.append(f"  nClasses: {nclasses}")
            out.append(f"  classes: {lookup(data, st + co, names)}")
            for s in range(2):
                row = struct.unpack_from(f">{nclasses}H", data, st + so + 2 * nclasses * s)
                out.append(f"  state {s}: entries by class {list(row)}")
            nentries = (aoff - eo) // 6
            for e in range(nentries):
                ns, fl, ai = struct.unpack_from(">HHH", data, st + eo + 6 * e)
                what = []
                if fl & 0x8000:
                    what.append("Mark")
                what.append("no action" if ai == 0xFFFF else f"action {ai}")
                out.append(f"  entry {e}: newState {ns}, {', '.join(what)}")
            out.append(f"  flags: action type {atype} ({ACTION_TYPES[atype]}), actions at {aoff}")
            if atype == 2:
                vals = struct.unpack_from(">4h", data, st + aoff)
                out.append(f"  action 0: marked ({vals[0]}, {vals[1]}), current ({vals[2]}, {vals[3]})")
            else:
                vals = struct.unpack_from(">2H", data, st + aoff)
                what = "point" if atype == 0 else "anchor"
                out.append(f"  action 0: marked glyph's {what} {vals[0]}, current glyph's {what} {vals[1]}")
        at += length
    return "\n".join(out)


def write_views(font_path):
    with open(font_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    font = TTFont(font_path)
    tables = {tag: font_views.table_view(font_path, tag)
              for tag in ("trak", "ankr", "STAT") if tag in font}
    if "kerx" in font:
        tables["kerx"] = kerx_view(font)
    out = os.path.splitext(font_path)[0] + ".views.json"
    with open(out, "w") as f:
        json.dump({"font": os.path.basename(font_path), "sha256": digest,
                   "lookups": {}, "tables": tables}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        write_views(path)
