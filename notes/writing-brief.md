# Brief for writing a chapter

What a writer of one chapter is given, whether that’s a person or an agent. The order chapters are written in is in `writing-order.md`.

## Read first

* `AGENTS.md` and `README.md`.
* `book/chapters/gsub.md`, the model for voice, structure and depth.
* `book/front/introduction.md` and `book/front/notation.md`. Build on them; don’t repeat them.
* The chapters this one depends on (see `writing-order.md`), in their current drafts. Link back to them instead of explaining again.
* `notes/outline.md`, and the parts of `notes/survey/` that cover the chapter.
* The block types in `tools/build-site.mjs`: `views`, `shape`, `trace` and `raster` (header comment), `draw`, `info` and `table` (comments above `blockDraw`, `blockInfo` and `blockTable`), and `example` and `demo` for whole programs from `examples/` (comments above `blockExample` and `blockDemo`, and `README.md`).

## Sources, and how claims are checked

The HarfBuzz version the book describes (`book/book.json`) is checked out at `.cache/harfbuzz/`, built by `tools/build-harfbuzz.sh`: `build/` (FreeType, ICU, cairo and the tests off), `build-msg/` with `HB_BUFFER_MESSAGE_MORE`, and `build-ft/` with FreeType, for comparing FreeType’s hinted outlines and metrics.

* **Claims about HarfBuzz** are checked against that code, and cite file and line (`hb-ot-map.cc:389` in prose, `src/...` in the “Where to read the source” table). The survey notes are a guide: where they disagree with the code, the code wins, and the disagreement is reported.
* **Claims about HarfBuzz’s history** come from `NEWS`, `README.md`, `AUTHORS`, `docs/` and source comments. `docs/usermanual-*.xml` is the hand-written manual, and the doc comments in `src/*.cc` (with their `Since:` versions) are the API reference. The manual says what was intended; the code says what happens.
* **Claims about other projects** (browsers, toolkits, platforms, HarfRust) need a source in that project: its repository or its own documentation, cited. A claim without one is left out, not softened.
* **Claims about standing** come from outside HarfBuzz, because the code can’t give them. The code says what HarfBuzz does, not whether that is the standard. For every tag, table, feature, flag or behavior a chapter describes, ask: is it in the OpenType specification or its registries, only in the ISO standard, Apple’s, or HarfBuzz’s own (experimental, or a private extension)? Do other engines (DirectWrite, Core Text, Uniscribe) do the same? Say which, with a source: the registries, Microsoft’s script development specifications, the ISO standard, Apple’s TrueType Reference Manual, or a HarfBuzz issue or discussion where the decision was made (the resources in `AGENTS.md`). A tag HarfBuzz accepts but no registry lists, such as `dev3`, must be called unregistered where it first appears. `node tools/check-tags.mjs` lists every quoted tag that isn’t registered; a new one goes in `notes/unregistered-tags.txt`, with where the book says so.
* Anything not checked is marked as the writer’s own reading (“(inferred)”, or said in words).

## Style

