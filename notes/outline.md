# Outline

Drawn from the survey of HarfBuzz 15.1.0 (`notes/survey/`). Chapter titles are working titles; `book/toc.txt` has the current ones. ✓ marks a chapter that has a draft, and … one being written.

## Part I: Foundations

1. **Why shaping exists.** ✓ Characters, glyphs and clusters; how Uniscribe, ATSUI, ICU and Pango led to HarfBuzz.
2. **Fonts as bytes.** ✓ Structs laid over bytes, offsets that know their targets, Null objects, the dispatch pattern.
3. **Trust nothing: the sanitizer.** ✓ It checks everything once, at load. Since 12.3 it repairs nothing: a bad table is dropped whole. Some GPOS checks wait until use.
4. **Blobs, faces and lazy tables.** ✓ Loading tables on demand, without locks; failed loads cached as Null.
5. **Fonts and font functions.** ✓ Tiers and sub-fonts, synthetic bold and slant, hb-ot as the default, fontations.
6. **Where metrics come from.** ✓ hmtx and HVAR, phantom points, extents.

## Part II: Text in

7. **Unicode inside HarfBuzz.** ✓ The UCD tables, the per-glyph Unicode properties, default ignorables and the “hidden” ones.
8. **Buffers.** ✓ Glyph info and positions, the scratch fields reused during shaping, flags, the four cluster levels.
9. **hb_shape and its backends.** ✓ Why `ot` always wins; harfrust, wasm, graphite2, kbts, and the platform shapers that run only when asked for by name.

## Part III: Planning

10. **Shape plans and their cache.** ✓ What the cache key holds and what it leaves out (variation coordinates, feature ranges).
11. **From features to lookups.** ✓ hb_ot_map: stages, mask bits (and features silently dropped when they run out), `rvrn`’s own stage, FeatureVariations.
12. **Choosing a script shaper.** ✓ The font’s script tag picks the shaper, not only the text.

## Part IV: The pipeline

13. **The pipeline, step by step.** ✓ One run followed through `--trace`, from reversal into native order to hiding default ignorables.
14. **Normalization.** ✓ Decompose, reorder, recompose, done against the font’s cmap (the cmap lookup happens here).
15. **Substituting glyphs: GSUB.** ✓ (`book/chapters/gsub.md`)
16. **Positioning glyphs: GPOS.** ✓ Value records, anchors, mark attachment, cursive chains, how attachments are resolved at the end.
17. **Fallbacks.** ✓ Shaping with no GSUB, no GPOS or no kern: fallback marks, spaces and kerning.
18. **Legacy `kern`.** ✓ Which shapers still apply it (since 12.2, not Thai or Indic).
19. **Vertical text.** ✓ Vertical metrics and origins, `vert` and `vrt2` (and the special search for a `vert` feature, `hb-ot-shape.cc:383`), the fallback to vertical presentation forms (`vertical_char_for`), and how a top-to-bottom run moves through the pipeline. Builds on chapter 6’s vertical metrics.

## Part V: Scripts

20. **Joining scripts.** ✓ Arabic joining, fallback shaping from presentation forms, `stch`, joining scripts under USE.
21. **Hebrew, Thai, Lao and Hangul.** ✓
22. **The Indic model.** ✓ Categories, Ragel syllable machines, reordering, and how the font’s own lookups decide what is a base.
23. **Khmer and Myanmar.** ✓
24. **The Universal Shaping Engine.** ✓ Microsoft’s data and HarfBuzz’s overrides, the grammar, reordering.
25. **Dotted circles and broken clusters.** ✓ The four insertion paths: at the start of text, broken syllables, Hangul tone marks, and the vowel constraints.

## Part VI: Apple Advanced Typography

26. **AAT inside HarfBuzz.** ✓ There is no separate AAT shaper. When morx is used, GSUB isn’t. The state-machine driver, morx’s five subtable kinds, `feat` and `ltag`.
27. **AAT positioning.** ✓ kerx and its subtable formats, `ankr`, `trak`, and when they are used instead of GPOS and `kern`.

## Part VII: Variations

28. **Design space.** ✓ fvar, avar 1 and 2, normalized coordinates.
29. **Deltas.** ✓ Item variation stores, HVAR, VVAR, MVAR.
30. **Varying outlines.** ✓ gvar, IUP, phantom points, cvar.
31. **Variable components: VARC.** ✓ VARC, and its hidden axes.

## Part VIII: Drawing

32. **Drawing outlines.** ✓ glyf (including cubic GLYF), CFF and CFF2 charstrings, the draw API, the shared work budget.
33. **Colour.** ✓ The paint API, COLR v0 and v1, CPAL, CBDT, sbix, SVG.
34. **Rendering.** ✓ hb-raster, hb-vector (SVG and PDF), hb-gpu.

## Part IX: Writing fonts

35. **Subsetting.** ✓ Plans and closures, which run in fixed stages, not to a fixpoint.
36. **Writing tables.** ✓ The serializer and the repacker.
37. **Instancing.** ✓ Pinning and limiting axes.
38. **hb-depend.** ✓ The glyph dependency graph.

## Part X: Around HarfBuzz

39. **Other tables.** ✓ MATH (`hb-ot-math`), BASE (baselines), STAT (through `hb-style`), `name` and `meta`: the tables HarfBuzz reads for applications rather than for shaping.
40. **For applications.** ✓ Clusters, safe-to-break, line breaking and reshaping.
41. **Testing HarfBuzz.** ✓ Tracing, buffer verification, the test suites, fuzzing, and the possible bugs found while writing this book (`notes/upstream-bug-reports.md`), with what happened to them upstream.
42. **The family.** ✓ HarfRust, and HarfBuzz in browsers and toolkits.

## Appendices

* A. ✓ Reading HarfBuzz’s C++: the containers (`hb_set_t`, `hb_map_t`, `hb_vector_t`), iterators and pipes (`+ iter | hb_apply (…)`), `hb-meta.hh`, and the other idioms the source is written in. Chapter 2 covers the table structs; this covers the rest. When written, name the file `reading-harfbuzz-cpp.md`.
* B. ✓ Compile-time configuration (`HB_NO_*`, `HB_OPTIMIZE_SIZE`, `HB_BUFFER_MESSAGE_MORE`)
* C. ✓ Regenerating the Unicode and shaping tables
* D. ✓ Limits (`hb-limits.hh`)
