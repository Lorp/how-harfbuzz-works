// Builds the book as one PDF, 6 × 9 inches, with book/cover.png as its cover
// (and book/cover-back.png, if there is one, as its last page), then
// the front matter (blanks, half-title, title page, imprint).
//
// usage: node tools/build-pdf.mjs [OUT.pdf]   (or: npm run pdf)
//        default: site/print/how-harfbuzz-works.pdf
//        Beside it, OUT.pages.txt gives its page numbering, one line where each
//        numbering starts: “PDF-page first-number [none|roman]” (arabic if left out).
//
// It builds the site (tools/build-site.mjs) into a scratch folder, joins the
// written pages in book order into one HTML document with print styles, and
// prints that with headless Chrome. Planned pages, which aren't written yet,
// are left out; links to them become plain text. Interactive figures print in
// one state: a lookup's default view, a slider's starting frame.
//
// Needs Google Chrome (or set CHROME to another Chromium-based browser), and
// the network, for the web fonts the pages use.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { RECORD, sourceHash } from "./source-hash.mjs";
import { bookVersion } from "./version.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const OUT = path.resolve(process.argv[2] || path.join(ROOT, "site", "print", "how-harfbuzz-works.pdf"));
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const work = fs.mkdtempSync(path.join(os.tmpdir(), "hb-book-pdf-"));
const siteDir = path.join(work, "site");

// The printed contents lists each chapter's sections too (TOC_DEPTH 2), with
// the page each one starts on.
const built = spawnSync(process.execPath, [path.join(ROOT, "tools", "build-site.mjs"), siteDir],
  { stdio: ["ignore", "ignore", "inherit"], env: { ...process.env, TOC_DEPTH: process.env.TOC_DEPTH || "2" } });
if (built.status !== 0) process.exit(built.status || 1);

// Pages in book order, with whether each is written. Same slugs as the site.
const slugify = (text) => text.normalize("NFKD").replace(/[^\x00-\x7f]/g, "")
  .replace(/[^\w\s-]/g, "").trim().toLowerCase().replace(/[-\s]+/g, "-");
// Chapters are numbered through the book, and each part's first page also
// carries the part (number and name), for its part title page.
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"];
const pages = [];
let part = null, parts = 0, chapter = 0, partStarts = false;
for (const raw of fs.readFileSync(path.join(ROOT, "book", "toc.txt"), "utf8").split("\n")) {
  const l = raw.trim();
  if (!l || l.startsWith("#")) continue;
  const sec = l.match(/^\[(\w+)\]\s*(.*)$/);
  if (sec) {
    part = sec[1] === "part" ? { label: `Part ${ROMAN[parts++]}`, name: sec[2] } : null;
    partStarts = !!part;
    continue;
  }
  const page = l.startsWith("?")
    ? { slug: slugify(l.slice(1).split("|")[0]), written: false }
    : { slug: path.basename(l, path.extname(l)), written: true };
  if (part) {
    page.part = part;
    page.number = ++chapter;
    if (partStarts && page.written) { page.startsPart = true; partStarts = false; }
  }
  pages.push(page);
}
const written = new Set(pages.filter((p) => p.written).map((p) => p.slug));

const read = (slug) => fs.readFileSync(path.join(siteDir, slug + ".html"), "utf8");
const first = read(pages.find((p) => p.written).slug);
const head = first.match(/<link rel="preconnect"[\s\S]*?<\/style>/)[0];

