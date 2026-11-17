"""Build the test fonts for the chapter “Drawing outlines”.

usage: python3 build-fonts.py OUT_DIR

Fonts written (upem 1000):
  outlines.ttf         glyf. b, a bowl and a stem with quadratic curves and
                       implied on-curve points; d, p and q, composites of b
                       flipped and rotated by 2x2 transforms; dotlessi,
                       dotaccent and i, where the dot is attached by
                       matching points (dotaccent has a one-point contour
                       below its dot, as an anchor); b_i (on x), b and i
                       side by side, so that i's point matching is nested
                       inside another composite; oncurve, offcurve and
                       cubic, the same four points flagged on-curve,
                       off-curve, and off-curve with the cubic bit (0x80)
  outlines-GLYF.ttf    the same glyph data in GLYF and LOCA instead of glyf
                       and loca, where HarfBuzz reads the cubic bit
  outlines-scaled.ttf  outlines.ttf with SCALED_COMPONENT_OFFSET set on the
                       components of d, p and q
  cff.otf              CFF: o, dieresis, and odieresis, made by seac from
                       the other two
  limits.ttf           spiral64 (on 1) and spiral65 (on 2), each a square
                       and the spiral before it, turned and shrunk, so
                       spiralN nests N composites deep; and heavy (on h), a
                       square and 14,520 components of an empty glyph;
                       and square (on s), a plain square

fontTools 4.38 drops the cubic bit when it compiles glyf (it keeps only the
on-curve and overlap flags), so the cubic glyph is written as bytes here.
"""
import os
import struct
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.misc.psCharStrings import T2CharString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent, GlyphCoordinates

SQUARE = [(100, 100), (100, 700), (700, 700), (700, 100)]


def simple(contours):
    """contours: lists of (x, y, flag); flag 1 is on-curve."""
    g = Glyph()
    g.numberOfContours = len(contours)
    g.coordinates = GlyphCoordinates([(x, y) for c in contours for x, y, _ in c])
    g.flags = bytearray(f for c in contours for _, _, f in c)
    g.endPtsOfContours, n = [], 0
    for c in contours:
        n += len(c)
        g.endPtsOfContours.append(n - 1)
    g.program = ttProgram.Program()
    g.program.fromBytecode(b"")
    return g


def composite(*components):
    """components: (glyph name, (xx, xy, yx, yy), (dx, dy)) or
    (glyph name, None, ('match', base point, component point))."""
    g = Glyph()
    g.numberOfContours = -1
    g.components = []
    for name, matrix, offset in components:
        c = GlyphComponent()
        c.glyphName = name
        if offset[0] == "match":
            c.firstPt, c.secondPt = offset[1], offset[2]
            c.flags = 0
        else:
            c.x, c.y = offset
            c.flags = 0x0004  # ROUND_XY_TO_GRID, as most fonts set it
            if matrix and matrix != (1, 0, 0, 1):
                c.transform = [[matrix[0], matrix[1]], [matrix[2], matrix[3]]]
        g.components.append(c)
    return g


def b_glyph():
    pen = TTGlyphPen(None)
    # The stem.
    pen.moveTo((100, 0)); pen.lineTo((100, 750)); pen.lineTo((200, 750)); pen.lineTo((200, 0))
    pen.closePath()
    # The bowl: two off-curve points in a row, so an on-curve point is
    # implied between them, at (500, 225).
    pen.moveTo((150, 0)); pen.lineTo((150, 450))
    pen.qCurveTo((500, 450), (500, 0), (150, 0))
    pen.closePath()
    # The counter, the other way round.
    pen.moveTo((200, 100)); pen.qCurveTo((400, 100), (400, 350), (200, 350))
    pen.closePath()
    return pen.glyph()


def outline_glyphs():
    return {
        ".notdef": simple([[(50, 0, 1), (50, 700, 1), (450, 700, 1), (450, 0, 1)]]),
        "b": b_glyph(),
        "d": composite(("b", (-1, 0, 0, 1), (600, 0))),
        "p": composite(("b", (1, 0, 0, -1), (0, 450))),
        "q": composite(("b", (-1, 0, 0, -1), (600, 450))),
        "dotlessi": simple([[(100, 0, 1), (100, 500, 1), (200, 500, 1), (200, 0, 1)]]),
        # A dot, and a contour of one point 150 units below it.
        "dotaccent": simple([[(0, 0, 1), (0, 100, 1), (100, 100, 1), (100, 0, 1)],
                             [(0, -150, 1)]]),
        # Point 1 of dotlessi (its top left) meets point 4 of dotaccent.
        "i": composite(("dotlessi", None, (0, 0)), ("dotaccent", None, ("match", 1, 4))),
        # b and i side by side: i is itself a composite that matches points.
        "b_i": composite(("b", None, (0, 0)), ("i", None, (600, 0))),
        "oncurve": simple([[(x, y, 1) for x, y in SQUARE]]),
        "offcurve": simple([[(x, y, 0) for x, y in SQUARE]]),
        "cubic": simple([[(x, y, 0) for x, y in SQUARE]]),  # bytes patched below
    }


