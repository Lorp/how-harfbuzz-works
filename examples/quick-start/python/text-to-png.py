# Shape a line of text with uharfbuzz, paint it with hb-raster, and save it
# as a PNG with Pillow.
# usage: python text-to-png.py FONT TEXT PIXELS > out.png
import math
import sys
import uharfbuzz as hb
from PIL import Image

font_path, text, pixels = sys.argv[1], sys.argv[2], int(sys.argv[3])

blob = hb.Blob.from_file_path(font_path)
face = hb.Face(blob)
font = hb.Font(face)

# The size: one pixel is 64 units, so positions keep fractions of a pixel.
font.scale = (pixels * 64, pixels * 64)

buf = hb.Buffer()
buf.add_str(text)
buf.guess_segment_properties()
hb.shape(font, buf)

infos = buf.glyph_infos
positions = buf.glyph_positions

# The image: as wide as the line, and as tall as the font's ascender and
# descender, in whole pixels.
width = 0
for pos in positions:
    width += pos.x_advance
extents = font.get_font_extents("ltr")
top = math.ceil(extents.ascender / 64)
bottom = math.floor(extents.descender / 64)

# Paint each glyph at its pen position, in black, the default.
paint = hb.RasterPaint()
paint.scale_factor = (64, 64)  # 64 units to the pixel
paint.extents = hb.RasterExtents(0, bottom, math.ceil(width / 64), top - bottom, 0)
x = y = 0
for i in range(len(infos)):
    pos = positions[i]
    paint.transform = (1, 0, 0, 1, x + pos.x_offset, y + pos.y_offset)
    paint.paint_glyph(font, infos[i].codepoint)
    x += pos.x_advance
    y += pos.y_advance

# hb-raster gives premultiplied BGRA pixels, rows bottom to top; Pillow
# turns them into a PNG.
image = paint.render()
e = image.extents
png = Image.frombuffer("RGBA", (e.width, e.height), image.buffer, "raw", "BGRa", e.stride, -1)
png.save(sys.stdout.buffer, "PNG")