* Plain, direct, short sentences. Explain, don’t sell. Present tense. A short opening like the GSUB chapter’s, no throat-clearing.
* American spelling (color, neighbor, behavior, center, gray, toward, spelled). Quotations keep their source’s spelling, and punctuation stays outside closing quotes unless it belongs to the quotation.
* The serial comma, American style: “A, B, and C”, “A, B, or C”, since 20 November 2026. Quotations and the titles of other works keep their own punctuation.
* Typographic quotes and apostrophes in prose (“ ” ‘ ’ ’); straight ones only in code, URLs and attributes.
* Colons and periods rather than em dashes.
* `{{hb}}` for the HarfBuzz version in prose about the build.
* Structure like gsub.md: `# Title` exactly as in `book/toc.txt`; an opening of two or three paragraphs; `##` sections; short, trimmed source excerpts (say they’re trimmed); tables where they help; occasional `> For type designers:` or `> For programmers:` callouts; then `## Where to read the source` (a table) and `## In short` (bullets).
* Headings say plainly what the section is about (“The three libraries”, “Dispatch contexts”). No formulas or wordplay: not “One X, many Y”, “Three libraries, one shape”, “X: the Y”. Avoid “shape” and “shaping” except for text shaping.
* Bold marks a term where it is defined, and nothing else: the book’s index and glossary are gathered from bold terms (`tools/index-terms.mjs`). A bold label on a paragraph or list item ends with its full stop inside the bold (“**In the font.**”).
* Fixed upstream since {{hb}}: the text keeps describing {{hb}}, and a one-line callout goes right after the paragraph or example that describes the behavior (after the table or list, naming the row or item, where a blockquote would break it): ``> Since {{hb}}: fixed on HarfBuzz main by [#6713](https://github.com/harfbuzz/harfbuzz/pull/6713) (17 November 2026), so main <does what>.``, or “partly fixed on … (date): <what changed>; <what remains>.”, or “changed on … (date): <how>.” The pull request that made the change, as “#6713” linked to it (the PDF prints no address for these), the date it landed, no bold; nothing for an open pull request. Add notes as fixes land on main, with `notes/upstream-bug-reports.md`’s “On main” as the authority; `grep -rn '> Since {{hb}}:' book` finds them all.
* Length: as long as the subject needs, and no longer. There is no target: a small subject makes a short chapter, and 1,500 words is fine if that covers it. Never pad, restate or add sections to reach a length. There is no hard limit either: around 4,000 words of prose (not counting code and blocks) is only a point to ask whether some of it belongs in another chapter, or in a chapter of its own. A subject that needs more can have more; say in the report if a chapter has grown well past that.

## Live examples

Anything shown as HarfBuzz’s output is a live block, run when the book is built; anything else is labeled as hand-written or as another tool’s output.

* Blocks run against the fonts in `fonts/<slug>/`: a `build.sh` that uses `${PYTHON:-python3}`, feature files, and if needed a builder script in that folder. Prefer deriving fonts from existing ones (as `fonts/blobs-faces-and-lazy-tables/` does) to writing yet another builder. `fonts/variations/` holds shared variable fonts.
* fontTools: the default `python3` here may lack it; Homebrew’s Python 3.10 has fontTools 4.38.
* The Write tool turns `\uXXXX` escapes into literal characters when it writes a file. After writing a chapter, check its `shape`, `trace` and `draw` text and put the escapes back with a script; look-alike text must stay escaped.
* The book is read on screen and in print. Describe what a figure shows, not how to operate it (“the frames run from weight 100 to 900”, not “drag the slider”). Give every slider a `print:` line naming the three to five values print should show, chosen where something changes (thresholds, not just the ends). A `views` block prints only its spec-like view unless a `print:` line names more (`print: spec hex`): add one whenever the text refers to another view. Where screen and print genuinely need different words, write both, side by side, as `<span class="screen-only">…</span><span class="print-only">…</span>`; keep that rare.
* Pass `--language` in any example whose output could depend on it: `hb-shape` otherwise takes the language from the locale.
* Useful `hb-shape` options: `--verify` (reshapes at every safe-to-break point and compares), `--text-before`/`--text-after` (pre- and post-context), `--show-flags`, `--show-extents`, `--cluster-level`, `--font-bold`, `--font-slant`, `--variations`, `--named-instance`, `--face-index`, `--trace`. See `hb-shape --help-all`.

## Verifying

Build the whole site into a directory of your own (`node tools/build-site.mjs DIR`), never into `site/` while others are writing. It must succeed. So must `node tools/check-tags.mjs`. Then read the chapter’s HTML and check that every block rendered and says what the prose says.

## Boundaries

* Write only `book/chapters/<slug>.md` and `fonts/<slug>/`. Don’t edit `book/toc.txt`, other chapters, front or end matter, `notes/`, or `tools/`; report what needs changing there.
* Links to other pages are `<slug>.html`: the file name, or for a planned page its title through `slugify` in `tools/build-site.mjs` (“hb_shape and its backends” → `hb_shape-and-its-backends.html`).

## Report back

The files written; a one-paragraph summary; synonyms and “see also” links the chapter’s terms need in `notes/index-notes.md`; disagreements between the notes and the code; possible HarfBuzz bugs found (and whether shown live); `HB_NO_*` macros, generators and limits the chapter mentions (for the appendices); glossary terms; bibliography entries. Short.

## Notes for particular chapters

Chapters are named, not numbered, here, as the numbers change when chapters move.

* **For applications.** Why shaping exists and Buffers explain clusters and the flags; this chapter is what an application does with them. `--verify`, `--text-before` and `--text-after` can show reshaping at a break live, both where it’s safe and where a font makes it unsafe.
* **Testing HarfBuzz.** The test suites are described from their files in `test/` (the shaping test format, the fuzzer corpora): our build has tests off, so nothing from them runs live unless `tools/build-harfbuzz.sh` changes. Traces and `--verify` can run live. It also covers the possible HarfBuzz bugs that writing this book turned up just by building examples (`notes/upstream-bug-reports.md`), with what happened to each upstream.
* **The family.** Mostly about other projects, so every claim needs a source in that project (see “Sources”). hb_shape and its backends covers the harfrust backend inside HarfBuzz, and HarfRust has a chapter of its own; this chapter points to it. Comparisons across platforms are prose with sources: our build can’t run them.
