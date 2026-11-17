"""Build the test fonts for “Hebrew, Thai, Lao and Hangul”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Fonts written:
  hebrew-old.ttf       Hebrew letters, points, and a few of the presentation
                       forms (U+FB1D..FB4B) in its cmap, with no GDEF, GSUB
                       or GPOS, like an old font
  hebrew-mark.ttf      hebrew-old.ttf with GDEF and a GPOS mark feature
                       under hebr (hebrew.fea)
  hebrew-mark-DFLT.ttf the same, with the mark feature under DFLT
  thai.ttf             Thai and Lao letters and marks, with a GSUB under
                       thai and lao (thai.fea)
  thai-pua.ttf         the same glyphs with no layout tables at all, and the
                       shifted and descender-less forms encoded at the
                       Windows private-use code points (U+F700..F71A), as in
                       old Windows Thai fonts
  thai-pua-mac.ttf     thai-pua.ttf with those forms at the Mac private-use
                       code points (U+F884..F89E) instead
  thai-am-only.ttf     thai-pua.ttf without glyphs for NIKHAHIT and SARA AA,
                       only one for SARA AM
  hangul.ttf           two precomposed syllables, GA and GAK, the modern
                       jamo they are made of, three Old Hangul jamo, the
                       tone marks and a dotted circle, with ljmo, vjmo, tjmo
                       and calt (hangul.fea)
  hangul-no-gak.ttf    hangul.ttf without GAK
  hangul-koh.ttf       hangul.ttf with ljmo, vjmo and tjmo only under the
                       Old Hangul language system, KOH

Marks have zero advance and are drawn to the left of their origin, over
the glyph before them. The Thai glyphs are drawn so that the differences
between a mark's forms show: tone marks sit high, or lower where there
is no vowel above, and to the left of PO PLA's ascender; SARA U sits
under a removable descender, or lower under a fixed one. Everything else
is a plain box.
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures, addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]


def box(width, top=500):
    return [rect(50, 0, width - 50, top)] if width else []


def mark(x0, y0, x1, y1):
    return (0, [rect(x0, y0, x1, y1)])


# glyph name: (Unicode code point or None, advance width, contours)
HEBREW = {
    ".notdef": (None, 500, box(500, 700)), "space": (0x20, 250, []),
    "alef": (0x5D0, 600, box(600)), "bet": (0x5D1, 600, box(600)),
    "vav": (0x5D5, 300, box(300)), "het": (0x5D7, 600, box(600)),
    "yod": (0x5D9, 300, box(300, 250)), "lamed": (0x5DC, 600, box(600, 750)),
    "shin": (0x5E9, 700, box(700)),
    "sheva": (0x5B0, *mark(-350, -250, -250, -100)),
    "hiriq": (0x5B4, *mark(-350, -200, -250, -100)),
    "patah": (0x5B7, *mark(-500, -150, -100, -100)),
    "qamats": (0x5B8, *mark(-500, -250, -100, -100)),
    "holam": (0x5B9, *mark(-550, 600, -450, 700)),
    "dagesh": (0x5BC, *mark(-350, 200, -250, 300)),
    "meteg": (0x5BD, *mark(-325, -250, -275, -100)),
    "shindot": (0x5C1, *mark(-150, 650, -50, 750)),
    "sindot": (0x5C2, *mark(-650, 650, -550, 750)),
    "etnahta": (0x591, *mark(-350, -300, -250, -150)),
    # presentation forms
    "yod_hiriq": (0xFB1D, 300, box(300, 250)),
    "shin_shindot": (0xFB2A, 700, box(700, 600)),
    "shin_sindot": (0xFB2B, 700, box(700, 600)),
    "shin_dagesh_shindot": (0xFB2C, 700, box(700, 600)),
    "bet_dagesh": (0xFB31, 600, box(600, 600)),
    "vav_dagesh": (0xFB35, 300, box(300, 600)),
    "vav_holam": (0xFB4B, 300, box(300, 600)),
}

# Thai consonants: a box, with an ascender at the right, or a descender.
DESCENDER = rect(50, -200, 450, -150)
THAI = {
    ".notdef": (None, 500, box(500, 700)), "space": (0x20, 250, []),
    "dottedcircle": (0x25CC, 500, box(500, 400)),
    "kokai": (0xE01, 500, box(500)),
    "dodek": (0xE14, 500, box(500)),
    "popla": (0xE1B, 500, box(500) + [rect(400, 500, 450, 800)]),
    "yoying": (0xE0D, 500, box(500) + [DESCENDER]),
    "thothan": (0xE10, 500, box(500) + [DESCENDER]),
    "dochada": (0xE0E, 500, box(500) + [DESCENDER]),
    "saraaa": (0xE32, 300, box(300)),
    "saraam": (0xE33, 300, box(300) + [rect(-150, 600, -50, 700)]),
    "sarai": (0xE34, *mark(-450, 550, -75, 650)),
    "sarau": (0xE38, *mark(-150, -175, -100, -50)),
    "maiek": (0xE48, *mark(-175, 700, -75, 850)),
    "maitho": (0xE49, *mark(-200, 700, -100, 850)),
    "maichattawa": (0xE4B, *mark(-200, 700, -50, 850)),
    "nikhahit": (0xE4D, *mark(-250, 550, -150, 650)),
    # The shifted forms (encoded only in the PUA fonts) and YO YING without
    # its descender (used by thai.ttf's ccmp, and by the PUA fonts).
    "maiek.low": (None, *mark(-175, 550, -75, 700)),
    "maiek.lowleft": (None, *mark(-375, 550, -275, 700)),
    "maiek.left": (None, *mark(-375, 700, -275, 850)),
    "sarai.left": (None, *mark(-600, 550, -225, 650)),
    "nikhahit.left": (None, *mark(-400, 550, -300, 650)),
    "sarau.low": (None, *mark(-150, -425, -100, -300)),
    "yoying.nodesc": (None, 500, box(500)),
    "thothan.nodesc": (None, 500, box(500)),
    # Lao
    "lko": (0xE81, 500, box(500)),
    "lsaraaa": (0xEB2, 300, box(300)),
    "lsaraam": (0xEB3, 300, box(300) + [rect(-150, 600, -50, 700)]),
    "lmaiek": (0xEC8, *mark(-150, 700, -100, 850)),
    "lnikhahit": (0xECD, *mark(-250, 550, -150, 650)),
}

# Each shifted form: its Windows and Mac private-use code points, from
# thai_pua_shape in hb-ot-shaper-thai.cc.
THAI_PUA = {
    "maiek.low": (0xF70A, 0xF88B),      # SD
    "maiek.lowleft": (0xF705, 0xF88C),  # SDL
    "maiek.left": (0xF713, 0xF88A),     # SL
    "sarai.left": (0xF701, 0xF885),     # SL
    "nikhahit.left": (0xF711, 0xF899),  # SL
    "sarau.low": (0xF718, 0xF89B),      # SD
    "yoying.nodesc": (0xF70F, 0xF89A),  # RD
    "thothan.nodesc": (0xF700, 0xF89E), # RD
}

HANGUL = {
    ".notdef": (None, 500, box(500, 700)), "space": (0x20, 250, []),
    "dottedcircle": (0x25CC, 500, box(500, 400)),
    "ga": (0xAC00, 1000, box(1000)), "gak": (0xAC01, 1000, box(1000)),
    "ga.calt": (None, 1000, box(1000, 600)),
    "kiyeok": (0x1100, 500, box(500)), "a": (0x1161, 500, box(500)),
    "kiyeokT": (0x11A8, 500, box(500, 250)),
    "hieuh": (0x1112, 500, box(500)), "araea": (0x119E, 500, box(500)),
    "nieunT": (0x11AB, 500, box(500, 250)), "pansiosT": (0x11EB, 500, box(500, 250)),
    "kiyeok.calt": (None, 500, box(500, 600)),
    "singledot": (0x302E, 200, box(200, 300)),
    "doubledot": (0x302F, 0, [rect(-150, 200, -50, 300), rect(-150, 400, -50, 500)]),
}
for g in ["kiyeok", "hieuh"]:
    HANGUL[g + ".ljmo"] = (None, 500, box(500, 600))
for g in ["a", "araea"]:
    HANGUL[g + ".vjmo"] = (None, 500, box(500, 600))
for g in ["kiyeokT", "nieunT", "pansiosT"]:
    HANGUL[g + ".tjmo"] = (None, 500, box(500, 300))


def glyph(contours):
    pen = TTGlyphPen(None)
    for c in contours:
        pen.moveTo(c[0])
        for p in c[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen.glyph()


def build(glyphs, name, extra_cmap=None, drop=()):
    glyphs = {g: v for g, v in glyphs.items() if g not in drop}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    cmap = {cp: g for g, (cp, _, _) in glyphs.items() if cp}
    cmap.update(extra_cmap or {})
    fb.setupCharacterMap(cmap)
    fb.setupGlyf({g: glyph(c) for g, (_, _, c) in glyphs.items()})
    glyf = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (w, getattr(glyf[g], "xMin", 0)) for g, (_, w, _) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=900, descent=-450)
    fb.setupNameTable({"familyName": "HBBook Small Shapers " + name, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-450, usWinAscent=900, usWinDescent=450)
    fb.setupPost()
    return fb.font


def main():
    build(HEBREW, "Hebrew Old").save("hebrew-old.ttf")
    hebrew = open("hebrew.fea").read()
    for tag, out in [("hebr", "hebrew-mark.ttf"), ("DFLT", "hebrew-mark-DFLT.ttf")]:
        font = TTFont("hebrew-old.ttf")
        addOpenTypeFeaturesFromString(font, hebrew.replace("SCRIPT", tag))
        font.save(out)

    font = build(THAI, "Thai")
    addOpenTypeFeatures(font, "thai.fea")
    font.save("thai.ttf")
    build(THAI, "Thai PUA", {win: g for g, (win, mac) in THAI_PUA.items()}).save("thai-pua.ttf")
    build(THAI, "Thai PUA Mac", {mac: g for g, (win, mac) in THAI_PUA.items()}).save("thai-pua-mac.ttf")
    build(THAI, "Thai AM Only", drop=("nikhahit", "saraaa")).save("thai-am-only.ttf")

    font = build(HANGUL, "Hangul")
    addOpenTypeFeatures(font, "hangul.fea")
    font.save("hangul.ttf")
    font = build(HANGUL, "Hangul No GAK", drop=("gak",))
    addOpenTypeFeatures(font, "hangul.fea")
    font.save("hangul-no-gak.ttf")
    font = build(HANGUL, "Hangul KOH")
    addOpenTypeFeaturesFromString(
        font, open("hangul.fea").read().replace("#KOH", "script hang; language KOH exclude_dflt;"))
    font.save("hangul-koh.ttf")


if __name__ == "__main__":
    main()
