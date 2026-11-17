"""Build the test fonts for “Dotted circles and broken clusters”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

All three fonts have the same glyphs (plain boxes): a Latin a and a
combining acute, a few Devanagari, Khmer, Myanmar and Brahmi letters and
vowel signs, and a dotted circle. They are compiled from circles.fea.

  circle.ttf     the whole file: GDEF, rphf, and a mark feature that
                 attaches the acute and Devanagari vowel sign U to a, KA
                 and the dotted circle
  no-circle.ttf  the same, but its cmap doesn't map U+25CC: the glyph
                 dottedcircle is still there, but no character reaches it
  bare.ttf       the same as circle.ttf, without GDEF or GPOS
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250), "nbsp": (0xA0, 250),
    "dottedcircle": (0x25CC, 500),
    # Latin
    "a": (0x61, 500), "acutecomb": (0x301, 0),
    # Devanagari
    "ka": (0x915, 600), "a.deva": (0x905, 600), "i.deva": (0x907, 500),
    "ra": (0x930, 500), "virama": (0x94D, 0), "aaMatra": (0x93E, 250),
    "iMatra": (0x93F, 250), "uMatra": (0x941, 0), "eMatra": (0x947, 0),
    "reph": (None, 0),
    # Khmer
    "ka.khmr": (0x1780, 600), "aa.khmr": (0x17B6, 300),
    # Myanmar
    "ka.mymr": (0x1000, 600), "i.mymr": (0x102D, 0),
    # Brahmi
    "a.brah": (0x11005, 600), "aa.brah": (0x11038, 0),
}


def box(width):
    pen = TTGlyphPen(None)
    w = width or 200   # marks: a small box, drawn left of the origin
    x0, x1 = (50, width - 50) if width else (-w + 50, -50)
    pen.moveTo((x0, 0)); pen.lineTo((x0, 500))
    pen.lineTo((x1, 500)); pen.lineTo((x1, 0))
    pen.closePath()
    return pen.glyph()


def build(out, fea, cmap_skip=(), drop=()):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(GLYPHS))
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items()
                          if cp and cp not in cmap_skip})
    fb.setupGlyf({g: (TTGlyphPen(None).glyph() if g in ("space", "nbsp") else box(w))
                  for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Dotted Circle " + out[:-4],
                       "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    for tag in drop:
        del fb.font[tag]
    fb.save(out)


def main():
    fea = open("circles.fea").read()
    build("circle.ttf", fea)
    build("no-circle.ttf", fea, cmap_skip=(0x25CC,))
    build("bare.ttf", fea, drop=("GDEF", "GPOS"))


if __name__ == "__main__":
    main()