// One page's content, with its ids and links made unique within the book.
function content(slug) {
  let html = read(slug).match(/<main class="flow">([\s\S]*?)<\/main>/)[1];
  // Chapters come headed “15. Title”, under “Part IV · Name”, from the site.
  const page = pages.find((p) => p.slug === slug);
  // Long option strings (feature lists) may break after a comma.
  html = html.replace(/(<td class="opt">)([^<]*)/g, (_, td, opts) => td + opts.replace(/,/g, ",<wbr>"));
  html = html.replace(/\sid="([^"]+)"/g, (_, id) => ` id="${slug}--${id}"`);
  html = html.replace(/<a href="([a-z0-9_-]+)\.html(?:#([^"]*))?"([^>]*)>([\s\S]*?)<\/a>/g, (m, target, frag, rest, text) =>
    written.has(target)
      ? `<a href="#${frag ? `${target}--${frag}` : target}"${rest}>${text}</a>`
      : `<span class="unwritten">${text}</span>`);
  html = html.replace(/<a href="#([^"]+)"/g, (m, frag) =>
    frag.includes("--") || written.has(frag) ? m : `<a href="#${slug}--${frag}"`);
  // Links have to survive printing. A cross-reference gets the page it points
  // to, “(p. 123)”: printed first with a placeholder of about the same width,
  // so that the numbers, filled in for the final printing, don't move the
  // text (see “Cross-references” below). Not in the indexes, which have their
  // own numbers, or the contents.
  if (!INDEXES.has(slug) && slug !== "title") {
    html = html.replace(/<a href="#([^"]+)"([^>]*)>([\s\S]*?)<\/a>/g, (m, target, rest, text) => {
      if (/class="(loc|src)"/.test(rest)) return m;
      const id = `xr-${++xrefs}`;
      return `${m}<span class="pref" id="${id}" data-target="${target}"> (p.&nbsp;000)</span>`;
    });
  }
  // A link out of the book gets a note number, and its address is listed at
  // the end of the page: “Links”. Links whose text is the address itself, and
  // the source references (\`hb-ot-map.cc:389\`, which say where they point),
  // don't.
  const notes = [];
  html = html.replace(/<a href="(https?:\/\/[^"]+)"([^>]*)>([\s\S]*?)<\/a>/g, (m, url, rest, text) => {
    if (/class="src"/.test(rest) || text.replace(/<[^>]+>/g, "").trim() === url.replace(/&amp;/g, "&")) return m;
    let n = notes.indexOf(url) + 1;
    if (!n) n = notes.push(url);
    return `${m}<sup class="lnote">${n}</sup>`;
  });
  if (notes.length) {
    html += `\n<div class="link-notes"><p class="link-notes-head">Links</p><ol>` +
      notes.map((u) => `<li>${u}</li>`).join("") + `</ol></div>`;
  }
  // A part opens on a right-hand page of its own, then a blank page, so its
  // first chapter starts on a right-hand page too.
  const opener = page.startsPart
    ? `<div class="part-title" id="part-${page.part.label.split(" ")[1]}"><p class="part-label">${esc(page.part.label)}</p><h1 class="part-name">${esc(page.part.name)}</h1></div>\n<div class="front blank">&nbsp;</div>\n`
    : "";
  // The title page: its description goes on the imprint's page, at the top.
  // The contents are printed twice: in brief, the chapters with their
  // summaries; then in detail, on a right-hand page of its own, with each
  // chapter's sections. The book's title, which is these pages, isn't listed.
  // Each entry gets the page it starts on, a placeholder for now, filled in
  // like the cross-references.
  if (slug === "title") {
    const h2 = html.indexOf("<h2");
    titleIntro = html.slice(0, h2).match(/<p>(?!<strong>)[\s\S]*?<\/p>/g).join("\n");
    html = html.slice(0, h2) .replace(/<p>(?!<strong>)[\s\S]*?<\/p>\s*/g, "") + html.slice(h2);
    html = html.replace(/<li><a href="#title">[\s\S]*?<\/li>/, "");
    const paged = (nav) => nav.replace(/(<a href="#([^"]+)"[^>]*>[\s\S]*?<\/a>)/g, (m, a, target) =>
      `${a}<span class="tocpg" data-target="${target}">000</span>`);
    html = html.replace(/<nav class="toc full">[\s\S]*?<\/nav>/, (nav) =>
      paged(nav.replace(/<ol class="toc-sub[\s\S]*?<\/ol>/g, "")).replace('class="toc full"', 'class="toc full brief"') +
      `\n<div class="contents-detail" id="${DETAIL}"><h2>Contents in detail</h2>\n` +
      paged(nav.replace(/<span class="summary">[\s\S]*?<\/span>/g, "")) + "</div>");
  }
  return `${opener}<section class="page-${slug}${opener ? " part-first" : ""}" id="${slug}">\n${html}\n</section>`;
}

const DETAIL = "contents-in-detail";
let titleIntro = "";
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, "book", "book.json"), "utf8"));
const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
// The version the PDF is built from, taken once, before anything is built.
const version = bookVersion(ROOT);
const madeFrom = sourceHash(ROOT);

