"""Build the test fonts for the chapter “Colour”.

usage: python3 build-colour-fonts.py OUT_DIR

Every glyph is made of squares, bars and discs. Each colour glyph also has an
outline of its own, a plain black square with a corner cut off, so that a
drawing shows at once when HarfBuzz has fallen back to the outline.

Fonts written:
  colr0.ttf          COLR version 0 and CPAL version 1, with two palettes.
                     A is three layers: a square in palette entry 0, a disc in
                     entry 1, and a bar in the foreground colour (0xFFFF).
                     B is the same layers in another order. Palette 0 is
                     marked usable on a light background, palette 1 on a
                     dark one, and both have names.
  colr0-swapped.ttf  colr0.ttf with its two palettes stored the other way
                     round.
  colr1.ttf          COLR version 1, with one variation axis, SPIN (0 to 1):
                       L  a smaller square filled with a linear gradient,
                          small enough to stay inside the ClipBox when
                          G and V rotate it
                       P, R, F  a radial gradient, the same in each, with
                          extend pad, repeat and reflect
                       S  a sweep gradient
                       X  two discs composited with DEST_OUT (a crescent)
                       M  two discs composited with MULTIPLY
                       G  PaintColrGlyph of L, rotated 30 degrees
                       V  L, rotated by a variable angle: 0 at SPIN=0,
                          90 degrees at SPIN=1
                       U  a PaintSolid with nothing around it, and no ClipBox
                       C  the same PaintSolid, with a ClipBox
                     Every glyph but U has the same ClipBox, so that
                     the clips hb-vector writes are the same in every
                     drawing: the drawings share one page, and the ids
                     of their definitions (c0, p0, gr0) with it.
  images.ttf         SVG and sbix:
                       S  an SVG document only
                       T  an SVG document and an sbix bitmap
                       P  sbix bitmaps only, in two strikes: a coarse 10-pixel
                          image at ppem 10, a smooth one at ppem 100
                       N  no image at all
"""
import math
import os
import struct
import sys
import zlib

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
from fontTools.ttLib.tables.sbixStrike import Strike as SbixStrike
from fontTools.varLib.builder import (buildVarData,
                                      buildVarRegionList, buildVarStore)

UPEM = 1000
ADVANCE = 1000

# --- outlines -------------------------------------------------------------


def rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()


def disc(pen, cx, cy, r):
    # Eight off-curve points on the octagon around the circle.
    k = r / math.cos(math.pi / 8)
    pts = [(round(cx + k * math.cos(a)), round(cy + k * math.sin(a)))
           for a in (-i * math.pi / 4 for i in range(8))]
    pen.qCurveTo(*pts, None)
    pen.closePath()


def fallback(pen):
    # The outline every colour glyph has: a square with its top right corner cut.
    pen.moveTo((100, 0)); pen.lineTo((100, 800)); pen.lineTo((650, 800))
    pen.lineTo((900, 550)); pen.lineTo((900, 0)); pen.closePath()


SHAPES = {
    "sq":    lambda p: rect(p, 100, 0, 900, 800),
    "disc":  lambda p: disc(p, 500, 400, 300),
    "bar":   lambda p: rect(p, 100, 330, 900, 470),
    "discL": lambda p: disc(p, 380, 400, 280),
    "discR": lambda p: disc(p, 620, 400, 280),
    "box":   lambda p: rect(p, 100, 0, 900, 800),
    "small": lambda p: rect(p, 250, 150, 750, 650),
}


def glyph(draw):
    pen = TTGlyphPen(None)
    if draw:
        draw(pen)
    return pen.glyph()


def make_font(base_glyphs, layer_glyphs, family, axes=None):
    """base_glyphs: letters, each drawn with the fallback outline."""
    order = [".notdef", "space"] + base_glyphs + layer_glyphs
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x20: "space", **{ord(g): g for g in base_glyphs}})
    glyphs = {".notdef": glyph(lambda p: rect(p, 100, 0, 900, 800)), "space": glyph(None)}
    for g in base_glyphs:
        glyphs[g] = glyph(fallback)
    for g in layer_glyphs:
        glyphs[g] = glyph(SHAPES[g])
    fb.setupGlyf(glyphs)
    metrics = {}
    for g in order:
        gl = fb.font["glyf"][g]
        metrics[g] = (ADVANCE, getattr(gl, "xMin", 0))
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-200, usWinAscent=900, usWinDescent=200)
    fb.setupPost()
    if axes:
        fb.setupFvar(axes, [])
    return fb


def rgba(hexstr, a=1.0):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


# --- COLR version 0 -------------------------------------------------------

V0_PALETTES = [
    [rgba("E8A33D"), rgba("2A6FDB")],   # 0: amber square, blue disc
    [rgba("3B2E5A"), rgba("F25C54")],   # 1: deep violet square, coral disc
]


def colr0(out, swapped=False):
    fb = make_font(["A", "B"], ["sq", "disc", "bar"], "Colour Test COLRv0")
    font = fb.font
    font["COLR"] = buildCOLR({
        "A": [("sq", 0), ("disc", 1), ("bar", 0xFFFF)],
        "B": [("disc", 1), ("bar", 0xFFFF), ("sq", 0)],
    }, version=0)
    palettes, types, labels = V0_PALETTES, [1, 2], ["Daylight", "Night"]
    if swapped:
        palettes, types, labels = palettes[::-1], types[::-1], labels[::-1]
    font["CPAL"] = buildCPAL(palettes, paletteTypes=types, paletteLabels=labels,
                             paletteEntryLabels=["Ground", "Disc"], nameTable=font["name"])
    font.save(out)


# --- COLR version 1 -------------------------------------------------------

