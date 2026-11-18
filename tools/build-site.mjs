// Builds the book as HTML pages: one page per Markdown file in book/toc.txt.
//
// usage: node tools/build-site.mjs [OUT_DIR] [--fragment]   (default: site/)
//        (or: npm run build)
//
// --fragment leaves out <!doctype>, <html>, <head> and <body>, for hosts
// that supply their own.
//
// Needs HB_BUILD (or .cache/harfbuzz/, made by tools/build-harfbuzz.sh): the
// HarfBuzz source, with build/ and build-msg/ beside it. Every shaping result
// and trace in the book is made here by running that hb-shape, so the text
// can't drift from what HarfBuzz does.
//
// Besides ordinary Markdown, a chapter can hold three kinds of fenced block,
// all run against the chapter's fonts in fonts/<chapter>/:
//
//   ```views                 the switchable views of one lookup
//   font: ligatures.ttf
//   lookup: 0
//   fea: ligatures.fea liga  (the feature file and block it came from)
//   cpp: LigatureSubstFormat1_2
//   print: spec fea          (optional: the views print shows; default spec)
//   ```
//
//   ```shape                 one hb-shape run per line: font, text, options,
//   ligatures.ttf  ffi       separated by two or more spaces; \uXXXX or \u{X…} in the
//   ligatures.ttf  ffi  --features=-liga                text is decoded
//   ```
//
//   ```trace                 hb-shape --trace, cut down to the lines between
//   font: ligatures.ttf      `from` and `to` (substrings of the trace lines),
//   text: f́i           and without skipped lookups unless `skipped: yes`
//   from: start lookup 0
//   to: end lookup 0
//   ```
//
//   ```raster                hb-raster's PNG, one image per line, enlarged
//   zoom: 8                  (optional; default 8). Lines as in `shape`;
//   hb:test/…/Roboto-Regular.ttf  Hamburgefonts  --font-size=11
//   hb:test/…/Roboto-Regular.ttf  Hamburgefonts  --font-size=11 --font-funcs=ft --ft-load-flags=0
//   ```                      --font-funcs=ft uses the FreeType build (build-ft/)
//
// The spec-like, TTX and bytes views are read from FONT.views.json beside each
// font. Those are written by tools/font-views.py (Python, with fontTools) when
// a chapter's fonts are built, and committed, so this build needs no Python.

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import MarkdownIt from "markdown-it";
import { boldTerm, canon, identifier, readNotes } from "./index-lib.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const HB_TAG = "15.1.0";
const HB_BUILD = process.env.HB_BUILD || path.join(ROOT, ".cache", "harfbuzz");
const HB_SHAPE = path.join(HB_BUILD, "build", "util", "hb-shape");
const HB_SHAPE_MSG = path.join(HB_BUILD, "build-msg", "util", "hb-shape");
const HB_VECTOR = path.join(HB_BUILD, "build", "util", "hb-vector");
const HB_INFO = path.join(HB_BUILD, "build", "util", "hb-info");
const HB_RASTER = path.join(HB_BUILD, "build", "util", "hb-raster");
// With FreeType, for `raster` blocks that ask for --font-funcs=ft (FreeType's
// outlines, which it can hint).
const HB_RASTER_FT = path.join(HB_BUILD, "build-ft", "util", "hb-raster");

// Where a font named in a block is. A plain name is in the chapter's own
// fonts folder; a name with a folder in it, like variations/var.ttf, is
// relative to fonts/; and hb:PATH is a font from HarfBuzz's own source tree,
// such as one of its test fonts.
function fontPath(name, fonts) {
  if (name.startsWith("hb:")) return path.join(HB_BUILD, name.slice(3));
  if (name.includes("/")) return path.join(ROOT, "fonts", name);
  return path.join(fonts, name);
}

// Runs one of the HarfBuzz tools, failing the build if it fails.
function runTool(exe, args, encoding = "utf8") {
  if (!fs.existsSync(exe)) throw new Error(`${exe} not found: run tools/build-harfbuzz.sh`);
  // A fixed locale: hb-shape takes the default language from it.
  const env = { ...process.env, LC_ALL: "C.UTF-8" };
  const r = spawnSync(exe, args, { encoding, maxBuffer: 64 << 20, env });
  if (r.status !== 0) throw new Error(`${path.basename(exe)} ${args.join(" ")} failed:\n${r.stderr}`);
  return r;
}

const VIEW_LABELS = [["spec", "Spec-like"], ["fea", "Feature file"], ["ttx", "TTX"],
                     ["hex", "Bytes"], ["cpp", "HarfBuzz C++"]];

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

const decode = (text) =>
  text.replace(/\\u\{([0-9A-Fa-f]{1,6})\}|\\u([0-9A-Fa-f]{4})/g,
               (_, h, h4) => String.fromCodePoint(parseInt(h || h4, 16)));

const codepoints = (text) =>
  [...text].map((c) => "U+" + c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")).join(" ");

// The text as a reader should see it: marks on a dotted circle, and
// invisible characters by name.
function shown(text) {
  const names = { "‍": "⟨ZWJ⟩", "‌": "⟨ZWNJ⟩", " ": "␣" };
  let out = "";
  for (const c of text) {
    const cp = c.codePointAt(0);
    if (c in names) out += names[c];
    else if (cp >= 0x300 && cp < 0x370) out += "◌" + c;
    else out += c;
  }
  return out;
}

function parseFields(body) {
  const fields = {};
  for (const line of body.trim().split("\n")) {
    const i = line.indexOf(":");
    const [k, v] = i < 0 ? [line, ""] : [line.slice(0, i), line.slice(i + 1)];
    fields[k.trim()] = v.trim();
  }
  return fields;
}

const reEscape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// A feature or lookup block, from its source.
function feaView(feaPath, name) {
  const src = fs.readFileSync(feaPath, "utf8");
  const n = reEscape(name);
  const m = src.match(new RegExp(`^(feature|lookup) ${n} \\{[\\s\\S]*?^\\} ${n};`, "m"));
  if (!m) throw new Error(`no block ${name} in ${feaPath}`);
  return m[0];
}

function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else yield p;
  }
}

