"""Prints some of bytes.ttf's bytes, field by field, for the chapter
"Fonts as bytes": the table directory at the start of the file, then
lookup 0's subtable and its Coverage table inside GSUB.

usage: python3 dump.py bytes.ttf

This reads the bytes with Python's struct module. It is not HarfBuzz, and
the field names are the ones HarfBuzz's structs use.
"""
import struct
import sys


def main(path):
    data = open(path, "rb").read()

    def row(at, size, label):
        print(f"{at:04x}  {' '.join(f'{b:02x}' for b in data[at:at + size]):<12} {label}")

    print("── OpenTypeOffsetTable (at 0x0000 in the file)")
    row(0, 4, "sfnt_version (0x00010000: TrueType outlines)")
    n = struct.unpack_from(">H", data, 4)[0]
    row(4, 2, f"tables.len = {n} (numTables)")
    sr, es, rs = struct.unpack_from(">HHH", data, 6)
    row(6, 2, f"tables.searchRange = {sr}")
    row(8, 2, f"tables.entrySelector = {es}")
    row(10, 2, f"tables.rangeShift = {rs}")
    gsub = None
    for i in range(n):
        rec = 12 + 16 * i
        tag = data[rec:rec + 4].decode("latin-1")
        off, length = struct.unpack_from(">II", data, rec + 8)
        row(rec, 4, f"tables[{i}].tag = '{tag}'")
        if i == 0 or tag == "GSUB":
            row(rec + 4, 4, f"tables[{i}].checkSum")
            row(rec + 8, 4, f"tables[{i}].offset = {off}")
            row(rec + 12, 4, f"tables[{i}].length = {length}")
        if tag == "GSUB":
            gsub = off
    print()

    g = lambda at: struct.unpack_from(">H", data, gsub + at)[0]
    lrow = lambda at, label: print(f"{at:04x}  {data[gsub + at]:02x} {data[gsub + at + 1]:02x}        {label}")
    lookup_list = g(8)
    lookup = lookup_list + g(lookup_list + 2)
    st = lookup + g(lookup + 6)
    cov = st + g(st + 2)
    print(f"── SingleSubstFormat2 (lookup 0's subtable, at {st:#06x} in GSUB)")
    lrow(st, f"format = {g(st)}")
    lrow(st + 2, f"coverage = {g(st + 2):#06x}   → Coverage at {cov:#06x}")
    count = g(st + 4)
    lrow(st + 4, f"substitute.len = {count}")
    for i in range(count):
        lrow(st + 6 + 2 * i, f"substitute[{i}] = glyph {g(st + 6 + 2 * i)}")
    print()
    print(f"── CoverageFormat1 (at {cov:#06x} in GSUB)")
    lrow(cov, f"coverageFormat = {g(cov)}")
    count = g(cov + 2)
    lrow(cov + 2, f"glyphArray.len = {count}")
    for i in range(count):
        lrow(cov + 4 + 2 * i, f"glyphArray[{i}] = glyph {g(cov + 4 + 2 * i)}")


if __name__ == "__main__":
    main(sys.argv[1])
