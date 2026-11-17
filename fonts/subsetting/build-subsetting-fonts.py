"""Build the source fonts for the chapter “Subsetting”.

usage: python3 build-subsetting-fonts.py OUT_DIR

Every glyph is a box, or a few boxes: only the glyph names, the cmap and the
tables that refer to glyphs matter here. build.sh then cuts subsets from
these fonts with hb-subset.

Fonts written:
  demo.ttf     a font with something for every stage of the closure:
                 liga    f i -> f_i, f l -> f_l
                 dlig    c t -> c_t (not a feature hb-subset keeps by default)
                 kern    A V, in GPOS
                 mark    acutecomb on e, in GPOS
                 eacute  (U+00E9) a composite of e and acutecomb
                 star    (U+2605) a COLRv0 glyph: star.back, and star.ring,
                         which is a composite of two dots
                 parenleft, parenright  a bidi-mirrored pair
               It has no Aacute: Á can only be shaped by decomposing it.
               It has fpgm and prep tables (one instruction each), which
               hb-subset passes through, and drops with --no-hinting.
  nested.ttf   a contextual lookup that applies twenty single substitutions,
               one after the other, at the same glyph: a -> s1 -> ... -> s20.
  kern.ttf     kerning in one GPOS PairPos format 1 subtable: A against
               C G O Q T V W Y, each pair with its own value.
  symbol.ttf   a symbol font: its only cmap subtable is (3, 0), which maps
               U+F061 to a glyph, as old symbol fonts do.
  math.ttf     a MATH table and an rtlm feature: the integral (U+222B) and
               its right-to-left mirror, integral.rtlm, each with a larger
               display-size variant and an italics correction.
"""
import io
import os
import sys

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._c_m_a_p import cmap_format_4
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables.otData import otData


def boxes(*rects):
    pen = TTGlyphPen(None)
    for x0, y0, x1, y1 in rects:
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def composite(glyphs, *components):
    """components: (glyph name, dx, dy)."""
    pen = TTGlyphPen(glyphs)
    for name, dx, dy in components:
        pen.addComponent(name, (1, 0, 0, 1, dx, dy))
    return pen.glyph()


def make(order, cmap, glyphs, advances, family):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    gl = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (advances[g], getattr(gl[g], "xMin", 0)) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    return fb


DEMO_FEA = """
languagesystem DFLT dflt;
languagesystem latn dflt;

table GDEF {
  GlyphClassDef [A V c e f i l t eacute parenleft parenright star], [f_i f_l c_t], [acutecomb], ;
} GDEF;

feature liga {
  sub f i by f_i;
  sub f l by f_l;
} liga;

feature dlig {
  sub c t by c_t;
} dlig;

feature kern {
  pos A V -150;
} kern;

markClass acutecomb <anchor 0 600> @TOP;
feature mark {
  pos base e <anchor 250 500> mark @TOP;
} mark;
"""


def build_demo(out):
    order = [".notdef", "space", "A", "V", "c", "e", "f", "i", "l", "t",
             "acutecomb", "eacute", "f_i", "f_l", "c_t",
             "parenleft", "parenright", "star", "star.back", "star.ring", "dot"]
    cmap = {0x20: "space", 0x41: "A", 0x56: "V", 0x63: "c", 0x65: "e", 0x66: "f",
            0x69: "i", 0x6C: "l", 0x74: "t", 0x301: "acutecomb", 0xE9: "eacute",
            0x28: "parenleft", 0x29: "parenright", 0x2605: "star"}
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    glyphs["space"] = boxes()
    for g in ("f_i", "f_l", "c_t"):
        glyphs[g] = boxes((50, 0, 850, 500))
    glyphs["acutecomb"] = boxes((-100, 0, 100, 150))
    glyphs["eacute"] = composite(glyphs, ("e", 0, 0), ("acutecomb", 250, 600))
    glyphs["parenleft"] = boxes((150, -100, 250, 700), (250, -100, 400, 0), (250, 600, 400, 700))
    glyphs["parenright"] = boxes((250, -100, 350, 700), (100, -100, 250, 0), (100, 600, 250, 700))
    glyphs["star"] = boxes((100, 0, 900, 800))
    glyphs["star.back"] = boxes((100, 0, 900, 800))
    glyphs["dot"] = boxes((0, 0, 200, 200))
    glyphs["star.ring"] = composite(glyphs, ("dot", 200, 300), ("dot", 600, 300))
    advances = {g: 500 for g in order}
    advances.update({"space": 250, "acutecomb": 0, "f_i": 900, "f_l": 900, "c_t": 900,
                     "star": 1000, "star.back": 1000, "star.ring": 1000, "dot": 200})
    fb = make(order, cmap, glyphs, advances, "HBBook Subset Demo")
    addOpenTypeFeaturesFromString(fb.font, DEMO_FEA)
    fb.font["CPAL"] = buildCPAL([[(0.9, 0.2, 0.1, 1.0), (1.0, 0.85, 0.1, 1.0)]])
    fb.font["COLR"] = buildCOLR({"star": [("star.back", 0), ("star.ring", 1)]}, version=0)
    for tag in ("fpgm", "prep"):
        t = newTable(tag)
        t.program = ttProgram.Program()
        t.program.fromAssembly(["PUSHB[ ]", "0", "POP[ ]"])
        fb.font[tag] = t
    fb.save(out)


