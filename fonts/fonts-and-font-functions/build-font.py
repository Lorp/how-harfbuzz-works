"""Build the test fonts for the chapter on fonts and font functions.

usage: python3 build-font.py OUT_DIR

Fonts written:
  funcs.ttf        H, I, space and a combining acute, with a GPOS
                   mark-to-base rule for the acute and one kerning pair
                   (H I) whose adjustment has a Device table at 12 ppem
  funcs-nogpos.ttf the same glyphs with no GPOS, so marks are placed by
                   HarfBuzz's fallback positioning, which reads extents

upem is 1000. The advances are deliberately odd numbers (625, 275), so
that rounding shows when the font is scaled to small sizes.
"""
import os
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

GLYPHS = {".notdef": None, "space": 0x20, "H": 0x48, "I": 0x49,
          "acutecomb": 0x301}
ADVANCE = {".notdef": 500, "space": 250, "H": 625, "I": 275, "acutecomb": 0}
CAP = 700


def rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1))
    pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()


def glyph(name):
    pen = TTGlyphPen(None)
    if name == "H":
        rect(pen, 80, 0, 180, CAP)
        rect(pen, 445, 0, 545, CAP)
        rect(pen, 180, 300, 445, 400)
    elif name == "I":
        rect(pen, 80, 0, 195, CAP)
    elif name == "acutecomb":
        # A small block above the cap height, left of the origin, as a
        # combining mark usually is.
        rect(pen, -200, 750, -100, 900)
    elif name == ".notdef":
        rect(pen, 50, 0, 450, CAP)
    return pen.glyph()


FEA = """
languagesystem DFLT dflt;
languagesystem latn dflt;

markClass acutecomb <anchor -150 750> @TOP;

feature mark {
    pos base H <anchor 312 700> mark @TOP;
    pos base I <anchor 137 700> mark @TOP;
} mark;

feature kern {
    pos H I <0 0 -25 0 <device NULL> <device NULL> <device 12 -1> <device NULL>>;
} kern;

table GDEF {
    GlyphClassDef [H I], , [acutecomb], ;
} GDEF;
"""


def build(path, gpos):
    order = list(GLYPHS)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in GLYPHS.items() if cp})
    glyphs = {g: glyph(g) for g in order}
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    metrics = {}
    for g in order:
        gl = glyf[g]
        gl.recalcBounds(glyf)
        metrics[g] = (ADVANCE[g], getattr(gl, "xMin", 0))
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Font Funcs Test",
                       "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    if gpos:
        addOpenTypeFeaturesFromString(fb.font, FEA)
    fb.save(path)


def main(out):
    build(os.path.join(out, "funcs.ttf"), gpos=True)
    build(os.path.join(out, "funcs-nogpos.ttf"), gpos=False)


if __name__ == "__main__":
    main(sys.argv[1])
