"""Prints what a font's MATH table says about each glyph: which glyphs have
an italics correction, and which have size variants, and what they are.

usage: python3 math-summary.py FONT.ttf ...

The chapter quotes this output (it is fontTools reading the fonts, not
HarfBuzz), because no HarfBuzz tool prints a MATH table.
"""
import os
import sys
from fontTools.ttLib import TTFont

for path in sys.argv[1:]:
    m = TTFont(path)["MATH"].table
    print(os.path.basename(path))
    ic = m.MathGlyphInfo.MathItalicsCorrectionInfo
    print("  italics correction:", ", ".join(ic.Coverage.glyphs) if ic else "none")
    v = m.MathVariants
    print("  vertical variants:")
    for g, c in zip(v.VertGlyphCoverage.glyphs, v.VertGlyphConstruction):
        print(f"    {g} -> {', '.join(r.VariantGlyph for r in c.MathGlyphVariantRecord)}")
