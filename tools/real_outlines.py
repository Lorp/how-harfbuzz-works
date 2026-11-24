"""Borrow glyph outlines from real fonts, for test fonts whose output is drawn.

A test font keeps its own glyph names, cmap and feature file; only the outlines
and advances come from a source font. A test glyph can be made of several
source glyphs, each moved by an offset: Noto Naskh Arabic, for example, draws
beh as a dotless body and a separate dot, which its GPOS places.

    from real_outlines import Sources, build
    src = Sources({"lat": "quick-start/LibreBaskerville.ttf", ...})
    build(src, GLYPHS, CMAP, "Family name", fea_path, out_path)

Source paths are relative to fonts/. A variable source gives its default
instance. Composites are decomposed, and hinting is not copied.
"""
import os
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.feaLib.builder import addOpenTypeFeatures

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")


class Sources:
    def __init__(self, paths):
        self.fonts = {k: TTFont(os.path.join(FONTS, p)) for k, p in paths.items()}

    def draw(self, key, parts, pen):
        """Draw parts, a list of (source glyph, dx, dy), into pen."""
        font = self.fonts[key]
        gs = font.getGlyphSet()
        for name, dx, dy in parts:
            rec = DecomposingRecordingPen(gs)
            gs[name].draw(rec)
            rec.replay(TransformPen(pen, (1, 0, 0, 1, dx, dy)))

    def advance(self, key, name):
        return self.fonts[key]["hmtx"][name][0]


def build(src, glyphs, family, fea, out, ascent=1100, descent=-650):
    """glyphs: {test glyph: (code point or None, source key, parts, advance or None)},
    in glyph order. An advance of None takes the first part's advance."""
    outlines, metrics = {}, {}
    for name, (_, key, parts, adv) in glyphs.items():
        pen = TTGlyphPen(None)
        src.draw(key, parts, pen)
        outlines[name] = pen.glyph()
        bounds = BoundsPen(None)
        src.draw(key, parts, bounds)
        lsb = bounds.bounds[0] if bounds.bounds else 0
        metrics[name] = (adv if adv is not None else src.advance(key, parts[0][0]), round(lsb))
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({cp: g for g, (cp, *_) in glyphs.items() if cp is not None})
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ascent, descent=descent)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=descent,
                usWinAscent=ascent, usWinDescent=-descent)
    fb.setupPost()
    addOpenTypeFeatures(fb.font, fea)
    fb.save(out)
