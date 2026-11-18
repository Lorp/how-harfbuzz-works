# Regenerating the Unicode and shaping tables

A good part of HarfBuzz’s source is written by programs. The Unicode properties, the categories of the Indic and USE shapers, the Arabic joining types, the mapping from BCP 47 languages to OpenType language systems and the syllable state machines are all generated, and the generated files are committed to the repository. Building HarfBuzz never downloads anything and never runs a data generator. The generators are run by hand, by a maintainer, when Unicode or one of the registries changes.

The scripts live in `src/`, and are of two kinds. The **data generators** read the Unicode Character Database, Microsoft’s data for the Universal Shaping Engine and two registries of language tags, and are run through `src/update-unicode-tables.make`. The **build helpers** are run by meson as part of an ordinary build: they turn Ragel grammars into C, stamp the version into a header, and write the single-file amalgamations. This appendix lists both: what each reads, what it writes, which corrections it makes by hand, and which chapter explains the result.

## Generated files and their inputs

| Generated file | Generator | Reads | Explained in |
|---|---|---|---|
| `hb-ucd-table.hh` | `gen-ucd-table.py` | `ucd.nounihan.grouped.zip` (the UCD in XML, without Unihan); `hb-script-list.h` | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#the-built-in-tables), [Normalization](normalization.html) |
| `hb-unicode-emoji-table.hh` | `gen-emoji-table.py` | `emoji-data.txt`; `emoji-test.txt`, for a test file | [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#continuations-just-enough-of-graphemes) |
| `hb-ot-shaper-arabic-table.hh` | `gen-arabic-table.py` | `ArabicShaping.txt`, `UnicodeData.txt`, `Blocks.txt` | [Joining scripts](joining-scripts.html#joining-types), [and fallback shaping](joining-scripts.html#shaping-without-gsub) |
| `hb-ot-shaper-arabic-joining-list.hh` | `gen-arabic-joining-list.py` | `ArabicShaping.txt`, `Scripts.txt` | [Joining scripts](joining-scripts.html#joining-scripts-under-use) |
| `hb-ot-shaper-arabic-pua.hh` | `gen-arabic-pua.py` | `ArabicPUASimplified.txt`, `ArabicPUATraditional.txt` (committed) | [Joining scripts](joining-scripts.html#legacy-encodings) |
| `hb-ot-shaper-indic-table.cc` | `gen-indic-table.py` | `IndicSyllabicCategory.txt`, `IndicPositionalCategory.txt`, `Blocks.txt` | [The Indic model](indic-model.html#where-the-table-comes-from), [Khmer and Myanmar](khmer-and-myanmar.html#categories) |
| `hb-ot-shaper-use-table.hh` | `gen-use-table.py` | seven UCD files and two of Microsoft’s (below) | [The Universal Shaping Engine](universal-shaping-engine.html#where-they-come-from) |
| `hb-ot-shaper-vowel-constraints.cc` | `gen-vowel-constraints.py` | `ms-use/IndicShapingInvalidCluster.txt` (committed), `Scripts.txt` | [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html#vowel-constraints) |
| `hb-ot-tag-table.hh` | `gen-tag-table.py` | the OpenType language system tag page (HTML), the IANA language subtag registry | [Choosing a script shaper](choosing-a-script-shaper.html#from-a-language-to-language-system-tags) |
| the array in `hb-ot-os2-unicode-ranges.hh` | `gen-os2-unicode-ranges.py` | a tab-separated copy of the `OS/2` Unicode range list, not in the repository | [Subsetting](subsetting.html#table-by-table) |
| `hb-ot-shaper-*-machine.hh`, `hb-buffer-deserialize-*.hh` | `gen-ragel-artifacts.py`, run by meson | the `.rl` grammars | [The Indic model](indic-model.html#ragel), [below](#the-ragel-machines) |

All the data generators except `gen-arabic-joining-list.py` and `gen-os2-unicode-ranges.py` take a first argument `--rust`, which writes the same data as Rust for HarfRust, the Rust port. The Rust output goes to standard output like the C, and lives in HarfRust’s repository, not HarfBuzz’s.

## Running the data generators

`update-unicode-tables.make` is a makefile with a `#!/usr/bin/env -S make -f` line, run from `src/`. Its default target is `packtab` and then the nine generated files it knows about (`update-unicode-tables.make:3`). Every rule has the same shape, the generator first and its inputs after it, run as `./$^ > $@`, and deletes the output if the generator fails:

```make
hb-ot-shaper-indic-table.cc: gen-indic-table.py IndicSyllabicCategory.txt IndicPositionalCategory.txt Blocks.txt
	./$^ > $@ || ($(RM) $@; false)
```

The inputs that aren’t in the repository are downloaded with `curl -O` when missing (`:45`–`:56`): the UCD files from `https://unicode.org/Public/UCD/latest/ucd/`, `emoji-data.txt` from the `emoji/` folder beside them, `emoji-test.txt` from `https://www.unicode.org/Public/emoji/latest/`, the XML database from `ucdxml/`, the language tag page from `learn.microsoft.com`, and the subtag registry from `www.iana.org`. Every URL says `latest`, so what a run produces depends on the day it is run. Four inputs are committed and never downloaded: Microsoft’s three files in `src/ms-use/`, and the two Arabic PUA files. `gen-os2-unicode-ranges.py` is not in the makefile at all; `hb-ot-os2-unicode-ranges.hh` says only that “the contents of this array was generated using gen-os2-unicode-ranges.py” (`:44`), and its input was pasted from the `OS/2` page of the OpenType specification.

The `packtab` target installs **packTab**, HarfBuzz’s table packer, with `pip install git+https://github.com/harfbuzz/packtab` if `import packTab` fails (`:43`). It is the latest commit, not a pinned version. Six generators use it: given a map from code points to values, it searches for the cheapest split of the code point into bit fields for a multi-level table, and writes the arrays and an inline lookup function. Its `compression` argument trades size for speed, and `gen-ucd-table.py` and `gen-use-table.py` run it twice or three times to write the `HB_OPTIMIZE_SIZE` variants side by side ([Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-sizes) shows the result).

Two further targets: `clean` deletes the generated files, and `clean-sources` the downloaded ones, so that the next run fetches new copies. `SOURCES`, the list `clean-sources` deletes (`:16`), leaves out `DerivedCoreProperties.txt` and `emoji-test.txt`, which other rules download. A stale copy of either survives a clean and is used again. That may be why `hb-ot-shaper-use-table.hh` records `DerivedCoreProperties-17.0.0.txt` beside version 18.0.0 of every other Unicode file (inferred).

> Since {{hb}}: fixed on HarfBuzz main by [`b873113`](https://github.com/harfbuzz/harfbuzz/commit/b873113f410f0fa0b215f225aec5d76eb55c22e3) (17 November 2026), so main’s `SOURCES` lists both files; the USE table hasn’t been regenerated since, and still records `DerivedCoreProperties-17.0.0.txt`.

### What the headers record

Each generated file begins with the command that made it and the first lines of each input file, so the headers are the record of which data a release carries. In {{hb}}:

| Input | Version or date in the generated header |
|---|---|
| UCD XML (`hb-ucd-table.hh`) | “Unicode 18.0.0” |
| `ArabicShaping.txt`, `Scripts.txt`, `Blocks.txt`, `IndicSyllabicCategory.txt`, `IndicPositionalCategory.txt` | 18.0.0 |
| `DerivedCoreProperties.txt` (USE table only) | 17.0.0 |
| `emoji-data.txt` | 18.0.0, dated 2026-01-30 |
| `ms-use/*-Additional.txt` | “Updated for Unicode 18.0 by Andrew Glass 2026-09-04” |
| `ms-use/IndicShapingInvalidCluster.txt` | dated 2015-03-12 and 2019-11-08 |
| OpenType language system tags | `updated_at` 2024-12-06 |
| IANA language subtag registry | `File-Date: 2026-09-17` |

`UnicodeData.txt` has no header, and the generators that read it say so. `hb-ot-shaper-arabic-pua.hh` records nothing about its inputs.

## The data generators

### gen-ucd-table.py

Reads the XML database through `packTab.ucdxml` and writes five properties for every code point: general category, canonical combining class, script, the Bidi mirroring glyph (as a difference) and the canonical decomposition. [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#the-built-in-tables) explains the encoding. Its second input is `hb-script-list.h`, a hand-written public header: the generator numbers the scripts in the order of the `HB_SCRIPT_*` lines there (`gen-ucd-table.py:147`), so a script Unicode adds must be added to that header before the table can be regenerated. Hangul syllables are left out of the decompositions on purpose, since `hb-ucd.cc` computes them (`:63`). The only change it makes to the data is the “sloppy” variant, which fills unassigned code points from their neighbors (`:257`).

The usage line names `ucd.nounihan.grouped.xml`, and the makefile passes the `.zip`; `packTab.ucdxml` reads either (inferred from the makefile working).

### gen-emoji-table.py

Reads every property in `emoji-data.txt`, but writes only `Extended_Pictographic` (`gen-emoji-table.py:78`), the one HarfBuzz uses, for keeping emoji ZWJ sequences in one cluster. It also reads `emoji-test.txt` and, if `test/shape/data/in-house/tests/` exists, rewrites `emoji-clusters.tests` there: one line per emoji sequence, shaped with `AdobeBlank2.ttf`, expecting every glyph in cluster 0 (`:112`–`:134`). That is the only generator that writes a test.

### gen-arabic-table.py

Writes three things. The **joining table**, from `ArabicShaping.txt`, with three changes: type C is stored as D, the Syriac joining groups Alaph and Dalath Rish replace their letters’ type, and anything unlisted is X, decided at run time ([Joining scripts](joining-scripts.html#joining-types)). The **shaping table**, a row of initial, medial, final and isolated presentation forms for each letter, from the `<initial>`, `<medial>`, `<final>` and `<isolated>` decompositions in `UnicodeData.txt`. And the **ligature tables** for fallback shaping, only for the ligatures in its `LIGATURES` list (`gen-arabic-table.py:139`).

Its overrides are in the data it adds: three made-up `UnicodeData.txt` lines for Private Use ligatures (U+F201 LELLAH, U+F211 lam-meem-jeem, U+F2EE shadda with fathatan, `:156`), which exist only for the legacy PUA fonts. A mark ligature is recognized by a leading U+0020 in its decomposition, which the generator drops before reversing the components (`:175`). `Blocks.txt` is read into a dictionary that nothing uses (`:45`, `:379`), and U+F2EE is in `LIGATURES` twice; neither affects the output.

### gen-arabic-joining-list.py

Writes one function, `has_arabic_joining`: a `switch` over every script, other than Common and Inherited, that has a character in `ArabicShaping.txt` whose type isn’t T or U. The USE shaper calls it to decide whether to run the Arabic joining machine. In {{hb}} that is thirteen scripts ([Joining scripts](joining-scripts.html#joining-scripts-under-use)). No overrides. Its usage string calls it `gen-arabic-joining-table.py`, an old name.

### gen-arabic-pua.py

Reads the two committed files, “Legacy Simplified Arabic encoding” and “Legacy Traditional Arabic encoding”, each a list of PUA code, Unicode code point and name, and packs the inverse maps, Unicode to PUA, as `_hb_arabic_pua_simp_map` and `_hb_arabic_pua_trad_map`. They are used by `cmap` (`hb-ot-cmap-table.hh:2222`) and by the FreeType font funcs (`hb-ft.cc:451`), not by the shaper. The files don’t say where they came from.

### gen-indic-table.py

One table serves the Indic, Khmer and Myanmar shapers: a 16-bit value per code point, a category in the low byte and a position in the high byte. Only some blocks are kept (`ALLOWED_BLOCKS`, `gen-indic-table.py:25`), plus U+00A0 and U+25CC. The steps, from Unicode’s two Indic properties to HarfBuzz’s categories and positions, are described in [The Indic model](indic-model.html#where-the-table-comes-from).

The hand-written parts are larger than the derivation:

* **The category lists** (`:93`): the categories each shaper’s machine knows, which must match the `export` numbers in the three `.rl` files. The generator `#define`s each category once, and for a category that a later shaper lists again, emits a `static_assert` that the two machines agree (`:537`). In {{hb}} only Khmer and Myanmar share listed categories, the four `V…` vowel classes.
* **`category_map`** (`:147`), from Unicode’s syllabic categories, with comments where the choice is a guess (“Don’t care”, “TODO”) or tied to an issue (`Gemination_Mark`, #552). `Consonant_Killer` maps to `M`, with the comment “U+17CD only”, but U+17CD is then overridden to `Xgroup`, so the entry decides nothing.
* **`category_overrides`** (`:207`), about 140 code points. The variation selectors U+FE00 to U+FE0F become `VS` and six punctuation and box characters `PLACEHOLDER`, both “not Myanmar-specific”. Ten RAs become `Ra`. Some Vedic signs become tone marks or `Symbol` (with TODOs saying they should be restricted). Grantha marks are included “according to ScriptExtensions.txt”, so that Tamil text can use them. Single characters follow, each with an issue or pull request. Then the Khmer classes (`Robatic`, `Xgroup`, `Ygroup`; U+17D3 is “Just guessing. Uniscribe doesn’t categorize it.”) and the Myanmar ones, from Microsoft’s Myanmar specification. One Myanmar override is commented out: “The spec says D0, but Uniscribe doesn’t seem to do.”
* **The matra positions** (`:393`–`:432`), per block, with one marked “Deviate from spec” (Gurmukhi top matras), and **`position_overrides`** (`:386`) for U+0A51 and U+0B01.

Unicode’s positions are discarded for every category except `CM`, `SM`, `RS`, `H`, `M` and `MPst` (`:457`), and consonants all get `BASE_C`. Khmer and Myanmar vowel signs are given a category from their position instead (`:473`), [as Khmer and Myanmar explains](khmer-and-myanmar.html#categories).

### gen-use-table.py

Reads nine files. The seven UCD files give each code point its Indic syllabic and positional categories, joining type, whether it is default ignorable, general category, block and script. The two `ms-use/*-Additional.txt` files, Microsoft’s, are read last into the same two slots, so their values replace Unicode’s (`gen-use-table.py:92`): DOTTED CIRCLE becomes a `Consonant`, and scripts outside Unicode’s Indic properties, such as Mongolian and Adlam, get values at all. Each code point is then passed through a list of predicates that follow Microsoft’s derivation of USE categories, and exactly one must say yes.

HarfBuzz’s own corrections, in the order of the source:

* five scripts are dropped, since other shapers handle them: Arabic, Lao, Samaritan, Syriac and Thai (`DISABLED_SCRIPTS`, `:40`);
* Microsoft’s `Consonant_Final_Modifier` is read as `Syllable_Modifier` and its positional `NA` as `Not_Applicable` (`:85`, `:88`);
* joining letters and joiners, the generic bases (the same six characters as the Indic table’s placeholders, `:224`), three viramas with classes of their own (U+0DCA, U+1A60 and the other invisible stackers), and which default ignorables are `WJ` (excluding the Hangul fillers and U+1BCA0 to U+1BCA3, `:297`) are all decided in the predicates;
* in `map_to_use` (`:382`), U+1CE2 to U+1CE8, four Tibetan signs and U+1CED get syllabic categories, and U+11302, U+11303 and U+114C1 the position `Top`; U+0F7F is excused from the check that a positioned category has a position (`:411`).

[The Universal Shaping Engine](universal-shaping-engine.html#harfbuzzs-own-changes) has the full table, with what each comment says. Two of the TODOs explain themselves as missing values “in Unicode 13.0.0” (`:389`, `:393`). Whether Unicode 18.0 has since assigned them can’t be checked without the data files, which aren’t in the repository; if it has, the overrides are now redundant.

The table is written twice, at packTab compression 5 and, under `HB_OPTIMIZE_SIZE`, 9. Its category names are macros for `USE(…)`, the export numbers of `hb-ot-shaper-use-machine.rl`, so the table and the machine must be regenerated together when a category is added. `src/test-use-table.cc` prints the category of every code point, which makes a before-and-after comparison of a regeneration easy (inferred use).

### gen-vowel-constraints.py

Reads Microsoft’s list of 103 sequences that should be shown as broken, `ms-use/IndicShapingInvalidCluster.txt`, and `Scripts.txt` to find each sequence’s script. It writes `_hb_preprocess_text_vowel_constraints`, a `switch` on the buffer’s script with nested `switch`es on the code points, which inserts a dotted circle inside a matching sequence. The Indic and USE shapers call it ([Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html#vowel-constraints)). The function carries its own comment, “UGLY UGLY UGLY business of adding dotted-circle…”, and returns at once under `HB_NO_OT_SHAPER_VOWEL_CONSTRAINTS` or `HB_BUFFER_FLAG_DO_NOT_INSERT_DOTTED_CIRCLE`. No overrides; the list itself hasn’t changed since 2019.

### gen-tag-table.py

At 1,498 lines the largest generator. It parses the OpenType language system tag page as HTML, taking from each row the name, the tag and the ISO 639 codes, and the IANA registry for names, scopes, macrolanguages, deprecations and variants. Tags are matched through the ISO codes (three-letter codes are turned into two-letter ones where those exist, through a table of 185 entries copied from SIL, `gen-tag-table.py:112`); names are used only for the comments in the output. Then it adds each macrolanguage’s individual languages, orders the OpenType tags for each language by rank, and writes:

* `ot_languages2` and `ot_languages3`, from two- and three-letter language subtags to OpenType tags, with comments such as “Avaric -> Avar”;
* `hb_ot_tags_from_complex_language`, generated C for tags with a script, region or variant, such as `zh-Hant-HK` or `und-fonipa`;
* `hb_ot_ambiguous_tag_to_language`, the way back for OpenType tags that several languages share.

The corrections are an explicit block (`:755`–`:871`): 63 `add_language` calls (Chinese by region and script, the Quechua varieties, phonetic transcription as `und-fonipa`, Polytonic Greek as `el-polyton`), ten tags removed and re-added differently, five rank adjustments, names and macrolanguages for three retired codes, and a `disambiguation` map of 33 OpenType tags to the BCP 47 tag they should turn back into (`:893`). The comments it copies from the two registries are checked against a list of allowed characters before they are written (`sanitize_comment`, `:57`), since they end up in C source.

### gen-os2-unicode-ranges.py

Reads lines of bit number, block name and range, and prints `_hb_os2_unicode_ranges`, sorted by first code point, for the subsetter’s recalculation of the `OS/2` Unicode range bits. The output has to be pasted into `hb-ot-os2-unicode-ranges.hh` by hand.

## The build helpers

These run in every meson build, from `src/meson.build`, and read nothing outside the source tree.

| Writes | Helper | From | Notes |
|---|---|---|---|
| the seven Ragel headers | `gen-ragel-artifacts.py` | `*.rl` | only if Ragel is found; [below](#the-ragel-machines) |
| `hb-version.h` | `gen-hb-version.py` | `hb-version.h.in` and the project version | |
| `harfbuzz.cc`, `harfbuzz-subset.cc` | `gen-harfbuzzcc.py` | meson’s source lists | one `#include` per `.cc` file; copied into `src/` if it changed |
| `harfbuzz-world.cc` | `gen-harfbuzz-world.py` | `harfbuzz-world.cc.in` and tagged source lists | every library in one file ([Building HarfBuzz](building-harfbuzz.html#single-file-builds)) |
| `harfbuzz*.def` | `gen-def.py` | the public headers | the Windows export list; leaves out eleven experimental functions unless `-Dexperimental_api=true` |
| `hb-gpu-*-{glsl,wgsl,msl,hlsl}.hh` | `gen-gpu-shader-artifacts.py` | the shader sources | each shader as a C string ([hb-gpu](hb-gpu.html#what-the-application-supplies)) |

The helpers that write into `src/` do it so that the committed copies stay current. `gen-ragel-artifacts.py`, `gen-gpu-shader-artifacts.py` and `gen-harfbuzz-world.py` also handle a read-only source tree: they compare instead, and stop with “out of date; regenerate with a writable source tree” if the committed file differs.

## The Ragel machines

**Ragel** compiles regular expressions with actions into C. HarfBuzz has seven grammars, and commits the C:

| Grammar | Generated header (lines) | Used by |
|---|---|---|
| `hb-ot-shaper-indic-machine.rl` | 1,302 | [The Indic model](indic-model.html#ragel) |
| `hb-ot-shaper-khmer-machine.rl` | 428 | [Khmer and Myanmar](khmer-and-myanmar.html#syllables) |
| `hb-ot-shaper-myanmar-machine.rl` | 683 | [Khmer and Myanmar](khmer-and-myanmar.html) |
| `hb-ot-shaper-use-machine.rl` | 1,112 | [The Universal Shaping Engine](universal-shaping-engine.html#the-grammar) |
| `hb-buffer-deserialize-json.rl` | 735 | `hb_buffer_deserialize_glyphs`, JSON ([Buffers](buffers.html#comparing-and-writing-out)) |
| `hb-buffer-deserialize-text-glyphs.rl` | 591 | `hb_buffer_deserialize_glyphs`, text |
| `hb-buffer-deserialize-text-unicode.rl` | 256 | `hb_buffer_deserialize_unicode` |

Meson looks for Ragel with `find_program('ragel', version: '6.10', required: false)` (`src/meson.build:455`). If it isn’t found, the option `-Dragel_subproject=true` builds Ragel 6.10 from `subprojects/ragel.wrap`, which downloads `ragel-6.10.tar.gz` from colm.net; without either, meson warns “You have to install ragel if you are going to develop HarfBuzz itself” and builds from the committed headers. With Ragel, `gen-ragel-artifacts.py` copies the `.rl` file into the build directory, runs `ragel -e -F1 -o <name>.hh`, and copies the result into `src/`. `-F1` is Ragel’s fast flat table style with expanded actions.

The generated headers don’t name the Ragel version that made them. They begin with `#line 1 "hb-ot-shaper-use-machine.rl"` and carry only `#line` directives after that, so 6.10, from `meson.build` and the wrap file, is the only version the repository states.

The machines once needed Ragel for every build from git (“Removed generated files from git again. So, one needs ragel to bootstrap from the git tree”, NEWS for 0.9.13); the headers are committed now. Ragel is used less than it was: 15.0.0 rewrote the number parser without it.

## A new Unicode version

`RELEASING.md`, HarfBuzz’s release checklist, says nothing about Unicode data: it covers NEWS, API documentation, the version bump and tagging. The practice shows in `NEWS`. Since Unicode 14.0, each version has had a release of its own, every time in September: 3.0.0 (Unicode 14.0, 17 September 2021), 5.2.0 (15.0), 8.2.1 (15.1), 10.0.0 (16.0), 11.5.0 (17.0) and 14.5.0 (“Update Unicode 18.0 data and script support”, 21 September 2026).

From the generators and the code that 14.5.0 touched, an update has these steps (inferred as a sequence; each step is in the source):

1. **New scripts first.** Add each to `hb-script-list.h`, with its four-letter tag, a `Since:` line and the Unicode version in a comment (`HB_SCRIPT_JURCHEN`, `/*18.0*/`). `gen-ucd-table.py` reads the list from there.
2. **Microsoft’s data.** Copy in the new `ms-use/*-Additional.txt` files, which Microsoft updates for each Unicode version.
3. **Regenerate.** `make -f update-unicode-tables.make clean-sources`, then `make -f update-unicode-tables.make`, remembering that `DerivedCoreProperties.txt` and `emoji-test.txt` must be deleted by hand.
4. **Fix what fails.** The generators assert rather than guess. A new syllabic category value stops `gen-indic-table.py` with a `KeyError` in `category_map` if it falls in an allowed block; a character that no USE predicate, or two, accepts stops `gen-use-table.py` at its assertion; a new value must also be added to `property_names` there.
5. **The hand-written lists.** New scripts that should go to USE are added to the `switch` in `hb-ot-shaper.hh` (“Unicode-18.0 additions”, `:405`), right-to-left ones to `hb_script_get_horizontal_direction` in `hb-common.cc`, and scripts with an ideographic baseline to `hb-ot-layout.cc:2336`.
6. **Test.** The shaping tests and `emoji-clusters.tests`, which the emoji generator has just rewritten.

New data isn’t always the end. 15.1.0, six weeks after 14.5.0, lists “Fix Indic shaping of the Unicode 18 Devanagari and Bengali additions”.

## Possible bugs in the generators

Read from the code, none affecting the output in {{hb}}:

* `gen-hb-version.py:20` looks for an existing version with `(\d.\d.\d)`, one digit per part, so for 10.0.0 and later the check that skips rewriting never matches. The header is rewritten every time, which is harmless.
* `gen-ragel-artifacts.py` checks `len (sys.argv) < 4` but reads `sys.argv[4]`, so a missing argument gives an `IndexError` instead of the usage message.
* `SOURCES` in `update-unicode-tables.make` omits `DerivedCoreProperties.txt` and `emoji-test.txt`, as above.
* `gen-arabic-table.py` reads `Blocks.txt` for nothing and lists U+F2EE twice; `gen-arabic-joining-list.py`’s usage string has an old name; `gen-emoji-table.py`’s header names only `emoji-data.txt`, not `emoji-test.txt`.
* `gen-tag-table.py` and `gen-os2-unicode-ranges.py` give `docs.microsoft.com` URLs, which now redirect to `learn.microsoft.com`, and the ISO 639 table cites `www-01.sil.org`.

> Since {{hb}}: partly fixed on HarfBuzz main by [`ebfcf19`](https://github.com/harfbuzz/harfbuzz/commit/ebfcf19c720f3328754ecdde620eb45c2fa8088c), [`c66b1a5`](https://github.com/harfbuzz/harfbuzz/commit/c66b1a505795d701b27c67702809814ee250d6cd) and [`b873113`](https://github.com/harfbuzz/harfbuzz/commit/b873113f410f0fa0b215f225aec5d76eb55c22e3) (17 November 2026): the version regex, the Ragel argument check and `SOURCES` (the first three items); the other items remain.

## Where to read the source

| File | What’s there |
|---|---|
| `src/update-unicode-tables.make` | which generator reads which files, and where each file is downloaded from |
| `src/gen-ucd-table.py` | the UCD properties and their encoding |
| `src/gen-emoji-table.py` | Extended_Pictographic, and `emoji-clusters.tests` |
| `src/gen-arabic-table.py`, `src/gen-arabic-joining-list.py`, `src/gen-arabic-pua.py` | joining types, presentation forms, fallback ligatures, the joining scripts, the PUA maps |
| `src/gen-indic-table.py` | the Indic, Khmer and Myanmar categories, with their overrides |
| `src/gen-use-table.py` | the USE predicates and HarfBuzz’s corrections |
| `src/ms-use/` | Microsoft’s files, under the MIT license |
| `src/gen-vowel-constraints.py` | the vowel constraint function |
| `src/gen-tag-table.py` | the language tag mapping and its manual corrections |
| `src/gen-ragel-artifacts.py`, `src/meson.build:455` | how Ragel is found and run |
| `subprojects/ragel.wrap` | Ragel 6.10 as a subproject |
| `src/hb-script-list.h`, `src/hb-ot-shaper.hh`, `src/hb-common.cc` | the hand-written script lists an update touches |
| `RELEASING.md`, `NEWS` | the release checklist, and when each Unicode version arrived |

## In short

* Generated tables are committed; a build never downloads data. `update-unicode-tables.make`, run by hand from `src/`, fetches the latest UCD, emoji data and language registries and runs nine generators, most through packTab.
* Every generated header records its command and its inputs’ versions: in {{hb}}, Unicode 18.0.0 throughout, except `DerivedCoreProperties.txt` at 17.0.0 in the USE table.
* The corrections that shape HarfBuzz’s behavior are in the generators: `category_overrides` in `gen-indic-table.py`, the predicates and `map_to_use` in `gen-use-table.py`, and the manual block in `gen-tag-table.py`. Microsoft’s `ms-use/` files correct Unicode for USE before HarfBuzz does.
* Seven Ragel grammars are compiled to committed headers when meson finds Ragel 6.10. The headers name no version.
* A Unicode update has come in a September release since 2021. It also means new scripts in `hb-script-list.h` first, and hand-kept script lists afterward.
