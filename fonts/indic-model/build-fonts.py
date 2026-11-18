"""Build the test fonts for “The Indic model”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every font has the same glyphs (plain boxes, as in the other chapters'
test fonts) and the same cmap, and its lookups are under dev2. They are
compiled from indic-model.fea, whole or with feature blocks changed:

  full.ttf           the whole file: rphf, blwf, half, pstf and init
  no-rphf.ttf        without rphf
  no-blwf.ttf        without blwf
  no-blwf-half.ttf   without blwf and half
  old-order.ttf      blwf written in the old (deva) order, RA before the
                     virama, as some fonts copied it into dev2
  pref.ttf           pstf replaced by pref: YA's form is pre-base-reordering
  vatu-cjct.ttf      blwf replaced by vatu, which makes RA's below-base
                     form, and a cjct ligature of KA's half form and TA
                     (one more glyph, kta)

scripts.ttf is compiled from scripts.fea, with its own glyphs: a few each
of Bengali, Telugu, Kannada and Malayalam, under bng2, tel2, knd2 and mlm2.
"""
import re

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500),
    "nbsp": (0xA0, 250), "a": (0x905, 600),
    "ka": (0x915, 600), "ta": (0x924, 550), "ra": (0x930, 500), "ya": (0x92F, 550),
    "ssa": (0x937, 600), "virama": (0x94D, 0), "iMatra": (0x93F, 250),
    "uMatra": (0x941, 0), "anusvara": (0x902, 0),
    "ka.half": (None, 400), "ta.half": (None, 350), "reph": (None, 0),
    "rakar": (None, 0), "ya.post": (None, 300), "ya.pref": (None, 300),
    "iMatra.init": (None, 250),
}

VATU_CJCT_GLYPHS = {**GLYPHS, "kta": (None, 700)}

SCRIPTS_GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500),
    # Bengali
    "bn.ra": (0x9B0, 500), "bn.ya": (0x9AF, 550), "bn.virama": (0x9CD, 0),
    "bn.reph": (None, 0), "bn.ya.phalaa": (None, 250),
    # Telugu
    "te.ka": (0xC15, 600), "te.ra": (0xC30, 500), "te.virama": (0xC4D, 0),
    "te.reph": (None, 0), "te.ka.below": (None, 0),
    # Kannada
    "kn.ka": (0xC95, 600), "kn.ra": (0xCB0, 500), "kn.virama": (0xCCD, 0),
    "kn.reph": (None, 0), "kn.ka.below": (None, 0),
    # Malayalam
    "ml.ka": (0xD15, 600), "ml.ta": (0xD24, 550), "ml.na": (0xD28, 550),
    "ml.ra": (0xD30, 500), "ml.la": (0xD32, 550), "ml.virama": (0xD4D, 0),
    "ml.aaMatra": (0xD3E, 300), "ml.eMatra": (0xD46, 300), "ml.dotReph": (0xD4E, 0),
    "ml.na.chillu": (None, 450), "ml.la.below": (None, 0), "ml.ra.pref": (None, 300),
}


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build(out, fea, glyphs=GLYPHS):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({cp: g for g, (cp, _) in glyphs.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Indic Model Test " + out[:-4], "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


def without(fea, *tags):
    for tag in tags:
        fea, n = re.subn(rf"^feature {tag} \{{.*?^\}} {tag};\n", "", fea, flags=re.S | re.M)
        assert n == 1, tag
    return fea


def main():
    fea = open("indic-model.fea").read()
    build("full.ttf", fea)
    build("no-rphf.ttf", without(fea, "rphf"))
    build("no-blwf.ttf", without(fea, "blwf"))
    build("no-blwf-half.ttf", without(fea, "blwf", "half"))
    build("old-order.ttf", without(fea, "blwf") +
          "\nfeature blwf {\n    sub ra virama by rakar;\n} blwf;\n")
    build("pref.ttf", without(fea, "pstf") +
          "\nfeature pref {\n    sub virama ya by ya.pref;\n} pref;\n")
    build("vatu-cjct.ttf", without(fea, "blwf") +
          "\nfeature vatu {\n    sub virama ra by rakar;\n} vatu;\n"
          "\nfeature cjct {\n    sub ka.half ta by kta;\n} cjct;\n",
          VATU_CJCT_GLYPHS)
    build("scripts.ttf", open("scripts.fea").read(), SCRIPTS_GLYPHS)


if __name__ == "__main__":
    main()
