# Outline

Drawn from the survey of HarfBuzz 15.1.0 (`notes/survey/`). Chapter titles are working titles; `book/toc.txt` has the current ones. ✓ marks a chapter that has a draft, and … one being written.

## Part I: Getting started

1. **Why shaping exists.** ✓ Characters, glyphs and clusters; how Uniscribe, ATSUI, ICU and Pango led to HarfBuzz.
2. **The command-line tools.** New. `hb-shape` in depth (output format and its switches, `--features` and `--variations` syntax, `--unicodes`, `--trace`, `--verify`, buffer and cluster options, batch mode); `hb-view`, `hb-info`, `hb-subset`, `hb-vector`, `hb-raster`, `hb-gpu`, `hb-subset-depend`; the options they share (`util/`); and recipes for answering questions about a font. `front/notation.md` points here.
3. **Quick start: shaping text, then drawing it.** New (18 November 2026). One line of text drawn as SVG and as PNG: with `hb-vector` and `hb-raster`; in C with libharfbuzz-vector and libharfbuzz-raster; in JavaScript with harfbuzzjs (SVG in Node, a canvas demo in the browser); in Rust with HarfRust, Skrifa and tiny-skia. The programs are in `examples/quick-start/`, compiled and run by the build. Later chapters in the outline are numbered as before, one less than in the book.
4. **Building HarfBuzz.** New. Setting up a build to work on HarfBuzz, in the order a developer does it: the source and what in it is generated; a first build with Meson and Ninja (explained from scratch: this is the first chapter to use them, and later chapters will link here for them), and what it makes (the libraries and their `.pc` files, `util/`, the tests); a development build (debug, `b_sanitize`, `experimental_api`, `compile_commands.json`, ccache); a second build for traces, with `HB_DEBUG_*` compiled in (this book’s `tools/build-harfbuzz.sh` as the worked example); working in the tree (tools from `build/util`, `meson test`, regenerating tables); and, briefly, builds to ship: optional backends and dependencies (FreeType among them, needed for hinting), the single-file builds (`harfbuzz.cc`, `harfbuzz-subset.cc`, `harfbuzz-world.cc` with `HB_FEATURES_H`, `gen-harfbuzz-world.py`), cutting the library down, CMake, WebAssembly, MinGW. Options are named where they’re needed; the full lists stay in the appendix Compile-time configuration. Moved after Quick start on 19 November 2026, since most readers can skip it.

## Part II: Foundations

4. **Fonts as bytes.** ✓ Structs laid over bytes, offsets that know their targets, Null objects, the dispatch pattern.
5. **Trust nothing: the sanitizer.** ✓ It checks everything once, at load. Since 12.3 it repairs nothing: a bad table is dropped whole. Some GPOS checks wait until use.
6. **Blobs, faces and lazy tables.** ✓ Loading tables on demand, without locks; failed loads cached as Null.
7. **Fonts and font functions.** ✓ Tiers and sub-fonts, synthetic bold and slant, hb-ot as the default, fontations.
8. **Where metrics come from.** ✓ hmtx and HVAR, phantom points, extents.

## Part III: Text in

9. **Unicode inside HarfBuzz.** ✓ The UCD tables, the per-glyph Unicode properties, default ignorables and the “hidden” ones.
10. **Buffers.** ✓ Glyph info and positions, the scratch fields reused during shaping, flags, the four cluster levels.
11. **hb_shape and its backends.** ✓ Why `ot` always wins; harfrust, wasm, graphite2, kbts, and the platform shapers that run only when asked for by name.

## Part IV: Planning

12. **Shape plans and their cache.** ✓ What the cache key holds and what it leaves out (variation coordinates, feature ranges).
13. **From features to lookups.** ✓ hb_ot_map: stages, mask bits (and features silently dropped when they run out), `rvrn`’s own stage, FeatureVariations.
14. **Choosing a script shaper.** ✓ The font’s script tag picks the shaper, not only the text.

## Part V: The pipeline

15. **The pipeline, step by step.** ✓ One run followed through `--trace`, from reversal into native order to hiding default ignorables.
16. **Normalization.** ✓ Decompose, reorder, recompose, done against the font’s cmap (the cmap lookup happens here).
17. **GSUB: substituting glyphs.** ✓ (`book/chapters/gsub.md`)
18. **GPOS: positioning glyphs.** ✓ Value records, anchors, mark attachment, cursive chains, how attachments are resolved at the end.
19. **Fallbacks.** ✓ Shaping with no GSUB, no GPOS or no kern: fallback marks, spaces and kerning.
20. **Legacy `kern`.** ✓ Which shapers still apply it (since 12.2, not Thai or Indic).
21. **Vertical text.** ✓ Vertical metrics and origins, `vert` and `vrt2` (and the special search for a `vert` feature, `hb-ot-shape.cc:383`), the fallback to vertical presentation forms (`vertical_char_for`), and how a top-to-bottom run moves through the pipeline. Builds on chapter 8’s vertical metrics.

