// Shape a line of text with harfbuzzjs and draw it as SVG.
// usage: node text-to-svg.mjs FONT TEXT > out.svg
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

// Draw each glyph's outline as an SVG path at its pen position.
const infos = buffer.getGlyphInfos();
const positions = buffer.getGlyphPositions();
let x = 0, y = 0, paths = "";
for (let i = 0; i < infos.length; i++) {
  const pos = positions[i];
  const d = font.glyphToPath(infos[i].codepoint);   // a glyph id, after shaping
  const at = `translate(${x + pos.xOffset},${y + pos.yOffset})`;
  if (d) paths += `<path transform="${at}" d="${d}"/>\n`;
  x += pos.xAdvance;
  y += pos.yAdvance;
}

// The box: the line's advance, and the font's ascender and descender.
const { ascender, descender } = font.hExtents();
const viewBox = `0 ${-ascender} ${x} ${ascender - descender}`;
console.log(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">`);
console.log(`<g transform="scale(1,-1)">\n${paths}</g>\n</svg>`);
