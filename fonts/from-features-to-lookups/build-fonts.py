"""Build the test fonts for the chapter “From features to lookups”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

  bits.ttf      27 features, each a single substitution of one character:
                cv01–cv06 turn a–f into a.alt–f.alt, ss01–ss20 turn g–z
                into g.alt–z.alt, and zero turns 0 into zero.alt. Asking
                for them over a range needs a mask bit each, which is how
                the chapter runs HarfBuzz out of bits.

  stages.ttf    a feature file (stages.fea) whose lookup numbers are
                chosen to show stages: ccmp's lookup comes before rvrn's
                in the LookupList, but rvrn still runs first. It also has
                a required feature, xreq, for the latn script.

  arabic.ttf    an Arabic font (arabic.fea) with lookups for Harf, Buzz,
                init and fina, numbered so that the order they run in
                shows the Arabic shaper's stages.

  varliga.ttf   variations/var.ttf with a liga feature (I -> H) and a
                FeatureVariations record that, from user weight 700 up,
                replaces liga's feature table with one whose only lookup
                is I -> V.

  varliga-minor1.ttf
                varliga.ttf with the FeatureVariations table's minorVersion
                set to 1 and nothing else changed.

Glyphs are plain boxes: only their names, the cmap and the layout tables
matter here.
"""
from fontTools.feaLib.builder import addOpenTypeFeatures, addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib.featureVars import addFeatureVariations


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build(glyphs, fea, out, fea_is_text=False):
    """glyphs: {name: codepoint or None}."""
    order = [".notdef"] + [g for g in glyphs if g != ".notdef"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in glyphs.items() if cp})
    widths = {g: 250 if g == "space" else 500 for g in order}
    fb.setupGlyf({g: box(0 if g == "space" else widths[g]) for g in order})
    fb.setupHorizontalMetrics({g: (widths[g], 50) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Map Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    if fea_is_text:
        addOpenTypeFeaturesFromString(fb.font, fea)
    else:
        addOpenTypeFeatures(fb.font, fea)
    fb.save(out)


def build_bits():
    letters = [chr(c) for c in range(ord("a"), ord("z") + 1)]
    tags = [f"cv{n:02d}" for n in range(1, 7)] + [f"ss{n:02d}" for n in range(1, 21)]
    glyphs = {"space": 0x20}
    for ch in letters:
        glyphs[ch] = ord(ch)
    glyphs["zero"] = 0x30
    for ch in letters:
        glyphs[ch + ".alt"] = None
    glyphs["zero.alt"] = None
    fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
    for tag, ch in zip(tags, letters):
        fea.append(f"feature {tag} {{ sub {ch} by {ch}.alt; }} {tag};")
    fea.append("feature zero { sub zero by zero.alt; } zero;")
    build(glyphs, "\n".join(fea) + "\n", "bits.ttf", fea_is_text=True)


def build_stages():
    glyphs = {"space": 0x20, "a": 0x61, "b": 0x62, "c": 0x63, "d": 0x64,
              "e": 0x65, "e.req": None}
    build(glyphs, "stages.fea", "stages.ttf")


def build_arabic():
    glyphs = {"space": 0x20, "beh": 0x0628, "teh": 0x062A,
              "beh.init": None, "beh.fina": None, "beh.buzz": None}
    build(glyphs, "arabic.fea", "arabic.ttf")


def build_varliga():
    font = TTFont("../variations/var.ttf")
    addOpenTypeFeaturesFromString(font, """
languagesystem DFLT dflt;
languagesystem latn dflt;
feature liga { sub I by H; } liga;
""")
    # fontTools adds the new lookup to liga's existing ones; keep only the
    # new one, so the record replaces liga's lookups instead of adding to them.
    addFeatureVariations(font, [([{"wght": (0.6, 1.0)}], {"I": "V"})],
                         featureTag="liga")
    gsub = font["GSUB"].table
    for rec in gsub.FeatureVariations.FeatureVariationRecord:
        for sub in rec.FeatureTableSubstitution.SubstitutionRecord:
            sub.Feature.LookupListIndex = sub.Feature.LookupListIndex[-1:]
            sub.Feature.LookupCount = 1
    font.save("varliga.ttf")

    font = TTFont("varliga.ttf")
    font["GSUB"].table.FeatureVariations.Version = 0x00010001
    font.save("varliga-minor1.ttf")


build_bits()
build_stages()
build_arabic()
build_varliga()