// A struct's fields, from the HarfBuzz source, with where it is.
function cppView(hbSrc, structName) {
  for (const file of walk(hbSrc)) {
    if (!file.endsWith(".hh")) continue;
    const lines = fs.readFileSync(file, "utf8").split("\n");
    const i = lines.findIndex((l) => l.trim() === `struct ${structName}`);
    if (i < 0) continue;
    let j = i;
    while (!lines[j].includes("DEFINE_SIZE")) j++;
    const start = lines[i - 1].startsWith("template") ? i - 1 : i;
    const rel = path.relative(path.dirname(hbSrc), file);
    const url = `https://github.com/harfbuzz/harfbuzz/blob/${HB_TAG}/${rel}#L${start + 1}-L${j + 1}`;
    return { code: lines.slice(start, j + 1).join("\n") + "\n  /* … */\n};", rel, line: start + 1, url };
  }
  throw new Error(`struct ${structName} not found in ${hbSrc}`);
}

// The views tools/font-views.py wrote for a font, checked against the font.
const fontViewsCache = new Map();
function fontViews(fontPath) {
  if (fontViewsCache.has(fontPath)) return fontViewsCache.get(fontPath);
  const jsonPath = fontPath.replace(/\.[^.]+$/, ".views.json");
  const rebuild = `run ${path.relative(ROOT, path.join(path.dirname(fontPath), "build.sh"))}`;
  if (!fs.existsSync(jsonPath)) throw new Error(`${path.relative(ROOT, jsonPath)} is missing: ${rebuild}`);
  const data = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
  const digest = createHash("sha256").update(fs.readFileSync(fontPath)).digest("hex");
  if (digest !== data.sha256)
    throw new Error(`${path.relative(ROOT, jsonPath)} is out of date with its font: ${rebuild}`);
  fontViewsCache.set(fontPath, data);
  return data;
}

function blockViews(body, fonts) {
  const f = parseFields(body);
  const idx = parseInt(f.lookup, 10);
  const stored = fontViews(fontPath(f.font, fonts)).lookups[String(idx)];
  if (!stored) throw new Error(`${f.font} has no lookup ${idx}`);
  const panes = { ...stored };
  if (f.fea) {
    const [fea, name] = f.fea.split(/\s+/);
    panes.fea = feaView(path.join(fonts, fea), name);
  }
  let cppRef = "";
  if (f.cpp) {
    const { code, rel, line, url } = cppView(path.join(HB_BUILD, "src"), f.cpp);
    panes.cpp = code;
    cppRef = `<a class="src" href="${url}">${esc(rel)}:${line}</a>`;
  }
  // Print can't switch tabs: it shows the views a `print:` line names, in
  // order, or else the spec-like view.
  const printViews = (f.print || "spec").split(/\s+/).filter(Boolean);
  const tabs = [], bodies = [];
  for (const [key, label] of VIEW_LABELS) {
    if (!(key in panes)) continue;
    tabs.push(`<button type="button" role="tab" data-view="${key}">${label}</button>`);
    const extra = key === "cpp" ? cppRef : "";
    const pr = printViews.includes(key) ? " print" : "";
    bodies.push(`<div class="pane${pr}" data-view="${key}" data-label="${label}" role="tabpanel">` +
                `<pre><code>${esc(panes[key])}</code></pre>${extra}</div>`);
  }
  const caption = `${esc(f.font)}, lookup ${idx}`;
  return `<figure class="views"><div class="tabs" role="tablist" aria-label="Views of ${caption}">` +
         `${tabs.join("")}</div>${bodies.join("")}` +
         `<figcaption>${caption}</figcaption></figure>`;
}

// Runs hb-shape. Traces go to stderr, so for the message build both
// streams are kept, stderr first.
function runShape(font, text, opts, msg = false) {
  const r = runTool(msg ? HB_SHAPE_MSG : HB_SHAPE, [font, text, ...opts]);
  return (msg ? r.stderr + r.stdout : r.stdout).trim();
}

function blockShape(body, fonts) {
  const rows = [];
  for (const line of body.trim().split("\n")) {
    const parts = line.trim().split(/\s{2,}/);
    const [font, rawText, ...opts] = parts;
    const text = decode(rawText);
    const out = runShape(fontPath(font, fonts), text, opts);
    rows.push("<tr>" +
      `<td class="font">${esc(font)}</td>` +
      `<td class="in"><span class="txt">${esc(shown(text))}</span>` +
      `<span class="cps">${codepoints(text)}</span></td>` +
      `<td class="opt">${esc(opts.join(" "))}</td>` +
      `<td class="out"><code>${esc(out)}</code></td>` +
      "</tr>");
  }
  return '<div class="shape"><table><thead><tr><th>Font</th><th>Text</th>' +
         "<th>Options</th><th>hb-shape output</th></tr></thead><tbody>" +
         rows.join("") + "</tbody></table></div>";
}

