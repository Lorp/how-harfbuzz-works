"""Build the test fonts for “Khmer and Myanmar”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Glyphs are plain boxes, as in the other chapters' test fonts.

  khmer.ttf          khmer.fea: pref (COENG + RO), blwf (COENG + KA, KO,
                     NGO), abvf (the above part of OE), pstf (the right
                     part of OO), cfar (KO's subscript after COENG RO),
                     and psts (a shorter OO before KA)
  khmer-no-pref.ttf  the same without pref
  khmer-late.ttf     the same, with cfar's lookup put first in the
                     LookupList, before blwf's
  myanmar.ttf        myanmar.fea: rphf (kinzi), pref (a wide medial RA
                     before a consonant) and blwf (VIRAMA + KA)
"""
import re

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

COMMON = {".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500)}

# glyph name: (Unicode code point or None, advance width)
KHMER = dict(COMMON, **{
    "ka": (0x1780, 600), "ko": (0x1782, 600), "ngo": (0x1784, 600), "ro": (0x179A, 500),
    "coeng": (0x17D2, 0), "aa": (0x17B6, 300), "e": (0x17C1, 300),
    "oe": (0x17BE, 0), "oo": (0x17C4, 300),
    "ro.pref": (None, 300), "ka.sub": (None, 0), "ko.sub": (None, 0),
    "ko.sub.cfar": (None, 0), "ngo.sub": (None, 0),
    "oe.abv": (None, 0), "oo.pst": (None, 250), "oo.pst.short": (None, 150),
})

MYANMAR = dict(COMMON, **{
    "ka": (0x1000, 600), "ga": (0x1002, 600), "nga": (0x1004, 600),
    "asat": (0x103A, 0), "virama": (0x1039, 0), "medialra": (0x103C, 300),
    "e": (0x1031, 300), "u": (0x102F, 0), "anusvara": (0x1036, 0),
    "i": (0x102D, 0), "aa": (0x102C, 300), "medialya": (0x103B, 250), "medialwa": (0x103D, 0),
    "kinzi": (None, 0), "ka.sub": (None, 0), "medialra.wide": (None, 400),
})


def box(width):
    pen = TTGlyphPen(None)
    w = width or 200   # marks: a small box, drawn left of the origin
    x0, x1 = (50, width - 50) if width else (-w + 50, -50)
    pen.moveTo((x0, 0)); pen.lineTo((x0, 500))
    pen.lineTo((x1, 500)); pen.lineTo((x1, 0))
    pen.closePath()
    return pen.glyph()


def build(out, glyphs, fea, family):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({cp: g for g, (cp, _) in glyphs.items() if cp})
    fb.setupGlyf({g: (TTGlyphPen(None).glyph() if g == "space" else box(w))
                  for g, (_, w) in glyphs.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook " + family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


def block(fea, tag):
    m = re.search(rf"^feature {tag} \{{.*?^\}} {tag};\n", fea, flags=re.S | re.M)
    assert m, tag
    return m.group(0)


def main():
    khmer = open("khmer.fea").read()
    build("khmer.ttf", KHMER, khmer, "Khmer Test")
    build("khmer-no-pref.ttf", KHMER, khmer.replace(block(khmer, "pref"), ""),
          "Khmer Test No Pref")
    # Lookups are numbered in the order the feature blocks come in, so
    # moving cfar's block to the front puts its lookup first.
    cfar = block(khmer, "cfar")
    late = khmer.replace(cfar, "")
    late = late.replace("feature pref {", cfar + "\nfeature pref {")
    build("khmer-late.ttf", KHMER, late, "Khmer Test Late")
    build("myanmar.ttf", MYANMAR, open("myanmar.fea").read(), "Myanmar Test")


if __name__ == "__main__":
    main()
