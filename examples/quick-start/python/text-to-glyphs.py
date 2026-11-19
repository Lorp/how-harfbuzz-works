# Shape a line of text with uharfbuzz and print the glyphs, as hb-shape does.
# usage: python text-to-glyphs.py FONT TEXT
import sys
import uharfbuzz as hb

font_path, text = sys.argv[1], sys.argv[2]

# Load the font: file → blob → face → font.
blob = hb.Blob.from_file_path(font_path)
face = hb.Face(blob)
font = hb.Font(face)

# Shape: characters in, positioned glyphs out, in font units.
buf = hb.Buffer()
buf.add_str(text)
buf.guess_segment_properties()  # script, language, direction
hb.shape(font, buf)

# Print each glyph: name=cluster, @offset if it has one, +advance.
glyphs = []
for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
    name = font.glyph_to_string(info.codepoint)  # a glyph id, after shaping
    offset = f"@{pos.x_offset},{pos.y_offset}" if pos.x_offset or pos.y_offset else ""
    glyphs.append(f"{name}={info.cluster}{offset}+{pos.x_advance}")
print("[" + "|".join(glyphs) + "]")
