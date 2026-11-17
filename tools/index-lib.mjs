// What the book's two indexes are made of, shared by tools/index-terms.mjs
// (which lists candidate terms for review) and tools/build-site.mjs (which
// finds where they occur and writes the index pages).
//
//   general  concepts (terms in **bold**, which by the book's convention mark
//            the place a term is defined) and OpenType table and feature tags
//   code     HarfBuzz's own names: API and macros, types and structs, and
//            source files
//
// notes/index-notes.md, kept by hand, says which bold runs aren't terms, and
// gives main entries their variant forms, other names and cross-references.

import fs from "node:fs";
import path from "node:path";

// Four-letter code spans that aren't tags.
const NOT_TAGS = new Set(["mask", "NEWS", "else", "true", "null", "void", "char", "bool", "this", "base", "auto", "case", "info", "goto"]);

// A code span, classified: ["file" | "api" | "type" | "tag", name], or null.
export function identifier(span) {
  const s = span.trim().replace(/\s*\(\s*\.*\s*\)$/, "");          // hb_shape () -> hb_shape
  const file = s.match(/^((?:src\/|util\/|test\/|docs\/)?[\w./-]+\.(?:hh|cc|h|py|rs|rl|md|txt|build))(?::[\d–-]+)?$/);
  if (file) return ["file", file[1].replace(/^src\//, "")];
  if (/^:[\d–,-]+$/.test(s)) return null;                         // bare line numbers
  if (/^_?hb_\w+$|^HB_\w+$/.test(s)) return ["api", s];
  if (/^(?:OT|AAT|CFF|graph)::\w+$/.test(s)) return ["type", s];
  if (/^[A-Z][a-z]+[A-Z]\w*$|^[A-Z][A-Za-z]*\d\w*$/.test(s)) return ["type", s];  // CamelCase structs
  if (/^[A-Za-z][A-Za-z0-9/ ]{2,3}$/.test(s) && /[A-Za-z]/.test(s) &&
      (s.length === 4 || /^(?:CFF|OS\/2)$/.test(s)) && !NOT_TAGS.has(s)) return ["tag", s];   // GSUB, liga, OS/2, CFF
  return null;
}

// The key a term is filed under: case, code ticks and quotes don't matter.
export const canon = (t) => t.replace(/[`“”‘’"]/g, "").replace(/\s+/g, " ").trim().toLowerCase();

// A bold run that is a definition, rather than a lead-in label
// ("**In the font.**") or a callout ("**For programmers:**").
export function boldTerm(text) {
  if (/[.:]$/.test(text)) return null;
  const t = text.replace(/,$/, "").trim();
  if (!t || /^For (type designers|programmers)/.test(t)) return null;
  return t;
}

// notes/index-notes.md, read into:
//   notTerms  bold runs that aren't terms (canon keys)
//   mains     canon key -> { display, variants, aliases, see, seeAlso }
export function readNotes(root) {
  const file = path.join(root, "notes", "index-notes.md");
  const text = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  const section = (name) => (text.match(new RegExp(`^## ${name}\\n([\\s\\S]*?)(?=^## |(?![\\s\\S]))`, "m")) || [, ""])[1];
  const notTerms = new Set(section("Not index terms").split("\n")
    .filter((l) => l.startsWith("* ")).map((l) => canon(l.slice(2))));
  const mains = new Map();
  const list = (s) => s.split(/,\s*/).map((x) => x.trim()).filter(Boolean);
  for (const line of section("Main entries and synonyms").split("\n")) {
    if (!line.startsWith("* **")) continue;
    // "; " separates clauses; one starting with bold starts another entry.
    const entries = [];
    for (const clause of line.slice(2).split(/;\s+/)) {
      if (clause.startsWith("**") || !entries.length) entries.push([clause]);
      else entries[entries.length - 1].push(clause);
    }
    for (const [head, ...more] of entries) {
      const m = head.match(/^\*\*(.+?)\*\*\s*(?:\(([^)]*)\))?\s*(?:(=|:)\s*(.*))?$/);
      if (!m) continue;
      const e = { display: m[1], variants: [], aliases: [], see: null, seeAlso: [] };
      if (m[2]) {
        const quoted = [...m[2].matchAll(/“([^”]+)”/g)].map((q) => q[1]);
        if (quoted.length) e.variants.push(...quoted); else e.aliases.push(...list(m[2]));
      }
      const clauses = [...(m[4] ? [(m[3] === "=" ? "also " : "") + m[4]] : []), ...more];
      for (const c of clauses) {
        const x = c.replace(/\*\*/g, "");
        let r;
        if ((r = x.match(/^see also\s+(.+)/))) e.seeAlso.push(...list(r[1]));
        else if ((r = x.match(/^see\s+(.+)/))) e.see = list(r[1]).join(", ");
        else if ((r = x.match(/^(?:also|=)\s+(.+)/))) e.aliases.push(...list(r[1].replace(/,?\s*see also\s+.*$/, "")));
      }
      e.aliases = e.aliases.map((a) => a.replace(/\s*\(.*\)$/, "")).filter((a) => !/^see\b/.test(a));
      mains.set(canon(e.display), e);
    }
  }
  return { notTerms, mains };
}