## Part VI: Scripts

22. **Joining scripts.** ✓ Arabic joining, fallback shaping from presentation forms, `stch`, joining scripts under USE.
23. **Hebrew, Thai, Lao and Hangul.** ✓
24. **The Indic model.** ✓ Categories, Ragel syllable machines, reordering, and how the font’s own lookups decide what is a base.
25. **Khmer and Myanmar.** ✓
26. **The Universal Shaping Engine.** ✓ Microsoft’s data and HarfBuzz’s overrides, the grammar, reordering.
27. **Dotted circles and broken clusters.** ✓ The four insertion paths: at the start of text, broken syllables, Hangul tone marks, and the vowel constraints.

## Part VII: Apple Advanced Typography

28. **AAT inside HarfBuzz.** ✓ There is no separate AAT shaper. When morx is used, GSUB isn’t. The state-machine driver, morx’s five subtable kinds, `feat` and `ltag`.
29. **AAT positioning.** ✓ kerx and its subtable formats, `ankr`, `trak`, and when they are used instead of GPOS and `kern`.

## Part VIII: Variations

30. **Design space.** ✓ fvar, avar 1 and 2, normalized coordinates.
31. **Deltas.** ✓ Item variation stores, HVAR, VVAR, MVAR.
32. **Varying outlines.** ✓ gvar, IUP, phantom points, cvar.
33. **VARC: variable components.** ✓ VARC, and its hidden axes.

## Part IX: Drawing

34. **Drawing outlines.** ✓ glyf (including cubic GLYF), CFF and CFF2 charstrings, the draw API, the shared work budget.
35. **Color.** ✓ The paint API, COLR v0 and v1, CPAL, CBDT, sbix, SVG.

Rendering (drafted as one chapter, `rendering.md`) is being split into one chapter per library, at Behdad Esfahbod’s suggestion: a reader who wants one may not want to read about the others. Each opens with a short paragraph on what the three libraries are, so it can be read alone, and each is in two parts, outlines first and color glyphs second, so a reader who only draws ordinary text can stop halfway. Building them moves to Building HarfBuzz (now chapter 4), and their tools to The command-line tools (chapter 2).

36. **hb-raster: rendering to pixels.** *Outlines:* flattening, analytic coverage and the nonzero winding rule, the A8 image (layout, extents, transform), the edge limit, and checking against FreeType with `hb-ft-raster`. Then, spelled out, what it doesn’t do: no hinting of any kind (no TrueType bytecode interpreter, no autohinter, no CFF hints), no gamma correction, no LCD subpixel rendering, no stem darkening. Text that needs hinting needs FreeType, or Skrifa, beside HarfBuzz: how to pair them (`hb-ft`, its load flags, hinted advances), and when hinting still matters. The Raster Tragedy (`resources/raster-tragedy/`) is the background to point to. *Color glyphs:* the surface, clip and transform stacks, groups and the 28 composite modes, gradients, images, palettes, foreground and background, BGRA output and PNG, the pixel budget. Assumes chapter 35.
37. **hb-vector: rendering to SVG and PDF.** *Outlines:* paths in SVG, ids and the prefix, limits. *Color glyphs:* color glyphs in SVG and the compositing modes it can and can’t express, then PDF.
38. **hb-gpu: rendering on the GPU.** *Outlines:* encoding outlines for the GPU, and the shaders. *Color glyphs:* painting on the GPU, its limits.

## Part X: Writing fonts

39. **Subsetting.** ✓ Plans and closures, which run in fixed stages, not to a fixpoint.
40. **Writing tables.** ✓ The serializer and the repacker.
41. **Instancing.** ✓ Pinning and limiting axes.
42. **hb-depend: the glyph dependency graph.** ✓

## Part XI: Using HarfBuzz

What an application does with HarfBuzz: using its output, plugging it into other libraries, and the tables it reads for applications; and what a font maker does with it: testing fonts.

