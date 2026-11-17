"""Build the test font for “For applications”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like fonts/buffers/build-font.py, with a glyph set for line breaking: a
few Latin letters, a space and a hyphen, three f ligatures, and beh in its
four Arabic forms with tatweel. Every glyph is a plain box: only the glyph
names, the cmap, the advance widths and the layout tables matter here.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250), "hyphen": (0x2D, 300),
    # Latin
    "T": (0x54, 600), "a": (0x61, 500), "c": (0x63, 500), "e": (0x65, 500),
    "f": (0x66, 300), "i": (0x69, 250), "n": (0x6E, 500), "o": (0x6F, 500),
    "x": (0x78, 500),
    "f_i": (None, 550), "f_f": (None, 600), "f_f_i": (None, 850),
    # Arabic: beh in four forms, and tatweel
    "beh": (0x628, 600), "beh.init": (None, 400), "beh.medi": (None, 400),
    "beh.fina": (None, 600), "tatweel": (0x640, 300),
}

def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()

def main(fea, out):
    order = list(GLYPHS)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Applications Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