// hb-raster's PNG output, one image per line, enlarged so its pixels show.
// Lines are like a shape block's: font, text and hb-raster options,
// separated by two or more spaces. A first line `zoom: N` sets the
// enlargement (default 8). The margin is 2 pixels unless an option sets it.
function blockRaster(body, fonts) {
  let lines = body.trim().split("\n");
  let zoom = 8;
  if (/^zoom:/.test(lines[0])) zoom = Number(lines.shift().slice(5));
  const rows = lines.map((line) => {
    const [font, rawText, ...opts] = line.trim().split(/\s{2,}/);
    const text = decode(rawText);
    const args = opts.flatMap((o) => o.split(/\s+/));
    if (!args.some((a) => a.startsWith("--margin"))) args.push("--margin=2");
    const exe = args.includes("--font-funcs=ft") ? HB_RASTER_FT : HB_RASTER;
    const png = runTool(exe, [fontPath(font, fonts), text, "--output-format=png", ...args], "buffer").stdout;
    const [w, h] = [png.readUInt32BE(16), png.readUInt32BE(20)];
    const shownFont = font.startsWith("hb:") ? path.basename(font) : font;
    return `<figure class="raster"><img src="data:image/png;base64,${png.toString("base64")}" ` +
           `width="${w * zoom}" height="${h * zoom}" alt="${esc(shown(text))}, rendered by hb-raster">` +
           `<figcaption><code>hb-raster ${esc(shownFont)} ${esc(shown(text))} ${esc(opts.join(" "))}</code>` +
           ` (${w} × ${h} pixels, shown ${zoom} times larger)</figcaption></figure>`;
  });
  return `<div class="rasters">${rows.join("")}</div>`;
}

function blockTrace(body, fonts) {
  const f = parseFields(body);
  const text = decode(f.text);
  const opts = (f.options || "").split(/\s+/).filter(Boolean);
  const out = runShape(fontPath(f.font, fonts), text, [...opts, "--trace"], true);
  let lines = out.split("\n").filter((l) => l.startsWith("trace: ")).map((l) => l.slice(7));
  const find = (needle) => {
    const i = lines.findIndex((l) => l.includes(needle));
    if (i < 0) throw new Error(`no trace line contains "${needle}"`);
    return i;
  };
  if (f.from) lines = lines.slice(find(f.from));
  if (f.to) lines = lines.slice(0, find(f.to) + 1);
  if (f.skipped !== "yes") {
    const drop = new Set();
    lines.forEach((l, i) => { if (l.includes("skipped lookup")) [i - 1, i, i + 1].forEach((d) => drop.add(d)); });
    lines = lines.filter((_, i) => !drop.has(i));
  }
  const rows = lines.map((l) => {
    const i = l.indexOf("\tbuffer: ");
    const [what, buf] = i < 0 ? [l, ""] : [l.slice(0, i), l.slice(i + 9)];
    return `<tr><td class="what">${esc(what)}</td>` +
           `<td class="buf"><code>${esc(buf)}</code></td></tr>`;
  });
  const head = `<div class="trace-head"><code>hb-shape ${esc(f.font)} ` +
               `"${esc(shown(text))}" ${esc(opts.join(" "))} --trace</code></div>`;
  return `<div class="trace">${head}<table><tbody>${rows.join("")}</tbody></table></div>`;
}

// ```draw: outlines drawn by hb-vector, with hb-shape's output beneath.
//
//   font: variations/var.ttf
//   text: IHV
//   variations: wdth=100        (optional: settings for every frame)
//   slider: wght 100 900 25     (a slider over one axis: tag, from, to, step)
//   start: 400                  (optional: where the slider starts)
//   print: 100 400 900          (optional: the frames print shows in a row;
//                               default: the first, the start and the last)
//   at: wght=100; wght=400      (or instead of a slider: frames side by side)
//   options: --direction=ttb    (optional: more hb-vector and hb-shape options)
//   vector-options: --font-palette=1   (optional: options for hb-vector only)
//
// Every frame is drawn when the book is built, so what the slider shows is
// always HarfBuzz's own output at that position.
let drawCount = 0;

