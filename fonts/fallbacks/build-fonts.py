"""Build the test fonts for “Fallbacks”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Fonts written:
  fallback.ttf    a GSUB with the f_i and f_f_i ligatures (fallback.fea),
                  and no GDEF, GPOS or kern: everything is placed by
                  HarfBuzz's fallbacks. It has no glyphs for the space
                  characters other than U+0020.
  with-gpos.ttf   fallback.ttf with a GPOS holding one kerning pair, o o
                  (kern.fea), and no mark feature
  kern-table.ttf  fallback.ttf with a kern table (format 0) holding the
                  same pair
  cross-kern.ttf  kern-table.ttf with its subtable marked cross-stream
  no-space.ttf    fallback.ttf without a glyph for U+0020
  with-morx.ttf   fallback.ttf with a morx table, whose one subtable
                  changes period into zero, so that HarfBuzz shapes it
                  with morx instead of GSUB

Unlike the other chapters' test fonts, the marks here have outlines, at
heights a designer might draw them, because the fallback positioner works
from glyph extents. The bases are boxes of different heights.
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]


# glyph name: (Unicode code point or None, advance width, contours)
GLYPHS = {
    ".notdef": (None, 500, [rect(50, 0, 450, 700)]),
    "space": (0x20, 250, []),
    "zero": (0x30, 560, [rect(50, 0, 510, 700)]),
    "period": (0x2E, 200, [rect(50, 0, 150, 100)]),
    "o": (0x6F, 500, [rect(50, 0, 450, 500)]),
    "l": (0x6C, 250, [rect(50, 0, 200, 750)]),
    "f": (0x66, 400, [rect(50, 0, 350, 750)]),
    "i": (0x69, 250, [rect(50, 0, 200, 500)]),
    "f_i": (None, 650, [rect(50, 0, 600, 750)]),
    "f_f_i": (None, 1050, [rect(50, 0, 1000, 750)]),
    # Latin marks, zero-width and drawn to the left of the origin
    "gravecomb": (0x300, 0, [[(-350, 950), (-250, 950), (-150, 800), (-200, 800)]]),
    "acutecomb": (0x301, 0, [[(-300, 550), (-250, 550), (-150, 700), (-250, 700)]]),
    "commaaboverightcomb": (0x315, 0, [rect(-100, 550, -50, 650)]),
    "horncomb": (0x31B, 0, [rect(-100, 400, 0, 450)]),
    "dotbelowcomb": (0x323, 0, [rect(-300, -200, -200, -100)]),
    "cedillacomb": (0x327, 0, [[(-300, 0), (-200, 0), (-200, -150), (-300, -150)]]),
    "longsolidusoverlay": (0x338, 0, [[(-450, -50), (-400, -50), (-50, 550), (-100, 550)]]),
    "brevebelowdbl": (0x35C, 0, [rect(-500, -200, 0, -150)]),
    "brevedbl": (0x361, 0, [rect(-500, 600, 0, 650)]),
    # Hebrew
    "bet": (0x5D1, 600, [rect(50, 0, 550, 600)]),
    "shin": (0x5E9, 700, [rect(50, 0, 650, 600)]),
    "hiriq": (0x5B4, 0, [rect(-350, -200, -250, -100)]),
    "patah": (0x5B7, 0, [rect(-500, -150, -100, -100)]),
    "dagesh": (0x5BC, 0, [rect(-350, 250, -250, 350)]),
    "meteg": (0x5BD, 0, [rect(-325, -250, -275, -100)]),
    "shindot": (0x5C1, 0, [rect(-150, 650, -50, 750)]),
    "sindot": (0x5C2, 0, [rect(-650, 650, -550, 750)]),
    # Arabic
    "beh": (0x628, 600, [rect(50, 0, 550, 300)]),
    "fatha": (0x64E, 0, [[(-400, 400), (-200, 450), (-200, 500), (-400, 450)]]),
    "kasra": (0x650, 0, [[(-400, -200), (-200, -150), (-200, -100), (-400, -150)]]),
    "shadda": (0x651, 0, [rect(-400, 400, -200, 500)]),
    # Thai: a mark with an advance of its own
    "kokai": (0xE01, 550, [rect(50, 0, 500, 500)]),
    "maiek": (0xE48, 200, [rect(50, 600, 150, 750)]),
    # Musical augmentation dot, Mc with combining class 226 (Right)
    "augdot": (0x1D16D, 200, [rect(50, 200, 150, 300)]),
}


def glyph(contours):
    pen = TTGlyphPen(None)
    for c in contours:
        pen.moveTo(c[0])
        for p in c[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen.glyph()


def build_fallback():
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(GLYPHS))
    fb.setupCharacterMap({cp: g for g, (cp, _, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: glyph(c) for g, (_, _, c) in GLYPHS.items()})
    glyf = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (w, getattr(glyf[g], "xMin", 0)) for g, (_, w, _) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Fallback Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, "fallback.fea")
    assert "GDEF" not in fb.font and "GPOS" not in fb.font
    fb.save("fallback.ttf")


def build_with_gpos():
    font = TTFont("fallback.ttf")
    addOpenTypeFeatures(font, "kern.fea", tables=["GPOS"])
    assert "GDEF" not in font
    font.save("with-gpos.ttf")


def build_kern_table(out, coverage):
    font = TTFont("fallback.ttf")
    kern = font["kern"] = newTable("kern")
    kern.version = 0
    st = KernTable_format_0()
    st.version, st.format, st.coverage = 0, 0, coverage
    st.tupleIndex = None
    st.kernTable = {("o", "o"): -100}
    kern.kernTables = [st]
    font.save(out)


MORX = """<?xml version="1.0" encoding="UTF-8"?>
<ttFont sfntVersion="\\x00\\x01\\x00\\x00" ttLibVersion="4.38">
  <morx>
    <Version value="2"/>
    <Reserved value="0"/>
    <MorphChain index="0">
      <DefaultFlags value="0x00000001"/>
      <MorphFeature index="0">
        <FeatureType value="0"/>
        <FeatureSetting value="1"/>
        <EnableFlags value="0x00000000"/>
        <DisableFlags value="0x00000000"/>
      </MorphFeature>
      <MorphSubtable index="0">
        <TextDirection value="Any"/>
        <ProcessingOrder value="LayoutOrder"/>
        <SubFeatureFlags value="0x00000001"/>
        <NoncontextualMorph>
          <Substitution>
            <Lookup glyph="period" value="zero"/>
          </Substitution>
        </NoncontextualMorph>
      </MorphSubtable>
    </MorphChain>
  </morx>
</ttFont>
"""


def build_with_morx():
    import io
    font = TTFont("fallback.ttf")
    font.importXML(io.StringIO(MORX))
    font.save("with-morx.ttf")


def build_no_space():
    font = TTFont("fallback.ttf")
    for t in font["cmap"].tables:
        t.cmap.pop(0x20, None)
    font.save("no-space.ttf")


if __name__ == "__main__":
    build_fallback()
    build_with_gpos()
    build_kern_table("kern-table.ttf", 0x01)   # horizontal
    build_kern_table("cross-kern.ttf", 0x05)   # horizontal, cross-stream
    build_no_space()
    build_with_morx()