// Front matter, after the cover: three blank pages, the half-title, a blank,
// the title page and the imprint, none numbered. The cover is page 1, so the
// half-title and title page fall on right-hand pages, the imprint behind it.
const blank = `<div class="front blank">&nbsp;</div>`;
const front = [
  blank, blank, blank,
  `<div class="front half-title"><p>${esc(meta.title)}</p></div>`,
  blank,
  // The subtitle breaks after “glyphs,”.
  `<div class="front title-page"><h1>${esc(meta.title)}</h1><p class="subtitle">${esc(meta.subtitle).replace(/glyphs,? /, "glyphs,<br>")}</p>
<p class="author">${esc(meta.author)}${meta.with ? ` <span>with ${esc(meta.with)}</span>` : ""}</p>
<p class="publisher">${esc(meta.publisher || "")}<br>${new Date().getFullYear()}</p></div>`,
  `<div class="front imprint">
<div class="imprint-intro">{{intro}}</div>
<p><i>${esc(meta.title)}</i>: ${esc(meta.subtitle).replace(/^./, (c) => c.toLowerCase())}</p>
<p>By ${esc(meta.author)}${meta.with ? ` with ${esc(meta.with)}` : ""}</p>
<p>${esc(version.label)}. It describes HarfBuzz ${esc(meta.harfbuzz)}, and every example in it was run on that version.</p>
<p>Set in Source Serif 4, Commissioner and JetBrains Mono.</p>
</div>`,
].join("\n");

const png = (name) => `data:image/png;base64,${fs.readFileSync(path.join(ROOT, "book", name)).toString("base64")}`;
const cover = png("cover.png");
const backCover = fs.existsSync(path.join(ROOT, "book", "cover-back.png")) ? png("cover-back.png") : null;

