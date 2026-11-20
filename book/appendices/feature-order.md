# Feature order

“Does my `calt` run before my `ccmp`?” has no single answer. It depends on the script shaper, and on the order of the lookups in the font. This appendix gives the order for each of HarfBuzz’s shapers, as HarfBuzz {{hb}} runs it. Each table is generated automatically by running HarfBuzz when the book is built, so it can’t drift from the code.

## The rule

Planning sorts features into **stages** ([From features to lookups](from-features-to-lookups.html#stages-and-pauses)):

* Stages run one after another, in a fixed order that the shaper sets.
* Within a stage, lookups run in LookupList order, whatever features they belong to ([GSUB](gsub.html#the-order-lookups-run-in)). The order in which the features are listed, requested, or written doesn’t count.
* GPOS always has one stage. All its lookups run in LookupList order, after all of GSUB.

So each table below lists stages, not features. Within one stage, the features are listed alphabetically, because their order there is the font’s, not HarfBuzz’s.

Between the stages, the tables show the other steps HarfBuzz’s trace reports, in italics, under the names the trace gives them:

| Step | What it is |
|---|---|
| *preprocess-text* | the shaper’s work on the characters before shaping, such as composing Hangul jamo ([Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html)) |
| *decompose*, *reorder*, *compose* | normalization’s three rounds ([Normalization](normalization.html)) |
| *reordering …* | a shaper moving glyphs between stages: the Indic, Khmer, Myanmar, and USE reorderings |
| *postprocess-glyphs* | the shaper’s work after GPOS, such as stretching for Arabic `stch` ([Joining scripts](joining-scripts.html)) |
| *fallback mark*, *fallback kern* | HarfBuzz positioning marks or kerning itself, for a font without the GPOS features ([Fallbacks](fallbacks.html)) |

Only steps that the shaped text needs appear. A step that leaves no message in the trace isn’t shown either. Finding syllables, for example, leaves no message, but it ends a stage.

## How the tables are made

`fonts/feature-order/build-fonts.py` builds a pair of fonts for each script. Each font has one lookup for every feature tag that any of HarfBuzz’s shapers asks for, 58 in all, plus `smcp` to stand for a feature an application asks for. Each lookup acts on a glyph that is never in the text, so it changes nothing. It is there to be seen: HarfBuzz’s trace reports every lookup in the plan, in the order it runs, whether or not it matches.

The two fonts differ only in how their lookups are numbered: alphabetically by feature tag in one, and in reverse in the other. Within a stage, LookupList order decides, so the two fonts give opposite orders. Across stages, the stage order decides, so they agree. A stage therefore ends exactly where the lookups run so far are the same set in both fonts. The `order` block in `tools/build-site.mjs` shapes both fonts and finds the stages that way.

A feature that is missing from a table wasn’t asked for. Under the Indic shaper, for example, `liga` is turned off, so it never runs, even though the fonts have it.

## The default shaper

The default shaper handles Latin, Greek, Cyrillic, Han, and most other scripts, and Thai and Lao use its features too ([From tags to a shaper](choosing-a-script-shaper.html#from-tags-to-a-shaper)). It adds no pauses, so after `rvrn` everything is one stage: the font’s lookup order decides everything else.

```order
fonts: order-latn
text: a
options: --features=smcp
```

In right-to-left text, as with the Hebrew shaper, `rtla` and `rtlm` take the place of `ltra` and `ltrm`:

```order
fonts: order-hebr
text: א
options: --features=smcp
```

In vertical text, `vert` replaces the horizontal features `calt`, `clig`, `curs`, `dist`, `kern`, `liga`, and `rclt`:

```order
fonts: order-latn
text: a
options: --features=smcp  --direction=ttb
```

## Arabic

The Arabic shaper is used for Arabic in horizontal text, and for Syriac in horizontal text if the font has a Syriac script tag. The other joining scripts, such as Mongolian and N’Ko, are shaped by USE ([Joining scripts](joining-scripts.html#joining-scripts-under-use)); [Choosing a script shaper](choosing-a-script-shaper.html#from-tags-to-a-shaper) has the conditions. It puts a pause after each joining feature, and after `rlig`, so `isol`, `fina`, `fin2`, `fin3`, `medi`, `med2`, `init`, and `rlig` each run on their own, in that order ([Joining scripts](joining-scripts.html#the-features-in-order)):

```order
fonts: order-arab
text: بب
options: --features=smcp
```

## Indic

The nine Indic scripts, under their `2` tags or their old ones ([The Indic model](indic-model.html#features-and-stages)). Syllables are found before the shaper’s first feature, and the glyphs are reordered twice: after `locl` and `ccmp`, and after the basic features. Each basic feature has a stage of its own, so each sees what the one before made. The presentation features then share the last stage with the common ones and the application’s.

```order
fonts: order-dev2
text: कि
options: --features=smcp
```

## Khmer

Khmer reorders first, before any of its own features. Then the basic features share one stage ([Khmer and Myanmar](khmer-and-myanmar.html)):

```order
fonts: order-khmr
text: ក
options: --features=smcp
```

## Myanmar

Under `mym2`, Myanmar reorders after `locl` and `ccmp`, and its basic features each have a stage of their own ([Khmer and Myanmar](khmer-and-myanmar.html)):

```order
fonts: order-mym2
text: က
options: --features=smcp
```

## The Universal Shaping Engine

USE covers the scripts in its list, and the nine Indic scripts under the unregistered `3` tags, such as `dev3` ([The Universal Shaping Engine](universal-shaping-engine.html#features-and-stages)). The order is the same for all of them. Balinese is the example here:

```order
fonts: order-bali
text: ᬓ
options: --features=smcp
```

Only `rphf` and `pref` have stages of their own, because what each one did is recorded before the next. The specification leaves the order within each group to the font.

## Hangul

The Hangul shaper composes or decomposes the jamo before shaping, and its `ljmo`, `vjmo`, and `tjmo` share the default shaper’s single stage ([Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html)):

```order
fonts: order-hang
text: 한
options: --features=smcp
```

## AAT fonts

A font with a `morx` table that HarfBuzz uses gets none of the GSUB stages: `morx` runs in GSUB’s place ([When morx is used](aat-inside-harfbuzz.html#when-morx-is-used)). Its order is the font’s own: chains run in the order they are stored, and the subtables in each chain likewise. Feature tags only turn subtables on and off ([From feature tags to feature types](aat-inside-harfbuzz.html#from-feature-tags-to-feature-types)).

## What it means for a font

* Under the default shaper, the order of lookups in the LookupList is the order in which they run, apart from `rvrn`. In a feature file, that is the order the lookups are written in.
* Under the default shaper, no feature is “early” or “late” except `rvrn`. `calt` runs late only if its lookups come late in the LookupList. Under the Arabic, Indic, Khmer, Myanmar, and USE shapers it really is late, in the last stage with the presentation features.
* Under a shaper with stages, a lookup can’t see the output of a feature in a later stage, wherever it is in the LookupList. A `ccmp` lookup never sees what `init` made, under the Arabic shaper or the Indic one.
* `rvrn` always runs first, in a stage of its own.
* An application’s features, such as `smcp` or `ss01`, always run in the last stage, after all reordering, so they can’t change how a syllable is reordered.
* GPOS runs after all of GSUB, so its lookups see only the final glyphs.

## Where to read the source

| What | Where |
|---|---|
| The features every shaper asks for, and in what order | `hb_ot_shape_collect_features`, `src/hb-ot-shape.cc:317` |
| Running the stages, and the trace’s lookup messages | `hb_ot_map_t::apply`, `src/hb-ot-layout.cc:2094` |
| Each shaper’s features and pauses | `collect_features_*` in `src/hb-ot-shaper-arabic.cc`, `-indic.cc`, `-khmer.cc`, `-myanmar.cc`, `-use.cc`, `-hangul.cc` |
| The fonts | `fonts/feature-order/build-fonts.py` |
| The `order` block | `blockOrder`, `tools/build-site.mjs` |

## In short

* Features run in stages: in order across stages, and in LookupList order within one.
* The default shaper has one stage after `rvrn`, so the font decides the order.
* The Arabic, Indic, Khmer, Myanmar, and USE shapers add stages, and reorder glyphs between them.
* An application’s features run last in GSUB, and GPOS runs after GSUB, in one stage.
