# Choosing a script shaper

A shape plan holds a script shaper: default, Arabic, Indic, the Universal Shaping Engine or one of the others. [Shape plans and their cache](shape-plans-and-their-cache.html) showed where it is kept. This chapter is about how it is picked, and the answer is less obvious than “by the script of the text”. HarfBuzz first turns the run’s script and language into OpenType tags, then looks for those tags in the font, and only then chooses a shaper, from the text’s script *and* the script tag it found. The same Devanagari text gets the Indic shaper in one font, the Universal Shaping Engine in another, and no script shaping at all in a third.

This chapter follows that order. What the chosen tags lead to, the features and their lookups, is the subject of the [previous chapter](from-features-to-lookups.html).

The examples use test fonts built by `fonts/choosing-a-script-shaper/build-fonts.py`. Each family is compiled from one feature file, and its fonts differ only in the script tags written into it. Every result and trace on this page was produced by running HarfBuzz {{hb}} on them when the page was built.

## From a script to script tags

HarfBuzz’s scripts are [ISO 15924 codes](https://www.unicode.org/iso15924/iso15924-codes.html) (`Deva`, `Arab`), as [Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told) said. A font’s ScriptList uses OpenType’s own **script tags**, [registered in the specification](https://learn.microsoft.com/en-us/typography/opentype/spec/scripttags), and one script can have several. `hb_ot_all_tags_from_script` (`hb-ot-tag.cc:157`) lists them, newest first:

| Script | Tags tried, in order |
|---|---|
| Bengali, Devanagari, Gujarati, Gurmukhi, Kannada, Malayalam, Oriya, Tamil, Telugu | `bng3` `bng2` `beng`, `dev3` `dev2` `deva`, and so on |
| Myanmar | `mym2` `mymr` |
| Hiragana, Katakana | `kana` |
| Lao, Yi, N’Ko, Vai | `lao `, `yi  `, `nko `, `vai ` |
| everything else | the ISO 15924 code with its first letter lowercased: `arab`, `latn`, `syrc` |

The nine Indic scripts have three generations of tag. The old tags, such as `deva`, go with the shaping model of the first OpenType Indic specifications, and the `2` tags with a later model that changed the order of glyphs some lookups see (more on that below). A `3` tag isn’t a third Indic model: as `NEWS` for 2.0.0 says, “Indic3 tags (‘dev3’, etc) are passed to USE shaper.” Myanmar has no `mym3` (`:166`). The old tags are made by lowercasing, with a switch for the exceptions (`hb_ot_old_tag_from_script`, `:37`). Text with no script of its own, such as digits alone, has the script `HB_SCRIPT_INVALID`, which gets no tags. At most three tags are kept (`HB_OT_MAX_TAGS_PER_SCRIPT`, `hb-ot-layout.h:99`).

`hb-shape --script` takes an ISO 15924 code ([The command-line tools](command-line-tools.html#direction-script-and-language)). `hb_script_from_iso15924_tag` (`hb-common.cc:445`) fixes its case, so `--script=deva` is Devanagari, but `--script=dev2` is no code at all and becomes `HB_SCRIPT_UNKNOWN`.

## From a language to language system tags

The language is turned into OpenType **language system tags**, [registered in the specification](https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags), also up to three (`HB_OT_MAX_TAGS_PER_LANGUAGE`, `hb-ot-layout.h:107`). The language comes from the application, which usually takes it from the document, such as an HTML `lang` attribute ([Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told)). It arrives as an `hb_language_t`, a BCP 47 string that `hb_language_from_string` has already lowercased, with `_` read as `-` (`hb-common.cc:167`; [Shape plans and their cache](shape-plans-and-their-cache.html) has more), so `TR`, `tr` and `tr_TR` are handled like `tr` and `tr-tr`. `hb_ot_tags_from_language` (`hb-ot-tag.cc:322`) reads it in this order:

1. Some tags of several subtags have mappings of their own, tested first by `hb_ot_tags_from_complex_language`: `zh-Hant`, `zh-HK`, `el-polyton`, and variants such as `-fonipa` (`IPPH`) and `-syre` (`SYRE`).
2. If the second subtag is a three-letter extended language subtag, as in `zh-yue`, it is used instead of the first.
3. A two-letter primary subtag is looked up in `ot_languages2`, a three-letter one in `ot_languages3` and then in a table of codes with several tags: binary searches, each with a one-entry “Poor man’s cache” (`:355`).
4. A three-letter code in `ot_languages3_blocked` gets no tag. These are ISO 639-3 codes that spell some other OpenType tag: `far` is Fataleka, not Persian (`FAR `).
5. Any other three-letter code is assumed to be ISO 639-3, upper-cased, and used as it is (`:421`). A two-letter code that isn’t in the table gets no tag.

Some languages have more than one tag, tried in order: Korean `ko` gives `KOR` then `KOH` (Old Hangul), and Armenian `hy` gives `HYE0` then `HYE`.

The tables are in `hb-ot-tag-table.hh`, made by `gen-tag-table.py` from the OpenType specification’s page of language system tags and the IANA language subtag registry. It matches the two by the ISO 639 codes the OpenType page lists for each tag, turned into two-letter codes where one exists (`gen-tag-table.py:451`), with corrections by hand, and adds each macrolanguage’s individual languages. The header records the registry’s `File-Date: 2026-09-17`.

The test font `indic-dev2.ttf` has a Marathi language system, `MAR`, whose `locl` swaps RA for another glyph, standing in for Marathi’s eyelash RA:

```shape
indic-dev2.ttf  र  --language=hi
indic-dev2.ttf  र  --language=mr
indic-dev2.ttf  र  --language=mr-IN
indic-dev2.ttf  र  --language=mar
indic-dev2.ttf  र  --language=xyz
```

`hi` gives `HIN`, which this font doesn’t have, so the default language system is used. `mr`, `mr-IN` and the ISO 639-3 code `mar` all give `MAR`. `xyz` gives the tag `XYZ `, which the font doesn’t have either.

## Naming the tags directly

An application that knows exactly which tags it wants can say so with two **private-use subtags** in the language (`parse_private_use_subtag`, `hb-ot-tag.cc:444`). After an `x-` singleton, `-hbsc` followed by a tag forces the script tag, and `-hbot` followed by a tag forces the language system tag. `hi-x-hbscdev2` is Hindi with the script tag `dev2`. `x-hbotMAR` is the language system `MAR`. A tag that can’t be spelled in letters and digits can be given in hex: `-hbsc-64657632` is `dev2` too.

A forced tag replaces the whole list, so only that tag is tried (and then the fallbacks of the next section). The case is normalized: script tags to lower case, language tags to upper case. That would turn the two default tags into each other’s spelling, so there is one exception: `-hbscdflt` gives `DFLT`, and `-hbotdflt` gives `dflt` (`:483`).

`indic-both.ttf` has both `dev2` and `deva`, with the same lookups under each:

```shape
indic-both.ttf  क्र  --language=hi
indic-both.ttf  क्र  --language=hi-x-hbscdeva
indic-both.ttf  क्र  --language=hi-x-hbsc-64657661
indic-dev2.ttf  र  --language=x-hbotMAR
```

Forced to `deva`, the same font gives a different result, for reasons that come below. The trace shows the tag chosen:

```trace
font: indic-both.ttf
text: क्र
options: --language=hi-x-hbscdeva
from: start table GSUB
to: end reordering indic initial
```

The subtags also run the other way. `hb_ot_tags_to_script_and_language` (`:653`), which turns a font’s tags back into an `hb_script_t` and an `hb_language_t`, writes them when it must: a language tag with no BCP 47 equivalent becomes `x-hbot-` and its hex, and a script tag that isn’t the script’s first choice is appended as `-x-hbsc-` and its hex. For Devanagari the first choice is `dev3`, so `dev2` with `MAR` comes back as `mr-x-hbsc-64657632`. With the default language system the language is null, and the script tag is lost: `deva` with `dflt` comes back as plain Devanagari (checked with a small C program, not part of the book’s build). A build with `HB_NO_LANGUAGE_PRIVATE_SUBTAG` ignores the subtags.

> For programmers: `hb_ot_tags_from_script_and_language` (since 2.0.0) is the public form of all this. It fills two arrays with the script and language tags the planner would try. It replaced `hb_ot_tags_from_script` and `hb_ot_tag_from_language`, now deprecated.

## Finding them in the font

The map builder’s constructor (`hb-ot-map.cc:45`) takes the tags to the font, once for GSUB and once for GPOS, with two functions.

`hb_ot_layout_table_select_script` (`hb-ot-layout.cc:564`) tries each script tag in order. If none is in the ScriptList, it tries three more:

1. `DFLT`, the default script;
2. `dflt`, which isn’t a script tag at all, but “MS site has had typos and many fonts use it now :(”;
3. `latn`, because “some old fonts put their features there even though they’re really trying to support Thai, for example :(”.

Failing those, no script is chosen, and the **chosen script** is `HB_TAG_NONE`. The function returns true only for a requested tag, and the map keeps both answers for each table: `chosen_script` and `found_script` (`hb-ot-map.hh:174`).

`hb_ot_layout_script_select_language2` (`hb-ot-layout.cc:772`) does the same within that script: each language tag in order, then a language system record tagged `dflt` if there is one, and otherwise the script’s default language system.

Both are binary searches (`RecordArrayOf::find_index`, `hb-ot-layout-common.hh:948`), so they rely on the lists being sorted by tag, as the specification requires; a tag out of order can be missed (inferred). `hb-info --list-scripts` shows what a font has:

```info
indic-both.ttf  --list-scripts
```

Only a script’s *presence* counts: a `dev2` with no features is still chosen over a `DFLT` that has them. HarfBuzz’s manual says it “falls back on the lookups under the DFLT tag … if there are actually no lookups for the tag requested” (`docs/usermanual-opentype-features.xml:289`), but the code falls back only when the tag is missing.

### GSUB and GPOS choose separately

So GSUB and GPOS can settle on different scripts: a font may keep its Devanagari substitutions under `dev2` and its kerning under `DFLT`. Each table’s features come from its own choice. Only GSUB’s picks the shaper; GPOS’s matters to Hebrew, as a later section shows.

The trace line “start table GPOS script tag” doesn’t show GPOS’s choice. It prints GSUB’s chosen script (`hb-ot-layout.cc:2149` formats `chosen_script[0]`, not `chosen_script[1]`), so in a font with no GSUB it says `''` even when GPOS found a script. The Hebrew trace below shows it.

## From tags to a shaper

With the scripts chosen, the planner picks the shaper (`hb-ot-shape.cc:84`):

```c++
hb_ot_shape_planner_t::hb_ot_shape_planner_t (hb_face_t *face,
                                              const hb_segment_properties_t &props) :
  face (face), props (props), map (face, props),
  aat_map (face, props), apply_morx (_hb_apply_morx (face, props))
{
  shaper = hb_ot_shaper_categorize (props.script, props.direction, map.chosen_script[0]);

  script_zero_marks = shaper->zero_width_marks != HB_OT_SHAPE_ZERO_WIDTH_MARKS_NONE;
  script_fallback_position = shaper->fallback_position;

  /* https://github.com/harfbuzz/harfbuzz/issues/1528 */
  if (apply_morx && shaper != &_hb_ot_shaper_default)
    shaper = &_hb_ot_shaper_dumber;
}
```

(trimmed of its `#ifndef HB_NO_AAT_SHAPE` lines). `map` is the map builder, so the tags have been searched for before the body runs.

`hb_ot_shaper_categorize` (`hb-ot-shaper.hh:177`) is one `switch` on the script. Here are its rules, read from the code:

| Script | Shaper |
|---|---|
| Arabic | Arabic, if the text is horizontal; otherwise default |
| Syriac | Arabic, if horizontal and GSUB’s chosen script isn’t `DFLT`; otherwise default |
| Thai, Lao | Thai |
| Hangul | Hangul |
| Hebrew | Hebrew |
| Khmer | Khmer |
| the nine Indic scripts | default if the chosen script is `DFLT` or `latn`; the USE if it ends in `3`; otherwise Indic |
| Myanmar | default if the chosen script is `DFLT`, `latn` or `mymr`; otherwise Myanmar |
| `Qaag` (Zawgyi) | Myanmar Zawgyi |
| a list of 91 more scripts, from Tibetan to the Unicode 18.0 additions | default if the chosen script is `DFLT` or `latn`; otherwise the USE |
| everything else, Latin, Cyrillic, Greek and Han among them | default |

The Indic case is short enough to quote (`:234`):

```c++
/* If the designer designed the font for the 'DFLT' script,
 * (or we ended up arbitrarily pick 'latn'), use the default shaper.
 * Otherwise, use the specific shaper.
 *
 * If it's indy3 tag, send to USE. */
if (gsub_script == HB_TAG ('D','F','L','T') ||
    gsub_script == HB_TAG ('l','a','t','n'))
  return &_hb_ot_shaper_default;
else if ((gsub_script & 0x000000FF) == '3')
  return &_hb_ot_shaper_use;
else
  return &_hb_ot_shaper_indic;
```

### The same text in seven fonts

The Devanagari test fonts are compiled from one feature file, `indic.fea`. Its `akhn` makes the conjunct K.SSA, and its `blwf` turns virama + RA into a below-base form, written in the order the `2` model uses, virama first:

```c++
feature akhn {
    sub ka virama ssa by k_ssa;
} akhn;

feature blwf {
    sub virama ra by rakar;
} blwf;
```

(trimmed). `indic-typo.ttf` has the misspelling `dflt`, patched in after compiling since feaLib won’t write it, and `indic-none.ttf` has no GSUB or GPOS. Here are three syllables, KA with the vowel sign I, the conjunct K.SSA, and KA with RA below it, in each font (two in the last three):

```shape
indic-dev2.ttf  कि  --language=hi
indic-dev2.ttf  क्ष  --language=hi
indic-dev2.ttf  क्र  --language=hi
indic-dev3.ttf  कि  --language=hi
indic-dev3.ttf  क्ष  --language=hi
indic-dev3.ttf  क्र  --language=hi
indic-deva.ttf  कि  --language=hi
indic-deva.ttf  क्ष  --language=hi
indic-deva.ttf  क्र  --language=hi
indic-DFLT.ttf  कि  --language=hi
indic-DFLT.ttf  क्ष  --language=hi
indic-DFLT.ttf  क्र  --language=hi
indic-latn.ttf  कि  --language=hi
indic-latn.ttf  क्र  --language=hi
indic-typo.ttf  कि  --language=hi
indic-typo.ttf  क्र  --language=hi
indic-none.ttf  कि  --language=hi
indic-none.ttf  क्र  --language=hi
```

Under `dev2` everything works: the vowel sign moves before KA, the conjunct forms, and RA goes below. Under `dev3` the result is the same here, from a different shaper; [The Universal Shaping Engine](the-universal-shaping-engine.html) shows where the two part company. Under `DFLT` and `latn` nothing works. The vowel sign stays after KA, and `akhn` and `blwf` never run, though their lookups are under the very script that was chosen: they are Indic features, which only the Indic shaper and the USE ask for. The virama is placed by fallback mark positioning, which the default shaper has and the Indic shaper doesn’t.

The traces show which shaper ran by the steps that appear. Under `dev2`, the Indic shaper’s `preprocess_text` runs, and its two reordering passes run as pauses inside GSUB:

```trace
font: indic-dev2.ttf
text: क्र
options: --language=hi
```

Under `DFLT`, there is no `preprocess-text`, no reordering and no lookups, but there is a fallback step after GSUB:

```trace
font: indic-DFLT.ttf
text: क्र
options: --language=hi
```

Under `dev3`, the USE has its own reordering step, after the basic features:

```trace
font: indic-dev3.ttf
text: क्र
options: --language=hi
from: start table GSUB
to: end table GSUB
```

### Old and new Indic tags

Under `deva`, KA with RA below comes out as KA, RA, virama. The Indic shaper ran, but in its old mode. When the plan is made, the Indic shaper records whether the font uses the old model (`data_create_indic`, `hb-ot-shaper-indic.cc:328`):

```c++
indic_plan->is_old_spec = indic_plan->config->has_old_spec &&
                          ((plan->map.chosen_script[0] & 0x000000FFu) != '2');
```

All nine Indic scripts have `has_old_spec` set. In the old mode, the shaper moves the first virama after the base to after the last consonant (`:669`), the order old fonts’ lookups expect: `ra virama`, not `virama ra`. It also merges clusters differently and sets the `blwf` mask on fewer glyphs; [The Indic model](the-indic-model.html) has the rest. This font’s `blwf` was written for the new order, so under `deva` it no longer matches:

```trace
font: indic-deva.ttf
text: क्र
options: --language=hi
from: start table GSUB
to: end table GSUB
```

The test is “doesn’t end in `2`”, not “is the old tag”. So `dflt`, which isn’t `DFLT`, gets the Indic shaper in its old mode, as the results above show. So does a font with no script for the text, or no GSUB at all: its chosen script, `HB_TAG_NONE`, is neither `DFLT` nor `latn`, and doesn’t end in `2`. `indic-none.ttf` has no lookups, but its vowel sign is still reordered, by the shaper alone. The 91 USE scripts are the same: with no GSUB they go to the USE. The comment above that case says “for some simple scripts, there may not be *any* GSUB/GPOS needed, so there may be no scripts found!”, but only `DFLT` and `latn` are tested (inferred: no test font here uses a USE script).

### Arabic and Syriac

Arabic gets its shaper whatever the font has, if the text is horizontal, because “we do fallback shaping for Arabic script (and not others)”: from the presentation forms in the `cmap`, as [Joining scripts](joining-scripts.html) describes. Syriac gets the Arabic shaper only if GSUB’s chosen script isn’t `DFLT`. The test fonts `join-*.ttf` have `init`, `medi` and `fina` for Arabic BEH and Syriac BETH under `arab` and `syrc`, under `DFLT` only, or under `latn` only:

```shape
join-arab.ttf  ببب  --language=ar
join-arab.ttf  ܒܒܒ  --language=syr
join-DFLT.ttf  ببب  --language=ar
join-DFLT.ttf  ܒܒܒ  --language=syr
join-latn.ttf  ببب  --language=ar
join-latn.ttf  ܒܒܒ  --language=syr
join-DFLT.ttf  ببب  --language=ar  --direction=ttb
```

The Arabic joins in all three fonts. The Syriac joins under `syrc`, doesn’t under `DFLT`, and does again under `latn`. The Indic and USE cases treat a `latn` fallback like `DFLT`, but the Syriac case tests only `DFLT`, so here `latn` gets the Arabic shaper, which finds the joining features under `latn` and applies them. So do `dflt` and a font with no GSUB. Vertical text gets the default shaper, and the behs don’t join.

### Myanmar and Zawgyi

Myanmar treats its old tag differently. `mymr` is the “tag used from before Myanmar shaping spec was developed. The shaping spec uses ‘mym2’ tag”, says the comment, and a font with only `mymr` gets the default shaper. There is no old mode. (`NEWS` for 0.9.34 lists “Add old-spec Myanmar shaper”; {{hb}} has none.) In the test fonts, a `pres` ligature expects medial RA (U+103C) moved before its consonant:

```shape
myanmar-mym2.ttf  ကြ  --language=my
myanmar-mymr.ttf  ကြ  --language=my
```

`Qaag` is not a Unicode script. It is a code from ISO 15924’s private-use range that HarfBuzz uses for **Zawgyi**, a font encoding for Burmese that uses the Myanmar block’s code points in its own way (`hb-ot-shaper.hh:267`, and HarfBuzz issue #1162, though the source itself calls it only “Ugly Zawgyi encoding”). No character has that script, so an application must set it. The `myanmar_zawgyi` shaper has every hook null, uses the lightest normalization, and zeroes no marks: “Disable all auto processing” (`hb-ot-shaper-myanmar.cc:367`). `HB_NO_OT_SHAPER_MYANMAR_ZAWGYI` leaves it out, and `Qaag` then gets the default shaper.

### Hebrew and its GPOS tag

Hebrew always gets the Hebrew shaper, which asks something of GPOS. A shaper’s `gpos_tag`, if set, must be the script GPOS chose, or GPOS isn’t applied and positioning falls back to HarfBuzz’s own (`hb-ot-shape.cc:135`). Only Hebrew sets it, to `hebr`, citing issue #347. The Hebrew test fonts have no GSUB and one `mark` lookup, putting the hiriq at the alef’s right-hand edge, under `hebr` or `DFLT`:

```shape
hebrew-hebr.ttf  אִ  --language=he
hebrew-DFLT.ttf  אִ  --language=he
```

Under `DFLT` the anchor is ignored, and fallback mark positioning centers the hiriq. Under `hebr` GPOS runs, though its trace line names GSUB’s chosen script, which here is none:

```trace
font: hebrew-hebr.ttf
text: אִ
options: --language=he
from: start table GPOS
to: end table GPOS
```

### Thai and Lao

Thai and Lao always get the Thai shaper, but if GSUB didn’t find `thai` itself (`found_script[0]` false, so `DFLT` and `latn` don’t count), Thai is shaped with the private-use glyphs of old Thai fonts’ `cmap`s (`hb-ot-shaper-thai.cc:368`), as [Hebrew, Thai, Lao and Hangul](hebrew-thai-lao-and-hangul.html) explains. `HB_NO_OT_SHAPER_THAI_FALLBACK` leaves that out.

### AAT fonts

The planner’s last step swaps any shaper but the default one for `dumber` when the font will be shaped with `morx`: when it has `morx` (or `mort`) and the text is horizontal or there is no GSUB (`_hb_apply_morx`, `hb-ot-shape.cc:60`). `dumber` is the default shaper without mark zeroing and fallback positioning (`hb-ot-shaper-default.cc:55`), “Dumbest shaper ever, basically.” An AAT font reorders in its own state machines, and HarfBuzz mustn’t do it again (issue #1528). This Tamil font from HarfBuzz’s tests has `morx` and GPOS but no GSUB:

```trace
font: hb:test/shape/data/in-house/fonts/e6185e88b04432fbf373594d5971686bb7dd698d.ttf
text: கொ
options: --language=ta
from: start table morx
to: end table morx
```

Tamil with no GSUB would get the Indic shaper. Here it gets `dumber`, and the whole trace has no Indic step: the font’s own chain subtables split the vowel sign O and move its first part before KA. The original shaper’s settings are kept before the swap (`script_fallback_position`, `script_zero_marks`), and later decisions, such as whether legacy `kern` may apply, use them. [AAT inside HarfBuzz](aat-inside-harfbuzz.html) covers the rest.

## What the choice decides

A script shaper is an `hb_ot_shaper_t` (`hb-ot-shaper.hh:67`): a table of hooks, any of which may be null, and four settings. The choice of shaper is the choice of these:

| Member | What it does | When it runs |
|---|---|---|
| `collect_features`, `override_features` | add the script’s features and the pauses between them, and change the common ones | while the plan is made |
| `data_create`, `data_destroy` | make and free the shaper’s plan data | at the end of planning, and when the plan is destroyed |
| `preprocess_text` | change the characters before normalization | each run |
| `decompose`, `compose`, `reorder_marks` | change how normalization treats the script | each run, during normalization |
| `setup_masks` | set each character’s feature masks, or record categories for later | each run, before the glyphs are looked up |
| `postprocess_glyphs` | change the glyphs after positioning | each run, at the end |
| `gpos_tag` | the script GPOS must have chosen to be used | at planning |
| `normalization_preference` | how far normalization should compose | at planning |
| `zero_width_marks` | whether, and when, marks lose their advance | at planning |
| `fallback_position` | whether fallback mark positioning, and legacy `kern`, may be used | at planning |

Much of a shaper’s work is in the pauses that `collect_features` adds between GSUB stages, such as the Indic reordering passes ([From features to lookups](from-features-to-lookups.html)). [The pipeline, step by step](the-pipeline-step-by-step.html) shows where each hook runs. The default shaper’s hooks are all null.

## What it means

### For applications

The script HarfBuzz is told decides most of this. `hb_buffer_guess_segment_properties` takes it from the first character with a real script, which is right for a run already split by script and wrong for one that mixes them.

The language should be set too, or the locale’s is used. It is given as BCP 47, so an application needn’t know OpenType’s tags, though each distinct BCP 47 tag is a separate plan ([Shape plans and their cache](shape-plans-and-their-cache.html#segment-properties)).

To shape with tags HarfBuzz wouldn’t choose, the `-x-hbsc` and `-x-hbot` subtags are the only way through `hb_shape`. To ask what a font supports before choosing it for a run, `hb_ot_tags_from_script_and_language` gives the tags HarfBuzz will try, and the return value of `hb_ot_layout_table_select_script` says whether the font has one of them or only a fallback.

> For programmers: nothing in the public API reports which script shaper a plan chose. A trace shows it indirectly: “reordering indic initial”, “reordering USE”, “reordering myanmar”, “preprocess-text” and “postprocess-glyphs” come from shapers’ hooks.

### For type designers

The script tag in a font is not a label. It decides which shaper runs, and so which features are applied at all.

* A font for an Indic or USE script needs its lookups under that script’s own tag. Under `DFLT` or `latn` alone, the shaper is the default one, and features such as `akhn`, `blwf`, `half` and `pref` are never applied, however they are registered.
* For the nine Indic scripts, the `2` tag and the old tag mean different glyph orders in some lookups. A font with both is shaped with the `2` tag. A font with only the old tag gets the old mode, and so does a font whose only tag is the misspelling `dflt`.
* A `3` tag, such as `dev3`, sends the text to the Universal Shaping Engine, which has its own feature order and categories, and HarfBuzz looks for it before the `2` tag.
* A Myanmar font needs `mym2`: `mymr` gets the default shaper.
* A Hebrew font needs `hebr` in GPOS, not just `DFLT`, or its GPOS is ignored.
* A Syriac font under `DFLT` alone gets no joining. Under `latn` it does.
* GSUB and GPOS are searched separately, and only GSUB’s answer picks the shaper. A font with no GSUB still gets the script’s shaper (for the Indic scripts, in its old mode).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-tag.cc` | script to tags (`hb_ot_all_tags_from_script`, the new and old tags), language to tags, the private-use subtags, and the reverse mappings |
| `src/hb-ot-tag-table.hh` | the generated language tables and `hb_ot_tags_from_complex_language` |
| `src/gen-tag-table.py` | the generator, which reads the OpenType language tag page and the IANA subtag registry |
| `src/hb-ot-layout.cc` | `hb_ot_layout_table_select_script` and `hb_ot_layout_script_select_language2`, with the `DFLT`, `dflt` and `latn` fallbacks |
| `src/hb-ot-map.cc` | the map builder’s constructor, which searches GSUB and GPOS for the tags |
| `src/hb-ot-shaper.hh` | `hb_ot_shaper_t`, the list of shapers, and `hb_ot_shaper_categorize` |
| `src/hb-ot-shape.cc` | the planner’s constructor, `_hb_apply_morx` and the swap to `dumber`, and the `gpos_tag` test |
| `src/hb-ot-shaper-default.cc` | the default and `dumber` shapers |
| `src/hb-ot-shaper-indic.cc` | `is_old_spec`, and what it changes |

## In short

* A run’s script becomes up to three OpenType script tags, newest first (`dev3`, `dev2`, `deva`), and its BCP 47 language becomes up to three language system tags, from tables generated from the OpenType and IANA registries.
* `-x-hbsc` and `-x-hbot` private-use subtags force the tags.
* Each of GSUB and GPOS chooses a script: the first tag the font has, else `DFLT`, `dflt` or `latn`, else none. Then a language system: the first tag found, else the default.
* The shaper is chosen from the text’s script and the script GSUB chose. For Indic, Myanmar and USE scripts, `DFLT` and `latn` mean the default shaper; for Indic, a `3` tag means the USE, and any tag not ending in `2` means the old mode.
* Arabic always gets its shaper in horizontal text; Syriac unless GSUB chose `DFLT`. Hebrew uses GPOS only under `hebr`. Fonts shaped with `morx` get `dumber`.
* The choice decides which features are applied, how the text is normalized and reordered, and how marks are positioned.