const print = `
<style>
/* Print: a 6 × 9 inch book, light colors, one state of every figure. */
@page {
  size: 6in 9in;
  margin: 0.7in 0.6in 0.75in;
}
/* No page numbers here: Chrome can't restart the count for the main text, so
   they're stamped on afterwards (see “Page numbers” below). */
/* The cover page here only holds the place: in the whole book Chrome shrinks
   it, so it's printed on its own and swapped in afterwards (see the end). */
@page cover { margin: 0; }
:root { --paper: #fff; --measure: none; --wide: none; color-scheme: light; }
html, body { background: #fff; }
/* The web styles size everything in rem, so scaling the root scales the whole
   design: body text is 1.0625rem, about 9pt here. */
html { font-size: 8.5pt; }
body { padding: 0; line-height: 1.5; }
.cover { page: cover; break-after: page; width: 6in; height: 9in; }
.cover img { display: block; width: 6in; height: 9in; object-fit: cover; }
section[id] { break-before: page; }
/* Part title pages: alone, unnumbered, on a right-hand (odd) page. Chrome's
   “break-before: right” isn't reliable here, so the build adds a blank page
   (.turn) before any part the first printing puts on an even page. The blank
   after a part's page (.front.blank) holds its own page, so the chapter needs
   no break. */
.turn { break-before: page; }
.part-title { page: front; break-before: page; break-after: page; box-sizing: border-box; height: 7.4in; padding-top: 2.2in; text-align: center; }
.part-title .part-label { margin: 0 0 .8rem; font: 600 .9rem var(--font-head); text-transform: uppercase; letter-spacing: .12em; color: #5a6373; }
.part-title .part-name { margin: 0; font-size: 2.6rem; font-weight: 500; }
section.part-first { break-before: auto; }
/* Front matter: each piece a page of its own, with no page number. */
.front { page: front; break-after: page; box-sizing: border-box; height: 7.4in; }
.half-title { padding-top: 1.6in; }
.half-title p { margin: 0; text-align: center; font: 500 2.2rem var(--font-head); letter-spacing: .02em; }
/* Title page: left aligned. The title is 4.5rem; subtitle, author, and the
   publisher and date below them, are half that. */
.title-page { padding-top: 1.2in; text-align: left; display: flex; flex-direction: column; height: 7.4in; box-sizing: border-box; }
.title-page h1 { margin: 0 0 1.2rem; font-size: 4.5rem; line-height: 1.05; font-weight: 500; }
.title-page .subtitle { margin: 0; font: italic 400 2.25rem/1.3 var(--font-text); }
.title-page .author { margin: 1in 0 0; font: 500 2.25rem/1.3 var(--font-head); }
.title-page .author span { color: #5a6373; }
.title-page .publisher { margin: auto 0 0; font: 400 2.25rem/1.3 var(--font-text); }
.imprint { display: flex; flex-direction: column; justify-content: flex-end; font-size: .85rem; line-height: 1.5; }
.imprint p { margin: 0 0 .6rem; }
.imprint .imprint-intro { margin-bottom: auto; font-size: 1.0625rem; line-height: 1.5; }
.imprint .imprint-intro p { margin: 0 0 .8rem; }
.contents-detail { break-before: page; }
/* The title page is printed above, so the web title page gives only its
   description and the contents. */
.page-title > h1, .page-title > h1 + p { display: none; }
.flow, .flow > * { max-width: none !important; }
h1 { margin-top: 0; }
h2, h3, h4 { break-after: avoid; }
p, li { orphans: 3; widows: 3; }
/* Code may run across pages, with at least three lines on each side of a break,
   so a short block stays whole. */
pre { white-space: pre-wrap; overflow-wrap: anywhere; break-inside: auto; orphans: 3; widows: 3; }
table { width: 100%; }
td, th { overflow-wrap: anywhere; }
figure, .shape, .trace, .info, .draw { break-inside: avoid; max-width: 100% !important; overflow: hidden; }
/* A program's listing is often longer than a page: let it run across pages,
   keeping its file name with its first lines. Its output, a picture and a
   caption, stays in one piece. */
figure.listing, figure.listing pre { break-inside: auto; overflow: visible; }
figure.listing figcaption { break-after: avoid; }
figure.listing pre { orphans: 4; widows: 4; }
.example-output img { break-after: avoid; }
.example-output figcaption { break-before: avoid; }
/* The web styles keep figure cells on one line and scroll them; a page can't scroll. */
.shape td, .trace td, .info td, .shape td *, .trace td *, .info td * { white-space: normal !important; }
.shape td.out code, .trace td.buf code, .info td.out code, .shape td.in .cps { white-space: pre-wrap !important; overflow-wrap: anywhere; }
.shape td.font, .shape th { white-space: nowrap !important; }
.shape td.opt, .shape td.opt * { overflow-wrap: break-word; word-break: normal; }
.trace td.what { white-space: normal !important; }
td code { overflow-wrap: break-word; }
.draw .frame-shape { white-space: pre-wrap !important; overflow-wrap: anywhere; }
.eyebrow { margin: 0 0 .4rem !important; }
.views .tabs, .draw .control, nav.pager { display: none !important; }
/* View figures: the views marked for print, each labelled if there are several. */
.views .pane { display: none !important; }
.views .pane.print { display: block !important; }
.views .pane.print ~ .pane.print::before, .views .pane.print:has(~ .pane.print)::before {
  content: attr(data-label); display: block; padding: .4rem 1rem 0;
  font: 600 .72rem "Commissioner", sans-serif; text-transform: uppercase; letter-spacing: .06em; color: #5a6373; }
/* Slider figures: the frames marked for print, in a row. */
.draw.slider .frames { display: flex !important; gap: .5rem; }
.draw.slider .frame { display: none !important; }
.draw.slider .frame.print { display: block !important; flex: 1 1 0; min-width: 0; }
.draw.slider .frame-shape { font-size: .62rem !important; }
/* Text for one medium only. */
.screen-only { display: none !important; }
.print-only { display: revert !important; }
.draw svg { max-width: 100%; height: auto; }
a { color: inherit; text-decoration: none; }
/* Links that survive printing: cross-references in the accent color, with the
   page they point to; links out with a note number, and their addresses in a
   list at the end of the page. Source references keep their own style. */
.flow a:not(.src):not(.loc) { color: #2c48c9; }
.pref { white-space: nowrap; font-size: .85em; color: #5a6373; }
sup.lnote { font-size: .62em; line-height: 0; color: #2c48c9; margin-left: .05em; }
.link-notes { margin-top: 1.6rem; border-top: 1px solid #c9ced8; padding-top: .5rem; font-size: .72rem; line-height: 1.35; }
.link-notes-head { font: 600 .72rem var(--font-head); text-transform: uppercase; letter-spacing: .08em; color: #5a6373; margin: 0 0 .3rem !important; }
.link-notes ol { margin: 0; padding-left: 1.6rem; }
.link-notes li { overflow-wrap: anywhere; word-break: break-all; }
.unwritten { color: inherit; }
/* The contents: page numbers on the right; each chapter's sections under it,
   in smaller type, without the summaries. */
.toc.full li { grid-template-columns: 2.2em 1fr auto; column-gap: .6rem; break-inside: avoid; }
.toc.full .tocpg { grid-column: 3; grid-row: 1; text-align: right; font-variant-numeric: tabular-nums; color: #5a6373; }
.toc.full .toc-sub { grid-column: 2 / 4; margin: .1rem 0 .5rem; }
.toc.full .toc-sub li { display: flex; gap: .6rem; break-inside: avoid; line-height: 1.45; }
.toc.full .toc-sub li > a { flex: 1; color: inherit !important; }
.toc.full .toc-sub .tocpg { font-size: .9em; }
/* The indexes: two columns of small type. */
.index ul { columns: 2; column-gap: 1.4rem; }
.index li { font-size: .8rem; line-height: 1.35; }
.index .index-letter h2 { break-after: avoid; font-size: 1rem; margin-top: .8rem; }
</style>`;

