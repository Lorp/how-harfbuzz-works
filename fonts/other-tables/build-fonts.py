"""Build the test fonts for the chapter “Other tables”.

usage: python3 build-fonts.py OUT_DIR

Every glyph is a box, or a few boxes. What matters is the tables the
chapter reads: MATH, BASE, STAT and the style fallbacks, name, ltag and meta.

Fonts written:
  math.ttf         a MATH table: constants, an italics correction and a math
                   kern on f, a top accent position on a (and none on x), and
                   a left parenthesis with two larger variants and an
                   assembly of three parts.
  base.ttf         a BASE table with a horizontal axis only: baselines hang,
                   ideo and romn for DFLT, dev2 and hani; latn has min/max
                   extents (and a VIT language system with its own) but no
                   baselines.
  nobase.ttf       the same glyphs, with no BASE table: everything a
                   baseline query returns is synthesized.
  names.ttf        name records for Windows English (US and UK), German and
                   Japanese, Macintosh English (one in Mac Roman with an é),
                   and the Unicode platform with an ltag table; a meta table
                   with dlng and slng.
  names-noltag.ttf names.ttf without its ltag table.
  style.ttf        no STAT and no fvar: OS/2 version 5 with weight 700, width
                   class 3, the italic bit and an optical size range of
                   8 to 24 points; post's italic angle −12.
  style-stat.ttf   style.ttf with a STAT table: weight values 300, 400 and
                   700, in that order, and a slant value of 0.
  style-size.ttf   style.ttf with OS/2 version 4, which has no optical size
                   range, and a GPOS size feature: design size 10 points.
"""
import os
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.otData import otData
from fontTools.ttLib.tables._n_a_m_e import NameRecord


def boxes(*rects):
    pen = TTGlyphPen(None)
    for x0, y0, x1, y1 in rects:
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def make(order, cmap, glyphs, advances, family, os2=None):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    gl = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (advances[g], getattr(gl[g], "xMin", 0)) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"}, mac=False)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200,
                sxHeight=500, sCapHeight=700, **(os2 or {}))
    fb.setupPost()
    return fb


def coverage(glyphs):
    c = ot.Coverage()
    c.glyphs = list(glyphs)
    return c


def value(v):
    r = ot.MathValueRecord()
    r.Value = v
    r.DeviceTable = None
    return r


# ---------------------------------------------------------------- MATH

MATH_CONSTANTS = {
    "ScriptPercentScaleDown": 70,
    "ScriptScriptPercentScaleDown": 50,
    "DelimitedSubFormulaMinHeight": 1300,
    "DisplayOperatorMinHeight": 1500,
    "AxisHeight": 250,
    "AccentBaseHeight": 500,
    "FractionRuleThickness": 50,
    "SuperscriptShiftUp": 350,
    "SubscriptShiftDown": 200,
    "RadicalDegreeBottomRaisePercent": 60,
}


def math_constants():
    fields = dict(otData)["MathConstants"]
    mc = ot.MathConstants()
    for kind, name, *_ in fields:
        v = MATH_CONSTANTS.get(name, 0)
        setattr(mc, name, value(v) if kind == "MathValueRecord" else v)
    return mc


def math_kern(heights, kerns):
    k = ot.MathKern()
    k.CorrectionHeight = [value(h) for h in heights]
    k.KernValue = [value(v) for v in kerns]
    k.HeightCount = len(heights)
    return k


def part(glyph, start, end, full, extender):
    p = ot.GlyphPartRecord()
    p.glyph = glyph
    p.StartConnectorLength = start
    p.EndConnectorLength = end
    p.FullAdvance = full
    p.PartFlags = 1 if extender else 0
    return p


