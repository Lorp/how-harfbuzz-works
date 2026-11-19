// Draw a line of text on a <canvas>: harfbuzzjs shapes it, and the browser
// fills the glyphs' outlines.
import * as hb from "harfbuzzjs";

export function drawText(canvas, fontData, text, pixels) {
  // Load the font and shape the text, in font units.
  const font = new hb.Font(new hb.Face(new hb.Blob(fontData)));
  const buffer = new hb.Buffer();
  buffer.addText(text);
  buffer.guessSegmentProperties();
  hb.shape(font, buffer);

  // Size the canvas: the line's advance, and the font's ascender and
  // descender, turned from font units into pixels.
  const scale = pixels / font.face.upem;
  const { ascender, descender } = font.hExtents();
  const positions = buffer.getGlyphPositions();
  let width = 0;
  for (let i = 0; i < positions.length; i++) width += positions[i].xAdvance;
  const top = Math.ceil(ascender * scale);
  const bottom = Math.floor(descender * scale);
  canvas.width = Math.ceil(width * scale);
  canvas.height = top - bottom;

  // Draw in font units, y up, with the baseline below the ascender.
  const ctx = canvas.getContext("2d");
  ctx.translate(0, top);
  ctx.scale(scale, -scale);

  // Fill each glyph's outline at its pen position.
  const infos = buffer.getGlyphInfos();
  let x = 0, y = 0;
  for (let i = 0; i < infos.length; i++) {
    const pos = positions[i];
    ctx.save();
    ctx.translate(x + pos.xOffset, y + pos.yOffset);
    ctx.fill(new Path2D(font.glyphToPath(infos[i].codepoint)));
    ctx.restore();
    x += pos.xAdvance;
    y += pos.yAdvance;
  }
}