// The indexes need page numbers, which only laying out the book can give.
// So the book is printed twice. The first time it leaves the indexes out and
// ends instead with a page of links to every place they cite: Chrome records
// the page of each place a link points to, as a named destination. Those
// pages go into the indexes, which are added for the second, final printing.
// They come after every page they cite, so adding them moves none of them.
const INDEXES = new Set(["general-index", "code-index"]);
let xrefs = 0;
// The text column and the size body text actually prints at, measured from a
// printing: Chrome shrinks the whole book to fit, so neither is what the CSS
// says. The column's left edge is where most lines begin; it is centered, so
// the right edge mirrors it. pdftotext's word boxes for Source Serif 4 are
// 1.664 times the font size (measured: 9 pt gives 14.98), and most words on
// the pages measured are body text, so the commonest height is its.
function measure(pdf, from) {
  const bbox = spawnSync("pdftotext", ["-bbox", "-f", String(from), "-l", String(from + 38), pdf, "-"], { encoding: "utf8", maxBuffer: 1 << 28 }).stdout;
  const starts = new Map(), heights = new Map();
  for (const m of bbox.matchAll(/<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)"/g)) {
    const x = (+m[1]).toFixed(1), h = (+m[3] - +m[2]).toFixed(2);
    starts.set(x, (starts.get(x) || 0) + 1);
    heights.set(h, (heights.get(h) || 0) + 1);
  }
  const columnLeft = Math.min(...[...starts].filter(([, n]) => n >= 50).map(([x]) => +x));
  const bodySize = +([...heights].sort((a, b) => b[1] - a[1])[0][0] / 1.664).toFixed(2);
  if (!isFinite(columnLeft) || !bodySize) { console.error("measure: can't find the text column"); process.exit(1); }
  return { columnLeft, bodySize };
}

const doc = (main, extra = "") => `<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>How HarfBuzz Works</title>
${head}
${print}
${extra ? `<style>${extra}</style>` : ""}
</head>
<body>
<div class="cover"><img src="${cover}" alt="How HarfBuzz Works"></div>
${front.replace("{{intro}}", titleIntro)}
<main class="flow">
${main}
</main>
</body>
</html>
`;

// The pages printed on the way (the book without its indexes, the cover, the
// folios) are kept in the scratch folder, not beside the PDF.
const printDir = path.join(work, "print");
fs.mkdirSync(printDir, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });
function printPdf(html, out, name) {
  const htmlFile = path.join(printDir, name);
  fs.writeFileSync(htmlFile, html);
  const r = spawnSync(CHROME, ["--headless", "--disable-gpu", "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
    "--generate-pdf-document-outline",
    `--print-to-pdf=${out}`, pathToFileURL(htmlFile).href], { encoding: "utf8" });
  if (r.status !== 0 || !fs.existsSync(out)) { console.error(r.stderr); process.exit(1); }
  return htmlFile;
}

