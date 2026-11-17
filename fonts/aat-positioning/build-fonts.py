"""Build the test fonts for “AAT positioning”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every font is derived from ../legacy-kern/kern.ttf: its box glyphs for a
few Latin, Thai, Devanagari and Hebrew letters and a combining acute. Its
`kern` table is taken out. In the fonts with marks, the acute is given a
small box above the line, hanging to the left of its origin, as a mark
designed to sit over a 600-unit letter.

Fonts written:
  kerx.ttf          one `kerx` format 0 subtable with kern.ttf's five pairs
  kerx-gpos.ttf     kerx.ttf with GPOS (gpos.fea: `kern` A V −50, `mark`)
  kerx-gsub-gpos.ttf
                    kerx-gpos.ttf with a GSUB too (gsub.fea)
  morx-kerx.ttf     kerx-gsub-gpos.ttf with a morx table that does nothing
                    to this text (MORX)
  morx-gpos.ttf     morx-kerx.ttf without its `kerx`
  mark-gpos.ttf     GSUB and a GPOS with `mark` and no `kern` (mark.fea),
                    and an acute with an advance of 200; no `kerx`
  mark-gpos-kerx.ttf
                    morx-kerx.ttf     kerx-gsub-gpos.ttf with a morx table that does nothing
                    to this text (MORX)
  morx-gpos.ttf     morx-kerx.ttf without its `kerx`
  mark-gpos.ttf with kerx.ttf's `kerx`
  format2.ttf       the Latin pairs as one `kerx` format 2 subtable
  backwards.ttf     kerx.ttf with the Backwards bit set in its subtable
  tuples.ttf        kerx.ttf with the Variation bit set and a tupleCount
                    of 3: each value is an offset to three values
  format6.ttf       the Latin pairs as one `kerx` format 6 subtable
  cross.ttf         kerx.ttf with a second, cross-stream format 0 subtable:
                    A V +100, bet gimel +100
  cross-first.ttf   cross.ttf with its two subtables the other way round
  anchors.ttf       a `kerx` format 4 subtable, anchor point actions, and
                    an `ankr` table: the acute attaches to the letter
                    before it
  coords.ttf        the same attachment, with coordinate actions
  points.ttf        the same attachment, with control point actions
  trak.ttf          a `trak` table and a STAT table
  trak-nostat.ttf   trak.ttf without STAT

fontTools writes `trak` and `ankr`, and STAT; it doesn't write `kerx`, so
every `kerx` table here is written byte by byte, from the structures in
Apple's TrueType Reference Manual, as HarfBuzz reads them
(hb-aat-layout-kerx-table.hh).
"""
import io
import struct

from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables._t_r_a_k import TrackData, TrackTableEntry

BASE = "../legacy-kern/kern.ttf"

# Glyph order of kern.ttf.
ORDER = [".notdef", "space", "A", "T", "V", "o", "acutecomb",
         "ko", "ka", "bet", "gimel"]
GID = {g: i for i, g in enumerate(ORDER)}

# kern.ttf's pairs: left-hand glyph, right-hand glyph, value.
PAIRS = {("A", "V"): -80, ("T", "o"): -100, ("ko", "ko"): -100,
         ("ka", "ka"): -100, ("bet", "gimel"): -100}
LATIN = {k: v for k, v in PAIRS.items() if k in (("A", "V"), ("T", "o"))}

# Anchors, in font units: where the acute attaches on each letter, and the
# point on the acute that goes there.
ANCHORS = {"A": (300, 600), "T": (300, 600), "V": (300, 600),
           "o": (250, 520), "acutecomb": (-300, 520)}

# kerx coverage bits (the high byte of the 32-bit coverage field).
VERTICAL, CROSS_STREAM, VARIATION, BACKWARDS = 0x80000000, 0x40000000, 0x20000000, 0x10000000


