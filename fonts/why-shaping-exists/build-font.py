"""Build the test font for “Why shaping exists”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like tools/build-test-font.py, but with a few Arabic and Devanagari glyphs
as well as Latin ones. Every glyph is a plain box: only the glyph names,
the cmap, the advance widths and the layout tables matter here.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    # Latin
    "a": (0x61, 500), "e": (0x65, 500), "f": (0x66, 500), "i": (0x69, 500),
    "aacute": (0xE1, 500), "acutecomb": (0x301, 0), "f_f": (None, 900), "f_i": (None, 900),
    # Arabic: beh in four forms, lam and alef, and their ligature
    "beh": (0x628, 600), "beh.init": (None, 400), "beh.medi": (None, 400),
    "beh.fina": (None, 600), "lam": (0x644, 500), "lam.init": (None, 400),
    "alef": (0x627, 300), "alef.fina": (None, 300), "lam_alef": (None, 700),
    # Devanagari: KA, SSA, virama, the vowel sign I, and the conjunct K.SSA
    "ka": (0x915, 600), "ssa": (0x937, 600), "virama": (0x94D, 0),
    "iMatra": (0x93F, 250), "k_ssa": (None, 800),
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
    fb.setupNameTable({"familyName": "HBBook Shaping Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
