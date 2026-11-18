// Checks every four-character tag the book quotes in code (`dev3`, `GSUB`,
// `liga`) against the registries: OpenType's script, language system,
// feature, baseline, axis, MVAR value and table tags, and Apple's table
// tags. A tag that is in none of them must be listed in
// notes/unregistered-tags.txt, either as not a tag at all (a word such as
// `NULL`) or as a real tag outside the registries, with where the book says
// so. The point is the second kind: what HarfBuzz's code accepts isn't
// always a standard, and the code doesn't say which.
//
//   node tools/check-tags.mjs           check the book
//   node tools/check-tags.mjs --update  fetch the registries again first
//
// The registries are kept, as tag lists only, in tools/registries.json.

import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const REGISTRIES = path.join(ROOT, "tools/registries.json");
const LIST = path.join(ROOT, "notes/unregistered-tags.txt");

const MS = "https://learn.microsoft.com/en-us/typography/opentype/spec/";
const SOURCES = {
  script: [MS + "scripttags", /'([^'<>\n]{1,4})'/g],
  language: [MS + "languagetags", /<tr>\s*<td>[^<]*<\/td>\s*<td>'?([^'<>\n]{1,4})'?<\/td>/g],
  feature: [MS + "featurelist", />'([^'<>\n]{4})'</g],
  baseline: [MS + "baselinetags", /'([^'<>\n]{4})'/g],
  axis: [MS + "dvaraxisreg", /'([^'<>\n]{4})'/g],
  mvar: [MS + "mvar", /'([^'<>\n]{4})'/g],
  "opentype table": [MS + "otff", /'([^'<>\n]{4})'|>([A-Z][A-Z0-9/ ]{3})</g],
  "apple table": ["https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6.html", /'([^'<>\n]{4})'/g],
};

function unescape(s) {
  return s.replace(/&nbsp;|&#160;/g, " ").replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, "&")
    .replace(/ /g, " ");
}

async function update() {
  const out = {};
  for (const [name, [url, re]] of Object.entries(SOURCES)) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: ${res.status}`);
    const text = unescape(await res.text());
    const tags = new Set();
    for (const m of text.matchAll(re)) tags.add((m[1] ?? m[2]).padEnd(4, " "));
    // Feature tags given as ranges in the list
    if (name === "feature") for (let i = 1; i <= 99; i++) {
      tags.add("cv" + String(i).padStart(2, "0"));
      if (i <= 20) tags.add("ss" + String(i).padStart(2, "0"));
    }
    out[name] = { url, tags: [...tags].sort() };
    console.log(`${name}: ${tags.size} tags`);
  }
  // Graphite's tables are SIL's, not in either list
  out["graphite table"] = { url: "https://graphite.sil.org/", tags: ["Feat", "Glat", "Gloc", "Sile", "Silf", "Sill"] };
  fs.writeFileSync(REGISTRIES, JSON.stringify(out, null, 1) + "\n");
}

function readList() {
  const known = new Map();
  for (const line of fs.readFileSync(LIST, "utf8").split("\n")) {
    if (!line.trim() || line.startsWith("#")) continue;
    const m = line.match(/^`([^`]{4})`\s+(\S+)\s*(.*)$/);
    if (!m) throw new Error(`${LIST}: can't read “${line}”`);
    known.set(m[1], { kind: m[2], note: m[3] });
  }
  return known;
}

if (process.argv.includes("--update")) await update();
const registries = JSON.parse(fs.readFileSync(REGISTRIES, "utf8"));
const registered = new Map();
for (const [name, { tags }] of Object.entries(registries))
  for (const t of tags) registered.set(t, [...(registered.get(t) ?? []), name]);
const known = readList();

const found = new Map();
const files = fs.readdirSync(path.join(ROOT, "book"), { recursive: true })
  .filter((f) => f.endsWith(".md")).sort();
for (const f of files) {
  const text = fs.readFileSync(path.join(ROOT, "book", f), "utf8").replace(/^```[\s\S]*?^```/gm, "");
  for (const [, tag] of text.matchAll(/`([A-Za-z][A-Za-z0-9 /]{3})`/g)) {
    if (!found.has(tag)) found.set(tag, new Set());
    found.get(tag).add(f);
  }
}

const unknown = [], unregistered = [];
for (const [tag, where] of [...found].sort()) {
  if (registered.has(tag)) continue;
  const k = known.get(tag);
  if (!k) unknown.push(`  \`${tag}\`  ${[...where].join(", ")}`);
  else if (k.kind === "unregistered") unregistered.push(`  \`${tag}\`  ${k.note}`);
}
const stale = [...known.keys()].filter((t) => !found.has(t) || registered.has(t));

console.log(`tags: ${found.size} quoted, ${found.size - unknown.length - [...known.keys()].filter((t) => found.has(t)).length} registered`);
if (unregistered.length) console.log(`real tags outside the registries:\n${unregistered.join("\n")}`);
if (stale.length) console.log(`listed in ${path.relative(ROOT, LIST)} but no longer needed: ${stale.map((t) => "`" + t + "`").join(" ")}`);
if (unknown.length) {
  console.log(`not registered, and not in ${path.relative(ROOT, LIST)}:\n${unknown.join("\n")}`);
  process.exitCode = 1;
}