const LOC = /<a href="#([^"]+)" class="loc( def)?"[^>]*>[^<]*<\/a>/g;
const bodies = new Map(pages.filter((p) => p.written).map((p) => [p.slug, content(p.slug)]));
const indexes = [...bodies].filter(([slug]) => INDEXES.has(slug));
let mainHtml = [...bodies].filter(([slug]) => !INDEXES.has(slug)).map(([, b]) => b).join("\n");
const partIds = [...new Set(pages.filter((p) => p.startsPart).map((p) => `part-${p.part.label.split(" ")[1]}`))];
const targets = new Set([DETAIL, ...partIds, ...indexes.flatMap(([, b]) => [...b.matchAll(LOC)].map((m) => m[1]))]);
for (const m of mainHtml.matchAll(/<span class="tocpg" data-target="([^"]+)">/g)) targets.add(m[1]);
// and every cross-reference, and where it points
for (const m of mainHtml.matchAll(/<span class="pref" id="(xr-\d+)" data-target="([^"]+)">/g)) { targets.add(m[1]); targets.add(m[2]); }
const firstPdf = path.join(printDir, "without-indexes.pdf");
printPdf(doc(mainHtml + `\n<section class="index-targets" style="font-size:1px">` +
  [...targets].map((t) => `<a href="#${t}">.</a>`).join(" ") + "</section>"), firstPdf, "without-indexes.html");
const firstPages = destinations(firstPdf);

// Every part starts on an odd page. Each one the first printing puts on an
// even page gets a blank page before it, which moves it and everything after
// it on by one page; nothing else in the layout changes, as each part starts
// on a new page anyway.
// The detailed contents also starts on an odd page, the same way.
const turns = [];
for (const id of [DETAIL, ...partIds]) {
  if ((firstPages.get(id) + turns.length) % 2 === 0) turns.push(firstPages.get(id));
}
for (const id of [DETAIL, ...partIds]) if (turns.includes(firstPages.get(id)))
  mainHtml = mainHtml.replace(new RegExp(`<div class="[^"]*" id="${id}"`), `<div class="front blank turn">&nbsp;</div>\n$&`);
const pageOf = new Map([...firstPages].map(([t, n]) => [t, n + turns.filter((p) => p <= n).length]));

// Page numbers. The cover and the blanks before the half-title have none; the
// front matter counts in roman numerals from the half-title; the main text in
// arabic from the first part's title page. PDF page → printed number:
const ROMAN_FROM = 5; // cover, three blanks, then the half-title
const ARABIC_FROM = pageOf.get(partIds[0]);
if (!ARABIC_FROM) { console.error("pages: can't find the first part's page"); process.exit(1); }
const { columnLeft, bodySize } = measure(firstPdf, firstPages.get(partIds[0]) + 2);
// How much Chrome shrinks the book: body text is 1.0625rem at 8.5pt a rem.
const shrink = bodySize / (1.0625 * 8.5);
console.log(`measured: text column from ${columnLeft} pt, body text ${bodySize} pt (${Math.round(shrink * 100)}% of its CSS size)`);
const roman = (n) => [[1000, "m"], [900, "cm"], [500, "d"], [400, "cd"], [100, "c"], [90, "xc"], [50, "l"], [40, "xl"], [10, "x"], [9, "ix"], [5, "v"], [4, "iv"], [1, "i"]]
  .reduce((acc, [v, r]) => { while (n >= v) { acc += r; n -= v; } return acc; }, "");
const label = (n) => n >= ARABIC_FROM ? String(n - ARABIC_FROM + 1) : n >= ROMAN_FROM ? roman(n - ROMAN_FROM + 1) : "";
// Pages that are counted but carry no printed number: the front matter's own
// pages, each part's title page and the blank after it.
const unnumbered = new Set(partIds.flatMap((id) => [pageOf.get(id), pageOf.get(id) + 1]));
for (let n = 1; n < ROMAN_FROM + 4; n++) unnumbered.add(n); // through the imprint