def base_font(mark_advance=None):
    font = TTFont(BASE)
    del font["kern"]
    if mark_advance is not None:
        pen = TTGlyphPen(None)
        pen.moveTo((-350, 540)); pen.lineTo((-350, 640))
        pen.lineTo((-250, 640)); pen.lineTo((-250, 540))
        pen.closePath()
        font["glyf"]["acutecomb"] = pen.glyph()
        font["hmtx"]["acutecomb"] = (mark_advance, -350)
    return font


# ---------------------------------------------------------------- kerx

def lookup8(first, values):
    """An AAT lookup table, format 8 (trimmed array) of 16-bit values."""
    return struct.pack(f">HHH{len(values)}H", 8, first, len(values), *values)


def subtable(fmt, body, coverage=0, tuple_count=0):
    """A kerx subtable: a 12-byte header (length, coverage with the format
    in its low byte, tupleCount) and the body."""
    return struct.pack(">LLL", 12 + len(body), coverage | fmt, tuple_count) + body


def kerx(*subtables):
    """The kerx table: version 2, padding, a 32-bit count, the subtables."""
    return struct.pack(">HHL", 2, 0, len(subtables)) + b"".join(subtables)


def format0(pairs, coverage=0):
    rows = sorted((GID[l], GID[r], v) for (l, r), v in pairs.items())
    n = len(rows)
    search_range = 6 * 2 ** (n.bit_length() - 1)
    body = struct.pack(">LLLL", n, search_range, n.bit_length() - 1, 6 * n - search_range)
    body += b"".join(struct.pack(">HHh", *p) for p in rows)
    return subtable(0, body, coverage)


def format0_tuples(pairs, tuple_count, coverage=0):
    """A format 0 subtable whose values are tuples: each pair's value is
    the byte offset, from the start of the subtable, of tuple_count
    values. The first of each tuple is the pair's value; the others are
    twice and three times it."""
    rows = sorted((GID[l], GID[r], v) for (l, r), v in pairs.items())
    n = len(rows)
    search_range = 6 * 2 ** (n.bit_length() - 1)
    head = struct.pack(">LLLL", n, search_range, n.bit_length() - 1, 6 * n - search_range)
    tuples_at = 12 + len(head) + 6 * n
    body, tuples = head, b""
    for l, r, v in rows:
        body += struct.pack(">HHH", l, r, tuples_at + len(tuples))
        tuples += struct.pack(f">{tuple_count}h", *(v * (i + 1) for i in range(tuple_count)))
    return subtable(0, body + tuples, coverage, tuple_count)


def format2():
    """A class array. Left classes: A row 1, T row 2; right classes: V
    column 1, o column 2. A left class value is the byte offset of its row
    from the start of the array, a right class value that of its column
    within the row. Glyphs not in a class table have class 0."""
    row_width = 3 * 2
    left = lookup8(GID["A"], [1 * row_width, 2 * row_width])   # A, T
    right = lookup8(GID["V"], [1 * 2, 2 * 2])                  # V, o
    array = struct.pack(">9h", 0, 0, 0,
                               0, LATIN["A", "V"], 0,
                               0, 0, LATIN["T", "o"])
    fixed = 12 + 4 * 4
    left_off = fixed
    right_off = left_off + len(left)
    array_off = right_off + len(right)
    pad = b"\0" * ((-array_off) % 4)
    array_off += len(pad)
    body = struct.pack(">LLLL", row_width, left_off, right_off, array_off) + left + right + pad + array
    return subtable(2, body)


def format6():
    """An extended class matrix, 16-bit values. The row lookup gives the
    index of a row's first value (row × columnCount), the column lookup the
    column; the value is array[row value + column value]."""
    rows, cols = 3, 3
    row_index = lookup8(GID["A"], [1 * cols, 2 * cols])         # A, T
    col_index = lookup8(GID["V"], [1, 2])                       # V, o
    array = struct.pack(">9h", 0, 0, 0,
                               0, LATIN["A", "V"], 0,
                               0, 0, LATIN["T", "o"])
    fixed = 12 + 4 + 2 + 2 + 4 * 4
    row_off = fixed
    col_off = row_off + len(row_index)
    array_off = col_off + len(col_index)
    pad = b"\0" * ((-array_off) % 4)
    array_off += len(pad)
    body = struct.pack(">LHHLLLL", 0, rows, cols, row_off, col_off, array_off, 0)
    body += row_index + col_index + pad + array
    return subtable(6, body)


