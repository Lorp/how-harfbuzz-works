"""Build the test font for “Unicode inside HarfBuzz”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like tools/build-test-font.py, but with the glyphs this chapter needs: a few
Latin letters, a visible soft hyphen, parentheses and a Hebrew letter for
mirroring, Hebrew and Thai marks whose order HarfBuzz changes, and a
variation sequence in a format 14 cmap subtable. Every glyph is a plain box:
only the glyph names, the cmap, the advance widths and the layout tables
matter here.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "a": (0x61, 500), "b": (0x62, 500), "f": (0x66, 500), "i": (0x69, 500),
    "f_i": (None, 900), "a.vs1": (None, 500),
    "hyphen": (0x2D, 300), "softhyphen": (0xAD, 300),
    "parenleft": (0x28, 300), "parenright": (0x29, 300),
    # Hebrew: bet, alef, and two points
    "bet": (0x5D1, 500), "alef": (0x5D0, 500),
    "qamats": (0x5B8, 0), "dagesh": (0x5BC, 0),
    # Thai: KO KAI, and two below-base marks
    "kokai": (0xE01, 500), "saraU": (0xE38, 0), "phinthu": (0xE3A, 0),
}
# Variation sequences: (base, selector) → glyph
UVS = [(0x61, 0xFE00, "a.vs1")]

def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
    else:  # a mark: a small box to the left of its origin
        pen.moveTo((-200, -150)); pen.lineTo((-200, -50))
        pen.lineTo((-100, -50)); pen.lineTo((-100, -150))
    pen.closePath()
    return pen.glyph()

def main(fea, out):
    order = list(GLYPHS)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp},
                         uvs=UVS)
    fb.setupGlyf({g: box(w) if g != "space" else TTGlyphPen(None).glyph()
                  for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Unicode Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