OUTLINE_CMAP = {"b": 0x62, "d": 0x64, "p": 0x70, "q": 0x71, "dotlessi": 0x131,
                "dotaccent": 0x2D9, "i": 0x69, "b_i": 0x78, "oncurve": 0x31, "offcurve": 0x32,
                "cubic": 0x33}
ADVANCES = {".notdef": 500, "b": 600, "d": 600, "p": 600, "q": 600, "dotlessi": 300,
            "dotaccent": 100, "i": 300, "b_i": 900, "oncurve": 800, "offcurve": 800, "cubic": 800}


def raw_simple(points, flag):
    """A simple glyph of one contour, every flag written out, every
    coordinate a 16-bit delta: the plainest encoding there is."""
    xs = [x for x, _ in points]; ys = [y for _, y in points]
    out = struct.pack(">hhhhh", 1, min(xs), min(ys), max(xs), max(ys))
    out += struct.pack(">H", len(points) - 1)
    out += struct.pack(">H", 0)                    # no instructions
    out += bytes([flag] * len(points))
    px = py = 0
    for x, _ in points:
        out += struct.pack(">h", x - px); px = x
    for _, y in points:
        out += struct.pack(">h", y - py); py = y
    return out


def raw_glyf(font, replace):
    """glyf and loca as bytes (long offsets), with some glyphs replaced."""
    glyf = font["glyf"]
    data, offsets = b"", []
    for name in font.getGlyphOrder():
        offsets.append(len(data))
        g = replace[name] if name in replace else glyf[name].compile(glyf)
        data += g + b"\0" * (-len(g) % 4)
    offsets.append(len(data))
    return data, struct.pack(">%dI" % len(offsets), *offsets)


def table(tag, data):
    t = DefaultTable(tag)
    t.data = data
    return t


def builder(order, cmap, advances):
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    return fb


