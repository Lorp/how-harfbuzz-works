"""Build the test font for “hb_shape and its backends”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like tools/build-test-font.py, with a different glyph set: a ligature,
a kerning pair, a combining acute (but no precomposed é), and Arabic beh
in its four forms. Every glyph is a plain box: only the glyph names, the
cmap, the advance widths and the layout tables matter here.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "A": (0x41, 600), "V": (0x56, 600),
    "e": (0x65, 500), "f": (0x66, 500), "i": (0x69, 500),
    "acutecomb": (0x301, 0), "f_i": (None, 900),
    "beh": (0x628, 600), "beh.init": (None, 400), "beh.medi": (None, 400),
    "beh.fina": (None, 600),
}

def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()

def main(fea, out):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(GLYPHS))
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Backends Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
