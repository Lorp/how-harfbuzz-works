# From features to lookups

A font’s GSUB and GPOS tables say which lookups each feature uses. An application says which features it wants. Between the two sits the **map**, `hb_ot_map_t`, the part of a [shape plan](shape-plans-and-their-cache.html) that turns a list of feature tags into the lookups that will actually run, in order, each with the mask bits that say which glyphs it may touch and the few flags it runs with.

This chapter follows the map being built. The planner adds features, the shaper for the script adds more, the application’s come last, and then `compile` merges them, finds them in the font, hands out mask bits, and collects the lookups stage by stage. Several things happen quietly along the way: a feature can be dropped because the mask has run out of bits, a feature turned on in one place can switch off others, and a variable font can swap a feature’s lookups for different ones. Which script and language system the map reads is decided first, and is the subject of the [next chapter](choosing-a-script-shaper.html); so is the choice of script shaper. Here they are taken as given.

The examples use five small test fonts, built by `fonts/from-features-to-lookups/build-fonts.py`: `bits.ttf`, with 27 features of one substitution each; `stages.ttf` and `arabic.ttf`, whose lookups are numbered to show stages; and `varliga.ttf` and `varliga-minor1.ttf`, made from the variable font of [Design space](design-space.html). Every result and trace on this page was produced by running HarfBuzz {{hb}} when the page was built.

## Two structs

The work is split between a builder and what it builds (`hb-ot-map.hh`). The **map builder**, `hb_ot_map_builder_t`, lives only while a plan is made. Its constructor chooses the script and language system in GSUB and in GPOS (`hb-ot-map.cc:45`), then it collects feature requests, and its `compile` (`:208`) writes the map. The builder is then thrown away.

The map is what the plan keeps (`hb-ot-map.hh:42`):

| Field | What it holds |
|---|---|
| `chosen_script[2]`, `found_script[2]` | the script tags chosen in GSUB and GPOS, and whether the font had them |
| `global_mask` | the mask every glyph starts with |
| `features` | one `feature_map_t` per feature that survived: its tag, its feature index in each table, its stage in each, its mask and shift, and four flags |
| `lookups[2]` | the GSUB and GPOS lookups, as `lookup_map_t`: index, mask, flags, and the tag of the feature that brought it |
| `stages[2]` | for each stage, where its lookups end in `lookups`, and its pause function |