// Source citations link to the HarfBuzz repository at the book's tag: a code
// span that names a file in the checkout (`src/hb-ot-map.cc`, or as prose
// cites it, `hb-ot-map.cc:389`, `OT/Layout/GPOS/GPOS.hh:126–151`) becomes a
// link to that file, and to the line or lines if it gives them. Paths without
// a folder are looked for in src/ and then util/. A path that isn't in the
// checkout stays plain text, so a slip can't make a broken link.
const SOURCE_DIRS = ["", "src/", "util/"];
const sourceFile = new Map();
function resolveSource(p) {
  if (sourceFile.has(p)) return sourceFile.get(p);
  let found = null;
  for (const d of SOURCE_DIRS) {
    const rel = d + p;
    if (fs.existsSync(path.join(HB_BUILD, rel)) && fs.statSync(path.join(HB_BUILD, rel)).isFile()) { found = rel; break; }
  }
  // A bare file name, as chapters write after giving the full path once
  // (`COLR.hh`), is linked if exactly one file under src/ has that name.
  if (!found && !p.includes("/")) {
    const hits = sourceIndex().get(p) || [];
    if (hits.length === 1) found = hits[0];
  }
  sourceFile.set(p, found);
  return found;
}
let sourceIdx = null;
function sourceIndex() {
  if (sourceIdx) return sourceIdx;
  sourceIdx = new Map();
  const walk = (dir) => {
    for (const e of fs.readdirSync(path.join(HB_BUILD, dir), { withFileTypes: true })) {
      const rel = path.posix.join(dir, e.name);
      if (e.isDirectory()) walk(rel);
      else if (!sourceIdx.has(e.name)) sourceIdx.set(e.name, [rel]); else sourceIdx.get(e.name).push(rel);
    }
  };
  walk("src");
  return sourceIdx;
}
function linkSources(html) {
  // A wildcard or brace list (`src/hb-ot-shaper-*.cc`, `src/hb-paint-extents.{hh,cc}`)
  // names several files: it links to the folder they are in.
  html = html.replace(/(<a\b[^>]*>)?<code>((?:src|util|test|docs)(?:\/[\w.+-]+)*\/)?([\w.+-]*[*{][\w.,*{}+-]*)<\/code>/g,
    (m, inLink, dir, name) => {
      if (inLink) return m;
      const folder = (dir || "").replace(/\/$/, "");
      if (!folder || !fs.existsSync(path.join(HB_BUILD, folder))) return m;
      return `<a class="src" href="https://github.com/harfbuzz/harfbuzz/tree/${HB_TAG}/${folder}">${m}</a>`;
    });
  return html.replace(/(<a\b[^>]*>)?<code>([\w./+-]+\.(?:hh|cc|h|c|py|rs|rl|txt|md|build|tests))(?::(\d+)(?:[–-](\d+))?)?<\/code>/g,
    (m, inLink, file, l1, l2) => {
      if (inLink) return m;
      const rel = resolveSource(file);
      if (!rel) return m;
      const anchor = l1 ? `#L${l1}` + (l2 ? `-L${l2}` : "") : "";
      return `<a class="src" href="https://github.com/harfbuzz/harfbuzz/blob/${HB_TAG}/${rel}${anchor}">${m}</a>`;
    });
}

function blockDraw(body, fonts) {
  const f = parseFields(body);
  const font = fontPath(f.font, fonts);
  const text = decode(f.text);
  const base = f.variations ? f.variations.split(",").map((s) => s.trim()) : [];
  const extra = f.options ? f.options.trim().split(/\s+/) : [];
  const vectorOnly = f["vector-options"] ? f["vector-options"].trim().split(/\s+/) : [];
  let settings, slider = null;
  if (f.slider) {
    const [tag, from, to, step] = f.slider.split(/\s+/);
    const [lo, hi, st] = [from, to, step].map(Number);
    const values = [];
    for (let v = lo; v <= hi + 1e-9; v += st) values.push(+v.toFixed(4));
    const start = f.start !== undefined ? Number(f.start) : values[0];
    slider = { tag, lo, hi, st, start };
    settings = values.map((v) => ({ label: `${tag}=${v}`, value: v, vars: [...base, `${tag}=${v}`] }));
  } else {
    settings = (f.at || "").split(";").map((s) => s.trim()).filter(Boolean)
      .map((s) => ({ label: s, vars: [...base, ...s.split(",").map((x) => x.trim())] }));
    if (!settings.length) settings = [{ label: base.join(",") || "default", vars: base }];
  }
  const frames = settings.map((s) => {
    const opts = [...(s.vars.length ? [`--variations=${s.vars.join(",")}`] : []), ...extra];
    const svg = runTool(HB_VECTOR, [font, text, ...opts, ...vectorOnly, "--background=none", "--margin=40", "-o", "/dev/stdout"]).stdout;
    const shaped = runShape(font, text, opts);
    const vb = svg.match(/viewBox="([^"]+)"/)[1].split(/\s+/).map(Number);
    // Every frame is inlined into the page, and hb-vector numbers its ids
    // (gradients, clips, reused paths) from zero each time, so give each
    // frame's ids a prefix of its own, or one drawing would use another's.
    const pre = `d${++drawCount}-`;
    const inner = svg.replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "")
      .replace(/fill="#000(000)?"/g, 'fill="currentColor"')
      .replace(/\bid="([^"]+)"/g, (_, id) => `id="${pre}${id}"`)
      .replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${pre}${id})`)
      .replace(/(\b(?:xlink:)?href)="#([^"]+)"/g, (_, attr, id) => `${attr}="#${pre}${id}"`);
    return { ...s, vb, inner, shaped };
  });
  // One viewBox for every frame, so the glyphs don't jump as the slider moves.
  const x0 = Math.min(...frames.map((fr) => fr.vb[0])), y0 = Math.min(...frames.map((fr) => fr.vb[1]));
  const x1 = Math.max(...frames.map((fr) => fr.vb[0] + fr.vb[2])), y1 = Math.max(...frames.map((fr) => fr.vb[1] + fr.vb[3]));
  const viewBox = `${x0} ${y0} ${x1 - x0} ${y1 - y0}`;
  const frameHtml = (fr, hidden) =>
    `<div class="frame${fr.print ? " print" : ""}"${slider ? ` data-value="${fr.value}"` : ""}${hidden ? " hidden" : ""}>` +
    `<svg viewBox="${viewBox}" role="img" aria-label="${esc(shown(text))} at ${esc(fr.label)}">${fr.inner}</svg>` +
    `<div class="frame-label">${esc(fr.label)}</div>` +
    `<code class="frame-shape">${esc(fr.shaped)}</code></div>`;
  const cmd = `hb-vector ${esc(f.font)} "${esc(shown(text))}"` + ([...extra, ...vectorOnly].length ? ` ${esc([...extra, ...vectorOnly].join(" "))}` : "") +
    (base.length || slider ? ` --variations=${esc([...base, slider ? `${slider.tag}=…` : ""].filter(Boolean).join(","))}` : "");
  if (slider) {
    const nearest = (v) => frames.reduce((a, b) => Math.abs(b.value - v) < Math.abs(a.value - v) ? b : a);
    const startFrame = nearest(slider.start);
    // Print can't move a slider: it shows a row of the frames nearest the
    // values a `print:` line names, or else the first, the starting and the last.
    const printAt = f.print ? f.print.split(/\s+/).map(Number) : [slider.lo, slider.start, slider.hi];
    for (const v of printAt) nearest(v).print = true;
    return `<figure class="draw slider">` +
      `<div class="frames">${frames.map((fr) => frameHtml(fr, fr !== startFrame)).join("")}</div>` +
      `<label class="control"><span>${esc(slider.tag)}</span>` +
      `<input type="range" min="${slider.lo}" max="${slider.hi}" step="${slider.st}" value="${startFrame.value}">` +
      `<output>${startFrame.value}</output></label>` +
      `<figcaption><code>${cmd}</code>, drawn at every ${slider.st} from ${slider.lo} to ${slider.hi}</figcaption></figure>`;
  }
  return `<figure class="draw row"><div class="frames">${frames.map((fr) => frameHtml(fr, false)).join("")}</div>` +
    `<figcaption><code>${cmd}</code></figcaption></figure>`;
}

// ```info: one hb-info run per line: font, then its options, separated by
// two or more spaces.
function blockInfo(body, fonts) {
  const rows = body.trim().split("\n").map((line) => {
    const [font, ...opts] = line.trim().split(/\s{2,}/);
    const out = runTool(HB_INFO, [...opts.flatMap((o) => o.split(/\s+/)), fontPath(font, fonts)]).stdout.trim();
    return `<tr><td class="font">${esc(font)}</td><td class="opt">${esc(opts.join(" "))}</td>` +
           `<td class="out"><pre><code>${esc(out)}</code></pre></td></tr>`;
  });
  return '<div class="shape info"><table><thead><tr><th>Font</th><th>Options</th>' +
         "<th>hb-info output</th></tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
}

