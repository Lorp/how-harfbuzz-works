"""Build the small variable test fonts used by the chapters on variations.

usage: python3 tools/build-var-test-fonts.py OUT_DIR

The fonts are made the way font tools make real ones: a static master for
each position in the design space, built with fontTools' FontBuilder, then
combined by fontTools.varLib from a designspace. That gives fvar, gvar,
HVAR and MVAR (and avar, for the fonts that ask for it) exactly as a
production font would have them.

Axes: wght 100–900 (default 400) and wdth 75–100 (default 100).

Named instances: Light (wght 100), Regular, Bold (wght 700), Narrow (wdth 75).

Glyphs, all plain shapes, since only their points and metrics matter:
  I  one stem, as wide as the weight says; advance = stem + 160
  H  two stems and a bar; its advance follows the width axis
  V  a stem whose right edge leans further as the weight grows. Its right
     edge has five points, and the three in the middle always lie on the
     line between the end ones, so varLib leaves their deltas out of gvar
     and HarfBuzz has to infer them (IUP).

Fonts written:
  var.ttf          no avar
  var-avar.ttf     avar 1: the weight axis is bent, so wght=600 is drawn
                   as the design at 750
  var-avar2.ttf    avar 2: at the narrowest width, weight is mapped lighter
  var-nohvar.ttf   var.ttf without HVAR: advances come from gvar's phantom
                   points instead
  var-badhvar.ttf  var.ttf with HVAR's deltas doubled, so HVAR and the
                   outlines disagree about the advances
"""
import os
import sys
import tempfile

from fontTools.designspaceLib import (AxisDescriptor, AxisMappingDescriptor,
                                      DesignSpaceDocument, InstanceDescriptor,
                                      SourceDescriptor)
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools import varLib

GLYPHS = {".notdef": None, "space": 0x20, "H": 0x48, "I": 0x49, "V": 0x56}
SB = 80        # side bearing
CAP = 700      # height of every glyph

# The masters: (wght, wdth) in design coordinates, and the shapes there.
# stem: stem width. width: H's advance. lean: how far V's top-right corner
# is right of its bottom-right corner. xheight, capheight: OS/2 metrics,
# which varLib turns into MVAR.
MASTERS = [
    # wght  wdth  stem  width  lean  xheight
    (400, 100, 100, 600,   0, 500),   # the default
    (100, 100,  40, 560,   0, 480),
    (650, 100, 200, 660,  60, 515),   # off the straight line from 400 to 900
    (900, 100, 250, 700, 150, 530),
    (400,  75,  90, 450,   0, 500),
]


def rect(pen, x0, y0, x1, y1):
    """A clockwise rectangle, as TrueType outer contours are."""
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()


def draw(name, stem, width, lean):
    pen = TTGlyphPen(None)
    if name == "I":
        rect(pen, SB, 0, SB + stem, CAP)
        advance = stem + 2 * SB
    elif name == "H":
        bar = round(stem * 0.8)
        rect(pen, SB, 0, SB + stem, CAP)
        rect(pen, width - SB - stem, 0, width - SB, CAP)
        rect(pen, SB + stem, 330, width - SB - stem, 330 + bar)
        advance = width
    elif name == "V":
        right = lambda y: SB + stem + round(lean * y / CAP)
        pen.moveTo((SB, 0)); pen.lineTo((SB, CAP))
        for y in (CAP, 525, 350, 175, 0):
            pen.lineTo((right(y), y))
        pen.closePath()
        advance = SB + stem + lean + SB
    elif name == "space":
        advance = 250
    else:  # .notdef
        rect(pen, SB, 0, 500 - SB, CAP)
        advance = 500
    return pen.glyph(), advance


def master(path, stem, width, lean, xheight):
    order = list(GLYPHS)
    glyphs, metrics = {}, {}
    for g in order:
        glyph, advance = draw(g, stem, width, lean)
        glyphs[g] = glyph
        metrics[g] = advance
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, cp in GLYPHS.items() if cp})
    fb.setupGlyf(glyphs)
    # The left side bearing is the glyph's xMin, as the font tools set it.
    fb.setupHorizontalMetrics({g: (metrics[g], getattr(glyphs[g], "xMin", 0)) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Var Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200,
                sxHeight=xheight, sCapHeight=CAP)
    fb.setupPost()
    fb.save(path)


def designspace(tmp, avar=None, avar2=False):
    doc = DesignSpaceDocument()
    for tag, name, lo, default, hi in (("wght", "Weight", 100, 400, 900), ("wdth", "Width", 75, 100, 100)):
        a = AxisDescriptor()
        a.tag, a.name, a.minimum, a.default, a.maximum = tag, name, lo, default, hi
        if tag == "wght" and avar:
            a.map = avar  # (user, design) pairs: this is what becomes avar 1
        doc.addAxis(a)
    for i, (wght, wdth, stem, width, lean, xheight) in enumerate(MASTERS):
        path = os.path.join(tmp, f"master{i}.ttf")
        master(path, stem, width, lean, xheight)
        s = SourceDescriptor()
        s.path, s.location = path, {"Weight": wght, "Width": wdth}
        doc.addSource(s)
    # Named instances, in fvar. Their locations are in user coordinates.
    for style, wght, wdth in (("Light", 100, 100), ("Regular", 400, 100),
                              ("Bold", 700, 100), ("Narrow", 400, 75)):
        inst = InstanceDescriptor()
        inst.familyName, inst.styleName = "HBBook Var Test", style
        inst.userLocation = {"Weight": wght, "Width": wdth}
        doc.addInstance(inst)
    if avar2:
        # avar 2: at the narrowest width, every weight is drawn lighter. The
        # mappings are in design coordinates.
        for wght_in, wght_out in ((100, 100), (400, 300), (900, 750)):
            m = AxisMappingDescriptor()
            m.inputLocation = {"Weight": wght_in, "Width": 75}
            m.outputLocation = {"Weight": wght_out, "Width": 75}
            doc.axisMappings.append(m)
    return doc


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        plain = varLib.build(designspace(tmp))[0]
        plain.save(os.path.join(out_dir, "var.ttf"))

        bent = [(100, 100), (400, 400), (600, 750), (900, 900)]
        varLib.build(designspace(tmp, avar=bent))[0].save(os.path.join(out_dir, "var-avar.ttf"))

        varLib.build(designspace(tmp, avar2=True))[0].save(os.path.join(out_dir, "var-avar2.ttf"))

        nohvar = TTFont(os.path.join(out_dir, "var.ttf"))
        del nohvar["HVAR"]
        nohvar.save(os.path.join(out_dir, "var-nohvar.ttf"))

        bad = TTFont(os.path.join(out_dir, "var.ttf"))
        for data in bad["HVAR"].table.VarStore.VarData:
            data.Item = [[2 * d for d in row] for row in data.Item]
        bad.save(os.path.join(out_dir, "var-badhvar.ttf"))
    for f in sorted(os.listdir(out_dir)):
        if f.endswith(".ttf"):
            print(os.path.join(out_dir, f))


if __name__ == "__main__":
    build(sys.argv[1])