43. **For applications.** ✓ Clusters, safe-to-break, line breaking and reshaping.
44. **Integrations: FreeType, cairo, ICU and the platforms.** New. HarfBuzz’s integration layers, each with what it adds and when to use it: `hb-ft` (FreeType faces and font funcs, load flags, hinted metrics), `hb-cairo`, `hb-icu` and `hb-glib` (Unicode functions), `hb-coretext`, `hb-directwrite`, `hb-uniscribe` and `hb-gdi` (platform faces, font funcs and shapers), `hb-graphite2`, `hb-gobject` (introspection, and through it the Python and JavaScript bindings), and the other language bindings. Links chapter 7 (font funcs), chapter 11 (backends) and chapter 36 (hinting with FreeType); doesn’t repeat them.
45. **Other tables.** ✓ MATH (`hb-ot-math`), BASE (baselines), STAT (through `hb-style`), `name` and `meta`: the tables HarfBuzz reads for applications rather than for shaping.
46. **Testing and debugging fonts with HarfBuzz.** ✓ (drafted 20 November 2026; debugging added first, as the way in, the same day). For font makers and font engineers. First, a method for a font that doesn’t work: reproduce it with `hb-shape` and the application’s settings, find the step (`hb-info`, `--trace`, features off one at a time), decide whose problem it is (other engines and releases), cut it down (`hb-subset`, then the feature file) into a font a bug report can use, and keep the case as a test. Then regression tests, not HarfBuzz’s developers (who have Testing HarfBuzz, chapter 47; each chapter links to the other). HarfBuzz as the reference most software shapes with, so “does my font shape right?” mostly means “does HarfBuzz shape it as intended?”. Covers, all through HarfBuzz’s own tools and output: test strings and expected `hb-shape` output, recorded once, checked by eye, and rerun on every build of the font (the `.tests` format and `--batch`, as HarfBuzz’s own suite uses them; a small script that diffs the results); `--verify` and the unsafe-to-break flags, for lookups that differ when text is shaped in pieces or broken across lines; `--trace` to find the lookup behind a changed result; comparing against another HarfBuzz version, the platform shapers through `--shapers` (`coretext`, `directwrite`, `uniscribe`, where built), and HarfRust; variable fonts at named instances and at the corners of the design space; per-script and per-language runs (`--script`, `--language`), including the dotted circles that mark broken clusters; and proofs with `hb-view`, `hb-raster`, and `hb-vector`. A worked example on one of the book’s fonts, every result a live block. Out of scope: font QA that HarfBuzz isn’t part of (outlines, metadata, spacing, most of fontbakery), in a paragraph saying where those tools are. Links The command-line tools for the switches, and doesn’t repeat them.
    *The boundary with The command-line tools (chapter 2).* That chapter is the reference: what each tool and switch does, and recipes for questions asked once, about one font, at one moment (“What does HarfBuzz do with this?”). This one is a method: a suite of cases rerun on every build of the font (“Does my font still do what it should?”). So this chapter never explains a switch, and links to the reference instead. Its own material is what to test (strings for each script, edge cases, the corners of the design space), recording expected output, comparing runs, deciding whether a change is a regression, comparing shapers and versions, and what a failure means. Where they meet: the recipe “Why didn’t this ligature form?” stays in chapter 2, and this chapter uses `--trace` only once a test has failed, linking to that recipe for how to read one; chapter 2 says what `--verify` and `--batch` do, and this chapter why a test suite uses them. The command-line tools chapter should link here from its recipes and from Verifying and Many runs.

## Part XII: HarfBuzz and its relatives

47. **Testing HarfBuzz.** ✓ How HarfBuzz itself is tested, for its developers and contributors: tracing, buffer verification, the test suites, fuzzing, testing a rule with a small font of your own, and what the possible bugs found while writing this book suggest about where bugs are left. The bugs themselves are in the appendix Bugs this book found (moved there 20 November 2026). Testing and debugging a font is chapter 46.
48. **HarfRust.** New, from the section in chapter 49. Where it came from (rustybuzz); how it’s ported and kept in step with HarfBuzz; reading fonts with `read-fonts` and `skrifa` instead of a sanitizer; what it covers and leaves to other crates; its Rust API; its C API and HarfBuzz’s `harfrust` backend; a section on fontations, the Rust font stack it’s built on (`read-fonts`, `skrifa` and their siblings): what each crate does, memory-safe parsing as the alternative to a sanitizer (link chapter 5), Skrifa as a hinting engine (link chapter 36), and where fontations is used, every claim sourced in that project; speed; and every `shape` example in the book run through HarfRust too, with differences reported. Needs the HarfRust source, pinned to the release in step with HarfBuzz 15.1.0, and a HarfBuzz build with the `harfrust` backend.
49. **The family.** ✓ HarfBuzz in browsers and toolkits; HarfRust cut to a paragraph pointing to chapter 48. Mentions, from `README.md`, the widely used closed programs that use HarfBuzz (Adobe’s among them) alongside the open ones it examines; done.

## Appendices

* A. ✓ Reading HarfBuzz’s C++: the containers (`hb_set_t`, `hb_map_t`, `hb_vector_t`), iterators and pipes (`+ iter | hb_apply (…)`), `hb-meta.hh`, and the other idioms the source is written in. Chapter 4 covers the table structs; this covers the rest. When written, name the file `reading-harfbuzz-cpp.md`.
* B. ✓ Compile-time configuration (`HB_NO_*`, `HB_OPTIMIZE_SIZE`, `HB_BUFFER_MESSAGE_MORE`, the Meson options): the reference that Building HarfBuzz points to.
* C. ✓ Regenerating the Unicode and shaping tables
* D. ✓ Limits (`hb-limits.hh`)
* ✓ Bugs this book found: the draft bug reports from `notes/upstream-bug-reports.md` in tables, each with its chapter, how it was checked, and what happened upstream. Moved out of Testing HarfBuzz, which keeps a paragraph and “Where the bugs are”. The last appendix, so the others keep their letters.
