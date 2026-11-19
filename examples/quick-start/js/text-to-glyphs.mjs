// Shape a line of text with harfbuzzjs and print the glyphs, as hb-shape does.
// usage: node text-to-glyphs.mjs FONT TEXT
import fs from "node:fs";
import * as hb from "harfbuzzjs";

const [fontPath, text] = process.argv.slice(2);

// Load the font: file → blob → face → font.
const blob = new hb.Blob(fs.readFileSync(fontPath));
const face = new hb.Face(blob);
if (!face.referenceTable("head")) {   // not a font: HarfBuzz gives an empty face
  console.error(`${fontPath} isn't a font`);
  process.exit(1);
}
const font = new hb.Font(face);

// Shape: characters in, positioned glyphs out, in font units.
const buffer = new hb.Buffer();
buffer.addText(text);
buffer.guessSegmentProperties();   // script, language, direction
hb.shape(font, buffer);

// Print each glyph: name=cluster, @offset if it has one, +advance.
const infos = buffer.getGlyphInfos();
const positions = buffer.getGlyphPositions();
const glyphs = infos.map((info, i) => {
  const pos = positions[i];
  const name = font.glyphName(info.codepoint);   // a glyph id, after shaping
  const offset = pos.xOffset || pos.yOffset ? `@${pos.xOffset},${pos.yOffset}` : "";
  return `${name}=${info.cluster}${offset}+${pos.xAdvance}`;
});
console.log(`[${glyphs.join("|")}]`);
