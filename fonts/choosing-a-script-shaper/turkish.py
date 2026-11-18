"""Build turkish.ttf and turkish-late.ttf from turkish.fea.

usage: python3 turkish.py   (run from this folder; build.sh does)

turkish-late.ttf has the locl block moved after liga, so its lookup comes
later in the LookupList. Glyphs are plain boxes.
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

GLYPHS = {".notdef": None, "f": 0x66, "i": 0x69, "f_i": None,
          "i.TRK": None, "i.sc": None, "i.TRK.sc": None}


def box(width):
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0)); pen.lineTo((50, 500))
    pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
    pen.closePath()
    return pen.glyph()


def build(fea, out):
    order = list(GLYPHS)
    widths = {g: 900 if "_" in g else 500 for g in order}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(widths[g]) for g in order})
    fb.setupHorizontalMetrics({g: (widths[g], 50) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Turkish Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


fea = open("turkish.fea").read()
build(fea, "turkish.ttf")
start = fea.index("feature locl"); end = fea.index("} locl;") + len("} locl;\n")
build(fea[:start] + fea[end:] + "\n" + fea[start:end], "turkish-late.ttf")
