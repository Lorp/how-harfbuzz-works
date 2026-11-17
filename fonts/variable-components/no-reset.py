"""Writes a copy of a VARC font with the RESET_UNSPECIFIED_AXES flag
cleared on every component of some glyphs, for the chapter "Variable
components".

usage: python3 no-reset.py IN.ttf OUT.ttf GLYPH...

Only that one bit of each component's flags changes. It is bit 0, the
lowest bit of the flags' last byte whatever the flags' length, so no record
changes size and nothing else in the font moves. The table checksum isn't
updated: HarfBuzz doesn't check it.
"""
import importlib.util
import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("varc_dump", os.path.join(HERE, "varc-dump.py"))
varc_dump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(varc_dump)


def main(src, dst, *glyphs):
    v = varc_dump.Varc(src)
    table_offset = next(t.offset for tag, t in v.font.reader.tables.items() if tag == "VARC")
    data = bytearray(open(src, "rb").read())
    for gid in map(int, glyphs):
        for c, _ in v.components(gid):
            _, n = varc_dump.varint(v.data, c["start"])
            last = table_offset + c["start"] + n - 1
            data[last] &= ~1 & 0xFF
    open(dst, "wb").write(data)


if __name__ == "__main__":
    main(*sys.argv[1:])
