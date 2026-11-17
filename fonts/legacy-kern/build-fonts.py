"""Build the test fonts for “Legacy kern”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Fonts written:
  kern.ttf       box glyphs for a few Latin, Thai, Devanagari and Hebrew
                 letters and a combining acute, with no GSUB and no GPOS,
                 and an OpenType (version 0) `kern` table: one format 0
                 subtable of five pairs
  both.ttf       kern.ttf with a GPOS added, from both.fea: `kern` (A V −50)
                 and `mark` for Latin, but `mark` alone for Turkish; `dist`
                 (ka ka −30) for Devanagari
  apple.ttf      kern.ttf with the same pairs in an Apple (version 1.0)
                 `kern` table
  format2.ttf    kern.ttf with its subtable replaced by a format 2 (class
                 array) subtable under the OpenType header
  format2-array.ttf
                 format2.ttf with its left class values counted from the
                 start of the kerning array instead of the subtable
  format3.ttf    kern.ttf with an Apple `kern` table holding one format 3
                 (compact index) subtable
  cross.ttf      kern.ttf with a second, cross-stream subtable: A V +100,
                 and T o 0x8000, the value that should reset the shift
  override.ttf   kern.ttf with a second subtable, A V −30, whose coverage
                 has the override bit set
  unsorted.ttf   kern.ttf with its five pairs stored in descending order of
                 glyph IDs, where the format requires ascending order

The format 2 and format 3 subtables, and the unsorted format 0 one, are
written byte by byte: fontTools writes only format 0, and sorts its pairs.
Every glyph is a box, as in tools/build-test-font.py.
"""
import struct

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "A": (0x41, 600), "T": (0x54, 600), "V": (0x56, 600), "o": (0x6F, 500),
    "acutecomb": (0x301, 0),
    "ko": (0x0E01, 600),          # THAI CHARACTER KO KAI
    "ka": (0x0915, 600),          # DEVANAGARI LETTER KA
    "bet": (0x05D1, 600), "gimel": (0x05D2, 400),   # HEBREW LETTERS
}
ORDER = list(GLYPHS)
GID = {g: i for i, g in enumerate(ORDER)}

# The left-hand glyph, the right-hand glyph, and the value.
PAIRS = {("A", "V"): -80, ("T", "o"): -100, ("ko", "ko"): -100,
         ("ka", "ka"): -100, ("bet", "gimel"): -100}


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def format0(pairs, coverage=0x01, apple=False):
    st = KernTable_format_0(apple=apple)
    st.coverage, st.tupleIndex = coverage, (0 if apple else None)
    st.kernTable = dict(pairs)
    return st


def kern_table(subtables, version=0):
    kern = newTable("kern")
    kern.version, kern.kernTables = version, subtables
    return kern


def build_kern():
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(ORDER)
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Kern Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.font["kern"] = kern_table([format0(PAIRS)])
    fb.save("kern.ttf")


def derive(name, kern=None, raw_kern=None, fea=None):
    font = TTFont("kern.ttf")
    if kern is not None:
        font["kern"] = kern
    if raw_kern is not None:
        t = DefaultTable("kern")
        t.data = raw_kern
        font["kern"] = t
    if fea:
        addOpenTypeFeatures(font, fea)
    font.save(name)


def raw_format2(from_array=False):
    """An OpenType kern table, version 0, with one format 2 subtable.
    Left classes: A row 1, T row 2. Right classes: V column 1, o column 2.
    Class values are byte offsets: a left class's is the offset of its row
    from the start of the subtable, a right class's that of its column
    within the row. Everything else is class 0, whose row and column hold
    zeros. With from_array, a left class's value is the offset of its row
    from the start of the array instead."""
    hdr, row_width = 6, 3 * 2
    left_off = hdr + 8                     # after rowWidth and three offsets
    left = struct.pack(">HH", GID["A"], 2)  # firstGlyph, nGlyphs
    right_off = left_off + len(left) + 2 * 2
    right = struct.pack(">HH", GID["V"], 2)
    array_off = right_off + len(right) + 2 * 2
    base = 0 if from_array else array_off
    left += struct.pack(">HH", base + 1 * row_width, base + 2 * row_width)
    right += struct.pack(">HH", 1 * 2, 2 * 2)
    array = struct.pack(">9h", 0, 0, 0,
                               0, PAIRS["A", "V"], 0,
                               0, 0, PAIRS["T", "o"])
    body = struct.pack(">HHHH", row_width, left_off, right_off, array_off) + left + right + array
    length = hdr + len(body)
    sub = struct.pack(">HHBB", 0, length, 2, 0x01) + body
    return struct.pack(">HH", 0, 1) + sub


def raw_unsorted():
    """An OpenType kern table, version 0, with one format 0 subtable whose
    pairs are in descending order instead of ascending."""
    pairs = sorted(((GID[l], GID[r], v) for (l, r), v in PAIRS.items()), reverse=True)
    n = len(pairs)
    search_range = 6 * 2 ** (n.bit_length() - 1)
    body = struct.pack(">HHHH", n, search_range, n.bit_length() - 1, 6 * n - search_range)
    body += b"".join(struct.pack(">HHh", *p) for p in pairs)
    sub = struct.pack(">HHBB", 0, 6 + len(body), 0, 0x01) + body
    return struct.pack(">HH", 0, 1) + sub


def raw_format3():
    """An Apple kern table, version 1.0, with one format 3 subtable: a value
    list, a left and a right class for every glyph, and a matrix of indices
    into the value list."""
    n = len(ORDER)
    values = [0, PAIRS["A", "V"], PAIRS["T", "o"]]
    left = [0] * n; left[GID["A"]] = 1; left[GID["T"]] = 2
    right = [0] * n; right[GID["V"]] = 1; right[GID["o"]] = 2
    index = [0, 0, 0,
             0, 1, 0,
             0, 0, 2]
    body = struct.pack(">HBBBB", n, len(values), 3, 3, 0)
    body += struct.pack(f">{len(values)}h", *values)
    body += bytes(left) + bytes(right) + bytes(index)
    if len(body) % 2:
        body += b"\0"
    length = 8 + len(body)
    sub = struct.pack(">LBBH", length, 0x00, 3, 0) + body
    return struct.pack(">LL", 0x00010000, 1) + sub


if __name__ == "__main__":
    build_kern()
    derive("both.ttf", fea="both.fea")
    derive("apple.ttf", kern=kern_table([format0(PAIRS, coverage=0x00, apple=True)], version=1.0))
    derive("format2.ttf", raw_kern=raw_format2())
    derive("format2-array.ttf", raw_kern=raw_format2(from_array=True))
    derive("format3.ttf", raw_kern=raw_format3())
    derive("cross.ttf", kern=kern_table([format0(PAIRS), format0({("A", "V"): 100, ("T", "o"): -0x8000}, coverage=0x05)]))
    derive("unsorted.ttf", raw_kern=raw_unsorted())
    derive("override.ttf", kern=kern_table([format0(PAIRS), format0({("A", "V"): -30}, coverage=0x09)]))
