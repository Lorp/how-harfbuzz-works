# Survey: script-specific shaping and AAT (HarfBuzz 15.1.0)

Source: `harfbuzz/` checkout (15.1.0, NEWS dated 2026-11-04). All paths are relative to `harfbuzz/src/` unless noted. Line numbers are for this checkout. Where something was inferred rather than read in the code, it is marked **(inferred)**.

Terminology trap for the book: HarfBuzz uses “shaper” for two different things.
1. **Backend shapers** (`hb-shaper-list.hh`): `wasm`, `graphite2`, `ot`, `uniscribe`, `directwrite`, `coretext`, `harfrust`, `kbts`, `fallback`. There is **no `aat` backend shaper**. AAT (morx/kerx/trak) runs *inside* the `ot` shaper.
2. **OT script shapers** (`hb_ot_shaper_t`, `hb-ot-shaper.hh`): `arabic`, `default`, `dumber`, `hangul`, `hebrew`, `indic`, `khmer`, `myanmar`, `myanmar_zawgyi`, `thai`, `use`. These are “complex shapers” in older writing (the files were renamed from `hb-ot-shape-complex-*` to `hb-ot-shaper-*`; older descriptions use the old names **(inferred from naming; not checked in git history)**).

`docs/usermanual-opentype-features.xml:236-264` still talks about an “`aat` shaper” chosen for AAT fonts and suggests a shaper list `{"ot", "default", "aat"}`. That is wrong for this code: no such backend exists. The same file (`:48-58`) gives a simplified table-precedence rule that the code contradicts (see section 13).

---

## 1. Choosing a script shaper

**Files:** `hb-ot-shaper.hh` (struct, master list, `hb_ot_shaper_categorize` at :176-421), `hb-ot-shape.cc` (planner at :84-102), `hb-ot-tag.cc` (script tags, :89-175).

**How it works.**
- `hb_ot_shape_planner_t::hb_ot_shape_planner_t` (`hb-ot-shape.cc:84`) calls `hb_ot_shaper_categorize (props.script, props.direction, map.chosen_script[0])`. The third argument is the **GSUB script tag actually found in the font** (`chosen_script[0]`, set by `hb_ot_layout_table_select_script` in `hb-ot-map.cc:75-80`). The choice depends on the font as well as on the text’s script.
- The rules, read from the switch:
  - **Arabic, Syriac**: Arabic shaper, if horizontal and (the font has a non-`DFLT` GSUB script, or the script is Arabic). Arabic gets its shaper even with no GSUB at all, because Arabic has fallback shaping; Syriac without a Syriac GSUB script goes to `default`. Vertical Arabic or Syriac goes to `default`.
  - **Thai, Lao**: `thai`. **Hangul**: `hangul`. **Hebrew**: `hebrew`. **Khmer**: always `khmer`.
  - **The nine Indic scripts** (Bengali, Devanagari, Gujarati, Gurmukhi, Kannada, Malayalam, Oriya, Tamil, Telugu): `default` if the GSUB script found is `DFLT` or `latn`; **`use` if the found tag ends in `'3'`** (`dev3`, `bng3`, …); otherwise `indic`.
  - **Myanmar**: `default` if `DFLT`, `latn` or the pre-spec `mymr` tag; otherwise `myanmar`. **`Qaag`** (private script code for Zawgyi) goes to `myanmar_zawgyi`.
  - **A long explicit list** (Tibetan, Mongolian, Sinhala, … through the Unicode 18.0 additions Jurchen, Proto-Cuneiform, Seal at :405-408) goes to `use`, unless the GSUB script is `DFLT`/`latn`.
  - **Everything else**: `default`.
- Tag order matters. `hb_ot_all_tags_from_script` (`hb-ot-tag.cc:157`) tries `xxx3`, then `xxx2`, then the old tag, so a font that has a `dev3` script runs Devanagari through USE. Myanmar has no `mym3` (:166).
- **The AAT override** (`hb-ot-shape.cc:98-101`): if the font will use `morx` (see section 12) and the categorized shaper isn’t `default`, the shaper is replaced by `_hb_ot_shaper_dumber`. `script_zero_marks` and `script_fallback_position` are captured from the categorized shaper *before* the swap (:95-96), so a morx Arabic font keeps the Arabic shaper’s legacy-kern eligibility. Zeroing, though, goes through `plan->shaper->zero_width_marks`, which for `dumber` is NONE (`hb-ot-shape.cc:1052-1078`). So `plan.zero_marks` can be true while nothing is zeroed. This is subtle: it’s read from the code, but I didn’t test it.

**Non-obvious, for the book.**
- A Devanagari font with only a `DFLT` or `latn` GSUB script gets **no Indic reordering at all**: the default shaper runs.
- **Corrected:** simple scripts in the USE list with no GSUB do *not* fall to `default`. No GSUB gives `HB_TAG_NONE`, which isn’t `DFLT` or `latn`, so they go to the USE; the same holds for the Indic scripts (Indic shaper, in old mode, since the tag doesn’t end in `2`). Syriac goes to `default` only when GSUB chose `DFLT`: `latn`, `dflt` and no GSUB all give the Arabic shaper. Shown live in chapter 12. The manual (`usermanual-opentype-features.xml:289`) says HarfBuzz falls back to `DFLT` when the requested tag has no lookups; the code falls back only when the tag is missing.
- A font with a GSUB script but no USE- or Indic-type script tag still goes through the script-specific shaper.

---

## 2. The `hb_ot_shaper_t` hooks and where they run

**Struct:** `hb-ot-shaper.hh:67-169`. **Pipeline:** `hb-ot-shape.cc` (`hb_ot_shape_internal` :1169-1199), `hb-ot-shape-normalize.cc`.

| Hook / field | When it runs (file:line) |
|---|---|
| `collect_features` | Plan time, in `hb_ot_shape_collect_features` (`hb-ot-shape.cc:362-366`). It runs after `rvrn`, the direction features, `frac/numr/dnom`, `rand` and the `Harf/HARF` sentinels, and **before** the common features (`abvm blwm ccmp locl mark mkmk rlig`), the horizontal features (`calt clig curs dist kern liga rclt`) and the user features. This hook is where shapers insert **GSUB pauses** (`add_gsub_pause(callback)`), and most script logic actually lives in those pause callbacks. |
| `override_features` | Plan time, after the user features (`:401-402`). Used to disable `liga` (Indic, Khmer), enable `clig` (Khmer), add `calt` as a maskable feature (Hangul), or append a final pause (Indic). |
| `data_create` / `data_destroy` | End of planning (`:241-249`) and plan destruction. Per-plan private data (`plan->data`), e.g. feature masks. A null return fails the plan. |
| `preprocess_text` | Shape time, on **Unicode** (before normalization and cmap), right after `hb_set_unicode_props`, the generic dotted circle, `hb_form_clusters` and `hb_ensure_native_direction` (`:1185-1190`). |
| `decompose` / `compose` | During normalization (`hb-ot-shape-normalize.cc:304-307`). They override `unicode->decompose/compose`. |
| `reorder_marks` | During normalization’s reorder round, after each run of combining marks is sorted by ccc (`hb-ot-shape-normalize.cc:396-397`). Only for runs of 32 marks or fewer (`HB_OT_SHAPE_MAX_COMBINING_MARKS`). |
| `setup_masks` | After normalization, before glyph mapping (`hb-ot-shape.cc:757-758`). “Shapers may NOT modify characters.” Indic-family shapers only store categories here and set masks later in pauses. |
| (pause callbacks) | Inside GSUB application, between stages. They see **glyphs**, not characters. |
| `postprocess_glyphs` | After GPOS/positioning, in `hb_ot_substitute_post` (`:961-964`). It runs after `hb_ot_hide_default_ignorables`. Only Arabic uses it (for `stch`). |
| `gpos_tag` | If set, GPOS is used only if the GPOS script found equals it; otherwise positioning falls back (`:135-136`). Only Hebrew sets it (`'hebr'`). |
| `normalization_preference` | `DEFAULT`, `NONE` (Hangul, Zawgyi) or `COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT` (Indic, Khmer, Myanmar, USE). |
| `zero_width_marks` | `NONE`, `BY_GDEF_EARLY` (before GPOS: Myanmar, USE) or `BY_GDEF_LATE` (after GPOS: default, Arabic, Hebrew, Thai) (`:1052-1078`). |
| `fallback_position` | Enables fallback mark positioning and, **since 12.2.0, legacy `kern` too** (`hb-ot-shape.cc:182`: `plan.apply_kern = script_fallback_position`). |