V1_PALETTE = [
    rgba("D7263D"),   # 0 red
    rgba("F4A259"),   # 1 amber
    rgba("1B98E0"),   # 2 blue
    rgba("2E294E"),   # 3 ink
    rgba("8CD867"),   # 4 green
]

F = ot.PaintFormat


def stops(*s):
    return [{"StopOffset": o, "PaletteIndex": i, "Alpha": a} for o, i, a in s]


def solid(index, alpha=1.0):
    return {"Format": F.PaintSolid, "PaletteIndex": index, "Alpha": alpha}


def in_glyph(name, paint):
    return {"Format": F.PaintGlyph, "Glyph": name, "Paint": paint}


LINEAR = {
    "Format": F.PaintLinearGradient,
    "ColorLine": {"Extend": "pad", "ColorStop": stops((0, 0, 1), (0.5, 1, 1), (1, 2, 1))},
    "x0": 250, "y0": 150, "x1": 750, "y1": 150, "x2": 250, "y2": 650,
}


def radial(extend):
    return {
        "Format": F.PaintRadialGradient,
        "ColorLine": {"Extend": extend, "ColorStop": stops((0, 1, 1), (1, 2, 1))},
        "x0": 500, "y0": 400, "r0": 0, "x1": 500, "y1": 400, "r1": 160,
    }


SWEEP = {
    "Format": F.PaintSweepGradient,
    "ColorLine": {"Extend": "pad", "ColorStop": stops((0, 0, 1), (0.33, 1, 1), (0.66, 4, 1), (1, 2, 1))},
    "centerX": 500, "centerY": 400, "startAngle": 0, "endAngle": 360,
}


def composite(mode):
    return {
        "Format": F.PaintComposite,
        "BackdropPaint": in_glyph("discL", solid(2)),
        "SourcePaint": in_glyph("discR", solid(0)),
        "CompositeMode": mode,
    }


def colr1(out):
    base = ["L", "P", "R", "F", "S", "X", "M", "G", "V", "U", "C"]
    fb = make_font(base, ["box", "small", "discL", "discR"], "Colour Test COLRv1",
                   axes=[("SPIN", 0, 0, 1, "Spin")])
    font = fb.font
    # One region, peaking at SPIN=1; one delta set: +0.5 (90 degrees), as
    # F2DOT14 raw units.
    regions = buildVarRegionList([{"SPIN": (0, 1, 1)}], ["SPIN"])
    store = buildVarStore(regions, [buildVarData([0], [[8192]], optimize=False)])
    paints = {
        "L": in_glyph("small", LINEAR),
        "P": in_glyph("box", radial("pad")),
        "R": in_glyph("box", radial("repeat")),
        "F": in_glyph("box", radial("reflect")),
        "S": in_glyph("box", SWEEP),
        "X": composite("dest_out"),
        "M": composite("multiply"),
        "G": {"Format": F.PaintRotateAroundCenter, "angle": 30, "centerX": 500, "centerY": 400,
              "Paint": {"Format": F.PaintColrGlyph, "Glyph": "L"}},
        "V": {"Format": F.PaintVarRotateAroundCenter, "angle": 0, "centerX": 500, "centerY": 400,
              "VarIndexBase": 0,
              "Paint": {"Format": F.PaintColrGlyph, "Glyph": "L"}},
        "U": solid(4),
        "C": solid(4),
    }
    clip = (100, 0, 900, 800)
    clips = {g: clip for g in base if g != "U"}
    font["COLR"] = buildCOLR(paints, version=1, glyphMap=font.getReverseGlyphMap(),
                             varStore=store, clipBoxes=clips)
    font["CPAL"] = buildCPAL([V1_PALETTE])
    font.save(out)


# --- SVG and sbix ---------------------------------------------------------


def png(width, height, pixel):
    """A minimal RGBA PNG; pixel(x, y) gives (r, g, b, a), y from the top."""
    raw = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(width))
                   for y in range(height))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def disc_png(size, colour):
    c = (size - 1) / 2
    r = size * 0.42

    def pixel(x, y):
        return colour + (255,) if (x - c) ** 2 + (y - c) ** 2 <= r * r else (0, 0, 0, 0)
    return png(size, size, pixel)


SVG_DOC = ('<svg xmlns="http://www.w3.org/2000/svg">'
           '<g id="glyph{gid}"><circle cx="500" cy="-400" r="300" fill="#2A6FDB"/></g></svg>')


def images(out):
    fb = make_font(["S", "T", "P", "N"], [], "Colour Test Images")
    font = fb.font
    gid = font.getReverseGlyphMap()
    svg = newTable("SVG ")
    svg.docList = [(SVG_DOC.format(gid=gid["S"]), gid["S"], gid["S"]),
                   (SVG_DOC.format(gid=gid["T"]), gid["T"], gid["T"])]
    font["SVG "] = svg
    sbix = newTable("sbix")
    sbix.version, sbix.flags = 1, 1
    for ppem, size, colour in ((10, 8, (215, 38, 61)), (100, 80, (46, 160, 90))):
        strike = SbixStrike(ppem=ppem, resolution=72)
        for name in ("T", "P"):
            # Images sit 10% of the em in from the left, on the baseline.
            strike.glyphs[name] = SbixGlyph(glyphName=name, graphicType="png ",
                                            originOffsetX=ppem // 10, originOffsetY=0,
                                            imageData=disc_png(size, colour))
        sbix.strikes[ppem] = strike
    font["sbix"] = sbix
    font.save(out)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    colr0(os.path.join(out, "colr0.ttf"))
    colr0(os.path.join(out, "colr0-swapped.ttf"), swapped=True)
    colr1(os.path.join(out, "colr1.ttf"))
    images(os.path.join(out, "images.ttf"))


if __name__ == "__main__":
    main()
