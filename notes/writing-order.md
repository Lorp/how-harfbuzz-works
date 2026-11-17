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
* Brought forward from wave 9, since Part VIII doesn’t depend on Part V: 32 (Drawing outlines) and 33 (Colour), being written; 34 (Rendering) waits for both.

## To come

**Wave 5: the pipeline.**
* 13 The pipeline, step by step (needs 7, 8, 10–12). The chapter every later one hangs off. Big enough for two passes: the main flow, then the edge cases.
* 14 Normalization (needs 7, 13).
* Then revise 15 GSUB against 10–14. It’s drafted, but it was written before them, and some of what it explains in passing now has a chapter of its own.

**Wave 6: positioning, and vertical text.**
* 16 Positioning glyphs: GPOS (needs 15, and 29 for the Device and VariationIndex tables in value records and anchors).
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
* 32 Drawing outlines (needs 30, drafted), then 33 Colour and 34 Rendering.

**Wave 10: writing fonts.**
* 36 Writing tables before 35 Subsetting: the serializer and repacker are the machinery subsetting uses. They keep their places in the book. Subsetting is big enough for two passes.
* 37 Instancing (needs 28–30, drafted, and 35) and 38 hb-depend (needs 35).

**Wave 11: around HarfBuzz.**
* 39 Other tables (needs only Part I; it can be written earlier, in any wave, if a writer is free).
* 40 For applications and 41 Testing HarfBuzz. 41 includes the possible bugs in `upstream-bug-reports.md`, so file or settle those first, so the chapter can say what happened to them.
* 42 The family, last: it is mostly about other projects, and needs the strictest sourcing (see `writing-brief.md`).

**Appendices, last.** A (Reading HarfBuzz’s C++) can be written any time after Part I, and is worth having early: later chapters can point to it instead of explaining `hb_set_t` or the pipe syntax. B (compile-time configuration), C (regenerating the tables) and D (limits) gather what the chapters mention: keep a running list of `HB_NO_*` macros, generators and limits from the writers’ reports, so they are compiled rather than researched again.
