"""Build the test fonts for the appendix “Feature order”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

For each script tag below, two fonts, order-TAG-a.ttf and order-TAG-b.ttf.
Both have one lookup for every feature tag any of HarfBuzz’s shapers asks
for (FEATURES), plus smcp, for a feature an application asks for. Each
lookup substitutes, or moves, an unencoded glyph that never appears in the
text, so it never changes anything: it is there to be seen in the trace,
which lists every lookup in the plan, in the order HarfBuzz runs them.

In the -a font the lookups are numbered in alphabetical order of their
feature tags, and in the -b font in reverse. Within one stage, HarfBuzz runs
lookups in LookupList order, so the two fonts give opposite orders; across
stages they give the same one. The `order` block in tools/build-site.mjs
shapes both and finds the stages from where the orders agree.

The features are registered under the script tag and DFLT, for the default
language system. Glyphs are plain boxes.
"""
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

# Every tag in hb-ot-shape.cc and hb-ot-shaper-*.cc that is a feature
# (HarfBuzz 15.1.0), and smcp. The GPOS ones get a single adjustment, the
# rest a single substitution.
GPOS = ["abvm", "blwm", "curs", "dist", "kern", "mark", "mkmk"]
GSUB = sorted("""
  BUZZ Buzz HARF Harf abvf abvs akhn blwf blws calt ccmp cfar cjct clig cswh
  dnom fin2 fin3 fina frac half haln init isol liga ljmo locl ltra ltrm med2
  medi mset nukt numr pref pres pstf psts rand rclt rkrf rlig rphf rtla rtlm
  rvrn smcp stch tjmo vatu vert vjmo
""".split())

# Script tag: the characters the appendix shapes with it.
SCRIPTS = {
    "latn": "a",
    "arab": "بب",
    "hebr": "א",
    "dev2": "कि",
    "khmr": "ក",
    "mym2": "က",
    "bali": "ᬓ",
    "hang": "한",
}


def box(width):
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0)); pen.lineTo((50, 500))
    pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
    pen.closePath()
    return pen.glyph()


def fea(script, reverse):
    out = ["languagesystem DFLT dflt;", f"languagesystem {script} dflt;", ""]
    for table, tags in (("sub", GSUB), ("pos", GPOS)):
        for tag in (reversed(tags) if reverse else tags):
            rule = "sub dummy by dummy.alt;" if table == "sub" else "pos dummy -10;"
            out.append(f"lookup L_{tag} {{ {rule} }} L_{tag};")
    out.append("")
    for tag in GSUB + GPOS:
        out.append(f"feature {tag} {{ lookup L_{tag}; }} {tag};")
    return "\n".join(out) + "\n"


def build(script, text, reverse, out):
    chars = sorted(set(text))
    names = [f"uni{ord(c):04X}" for c in chars]
    order = [".notdef", "dummy", "dummy.alt"] + names
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(c): n for c, n in zip(chars, names)})
    fb.setupGlyf({g: box(500) for g in order})
    fb.setupHorizontalMetrics({g: (500, 50) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Feature Order", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea(script, reverse))
    fb.save(out)


if __name__ == "__main__":
    for script, text in SCRIPTS.items():
        for suffix, reverse in (("a", False), ("b", True)):
            build(script, text, reverse, f"order-{script}-{suffix}.ttf")