// ```table: a table's TTX dump, from FONT.views.json.
//
//   font: variations/var.ttf
//   table: gvar
//   glyph: V          (optional: for gvar, only this glyph's variations)
function blockTable(body, fonts) {
  const f = parseFields(body);
  const tables = fontViews(fontPath(f.font, fonts)).tables || {};
  let ttx = tables[f.table];
  if (ttx === undefined) throw new Error(`${f.font} has no ${f.table} in its views: is it in TABLES in tools/font-views.py?`);
  if (f.glyph) {
    const m = ttx.match(new RegExp(`( *)<glyphVariations glyph="${reEscape(f.glyph)}">[\\s\\S]*?</glyphVariations>`));
    if (!m) throw new Error(`${f.font} has no ${f.table} data for ${f.glyph}`);
    ttx = m[0].split("\n").map((l) => l.slice(Math.min(m[1].length, l.length - l.trimStart().length))).join("\n");
  }
  const what = f.glyph ? `${f.table}, glyph ${f.glyph}` : f.table;
  return `<figure class="views ttx"><pre><code>${esc(ttx)}</code></pre>` +
         `<figcaption>${esc(f.font)}: ${esc(what)} (TTX)</figcaption></figure>`;
}

const BLOCKS = { views: blockViews, shape: blockShape, trace: blockTrace,
                 draw: blockDraw, info: blockInfo, table: blockTable, raster: blockRaster };

// Heading ids, made the way Python-Markdown's toc extension made them, so
// links to sections keep working: "The mask" → "the-mask".
function slugify(text) {
  return text.normalize("NFKD").replace(/[^\x00-\x7f]/g, "")
    .replace(/[^\w\s-]/g, "").trim().toLowerCase().replace(/[-\s]+/g, "-");
}

function makeRenderer(fonts, index) {
  const md = new MarkdownIt({ html: true });
  const fence = md.renderer.rules.fence;
  md.renderer.rules.fence = (tokens, i, options, env, self) => {
    const kind = tokens[i].info.trim();
    if (kind in BLOCKS) return BLOCKS[kind](tokens[i].content, fonts) + "\n";
    return fence(tokens, i, options, env, self);
  };
  md.core.ruler.push("heading_ids", (state) => {
    const used = new Set();
    state.tokens.forEach((t, i) => {
      if (t.type !== "heading_open") return;
      const text = state.tokens[i + 1].children.filter((c) => c.type === "text" || c.type === "code_inline")
        .map((c) => c.content).join("");
      let id = slugify(text), n = 1;
      while (used.has(id)) id = `${slugify(text)}_${n++}`;
      used.add(id);
      t.attrSet("id", id);
    });
  });
  if (index) md.core.ruler.push("index_marks", (state) => index.mark(state.tokens));
  return md;
}

