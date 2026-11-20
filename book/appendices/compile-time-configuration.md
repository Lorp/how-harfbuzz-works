# Compile-time configuration

HarfBuzz can be built without most of what it can do. A browser wants all of it; a game console that shapes one Latin font wants `hb_shape` and little else, and would rather not carry an AAT engine, a color-font painter, and a subsetter in its binary. Nearly every part of the library can be removed by defining a preprocessor macro, most of them named `HB_NO_` and the thing removed.

This appendix lists them. It starts with how the macros are processed, then the three ready-made sets of them, the macros that change speed and size rather than features, every `HB_NO_*` macro in the {{hb}} source, the other switches, and the Meson build options. Chapters that mention a macro link here; the table of `HB_NO_*` macros links back to the chapter that explains what each one removes.

HarfBuzz explains configuration itself in two places: its user manual’s [Configuration options](https://harfbuzz.github.io/building.html#configuration), for the Meson options, and [`CONFIG.md`](https://github.com/harfbuzz/harfbuzz/blob/{{hb}}/CONFIG.md), for the macros, as advice on small builds. This appendix is drawn from the source instead, `hb-config.hh` and `meson_options.txt`, so it lists everything in {{hb}}. In particular, the manual describes ten of the thirty-four Meson options, mostly the outside libraries HarfBuzz can use, and leaves out its own optional libraries and backends, such as `subset`, `raster`, and `harfrust`.

## How the macros are processed

All configuration goes through one header, `hb-config.hh`. `hb.hh` includes it before anything else it includes (`hb.hh:174`), and every source file includes `hb.hh` first, so every file sees the same answers. The header does its work in this order:

1. `config.h`, if the build system made one (`hb-config.hh:34`). Meson writes the `HAVE_*` macros there.
2. `HB_NO_SUBSET_DEPEND`, unless `HB_EXPERIMENTAL_API` is defined (`:38`).
3. The three tiers: `HB_TINY` (`:42`), which defines the other two, then `HB_LEAN` (`:56`) and `HB_MINI` (`:94`).
4. `HB_OPTIMIZE_SIZE`, if the compiler defines `__OPTIMIZE_SIZE__` (`:100`).
5. The first **override header** (`:106`).
6. The **closure of options** (`:113`), the header’s own name for it: umbrella macros define the narrower macros they stand for.
7. The second override header, `HB_CONFIG_OVERRIDE_LAST_H` (`:192`).
8. `HB_OPTIMIZE_SIZE_VAL`, the same setting as 0 or 1 for use in ordinary `if` statements (`:199`).

Implications flow down this list and never back up. `HB_MINI` defines `HB_NO_LEGACY` in step 3, and in step 6 `HB_NO_LEGACY` defines six narrower macros. Here are the two blocks, trimmed:

```c++
#ifdef HB_MINI
#define HB_NO_AAT
#define HB_NO_LEGACY
#define HB_NO_BEYOND_64K
#endif
...
#ifdef HB_NO_LEGACY
#define HB_NO_CMAP_LEGACY_SUBTABLES
#define HB_NO_FALLBACK_SHAPE
#define HB_NO_OT_KERN
#define HB_NO_OT_LAYOUT_BLOCKLIST
#define HB_NO_AAT_LAYOUT_BLOCKLIST
#define HB_NO_OT_SHAPE_FALLBACK
#endif
```

and `HB_NO_OT_SHAPE_FALLBACK` defines five more a few lines further on (`:174`). One macro on the command line can remove a dozen things.

**Undoing part of a tier.** There is no command-line way to say “`HB_MINI`, but keep `kern`” (`CONFIG.md` says so), so the override headers exist. Define `HB_CONFIG_OVERRIDE_H` as the name of a header, in quotes, and it is included at step 5. Defining `HAVE_CONFIG_OVERRIDE_H` instead includes `config-override.h`, the fixed name used up to 3.1.2. The position matters. At step 5 the tiers have run but the closure hasn’t, so `#undef HB_NO_LEGACY` there brings back everything `HB_NO_LEGACY` would have removed. But `#undef HB_NO_OT_KERN` there achieves nothing while `HB_NO_LEGACY` is still defined, because the closure defines it again at step 6. A narrow macro set by the closure can only be undone in the second header, `HB_CONFIG_OVERRIDE_LAST_H` (or `config-override-last.h` with `HAVE_CONFIG_OVERRIDE_LAST_H`), which runs after it. `CONFIG.md` documents only the first header.

**Defined is enough.** The `HB_NO_*` macros are tested with `#ifdef` and `#ifndef`, so their value is ignored: `-DHB_NO_VAR=0` removes variations just as `-DHB_NO_VAR` does. The exceptions, tested with `#if` or `if`, are `HB_USE_ATEXIT`, `HB_FAST_NUM_ACCESS`, `HB_BUFFER_MESSAGE_MORE`, and the `HB_DEBUG_*` levels, below.

**What removal looks like.** A macro takes code out in one of three ways, and often in all three:

* **Whole files.** `hb-ot-math.cc` is wrapped in `#ifndef HB_NO_MATH` from top to bottom (`hb-ot-math.cc:29`), so in such a build the `hb_ot_math_*` functions don’t exist. The public headers are not changed (the only `HB_NO_*` test in them is `HB_NO_SUBSET_DEPEND`, in `hb-subset-depend.h:73`), so a program that calls a removed function still compiles, and fails to link.
* **Early returns.** `_hb_preprocess_text_vowel_constraints` begins with `#ifdef HB_NO_OT_SHAPER_VOWEL_CONSTRAINTS return; #endif` (`hb-ot-shaper-vowel-constraints.cc:67`). The function is still there and still called; it just does nothing.
* **Table slots.** `hb-ot-face-table-list.hh` lists the tables a face keeps a lazy slot for, and many entries are guarded, so a face in a build without color has no slot for `COLR` at all ([Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#one-pointer-per-table)).

## The tiers

The three predefined sets are meant for size-constrained builds. `CONFIG.md` describes them as: `HB_MINI`, “a capable OpenType shaper only”; `HB_LEAN`, which “disables various non-shaping functionality in the library, as well as esoteric or rarely-used shaping features”; and `HB_TINY`, both of those and more. They are used like any other macro, with `meson setup build -Dcpp_args=-DHB_MINI -Dc_args=-DHB_MINI`.

| Tier | Defines | What is lost |
|---|---|---|
| `HB_MINI` | `HB_NO_AAT`, `HB_NO_LEGACY`, and `HB_NO_BEYOND_64K` (`hb-config.hh:94`) | AAT tables and shaping; the `kern` table; fallback mark positioning and kerning; the legacy-font paths in the Arabic, Hebrew, and Thai shapers, Zawgyi, and vowel constraints; the fallback shaper; the blocklists of broken fonts; symbol and Mac `cmap` handling; formats for more than 65,535 glyphs |
| `HB_LEAN` | 27 macros (`:56`), plus `HB_NO_COLOR`, `HB_NO_DRAW`, and `HB_NO_PAINT` unless a drawing library is in the build (`:85`) | variations; vertical text; color, drawing, and painting; the `MATH`, `meta`, `name`, `STAT`, and metrics APIs; buffer messages, serialization, and verification; reading fonts from files; Device-table hinting; glyph names; several rarely used layout functions; deprecated API; environment variables, `errno`, locales, and `atexit` |
| `HB_TINY` | `HB_LEAN` and `HB_MINI`, plus `HB_NO_SVG`, `HB_OPTIMIZE_SIZE`, `HB_OPTIMIZE_SIZE_MORE`, `HB_MINIMIZE_MEMORY_USAGE`, `HB_NO_MT`, `HB_NO_UCD_UNASSIGNED`, and `NDEBUG` (`:42`) | all of the above; thread safety; the speed-ups that cost size; the three caches; assertions; exact Unicode properties for unassigned code points |

`HB_LEAN`’s 27 are `HB_DISABLE_DEPRECATED`, `HB_NO_ATEXIT`, `HB_NO_BUFFER_MESSAGE`, `HB_NO_BUFFER_SERIALIZE`, `HB_NO_BUFFER_VERIFY`, `HB_NO_BITMAP`, `HB_NO_ERRNO`, `HB_NO_FACE_COLLECT_UNICODES`, `HB_NO_GETENV`, `HB_NO_HINTING`, `HB_NO_LAYOUT_FEATURE_PARAMS`, `HB_NO_LAYOUT_COLLECT_GLYPHS`, `HB_NO_LAYOUT_RARELY_USED`, `HB_NO_LAYOUT_UNUSED`, `HB_NO_MATH`, `HB_NO_META`, `HB_NO_METRICS`, `HB_NO_MMAP`, `HB_NO_NAME`, `HB_NO_OPEN`, `HB_NO_OT_FETCH`, `HB_NO_OT_FONT_GLYPH_NAMES`, `HB_NO_SETLOCALE`, `HB_NO_STYLE`, `HB_NO_SUBSET_DEPEND`, `HB_NO_VERTICAL`, and `HB_NO_VAR`.

Two consequences are easy to miss. `HB_NO_DRAW` implies `HB_NO_OT_FONT_CFF` (`:139`), so a lean build without a drawing library has no glyph extents or glyph names from CFF fonts, as well as no outlines (`hb-ot-font.cc:831`, `:863`). And `HB_NO_STYLE` turns off `trak` ([AAT positioning](aat-positioning.html#when-it-applies)), because tracking is applied only when the font also has a `STAT` table (`hb-ot-shape.cc:213`).

**When `HB_LEAN` keeps drawing.** The test at `hb-config.hh:85` asks whether any of `HAVE_CAIRO`, `HAVE_RASTER`, `HAVE_VECTOR`, and `HAVE_GPU`, or the `HB_HAS_*` macros of the same names, is defined. The `HAVE_*` macros are what Meson writes in `config.h`; the `HB_HAS_*` ones come from `hb-features.h`, the header Meson generates for applications, which `harfbuzz-world.cc`, the single-file build, includes if `HB_FEATURES_H` names it (`harfbuzz-world.cc:1`). So in a Meson build with a renderer, `HB_LEAN` keeps drawing, painting, and color. Before 15.2.0 the test asked only for the `HB_HAS_*` macros, which no library source sees in a Meson build, so there `HB_LEAN` always removed them ([HHW-55](bugs-this-book-found.html#hhw-55)).

Many macros belong to no tier. Some are for unusual builds (`HB_NO_OT_SHAPE` for a library with only the Core Text backend, `HB_NO_UCD` for one that brings its own Unicode data); others are single features nobody has grouped: `HB_NO_AVAR2`, `HB_NO_BASE`, `HB_NO_CFF`, `HB_NO_EMOJI_SEQUENCES`, `HB_NO_LANGUAGE_LONG`, `HB_NO_OT_SHAPE_FRACTIONS`, `HB_NO_SUBSET_LAYOUT`, `HB_NO_WIN1256`, and more. The table below marks them “—” in the third column.

## Size and speed

Four macros change how the code is compiled rather than what it can do.

**`HB_OPTIMIZE_SIZE`** trades speed for size. It is defined automatically whenever the compiler defines `__OPTIMIZE_SIZE__` (`hb-config.hh:100`), which GCC and Clang do under `-Os` and `-Oz`, and so under Meson’s `--buildtype=minsize`. `CONFIG.md` recommends that for size-constrained builds and notes that Chrome builds HarfBuzz that way. It is tested in about 40 places:

| What changes | Where |
|---|---|
| `HB_ALWAYS_INLINE` is dropped from hot functions, leaving inlining to the compiler | the sanitizer’s range checks (`hb-sanitize.hh:269`), the skipping iterator and `match_input`, `match_backtrack`, `match_lookahead` (`hb-ot-layout-gsubgpos.hh:939`–`:2359`), `unsafe_to_concat` (`hb-buffer.hh:526`), `Coverage::sanitize`, the priority queue |
| loops unrolled four times are left rolled | delta decoding and adding (`hb-open-type.hh:1814`–`:2094`), `gvar` (`hb-ot-var-gvar-table.hh:713`) |
| smaller, slower lookup tables | the Unicode tables (`hb-ucd-table.hh:764`) and the USE categories (`hb-ot-shaper-use-table.hh:107`): [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-sizes), [The Universal Shaping Engine](universal-shaping-engine.html#where-they-come-from) |
| fast paths that test for special cases are skipped | context rule sets search linearly (`hb-ot-layout-gsubgpos.hh:3494`); ligature sets don’t filter on the second glyph (`LigatureSet.hh:101`, [GSUB](gsub.html#the-second-glyph-fast-path)); the region scalar doesn’t skip zero peaks eight bytes at a time (`hb-ot-var-common.hh:161`); hashing doesn’t take an aligned path (`hb-algs.hh:475`) |

The AAT state-machine transitions were on this list in 15.1.0, with a comment that forcing them inline “is worth 3-10% instructions on morx/kerx-heavy fonts, for about 16KB of code”. In 15.2.0 they are forced inline in every build (`hb-aat-layout-morx-table.hh:87`, `hb-aat-layout-kerx-table.hh:284`).

**`HB_OPTIMIZE_SIZE_MORE`**, set only by `HB_TINY`, goes a little further: it defines `HB_NO_OT_RULESETS_FAST_PATH` (`hb-config.hh:182`), which turns the rule-set and ligature fast paths off even without `HB_OPTIMIZE_SIZE`, and drops the `fasthash32` specialization of byte-array hashing (`hb-array.hh:510`).

**`HB_MINIMIZE_MEMORY_USAGE`**, also `HB_TINY` only, defines `HB_NO_GDEF_CACHE`, `HB_NO_OT_LAYOUT_LOOKUP_CACHE`, and `HB_NO_OT_FONT_CMAP_CACHE` (`:186`), removing the three caches that face and lookup accelerators allocate. It has no `_VAL` form: 15.1.0 defined one and never used it, and 15.2.0 removes it ([HHW-57](bugs-this-book-found.html#hhw-57)).

**`HB_FAST_NUM_ACCESS`** says whether big-endian numbers in font data can be read with one load and a byte swap rather than byte by byte. `hb-algs.hh:116` turns it on when optimizing, on big-endian machines or little-endian ones with the `__builtin_bswap` builtins, and off for GCC 12 and older (issue 5456). It can be preset to 0 or 1.

## Every HB_NO_ macro

These are all the `HB_NO_*` macros that the {{hb}} source in `src/` tests or defines, 82 of them. “Set by” gives the macros that define this one directly, with the tier they belong to; “—” means only by hand. Line numbers without a file are in `hb-config.hh`.

<div class="macros">

| Macro | What it removes | Set by | Explained in |
|---|---|---|---|
| `HB_NO_AAT` | the AAT table slots (`morx`, `mort`, `kerx`, `ankr`, `trak`, `ltag`, `feat`), and with them AAT shaping and the `feat`/`ltag` API | `HB_MINI` | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#feat-and-ltag) |
| `HB_NO_AAT_LAYOUT_BLOCKLIST` | the check for known-broken `morx` tables | `HB_NO_LEGACY` (`HB_MINI`) | [Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html#a-list-of-known-bad-fonts) |
| `HB_NO_AAT_SHAPE` | applying `morx`, `mort`, `kerx`, and `trak`, the public `hb_aat_layout_*` functions, and `kern` formats 1 and 3 | `HB_NO_AAT`, `HB_NO_OT_SHAPE`, `HB_NO_SHAPER` | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#when-morx-is-used), [AAT positioning](aat-positioning.html) |
| `HB_NO_ATEXIT` | freeing lazily made static objects at exit (`hb.hh:489`) | `HB_LEAN` | — |
| `HB_NO_AVAR2` | `avar` version 2 (`hb-ot-var-avar-table.hh:636`) | — | [Design space](design-space.html#avar-version-2) |
| `HB_NO_BASE` | the `BASE` table: `hb_ot_layout_get_baseline` and friends, and its subsetting | — | [Other tables](other-tables.html) |
| `HB_NO_BEYOND_64K` | 24-bit glyph IDs and offsets: Coverage formats 3 and 4, the wide lookup formats, `COLR`’s PaintGlyph format 33, 24-bit composite components in `glyf`, `cmap` format 15 | `HB_MINI` | [Fonts as bytes](fonts-as-bytes.html#smalltypes-and-mediumtypes) |
| `HB_NO_BITMAP` | nothing directly: an umbrella for `HB_NO_OT_FONT_BITMAP` | `HB_LEAN` | [Color](color.html#bitmaps-sbix-and-cbdt) |
| `HB_NO_BUFFER_MESSAGE` | the message callback and every message sent (`hb-buffer.hh:132`) | `HB_LEAN` | [Buffers](buffers.html#messages) |
| `HB_NO_BUFFER_SERIALIZE` | `hb_buffer_serialize*` and `hb_buffer_deserialize*` (`hb-buffer-serialize.cc:29`) | `HB_LEAN` | [Buffers](buffers.html#comparing-and-writing-out) |
| `HB_NO_BUFFER_VERIFY` | `HB_BUFFER_FLAG_VERIFY`’s checks (`hb-buffer-verify.cc:29`) | `HB_LEAN` | [Buffers](buffers.html#verification) |
| `HB_NO_CFF` | the `CFF ` and `CFF2` slots, and so CFF outlines, extents, and subsetting | — | [Drawing outlines](drawing-outlines.html#cff-and-cff2-running-charstrings) |
| `HB_NO_CMAP_LEGACY_SUBTABLES` | the special handling of symbol (3,0), MacRoman, and other Mac `cmap` subtables, including the Arabic PUA maps (`hb-ot-cmap-table.hh:2249`) | `HB_NO_LEGACY` (`HB_MINI`) | [Joining scripts](joining-scripts.html#legacy-encodings) |
| `HB_NO_COLOR` | the `COLR`, `CPAL`, `CBDT`, `sbix`, and `SVG ` slots and `hb-ot-color.cc` | `HB_LEAN`, if no drawing library | [Color](color.html#compiled-out) |
| `HB_NO_DRAW` | the draw API (`hb-draw.cc`) and every font funcs’ outline callback | `HB_LEAN`, if no drawing library | [Drawing outlines](drawing-outlines.html#the-draw-api) |
| `HB_NO_EMOJI_SEQUENCES` | keeping an Extended_Pictographic character after a ZWJ in the same cluster (`hb-ot-shape.cc:515`) | — | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#continuations-just-enough-of-graphemes) |
| `HB_NO_ERRNO` | `<cerrno>`: `errno` becomes a dummy variable (`hb.hh:449`) | `HB_LEAN`; old Windows CE (`hb.hh:433`) | — |
| `HB_NO_FACE_COLLECT_UNICODES` | `hb_face_collect_unicodes`, `hb_face_collect_nominal_glyph_mapping`, and the two variation-selector collectors (`hb-face.cc:970`) | `HB_LEAN` | — |
| `HB_NO_FALLBACK_SHAPE` | the `fallback` backend (`hb-shaper-list.hh:68`) | `HB_NO_LEGACY` (`HB_MINI`) | [hb_shape and its backends](hb_shape-and-its-backends.html#fallback) |
| `HB_NO_GDEF_CACHE` | GDEF’s cache of glyph properties and its mark-glyph-set bitmaps (`GDEF.hh:993`) | `HB_MINIMIZE_MEMORY_USAGE` (`HB_TINY`) | [GSUB](gsub.html#glyph-properties) |
| `HB_NO_GETENV` | reading `HB_SHAPER_LIST`, `HB_FONT_FUNCS`, and `HB_FACE_LOADER`: `getenv` returns null (`hb.hh:445`) | `HB_LEAN`; Windows CE and non-desktop Windows (`hb.hh:428`) | [hb_shape and its backends](hb_shape-and-its-backends.html#hb_shaper_list), [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#face-loaders) |
| `HB_NO_HINTING` | hinting Device tables and anchor format 2’s contour points (`hb-ot-layout-common.hh:6522`, `AnchorFormat2.hh:30`) | `HB_LEAN` | [GPOS](gpos.html#device-tables) |
| `HB_NO_LANGUAGE_LONG` | complex BCP 47 tags and three-letter language codes in tag conversion (`hb-ot-tag.cc:328`) | — | [Choosing a script shaper](choosing-a-script-shaper.html#from-a-language-to-language-system-tags) |
| `HB_NO_LANGUAGE_PRIVATE_SUBTAG` | the `-hbsc-` and `-hbot-` private-use subtags (`hb-ot-tag.cc:450`) | — | [Choosing a script shaper](choosing-a-script-shaper.html#naming-the-tags-directly) |
| `HB_NO_LAYOUT_COLLECT_GLYPHS` | `hb_ot_layout_lookup_collect_glyphs` (`hb-ot-layout.cc:1364`) | `HB_LEAN` | — |
| `HB_NO_LAYOUT_FEATURE_PARAMS` | `hb_ot_layout_get_size_params`, `hb_ot_layout_feature_get_name_ids`, `hb_ot_layout_feature_get_characters` (`hb-ot-layout.cc:1764`) | `HB_LEAN` | — |
| `HB_NO_LAYOUT_RARELY_USED` | `hb_ot_layout_lookup_get_glyph_alternates`, `…_collect_glyph_alternates`, `…_get_optical_bound` (`hb-ot-layout.cc:2690`) | `HB_LEAN` | — |
| `HB_NO_LAYOUT_UNUSED` | `hb_ot_layout_get_attach_points`, `hb_ot_layout_get_ligature_carets` (`hb-ot-layout.cc:341`) | `HB_LEAN` | — |
| `HB_NO_LEGACY` | nothing directly: an umbrella for six macros (`:148`) | `HB_MINI` | [Fallbacks](fallbacks.html#configuration) |
| `HB_NO_MATH` | the `MATH` slot, `hb_ot_math_*`, and `MATH` in subsetting and `hb-depend` | `HB_LEAN` | [Other tables](other-tables.html) |
| `HB_NO_META` | the `meta` slot and `hb_ot_meta_*` | `HB_LEAN` | [Other tables](other-tables.html) |
| `HB_NO_METRICS` | `hb_ot_metrics_*` (`hb-ot-metrics.cc:109`), and the x-height used for a fallback baseline | `HB_LEAN` | [Where metrics come from](where-metrics-come-from.html#mvar) |
| `HB_NO_MMAP` | mapping font files into memory; they are read instead (`hb-blob.cc:543`) | `HB_LEAN` | [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#from-a-file) |
| `HB_NO_MT` | thread safety: atomics become plain variables and mutexes do nothing (`hb-atomic.hh:61`, `hb-mutex.hh:83`) | `HB_TINY` | [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#loading-without-a-lock) |
| `HB_NO_NAME` | the `name` slot and `hb_ot_name_*` | `HB_LEAN` | [Other tables](other-tables.html) |
| `HB_NO_OPEN` | `hb_blob_create_from_file*` and `hb_face_create_from_file_or_fail` (`hb-blob.cc:512`, `hb-face.cc:303`) | `HB_LEAN` | [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#from-a-file) |
| `HB_NO_OT` | nothing directly: an umbrella for the four below it (`:163`) | — | [hb_shape and its backends](hb_shape-and-its-backends.html#ot) |
| `HB_NO_OT_FETCH` | `hb_ot_fetch_bits` and `hb_ot_fetch_number` (new in 14.3.0) | `HB_LEAN` | [Other tables](other-tables.html) |
| `HB_NO_OT_FONT` | the hb-ot font funcs (`hb-ot-font.cc:29`); fonts must be given others | `HB_NO_OT` | [Fonts and font functions](fonts-and-font-functions.html#hb-ot-the-default-funcs) |
| `HB_NO_OT_FONT_BITMAP` | hb-ot’s extents and painting from `sbix` and `CBDT` (`hb-ot-font.cc:820`, `:964`) | `HB_NO_BITMAP` (`HB_LEAN`) | [Color](color.html#bitmaps-sbix-and-cbdt) |
| `HB_NO_OT_FONT_CFF` | hb-ot’s CFF extents, glyph names, and outlines (`hb-ot-font.cc:831`) | `HB_NO_CFF`, `HB_NO_DRAW` | [Drawing outlines](drawing-outlines.html#cff-and-cff2-running-charstrings) |
| `HB_NO_OT_FONT_CMAP_CACHE` | the 1 KB cache of recent `cmap` lookups (`hb-ot-cmap-table.hh:2240`) | `HB_MINIMIZE_MEMORY_USAGE` (`HB_TINY`) | [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html#two-kinds-of-loader) |
| `HB_NO_OT_FONT_GLYPH_NAMES` | the glyph-name callbacks of hb-ot and the platform font funcs (`hb-ot-font.cc:851`) | `HB_LEAN` | [Fonts and font functions](fonts-and-font-functions.html#hb-ot-the-default-funcs) |
| `HB_NO_OT_KERN` | the `kern` table slot and `hb_ot_layout_has_kerning` | `HB_NO_LEGACY` (`HB_MINI`) | [Legacy kern](legacy-kern.html) |
| `HB_NO_OT_LAYOUT` | the GDEF, GSUB, and GPOS slots and `hb-ot-layout.cc` | `HB_NO_OT` | [GSUB](gsub.html) |
| `HB_NO_OT_LAYOUT_BLOCKLIST` | the check for known-broken GDEF tables (`hb-ot-layout.cc:154`); before 15.2.0, GSUB and GPOS had empty lists too | `HB_NO_LEGACY` (`HB_MINI`) | [Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html#a-list-of-known-bad-fonts) |
| `HB_NO_OT_LAYOUT_LOOKUP_CACHE` | the per-subtable caches of the first eight subtables (`hb-ot-layout-gsubgpos.hh:1539`) | `HB_MINIMIZE_MEMORY_USAGE` (`HB_TINY`) | [GPOS](gpos.html#pair-adjustment) |
| `HB_NO_OT_NAME_LANGUAGE` | turning a `name` record’s language ID into an `hb_language_t` (`OT/name/name.hh:99`) | `HB_NO_NAME` (`HB_LEAN`) | [Other tables](other-tables.html) |
| `HB_NO_OT_NAME_LANGUAGE_AAT` | the same through `ltag` (`OT/name/name.hh:109`) | `HB_NO_AAT` (`HB_MINI`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#feat-and-ltag) |
| `HB_NO_OT_RULESETS_FAST_PATH` | the second-glyph filter in context rule sets and ligature sets (`hb-ot-layout-gsubgpos.hh:3493`, `LigatureSet.hh:100`) | `HB_OPTIMIZE_SIZE_MORE` (`HB_TINY`) | [GSUB](gsub.html#the-second-glyph-fast-path) |
| `HB_NO_OT_SHAPE` | the `ot` backend: the shape planner, normalizer, and every script shaper | `HB_NO_OT`, `HB_NO_SHAPER` | [hb_shape and its backends](hb_shape-and-its-backends.html#ot) |
| `HB_NO_OT_SHAPE_FALLBACK` | fallback mark positioning, mark recategorizing, and kerning through the font funcs (`hb-ot-shape-fallback.cc:173`), and hb-ft’s kerning callback | `HB_NO_LEGACY` (`HB_MINI`) | [Fallbacks](fallbacks.html#configuration) |
| `HB_NO_OT_SHAPE_FRACTIONS` | automatic `frac`, `numr`, and `dnom` around U+2044 (`hb-ot-shape.cc:345`) | — | [From features to lookups](from-features-to-lookups.html#which-features-are-asked-for) |
| `HB_NO_OT_SHAPER_ARABIC_FALLBACK` | Arabic shaping from presentation forms, and the PUA `cmap` maps (`hb-ot-shaper-arabic.cc:421`) | `HB_NO_OT_SHAPE_FALLBACK` | [Joining scripts](joining-scripts.html#shaping-without-gsub) |
| `HB_NO_OT_SHAPER_HEBREW_FALLBACK` | composing Hebrew presentation forms (`hb-ot-shaper-hebrew.cc:77`) | `HB_NO_OT_SHAPE_FALLBACK` | [Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html#presentation-forms-for-old-fonts) |
| `HB_NO_OT_SHAPER_MYANMAR_ZAWGYI` | the Zawgyi shaper and its `Qaag` script (`hb-ot-shaper.hh:266`) | `HB_NO_OT_SHAPE_FALLBACK` | [Choosing a script shaper](choosing-a-script-shaper.html#myanmar-and-zawgyi) |
| `HB_NO_OT_SHAPER_THAI_FALLBACK` | Thai and Lao shaping with PUA glyphs (`hb-ot-shaper-thai.cc:225`) | `HB_NO_OT_SHAPE_FALLBACK` | [Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html#old-fonts-and-the-private-use-area) |
| `HB_NO_OT_SHAPER_VOWEL_CONSTRAINTS` | the dotted circles inserted for forbidden vowel sequences (`hb-ot-shaper-vowel-constraints.cc:67`) | `HB_NO_OT_SHAPE_FALLBACK` | [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html#vowel-constraints) |
| `HB_NO_OT_TAG` | `hb_ot_tag*` conversions; `hb-ot-layout.cc` and Uniscribe refuse to compile without them | `HB_NO_OT` | [Choosing a script shaper](choosing-a-script-shaper.html) |
| `HB_NO_OUTLINE` | synthetic bold and slant of drawn outlines (`hb-font.hh:717`) | `HB_NO_DRAW` | [Fonts and font functions](fonts-and-font-functions.html#synthetic-bold-and-slant) |
| `HB_NO_PAINT` | the paint API and every font funcs’ paint callback (`hb-paint.cc:27`) | `HB_NO_DRAW`; `HB_LEAN`, if no drawing library | [Color](color.html#the-paint-api) |
| `HB_NO_PRAGMA_GCC_DIAGNOSTIC` | the `#pragma`s that set HarfBuzz’s warnings (`hb.hh:38`) | — | — |
| `HB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR` | the warnings promoted to errors (`hb.hh:69`) | — | — |
| `HB_NO_PRAGMA_GCC_DIAGNOSTIC_IGNORED` | the warnings silenced (`hb.hh:143`) | — | — |
| `HB_NO_PRAGMA_GCC_DIAGNOSTIC_WARNING` | the warnings turned on (`hb.hh:55`) | — | — |
| `HB_NO_RESOURCE_FORK` | reading a Mac file’s resource fork when its data fork is empty (`hb-blob.cc:514`) | — | [Fonts as bytes](fonts-as-bytes.html#collections-and-resource-forks) |
| `HB_NO_SETLOCALE` | parsing and printing numbers in the C locale with `newlocale`/`uselocale` (`hb-common.cc:1080`) | `HB_LEAN`; automatically without `newlocale` and `uselocale` (`hb.hh:511`) | — |
| `HB_NO_SHAPER` | `hb_shape`, shape plans, and every backend; also implies `HB_NO_OT_SHAPE` (`:132`) | — | [hb_shape and its backends](hb_shape-and-its-backends.html#the-shaper-list) |
| `HB_NO_SINGLE_HEADER_ERROR` | the `#error` when a public header such as `hb-buffer.h` is included on its own | the header test in `src/meson.build:1341` | — |
| `HB_NO_STYLE` | the `STAT` slot, `hb_style_get_value`, and so `trak` (`hb-style.cc:27`) | `HB_LEAN` | [Other tables](other-tables.html), [AAT positioning](aat-positioning.html#when-it-applies) |
| `HB_NO_SUBSET_CFF` | subsetting CFF and CFF2 (`hb-subset-cff1.cc`, `hb-subset-cff2.cc`) | `HB_NO_CFF` | [Subsetting](subsetting.html) |
| `HB_NO_SUBSET_DEPEND` | the public `hb_subset_depend_*` API (`hb-subset-depend.h:73`) | `HB_LEAN`; every build without `HB_EXPERIMENTAL_API` (`:38`) | [hb-depend](hb-depend.html#status-and-limits) |
| `HB_NO_SUBSET_LAYOUT` | the layout stage of subsetting: GDEF, GSUB, GPOS, `kern`, and the AAT tables are dropped (`hb-subset.cc:238`) | — | [Subsetting](subsetting.html#the-layout-stage) |
| `HB_NO_SVG` | the `SVG ` slot and its painting (`hb-ot-color.cc:279`) | `HB_TINY` | [Color](color.html#svg) |
| `HB_NO_UCD` | HarfBuzz’s own Unicode tables (`hb-ucd.cc:258`) | — | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-implementations) |
| `HB_NO_UCD_UNASSIGNED` | exact properties for unassigned code points, in the size-optimized tables only (`hb-ucd-table.hh:2774`) | `HB_TINY` | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-sizes) |
| `HB_NO_UNICODE_FUNCS` | any default Unicode funcs, and the `#error` when none is found (`hb-unicode.cc:166`) | — | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-implementations) |
| `HB_NO_VAR` | font variations: the `fvar`, `avar`, `cvar`, `gvar`, and `MVAR` slots, FeatureVariations, `hb_ot_var_*`, `hb_font_set_variations` and the rest, and `hb_shape_justify` | `HB_LEAN` | [Design space](design-space.html) |
| `HB_NO_VAR_COMPOSITES` | the `VARC` table (`OT/Var/VARC/VARC.hh`) | `HB_NO_VAR` (`HB_LEAN`) | [Variable components](variable-components.html) |
| `HB_NO_VERTICAL` | the `vhea`, `vmtx`, and `VORG` slots and vertical metrics and origins | `HB_LEAN` | [Vertical text](vertical-text.html#compiled-out) |
| `HB_NO_VISIBILITY` | hiding internal symbols with `visibility("hidden")` (`hb.hh:301`) | automatically on MinGW, Cygwin, MSVC, and Sun compilers (`hb.hh:311`) | — |
| `HB_NO_WIN1256` | Arabic fallback shaping for fonts in the Windows-1256 encoding (`hb-ot-shaper-arabic-fallback.hh:236`) | — | [Joining scripts](joining-scripts.html#legacy-encodings) |

</div>

## The other switches

| Macro | What it does | Default |
|---|---|---|
| `HB_EXPERIMENTAL_API` | adds the experimental API: `hb_shape_justify`, `hb_subset_input_override_name_table`, `hb_subset_input_to_string_or_fail`, the raw CFF charstring accessors, the subset flags `IFTB_REQUIREMENTS` and `RETAIN_NUM_GLYPHS`, and `hb_subset_depend_*` | off; Meson’s `experimental_api` defines it |
| `HB_DISABLE_DEPRECATED` | removes deprecated functions, and makes `HB_IF_NOT_DEPRECATED (x)` expand to nothing (`hb-config.hh:119`) | off; set by `HB_LEAN` |
| `HB_BUFFER_MESSAGE_MORE` | sends messages from inside lookups as well as between them (“ligating glyphs at 0,2”); since 12.0.0 it needs a rebuild (`hb-debug.hh:452`) | `HB_DEBUG`, so 0 |
| `HB_DEBUG`, `HB_DEBUG_*` | debug output to `stderr`, described below | 0 |
| `HB_CUSTOM_MALLOC` | routes every allocation through `hb_malloc_impl`, `hb_calloc_impl`, `hb_realloc_impl`, and `hb_free_impl`, which the embedder supplies; defining all four implies it (`hb.hh:553`) | off: the C library’s |
| `hb_mutex_impl_init`, `…_lock`, `…_unlock`, `…_finish` | a mutex of the embedder’s own, with `hb_mutex_impl_t` (`hb-mutex.hh:40`) | pthreads, Windows critical sections, or `std::mutex` |
| `HB_MUTEX_IMPL_STD_MUTEX` | uses `std::mutex` even where pthreads or Windows are available (`hb-mutex.hh:50`) | off |
| `HB_USE_ATEXIT` | whether to free static objects at exit, which keeps leak checkers quiet; `hb_atexit` can also be defined directly (`hb.hh:460`) | 1 on glibc 2.3+, Windows, Android, and Apple platforms when `atexit` exists; 0 elsewhere and under `HB_NO_ATEXIT` |
| `HB_CONFIG_OVERRIDE_H`, `HB_CONFIG_OVERRIDE_LAST_H` | headers included before and after the closure of options | none |
| `HB_OPTIMIZE_SIZE`, `HB_OPTIMIZE_SIZE_MORE`, `HB_MINIMIZE_MEMORY_USAGE`, `HB_FAST_NUM_ACCESS` | size and speed, above | see above |
| `NDEBUG` | the usual: removes `assert` (`hb_always_assert` stays, for the tests: `hb.hh:600`) | off; set by `HB_TINY` |
| `HB_INTERNAL`, `HB_EXTERN`, `HB_DLL_EXPORT` | symbol visibility and export (`hb.hh:203`, `:300`) | hidden internals; exported API |
| `HB_ALWAYS_INLINE`, `HB_NEVER_INLINE`, `HB_HOT` | the inlining attributes, which can be preset to nothing (`hb.hh:335`) | compiler attributes |
| `HB_WASM_NO_MODULES` | builds the `wasm` backend without loading modules; `hb-wasm-shape.cc:62` defines it unless told otherwise | on |
| `HB_GPU_ATLAS_2D`, `HB_GPU_NO_MSAA` | not C macros: preprocessor switches in hb-gpu’s shaders, for WebGL 2 and for turning off multisampling | off |

The limits in `hb-limits.hh` (`HB_MAX_NESTING_LEVEL`, `HB_BUFFER_MAX_LEN_FACTOR`, and the rest) are compile-time switches too, each with an `#ifndef` so a build can change it. [Limits](limits.html) lists them.

**The debug macros.** Setting `HB_DEBUG_SANITIZE=N`, say, prints a trace of every sanitize call up to N levels deep. `HB_DEBUG` sets the default for all of them at once (`hb-debug.hh:35`); each is `HB_DEBUG+0` unless defined. They come in three groups:

| Group | Macros | What they trace |
|---|---|---|
| Walks over table structures, with `TRACE_*` macros | `HB_DEBUG_APPLY`, `HB_DEBUG_SANITIZE`, `HB_DEBUG_SERIALIZE`, `HB_DEBUG_SUBSET`, `HB_DEBUG_PAINT`, and `HB_DEBUG_DISPATCH`, which is their sum | lookups as they are applied, sanitizing ([Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html)), writing and subsetting tables, `COLR` painting, and which format each dispatch chose |
| Parts of the library | `HB_DEBUG_BLOB`, `HB_DEBUG_OBJECT`, `HB_DEBUG_SHAPE_PLAN`, `HB_DEBUG_ARABIC`, `HB_DEBUG_JUSTIFY`, `HB_DEBUG_DEPEND`, `HB_DEBUG_SUBSET_REPACK` | blob modes, reference counts, plan creation ([Shape plans and their cache](shape-plans-and-their-cache.html)), Arabic stretching, `hb_shape_justify`, the dependency graph, the repacker ([Writing tables](writing-tables.html)) |
| Backends | `HB_DEBUG_CORETEXT`, `HB_DEBUG_DIRECTWRITE`, `HB_DEBUG_UNISCRIBE`, `HB_DEBUG_FT`, `HB_DEBUG_WASM`, `HB_DEBUG_KBTS` | the platform shapers and font funcs |

> For programmers: debug output is not buffer messages. `HB_DEBUG_*` writes to `stderr` from inside the library and needs a rebuild. Buffer messages go to a callback the application installs, and a normal build sends the coarse ones; only the fine ones need `HB_BUFFER_MESSAGE_MORE`. This book’s traces use a second build made with `CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1` (`tools/build-harfbuzz.sh:19`).

## The Meson options

The options in `meson_options.txt` decide what is built and linked. Most of them work by setting a `HAVE_*` macro in `config.h`; the library’s own optional parts are selected that way, not by `HB_NO_*` macros. Configuration by macro and configuration by option meet only in `HB_EXPERIMENTAL_API`.

| Option | Default | What it does |
|---|---|---|
| `glib` | auto | `HAVE_GLIB`: `libharfbuzz`’s GLib Unicode funcs and script conversion |
| `gobject` | auto | `HAVE_GOBJECT`: `libharfbuzz-gobject` |
| `introspection` | auto | GObject introspection data |
| `icu` | auto | `HAVE_ICU`: `libharfbuzz-icu`, ICU’s Unicode funcs |
| `icu_builtin` | false | `HAVE_ICU_BUILTIN`: puts the ICU funcs in `libharfbuzz` itself, where they can be the default ([Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-implementations)) |
| `freetype` | auto | `HAVE_FREETYPE`: hb-ft, FreeType font funcs |
| `fontations` | disabled | `HAVE_FONTATIONS`: font funcs from the Rust fontations crates ([Fonts and font functions](fonts-and-font-functions.html#the-other-funcs)) |
| `cairo` | auto | `HAVE_CAIRO`: `libharfbuzz-cairo`, and `hb-view` |
| `chafa` | auto | `HAVE_CHAFA`: terminal output in the image tools |
| `png` | auto | `HAVE_PNG`: PNG in hb-raster and its tool |
| `zlib` | auto | `HAVE_ZLIB`: gzip-compressed `SVG ` documents, and PDF output in hb-vector |
| `graphite2` | disabled | `HAVE_GRAPHITE`: the `graphite2` backend (`HAVE_GRAPHITE2` before 15.2.0) |
| `graphite` | disabled | the same, deprecated |
| `harfrust`, `kbts`, `wasm` | disabled | the `harfrust`, `kbts`, and `wasm` backends ([hb_shape and its backends](hb_shape-and-its-backends.html#the-backends)); `wasm` also sets `HB_WASM_MODULE_DIR` |
| `coretext`, `directwrite`, `gdi` | disabled | the platform backends and font funcs; `gdi` brings Uniscribe |
| `subset` | enabled | `libharfbuzz-subset` |
| `raster`, `vector`, `gpu` | enabled | `libharfbuzz-raster`, `-vector`, and `-gpu` ([hb-raster](hb-raster.html), [hb-vector](hb-vector.html), and [hb-gpu](hb-gpu.html)) |
| `gpu_demo` | auto | the hb-gpu demo, which needs GLEW, GLFW, and GL |
| `experimental_api` | false | `HB_EXPERIMENTAL_API` |
| `utilities` | enabled | `hb-shape`, `hb-view`, `hb-subset`, and the other tools |
| `tests`, `benchmark` | enabled, disabled | the test suites ([Testing HarfBuzz](testing-harfbuzz.html)) and the benchmarks |
| `docs`, `doc_tests` | auto, false | the gtk-doc reference, and its checks |
| `with_libstdcxx` | false | links with a C++ linker; by default HarfBuzz is linked with a C linker and doesn’t depend on libstdc++ (`src/meson.build:498`) |
| `ragel_subproject` | false | builds Ragel if no suitable one is installed ([The Indic model](indic-model.html#ragel)) |
| `fuzzer_ldflags` | empty | extra link flags for the fuzzers |
| `cmakepackagedir` | `libdir/cmake` | where the CMake package files go |

Meson also writes `hb-features.h`, installed for applications, which defines an `HB_HAS_*` macro for each optional part that was built, from the `HAVE_*` macro of the same name (`src/meson.build:588`). In the book’s build, where hb-gpu is built, it has `#define HB_HAS_GPU 1`. Before 15.2.0 no Meson file set `HAVE_GRAPHITE` or `HAVE_GPU`, so `HB_HAS_GRAPHITE` and `HB_HAS_GPU` were never defined ([HHW-56](bugs-this-book-found.html#hhw-56)).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-config.hh` | the tiers, the override headers, and the closure of options |
| `src/hb.hh` | `HB_NO_GETENV`, `HB_NO_ERRNO`, `HB_NO_SETLOCALE`, `HB_USE_ATEXIT`, `HB_CUSTOM_MALLOC`, `HB_NO_VISIBILITY`, and the pragmas |
| `src/hb-debug.hh` | `HB_DEBUG`, every `HB_DEBUG_*` macro, `HB_BUFFER_MESSAGE_MORE` |
| `src/hb-mutex.hh`, `src/hb-atomic.hh` | the mutex choices and `HB_NO_MT` |
| `src/hb-ot-face-table-list.hh` | the table slots and the macros that remove them |
| `src/hb-algs.hh` | `HB_FAST_NUM_ACCESS` |
| `src/hb-limits.hh` | the limits a build can change |
| `src/harfbuzz-world.cc` | the single-file build, selected with `HB_HAS_*` ([Building HarfBuzz](building-harfbuzz.html#single-file-builds)) |
| `CONFIG.md` | upstream’s guide to small builds |
| `meson_options.txt`, `meson.build` | the build options and the `HAVE_*` macros they set |

## In short

* All configuration is in `hb-config.hh`, which every file sees first. Implications flow downward: tiers, then the first override header, then the closure of options, then the last override header.
* `HB_MINI` keeps an OpenType shaper and drops AAT, `kern`, the legacy-font paths, and fonts beyond 64K glyphs. `HB_LEAN` drops most of what isn’t shaping. `HB_TINY` is both, plus no threads, the size-optimized code, and fewer caches.
* The `HB_NO_*` macros only need to be defined. They remove whole files, empty function bodies, or remove table slots, and the public headers don’t change, so calling a removed function fails at link time.
* `-Os` turns on `HB_OPTIMIZE_SIZE` by itself. It gives up forced inlining, unrolled loops, fast paths, and the larger lookup tables.
* `HB_BUFFER_MESSAGE_MORE` and the `HB_DEBUG_*` macros need a rebuild; `HB_EXPERIMENTAL_API` is the one macro with a Meson option.
* `HB_LEAN` removes drawing, painting, and color only when no renderer is in the build.
