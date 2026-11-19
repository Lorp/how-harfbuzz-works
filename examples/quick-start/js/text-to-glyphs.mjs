// Shape a line of text with harfbuzzjs and print the glyphs, as hb-shape does.
// usage: node text-to-glyphs.mjs FONT TEXT
import fs from "node:fs";
import * as hb from "harfbuzzjs";

const [fontPath, text] = process.argv.slice(2);

// Load the font: file → blob → face → font.
const blob = new hb.Blob(fs.readFileSync(fontPath));
const face = new hb.Face(blob);
const font = new hb.Font(face);

// Shape: characters in, positioned glyphs out, in font units.
const buffer = new hb.Buffer();
buffer.addText(text);
buffer.guessSegmentProperties();   // script, language, direction
hb.shape(font, buffer);

// Print each glyph: name=cluster, @offset if it has one, +advance.
const infos = buffer.getGlyphInfos();
const positions = buffer.getGlyphPositions();
const glyphs = [];
for (let i = 0; i < infos.length; i++) {
  const pos = positions[i];
  const name = font.glyphName(infos[i].codepoint);   // a glyph id, after shaping
  let glyph = `${name}=${infos[i].cluster}`;
  if (pos.xOffset || pos.yOffset) glyph += `@${pos.xOffset},${pos.yOffset}`;
  glyph += `+${pos.xAdvance}`;
  glyphs.push(glyph);
}
console.log(`[${glyphs.join("|")}]`);
