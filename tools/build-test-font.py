"""Build a small test font from a feature file, for shaping with HarfBuzz.

usage: python3 tools/build-test-font.py FEATURES.fea OUT.ttf [--shortest-first]

--shortest-first reverses every LigatureSet after compiling, which no
feature file can express: feaLib always puts longer ligatures first.

Every glyph is a plain box: the outlines don't matter, only the glyph
names, the cmap and the layout tables do.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

GLYPHS = {  # glyph name: Unicode codepoint (None for unencoded glyphs)
    ".notdef": None, "space": 0x20, "a": 0x61, "e": 0x65, "f": 0x66,
    "i": 0x69, "l": 0x6C, "x": 0x78, "acutecomb": 0x301,
    "f_i": None, "f_l": None, "f_f": None, "f_f_i": None,
    "a.alt1": None, "a.alt2": None, "a.alt3": None, "e.init": None,
}

def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()

def main(fea, out, shortest_first=False):
    order = list(GLYPHS)
    widths = {g: (0 if g == "acutecomb" else 250 if g == "space"
                  else 900 if "_" in g else 500) for g in order}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g in ("space", "acutecomb") else widths[g]) for g in order})
    fb.setupHorizontalMetrics({g: (widths[g], 50) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook GSUB Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    if shortest_first:
        for lookup in fb.font["GSUB"].table.LookupList.Lookup:
            for st in lookup.SubTable:
                if lookup.LookupType == 4:
                    for first in st.ligatures:
                        st.ligatures[first].sort(key=lambda lig: len(lig.Component))
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], '--shortest-first' in sys.argv[3:])