if (indexes.length) {
  const indexTargets = new Set(indexes.flatMap(([, b]) => [...b.matchAll(LOC)].map((m) => m[1])));
  const places = indexTargets.size;
  const missing = [...indexTargets].filter((t) => !pageOf.has(t));
  console.log(`index: ${places} places, ${places - missing.length} found in the first printing`);
  if (missing.length) console.error(`index: no page found for ${missing.length} places, e.g. ${missing.slice(0, 3).join(", ")}`);
  // Each entry's places become page numbers: in book order, one per page,
  // bold if the term is defined on that page.
  const numbered = indexes.map(([, b]) => b.replace(/<li>([\s\S]*?)<\/li>/g, (li, inner) => {
    const locs = [...inner.matchAll(LOC)];
    if (!locs.length) return li;
    const byPage = new Map();
    for (const [, target, def] of locs) {
      const n = pageOf.get(target);
      if (n == null) continue;
      const had = byPage.get(n);
      if (!had || (def && !had.def)) byPage.set(n, { def: !!def, target });
    }
    const nums = [...byPage].sort((a, b) => a[0] - b[0])
      .map(([n, { def, target }]) => `<a href="#${target}" class="loc${def ? " def" : ""}">${label(n)}</a>`).join(", ");
    const start = inner.search(LOC);
    const rest = inner.slice(start).replace(/^(?:\s*<a href="#[^"]*" class="loc[^>]*>[^<]*<\/a>,?)+/, "");
    return `<li>${inner.slice(0, start)}${nums}${rest}</li>`;
  }));
  mainHtml += "\n" + numbered.join("\n");
}
// Cross-references: each placeholder becomes the printed number of the page
// its target is on, or goes, if that is the page the reference is on.
{
  let same = 0, lost = 0;
  mainHtml = mainHtml.replace(/<span class="pref" id="(xr-\d+)" data-target="([^"]+)"> \(p\.&nbsp;000\)<\/span>/g, (m, id, target) => {
    const at = pageOf.get(id), to = pageOf.get(target);
    if (to == null) { lost++; return ""; }
    if (at === to) { same++; return ""; }
    return `<span class="pref"> (p.&nbsp;${label(to)})</span>`;
  });
  console.log(`cross-references: ${xrefs}, ${same} on their own page, ${lost} with no page found`);
}
mainHtml = mainHtml.replace(/<span class="tocpg" data-target="([^"]+)">000<\/span>/g, (m, target) =>
  `<span class="tocpg">${pageOf.has(target) ? label(pageOf.get(target)) : ""}</span>`);
// The title page fills the text area, so its last lines sit on the bottom
// margin: 7.55in on paper (9in less the margins), in CSS inches before Chrome shrinks it.
const htmlFile = printPdf(doc(mainHtml, `.title-page { height: ${(7.55 / shrink - 0.05).toFixed(3)}in; }`), OUT, "book.html");

// The cover, full bleed: printed alone, it fills the page, so it replaces the
// placeholder page 1. qpdf keeps the rest of the book's pages, outline, links
// and tags, and packs its objects into compressed streams, which halves the
// file: most of it is the structure tree that makes the PDF accessible.
const coverPage = (src, alt, out, name) => printPdf(`<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: 6in 9in; margin: 0; } html, body { margin: 0; }
img { display: block; width: 6in; height: 9in; object-fit: cover; }
</style></head><body>${src ? `<img src="${src}" alt="${alt}">` : "&nbsp;"}</body></html>`, out, name);
const coverPdf = path.join(printDir, "cover.pdf");
coverPage(cover, "How HarfBuzz Works", coverPdf, "cover.html");
// The back cover, the last page, which is a left-hand (even) page: after a
// blank if the book ends on one. It has no page number.
const bookPages = Number(spawnSync("qpdf", ["--show-npages", OUT], { encoding: "utf8" }).stdout.trim());
const back = [];
if (backCover) {
  if (bookPages % 2 === 0) {
    const blankPdf = path.join(printDir, "blank.pdf");
    coverPage(null, "", blankPdf, "blank.html");
    back.push(blankPdf, "1");
  }
  const backPdf = path.join(printDir, "cover-back.pdf");
  coverPage(backCover, "Back cover", backPdf, "cover-back.html");
  back.push(backPdf, "1");
}
const UNNUMBERED_FROM = bookPages + 1; // the back cover, and any blank before it
// The printed page numbers, stamped on as an overlay: a PDF of the same
// number of pages, blank but for the number, at the outer foot of the page.
// Pages with no text (blanks Chrome adds so a part starts on the right) get
// none either.
const texts = spawnSync("pdftotext", ["-layout", OUT, "-"], { encoding: "utf8", maxBuffer: 1 << 30 }).stdout.split("\f");
const total = Number(spawnSync("qpdf", ["--show-npages", OUT], { encoding: "utf8" }).stdout.trim());
// Check that the final printing put every part where it was meant to go.
for (const id of partIds) {
  const n = pageOf.get(id), name = id.replace("part-", "PART ");
  if (n % 2 === 0 || !new RegExp(`^\\s*${name}\\s`).test(texts[n - 1] || "")) {
    console.error(`pages: ${name} isn't on page ${n}, as planned`); process.exit(1);
  }
}
const folios = [];
for (let n = 1; n <= total; n++) {
  const show = !unnumbered.has(n) && label(n) && (texts[n - 1] || "").trim();
  folios.push(`<div class="pg ${n % 2 ? "r" : "l"}">${show ? label(n) : ""}</div>`);
}
const foliosPdf = path.join(printDir, "folios.pdf");
printPdf(`<!doctype html><html><head><meta charset="utf-8">${head.match(/<link[^>]*fonts\.googleapis[^>]*>/g)?.join("\n") || ""}<style>
@page { size: 6in 9in; margin: 0; } html, body { margin: 0; }
/* In the body text's style: its face, size and color. */
.pg { position: relative; width: 6in; height: 9in; break-after: page; overflow: hidden;
  font: 400 ${bodySize}pt "Source Serif 4", Georgia, serif; font-optical-sizing: auto; color: #1a1e27; }
.pg.r { text-align: right; padding: 0 ${columnLeft}pt; box-sizing: border-box; line-height: 0.75in; padding-top: calc(8.25in - 1em); }
.pg.l { text-align: left; padding: 0 ${columnLeft}pt; box-sizing: border-box; line-height: 0.75in; padding-top: calc(8.25in - 1em); }
</style></head><body>${folios.join("")}</body></html>`, foliosPdf, "folios.html");

