"""Build the test font for the chapter “hb-raster”.

usage: python3 build-fonts.py OUT_DIR

Font written (upem 400, so that at 20 pixels per em one pixel is 20 units):
  raster.ttf  l  a bar one pixel wide and ten high (at 20 ppem), with an
                 advance of 105 units, 5.25 pixels, so that each l in a
                 row starts a quarter of a pixel further right than the
                 one before
              o  a square with a square counter wound the other way
              q  the same square with its counter wound the same way
              x  two overlapping squares, wound the same way
"""
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPEM = 400


def rect(pen, x0, y0, x1, y1, clockwise=True):
    pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
    if not clockwise:
        pts.reverse()
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


def glyph(draw):
    pen = TTGlyphPen(None)
    draw(pen)
    return pen.glyph()


def main(out):
    glyphs = {
        ".notdef": glyph(lambda p: None),
        "l": glyph(lambda p: rect(p, 0, 0, 20, 200)),
        "o": glyph(lambda p: (rect(p, 20, 0, 260, 240),
                              rect(p, 80, 60, 200, 180, clockwise=False))),
        "q": glyph(lambda p: (rect(p, 20, 0, 260, 240),
                              rect(p, 80, 60, 200, 180))),
        "x": glyph(lambda p: (rect(p, 20, 0, 180, 160),
                              rect(p, 100, 80, 260, 240))),
    }
    order = list(glyphs)
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(g): g for g in order if len(g) == 1})
    fb.setupGlyf(glyphs)
    adv = {".notdef": 300, "l": 105, "o": 300, "q": 300, "x": 300}
    lsb = {".notdef": 0, "l": 0, "o": 20, "q": 20, "x": 20}
    fb.setupHorizontalMetrics({g: (adv[g], lsb[g]) for g in order})
    fb.setupHorizontalHeader(ascent=300, descent=-100)
    fb.setupNameTable({"familyName": "Raster Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=300, sTypoDescender=-100, usWinAscent=300, usWinDescent=100)
    fb.setupPost()
    fb.save(f"{out}/raster.ttf")


if __name__ == "__main__":
    main(sys.argv[1])