Hook usage per shaper (read from each shaper’s `const hb_ot_shaper_t` initializer):

| shaper | collect | override | data | preprocess | postprocess | decomp | comp | masks | reorder_marks | gpos_tag | norm | zero marks | fallback_pos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| default | | | | | | | | | | – | DEFAULT | LATE | yes |
| dumber | | | | | | | | | | – | DEFAULT | NONE | no |
| arabic | ✓ | | ✓ | | ✓ (stch) | | | ✓ | ✓ | – | DEFAULT | LATE | yes |
| hebrew | | | | | | | ✓ | | ✓ | hebr | DEFAULT | LATE | yes |
| thai | | | | ✓ | | | | | | – | DEFAULT | LATE | **no** |
| hangul | ✓ | ✓ | ✓ | ✓ | | | | ✓ | | – | NONE | NONE | yes |
| indic | ✓ | ✓ | ✓ | ✓ (vowel constraints) | | ✓ | ✓ | ✓ | | – | CD_NSC | NONE | no |
| khmer | ✓ | ✓ | ✓ | | | ✓ | ✓ | ✓ | | – | CD_NSC | NONE | no |
| myanmar | ✓ | | | | | | | ✓ | | – | CD_NSC | EARLY | no |
| myanmar_zawgyi | | | | | | | | | | – | NONE | NONE | no |
| use | ✓ | | ✓ | ✓ (vowel constraints) | | | ✓ | ✓ | | – | CD_NSC | EARLY | no |

(CD_NSC = `COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT`.)

**Full order of a shape call** (`hb_ot_shape_internal`): unicode props, then generic dotted circle, then clusters, then native direction, then **preprocess_text**, then [`hb_ot_substitute_pre`: rotate chars (mirroring/vertical), **normalize** (decompose/compose/reorder_marks), **setup_masks**, map glyphs, GSUB **with pauses** *or* morx], then position (GPOS/kerx/kern/fallback, mark zeroing, trak), then [`hb_ot_substitute_post`: remove AAT-deleted glyphs if no GPOS, variation selectors, hide default ignorables, **postprocess_glyphs**].

Pause callbacks return `bool`. Returning true means “buffer content changed, re-digest” (e.g. `initial_reordering_indic` returns true when it inserted dotted circles) **(inferred from usage; the GSUB pause loop wasn’t read)**.

---

## 3. Default and “dumber”