// The index. Before any page is rendered, terms() gathers the terms from
// every chapter's prose, as tools/index-terms.mjs does. While a chapter is
// rendered, mark() finds each paragraph, heading, list item or table cell
// that mentions a term, gives it an id if it hasn't one, and records it.
// page() then writes either index as HTML, one link per place it cites: the
// chapter and section number on screen, a page number in print
// (tools/build-pdf.mjs fills those in).
// “variable components” → “components, variable”, for a phrase of two or
// three words; not one with a preposition or article (“pixels per em”), or a
// name ending in a capitalised word (“Universal Shaping Engine”, “SARA AM”).
const NOT_INVERTED = new Set(["per", "of", "to", "the", "a", "an", "and", "or", "in", "for", "on", "at", "by", "with", "from", "as", "not", "no", "vs"]);
function inverted(display) {
  const words = display.split(" ");
  if (words.length < 2 || words.length > 3) return null;
  if (words.some((w) => NOT_INVERTED.has(w.toLowerCase()) || /[\d/`]/.test(w))) return null;
  const last = words[words.length - 1];
  if (/^[A-Z]/.test(last)) return null;
  return `${last}, ${words.slice(0, -1).join(" ")}`;
}

class Index {
  constructor(pages) {
    const { notTerms, mains } = readNotes(ROOT);
    this.mains = mains;
    this.entries = new Map();          // key -> { key, display, code, which, locs: [] }
    this.variant = new Map();          // variant key -> main key
    for (const [k, e] of mains) for (const v of e.variants) this.variant.set(canon(v), k);
    this.indexed = pages.filter((p) => !p.planned && (p.section.kind === "part" || p.section.kind === "appendices"));
    const add = (display, code, which) => {
      let key = canon(display);
      key = this.variant.get(key) || key;
      if (!this.entries.has(key)) this.entries.set(key, { key, display, code, which, locs: [] });
      return key;
    };
    for (const p of this.indexed) {
      const text = p.src.replace(/^```[\s\S]*?^```/gm, "");
      for (const m of text.matchAll(/\*\*([^*\n]+?)\*\*/g)) {
        const t = boldTerm(m[1]);
        if (!t || notTerms.has(canon(t))) continue;
        const one = t.match(/^`([^`]+)`$/);
        const id = one && identifier(one[1]);
        if (id) add(id[1], true, id[0] === "tag" ? "general" : "code");
        else if (!t.includes("`")) add(t, false, "general");
      }
      for (const m of text.matchAll(/`([^`\n]+)`/g)) {
        const id = identifier(m[1]);
        if (id) add(id[1], true, id[0] === "tag" ? "general" : "code");
      }
    }
    // Plurals file under the singular.
    for (const key of [...this.entries.keys()]) {
      const single = key.replace(/(?:e?s)$/, "");
      if (single !== key && this.entries.has(single) && !this.entries.get(key).code) {
        this.variant.set(key, single); this.entries.delete(key);
      }
    }
    // Words found in running text: concepts in any case, and tags only as
    // written when they are capitals (GSUB, OS/2), since liga or mark in
    // prose is usually the plain word.
    const words = [...this.entries.values()].filter((e) => !e.code).map((e) => e.key)
      .concat([...this.variant.keys()]);
    const caps = [...this.entries.values()].filter((e) => e.code && e.which === "general" && /^[A-Z0-9/ ]+$/.test(e.display)).map((e) => e.display);
    const alt = (xs) => xs.sort((a, b) => b.length - a.length).map(reEscape).join("|");
    this.wordRe = new RegExp(`(?<![\\w-])(${alt(words)})(?:e?s)?(?![\\w-])`, "gi");
    this.capsRe = caps.length ? new RegExp(`(?<![\\w/-])(${alt(caps)})(?![\\w/-])`, "g") : null;
    // Each concept as it is most often written mid-sentence, so “point size”
    // isn't filed as “Point size” for having been defined at a sentence's
    // start; the notes' own spelling wins.
    const forms = new Map();
    for (const p of this.indexed) {
      const text = p.src.replace(/^```[\s\S]*?^```/gm, "").replace(/`[^`\n]*`/g, " ");
      for (const m of text.matchAll(this.wordRe)) {
        const before = text.slice(Math.max(0, m.index - 3), m.index);
        if (/(^|[.!?:]\s+|\n\s*[*|]?\s*|\*\*)$/.test(before) || m.index === 0) continue;
        const key = this.variant.get(canon(m[1])) || canon(m[1]);
        if (!forms.has(key)) forms.set(key, new Map());
        const f = forms.get(key); f.set(m[1], (f.get(m[1]) || 0) + 1);
      }
    }
    for (const e of this.entries.values()) {
      if (e.code) continue;
      const main = this.mains.get(e.key);
      if (main) { e.display = main.display.replace(/`/g, ""); continue; }
      const f = forms.get(e.key);
      if (f) e.display = [...f].sort((a, b) => b[1] - a[1])[0][0];
    }
    this.page = null;
  }

  // Which page mark() is reading, or null for one that isn't indexed.
  begin(p) { this.page = this.indexed.includes(p) ? p : null; this.n = 0; }

  lookup(text, code) {
    let key = canon(text);
    key = this.variant.get(key) || key;
    const e = this.entries.get(key);
    return e && e.code === code ? key : null;
  }

  mark(tokens) {
    const p = this.page;
    if (!p) return;
    let h2 = 0, h2title = "", skip = false;
    const SKIP = new Set(["Where to read the source", "In short"]);
    for (let i = 1; i < tokens.length; i++) {
      const t = tokens[i];
      if (t.type !== "inline") continue;
      const block = tokens[i - 1];
      if (!/^(paragraph|heading|td|th)_open$/.test(block.type)) continue;
      const heading = block.type === "heading_open";
      if (heading && block.tag === "h1") { h2 = 0; h2title = ""; }
      if (heading && block.tag === "h2") {
        h2++; h2title = t.content.replace(/`/g, ""); skip = SKIP.has(h2title);
      }
      if (skip) continue;
      const found = new Map();                       // key -> definition?
      const note = (key, def) => key && found.set(key, found.get(key) || def);
      let strong = 0, run = "";
      for (const c of t.children || []) {
        if (c.type === "strong_open") { strong++; run = ""; continue; }
        if (c.type === "strong_close") {
          strong--;
          const b = boldTerm(run);
          if (b) {
            const one = b.match(/^`([^`]+)`$/), id = one && identifier(one[1]);
            note(id ? this.lookup(id[1], true) : this.lookup(b, false), true);
          }
          continue;
        }
        if (c.type === "code_inline") {
          if (strong) run += "`" + c.content + "`";
          const id = identifier(c.content);
          if (id) note(this.lookup(id[1], true), false);
        } else if (c.type === "text") {
          if (strong) run += c.content;
          for (const m of c.content.matchAll(this.wordRe)) note(this.lookup(m[1], false), false);
          if (this.capsRe) for (const m of c.content.matchAll(this.capsRe)) note(this.lookup(m[1], true), false);
          // In a chapter's title, a tag written plainly is the tag (“Legacy kern”).
          if (block.tag === "h1") for (const w of c.content.split(/[^\w/]+/)) {
            const k = this.lookup(w, true);
            if (k && this.entries.get(k).which === "general") note(k, false);
          }
        }
      }
      if (!found.size) continue;
      // A paragraph in a tight list isn't printed, so its list item takes the id.
      let holder = block;
      if (block.hidden) for (let j = i - 2; j >= 0; j--)
        if (tokens[j].type === "list_item_open" && tokens[j].level === block.level - 1) { holder = tokens[j]; break; }
      let id = holder.attrGet("id");
      if (!id) { id = `ix-${++this.n}`; holder.attrSet("id", id); }
      for (const [key, def] of found)
        this.entries.get(key).locs.push({ p, id, h2, h2title, def, heading, title: block.tag === "h1",
                                          order: this.order = (this.order || 0) + 1 });
    }
  }

  // The places an entry cites: one per section; the chapter named for it, its
  // definition and the headings that name it first, then the sections that
  // say most about it; at most twelve, or six for a term in most chapters
  // (glyph, GSUB), which would otherwise cite nearly every section.
  places(e) {
    const groups = new Map();
    for (const l of e.locs) {
      const k = `${l.p.slug}#${l.h2}`;
      if (!groups.has(k)) groups.set(k, { locs: [], first: l.order });
      groups.get(k).locs.push(l);
    }
    const common = new Set(e.locs.map((l) => l.p.slug)).size > 0.4 * this.indexed.length;
    let gs = [...groups.values()].map((g) => ({
      ...g, def: g.locs.some((l) => l.def), heading: g.locs.some((l) => l.heading), title: g.locs.some((l) => l.title),
      loc: g.locs.find((l) => l.def) || g.locs.find((l) => l.title) || g.locs.find((l) => l.heading) || g.locs[0] }));
    const rank = (g) => (g.title ? 4e6 : 0) + (g.def ? 2e6 : 0) + (g.heading ? 1e6 : 0) + g.locs.length * 1000 - g.first / 1e6;
    const keep = gs.sort((a, b) => rank(b) - rank(a)).slice(0, common ? 6 : 12).sort((a, b) => a.first - b.first);
    return keep.map((g) => g.loc);
  }

  inline(md) { return (this.md ||= new MarkdownIt()).renderInline(md); }

  html(which) {
    const sortKey = (e) => (which === "code" ? e.display.replace(/^_*(?:hb[_-]|HB_)/, "") : e.display.replace(/^_+/, ""))
      .replace(/`/g, "");
    const rows = [];
    const label = (e) => (e.code ? `<code>${esc(e.display)}</code>` : esc(e.display));
    for (const e of this.entries.values()) {
      if (e.which !== which || !e.locs.length) continue;
      const links = this.places(e).map((l) => {
        const title = `${l.p.number} ${l.p.title}${l.h2title ? ` › ${l.h2title}` : ""}`;
        return `<a href="${l.p.slug}.html#${l.id}" class="loc${l.def ? " def" : ""}" title="${esc(title)}">` +
               `${l.p.number}${l.h2 ? "." + l.h2 : ""}</a>`;
      }).join(", ");
      const main = this.mains.get(e.key);
      const also = main && main.seeAlso.length
        ? `; <i>see also</i> ${main.seeAlso.map((x) => this.inline(x.replace(/\s*\(“[^)]*\)$/, ""))).join(", ")}` : "";
      rows.push({ key: sortKey(e), html: `<li><span class="term">${label(e)}</span> ${links}${also}</li>` });
      // A phrase is also filed under its last word, the noun, with the same
      // places: “variable components” as “components, variable”.
      const inv = !e.code && inverted(e.display);
      if (inv && !this.entries.has(canon(inv)))
        rows.push({ key: inv, html: `<li><span class="term">${esc(inv)}</span> ${links}</li>` });
    }
    // Other names, pointing at the main entry.
    if (which === "general") for (const [k, m] of this.mains) {
      const target = this.entries.get(k);
      if (!target || !target.locs.length) continue;
      for (const a of m.aliases) {
        if (a.includes("`") || this.entries.has(canon(a))) continue;
        for (const name of [a, inverted(a)])
          if (name && !this.entries.has(canon(name)))
            rows.push({ key: name, html: `<li><span class="term">${esc(name)}</span>, <i>see</i> ${label(target)}</li>` });
      }
    }
    rows.sort((a, b) => a.key.localeCompare(b.key, "en", { sensitivity: "base" }));
    const letters = new Map();
    for (const r of rows) {
      const L = /^[a-z]/i.test(r.key) ? r.key[0].toUpperCase() : "#";
      if (!letters.has(L)) letters.set(L, []);
      letters.get(L).push(r.html);
    }
    return `<div class="index index-${which}">` + [...letters].map(([L, items]) =>
      `<section class="index-letter"><h2 id="index-${L === "#" ? "symbols" : L.toLowerCase()}">${L}</h2>` +
      `<ul>${items.join("")}</ul></section>`).join("") + "</div>";
  }
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
               "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"];

// book/toc.txt, read into pages (in reading order) and sections (for the
// contents). See the comment at the top of toc.txt for its format.
function readToc() {
  const lines = fs.readFileSync(path.join(ROOT, "book", "toc.txt"), "utf8").split("\n")
    .map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  const pages = [], sections = [];
  let section = null, chapter = 0, parts = 0, appendix = 0;
  for (const line of lines) {
    const m = line.match(/^\[(front|part|appendices|end)\]\s*(.*)$/);
    if (m) {
      const kind = m[1];
      const label = kind === "part" ? `Part ${ROMAN[parts++]}` : kind === "appendices" ? "Appendices" : "";
      section = { kind, label, title: m[2], pages: [] };
      sections.push(section);
      continue;
    }
    if (!section) throw new Error(`toc.txt: “${line}” comes before any [section]`);
    let page;
    if (line.startsWith("?")) {
      const [title, summary = ""] = line.slice(1).split("|").map((s) => s.trim());
      page = { slug: slugify(title), title, summary, planned: true };
    } else {
      const src = fs.readFileSync(path.join(ROOT, "book", line), "utf8");
      const title = src.match(/^# (.+)$/m)[1];
      page = { slug: path.basename(line, path.extname(line)), title, src, planned: false };
    }
    if (section.kind === "part") page.number = String(++chapter);
    if (section.kind === "appendices") page.number = String.fromCharCode(65 + appendix++);
    page.eyebrow = section.kind === "part" ? `${section.label} · ${section.title}`
                 : section.kind === "appendices" ? `Appendix ${page.number}` : "";
    page.section = section;
    if (pages.some((p) => p.slug === page.slug)) throw new Error(`toc.txt: two pages are named ${page.slug}`);
    pages.push(page);
    section.pages.push(page);
  }
  return { pages, sections };
}

// The contents, as nested lists. With summaries, it's the full contents for
// the title page; without, it's the short one in every page's header.
function contents(sections, md, withSummaries) {
  const item = (p) => {
    const num = p.number ? `<span class="num">${p.number}</span> ` : "";
    const cls = p.planned ? ' class="planned"' : "";
    const summary = withSummaries && p.summary ? `<span class="summary">${md.renderInline(p.summary)}</span>` : "";
    return `<li${cls}>${num}<a href="${p.slug}.html">${esc(p.title)}</a>${summary}</li>`;
  };
  return sections.map((s) => {
    const head = s.label ? `<p class="toc-head">${esc(s.label)}${s.title ? `: ${esc(s.title)}` : ""}</p>` : "";
    return `<div class="toc-section">${head}<ol>${s.pages.map(item).join("")}</ol></div>`;
  }).join("");
}

// The page for a chapter that's planned but not written yet.
function plannedSource(p) {
  return `# ${p.title}\n\n${p.summary}\n\n<p class="planned-note">This ${p.section.kind === "appendices" ? "appendix" : "chapter"} ` +
         "isn’t written yet. It’s planned in the book’s outline, <code>notes/outline.md</code>.</p>\n";
}

function main(outDir, fragment) {
  fs.mkdirSync(outDir, { recursive: true });
  const template = fs.readFileSync(path.join(ROOT, "tools", "page.html"), "utf8");
  const meta = JSON.parse(fs.readFileSync(path.join(ROOT, "book", "book.json"), "utf8"));
  const { pages, sections } = readToc();
  const plain = new MarkdownIt({ html: true });
  const nav = contents(sections, plain, false);
  const fullContents = contents(sections, plain, true);
  const index = new Index(pages);
  pages.forEach((p, n) => {
    const { slug, title } = p;
    const src = p.planned ? plannedSource(p) : p.src;
    const fonts = path.join(ROOT, "fonts", slug);
    index.begin(p);
    let body = makeRenderer(fonts, index).render(src.replaceAll("{{hb}}", HB_TAG))
      .replace("<p>{{contents}}</p>", () => `<nav class="toc full">${fullContents}</nav>`)
      .replace("<p>{{index:general}}</p>", () => index.html("general"))
      .replace("<p>{{index:code}}</p>", () => index.html("code"));
    body = linkSources(body);
    // A chapter is headed “15. Title”, under “Part IV · Name”.
    if (p.section.kind === "part") body = body.replace(/(<h1[^>]*>)/, `$1${p.number}. `);
    if (p.eyebrow) body = `<p class="eyebrow">${esc(p.eyebrow)}</p>\n` + body;
    const prev = n ? pages[n - 1] : null, next = pages[n + 1];
    const prevLink = prev ? `<a rel="prev" href="${prev.slug}.html">← ${esc(prev.title)}</a>` : "<span></span>";
    const nextLink = next ? `<a rel="next" href="${next.slug}.html">${esc(next.title)} →</a>` : "<span></span>";
    // Functions as replacements, so a "$" in the content is never special.
    let page = template.replaceAll("{{title}}", () => esc(title))
      .replaceAll("{{book}}", () => esc(meta.title))
      .replaceAll("{{subtitle}}", () => esc(meta.subtitle))
      .replaceAll("{{hb_version}}", HB_TAG)
      .replaceAll("{{nav}}", () => nav)
      .replaceAll("{{prev}}", () => prevLink).replaceAll("{{next}}", () => nextLink)
      .replaceAll("{{body}}", () => body);
    if (!fragment) {
      page = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' +
             page.replace('<div class="page">', '</head>\n<body>\n<div class="page">') +
             "\n</body>\n</html>\n";
    }
    fs.writeFileSync(path.join(outDir, `${slug}.html`), page);
    console.log(`${slug}.html`);
  });
  // The site's front door (what https://…/how-harfbuzz-works/ serves): the
  // title page again, as the links in the header lead there.
  if (!fragment) {
    fs.copyFileSync(path.join(outDir, "title.html"), path.join(outDir, "index.html"));
    console.log("index.html (the title page)");
  }
}

const args = process.argv.slice(2);
const dirs = args.filter((a) => !a.startsWith("--"));
main(dirs[0] || path.join(ROOT, "site"), args.includes("--fragment"));