`features` is sorted by tag, so that `get_mask`, `get_1_mask` and the other queries can find a tag by binary search (`hb-ot-map.hh:121`). The pipeline uses those queries for features it treats specially, such as `frac` and `kern`, as [Shape plans and their cache](shape-plans-and-their-cache.html#the-ot-part) lists.

## Which features are asked for

`hb_ot_shape_collect_features` (`hb-ot-shape.cc:321`) makes the requests, always in this order:

| # | Features | How they are added |
|---|---|---|
| 1 | `rvrn` | on, then a GSUB pause, so it has a stage to itself |
| 2 | `ltra`, `ltrm` (left to right); `rtla`, and `rtlm` with its own bit (right to left) | on |
| 3 | `frac`, `numr`, `dnom` | with their own bits, set later around U+2044 FRACTION SLASH |
| 4 | `rand` | on, with value 255 and the random flag |
| 5 | `Harf`, `HARF` | on |
| 6 | the script shaper’s features | its `collect_features`, which may add pauses |
| 7 | `Buzz`, `BUZZ` | on |
| 8 | `abvm`, `blwm`, `ccmp`, `locl`, `mark`, `mkmk`, `rlig` | on; `mark` and `mkmk` with manual joiners |
| 9 | `calt`, `clig`, `curs`, `dist`, `kern`, `liga`, `rclt` (horizontal) or `vert` (vertical) | on; `kern` with fallback; `vert` with global search |
| 10 | the application’s features | on, or with their own bits if they have a range |
| 11 | the script shaper’s overrides | its `override_features` |

Each request is one call to `add_feature` (`hb-ot-map.cc:97`), which records the tag, the value, the flags and the current stage of each table. `enable_feature` is `add_feature` with the global flag, and `disable_feature` is the same with value 0. Nothing is looked up in the font yet.

Order decides two things: which stage a feature lands in, and which request wins when a tag is asked for twice.

### The flags

The flags are those of `hb_ot_map_feature_flags_t` (`hb-ot-map.hh:186`):

| Flag | Meaning |
|---|---|
| `F_GLOBAL` | on for the whole run; with value 1 it shares the global bit |
| `F_HAS_FALLBACK` | keep the feature even if the font lacks it, because HarfBuzz has a fallback for it (`kern`, and the Arabic joining features and `rlig`) |
| `F_MANUAL_ZWNJ`, `F_MANUAL_ZWJ` | don’t pass over ZWNJ in context, or ZWJ in input ([Joiners](gsub.html#joiners)) |
| `F_GLOBAL_SEARCH` | if the language system lacks the feature, take the first one with that tag anywhere in the font (only `vert`, `hb-ot-shape.cc:387`) |
| `F_RANDOM` | Alternate substitution picks at random (only `rand`; see [The mask](gsub.html#the-mask)) |
| `F_PER_SYLLABLE` | lookups may not match across a syllable boundary (the syllable-based shapers) |

Every feature the planner adds is global except `rtlm`, `frac`, `numr` and `dnom`, the script shapers’ features that are only on for some glyphs (Arabic’s `init`, Indic’s `half` and the like), and application features with a range. Those need bits of their own, because they are on in some places and off in others.

### Harf and Buzz

`Harf`, `HARF`, `Buzz` and `BUZZ` are private tags, not registered features. The only comments on them are “Considered required” for the first of each pair and “Considered discretionary” for the second (`hb-ot-shape.cc:359`, `:368`), and nothing in the map treats the two kinds differently: all four are simply turned on. What makes them useful is where they are added. `Harf` comes before the script shaper’s features and `Buzz` after them, so a font can put lookups in either place: `Harf`’s run before the shaper’s first pause, and `Buzz`’s after its last, whatever their position in the LookupList. Neither `NEWS` nor the manual mentions them, and the subsetter keeps them as features to retain (`hb-subset-input.cc:134`). The comments’ “required” and “discretionary” are the font’s business: one plausible use is a font that wants the lowercase tag kept on while the uppercase one is offered to users (inferred). `arabic.ttf` shows them at work in [Stages and pauses](#stages-and-pauses).

## When a tag is asked for twice

The same tag is often added more than once: `ccmp` by the Indic shaper and again in the common list, `liga` by the default list and then by the application. `compile` sorts the requests by tag, keeping the order they were made in among requests for the same tag, and merges each run of equal tags into the first (`hb-ot-map.cc:238`):

```c++
if (f[i].flags & F_GLOBAL) {
  f[j].flags |= F_GLOBAL;
  f[j].max_value = f[i].max_value;
  f[j].default_value = f[i].default_value;
} else {
  if (f[j].flags & F_GLOBAL)
    f[j].flags ^= F_GLOBAL;
  f[j].max_value = hb_max (f[j].max_value, f[i].max_value);
  /* Inherit default_value from j */
}
f[j].flags |= (f[i].flags & F_HAS_FALLBACK);
f[j].stage[0] = hb_min (f[j].stage[0], f[i].stage[0]);
f[j].stage[1] = hb_min (f[j].stage[1], f[i].stage[1]);
```

So:

* A later global request replaces the value. That is how `-liga` turns off the default `liga`: its value 0 is the last word.
* A later request with a range makes the feature non-global, keeps the larger value (it decides how many bits are needed), and keeps the earlier default, so a feature on by default stays on outside the range.
* The feature goes in the earliest stage any request named.
* Apart from the global and fallback flags, the flags are those of the first request. Indic’s per-syllable `ccmp` stays per-syllable when the common list asks for `ccmp` again.

Two consequences follow from the order of the table above. The script shaper’s overrides come after the application’s features, so they have the last word: the Indic and Khmer shapers disable `liga` there (`hb-ot-shaper-indic.cc:274`, `hb-ot-shaper-khmer.cc:143`), and an application can’t turn it back on for those scripts. And the Hangul shaper adds a second, non-global `calt` there, which by the rules above stays on by default but now has a bit of its own, so that its `setup_masks` can clear that bit on jamo only (`hb-ot-shaper-hangul.cc:67`).

When no script shaper adds features and the application asks for none, nothing can be duplicated, and the sort is skipped (`is_simple`, `hb-ot-shape.cc:327`). The features are then given bits in the order they were added rather than by tag, which matters only if bits run out.

### A range followed by a global request

One sequence goes wrong. If an application turns `liga` off over a range and then asks for `liga` globally, the merge ends with a global feature of value 1, which shares the global bit. But the ranged request is still in the list of features passed to the run, and when the plan runs, `hb_ot_shape_setup_masks` applies it with whatever mask `liga` has (`hb-ot-shape.cc:760`). The mask is now the global bit, so the range clears the global bit, and with it every feature that shares that bit, on those clusters. Here `calt` turns `e` into `e.init` after a space or an `e.init`, and the range is cluster 2, the second `e`:

```shape
gsub/ligatures.ttf   \u0020eeefi  --language=en
gsub/ligatures.ttf   \u0020eeefi  --language=en  --features=-liga[2:3]
gsub/ligatures.ttf   \u0020eeefi  --language=en  --features=-liga[2:3],liga
gsub/ligatures.ttf   \u0020eeefi  --language=en  --features=liga,-liga[2:3]
```

In the third run, `calt` stops at cluster 2 although nobody asked for that, and since its rule looks back at its own output, cluster 3 is left plain too. The other order, in the fourth run, does what was meant. This looks like a bug: the merge treats the global request as overriding the range, but `setup_masks` doesn’t know that it did.

> Since {{hb}}: fixed on HarfBuzz main by [`5d9dfde`](https://github.com/harfbuzz/harfbuzz/commit/5d9dfde259979dd91439903d09e708d16a41bbf7) (17 November 2026), so on main the later global request supersedes the range, and the third run has `e.init` for all three `e`s.

## Finding the features in the font

With duplicates merged, `compile` reads the chosen language system’s features into a map from tag to feature index, once per table (`hb_ot_layout_collect_features_map`, `hb-ot-layout.cc:1316`). If a language system lists two features with the same tag, the earlier one wins: the code loops backwards “such that earlier entries win”, because a font, `arialuni_t.ttf`, was found that only works that way (`:1328`).

A feature can be found in GSUB, in GPOS or in both, and keeps its index in each. One that is in neither is dropped, unless it has `F_HAS_FALLBACK`, in which case it is kept, marked `needs_fallback`, so that HarfBuzz’s fallback can use its mask bits ([Fallbacks](fallbacks.html)). Only `vert` looks further, through `F_GLOBAL_SEARCH`, taking the first `vert` in the FeatureList even if the language system doesn’t list it (`hb-ot-map.cc:311`). The comment where it is added explains: “We really want to find a ‘vert’ feature if there’s any in the font, no matter which script/langsys it is listed (or not) under.”

### The required feature

A language system can name a **required feature**, by index, in its `requiredFeatureIndex` field. `compile` asks for it in each table (`hb-ot-map.cc:229`) and adds its lookups directly, with the global bit and no flags (`:365`), whatever tag it has and whatever the application asked for. It goes in stage 0, unless its tag is one the planner asked for, in which case it goes in that feature’s stage (`:299`).

In `stages.ttf`, the `latn` language system has a required feature tagged `xreq` that turns `e` into `e.req`. Turning it off does nothing:

```shape
stages.ttf  ade  --language=en
stages.ttf  ade  --language=en  --features=-xreq
```

In a trace its lookup carries a blank feature tag, since the map adds it by index rather than through a feature (it is lookup 3 below). If its tag is one the planner asked for, and that request was turned off or ran out of bits, the code never records that tag’s stage, so the required feature falls back to stage 0 (read from the code, `:292`–`:300`).

## Mask bits

Each glyph’s mask has 32 bits. Bits 0–2 are the public glyph flags, and bit 31 is the **global bit**, shared by every global feature with value 1 ([Buffers](buffers.html#the-mask)). The rest are handed out here (`hb-ot-map.cc:274`, trimmed):

```c++
unsigned int global_bit_shift = 8 * sizeof (hb_mask_t) - 1;   /* 31 */
unsigned int next_bit = hb_popcount (HB_GLYPH_FLAG_DEFINED) + 1;   /* 4 */

for (unsigned int i = 0; i < count; i++)
{
  const feature_info_t *info = &feature_infos[i];
  unsigned int bits_needed;

  if ((info->flags & F_GLOBAL) && info->max_value == 1)
    /* Uses the global bit */
    bits_needed = 0;
  else
    /* Limit bits per feature. */
    bits_needed = hb_min (HB_OT_MAP_MAX_BITS, hb_bit_storage (info->max_value));

  if (!info->max_value || next_bit + bits_needed >= global_bit_shift)
    continue; /* Feature disabled, or not enough bits. */

  /* ... find the feature in GSUB and GPOS; skip it if it isn't there ... */

  map->shift = next_bit;
  map->mask = (1u << (next_bit + bits_needed)) - (1u << next_bit);
  next_bit += bits_needed;
  m.global_mask |= (info->default_value << map->shift) & map->mask;
}
```

A global feature with value 1 needs no bits of its own. Any other feature gets as many bits as its largest value needs, at most eight (`HB_OT_MAP_MAX_BITS`, so values above 255 lose their high bits). A global feature with a larger value, such as `salt=2` everywhere, or `rand` with 255, gets its own bits, and its value is written into `global_mask`, which every glyph starts with. So does the default of a feature with a range that is on outside it.

The test for running out comes before the font is consulted, but the bits are only taken once the feature has been found, so features the font doesn’t have use none.

### Running out

When the bits run out, the feature is skipped with `continue`. There is no message, not even in a trace: the feature simply has no lookups and no mask, and a later `get_mask` for it returns 0.

The comparison is `>=`, so a feature fits only if its last bit is below bit 30. Bit 30 is never handed out, and the bits available are 4 to 29: 26 of them, not the 27 that lie between the glyph flags and the global bit. That looks like an off-by-one, harmless except that it costs one feature.

Because the features are sorted by tag before bits are given out, it is the features with the latest tags that are lost, not the last ones asked for. `bits.ttf` has 27 features, each changing one character: `cv01`–`cv06` for *a*–*f*, `ss01`–`ss20` for *g*–*z*, and `zero` for the digit 0. The text starts with a space, so that a range from cluster 1 to the end covers every letter. Asked for over that range, each feature needs one bit:

```shape
bits.ttf   \u0020abcdefghijklmnopqrstuvwxyz0  --language=en  --no-positions  --no-clusters  --features=zero[1:],cv01[1:],cv02[1:],cv03[1:],cv04[1:],cv05[1:],cv06[1:],ss01[1:],ss02[1:],ss03[1:],ss04[1:],ss05[1:],ss06[1:],ss07[1:],ss08[1:],ss09[1:],ss10[1:],ss11[1:],ss12[1:],ss13[1:],ss14[1:],ss15[1:],ss16[1:],ss17[1:],ss18[1:],ss19[1:],ss20[1:]
bits.ttf   \u0020abcdefghijklmnopqrstuvwxyz0  --language=en  --no-positions  --no-clusters  --features=zero,cv01,cv02,cv03,cv04,cv05,cv06,ss01,ss02,ss03,ss04,ss05,ss06,ss07,ss08,ss09,ss10,ss11,ss12,ss13,ss14,ss15,ss16,ss17,ss18,ss19,ss20
bits.ttf   \u0020abcdefghijklmnopqrstuvwxyz0  --language=en  --no-positions  --no-clusters  --features=cv01[1:],cv02[1:],cv03[1:],cv04[1:],cv05[1:],cv06[1:],ss01[1:],ss02[1:],ss03[1:],ss04[1:],ss05[1:],ss06[1:],ss07[1:],ss08[1:],ss09[1:],ss10[1:],ss11[1:],ss12[1:],ss13[1:],ss14[1:],ss15[1:],ss16[1:],ss17[1:],ss18[1:],ss19[1:],ss20[1:]=2,zero[1:]
```

In the first run, 26 features fit and `zero` is lost, although it was asked for first. In the second, the same features asked for everywhere share the global bit and all apply. In the third, `ss20` with value 2 needs two bits when only bit 29 is left, so it is lost, and `zero`, which needs one, fits after it.

> Since {{hb}}: fixed on HarfBuzz main by [`ec94764`](https://github.com/harfbuzz/harfbuzz/commit/ec9476415057f3437019eed9b773984438d1d802) (17 November 2026), so main hands out bit 30 too: 27 one-bit features fit, and in the first run `zero` applies.

The planner itself uses few bits (`frac`, `numr`, `dnom`, `rtlm`, eight for `rand`, a few for a script shaper). It is applications that run out, such as an editor that applies stylistic sets and character variants to spans of text.

> For programmers: features with ranges and features with values other than 0 and 1 cost mask bits; global features with value 1 don’t. If an application may ask for more than a couple of dozen ranged features in one run, it should check the result, because HarfBuzz won’t say that it dropped any. Splitting the run so that each part has fewer distinct ranged features avoids the limit.

## Stages and pauses

A **pause** ends a stage. `add_gsub_pause` and `add_gpos_pause` push a stage boundary, optionally with a **pause function**, and move the builder on to the next stage (`hb-ot-map.cc:198`); every feature added after it is in the new stage. `compile` adds one last pause to each table (`:353`). When the map runs, the pause function is called after the stage’s lookups, and if it returns true, because it may have added glyphs, the buffer’s digest is refreshed (`hb-ot-layout.cc:2122`). [GSUB: substituting glyphs](gsub.html#the-order-lookups-run-in) explains why stages matter: within one, lookups run in LookupList order, whatever their features; across them, the stage order wins.

The default shaper adds no pauses, so after `rvrn` every feature is in one stage. The others use pauses for two reasons. Some need to do work between features: the Indic shaper finds syllables before any lookup and reorders after the basic forms (`hb-ot-shaper-indic.cc:249`–`:265`), and USE, Khmer and Myanmar do the same. Others need features applied one at a time: the Arabic shaper puts a pause after each joining feature (`hb-ot-shaper-arabic.cc:219`), following what Uniscribe was found to do. The script chapters describe each.

No shaper adds a GPOS pause in {{hb}}: GPOS always has one stage.

### rvrn’s own stage

`rvrn` is turned on first, and a GSUB pause follows it at once (`hb-ot-shape.cc:329`). Its lookups therefore form stage 0, which runs before any other feature’s lookups, wherever they are in the LookupList. That is what the feature registry asks for: `rvrn` “should be processed early in GSUB processing, before application of the localized forms feature or features related to shaping of complex scripts or discretionary typographic effects” (OpenType 1.9.1, `features_pt`). A font could otherwise put an `rvrn` lookup late in the LookupList and see it run after `locl` or `ccmp`.

In `stages.ttf`, `ccmp` turns *b* into *c* and is lookup 0, `rvrn` turns *a* into *b* and is lookup 1, and `calt` turns *d* into *b* and is lookup 2:

```trace
font: stages.ttf
text: ade
options: --language=en
from: start table GSUB
to: end table GSUB
```

`rvrn` runs first, though its lookup is numbered after `ccmp`’s, and the required feature, with an unknown tag, runs in the same stage. Then `ccmp` turns the *b* made from *a* into *c*. The *b* made from *d* by `calt` comes too late for `ccmp`, which is in the same stage and earlier in the LookupList.

The registry also says `rvrn` should be on by default and “not directly exposed to user control”. HarfBuzz doesn’t enforce that: `-rvrn` is an ordinary global request with value 0, and it wins.

```shape
stages.ttf  ade  --language=en  --features=-rvrn
```

Nor does it enforce the registry’s rule that only single substitutions are processed for `rvrn`: nothing in the map looks at lookup types (read from the code).

### Harf and Buzz, seen through the Arabic shaper’s stages

`arabic.ttf` has four lookups: lookup 0 for `Buzz` turns `beh.init` into `beh.buzz`, 1 for `init`, 2 for `fina`, and lookup 3 for `Harf` turns *teh* into *beh*. In one stage they would run in that order and `Buzz` would find nothing to do. Under the Arabic shaper:

```trace
font: arabic.ttf
text: تب
options: --language=ar
from: start table GSUB
to: end table GSUB
```

They run in exactly the opposite order. `Harf` is in the stage before the shaper’s first pause. `fina` comes before `init` because the shaper adds the joining features in the order `isol`, `fina`, `fin2`, `fin3`, `medi`, `med2`, `init`, with a pause after each. And `Buzz`, added after the shaper’s features, is in the stage after its last pause, later than all the joining features. (It shares that stage with the features the shaper adds after its last pause, such as `liga` and `mset`, and with the common ones.)

> For type designers: under a shaper with stages, which stage a lookup runs in is set by its feature, not by its place in the LookupList. A lookup that must run before the shaper reorders or joins can go in `Harf`; one that must see the shaper’s results can go in `Buzz`. Both are HarfBuzz’s own, so other engines won’t run them, and under the default shaper they are in the same stage as everything else.

## Collecting the lookups

Once features have bits, `compile` goes through the stages of each table and, for each, adds the lookups of the required feature if it belongs there and of every feature in that stage (`hb-ot-map.cc:356`). `add_lookups` (`:128`) pushes one `lookup_map_t` per lookup, carrying the feature’s mask and its flags: `auto_zwnj` and `auto_zwj` (the opposite of the manual flags), `random`, and `per_syllable`. A lookup index beyond the end of the LookupList is skipped.

Where the lookup indices come from depends on the variation state the plan was made for, which is in its key ([The variation state](shape-plans-and-their-cache.html#the-variation-state)).

### FeatureVariations

With no FeatureVariations record in force, a feature’s lookups are those of its feature table. With one in force, `hb_ot_layout_feature_with_variations_get_lookups` asks for the feature table through `get_feature_variation` (`hb-ot-layout-gsubgpos.hh:6559`), which looks in that record’s **feature table substitution** for the feature’s index. If the record substitutes the feature, its alternate table is used instead: the whole table, so the default lookups are replaced, not added to. A record only applies at all when GSUB or GPOS is version 1.1 or later.

Any feature can vary, not only `rvrn`. In `varliga.ttf`, `liga` turns *I* into *H*, and from user weight 700 a record replaces `liga`’s table with one whose only lookup turns *I* into *V*:

```shape
varliga.ttf  I  --language=en  --variations=wght=400
varliga.ttf  I  --language=en  --variations=wght=650
varliga.ttf  I  --language=en  --variations=wght=700
varliga.ttf  I  --language=en  --variations=wght=800  --features=-liga
```

```draw
font: varliga.ttf
text: I
slider: wght 100 900 25
start: 700
print: 400 650 700 900
```

The varied lookups belong to `liga`: they run in its stage, with its mask, and `-liga` turns them off with the rest of it. Only `rvrn` gets the stage of its own, so a substitution that should happen before everything else belongs in `rvrn`.

(fontTools’ `addFeatureVariations` makes an alternate table of the default lookups plus the new ones; the build script keeps only the new one.)

### Lookup variations

FeatureVariations 1.1 adds lookup variations, which [Shape plans and their cache](shape-plans-and-their-cache.html#lookup-variations) introduced. `add_lookups` asks the key for them first (`hb-ot-map.cc:146`). If a `LookupVariationRecord` names this feature, its lookups are the union of the groups whose conditions are true, plus the default lookups of the feature table chosen above if the record’s flag says so, and the ordinary path isn’t taken. The result is a set, so the lookups come out in index order whatever order the groups list them in. The first record for a feature is the only one consulted (`hb-ot-layout-common.hh:6020`).

> For type designers: HarfBuzz reads a FeatureVariations table with minorVersion 1 or more as having an array of `LookupVariationRecord`s straight after its records (`hb-ot-layout-common.hh:5957`), and the sanitizer requires that array to be valid (`:6188`). The ISO/IEC 14496-22 working draft (WD9) gives minorVersion 1 a different meaning, “Condition Table Format 2 can also be used”, with nothing after the records, and OpenType 1.9.1 says minorVersion is 0. In a font written to the draft, whatever follows the records is read as a count, and if that makes the array run past the table, the FeatureVariations table fails, which fails the whole GSUB, and since 12.3.0 a failed table is dropped ([Pass or fail](trust-nothing-the-sanitizer.html#pass-or-fail)). `varliga-minor1.ttf` is `varliga.ttf` with only the minor version changed to 1; the bytes after its record are a ConditionSet, read as a count of 65,536:

```shape
varliga-minor1.ttf  I  --language=en  --variations=wght=400
varliga-minor1.ttf  I  --language=en  --variations=wght=800
```

> Even `liga`’s default substitution is gone. Until the two definitions are reconciled, a FeatureVariations table that doesn’t use lookup variations is safest at minorVersion 0.

### Sorting, and lookups shared by features

At the end of each stage, the stage’s lookups are sorted by index and duplicates are merged (`hb-ot-map.cc:386`):

```c++
lookups.as_array ().sub_array (last_num_lookups, lookups.length - last_num_lookups).qsort ();

unsigned int j = last_num_lookups;
for (unsigned int i = j + 1; i < lookups.length; i++)
  if (lookups.arrayZ[i].index != lookups.arrayZ[j].index)
    lookups.arrayZ[++j] = lookups.arrayZ[i];
  else
  {
    lookups.arrayZ[j].mask |= lookups.arrayZ[i].mask;
    lookups.arrayZ[j].auto_zwnj &= lookups.arrayZ[i].auto_zwnj;
    lookups.arrayZ[j].auto_zwj &= lookups.arrayZ[i].auto_zwj;
  }
```

A lookup used by two features in one stage runs once, on the glyphs where either is on, since the masks are OR-ed. It passes over a joiner only if both features would. Its `random` and `per_syllable` flags, and the feature tag a trace shows for it, come from whichever entry the sort left first, and HarfBuzz’s sort is “not stable” (`hb-algs.hh:1507`). That matters only for a lookup shared by features with different flags (inferred).

The same lookup in two stages is two entries, and runs twice.

## Running the map

`hb_ot_map_t::apply` (`hb-ot-layout.cc:2069`) loops over the stages and their lookups. For each lookup it checks digests, sets the lookup’s mask and flags, and runs it; after each stage, it calls the pause function. `substitute` runs it for GSUB, `position` for GPOS. What happens inside one lookup is the subject of [GSUB: substituting glyphs](gsub.html#running-one-lookup), and where in the pipeline the two calls come is in [The pipeline, step by step](pipeline-step-by-step.html).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-shape.cc` | `hb_ot_shape_collect_features`, the default feature lists, and `hb_ot_shape_setup_masks` |
| `src/hb-ot-map.hh` | `hb_ot_map_t`, `hb_ot_map_builder_t`, the feature flags, `HB_OT_MAP_MAX_BITS` |
| `src/hb-ot-map.cc` | `add_feature`, `add_pause`, `add_lookups`, and `compile`: merging, bits, the required feature, stages, sorting |
| `src/hb-ot-layout.cc` | `hb_ot_layout_collect_features_map`, the required-feature and variation queries, and `hb_ot_map_t::apply` |
| `src/hb-ot-layout-gsubgpos.hh` | `get_feature_variation`, `get_lookup_variations`, and the FeatureVariations check in `sanitize` |
| `src/hb-ot-layout-common.hh` | `FeatureVariations`, `FeatureTableSubstitution`, `LookupVariationRecord` |
| `src/hb-ot-shaper-*.cc` | each script shaper’s `collect_features` and `override_features`, with their pauses |

## In short

* The planner asks for features in a fixed order: `rvrn`, direction, fractions, `rand`, `Harf`, the script shaper’s, `Buzz`, the common and horizontal ones, the application’s, and the shaper’s overrides.
* Requests for the same tag are merged: a later global one sets the value, a ranged one makes the feature non-global, and the earliest stage wins. A range followed by a global request for the same tag clears the global bit, turning off other features in that range.
* Features are found in the chosen language system; the required feature is added by index and can’t be turned off.
* Global features with value 1 share bit 31. Others get up to eight bits each, from bits 4 to 29, in tag order; when those run out, features are dropped without a word.
* Pauses divide GSUB into stages. `rvrn` has stage 0 to itself; `Harf` and `Buzz` bracket the script shaper’s stages. GPOS has one stage.
* A FeatureVariations record replaces whole feature tables, for any feature; 1.1 lookup variations choose groups of lookups by condition. HarfBuzz’s reading of minorVersion 1 differs from the ISO draft’s, and a mismatch can cost the whole GSUB.
* Within a stage, lookups are sorted by index and shared ones merged, with their masks OR-ed.
