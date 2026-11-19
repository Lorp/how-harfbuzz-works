# Shape a line of text with uharfbuzz and draw it as SVG.
# usage: python text-to-svg.py FONT TEXT > out.svg
import sys
import uharfbuzz as hb


class SvgPen:
    """Collects one glyph's outline as SVG path data, in font units, y up."""

    def __init__(self):
        self.d = []

    def moveTo(self, p):
        self.d.append(f"M{p[0]:g},{p[1]:g}")

    def lineTo(self, p):
        self.d.append(f"L{p[0]:g},{p[1]:g}")

    def qCurveTo(self, c, p):
        self.d.append(f"Q{c[0]:g},{c[1]:g} {p[0]:g},{p[1]:g}")

    def curveTo(self, c1, c2, p):
        self.d.append(f"C{c1[0]:g},{c1[1]:g} {c2[0]:g},{c2[1]:g} {p[0]:g},{p[1]:g}")

    def closePath(self):
        self.d.append("Z")


font_path, text = sys.argv[1], sys.argv[2]

# Load the font: file → blob → face → font.
blob = hb.Blob.from_file_path(font_path)
face = hb.Face(blob)
if not face.glyph_count:  # not a font: HarfBuzz gives an empty face
    sys.exit(f"{font_path} isn't a font")
font = hb.Font(face)

# Shape: characters in, positioned glyphs out, in font units.
buf = hb.Buffer()
buf.add_str(text)
buf.guess_segment_properties()  # script, language, direction
hb.shape(font, buf)

# Draw each glyph's outline as an SVG path at its pen position.
infos = buf.glyph_infos
positions = buf.glyph_positions
x = y = 0
paths = ""
for i in range(len(infos)):
    pos = positions[i]
    pen = SvgPen()
    font.draw_glyph_with_pen(infos[i].codepoint, pen)  # a glyph id, after shaping
    if pen.d:
        at = f"translate({x + pos.x_offset},{y + pos.y_offset})"
        paths += f'<path transform="{at}" d="{" ".join(pen.d)}"/>\n'
    x += pos.x_advance
    y += pos.y_advance

# The box: the line's advance, and the font's ascender and descender.
extents = font.get_font_extents("ltr")
asc, desc = extents.ascender, extents.descender
print(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {-asc} {x} {asc - desc}">')
print(f'<g transform="scale(1,-1)">\n{paths}</g>\n</svg>')
