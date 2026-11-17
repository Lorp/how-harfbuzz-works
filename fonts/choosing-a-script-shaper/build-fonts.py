"""Build the test fonts for “Choosing a script shaper”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every font has the same glyphs (plain boxes, as in the other chapters'
test fonts) and the same cmap. Within each family, the fonts are built from
one feature file and differ only in the script tags written into it:

  indic-dev2.ttf   indic.fea with dev2      (the new Indic model)
  indic-deva.ttf   indic.fea with deva      (the old Indic model)
  indic-dev3.ttf   indic.fea with dev3      (sent to the USE)
  indic-DFLT.ttf   indic.fea with DFLT
  indic-latn.ttf   indic.fea with latn
  indic-typo.ttf   indic-dev2.ttf with its script tag changed to dflt, the
                   misspelling of DFLT that some fonts have (feaLib won't
                   write it, so it is patched in after compiling)
  indic-both.ttf   indic.fea with dev2, and the same again with deva
  indic-none.ttf   no GSUB or GPOS at all, only GDEF
  join-arab.ttf    joining.fea with arab and syrc
  join-DFLT.ttf    joining.fea with DFLT
  join-latn.ttf    joining.fea with latn
  hebrew-hebr.ttf  hebrew.fea with hebr
  hebrew-DFLT.ttf  hebrew.fea with DFLT
  myanmar-mym2.ttf myanmar.fea with mym2
  myanmar-mymr.ttf myanmar.fea with mymr
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250), "dottedcircle": (0x25CC, 500),
    # Devanagari
    "ka": (0x915, 600), "ssa": (0x937, 600), "ra": (0x930, 500),
    "virama": (0x94D, 0), "iMatra": (0x93F, 250),
    "k_ssa": (None, 800), "rakar": (None, 0), "ra.mar": (None, 500),
    # Arabic BEH and Syriac BETH, each in four forms
    "beh": (0x628, 600), "beh.init": (None, 400), "beh.medi": (None, 400), "beh.fina": (None, 600),
    "beth": (0x712, 600), "beth.init": (None, 450), "beth.medi": (None, 450), "beth.fina": (None, 650),
    # Hebrew ALEF and the point HIRIQ
    "alef": (0x5D0, 600), "hiriq": (0x5B4, 0),
    # Myanmar KA and medial RA
    "mka": (0x1000, 600), "medialRa": (0x103C, 200), "ra_mka": (None, 800),
}


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build(out, fea):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(GLYPHS))
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Script Shaper Test " + out[:-4], "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(out)


def main():
    indic = open("indic.fea").read()
    for tag in ["dev2", "deva", "dev3", "DFLT", "latn"]:
        build(f"indic-{tag}.ttf", indic.replace("SCRIPT", tag))
    font = TTFont("indic-dev2.ttf")
    font["GSUB"].table.ScriptList.ScriptRecord[0].ScriptTag = "dflt"
    font.save("indic-typo.ttf")
    # Both tags. akhn and blwf name no script, so feaLib registers them
    # under every language system, deva's as well as dev2's.
    head, body = indic.split("table GDEF", 1)
    body = "table GDEF" + body
    both = (head.replace("SCRIPT", "dev2") +
            "languagesystem deva dflt;\nlanguagesystem deva MAR;\n" + body.replace("SCRIPT", "dev2"))
    build("indic-both.ttf", both)
    # GDEF only: no GSUB, no GPOS.
    build("indic-none.ttf", body[:body.index("} GDEF;") + len("} GDEF;")].replace("SCRIPT", "dev2"))

    joining = open("joining.fea").read()
    for name, systems in [("arab", ["arab", "syrc"]), ("DFLT", ["DFLT"]), ("latn", ["latn"])]:
        lines = "\n".join(f"languagesystem {s} dflt;" for s in systems)
        build(f"join-{name}.ttf", joining.replace("LANGUAGESYSTEMS", lines))

    hebrew = open("hebrew.fea").read()
    for tag in ["hebr", "DFLT"]:
        build(f"hebrew-{tag}.ttf", hebrew.replace("SCRIPT", tag))

    myanmar = open("myanmar.fea").read()
    for tag in ["mym2", "mymr"]:
        build(f"myanmar-{tag}.ttf", myanmar.replace("SCRIPT", tag))


if __name__ == "__main__":
    main()