def build_math(out):
    order = [".notdef", "space", "f", "a", "x", "parenleft", "parenleft.size1",
             "parenleft.size2", "parenleft.top", "parenleft.ext", "parenleft.bot", "minus"]
    cmap = {0x20: "space", 0x66: "f", 0x61: "a", 0x78: "x", 0x28: "parenleft", 0x2212: "minus"}
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    glyphs["space"] = boxes()
    glyphs["f"] = boxes((50, 0, 150, 700), (150, 600, 450, 700))
    glyphs["parenleft"] = boxes((150, -150, 250, 750))
    glyphs["parenleft.size1"] = boxes((150, -350, 250, 950))
    glyphs["parenleft.size2"] = boxes((150, -550, 250, 1150))
    glyphs["parenleft.top"] = boxes((150, 0, 250, 600), (250, 500, 400, 600))
    glyphs["parenleft.ext"] = boxes((150, 0, 250, 600))
    glyphs["parenleft.bot"] = boxes((150, 0, 250, 600), (250, 0, 400, 100))
    glyphs["minus"] = boxes((50, 220, 450, 280))
    advances = {g: 500 for g in order}
    advances["space"] = 250
    fb = make(order, cmap, glyphs, advances, "HBBook Math")

    m = ot.MATH()
    m.Version = 0x00010000
    m.MathConstants = math_constants()

    info = ot.MathGlyphInfo()
    ic = ot.MathItalicsCorrectionInfo()
    ic.Coverage = coverage(["f"])
    ic.ItalicsCorrection = [value(120)]
    ic.ItalicsCorrectionCount = 1
    info.MathItalicsCorrectionInfo = ic

    ta = ot.MathTopAccentAttachment()
    ta.TopAccentCoverage = coverage(["a"])
    ta.TopAccentAttachment = [value(300)]
    ta.TopAccentAttachmentCount = 1
    info.MathTopAccentAttachment = ta

    info.ExtendedShapeCoverage = coverage(["parenleft.size1", "parenleft.size2"])

    ki = ot.MathKernInfo()
    ki.MathKernCoverage = coverage(["f"])
    rec = ot.MathKernInfoRecord()
    rec.TopRightMathKern = math_kern([300, 600], [-50, 0, 40])
    rec.TopLeftMathKern = None
    rec.BottomRightMathKern = None
    rec.BottomLeftMathKern = None
    ki.MathKernInfoRecords = [rec]
    ki.MathKernCount = 1
    info.MathKernInfo = ki
    m.MathGlyphInfo = info

    var = ot.MathVariants()
    var.MinConnectorOverlap = 20
    var.VertGlyphCoverage = coverage(["parenleft"])
    c = ot.MathGlyphConstruction()
    c.MathGlyphVariantRecord = []
    for name, size in (("parenleft", 900), ("parenleft.size1", 1300), ("parenleft.size2", 1700)):
        r = ot.MathGlyphVariantRecord()
        r.VariantGlyph = name
        r.AdvanceMeasurement = size
        c.MathGlyphVariantRecord.append(r)
    c.VariantCount = len(c.MathGlyphVariantRecord)
    asm = ot.GlyphAssembly()
    asm.ItalicsCorrection = value(0)
    asm.PartRecords = [part("parenleft.bot", 0, 200, 600, False),
                       part("parenleft.ext", 200, 200, 600, True),
                       part("parenleft.top", 200, 0, 600, False)]
    asm.PartCount = 3
    c.GlyphAssembly = asm
    var.VertGlyphConstruction = [c]
    var.VertGlyphCount = 1
    var.HorizGlyphCoverage = None
    var.HorizGlyphConstruction = []
    var.HorizGlyphCount = 0
    m.MathVariants = var

    t = newTable("MATH")
    t.table = m
    fb.font["MATH"] = t
    fb.save(out)


# ---------------------------------------------------------------- BASE

def base_coord(v):
    c = ot.BaseCoord()
    c.Format = 1
    c.Coordinate = v
    return c


def min_max(lo, hi):
    mm = ot.MinMax()
    mm.MinCoord = base_coord(lo)
    mm.MaxCoord = base_coord(hi)
    mm.FeatMinMaxRecord = []
    mm.FeatMinMaxCount = 0
    return mm


BASE_TAGS = ["hang", "ideo", "romn"]


def base_script(values=None, default=None, minmax=None, langsys=()):
    s = ot.BaseScript()
    if values:
        bv = ot.BaseValues()
        bv.DefaultIndex = BASE_TAGS.index(default)
        bv.BaseCoord = [base_coord(values[t]) for t in BASE_TAGS]
        bv.BaseCoordCount = len(bv.BaseCoord)
        s.BaseValues = bv
    else:
        s.BaseValues = None
    s.DefaultMinMax = min_max(*minmax) if minmax else None
    s.BaseLangSysRecord = []
    for tag, lo, hi in langsys:
        r = ot.BaseLangSysRecord()
        r.BaseLangSysTag = tag
        r.MinMax = min_max(lo, hi)
        s.BaseLangSysRecord.append(r)
    s.BaseLangSysCount = len(s.BaseLangSysRecord)
    return s


def base_glyphs():
    order = [".notdef", "space", "H", "x", "ka", "minus", "uni4E00"]
    cmap = {0x20: "space", 0x48: "H", 0x78: "x", 0x915: "ka", 0x2212: "minus", 0x4E00: "uni4E00"}
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    glyphs["space"] = boxes()
    glyphs["H"] = boxes((50, 0, 150, 700), (350, 0, 450, 700), (150, 300, 350, 400))
    glyphs["ka"] = boxes((0, 560, 500, 640), (200, 0, 300, 560))
    glyphs["minus"] = boxes((50, 230, 450, 290))
    glyphs["uni4E00"] = boxes((80, 330, 920, 410))
    advances = {g: 500 for g in order}
    advances["space"] = 250
    advances["uni4E00"] = 1000
    return order, cmap, glyphs, advances


