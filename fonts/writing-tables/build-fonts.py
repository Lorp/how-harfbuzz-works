"""Build the source fonts for the chapter "Writing tables".

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Each font has 1,500 encoded glyphs, g1 to g1500 (U+4E01 to U+51DC), and
a GSUB table of many lookups, one feature each (ss01 to ss20, then cv01
onwards). Lookup n maps every glyph gi to g(i+n+1): one constant
difference in glyph ID, so fontTools writes each as a SingleSubst format 1
subtable, six bytes and a one-range Coverage table. The whole GSUB is a few
kilobytes.

  forty.ttf   40 such lookups
  sixty.ttf   60 such lookups

fontTools is told not to use HarfBuzz's repacker (through uharfbuzz) when
it compiles them, so the files don't depend on whether uharfbuzz is
installed. These tables are small enough not to need repacking anyway.

build.sh then subsets each with hb-subset, dropping some glyphs, which is
what makes the subset's GSUB grow (see the chapter).
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib import builder as otl
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot

N = 1500


def feature_tag(n):
    return f"ss{n + 1:02d}" if n < 20 else f"cv{n - 19:02d}"


def build(num_lookups, out):
    order = [".notdef"] + [f"g{i}" for i in range(1, N + 1)]
    fb = FontBuilder(1000, isTTF=True)
    fb.font.cfg["fontTools.ttLib.tables.otBase:USE_HARFBUZZ_REPACKER"] = False
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x4E00 + i: f"g{i}" for i in range(1, N + 1)})
    fb.setupGlyf({g: TTGlyphPen(None).glyph() for g in order})
    fb.setupHorizontalMetrics({g: (1000, 0) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Writing Tables", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()

    lookups = [otl.buildLookup([otl.buildSingleSubstSubtable(
                   {f"g{i}": f"g{i + n + 1}" for i in range(1, N - n)})])
               for n in range(num_lookups)]

    gsub = ot.GSUB()
    gsub.Version = 0x00010000
    gsub.LookupList = ot.LookupList()
    gsub.LookupList.Lookup = lookups
    gsub.FeatureList = ot.FeatureList()
    gsub.FeatureList.FeatureRecord = []
    for n in range(num_lookups):
        rec = ot.FeatureRecord()
        rec.FeatureTag = feature_tag(n)
        rec.Feature = ot.Feature()
        rec.Feature.FeatureParams = None
        rec.Feature.LookupListIndex = [n]
        gsub.FeatureList.FeatureRecord.append(rec)
    langsys = ot.LangSys()
    langsys.LookupOrderOffset = None
    langsys.ReqFeatureIndex = 0xFFFF
    langsys.FeatureIndex = list(range(num_lookups))
    script = ot.ScriptRecord()
    script.ScriptTag = "DFLT"
    script.Script = ot.Script()
    script.Script.DefaultLangSys = langsys
    script.Script.LangSysRecord = []
    gsub.ScriptList = ot.ScriptList()
    gsub.ScriptList.ScriptRecord = [script]
    table = newTable("GSUB")
    table.table = gsub
    fb.font["GSUB"] = table
    fb.save(out)


build(40, "forty.ttf")
build(60, "sixty.ttf")

# The characters the subsets keep: every one except those whose glyph's
# number is a multiple of 5 or of 7.
with open("unicodes.txt", "w") as f:
    for i in range(1, N + 1):
        if i % 5 and i % 7:
            f.write(f"U+{0x4E00 + i:04X}\n")
