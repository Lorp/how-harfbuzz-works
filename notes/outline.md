# Outline

Drawn from the survey of HarfBuzz 15.1.0 (`notes/survey/`). Chapter titles are working titles. ✓ marks a chapter that has a draft.

## Part I: Foundations

1. **Why shaping exists.** Characters, glyphs and clusters; how Uniscribe, ATSUI, ICU and Pango led to HarfBuzz.
2. **Fonts as bytes.** Structs laid over bytes, offsets that know their targets, Null objects, the dispatch pattern.
3. **Trust nothing: the sanitizer.** It checks everything once, at load. Since 12.3 it repairs nothing: a bad table is dropped whole. Some GPOS checks wait until use.
4. **Blobs, faces and lazy tables.** Loading tables on demand, without locks; failed loads cached as Null.
5. **Fonts and font functions.** Tiers and sub-fonts, synthetic bold and slant, hb-ot as the default, fontations.
6. **Where metrics come from.** hmtx and HVAR, phantom points, extents.

## Part II: Text in

7. **Unicode inside HarfBuzz.** The UCD tables, the per-glyph Unicode properties, default ignorables and the "hidden" ones.
8. **Buffers.** Glyph info and positions, the scratch fields reused during shaping, flags, the four cluster levels (GRAPHEMES is new).
9. **hb_shape and its backends.** Why `ot` always wins; harfrust, wasm, graphite2, and the platform shapers that run only when asked for by name.

## Part III: Planning

10. **Shape plans and their cache.** What the cache key holds and what it leaves out (variation coordinates, feature ranges).
11. **From features to lookups.** hb_ot_map: stages, mask bits (and features silently dropped when they run out), `Harf`/`Buzz`, `rvrn`'s own stage, FeatureVariations.
12. **Choosing a script shaper.** The font's script tag picks the shaper, not only the text.

## Part IV: The pipeline

13. **The pipeline, step by step.** One run followed through `--trace`, from reversal into native order to hiding default ignorables.
14. **Normalization.** Decompose, reorder, recompose, done against the font's cmap (the cmap lookup happens here).
15. **Substituting glyphs: GSUB.** ✓ (`book/chapters/gsub.md`)
16. **Positioning glyphs: GPOS.** Value records, anchors, mark attachment, cursive chains, how attachments are resolved at the end.
17. **Fallbacks.** Shaping with no GSUB, no GPOS or no kern: fallback marks, spaces and kerning.
18. **Legacy `kern`.** Which shapers still apply it (since 12.2, not Thai or Indic).

## Part V: Scripts

19. **Joining scripts.** Arabic joining, fallback shaping from presentation forms, `stch`, joining scripts under USE.
20. **Hebrew, Thai, Lao and Hangul.**
21. **The Indic model.** Categories, Ragel syllable machines, reordering, and how the font's own lookups decide what is a base.
22. **Khmer and Myanmar.**
23. **The Universal Shaping Engine.** Microsoft's data and HarfBuzz's overrides, the grammar, reordering.
24. **Dotted circles and broken clusters.** The four insertion paths, and vowel constraints.

## Part VI: Apple Advanced Typography

25. **AAT inside HarfBuzz.** There is no separate AAT shaper. When morx is used, GSUB isn't. The state-machine driver, morx's five subtable kinds, `feat` and `ltag`, kerx and `ankr`, `trak`.

## Part VII: Variations

26. **Design space.** fvar, avar 1 and 2, normalized coordinates.
27. **Deltas.** Item variation stores, HVAR, VVAR, MVAR.
28. **Varying outlines.** gvar, IUP, phantom points, cvar.
29. **Variable components.** VARC, and its hidden axes.

## Part VIII: Drawing

30. **Drawing outlines.** glyf (including cubic GLYF), CFF and CFF2 charstrings, the draw API, the shared work budget.
31. **Colour.** The paint API, COLR v0 and v1, CPAL, CBDT, sbix, SVG.
32. **Rendering.** hb-raster, hb-vector (SVG and PDF), hb-gpu.

## Part IX: Writing fonts

33. **Subsetting.** Plans and closures, which run in fixed stages, not to a fixpoint.
34. **Writing tables.** The serializer and the repacker.
35. **Instancing.** Pinning and limiting axes.
36. **hb-depend.** The glyph dependency graph.

## Part X: Around HarfBuzz

37. **For applications.** Clusters, safe-to-break, line breaking and reshaping.
38. **Testing HarfBuzz.** Tracing, buffer verification, the test suites, fuzzing.
39. **The family.** HarfRust, and HarfBuzz in browsers and toolkits.

## Appendices

* Compile-time configuration (`HB_NO_*`, `HB_OPTIMIZE_SIZE`, `HB_BUFFER_MESSAGE_MORE`)
* Regenerating the Unicode and shaping tables
* Limits (`hb-limits.hh`)