def build_base(out, with_base=True):
    order, cmap, glyphs, advances = base_glyphs()
    fb = make(order, cmap, glyphs, advances, "HBBook Base" if with_base else "HBBook No Base")
    if with_base:
        scripts = [
            ("DFLT", base_script({"hang": 600, "ideo": -120, "romn": 0}, "romn")),
            ("dev2", base_script({"hang": 640, "ideo": -120, "romn": 0}, "hang")),
            ("hani", base_script({"hang": 760, "ideo": -120, "romn": 0}, "ideo")),
            ("latn", base_script(minmax=(-250, 900), langsys=[("VIT ", -300, 1100)])),
        ]
        sl = ot.BaseScriptList()
        sl.BaseScriptRecord = []
        for tag, script in scripts:
            r = ot.BaseScriptRecord()
            r.BaseScriptTag = tag
            r.BaseScript = script
            sl.BaseScriptRecord.append(r)
        sl.BaseScriptCount = len(sl.BaseScriptRecord)
        tl = ot.BaseTagList()
        tl.BaselineTag = BASE_TAGS
        tl.BaseTagCount = len(BASE_TAGS)
        axis = ot.Axis()
        axis.BaseTagList = tl
        axis.BaseScriptList = sl
        b = ot.BASE()
        b.Version = 0x00010000
        b.HorizAxis = axis
        b.VertAxis = None
        t = newTable("BASE")
        t.table = b
        fb.font["BASE"] = t
    fb.save(out)


# ---------------------------------------------------------------- name, ltag, meta

def name_record(name_id, platform, encoding, language, text):
    r = NameRecord()
    r.nameID, r.platformID, r.platEncID, r.langID = name_id, platform, encoding, language
    r.string = text
    return r


def build_names(out, with_ltag=True):
    order = [".notdef", "space", "A"]
    glyphs = {g: boxes((50, 0, 450, 700)) for g in order}
    glyphs["space"] = boxes()
    fb = make(order, {0x20: "space", 0x41: "A"}, glyphs, {g: 500 for g in order}, "HBBook Names")
    names = fb.font["name"]
    names.names += [
        name_record(1, 3, 1, 0x0809, "HBBook Names (UK)"),
        name_record(1, 3, 1, 0x0407, "HBBook Namen"),
        name_record(1, 3, 1, 0x0411, "HBBook 名前"),
        name_record(1, 1, 0, 0, "HBBook Names (Mac)"),
        name_record(256, 1, 0, 0, "Café"),
        name_record(257, 0, 4, 0, "Name"),
        name_record(257, 0, 4, 1, "Ainm"),
    ]
    if with_ltag:
        ltag = newTable("ltag")
        ltag.version, ltag.flags = 1, 0
        ltag.tags = ["en", "ga"]
        fb.font["ltag"] = ltag
    meta = newTable("meta")
    meta.data = {"dlng": "Latn", "slng": "Latn, Grek, Cyrl"}
    fb.font["meta"] = meta
    fb.save(out)


# ---------------------------------------------------------------- style

def build_style(out, stat=False, size=False):
    order = [".notdef", "space", "A"]
    glyphs = {g: boxes((50, 0, 450, 700)) for g in order}
    glyphs["space"] = boxes()
    os2 = dict(usWeightClass=700, usWidthClass=3, fsSelection=0x01)
    if size:
        os2["version"] = 4
    else:
        os2.update(version=5, usLowerOpticalPointSize=8, usUpperOpticalPointSize=24)
    fb = make(order, {0x20: "space", 0x41: "A"}, glyphs, {g: 500 for g in order},
              "HBBook Style", os2)
    fb.font["post"].italicAngle = -12.0
    fb.font["head"].macStyle = 0x02
    if stat:
        axes = [
            dict(tag="wght", name="Weight", values=[
                dict(value=300, name="Light"),
                dict(value=400, name="Regular", flags=0x2),
                dict(value=700, name="Bold"),
            ]),
            dict(tag="slnt", name="Slant", values=[dict(value=0, name="Upright", flags=0x2)]),
        ]
        buildStatTable(fb.font, axes)
    if size:
        addOpenTypeFeaturesFromString(fb.font, """
languagesystem DFLT dflt;
feature size {
  parameters 100 0;
} size;
""")
    fb.save(out)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    build_math(os.path.join(out, "math.ttf"))
    build_base(os.path.join(out, "base.ttf"))
    build_base(os.path.join(out, "nobase.ttf"), with_base=False)
    build_names(os.path.join(out, "names.ttf"))
    build_names(os.path.join(out, "names-noltag.ttf"), with_ltag=False)
    build_style(os.path.join(out, "style.ttf"))
    build_style(os.path.join(out, "style-stat.ttf"), stat=True)
    build_style(os.path.join(out, "style-size.ttf"), size=True)
