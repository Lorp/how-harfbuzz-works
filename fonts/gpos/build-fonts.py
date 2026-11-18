"""Build the test fonts for “Positioning glyphs: GPOS”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Fonts written:
  gpos.ttf          from gpos.fea: the GSUB chapter's f, i and ligatures
                    with an acute and a grave, kerning, single adjustments,
                    mark, mark-to-ligature and mark-to-mark attachment, and
                    cursive chains with and without the RightToLeft flag
  class-first.ttf   gpos.ttf with the two subtables of its kerning lookup
                    swapped, so the class-pair subtable comes first, which
                    feaLib never writes
  second-value.ttf  gpos.ttf with the glyph-pair subtable of its kerning
                    lookup given a value record for the second glyph too
                    (valueFormat2 = XAdvance, every value zero)
  var-kern.ttf      variations/var.ttf, the shared variable font, with a
                    GDEF and a GPOS added: one kerning pair, H V, whose
                    value varies with wght through a VariationIndex table
  context.ttf       the same glyphs, from context.fea: a kerning pair, T o,
                    and a contextual rule that changes it before n

Every glyph is a box, as in tools/build-test-font.py.
"""
import copy

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures, addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

# glyph name: (Unicode code point or None, advance width)
GLYPHS = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "A": (0x41, 600), "T": (0x54, 600), "V": (0x56, 600),
    "a": (0x61, 500), "e": (0x65, 500), "f": (0x66, 500), "i": (0x69, 500),
    "n": (0x6E, 500), "o": (0x6F, 500),
    "beh": (0x628, 500),
    "acutecomb": (0x301, 0), "gravecomb": (0x300, 0),
    "f_i": (None, 900), "f_f_i": (None, 900),
}


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def build_gpos(fea="gpos.fea", out="gpos.ttf"):
    order = list(GLYPHS)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, (cp, _) in GLYPHS.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in GLYPHS.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook GPOS Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)


def kern_lookup(font):
    lookups = font["GPOS"].table.LookupList.Lookup
    (kern,) = [l for l in lookups if l.LookupType == 2]
    assert [st.Format for st in kern.SubTable] == [1, 2]
    return kern


def build_class_first():
    font = TTFont("gpos.ttf")
    kern = kern_lookup(font)
    kern.SubTable.reverse()
    font.save("class-first.ttf")


def build_second_value():
    font = TTFont("gpos.ttf")
    pairs = kern_lookup(font).SubTable[0]
    pairs.ValueFormat2 = 0x0004  # XAdvance
    for ps in pairs.PairSet:
        for rec in ps.PairValueRecord:
            rec.Value2 = otTables.ValueRecord()
            rec.Value2.XAdvance = 0
    font.save("second-value.ttf")


VAR_FEA = """
languagesystem DFLT dflt;
languagesystem latn dflt;
table GDEF { GlyphClassDef [H I V], , , ; } GDEF;
feature kern {
  pos H V (wght=100:-20 wght=400:-60 wght=900:-150);
} kern;
"""


def build_var_kern():
    font = TTFont("../variations/var.ttf")
    addOpenTypeFeaturesFromString(font, VAR_FEA)
    font.save("var-kern.ttf")


if __name__ == "__main__":
    build_gpos()
    build_gpos("context.fea", "context.ttf")
    build_class_first()
    build_second_value()
    build_var_kern()
