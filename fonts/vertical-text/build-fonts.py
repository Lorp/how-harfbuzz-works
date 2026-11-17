"""Build the test fonts for “Vertical text”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Fonts written:
  vertical.ttf   from vertical.fea: CJK-style punctuation and brackets with
                 vertical alternates under `vert`, `vkrn` and `vpal`, a kana
                 with a combining voiced-sound mark attached by `mark`, a
                 cursive chain under `curs`, and Latin a and b with `liga`
                 and `kern`. It has `vhea` and `vmtx`: every glyph advances
                 1000 units down, and hangs from y = 880. It also encodes the
                 vertical presentation forms (U+FE11 and the rest).
  novert.ttf     vertical.ttf without its `vert` feature, so HarfBuzz falls
                 back to the presentation forms
  vert-kana.ttf  vertical.ttf with `vert` listed only under the `kana`
                 script, where Han text won't look for it
  vrt2.ttf       vertical.ttf with `vrt2` in place of `vert`, with a second lookup
                 that turns `a` into a rotated `a.rot`

Every glyph is a box; only its bounds matter.
"""
import re

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

TOP = 880   # every glyph's vertical origin: yMax + top side bearing
VADV = 1000

# glyph name: (code point or None, advance width, box (xMin, yMin, xMax, yMax))
GLYPHS = {
    ".notdef": (None, 1000, (100, -70, 900, 830)),
    "space": (0x20, 250, None),
    "parenleft": (0x28, 300, (100, -100, 200, 800)),
    "parenright": (0x29, 300, (100, -100, 200, 800)),
    "a": (0x61, 500, (50, 0, 450, 500)),
    "b": (0x62, 500, (50, 0, 450, 700)),
    "l": (0x6C, 1000, (300, -70, 700, 830)),
    "ellipsis": (0x2026, 1000, (100, 0, 900, 100)),
    "ideocomma": (0x3001, 1000, (100, -70, 300, 130)),
    "ideoperiod": (0x3002, 1000, (100, -70, 300, 130)),
    "cornerleft": (0x300C, 1000, (600, 100, 800, 830)),
    "cornerright": (0x300D, 1000, (200, -70, 400, 660)),
    "parenleftfw": (0xFF08, 1000, (600, -70, 800, 830)),
    "parenrightfw": (0xFF09, 1000, (200, -70, 400, 830)),
    "ka": (0x304B, 1000, (100, -20, 900, 780)),
    "dakuten": (0x3099, 0, (50, 700, 250, 900)),
    "ideo": (0x6C34, 1000, (50, -70, 950, 830)),
    # The vertical presentation forms, encoded.
    "uniFE11": (0xFE11, 1000, (700, 630, 900, 830)),
    "uniFE12": (0xFE12, 1000, (700, 630, 900, 830)),
    "uniFE19": (0xFE19, 1000, (450, -70, 550, 830)),
    "uniFE35": (0xFE35, 1000, (50, 600, 950, 800)),
    "uniFE36": (0xFE36, 1000, (50, -40, 950, 160)),
    "uniFE41": (0xFE41, 1000, (100, 630, 900, 830)),
    "uniFE42": (0xFE42, 1000, (100, -70, 900, 130)),
    # The vertical alternates, unencoded.
    "ellipsis.vert": (None, 1000, (450, -70, 550, 830)),
    "ideocomma.vert": (None, 1000, (700, 630, 900, 830)),
    "ideoperiod.vert": (None, 1000, (700, 630, 900, 830)),
    "cornerleft.vert": (None, 1000, (100, 630, 900, 830)),
    "cornerright.vert": (None, 1000, (100, -70, 900, 130)),
    "parenleftfw.vert": (None, 1000, (50, 600, 950, 800)),
    "parenrightfw.vert": (None, 1000, (50, -40, 950, 160)),
    "a_b": (None, 900, (50, 0, 850, 700)),
    "a.rot": (None, 1000, (100, 380, 600, 780)),
}


def box(b):
    pen = TTGlyphPen(None)
    if b:
        x0, y0, x1, y1 = b
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1))
        pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def build(out, fea):
    order = list(GLYPHS)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, (cp, _, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(b) for g, (_, _, b) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, b[0] if b else 0) for g, (_, w, b) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupVerticalMetrics({g: (VADV, TOP - b[3] if b else 0) for g, (_, _, b) in GLYPHS.items()})
    fb.setupVerticalHeader(ascent=500, descent=-500)
    fb.setupNameTable({"familyName": "HBBook Vertical Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=880, sTypoDescender=-120, usWinAscent=880, usWinDescent=120)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


def block(src, tag):
    m = re.search(rf"^feature {tag} \{{.*?^\}} {tag};\n", src, re.S | re.M)
    assert m, tag
    return m


if __name__ == "__main__":
    src = open("vertical.fea").read()
    build("vertical.ttf", src)

    vert = block(src, "vert")
    build("novert.ttf", src[:vert.start()] + src[vert.end():])

    kana = vert.group(0).replace("feature vert {\n", "feature vert {\n  script kana;\n")
    build("vert-kana.ttf", src[:vert.start()] + kana + src[vert.end():])

    vrt2 = (vert.group(0).replace("feature vert", "feature vrt2").replace("} vert;", "} vrt2;")
            .replace("VERT", "VRT2")
            .replace("  } VRT2;", "  } VRT2;\n  lookup ROTATE {\n    sub a by a.rot;\n  } ROTATE;"))
    build("vrt2.ttf", src[:vert.start()] + vrt2 + src[vert.end():])
