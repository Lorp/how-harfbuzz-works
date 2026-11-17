"""Build the test fonts for the chapter “Where metrics come from”.

usage: python3 build-metrics-fonts.py OUT_DIR

Every glyph is made of plain rectangles: only the metrics matter. The glyph
order and the metrics are chosen so that each of HarfBuzz's code paths for
advances, side bearings, origins and extents has something to show:

  .notdef  500
  space    250, no outline
  H        600, xMin 80
  L        560, drawn from x=80, but hmtx says its left side bearing is 160
  p        560, with a descender to -210
  x        500, a small box in glyf, and a COLR glyph made of H and p
  zero     550 \
  one      550  } the same advance, so hmtx stores it once: these three
  two      550 /  share the last long metric, each with its own bearing

Fonts written:
  metrics.ttf          glyf, hmtx, COLR and CPAL; hhea ascender 900 and
                       descender -300, OS/2 typo 800/-200/100, win 950/350
  metrics-typo.ttf     metrics.ttf with USE_TYPO_METRICS set in OS/2
  metrics-short.ttf    metrics.ttf with hmtx cut two bytes short, so the
                       last glyph has no entry at all
  metrics-nohmtx.ttf   metrics.ttf without hmtx
  metrics-vert.ttf     metrics.ttf with vhea and vmtx: every vertical
                       advance is 1000, and every top side bearing puts the
                       glyph's top 880 above the baseline
  metrics-cff.otf      the same glyphs in CFF, with vhea, vmtx and VORG
                       (default origin 880; p's origin is 800)
  metrics-cff-novorg.otf  metrics-cff.otf without VORG
"""
import os
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.fixedTools import otRound
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

CMAP = {".notdef": None, "space": 0x20, "H": 0x48, "L": 0x4C, "p": 0x70,
        "x": 0x78, "zero": 0x30, "one": 0x31, "two": 0x32}
ORDER = list(CMAP)

# name: (advance, rectangles as (x0, y0, x1, y1))
GLYPHS = {
    ".notdef": (500, [(50, 0, 450, 700)]),
    "space":   (250, []),
    "H":       (600, [(80, 0, 180, 700), (420, 0, 520, 700), (180, 300, 420, 400)]),
    "L":       (560, [(80, 0, 180, 700), (180, 0, 480, 100)]),
    "p":       (560, [(80, -210, 180, 500), (180, 400, 480, 500), (380, 100, 480, 400),
                      (180, 100, 380, 200)]),
    "x":       (500, [(100, 0, 400, 300)]),
    "zero":    (550, [(60, 0, 490, 700)]),
    "one":     (550, [(200, 0, 350, 700)]),
    "two":     (550, [(60, 0, 490, 680)]),
}
# Left side bearings as hmtx stores them: xMin, except for L.
LSB = {g: (min(r[0] for r in rects) if rects else 0) for g, (_, rects) in GLYPHS.items()}
LSB["L"] = 160

VORIGIN = 880      # where the top of every glyph sits in vertical text
VADVANCE = 1000


def ymax(g):
    rects = GLYPHS[g][1]
    return max(r[3] for r in rects) if rects else 0


def draw(pen, rects):
    for x0, y0, x1, y1 in rects:
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
        pen.closePath()


def builder(cff=False):
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(ORDER)
    fb.setupCharacterMap({cp: g for g, cp in CMAP.items() if cp})
    if cff:
        charstrings = {}
        for g in ORDER:
            pen = T2CharStringPen(GLYPHS[g][0], None)
            draw(pen, GLYPHS[g][1])
            charstrings[g] = pen.getCharString()
        fb.setupCFF("HBBookMetricsTest", {"FullName": "HBBook Metrics Test"}, charstrings, {})
    else:
        glyphs = {}
        for g in ORDER:
            pen = TTGlyphPen(None)
            draw(pen, GLYPHS[g][1])
            glyphs[g] = pen.glyph()
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({g: (GLYPHS[g][0], LSB[g]) for g in ORDER})
    fb.setupHorizontalHeader(ascent=900, descent=-300, lineGap=0)
    fb.setupNameTable({"familyName": "HBBook Metrics Test", "styleName": "Regular"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=100,
                usWinAscent=950, usWinDescent=350, sxHeight=500, sCapHeight=700)
    fb.setupPost()
    return fb


def add_vertical(fb):
    fb.setupVerticalHeader(ascent=500, descent=-500)
    fb.setupVerticalMetrics({g: (VADVANCE, VORIGIN - ymax(g) if GLYPHS[g][1] else 0)
                             for g in ORDER})


def build(out):
    os.makedirs(out, exist_ok=True)
    path = lambda name: os.path.join(out, name)

    fb = builder()
    fb.setupCOLR({"x": [("H", 0), ("p", 1)]})
    fb.setupCPAL([[(0.8, 0.1, 0.1, 1.0), (0.1, 0.2, 0.8, 1.0)]])
    fb.save(path("metrics.ttf"))

    f = TTFont(path("metrics.ttf"))
    f["OS/2"].fsSelection |= 1 << 7  # USE_TYPO_METRICS
    f.save(path("metrics-typo.ttf"))

    # Table data is copied as it is: recalcBBoxes=False keeps fontTools from
    # rebuilding hhea from the (now missing or shortened) hmtx.
    f = TTFont(path("metrics.ttf"), recalcBBoxes=False)
    short = DefaultTable("hmtx")
    short.data = f.getTableData("hmtx")[:-2]
    f["hmtx"] = short
    f.save(path("metrics-short.ttf"))

    f = TTFont(path("metrics.ttf"), recalcBBoxes=False)
    del f["hmtx"]
    f.save(path("metrics-nohmtx.ttf"))

    fb = builder()
    add_vertical(fb)
    fb.save(path("metrics-vert.ttf"))

    fb = builder(cff=True)
    add_vertical(fb)
    fb.save(path("metrics-cff-novorg.otf"))
    fb.setupVerticalOrigins({"p": 800}, defaultVerticalOrigin=VORIGIN)
    fb.save(path("metrics-cff.otf"))

    for name in sorted(os.listdir(out)):
        if name.endswith((".ttf", ".otf")):
            print(path(name))


if __name__ == "__main__":
    build(sys.argv[1])
