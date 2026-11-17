"""Build the test font for “The pipeline, step by step”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like fonts/buffers/build-font.py, with its own glyph set: Arabic beh, lam
and alef in their joining forms, a lam-alef ligature, a fatha, a pair of
parentheses, and the digits and fraction slash for an automatic fraction.
Every glyph is a plain box: only the glyph names, the cmap, the advance
widths and the layout tables matter here.
"""
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "parenleft": (0x28, 300), "parenright": (0x29, 300),
    # Arabic
    "beh": (0x628, 600), "beh.init": (None, 400), "beh.medi": (None, 400),
    "beh.fina": (None, 600),
    "lam": (0x644, 300), "lam.init": (None, 250), "lam.medi": (None, 250),
    "lam.fina": (None, 300),
    "alef": (0x627, 250), "alef.fina": (None, 250),
    "lam_alef": (None, 500), "lam_alef.fina": (None, 500),
    # A mark with an advance, which a real font wouldn't give it, so that
    # zeroing mark widths shows.
    "fatha": (0x64E, 200),
    # An automatic fraction
    "one": (0x31, 500), "two": (0x32, 500), "slash": (0x2F, 300),
    "fraction": (0x2044, 200),
    "one.numr": (None, 350), "two.dnom": (None, 350),
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
    fb.setupNameTable({"familyName": "HBBook Pipeline Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