def format4(action_type):
    """A state machine that remembers each letter (the Mark flag) and
    attaches an acute that follows it. Classes 0–3 are the reserved ones;
    class 4 is a letter, class 5 the acute. One state, used for both start
    of text and start of line. Action type 0 holds control point indices,
    1 anchor indices into `ankr`, 2 coordinates.

    After the subtable header come the state machine's 16-byte header,
    the 32-bit flags field (action type and the offset of the actions),
    then the class lookup, the state array, the entries and the actions.
    Every offset counts from the start of the machine's header."""
    n_classes = 6
    classes = lookup8(GID["A"], [4, 4, 4, 4, 5])               # A T V o acute
    row = struct.pack(f">{n_classes}H", 0, 0, 0, 0, 1, 2)
    states = row + row
    # Entries: newState, flags, ankrActionIndex.
    entries = struct.pack(">HHH", 0, 0x0000, 0xFFFF)          # 0: nothing
    entries += struct.pack(">HHH", 0, 0x8000, 0xFFFF)         # 1: Mark this letter
    entries += struct.pack(">HHH", 0, 0x0000, 0)              # 2: attach, action 0
    if action_type == 0:
        # A's point 1 is its top left corner (50, 500); the acute's point 0
        # is its bottom left (-350, 540).
        actions = struct.pack(">HH", 1, 0)
    elif action_type == 1:
        actions = struct.pack(">HH", 0, 0)                     # anchor 0 on each
    else:
        mx, my = ANCHORS["A"]
        cx, cy = ANCHORS["acutecomb"]
        actions = struct.pack(">hhhh", mx, my, cx, cy)
    class_off = 16 + 4
    states_off = class_off + len(classes)
    entries_off = states_off + len(states)
    actions_off = entries_off + len(entries)
    pad = b"\0" * ((-actions_off) % 2)
    actions_off += len(pad)
    flags = (action_type << 30) | actions_off
    body = struct.pack(">LLLLL", n_classes, class_off, states_off, entries_off, flags)
    body += classes + states + entries + pad + actions
    return subtable(4, body)


def raw_ankr():
    glyphs = ["A", "T", "V", "o", "acutecomb"]
    data, offsets = b"", []
    for g in glyphs:
        offsets.append(len(data))
        data += struct.pack(">Lhh", 1, *ANCHORS[g])
    lookup = lookup8(GID[glyphs[0]], offsets)
    pad = b"\0" * ((-len(lookup)) % 4)
    lookup_off = 12
    data_off = lookup_off + len(lookup) + len(pad)
    return struct.pack(">HHLL", 0, 0, lookup_off, data_off) + lookup + pad + data


def with_table(font, tag, data):
    t = DefaultTable(tag)
    t.data = data
    font[tag] = t
    return font


# A morx table whose one subtable changes ko into ko: it does nothing to
# the text in this chapter, but makes HarfBuzz shape with morx, not GSUB.
MORX = """<?xml version="1.0" encoding="UTF-8"?>
<ttFont sfntVersion="\\x00\\x01\\x00\\x00" ttLibVersion="4.38">
  <morx>
    <Version value="2"/>
    <Reserved value="0"/>
    <MorphChain index="0">
      <DefaultFlags value="0x00000001"/>
      <MorphFeature index="0">
        <FeatureType value="0"/>
        <FeatureSetting value="1"/>
        <EnableFlags value="0x00000000"/>
        <DisableFlags value="0x00000000"/>
      </MorphFeature>
      <MorphSubtable index="0">
        <TextDirection value="Any"/>
        <ProcessingOrder value="LayoutOrder"/>
        <SubFeatureFlags value="0x00000001"/>
        <NoncontextualMorph>
          <Substitution>
            <Lookup glyph="ko" value="ko"/>
          </Substitution>
        </NoncontextualMorph>
      </MorphSubtable>
    </MorphChain>
  </morx>
</ttFont>
"""


