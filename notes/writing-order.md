# Writing order

The order chapters get written in, so that each is written after the chapters it builds on. Chapters in one wave can be written at the same time; a wave starts when the one before it has been reviewed. Numbers are the chapter numbers in `book/toc.txt` (and `outline.md`). How each chapter is briefed is in `writing-brief.md`.

## Done or under way

* Wave 1: 1–6 (Foundations), drafted.
* 15 (GSUB) and 28–31 (Variations), drafted before the others.
* Wave 2: 7–9 (Text in), drafted.
* Wave 3: 10 (Shape plans and their cache), drafted.
* Wave 4: 11 (From features to lookups) and 12 (Choosing a script shaper), drafted.
* Wave 5: 13 (The pipeline, first pass) and 14 (Normalization), drafted; 15 (GSUB) revised against 10–14.
* Wave 6: 16 (GPOS), 17 (Fallbacks), 18 (Legacy kern) and 19 (Vertical text), drafted.
* Wave 7: 20 (Joining scripts), 21 (Hebrew, Thai, Lao and Hangul) and 22 (The Indic model, first pass), being written.
* Brought forward from wave 9, since Part VIII doesn’t depend on Part V: 32 (Drawing outlines) and 33 (Color), being written; 34 (Rendering) waits for both.

## To come

**Wave 5: the pipeline.**
* 13 The pipeline, step by step (needs 7, 8, 10–12). The chapter every later one hangs off. Big enough for two passes: the main flow, then the edge cases.
* 14 Normalization (needs 7, 13).
* Then revise 15 GSUB against 10–14. It’s drafted, but it was written before them, and some of what it explains in passing now has a chapter of its own.

**Wave 6: positioning, and vertical text.**
* 16 GPOS: positioning glyphs (needs 15, and 29 for the Device and VariationIndex tables in value records and anchors).
* 17 Fallbacks and 18 Legacy kern, after 16.
* 19 Vertical text, after 16 (needs 6’s vertical metrics, 13, 15 and 16).

**Wave 7: scripts.**
* 20 Joining scripts and 21 Hebrew, Thai, Lao and Hangul (need 13–17).
* 22 The Indic model. Big enough for two passes.
* 23 Khmer and Myanmar, and 24 The Universal Shaping Engine (both grew from 22).
* 25 Dotted circles and broken clusters, last: it gathers what 22–24 do.

**Wave 8: AAT, and a pass over Variations.**
* 26 AAT inside HarfBuzz (needs the whole of Part IV; compares morx with GSUB), then 27 AAT positioning (compares kerx and trak with GPOS and kern).
* Revise 28–31 against what now links to them: chapters 5 and 6 (metrics, named instances), 10 and 11 (FeatureVariations) and 16 (Device tables in GPOS).

**Wave 9: drawing.**
* 32 Drawing outlines (needs 30, drafted), then 33 Color and 34 Rendering.

**Wave 10: writing fonts.**
* 36 Writing tables before 35 Subsetting: the serializer and repacker are the machinery subsetting uses. They keep their places in the book. Subsetting is big enough for two passes.
* 37 Instancing (needs 28–30, drafted, and 35) and 38 hb-depend (needs 35).

**Wave 11: around HarfBuzz.**
* 39 Other tables (needs only Part I; it can be written earlier, in any wave, if a writer is free).
* 40 For applications and 41 Testing HarfBuzz. 41 includes the possible bugs in `upstream-bug-reports.md`, so file or settle those first, so the chapter can say what happened to them.
* 42 The family, last: it is mostly about other projects, and needs the strictest sourcing (see `writing-brief.md`).

**Appendices, last.** A (Reading HarfBuzz’s C++) can be written any time after Part I, and is worth having early: later chapters can point to it instead of explaining `hb_set_t` or the pipe syntax. B (compile-time configuration), C (regenerating the tables) and D (limits) gather what the chapters mention: keep a running list of `HB_NO_*` macros, generators and limits from the writers’ reports, so they are compiled rather than researched again.

## Wave 12: Behdad Esfahbod’s suggestions

The waves above use the chapter numbers of the time. From here on, numbers are those in `outline.md` after this wave: a new Part I, Getting started (1 Why shaping exists, 2 Building HarfBuzz, 3 The command-line tools), which moves every other chapter on by two; Rendering split into 36–38; 46 HarfRust added; and, later, Part XI split into XI Using HarfBuzz (43 For applications, 44 Integrations, new, 45 Other tables) and XII HarfBuzz and its relatives (46 Testing, 47 HarfRust, 48 The family).

1. **36 hb-raster, 37 hb-vector, 38 hb-gpu,** split from `rendering.md`, each in two parts, outlines then color glyphs. Mostly reorganizing, with every source local. hb-raster also spells out what it doesn’t do, hinting above all, and how FreeType (or Skrifa) fills the gap. Split `fonts/rendering/` to match.
2. **2 Building HarfBuzz.** Then point appendix B, appendix C and 36–38 to it where they mention building or `harfbuzz-world.cc`.
3. **3 The command-line tools,** which uses 2’s build. Then trim the tool notes in 36–38 to links, and point `front/notation.md` and the preface to it. Both chapters come before Foundations, so check that they don’t lean on what only later chapters explain; where they must mention it, link ahead.
4. **47 HarfRust.** Clone HarfRust at the release in step with 15.1.0, and add a `harfrust` build of HarfBuzz to `tools/build-harfbuzz.sh` (2 shows how). Run the book’s `shape` examples through it. Sort each difference by whether it comes from a HarfBuzz change made after the version HarfRust says it’s synced to (NEWS and the git log between the two will show). Those are only HarfRust being behind: give their number and the reason in a sentence, not one by one (Behdad Esfahbod: don’t “care about small differences of behavior that are just HR still behind the changes since last HB release”). Report the rest, the real divergences, like the upstream bugs. Then cut 48’s section to a paragraph, and point chapter 11’s `harfrust` backend section to it.

5. **44 Integrations**, after 2 (it builds on Building’s dependencies and 36’s hinting with FreeType).

Each is reviewed before the next starts. After the wave: update `book/toc.txt` (the new part and chapters), the introduction’s tour of the parts (`front/introduction.md`, which names Parts I–X) and the one part number in chapter 1, regenerate `notes/index-terms.md`, check `notes/index-notes.md`, rebuild the PDF, publish.