// The labels file, beside the PDF: one line where each numbering starts, as
// “PDF-page first-number [style]”, style “none”, “roman” or (left out) arabic.
// The same labels go into the PDF, for viewers that show them.
const labelsFile = OUT.replace(/\.pdf$/, "") + ".pages.txt";
fs.writeFileSync(labelsFile, `1 1 none\n${ROMAN_FROM} 1 roman\n${ARABIC_FROM} 1\n${back.length ? `${UNNUMBERED_FROM} 1 none\n` : ""}`);

const joined = OUT + ".tmp";
const q = spawnSync("qpdf", ["--object-streams=generate", OUT, "--pages", coverPdf, "1", OUT, "2-z", ...back, "--",
  "--overlay", foliosPdf, "--",
  "--set-page-labels", "1:", `${ROMAN_FROM}:r/1`, `${ARABIC_FROM}:D/1`, ...(back.length ? [`${UNNUMBERED_FROM}:`] : []), "--", joined], { encoding: "utf8" });
if (q.status !== 0 && q.status !== 3) { console.error(q.stderr); process.exit(1); }
fs.renameSync(joined, OUT);
console.log(labelsFile);

// What this PDF was made from, so that publishing can tell when it's stale.
if (OUT === path.join(ROOT, "site", "print", "how-harfbuzz-works.pdf")) {
  fs.mkdirSync(path.join(ROOT, ".cache"), { recursive: true });
  fs.writeFileSync(path.join(ROOT, RECORD),
    JSON.stringify({ stamp: version.stamp, commit: version.commit, changes: version.changes, source: madeFrom }) + "\n");
}

// The PDF's named destinations, as a map from name to page number.
function destinations(pdf) {
  const r = spawnSync("qpdf", ["--json=2", pdf], { encoding: "utf8", maxBuffer: 1 << 30 });
  if (r.status !== 0) { console.error(r.stderr); process.exit(1); }
  const j = JSON.parse(r.stdout), objs = j.qpdf[1];
  const pageNo = new Map(j.pages.map((p, i) => [p.object, i + 1]));
  const deref = (v) => (typeof v === "string" && v.endsWith(" R") ? objs[`obj:${v}`].value : v);
  const catalog = Object.values(objs).map((o) => o.value).find((v) => v && v["/Type"] === "/Catalog");
  const out = new Map();
  const add = (name, d) => {
    d = deref(d);
    if (d && !Array.isArray(d)) d = deref(d["/D"]);
    if (Array.isArray(d) && pageNo.has(d[0])) out.set(name.replace(/^\//, "").replace(/^u:/, ""), pageNo.get(d[0]));
  };
  for (const [name, d] of Object.entries(deref(catalog["/Dests"]) || {})) add(name, d);
  // Destinations may also be in a name tree.
  const walk = (node) => {
    node = deref(node);
    if (!node) return;
    const names = node["/Names"];
    if (names) for (let i = 0; i < names.length; i += 2) add(String(names[i]), names[i + 1]);
    for (const kid of node["/Kids"] || []) walk(kid);
  };
  const tree = deref(catalog["/Names"]);
  if (tree) walk(tree["/Dests"]);
  return out;
}
console.log(OUT);
console.log(htmlFile);
