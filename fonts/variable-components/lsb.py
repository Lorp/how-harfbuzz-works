"""Writes a copy of varc-static-gvar.ttf whose glyphs' left side bearings
in hmtx are changed, for the chapter "Variable components".

usage: python3 lsb.py IN.ttf OUT.ttf LSB

The font has one long metric (.notdef's) and then a bare side bearing for
each of `a` and `b`; this sets both to LSB. The outlines, still starting
at x = 0, are left alone, and so are the table checksums: HarfBuzz doesn't
check them.
"""
import struct
import sys


def main(src, dst, lsb):
    data = bytearray(open(src, "rb").read())
    num_tables = struct.unpack_from(">H", data, 4)[0]
    for i in range(num_tables):
        tag, _, offset, _ = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        if tag == b"hmtx":
            struct.pack_into(">hh", data, offset + 4, int(lsb), int(lsb))
    open(dst, "wb").write(data)


if __name__ == "__main__":
    main(*sys.argv[1:])