def build_nested(out):
    n = 20
    chain = [f"s{k}" for k in range(1, n + 1)]
    order = [".notdef", "a"] + chain
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    fb = make(order, {0x61: "a"}, glyphs, {g: 500 for g in order}, "HBBook Subset Nested")
    src = ["a"] + chain
    # Lookup Lk turns the k-th glyph of the chain into the next one. They are
    # defined, and so numbered, last link first.
    lookups = "\n".join(f"lookup L{k} {{ sub {src[k]} by {src[k + 1]}; }} L{k};"
                        for k in reversed(range(n)))
    records = " ".join(f"lookup L{k}" for k in range(n))
    fea = f"languagesystem DFLT dflt;\n{lookups}\nfeature ccmp {{\n  sub a' {records};\n}} ccmp;\n"
    addOpenTypeFeaturesFromString(fb.font, fea)
    with open(os.path.join(os.path.dirname(out), "nested.fea"), "w") as f:
        f.write(fea)
    fb.save(out)


KERN_RIGHT = "C G O Q T V W Y".split()


def build_kern(out):
    order = [".notdef", "A"] + KERN_RIGHT
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    fb = make(order, {ord(g): g for g in order[1:]}, glyphs, {g: 500 for g in order},
              "HBBook Subset Kern")
    rules = "\n".join(f"  pos A {g} -{10 * k};" for k, g in enumerate(KERN_RIGHT, 1))
    addOpenTypeFeaturesFromString(fb.font, f"languagesystem DFLT dflt;\nfeature kern {{\n{rules}\n}} kern;\n")
    fb.save(out)


def build_symbol(out):
    order = [".notdef", "a"]
    glyphs = {g: boxes((50, 0, 450, 500)) for g in order}
    fb = make(order, {0xF061: "a"}, glyphs, {g: 500 for g in order}, "HBBook Subset Symbol")
    sub = fb.font["cmap"].tables[0]
    symbol = cmap_format_4(4)
    symbol.platformID, symbol.platEncID, symbol.language = 3, 0, 0
    symbol.cmap = dict(sub.cmap)
    fb.font["cmap"].tables = [symbol]
    fb.save(out)


def math_constants():
    """A MathConstants table with every field zero, but the two scale-downs."""
    fields = dict(otData)["MathConstants"]
    mc = ot.MathConstants()
    for kind, name, *_ in fields:
        if kind == "MathValueRecord":
            v = ot.MathValueRecord(); v.Value = 0; v.DeviceTable = None
            setattr(mc, name, v)
        else:
            setattr(mc, name, 0)
    mc.ScriptPercentScaleDown = 70
    mc.ScriptScriptPercentScaleDown = 50
    return mc


def coverage(names):
    c = ot.Coverage(); c.glyphs = list(names); return c


def construction(variants):
    c = ot.MathGlyphConstruction()
    c.GlyphAssembly = None
    c.MathGlyphVariantRecord = []
    for name, size in variants:
        r = ot.MathGlyphVariantRecord(); r.VariantGlyph = name; r.AdvanceMeasurement = size
        c.MathGlyphVariantRecord.append(r)
    c.VariantCount = len(variants)
    return c


def build_math(out):
    order = [".notdef", "integral", "integral.size1", "integral.rtlm", "integral.rtlm.size1"]
    glyphs = {
        ".notdef": boxes((50, 0, 450, 500)),
        "integral": boxes((200, -200, 300, 800)),
        "integral.size1": boxes((200, -600, 300, 1200)),
        "integral.rtlm": boxes((200, -200, 300, 800), (300, 700, 400, 800)),
        "integral.rtlm.size1": boxes((200, -600, 300, 1200), (300, 1100, 400, 1200)),
    }
    fb = make(order, {0x222B: "integral"}, glyphs, {g: 500 for g in order}, "HBBook Subset Math")
    addOpenTypeFeaturesFromString(fb.font, """
languagesystem DFLT dflt;
languagesystem math dflt;
feature rtlm {
  sub integral by integral.rtlm;
  sub integral.size1 by integral.rtlm.size1;
} rtlm;
""")
    m = ot.MATH()
    m.Version = 0x00010000
    m.MathConstants = math_constants()
    info = ot.MathGlyphInfo()
    ic = ot.MathItalicsCorrectionInfo()
    ic.Coverage = coverage(order[1:])
    ic.ItalicsCorrection = []
    for _ in order[1:]:
        v = ot.MathValueRecord(); v.Value = 80; v.DeviceTable = None
        ic.ItalicsCorrection.append(v)
    ic.ItalicsCorrectionCount = len(ic.ItalicsCorrection)
    info.MathItalicsCorrectionInfo = ic
    info.MathTopAccentAttachment = None
    info.ExtendedShapeCoverage = None
    info.MathKernInfo = None
    m.MathGlyphInfo = info
    var = ot.MathVariants()
    var.MinConnectorOverlap = 0
    var.VertGlyphCoverage = coverage(["integral", "integral.rtlm"])
    var.VertGlyphConstruction = [
        construction([("integral", 1000), ("integral.size1", 1800)]),
        construction([("integral.rtlm", 1000), ("integral.rtlm.size1", 1800)]),
    ]
    var.VertGlyphCount = 2
    var.HorizGlyphCoverage = None
    var.HorizGlyphConstruction = []
    var.HorizGlyphCount = 0
    m.MathVariants = var
    t = newTable("MATH"); t.table = m
    fb.font["MATH"] = t
    fb.save(out)


if __name__ == "__main__":
    d = sys.argv[1]
    build_demo(os.path.join(d, "demo.ttf"))
    build_nested(os.path.join(d, "nested.ttf"))
    build_math(os.path.join(d, "math.ttf"))
    build_kern(os.path.join(d, "kern.ttf"))
    build_symbol(os.path.join(d, "symbol.ttf"))