def add_morx(font):
    font.importXML(io.StringIO(MORX))
    return font


# ---------------------------------------------------------------- trak

def add_trak(font, stat=True):
    name = font["name"]
    normal = name.addMultilingualName({"en": "Normal"}, mac=False)
    tight = name.addMultilingualName({"en": "Tight"}, mac=False)
    loose = name.addMultilingualName({"en": "Loose"}, mac=False)
    trak = newTable("trak")
    trak.version, trak.format = 1.0, 0
    # Horizontal: tracking per point size. Only the 0 (Normal) track is
    # used by HarfBuzz; Tight and Loose are there to show it.
    sizes = {6.0: 50, 12.0: 0, 24.0: -20, 72.0: -40}
    trak.horizData = TrackData({
        -1.0: TrackTableEntry({s: v - 30 for s, v in sizes.items()}, nameIndex=tight),
        0.0: TrackTableEntry(sizes, nameIndex=normal),
        1.0: TrackTableEntry({s: v + 30 for s, v in sizes.items()}, nameIndex=loose),
    })
    # Vertical: 100 units looser at every size.
    trak.vertData = TrackData({0.0: TrackTableEntry({12.0: 100}, nameIndex=normal)})
    font["trak"] = trak
    if stat:
        buildStatTable(font, [{"tag": "wght", "name": "Weight",
                               "values": [{"value": 400, "name": "Regular", "flags": 0x2}]}])
    return font


if __name__ == "__main__":
    k = kerx(format0(PAIRS))
    with_table(base_font(), "kerx", k).save("kerx.ttf")

    f = with_table(base_font(), "kerx", k)
    addOpenTypeFeatures(f, "gpos.fea")
    f.save("kerx-gpos.ttf")

    f = with_table(base_font(), "kerx", k)
    addOpenTypeFeatures(f, "gpos.fea")
    addOpenTypeFeatures(f, "gsub.fea", tables=["GSUB"])
    f.save("kerx-gsub-gpos.ttf")
    add_morx(f).save("morx-kerx.ttf")
    del f["kerx"]
    f.save("morx-gpos.ttf")

    f = base_font(mark_advance=200)
    addOpenTypeFeatures(f, "mark.fea")
    f.save("mark-gpos.ttf")
    f = base_font(mark_advance=200)
    addOpenTypeFeatures(f, "mark.fea")
    with_table(f, "kerx", k).save("mark-gpos-kerx.ttf")

    with_table(base_font(), "kerx", kerx(format2())).save("format2.ttf")
    with_table(base_font(), "kerx", kerx(format0(PAIRS, coverage=BACKWARDS))).save("backwards.ttf")
    with_table(base_font(), "kerx", kerx(format0_tuples(PAIRS, 3, coverage=VARIATION))).save("tuples.ttf")
    with_table(base_font(), "kerx", kerx(format6())).save("format6.ttf")

    cross = format0({("A", "V"): 100, ("bet", "gimel"): 100}, coverage=CROSS_STREAM)
    with_table(base_font(), "kerx", kerx(format0(PAIRS), cross)).save("cross.ttf")
    with_table(base_font(), "kerx", kerx(cross, format0(PAIRS))).save("cross-first.ttf")

    f = with_table(base_font(mark_advance=0), "kerx", kerx(format4(1)))
    with_table(f, "ankr", raw_ankr()).save("anchors.ttf")
    with_table(base_font(mark_advance=0), "kerx", kerx(format4(2))).save("coords.ttf")
    with_table(base_font(mark_advance=0), "kerx", kerx(format4(0))).save("points.ttf")

    add_trak(base_font()).save("trak.ttf")
    add_trak(base_font(), stat=False).save("trak-nostat.ttf")
