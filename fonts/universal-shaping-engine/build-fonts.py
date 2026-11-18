"""Build the test fonts for “The Universal Shaping Engine”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every font has plain boxes for glyphs, as in the other chapters' test
fonts. The Devanagari fonts come in pairs that differ only in the script
tag, dev2 (the Indic shaper) or dev3 (the USE):

  deva2.ttf, deva3.ttf                       devanagari.fea whole: rphf, akhn,
                                             blwf, half, init,
                                             pres
  deva2-half-first.ttf, deva3-half-first.ttf the half block moved before
                                             blwf, so its lookup comes first
                                             in the LookupList
  deva2-no-half.ttf, deva3-no-half.ttf       without half

  balinese.ttf          balinese.fea: blwf makes two subjoined consonants
  balinese-no-blwf.ttf  without blwf
"""
import re

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

# glyph name: (Unicode code point or None, advance width)
DEVANAGARI = {
    ".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500),
    "nbsp": (0xA0, 250),
    "ka": (0x915, 600), "ta": (0x924, 550), "ra": (0x930, 500), "ssa": (0x937, 600),
    "virama": (0x94D, 0), "iMatra": (0x93F, 250), "uMatra": (0x941, 0),
    "anusvara": (0x902, 0),
    "ka.half": (None, 400), "ta.half": (None, 350), "k_ssa": (None, 800),
    "reph": (None, 0), "rakar": (None, 0), "iMatra.init": (None, 250),
    "ta_ta": (None, 900),
}
BALINESE = {
    ".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500),
    "ka": (0x1B13, 600), "ta": (0x1B22, 600), "sa": (0x1B32, 600),
    "adeg": (0x1B44, 0), "taling": (0x1B3E, 300), "tedung": (0x1B35, 300),
    "suku": (0x1B38, 0), "ulu": (0x1B36, 0), "surang": (0x1B03, 0),
    "cecek": (0x1B02, 0), "bisah": (0x1B04, 250),
    "ka.sub": (None, 0), "ta.sub": (None, 0),
}


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build(out, glyphs, fea):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({cp: g for g, (cp, _) in glyphs.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook USE Test " + out[:-4], "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


def block(fea, tag):
    m = re.search(rf"^(# [^\n]*\n)*feature {tag} \{{.*?^\}} {tag};\n", fea, flags=re.S | re.M)
    assert m, tag
    return m.group(0)


def without(fea, *tags):
    for tag in tags:
        fea = fea.replace(block(fea, tag), "")
    return fea


def main():
    deva = open("devanagari.fea").read()
    half_first = without(deva, "half").replace(block(deva, "blwf"),
                                               block(deva, "half") + "\n" + block(deva, "blwf"))
    for n in "23":
        tag = "dev" + n
        build(f"deva{n}.ttf", DEVANAGARI, deva.replace("SCRIPT", tag))
        build(f"deva{n}-half-first.ttf", DEVANAGARI, half_first.replace("SCRIPT", tag))
        build(f"deva{n}-no-half.ttf", DEVANAGARI, without(deva, "half").replace("SCRIPT", tag))
    bali = open("balinese.fea").read()
    build("balinese.ttf", BALINESE, bali)
    build("balinese-no-blwf.ttf", BALINESE, without(bali, "blwf"))


if __name__ == "__main__":
    main()
