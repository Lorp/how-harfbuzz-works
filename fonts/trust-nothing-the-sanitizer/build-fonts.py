"""Build the sanitizer chapter's test fonts: one good font, and copies of it
with one offset broken in each.

usage: python3 build-fonts.py   (run from this folder, by build.sh)

  good.ttf        sanitizer.fea, compiled
  bad-gsub.ttf    the ligature subtable's Coverage offset points past the
                  end of GSUB. Everything else is untouched.
  bad-gpos.ttf    the mark-to-base subtable's markCoverage offset points
                  past the end of GPOS: a check made when GPOS is loaded.
  bad-anchor.ttf  the mark-to-base anchor for base glyph b points past the
                  end of GPOS: a check HarfBuzz defers until the anchor is
                  used.

The broken fonts are made by patching the compiled bytes, because no font
compiler will write a bad offset. Only the one 16-bit offset changes; the
table's checksum in the table directory is recomputed, though HarfBuzz
doesn't check it.

Every glyph is a plain box: only the glyph names, the cmap and the layout
tables matter.
"""
import struct
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

GLYPHS = {  # glyph name: Unicode codepoint (None for unencoded glyphs)
    ".notdef": None, "space": 0x20, "a": 0x61, "b": 0x62, "f": 0x66,
    "i": 0x69, "acutecomb": 0x301, "f_i": None, "a.alt": None,
}
BAD = 0xFFFF  # far past the end of these small tables


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build_good(out):
    order = list(GLYPHS)
    widths = {g: (0 if g == "acutecomb" else 250 if g == "space"
                  else 900 if "_" in g else 500) for g in order}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(widths[g] if g not in ("space", "acutecomb") else 0) for g in order})
    fb.setupHorizontalMetrics({g: (widths[g], 50) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Sanitizer Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, "sanitizer.fea")
    fb.save(out)
    return fb.font.getGlyphOrder()


def u16(data, at):
    return struct.unpack_from(">H", data, at)[0]


def table_record(font, tag):
    """(position of the table record, table offset, table length)"""
    num_tables = u16(font, 4)
    for i in range(num_tables):
        rec = 12 + 16 * i
        if font[rec:rec + 4] == tag.encode():
            _, offset, length = struct.unpack_from(">III", font, rec + 4)
            return rec, offset, length
    raise KeyError(tag)


def checksum(data):
    data = data + b"\0" * (-len(data) % 4)
    return sum(struct.unpack(f">{len(data) // 4}I", data)) & 0xFFFFFFFF


def lookup_subtable(table, lookup_index):
    """Offset, from the start of the table, of a lookup's first subtable."""
    lookup_list = u16(table, 8)
    lookup = lookup_list + u16(table, lookup_list + 2 + 2 * lookup_index)
    return lookup + u16(table, lookup + 6)


def coverage_index(table, coverage, gid):
    fmt = u16(table, coverage)
    count = u16(table, coverage + 2)
    if fmt == 1:
        gids = [u16(table, coverage + 4 + 2 * k) for k in range(count)]
        return gids.index(gid)
    for k in range(count):
        start, end, first = struct.unpack_from(">HHH", table, coverage + 4 + 6 * k)
        if start <= gid <= end:
            return first + gid - start
    raise ValueError(gid)


def patched(src, out, tag, find_offset):
    font = bytearray(open(src, "rb").read())
    rec, offset, length = table_record(font, tag)
    table = font[offset:offset + length]
    at = find_offset(bytes(table))
    struct.pack_into(">H", table, at, BAD)
    font[offset:offset + length] = table
    struct.pack_into(">I", font, rec + 4, checksum(bytes(table)))
    open(out, "wb").write(font)


def main():
    order = build_good("good.ttf")

    # LigatureSubstFormat1: format, coverage, ... (GSUB lookup 0)
    patched("good.ttf", "bad-gsub.ttf", "GSUB",
            lambda t: lookup_subtable(t, 0) + 2)

    # MarkBasePosFormat1: format, markCoverage, baseCoverage, markClassCount,
    # markArray, baseArray (GPOS lookup 1)
    patched("good.ttf", "bad-gpos.ttf", "GPOS",
            lambda t: lookup_subtable(t, 1) + 2)

    def anchor_of_b(t):
        st = lookup_subtable(t, 1)
        base_coverage = st + u16(t, st + 4)
        class_count = u16(t, st + 6)
        base_array = st + u16(t, st + 10)
        row = coverage_index(t, base_coverage, order.index("b"))
        # BaseArray: baseCount, then baseCount rows of class_count offsets
        return base_array + 2 + 2 * (row * class_count + 0)
    patched("good.ttf", "bad-anchor.ttf", "GPOS", anchor_of_b)


if __name__ == "__main__":
    main()
