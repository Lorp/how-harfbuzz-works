"""Make a small font to ask HarfBuzz a question about some layout rules.

usage: python3 make-test-font.py FEATURES.fea OUT.ttf TEXT [GLYPH ...]

TEXT is the characters the font needs: each gets a glyph named as in the
Adobe Glyph List (a, T, acutecomb...), or uniXXXX. Each GLYPH is an extra,
unencoded glyph that the feature file's rules make, such as f_i.

Every glyph is a box. Shaping doesn't look at outlines: only the glyph
names, the cmap, the advances and the layout tables matter. Ligatures
(names with _) are wider, and combining marks have no advance.

Needs fontTools (pip install fonttools).
"""
import sys
import unicodedata

from fontTools.agl import UV2AGL
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def box(width):
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, 500))
    pen.lineTo((max(width, 100) - 50, 500))
    pen.lineTo((max(width, 100) - 50, 0))
    pen.closePath()
    return pen.glyph()


def main(fea, out, text, extra):
    cmap = {}
    for char in text:
        cmap[ord(char)] = UV2AGL.get(ord(char), f"uni{ord(char):04X}")
    marks = {name for cp, name in cmap.items() if unicodedata.combining(chr(cp))}
    names = [".notdef"] + sorted(set(cmap.values())) + list(extra)

    advances = {}
    for name in names:
        if name in marks:
            advances[name] = 0
        elif "_" in name:
            advances[name] = 900
        else:
            advances[name] = 500

    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf({name: box(advances[name]) for name in names})
    builder.setupHorizontalMetrics({name: (advances[name], 50) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    addOpenTypeFeatures(builder.font, fea)
    builder.save(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
