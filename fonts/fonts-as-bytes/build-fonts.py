"""Builds the test fonts for the chapter "Fonts as bytes".

usage: python3 build-fonts.py   (from this folder; build.sh runs it)

bytes.ttf is built from bytes.fea by tools/build-test-font.py. The other
fonts are copies of it with the bytes of one field changed, which no
feature file can express:

  null-coverage.ttf     lookup 0's coverage offset is 0 (a null offset)
  unknown-format.ttf    lookup 0's Coverage table says it is format 9
  outside.ttf           lookup 0's coverage offset points past the table
  null-coverage-f1.ttf  lookup 1 (a format 1 subtable) has a null coverage
                        offset

collection.ttc is a TrueType Collection of bytes.ttf and null-coverage.ttf.

Checksums are left as they are: HarfBuzz doesn't check them.
"""
import os
import struct
import subprocess
import sys
from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "tools")


def table_offset(data, tag):
    num_tables = struct.unpack_from(">H", data, 4)[0]
    for i in range(num_tables):
        rec = 12 + 16 * i
        if data[rec:rec + 4] == tag:
            return struct.unpack_from(">I", data, rec + 8)[0]
    raise KeyError(tag)


def subtable(data, gsub, lookup_index):
    """Where subtable 0 of a lookup is, in the file."""
    lookup_list = gsub + struct.unpack_from(">H", data, gsub + 8)[0]
    lookup = lookup_list + struct.unpack_from(">H", data, lookup_list + 2 + 2 * lookup_index)[0]
    return lookup + struct.unpack_from(">H", data, lookup + 6)[0]


def patched(src, out, lookup_index, change):
    data = bytearray(open(src, "rb").read())
    gsub = table_offset(data, b"GSUB")
    st = subtable(data, gsub, lookup_index)
    change(data, st)
    open(out, "wb").write(data)
    print(out)


def set_u16(at, value):
    return lambda data, st: struct.pack_into(">H", data, st + at(data, st), value)


def main():
    os.chdir(HERE)
    subprocess.run([sys.executable, os.path.join(TOOLS, "build-test-font.py"),
                    "bytes.fea", "bytes.ttf"], check=True)
    coverage_field = lambda data, st: 2
    coverage_table = lambda data, st: struct.unpack_from(">H", data, st + 2)[0]
    patched("bytes.ttf", "null-coverage.ttf", 0, set_u16(coverage_field, 0))
    patched("bytes.ttf", "unknown-format.ttf", 0, set_u16(coverage_table, 9))
    patched("bytes.ttf", "outside.ttf", 0, set_u16(coverage_field, 0xFFF0))
    patched("bytes.ttf", "null-coverage-f1.ttf", 1, set_u16(coverage_field, 0))
    ttc = TTCollection()
    ttc.fonts = [TTFont("bytes.ttf"), TTFont("null-coverage.ttf", lazy=True)]
    ttc.save("collection.ttc")
    print("collection.ttc")


if __name__ == "__main__":
    main()