def finish(fb, glyphs, advances, name):
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    fb.setupHorizontalMetrics({g: (advances[g], getattr(glyf[g], "xMin", 0))
                               for g in fb.font.getGlyphOrder()})
    fb.setupHorizontalHeader(ascent=1100, descent=-300, lineGap=0)
    fb.setupNameTable({"familyName": name, "styleName": "Regular"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, usWinAscent=1100,
                usWinDescent=300)
    fb.setupPost()


def build_outlines(out):
    glyphs = outline_glyphs()
    order = list(glyphs)
    fb = builder(order, {cp: g for g, cp in OUTLINE_CMAP.items()}, ADVANCES)
    finish(fb, glyphs, ADVANCES, "HBBook Outlines Test")
    tmp = os.path.join(out, "outlines.tmp.ttf")
    fb.save(tmp)

    f = TTFont(tmp, recalcBBoxes=False)
    glyf_data, loca_data = raw_glyf(f, {"cubic": raw_simple(SQUARE, 0x80)})
    scaled = TTFont(tmp, recalcBBoxes=False)
    for g in ("d", "p", "q"):
        for c in scaled["glyf"][g].components:
            c.flags |= 0x0800  # SCALED_COMPONENT_OFFSET
    sglyf_data, sloca_data = raw_glyf(scaled, {"cubic": raw_simple(SQUARE, 0x80)})

    for fname, tags, (gd, ld) in [("outlines.ttf", ("glyf", "loca"), (glyf_data, loca_data)),
                                  ("outlines-GLYF.ttf", ("GLYF", "LOCA"), (glyf_data, loca_data)),
                                  ("outlines-scaled.ttf", ("glyf", "loca"), (sglyf_data, sloca_data))]:
        f = TTFont(tmp, recalcBBoxes=False)
        f["head"].indexToLocFormat = 1
        del f["glyf"]; del f["loca"]
        f[tags[0]] = table(tags[0], gd)
        f[tags[1]] = table(tags[1], ld)
        f.save(os.path.join(out, fname))
    os.remove(tmp)


def ellipse(pen, cx, cy, rx, ry, clockwise):
    k = 0.5523
    pts = [(cx, cy - ry), (cx - rx, cy), (cx, cy + ry), (cx + rx, cy)]
    if clockwise:
        pts = [pts[0], pts[3], pts[2], pts[1]]
    pen.moveTo(pts[0])
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        # Control points along the tangents at a and b.
        c1 = (a[0] + k * (b[0] - a[0]), a[1]) if a[0] == cx else (a[0], a[1] + k * (b[1] - a[1]))
        c2 = (b[0], b[1] + k * (a[1] - b[1])) if a[0] == cx else (b[0] + k * (a[0] - b[0]), b[1])
        pen.curveTo(tuple(map(round, c1)), tuple(map(round, c2)), b)
    pen.closePath()


def build_cff(out):
    order = [".notdef", "o", "dieresis", "odieresis"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x6F: "o", 0xA8: "dieresis", 0xF6: "odieresis"})
    cs = {}
    pen = T2CharStringPen(500, None)
    for x0, y0, x1, y1 in [(50, 0, 450, 700)]:
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
        pen.closePath()
    cs[".notdef"] = pen.getCharString()
    pen = T2CharStringPen(600, None)
    ellipse(pen, 300, 250, 200, 250, clockwise=False)
    ellipse(pen, 300, 250, 100, 170, clockwise=True)
    cs["o"] = pen.getCharString()
    pen = T2CharStringPen(300, None)
    for x0 in (0, 200):
        pen.moveTo((x0, 0)); pen.lineTo((x0 + 100, 0)); pen.lineTo((x0 + 100, 100)); pen.lineTo((x0, 100))
        pen.closePath()
    cs["dieresis"] = pen.getCharString()
    # endchar with four arguments (after the width) is seac: draw the glyph
    # for StandardEncoding code 111 (o), then the one for 200 (dieresis),
    # moved by (150, 600).
    cs["odieresis"] = T2CharString(program=[600, 150, 600, 111, 200, "endchar"])
    fb.setupCFF("HBBookCFFTest", {"FullName": "HBBook CFF Test"}, cs, {})
    fb.setupHorizontalMetrics({".notdef": (500, 50), "o": (600, 100), "dieresis": (300, 0),
                               "odieresis": (600, 100)})
    fb.setupHorizontalHeader(ascent=900, descent=-300, lineGap=0)
    fb.setupNameTable({"familyName": "HBBook CFF Test", "styleName": "Regular"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, usWinAscent=900,
                usWinDescent=300)
    fb.setupPost()
    fb.save(os.path.join(out, "cff.otf"))


def build_limits(out, depth=65, fan=120):
    import math
    cx, cy = 450, 350
    glyphs = {".notdef": simple([[(50, 0, 1), (50, 700, 1), (450, 700, 1), (450, 0, 1)]]),
              "square": simple([[(0, 0, 1), (0, 100, 1), (100, 100, 1), (100, 0, 1)]]),
              "empty": Glyph()}
    # spiralN: a square, and spiralN-1 turned 15 degrees and shrunk by 5%
    # about (cx, cy). spiral0 is a plain square, so spiralN nests N deep.
    a, k = math.radians(15), 0.95
    m = (k * math.cos(a), k * math.sin(a), -k * math.sin(a), k * math.cos(a))
    # x' = x*m0 + y*m2, y' = x*m1 + y*m3; chosen so (cx, cy) stays put.
    off = (round(cx - (cx * m[0] + cy * m[2])), round(cy - (cx * m[1] + cy * m[3])))
    x0, y0 = cx + 250, cy - 50
    glyphs["spiral0"] = simple([[(x0, y0, 1), (x0, y0 + 100, 1), (x0 + 100, y0 + 100, 1),
                                 (x0 + 100, y0, 1)]])
    for n in range(1, depth + 1):
        glyphs["spiral%d" % n] = composite(("square", None, (x0, y0)),
                                           ("spiral%d" % (n - 1), m, off))
    # heavy: a square, and fan copies of mid, each fan copies of an empty
    # glyph: 1 + fan + fan * fan glyphs to load, and almost nothing to draw.
    glyphs["mid"] = composite(*[("empty", None, (0, 0))] * fan)
    glyphs["heavy"] = composite(("square", None, (0, 0)), *[("mid", None, (0, 0))] * fan)
    order = list(glyphs)
    cmap = {0x31: "spiral%d" % (depth - 1), 0x32: "spiral%d" % depth, 0x68: "heavy",
            0x73: "square"}
    fb = builder(order, cmap, None)
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    adv = {g: 900 for g in order}
    adv["heavy"] = adv["square"] = 150
    fb.setupHorizontalMetrics({g: (adv[g], getattr(glyf[g], "xMin", 0)) for g in order})
    fb.setupHorizontalHeader(ascent=900, descent=-300, lineGap=0)
    fb.setupNameTable({"familyName": "HBBook Limits Test", "styleName": "Regular"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, usWinAscent=900,
                usWinDescent=300)
    fb.setupPost()
    fb.save(os.path.join(out, "limits.ttf"))


def build(out):
    os.makedirs(out, exist_ok=True)
    build_outlines(out)
    build_cff(out)
    build_limits(out)
    for name in sorted(os.listdir(out)):
        if name.endswith((".ttf", ".otf")):
            print(os.path.join(out, name))


if __name__ == "__main__":
    build(sys.argv[1])