`hb-ot-shaper-default.cc:34-73`. Both are all-null hook tables. `dumber` exists only for morx fonts (`#ifndef HB_NO_AAT_SHAPE`). It differs from `default` by `ZERO_WIDTH_MARKS_NONE` and `fallback_position=false`. The rationale (issue #1528) is that AAT fonts do their own reordering and positioning, so HarfBuzz must not run Indic reordering or synthesize mark positions on top of them. Demonstration: `test/shape/data/in-house/fonts/e6185e88….ttf` (Tamil, morx plus GPOS, no GSUB). `hb-shape --trace` shows only `table morx` chain subtables, then GPOS with script tag `''`, and **no “reordering indic”** messages.

---

## 4. Arabic

**Files:** `hb-ot-shaper-arabic.cc` (805 lines), `hb-ot-shaper-arabic.hh`, `hb-ot-shaper-arabic-table.hh` (generated), `hb-ot-shaper-arabic-fallback.hh`, `hb-ot-shaper-arabic-win1256.hh`, `hb-ot-shaper-arabic-pua.hh` (generated), `hb-ot-shaper-arabic-joining-list.hh` (generated).

### 4.1 Joining
- Joining types U, L, R, D (C folded into D), plus two Syriac joining groups (ALAPH, DALATH_RISH) as extra state-machine columns, T (transparent) and X (“decide by general category”: Mn/Me/Cf give T, else U) (`:75-101`).
- `arabic_state_table[7][6]` (`:136-162`) is a 7-state machine. Each entry gives `prev_action`, `curr_action` and `next_state`, which is how a *following* letter retroactively changes the previous letter’s form (e.g. ISOL to INIT). States 4–6 handle Syriac Alaph’s FIN2/FIN3/MED2.
- `arabic_joining` (`:302-377`) primes the state from **pre-context** (`buffer->context[0]`) and finishes with **post-context**, skipping T characters. As it goes it sets `safe_to_insert_tatweel` on joined pairs (new flag in 5.x, `HB_GLYPH_FLAG_SAFE_TO_INSERT_TATWEEL`) and `unsafe_to_concat` elsewhere.
- **Mongolian**: `mongolian_variation_selectors` (`:380`) copies the base’s action onto FVS1–FVS4 (U+180B–180D, U+180F). Mongolian is shaped by **USE**, which reuses `setup_masks_arabic_plan` (section 9).
- Features (`collect_features_arabic` :187-266): `stch` + pause(`record_stch`), `ccmp`, `locl`, pause, then each of `isol fina fin2 fin3 medi med2 init` **with a pause after each**, then pause(`deallocate_buffer_var`), `rlig`, pause(`arabic_fallback_shape`) (Arabic script only), `calt`, a pause only if the font has no `rclt` (issue #1573), `liga`, `clig`, `mset`. `cswh` is deliberately not enabled (comment :251-259). ZWJ handling is manual for all of these (`F_MANUAL_ZWJ`), because in Arabic a ZWJ also means “don’t ligate”.

### 4.2 Mark reordering (UTR #53)
`reorder_marks_arabic` (`:721-782`) moves “modifier combining marks” (`modifier_combining_marks[]`, :692: hamza above/below, small high seen, …) of ccc 220/230 to the start of the mark run. It renumbers them to the internal ccc values 22/26 (`HB_MODIFIED_COMBINING_CLASS_CCC22/26`) so the sequence still looks sorted to the CGJ logic. The comment admits this can compose ALEF+MADDAH wrongly in ALEF, HAMZA, MADDAH.

### 4.3 Fallback shaping from presentation forms
- `data_create_arabic` (`:273-290`): `do_fallback` only for **Arabic script**, and only if **every** non-Syriac positional feature (`isol fina medi init`) “needs fallback”, i.e. isn’t found in GSUB (`hb-ot-map.cc:347`: `needs_fallback = !found`; `F_HAS_FALLBACK` keeps a mask bit allocated even when the feature is absent). One found feature disables the whole fallback.
- The fallback plan is built **lazily on first shape** (it needs a font for cmap lookups) and cached in the plan with an atomic compare-exchange (`arabic_fallback_shape` :417-445).
- `arabic_fallback_plan_create` (`hb-ot-shaper-arabic-fallback.hh:325-345`) first tries `init_unicode`: it **synthesizes real GSUB lookups in memory** with `hb_serialize_context_t`. Four SingleSubst lookups (init/medi/fina/isol) come from `shaping_table` (base char to presentation form, through the font’s cmap), plus three LigatureSubst `rlig` lookups (3-component, 2-component, mark ligatures like shadda+fatha), all `IgnoreMarks` except the mark ligatures. Pairs whose glyph would exceed 0xFFFF are skipped. If no lookup comes out of that, it tries `init_win1256`.
- These lookups run in a GSUB pause **after** the font’s own `rlig`, through the normal lookup applier (`arabic_fallback_plan_shape` :363-379).
- The ligature tables are keyed on **presentation-form codepoints**: they apply after the single substitutions have produced e.g. U+FEDF+U+FE8E for lam-alef. `gen-arabic-table.py` builds them from UnicodeData decompositions (`<initial>`, `<medial>`, …), restricted to a curated `LIGATURES` list. It also adds three invented **PUA** ligatures (U+F201 LELLAH, U+F211, U+F2EE shadda+fathatan) that only reach glyphs through the PUA cmap mapping (4.4).
- 15.1.0 NEWS: “Fix Arabic fallback shaping: wrong ligatures when a component is missing from the font, and disappearing marks in legacy fonts”. The current code drops a ligature if any component lacks a *nominal* glyph (`:150-161`).

### 4.4 Legacy Windows Arabic: win1256 and PUA
- **win1256** (`hb-ot-shaper-arabic-win1256.hh`): this detects a font whose cmap maps Arabic letters to glyph IDs equal to their Windows-1256 byte values (ALEF→199, LAM→225, ALEF MAKSURA→236, YEH→237, SUKUN→250; `arabic_fallback_plan_init_win1256` :251-290) and then applies a **hand-written GSUB lookup set compiled into the library**. The header uses a two-pass preprocessor trick: it `#include`s itself, defining `OT_MEASURE` the first time to compute sizes and emitting bytes the second time (“First we measure, then we cut”, :39-60, self-include at :345). It’s a nice example of hand-encoded OpenType data. **Changed in 14.4.0**: “Arabic Windows-1256 fallback shaping is now enabled on all platforms” (older descriptions say Windows-only; the exact old guard wasn’t checked).
- **PUA** (`hb-ot-shaper-arabic-pua.hh`, from `gen-arabic-pua.py ArabicPUASimplified.txt ArabicPUATraditional.txt`): this is **not in the shaper but in cmap**. For a symbol cmap (3,0) in a font whose **OS/2 version is 0** and whose `fsSelection` high byte is font page 0xB2 (Simplified Arabic) or 0xB3 (Traditional Arabic), `hb-ot-cmap-table.hh:2210-2231` installs a getter that maps Unicode to the legacy PUA codes (`OS2::get_font_page`, `hb-ot-os2-table.hh:335-345`). `hb-ft.cc:451-454` does the same for FreeType. The fallback shaping above then works on such fonts. 14.2.1 NEWS fixed the isolated lam-alef-maksura PUA ligature.

### 4.5 Stretching (`stch`, Syriac abbreviation marks and similar)
- `stch` is applied **first** among the shaper’s features. `record_stch` (`:456-480`) then marks every glyph that a MultipleSubst *multiplied*. Odd component index means `STCH_REPEATING`, even means `STCH_FIXED`. It stores this in the same byte as the joining action (“We abuse the same byte for other things”, :124-126) and sets a scratch flag.
- `apply_stch` (`:482-678`, run from `postprocess_glyphs`, i.e. **after GPOS**) measures, for each stretch sequence, the width of the adjacent “word” context (glyphs whose GC passes `HB_ARABIC_GENERAL_CATEGORY_IS_WORD` or that are default-ignorable). It then computes how many extra copies of the repeating tiles fill it, possibly adding one more copy and overlapping them (`extra_repeat_overlap`). It grows the buffer in a two-pass MEASURE/CUT loop and lays out the tiles with x_offsets and zero advances. A cap, `STCH_MAX_GLYPHS = 256`, was hardened in 13.x/14.x NEWS (“overflow when applying stch with malicious fonts”). LTR buffers are reversed around the algorithm.

---

## 5. Hebrew

`hb-ot-shaper-hebrew.cc`.
- `compose_hebrew` (`:35-163`): when Unicode composition fails **and the font has no GPOS `mark` feature** (`plan->has_gpos_mark`), it composes into Hebrew presentation forms (U+FB1D–FB4E: dagesh forms, shin dots, rafe…). These are composition-excluded in Unicode but needed by old fonts.
- `reorder_marks_hebrew` (`:166-187`): it swaps patah/qamats + sheva/hiriq + meteg/below sequences (the ccc order Unicode gives them is visually wrong). Improved in 5.x (“multiple mark interactions in Hebrew”).
- `gpos_tag = 'hebr'` (issue #347): a GPOS without a `hebr` script is ignored, and fallback mark positioning is used instead.

---

## 6. Thai and Lao

`hb-ot-shaper-thai.cc`.
- **Sara Am** (`preprocess_text_thai` :265-369): this runs whether or not the font has OpenType tables. U+0E33/U+0EB3 is decomposed to NIKHAHIT + SARA AA, and the nikhahit is moved **backwards over preceding above-base marks**. The nikhahit is relabelled Mn so it’s zeroed as a mark, and clusters are merged with the previous grapheme. The same code handles Lao by masking bit 0x80 (`IS_SARA_AM(x) (((x) & ~0x0080u) == 0x0E33u)`). This follows Uniscribe (per the comment, which cites Eric Muller), not the MS spec. Test file: `test/shape/data/in-house/tests/sara-am.tests`.
- **PUA fallback** (`do_thai_pua_shaping` :221-262, `thai_pua_shape` :98-152): **Thai only (not Lao)**, and only if the font has **no Thai GSUB script** (`!plan->map.found_script[0]`). Two small state machines (above: T0–T3, below: B0–B2) classify consonants (NC/AC/RC/DC) and marks (AV/BV/T) and choose SD/SL/SDL/RD actions. These rewrite codepoints, **before cmap**, to Windows PUA (U+F700…) or, if the font lacks those, Mac PUA (U+F88x) variants: shifted tone marks, and YO YING or THO THAN without their descender. Reference: linux.thai.net/~thep/th-otf/shaping.html.
- The U+0E3A ccc tweak lives in `unicode->modified_combining_class` (comment :295-300), not in the shaper.
- `fallback_position = false`: so **since 12.2.0 a Thai font with only a legacy `kern` table gets no kerning** in HarfBuzz.

---

## 7. Hangul

`hb-ot-shaper-hangul.cc`.
- Normalization mode `NONE`: the shaper does its own composition and decomposition in `preprocess_text_hangul` (`:144-405`), *with knowledge of the font*. The rules:
  - Compose <L,V(,T)> into a precomposed syllable if the font has that glyph.
  - Decompose a precomposed <LV>/<LVT> into jamo if the font lacks the syllable glyph but has all the jamo.
  - Combine <LV,T> if possible, otherwise decompose.
  - Decomposed (Old Hangul) syllables get `ljmo`/`vjmo`/`tjmo` features through a per-glyph action byte.
- **Tone marks** U+302E/U+302F: moved *before* the syllable, unless the tone-mark glyph has zero advance (`is_zero_width_char`, :136), in which case it’s assumed to overstrike. A tone mark with no valid syllable gets a dotted circle (before or after it, depending on its width). This is a **fourth, Hangul-specific dotted-circle path**.
- **14.3.0 change**: `calt` is now disabled only on jamo, not on the whole run. `override_features_hangul` (`:67-82`) adds `calt` as a maskable feature, and `setup_masks_hangul` (`:408-430`) clears the calt bit on L/V/T jamo. This works around Noto Sans CJK / Source Han putting jamo lookups in `calt`; Uniscribe doesn’t apply calt to Hangul. Older descriptions say “calt is disabled for Hangul”. Tests: `hangul-calt.tests`.

---

## 8. The Indic family: Indic, Khmer, Myanmar, and the syllable machinery

### 8.1 Shared categories table
- `gen-indic-table.py IndicSyllabicCategory.txt IndicPositionalCategory.txt Blocks.txt` produces `hb-ot-shaper-indic-table.cc`. The header shows the Unicode 18.0.0 data files. Only allowed blocks are included (Devanagari… Malayalam, Myanmar (+Ext-A/B/C), Khmer, Vedic Ext, General Punctuation, Superscripts and Subscripts, Devanagari Ext/Ext-A, Bengali Supplement, Basic Latin, Latin-1), plus U+00A0 and U+25CC.
- **One table serves three shapers.** `hb_indic_get_categories(u)` returns a 16-bit value, category | (position << 8). The Indic, Khmer and Myanmar Ragel machines `export` category numbers from **one shared number space**. The generator emits `static_assert (OT_x == K_Cat(x))` so that a category used by several machines has the same value everywhere (e.g. C=1, H=4, ZWNJ=5, ZWJ=6, PLACEHOLDER=10, DOTTEDCIRCLE=11, Ra=15, VAbv..VPst=20–23, Myanmar-only values 32+, SMPst=57).
- Mapping decisions in the generator worth explaining: `category_map` (Unicode ISC to HB category) and `position_map` (IPC to position; split vowels resolve to the position of their *last* part). Per-script `matra_pos_*` functions turn Unicode’s Left/Right/Top/Bottom into Uniscribe-style positions (e.g. Telugu right matras ≤U+0C42 are BEFORE_SUB). A big `category_overrides` dict: Ra per script, Khmer Robatic/Xgroup/Ygroup, Myanmar medials, Vedic signs as Symbol, variation selectors as VS. Bindus with `Not_Applicable` position become `SMPst`. For Khmer and Myanmar, matras are turned into VPre/VAbv/VBlw/VPst *categories* rather than positions.
- 15.1.0 NEWS: “Fix Indic shaping of the Unicode 18 Devanagari and Bengali additions”. 14.x: “Indic: categorize U+1CF5 and U+1CF6 as CS”. Test file `indic-unicode18.tests`.

### 8.2 Ragel syllable machines
- Sources are `hb-ot-shaper-{indic,khmer,myanmar,use}-machine.rl`. The `.hh` files are committed generated output. `gen-ragel-artifacts.py` (run from meson only when ragel is installed) runs `ragel -e -F1` and copies the result back into `src/`. If the source tree is read-only, it verifies that the committed copy matches.
- Each machine is a Ragel **scanner** (`|* … *|`, longest match). It reads `info[p].<shaper>_category()` and labels each match through `found_syllable(type)`: `syllable = (serial << 4) | type`, with the serial cycling 1..15. The low nibble is the type, the high nibble lets `foreach_syllable` tell adjacent syllables apart. A **broken cluster** match sets `HB_BUFFER_SCRATCH_FLAG_HAS_BROKEN_SYLLABLE`.
- Indic grammar (`indic-machine.rl:95-122`): `consonant_syllable = (Repha|CS)? cn complex_syllable_tail`, `vowel_syllable`, `standalone_cluster` (placeholder or dotted circle base), `symbol_cluster`, `broken_cluster = reph? n? complex_syllable_tail`, `other`. Syllable types are at :45-52.
- Khmer grammar (`khmer-machine.rl:78-96`): “experimentally extracted from what Uniscribe allows”. It has Robatic, Xgroup and Ygroup classes.
- Myanmar grammar (`myanmar-machine.rl:93-116`): kinzi `k = (Ra As H)`, a medial group, vowel groups and tone groups. 10.x NEWS: all tone marks, including visarga, are allowed in any order.

### 8.3 Indic shaper (`hb-ot-shaper-indic.cc`, 1541 lines)
- **Per-script config** `indic_configs[]` (`:153-166`) gives the virama codepoint, reph position (AFTER_MAIN / BEFORE_SUB / AFTER_SUB / BEFORE_POST / AFTER_POST), reph mode (IMPLICIT Ra+H, EXPLICIT Ra+H+ZWJ for Telugu, LOG_REPHA for Malayalam’s encoded dot reph) and blwf mode (POST_ONLY for Telugu/Kannada).
- **Old vs new spec**: `is_old_spec = has_old_spec && chosen_script[0] doesn't end in '2'` (`:325`). Old spec (`deva`) moves the first post-base halant after the last consonant (except Kannada with double halants) and applies blwf differently.
- **Feature/pause layout** (`collect_features_indic` :244-269):
  - pause(`setup_syllables_indic`), then `locl`, `ccmp` (both per-syllable)
  - pause(`initial_reordering_indic`), then `nukt akhn rphf rkrf pref blwf abvf half pstf vatu cjct`, **each followed by its own pause**
  - pause(`final_reordering_indic`), then `init pres abvs blws psts haln` applied together
  - `override_features_indic` disables `liga` and appends pause(`hb_syllabic_clear_var`).
  - Every one of these is `F_PER_SYLLABLE`.
- **Font-probing to classify consonants** (`consonant_position_from_face` :361-394, `update_consonant_positions_indic` :437-460). Whether a consonant is “below-base”, “post-base” or “base” is decided by asking the font: `would_substitute` on {virama, C} and {C, virama} against the `blwf`/`vatu`, `pstf` and `pref` lookups. Both orders are tried because broken fonts such as FreeSans copied old-spec lookups into new-spec scripts and Uniscribe honours them. Reph detection also probes `rphf` (`:504-529`). A zero-context vs context heuristic is commented “DON’T TOUCH OTHERWISE” (`:327-336`). This is the main thing a type designer should understand: **the font’s own lookups steer the reordering**.
- **Initial reordering** (`initial_reordering_consonant_syllable` :463-934) follows the MS Devanagari spec steps:
  1. find the base, scanning backwards and skipping below/post-base consonants, ZWJ after halant stopping the search
  2. mark the reph (`POS_RA_TO_BECOME_REPH`)
  3. old-spec halant move
  4. attach joiners/nukta/halant to the previous char’s position
  5. **stable sort by position**
  6. flip runs of left matras (issue #3863)
  7. set masks: rphf on reph, half/blwf on pre-base, blwf/abvf/pstf on post-base, the old-spec eyelash Ra special case, pref only where `pref.would_substitute` matches, ZWNJ disabling `half`.
  
  Kannada `Ra,H,ZWJ` is treated as `Ra,ZWJ,H` (:474-482). Vowel syllables and placeholder or dotted-circle clusters reuse the consonant logic (“We treat Vowels and placeholders as if they were consonants”, :60-66).
- **Final reordering** (`final_reordering_syllable_indic` :999-1441): this runs on glyphs after the basic features. Pre-base matras move to before the first half form. Reph moves according to the reph position, through numbered steps 1–6 from the spec, with the comment “This is our take on what step 4 is trying to say (and failing, BADLY)” (:291). Pre-base-reordering Ra (pref) is moved only if a substitution actually happened. `init` is applied to a left matra at word start.
- `decompose_indic` keeps some letters precomposed (U+0931, U+09DC, U+09DD, U+0B94). `compose_indic` refuses to recompose split matras and recomposes U+09AF+U+09BC to U+09DF.
- **NEWS 12.2.0, a behaviour change older books would get wrong**: in per-syllable features, the **backtrack and lookahead of (Chain)Context rules are now confined to the syllable**, as in DirectWrite. Earlier, HarfBuzz deliberately allowed crossing syllables, but buggily. The mechanism is the matcher’s `per_syllable`/`syllable` check, GSUB only (`hb-ot-layout-gsubgpos.hh:850-872`).
- NEWS 12.x also removed the “uniscribe-bug-compatible” mode from Indic and Khmer.

### 8.4 Khmer (`hb-ot-shaper-khmer.cc`)
- Pauses: `setup_syllables_khmer`, then **`reorder_khmer` *before* `locl`/`ccmp`** (unlike Indic, where `locl`/`ccmp` run before reordering). Then `pref blwf abvf pstf cfar` are applied **together with no pauses** (testing showed Uniscribe doesn’t pause; issue #974), then `hb_syllabic_clear_var`, then `pres abvs blws psts` globally (`:102-133`). `clig` is forced on and `liga` off (`:135-144`).
- `reorder_consonant_syllable` (`:206-280`): Coeng+Ro is moved to the syllable start and gets `pref`, and what follows gets `cfar`. VPre is moved to the start. `decompose_khmer` splits the two-part vowels U+17BE–17C5 into U+17C1 + the vowel (`:326-346`).

### 8.5 Myanmar (`hb-ot-shaper-myanmar.cc`)
- Pauses: `setup_syllables`, `locl`, `ccmp`, `reorder_myanmar`, then `rphf pref blwf pstf` each with a pause, then clear the syllables, then `pres abvs blws psts` (`:111-137`). Zero-width marks EARLY.
- Reordering (`:179-300`) assigns positions (kinzi as RA_TO_BECOME_REPH, medial Ra as PRE_C, VPre as PRE_M, below-base handling, Asat), stable-sorts, and flips left-matra runs.
- **Zawgyi** (`:370-386`): a null shaper with normalization NONE, selected only when the caller sets script `Qaag` (issue #1162). It exists so that mis-encoded Zawgyi text isn’t “fixed” by Unicode logic.

### 8.6 Syllabic helpers and dotted circles
`hb-ot-shaper-syllabic.cc`:
- `hb_syllabic_insert_dotted_circles` (`:33-100`) runs in a GSUB pause (the buffer holds **glyph IDs** by then, so it inserts the font’s U+25CC glyph). It does nothing if the buffer flag `DO_NOT_INSERT_DOTTED_CIRCLE` is set, if there are no broken syllables, or if the font lacks U+25CC. One circle goes at the start of each broken syllable, **after any leading Repha** (Indic: `Repha` category; USE: `R`). It’s given the shaper’s category (Indic DOTTEDCIRCLE with POS_END, USE `B`), so it joins the syllable as a base.
- `hb_syllabic_clear_var` frees the `syllable()` buffer var in a final pause.

There are **four distinct dotted-circle insertion paths**, which a book should lay side by side:
1. Generic `hb_insert_dotted_circle` (`hb-ot-shape.cc:552-578`): before `preprocess_text`, only if the buffer has the BOT flag, no pre-context, a Unicode mark first, and the font has U+25CC.
2. Vowel constraints (section 10): in `preprocess_text`, **inserts the Unicode character U+25CC without checking the font**.
3. Broken syllables (above): in a GSUB pause, as a glyph.
4. Hangul tone marks (section 7).

Example: `hb-shape NotoSansDevanagari-Regular.ttf -u U+0905,U+093E` gives `[adeva|uni25CC|aavowelsigndeva]`, the vowel-constraint path. The font is in `test/subset/data/fonts/`.

---

**Corrections from chapter 23:** the Myanmar kinzi gets `POS_AFTER_MAIN` (`hb-ot-shaper-myanmar.cc:216`), not `POS_RA_TO_BECOME_REPH`. In Khmer, `locl` and `ccmp` share the stage with `pref blwf abvf pstf cfar`; Khmer’s and Myanmar’s presentation features are not per syllable (Indic’s are). Neither Khmer nor Myanmar calls `would_substitute`: COENG + RO is moved without a `pref` probe.

## 9. Universal Shaping Engine (USE)

**Files:** `hb-ot-shaper-use.cc`, `hb-ot-shaper-use-machine.rl`, `hb-ot-shaper-use-table.hh` (generated), `gen-use-table.py`, `ms-use/` (Microsoft-supplied override data), `test-use-table.cc`.

### 9.1 Table generator
- `gen-use-table.py` reads IndicSyllabicCategory, IndicPositionalCategory, ArabicShaping, DerivedCoreProperties, UnicodeData, Blocks, Scripts, and **`ms-use/IndicSyllabicCategory-Additional.txt` and `IndicPositionalCategory-Additional.txt`**. The latter are maintained by Andrew Glass at Microsoft and updated per Unicode version, through “Updated for Unicode 18.0 … 2026-09-04”. They override Unicode’s ISC/IPC for shaping, e.g. “25CC; Consonant… Reassigned to allow it to cluster as a generic base”.
- `DISABLED_SCRIPTS = {Arabic, Lao, Samaritan, Syriac, Thai}` (`:40-46`): these get no USE categories. The Indic nine are **not** disabled, so `dev3`-style fonts work.
- Each USE category is a predicate over (U, ISC, UDI, UGC, AJT) (`is_BASE`, `is_HALANT`, …, `is_SAKOT` = U+1A60 only, hieroglyph categories). Exactly one must match (asserted). The category then gets a positional suffix (Abv/Blw/Pst/Pre) from `use_positions`. There are hand fixes for codepoints that lack ISC values (U+1CE2–1CE8, Tibetan U+0F18/19/3E/3F).
- Like the other generators, it has a `--rust` mode (output for HarfRust) and uses the `packTab` package to build compact multi-level lookup tables.

### 9.2 Machine
- Categories are exported at `use-machine.rl:63-108` (O, B, N, GB, CGJ, SUB, H, HN, ZWNJ, WJ, R, CS, IS, Sk, G, J, SB, SE, HVM, HM, HR, RK, F*, M*, CM*, V*, VM*, SM*, FM*).
- Grammar `:111-187`: virama-terminated, sakot-terminated, standard, number-joiner-terminated, numeral, symbol, **hieroglyph** (Egyptian format controls), broken and non clusters.
- **The machine runs over a filtered view of the buffer** (`find_syllables_use` :257-292): it skips CGJ, and it **hides a ZWNJ that’s followed (ignoring CGJ) by a mark**. The labels are then written back over original index ranges. Built with HarfBuzz’s iterator algebra (`hb_iter | hb_enumerate | hb_filter | machine_index`), so it’s a good showcase of the C++ style.

### 9.3 Shaper
- Feature stages (`collect_features_use` :110-150) map onto the USE spec groups:
  - setup syllables
  - “Default glyph pre-processing”: `locl ccmp nukt akhn`
  - “Reordering group”: clear substitution flags, `rphf`, `record_rphf_use`, clear flags, `pref`, `record_pref_use`
  - “Orthographic unit shaping”: `rkrf abvf blwf half pstf vatu cjct`
  - `reorder_use`, clear syllables
  - “Topographical”: `isol init medi fina`, pause
  - “Standard typographic presentation”: `abvs blws haln pres psts`
- **Recording what the font did**: after `rphf`, the first *substituted* glyph under the rphf mask is recategorized as `R` (repha). After `pref`, the first substituted glyph becomes `VPre` (`:311-358`). So reordering follows the font’s substitutions, not just the characters.
- `reorder_syllable_use` (`:362-446`): a repha moves forward to just before the first post-base glyph (or to the end). VPre/VMPre move back to after the last halant, and only the first component of a MultipleSubst moves (`lig_comp == 0`).
- **Joining in USE**: `data_create_use` makes an embedded Arabic plan for scripts in `has_arabic_joining()` (generated by `gen-arabic-joining-list.py` from ArabicShaping+Scripts: Adlam, Arabic, Chorasmian, Hanifi Rohingya, Mandaic, Manichaean, Mongolian, N’Ko, Old Uyghur, Phags-pa, Psalter Pahlavi, Sogdian, Syriac). These use the **Arabic joining state machine** for `isol/init/medi/fina` masks. Other USE scripts get **syllable-level** topographical forms (`setup_topographical_masks` :232-295): each *cluster* is isol/init/medi/fina according to its neighbours, with non-clusters and hieroglyph clusters breaking the chain. NEWS 2.8.0: joining scripts other than Arabic and Syriac moved from the Arabic shaper to USE.
- Sinhala moved from Indic to USE in 4.4.0.

---

## 10. Vowel constraints

`hb-ot-shaper-vowel-constraints.cc` (generated by `gen-vowel-constraints.py ms-use/IndicShapingInvalidCluster.txt Scripts.txt`). `_hb_preprocess_text_vowel_constraints` is the `preprocess_text` of Indic and USE. For each script it has a switch of **prohibited codepoint sequences**, e.g. Devanagari U+0905 + U+093E, which looks like U+0906, and similar spoofing pairs. It inserts U+25CC between them (“UGLY UGLY UGLY business”, issue #1019). The data is Microsoft’s (dated 2015 and 2019 in the header). It respects `DO_NOT_INSERT_DOTTED_CIRCLE` but **doesn’t check that the font has a dotted circle**. Tests: `indic-vowel-letter-spoofing.tests`, `use-vowel-letter-spoofing.tests`.

---

## 11. Generators and the data they read

| Generator | Output | Inputs |
|---|---|---|
| `gen-arabic-table.py [--rust]` | `hb-ot-shaper-arabic-table.hh` (joining types, shaping_table, ligature tables) | UCD ArabicShaping, UnicodeData, Blocks |
| `gen-arabic-joining-list.py` | `hb-ot-shaper-arabic-joining-list.hh` (`has_arabic_joining`) | ArabicShaping, Scripts |
| `gen-arabic-pua.py [--rust]` | `hb-ot-shaper-arabic-pua.hh` | ArabicPUASimplified.txt, ArabicPUATraditional.txt (legacy Microsoft PUA mappings; where they come from isn’t stated in the script) |
| `gen-indic-table.py [--rust]` | `hb-ot-shaper-indic-table.cc` | IndicSyllabicCategory, IndicPositionalCategory, Blocks |
| `gen-use-table.py [--rust]` | `hb-ot-shaper-use-table.hh` | ISC, IPC, ArabicShaping, DerivedCoreProperties, UnicodeData, Blocks, Scripts, ms-use/*-Additional.txt |
| `gen-vowel-constraints.py [--rust]` | `hb-ot-shaper-vowel-constraints.cc` | ms-use/IndicShapingInvalidCluster.txt, Scripts |
| `gen-ragel-artifacts.py` | `*-machine.hh` | `*-machine.rl` (needs ragel) |

The `--rust` flags exist so HarfRust (the Rust port, an optional `harfrust` backend for testing) can share the same generated data. That’s a modern development older accounts won’t mention. `packTab` is an external Python package by the HarfBuzz authors **(inferred)**.

---

## 12. AAT: when HarfBuzz uses morx, kerx, kern and trak

**File:** `hb-ot-shape.cc:58-65, 84-228, 268-292, 905-956`.

**Substitution:**
`apply_morx = has morx-or-mort && (horizontal || no GSUB)` (`_hb_apply_morx`, :60-65, issue #2124). When it’s true:
- **GSUB is never applied**, even though the shaper’s OpenType features were collected.
- The script shaper becomes `dumber` (section 1).
- `hb_aat_layout_substitute` runs instead of `plan->substitute` (:909-918). If there’s no GDEF, glyph classes are synthesized from Unicode first.
- `mort` (the old format) is used only if there’s no `morx` (`hb-aat-layout.cc:299-327`).

**Positioning** (`:157-185`):
```
has_gsub = !apply_morx && font has GSUB
if (has_kerx && !(has_gsub && has_gpos))  apply_kerx      // prefer GPOS over kerx if GSUB is present (#3008, 2.8.2)
else if (has_gpos)                          apply_gpos
if (!apply_kerx && (!GPOS-has-kern-feature || !apply_gpos)) {
   if (has_kerx) apply_kerx
   else if (has legacy kern) apply_kern = script_fallback_position
}
apply_fallback_kern = script_fallback_position && none of the above
```
Consequences:
- A morx font with GPOS and no kerx gets GPOS (3.1.0 NEWS).
- A font with GSUB and GPOS, where GPOS has no `kern` feature, **also gets the legacy `kern` table** on top of GPOS (`position()` :274-286 runs kern independently of GPOS). Test: `tt-kern-gpos.tests`.
- Legacy `kern` is applied only by shapers with `fallback_position`, i.e. default, Arabic, Hangul and Hebrew (12.2.0).
- Possible quirk **(inferred, untested)**: with GSUB+GPOS+kerx and no GPOS `kern` feature, both `apply_gpos` and `apply_kerx` become true. `position()` is `if (gpos) … else if (kerx)`, so kerx doesn’t run, but `zero_marks` and mark adjustment are computed as if kerx ran.
- `disable_gpos` (Hebrew `gpos_tag`) feeds into `has_gpos`.

**Marks with AAT:**
- With morx, `adjust_mark_positioning_when_zeroing` is forced off for Apple Color Emoji (#2967).
- `zero_marks` is false when kerx applies.
- AAT-deleted glyphs (glyph 0xFFFF) are removed **before** GPOS if GPOS will run (so they don’t block contextual positioning; 4.2.0), otherwise **after** positioning (`:945-956`). 11.0.1 NEWS fixed deleted-glyph marks interfering with fallback mark positioning.

**Tracking:**
`apply_trak = font has trak && font has STAT` (`:216-221`). The comment cites Ned Holbrook: trak is applied by default for “modern fonts”, detected by the STAT table. trak runs at the very end of `position()`.

**History of trak, which older descriptions get wrong:**
- 10.3.0 moved trak into the ot font functions (applied to advances) and dropped the `trak` pseudo-feature.
- 11.0.1 reverted it, and tracking is applied during shaping again.
- So in 15.1 tracking is a shaping step and there’s **no feature to turn it off**. **(inferred: grep finds no `trak` feature tag in hb-ot-shape.cc.)**

---

## 13. AAT tables in detail

### 13.1 Common machinery (`hb-aat-layout-common.hh`, 1453 lines)
- **Lookup tables** (formats 0, 2, 4, 6, 8, 10; `:286-860`) map glyph to value. Classes from lookups. 0xFFFF is `DELETED_GLYPH` (`:117`).
- **Reserved classes**: `CLASS_END_OF_TEXT=0`, `OUT_OF_BOUNDS=1`, `DELETED_GLYPH=2`, `END_OF_LINE=3` (`:914-917`). Start states: `START_OF_TEXT=0`, `START_OF_LINE=1` (`:929-930`). HarfBuzz always starts in state 0.
- **`ObsoleteTypes` vs `ExtendedTypes`** (`:1195-1269`) let one template implement both `mort`/`kern` (16-bit, byte-offset states and classes, class array tables) and `morx`/`kerx` (32-bit, state indices, lookup-table classes). In obsolete tables `newState` is a byte offset converted to an index, which **can be negative** (`new_state`, `get_entry` “State can be negative”). `offsetToIndex` deliberately returns an out-of-range index for offsets before the array (issues #3483, #2816).
- **`StateTableDriver::drive`** (`:1282-1440`) is the one loop used by every state-machine subtable (morx rearrangement, contextual, ligature, insertion; kerx formats 1 and 4; kern format 1):
  - It gets the class of the current glyph (with a per-subtable class cache), looks up the entry, calls the subtable’s `transition`, and advances unless `DontAdvance`.
  - Epsilon (DontAdvance) loops are bounded by `buffer->max_ops`.
  - A **fast path** skips runs of same-class, non-actionable glyphs in the start state. NEWS 12.x: “speed up state machine on Apple silicon using a fast-path”.
  - **Per-range feature flags**: when user features have ranges, it checks each glyph’s cluster against `range_flags` and resets to the start state where the subtable is disabled.
  - **Safe-to-break computation** (`:1366-1426`): it looks up the would-be entry from the start state to decide whether breaking before the current glyph would change the result (issue #2860). This gives granular `unsafe_to_break` for AAT. Contrast `mortmorx::apply` and `KerxTable::apply`, which mark the **whole buffer `unsafe_to_concat`**.
- `hb_aat_apply_context_t` (`:121`): if the font has GDEF glyph classes, glyph props are refreshed from GDEF on every AAT substitution (`output_glyphs`, `replace_glyph`; `:222-271`). A buffer glyph set and per-subtable “first set” let whole subtables be skipped when no glyph in the buffer can start an action (`buffer_intersects_machine`; trace message “skipped chainsubtable N because no glyph matches”).
- Budgets: `charge_buffer_pass`, `HB_AAT_MAX_SUBTABLES = 1024` (`hb-limits.hh:98-99`), and the map builder budget (`HB_BUDGET_AAT_MAP`). These come from the 14.5.0 “work budgets” hardening **(inferred link to that NEWS item)**.

### 13.2 morx / mort (`hb-aat-layout-morx-table.hh`, 1544 lines)
- **Structure**: `mortmorx` (:1352) holds chains. Each `Chain` (:1132) has `defaultFlags`, feature entries (type, setting, enableFlags, disableFlags) and subtables. Each `ChainSubtable` (:1044) has coverage bits and `subFeatureFlags`.
- **Compiling flags** (`Chain::compile_flags` :1138-1178): start from `defaultFlags`. For each feature entry whose (type, setting) is requested in the map, `flags = (flags & disableFlags) | enableFlags`. There are two special cases: deprecated Letter Case/Small Caps retried as Lower Case/Small Caps (#1342), and **Language Tag feature type (39) matched against the `ltag` table** for the buffer language (5.0.0 “language-specific forms in AAT shaping”).
- **Applying** (`Chain::apply` :1181-1265): a subtable runs only if its `subFeatureFlags` intersect some range’s flags and its vertical/all-directions coverage fits.
- **Processing direction**: bits 28 (Logical) and 30 (Backwards) give four orders (layout/reverse-layout/logical/reverse-logical). HarfBuzz keeps the buffer in logical order and reverses it around a subtable as needed (the big quoted spec comment at :1213-1238).
- **Blocklist**: `morx::is_blocklisted` (`hb-aat-layout.cc:214-232`) drops the morx of one known-broken font (AALMAGHRIBI.ttf, identified by morx/GSUB/GDEF lengths; 10.3.0).
- **Subtable types**:
  - **Rearrangement** (:49-196): MarkFirst/MarkLast/DontAdvance and a 4-bit verb. The `map[16]` table encodes the 15 verbs (Ax→xA … ABxCD→DCxBA) as “move l from start, r from end, maybe flip”. It merges clusters over the range and is limited to `HB_MAX_CONTEXT_LENGTH`.
  - **Contextual** (:198-384): SetMark and DontAdvance. Each entry can substitute the **marked** glyph and/or the **current** glyph through per-entry lookup indices (morx) or a shared offset array (mort). The comment “Looks like CoreText applies neither mark nor current substitution for end-of-text if mark was not explicitly set” (:251-253) is behaviour reverse-engineered from CoreText. 14.2.1 fixed legacy mort contextual offsets that could produce out-of-font glyph IDs.
  - **Ligature** (:449-640): SetComponent pushes the glyph’s output position onto a **ring-buffer stack** (`match_positions[HB_MAX_CONTEXT_LENGTH]`). PerformAction walks the ligature action list: each action adds `component[glyph + offset]` (a sign-extended 30-bit offset) to an accumulating ligature index, and Store/Last emits `ligature[idx]`. The ligature replaces the glyph at the cursor, the **other components become DELETED_GLYPH** (kept in the buffer and marked), and clusters are merged.
  - **Noncontextual** (:641-701): a plain lookup-table substitution in place, with its own copy of the range-flag check (“Keep in sync”).
  - **Insertion** (:703-913): marked and current insert lists, each up to 31 glyphs, inserted before or after. **The Kashida-like vs split-vowel-like flags are ignored** (“TODO We ignore KashidaLike setting”, :817, :843). The position after insertion follows the DontAdvance reading in issue #1224. 14.3.1 fixed insertion at end of text.
- Within a chain, subtables run in order. Chains run in order (`mortmorx::apply` :1459-1480).

### 13.3 Feature mapping (`hb-aat-layout.cc:102-203`, `hb-aat-map.cc`, `hb-aat-map.hh`)
- `feature_mappings[]` is a sorted table, “courtesy of Apple”, from OpenType tag to (AAT type, selector to enable, selector to disable): `liga` to Ligatures/CommonOn/Off, `smcp` to LowerCase/SmallCaps, `onum` to NumberCase, `hist` to type 40, `vrtr` to VerticalSubstitution (2,3), `rlig` (5.3.0), etc. Public API: `hb_aat_layout_find_feature_mapping`.
- `hb_aat_map_builder_t::add_feature` (`hb-aat-map.cc:38-82`): **a user feature does nothing unless the font has a `feat` table that exposes that feature type** (the early return if `feat` has no data). For `aalt`, the feature *value* is the selector of Character Alternatives (type 17).
- Exclusive vs non-exclusive settings: in non-exclusive features, selectors come in even/odd on/off pairs, so duplicates are found by comparing `setting & ~1`.
- **Feature ranges** (7.0.0): `compile` (:84-180) sorts start/end events, snapshots the active features per range, and compiles chain flags per range into `chain_flags[chain] = sorted vector of {flags, cluster_first, cluster_last}`. Adjacent ranges with equal flags are merged (`mortmorx::compile_flags` :1426-1455), under a budget.
- **Plan vs per-call**: the plan’s `aat_map` is compiled with **no features** (default flags only). If the call has *any* user features, `hb_aat_layout_substitute` rebuilds a map for that call (`hb-aat-layout.cc:290-298`). OpenType features the shaper enables by default (`liga`, `calt`, …) are **not** fed into the AAT map, so morx defaults come purely from the chains’ `defaultFlags`.

### 13.4 kerx (`hb-aat-layout-kerx-table.hh`, 1270 lines)
- `KerxTable<T>` (:999) is a **template shared with the legacy `kern` table** (`KernOT`, `KernAAT` in `hb-ot-kern-table.hh` derive from it).
- `apply` (:1055-1138):
  - Variation subtables are skipped for the obsolete (kern) types.
  - Direction must match the Vertical bit.
  - The Backwards flag drives buffer reversal.
  - On the **first cross-stream subtable**, every glyph is set to `ATTACH_TYPE_CURSIVE` with a chain to its neighbour. This makes cross-stream offsets accumulate along the line, using GPOS’s own attachment post-processing. The scratch flag is intentionally not set.
- **Formats**:
  - 0: sorted pairs.
  - 1: state machine with a value stack (Push flag). In cross-stream, the value `-0x8000` resets. “CoreText doesn’t do crossStream kerning in vertical. We do.” (:383).
  - 2: class-based two-dimensional array.
  - 4: **anchor/control-point/coordinate mark attachment**. Action type 0 uses control points, 1 uses **`ankr`** anchors, 2 uses coordinates. It uses `resolve_cross_offset` from GPOS. NEWS 15.1.0 fixed a format 4 regression from 14.3.0.
  - 6: extended pairs.
- Formats 0, 2 and 6 run only if `kern` was requested (`plan->requested_kerning`, i.e. the user didn’t disable `kern`), and they’re **silently skipped if their Backwards coverage bit is set** (:112, :488, :796). Format 1 still runs for cross-stream subtables. Format 4 always runs. Pair kerning goes through `hb_kern_machine_t` (`hb-kern.hh`).
- NEWS 15.1.0: “wrong kerx kerning (formats 1 and 2)”.

### 13.5 Legacy `kern` (`hb-ot-kern-table.hh`, 435 lines) and `hb-kern.hh`
- `kern` (:313) is a union over **Microsoft/OpenType version 0** (`KernOT`: 16-bit version, 6-byte subtable headers, coverage Horizontal/Minimum/CrossStream/Override) and **Apple version 1.0** (`KernAAT`: 32-bit version 0x00010000, 8-byte headers, Vertical/CrossStream/Variation, tupleIndex not implemented). It dispatches on the major version.
- **Formats**: 0 (pairs), 1 (Apple state machine, reusing kerx Format1), 2 (class array), 3 (Apple’s compact index-based format, `KernSubTableFormat3` :46-125).
- **Unsupported**: the Minimum and Override bits; Backwards and Variation are mapped to 0 for the OT header.
- `get_h_kerning` (for font funcs and `hb_ot_layout`) supports **only format 0** (comment :135).
- Applied by `hb_ot_layout_kern` (`hb-ot-layout.cc:130-146`), using the AAT apply context.
- `hb_ot_layout_has_machine_kerning` / `has_cross_kerning` (`hb-ot-layout.cc:88-127`) feed the zero-marks and mark-adjust decisions (`hb-ot-shape.cc:189-208`).
- NEWS 15.1.0 fixed ignored kern/mort tables whose state machines don’t start at the first state (“non-first initial state”). I didn’t locate the exact change.
- **`hb_kern_machine_t::kern`** (`hb-kern.hh:40-140`):
  - It skips marks (`IgnoreMarks`) using the GPOS skippy iterator and honours the `kern` feature mask.
  - It **splits each kern value in two**: `kern1 = kern >> 1` is added to the first glyph’s advance, and `kern2` to the second glyph’s advance *and* x_offset. The visual spacing equals the full kern, while the split keeps cluster boundaries sensible (matching the GPOS pair-positioning split described in NEWS 4.x [corrected: in 15.1.0 GPOS doesn’t split kerning; that code is behind `HB_SPLIT_KERN`, off by default (#3408)]).
  - Cross-stream values go into y_offset (x_offset in vertical).

### 13.6 trak, ankr, feat, ltag (and tables compiled but unused)
- **trak** (`hb-aat-layout-trak-table.hh`):
  - The point size is `font->ptem`, or **12 pt** (`HB_CORETEXT_DEFAULT_FONT_SIZE`, `hb-aat-layout.hh:36`) if unset, matching CoreText’s default.
  - The value is interpolated over the size table, and between tracks for a fractional `track`, and scaled from em units (`get_tracking` :132-165).
  - `apply` (:221-246) adds the whole amount to the **first glyph of each grapheme** (`foreach_grapheme`), x or y by direction.
  - 10.0/10.3 “brought closer to Core Text”: sizes not in the table are now interpolated.
  - `get_tracking` also refuses to track without STAT.
- **ankr**: per-glyph anchor point arrays through a lookup table (`hb-aat-layout-ankr-table.hh:59-90`). Used only by kerx format 4.
- **feat**: the feature-name and selector catalogue (`hb-aat-layout-feat-table.hh`). Exclusive flag. Used for the gate in 13.3 and the public APIs `hb_aat_layout_get_feature_types`, `hb_aat_layout_feature_type_get_name_id` and `hb_aat_layout_feature_type_get_selector_infos` (`hb-aat-layout.h:726-770`).
- **ltag**: language-tag strings for morx’s Language Tag feature (`hb-aat-ltag-table.hh:63-100`). “Rudimentary language matching” (`morx` :1165).
- `bsln`, `just` and `opbd` headers exist but are only `#include`d “so we compile it; unused otherwise” (`hb-aat-layout.cc:32,34`; `hb-ot-layout.cc:55`). `opbd` is commented out of the face table list (`hb-ot-face-table-list.hh:126`). AAT justification and baselines aren’t implemented in shaping.
- **Face accelerators**: morx, mort and kerx are accelerated (per-chain lazily created accelerators with glyph sets and class caches; `mortmorx::accelerator_t` :1358-1420). ankr, trak, ltag and feat are plain tables (`hb-ot-face-table-list.hh:117-125`).

---

## 14. Things a book should flag as new or changed (from NEWS, newest first)

- **15.1.0**: Unicode 18 Devanagari/Bengali Indic fixes; Arabic fallback ligatures and marks; kerx formats 1/2/4 and kern/mort initial-state fixes.
- **14.5.0**: Unicode 18.0 data, and the Jurchen, Proto-Cuneiform and Seal scripts in the USE list.
- **14.4.0**: win1256 Arabic fallback enabled on all platforms.
- **14.3.0**: Hangul `calt` disabled only on jamo.
- **14.3.1**: AAT insertion at end of text.
- **14.2.1**: mort contextual offset fixes; Arabic PUA lam-alef-maksura.
- **12.2.0**: (a) context matching in per-syllable features confined to the syllable (backtrack and lookahead); (b) legacy `kern` only for the default, Arabic, Hangul and Hebrew shapers.
- **12.x**: AAT fast path; Uniscribe-bug-compatible mode removed.
- **11.0.1**: trak back in shaping (reverting 10.3.0).
- **10.3.0**: AALMAGHRIBI morx blocklist; trak interpolation.
- Older but still often missed: 2.8.0 (other joining scripts to USE), 2.8.2 (GPOS preferred over kerx when GSUB is present), 3.1.0 (GPOS after morx when there’s no kerx), 4.2.0 (deleted glyphs don’t block GPOS), 4.4.0 (Sinhala to USE; win1256 and PUA support), 5.0.0 (ltag language matching), 7.0.0 (AAT feature ranges).
- **HarfRust (`harfrust` backend) and the `--rust` generator modes** are new infrastructure. The `kbts` backend (kb_text_shape) is new too. Neither is part of the `ot` script shapers.

---

## 15. Suggested chapter and section breakdown for this area

**Chapter A: “Choosing how to shape: script shapers and the plan”**
1. Two meanings of “shaper”; the `ot` backend contains AAT.
2. `hb_ot_shaper_categorize`: script, direction, *and the font’s GSUB script tag* (DFLT/latn → default, `xxx3` → USE, `mymr` → default, Zawgyi).
3. The hook table and the pipeline timeline: preprocess (Unicode), normalization hooks, setup_masks, GSUB pauses (glyphs), postprocess. Include a diagram of the stages.
4. The plan-time flags: zero-width marks early/late, fallback positioning, gpos_tag, normalization modes.

**Chapter B: “Joining scripts: Arabic, Syriac, Mongolian, N’Ko and friends”**
1. Joining types and the 7-state machine; pre/post context; tatweel safety.
2. Feature order and pauses; ZWJ semantics in Arabic.
3. UTR #53 mark reordering and the ccc 22/26 trick.
4. Fallback shaping: synthesized GSUB from presentation forms; win1256 detection and the self-including table; PUA cmap mapping keyed on OS/2 v0 font pages.
5. `stch` stretching after positioning.
6. Joining through USE: the Arabic plan inside USE vs syllable-level topographical forms.

**Chapter C: “Small script shapers: Hebrew, Thai/Lao, Hangul”**
1. Hebrew presentation-form composition gated on GPOS `mark`; meteg reordering; `gpos_tag`.
2. Thai/Lao Sara Am; Thai PUA state machines (Windows and Mac PUA).
3. Hangul font-aware composition, jamo features, tone marks, the calt-on-jamo change.

**Chapter D: “Syllables: the Indic model”**
1. Unicode ISC/IPC to HarfBuzz categories and positions (`gen-indic-table.py`); one table shared by three machines.
2. Ragel: reading the `.rl` grammars; serial/type encoding; broken clusters.
3. Base finding, reph, pref, and **probing the font’s lookups with would_substitute**.
4. Initial reordering, basic features with pauses, final reordering (reph steps 1–6), `init`.
5. Old-spec vs new-spec tags; per-script configs; Kannada and Malayalam special cases.
6. Per-syllable feature application and the 12.2.0 context-confinement change.
7. Khmer (Coeng Ro, cfar, no pauses) and Myanmar (kinzi, medials, early mark zeroing); Zawgyi.

**Chapter E: “The Universal Shaping Engine”**
1. Microsoft’s USE spec vs HarfBuzz; `ms-use` override data; disabled scripts.
2. `gen-use-table.py` predicates and positional suffixes.
3. The USE grammar (including hieroglyph clusters) and the filtered iterator (CGJ, ZWNJ before marks).
4. Feature groups; recording rphf/pref results; repha and pre-base reordering.
5. Indic scripts through USE with `xxx3` tags.

**Chapter F: “When text is invalid: dotted circles and vowel constraints”**
1. The four insertion paths, and the buffer flag that turns them off.
2. Vowel-sequence spoofing data (IndicShapingInvalidCluster).

**Chapter G: “Apple Advanced Typography inside HarfBuzz”**
1. The table-selection rules (morx vs GSUB, kerx vs GPOS vs kern, trak gated by STAT), worked through as a decision diagram; what docs/ gets wrong.
2. The extended state machine: classes, reserved classes, states, entries, DontAdvance; mort vs morx (`ObsoleteTypes`/`ExtendedTypes`, negative states); the driver loop, fast path, safe-to-break analysis.
3. Chains, feature flags, `feat`, `ltag`, OpenType-to-AAT mapping and feature ranges; why user features need a `feat` table.
4. The five morx subtable types, each with a worked example (rearrangement verb table, ligature stack, deleted glyphs, insertion).
5. kerx formats 0/1/2/4/6, cross-stream as cursive chains, ankr.
6. trak and point size.
7. Deleted glyphs, GDEF on AAT fonts, the `dumber` shaper, mark-zeroing interactions.

**Chapter H (or appendix): “Legacy kern”**
1. Microsoft v0 vs Apple v1 layouts; formats 0–3; unsupported bits.
2. The split-advance kerning in `hb_kern_machine_t`; mark skipping; when kern runs alongside GPOS; which shapers allow it.

**Appendix: “Regenerating the tables”**: the generator commands and UCD/MS inputs (section 11), packTab, ragel, the `--rust` outputs.

Useful test data for worked examples: `test/shape/data/in-house/tests/*.tests` (aat-morx, aat-kerx, aat-trak, arabic-fallback-shaping, arabic-stch, hangul-calt, indic-*, khmer-*, myanmar-*, sara-am, use-indic3, kern-format1/2, tt-kern-gpos, per-script-kern-fallback) and their fonts in `test/shape/data/in-house/fonts/`. `test/subset/data/fonts/NotoSansDevanagari-Regular.ttf` shows Indic pauses well with `build/util/hb-shape --trace` (“start reordering indic initial” / “final”).
