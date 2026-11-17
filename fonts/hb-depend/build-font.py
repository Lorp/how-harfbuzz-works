"""Build the test font for the hb-depend chapter.

usage: python3 build-font.py   (run from this folder; build.sh does)

depend.ttf is gsub/ligatures.ttf (the GSUB chapter's font, built from
gsub/ligatures.fea) with one glyph added at the end: aacute, mapped to
U+00E1, a TrueType composite of a and acutecomb. Everything else is
unchanged, so the GSUB edges come from the GSUB chapter's rules and the
composite adds one glyf dependency.
"""
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent


def main():
    font = TTFont("../gsub/ligatures.ttf")
    order = font.getGlyphOrder() + ["aacute"]
    font.setGlyphOrder(order)

    glyph = Glyph()
    glyph.numberOfContours = -1
    components = []
    for name, (x, y) in (("a", (0, 0)), ("acutecomb", (250, 0))):
        c = GlyphComponent()
        c.glyphName, c.x, c.y, c.flags = name, x, y, 0
        components.append(c)
    components[0].flags = 0x0200  # USE_MY_METRICS
    glyph.components = components
    font["glyf"].glyphs["aacute"] = glyph
    font["glyf"].glyphOrder = order
    font["hmtx"].metrics["aacute"] = font["hmtx"].metrics["a"]
    font["maxp"].numGlyphs = len(order)
    for table in font["cmap"].tables:
        table.cmap[0xE1] = "aacute"
    font["post"].formatType = 2.0
    font["post"].extraNames = []
    font["post"].mapping = {}
    font.save("depend.ttf")


if __name__ == "__main__":
    main()
