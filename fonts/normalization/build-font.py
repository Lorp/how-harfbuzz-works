"""Build the test font for “Normalization”.

usage: python3 build-font.py FEATURES.fea OUT.ttf

Like tools/build-test-font.py, but with a chosen set of precomposed
letters and combining marks, so that normalization has something to
decide: the font has some accented letters and not others, and some
marks and not others. Every glyph is a plain box (marks have no width):
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
    "A": (0x41, 600), "a": (0x61, 500), "e": (0x65, 500),
    "o": (0x6F, 500), "u": (0x75, 500),
    # precomposed letters the font has
    "aacute": (0xE1, 500), "acircumflex": (0xE2, 500), "eacute": (0xE9, 500),
    "udieresis": (0xFC, 500), "udieresisgrave": (0x1DC, 500),
    "odieresismacron": (0x22B, 500), "Aring": (0xC5, 600),
    "angstrom": (0x212B, 600), "Omega": (0x3A9, 700),
    # combining marks the font has (not U+0302 circumflex)
    "gravecomb": (0x300, 0), "acutecomb": (0x301, 0), "macroncomb": (0x304, 0),
    "dieresiscomb": (0x308, 0), "ringcomb": (0x30A, 0), "dotbelowcomb": (0x323, 0),
    # U+2010 HYPHEN, but not U+2011 NON-BREAKING HYPHEN
    "hyphen": (0x2010, 300),
    # Devanagari NA, NNNA, NUKTA and the vowel sign AA
    "na": (0x928, 600), "nnna": (0x929, 600), "nukta": (0x93C, 0), "aaMatra": (0x93E, 250),
    # an unencoded glyph, for hb-shape --not-found-glyph
    "missing": (None, 500),
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
    fb.setupNameTable({"familyName": "HBBook Normalization Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
