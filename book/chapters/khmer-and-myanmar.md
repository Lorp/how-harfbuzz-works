# Khmer and Myanmar

Khmer and Myanmar are written with scripts of the Brahmi family, like the nine of [the Indic model](indic-model.html), and each has a shaper of its own. Both began inside the Indic shaper: `NEWS` for 0.9.2 announces a “New Indic shaper, supporting main Indic scripts, Sinhala, and Khmer”, 0.9.13 a “New Win8-style Myanmar shaper”, and 1.7.5 says “Separate Khmer shaper from Indic.” What they kept is the machinery: the generated table of categories, a Ragel scanner over them, the `syllable` byte, `foreach_syllable`, a stable sort by position, and dotted circles for broken clusters.

What they dropped is most of the Indic shaper’s cleverness. Neither asks the font which consonant is the base, neither has a final reordering, and neither sets more than a handful of mask bits. Each reorders a syllable once, before its basic features, in the order Microsoft’s specification for the script gives, and then lets the font’s lookups do the rest. The two differ from each other in one way that matters to fonts: Khmer’s basic features run together, Myanmar’s one at a time.

The examples use four test fonts with plain boxes for glyphs, built by `fonts/khmer-and-myanmar/build-fonts.py`. `khmer.ttf` has lookups under `khmr` for `pref`, `blwf`, `abvf`, `pstf`, `cfar`, and `psts`; `khmer-no-pref.ttf` leaves out `pref`, and `khmer-late.ttf` puts `cfar`’s lookup first in the LookupList. `myanmar.ttf` has lookups under `mym2` for `rphf`, `pref`, and `blwf`. Every result and trace on this page was produced by running HarfBuzz {{hb}} on them when the page was built.

## Side by side

| | Indic | Khmer | Myanmar |
|---|---|---|---|
| categories | the shared table | the shared table, Khmer’s own overrides | the shared table, Myanmar’s own overrides |
| positions | from the table, then from the font | none | assigned while reordering |
| syllable types | six | three | three |
| `locl` and `ccmp` | before reordering | after reordering, with the basic features | before reordering |
| reorderings | initial and final | one | one |
| asks the font | `rphf`, `pref`, `blwf`, `pstf`, `vatu` | never | never |
| basic features | one stage each | one stage for all | one stage each |
| masks | most basic features | `pref`, `blwf`, `abvf`, `pstf`, `cfar` | none |
| presentation features | within the syllable | across syllables | across syllables |
| zero-width marks | none | none | by GDEF, before GPOS |
| `liga` | off | off, and `clig` on | on |

The rest of the chapter goes through the rows, script by script.

## Khmer

The shaper is `hb-ot-shaper-khmer.cc` (381 lines), about a quarter of the Indic shaper’s size, and its grammar `hb-ot-shaper-khmer-machine.rl`. Unlike Myanmar and the Indic scripts, Khmer gets its shaper whatever script tag the font’s GSUB was found under, `DFLT` included (`hb-ot-shaper.hh:247`).

### Categories

`setup_masks_khmer` (`:174`) looks each character up with `hb_indic_get_categories`, the same function as the Indic shaper, and keeps only the low byte, the category, in the scratch byte `khmer_category` ([Buffers](buffers.html#eight-bytes-of-scratch-space)). The position in the high byte is thrown away: Khmer has no use for it.

The generator gives Khmer and Myanmar vowel signs a category made from their position (`position_to_category`, `gen-indic-table.py:434`, applied at `:473`): a left one is `VPre`, a top one `VAbv`, a bottom one `VBlw`, a right one `VPst`. A two-part vowel sign has the position of its last part, so U+17BE KHMER VOWEL SIGN OE, top and left, is `VAbv`, and U+17C4 KHMER VOWEL SIGN OO, left and right, is `VPst`. Then come Khmer’s overrides (`:312`):

| Category | Characters | What they are |
|---|---|---|
| `Ra` | U+179A | RO, so that the reordering can find COENG + RO |
| `Robatic` | U+17C9, U+17CA, U+17CC | the two register shifters, and ROBAT |
| `Xgroup` | U+17C6, U+17CB, U+17CD–U+17D1 | signs above the base, such as NIKAHIT |
| `Ygroup` | U+17C7, U+17C8, U+17DD, U+17D3 | signs after it, such as REAHMUK; for U+17D3, “Just guessing. Uniscribe doesn’t categorize it.” |
| `PLACEHOLDER` | U+17D9 | issue #2384 |

The rest come from Unicode through the shared mapping. U+17D2 KHMER SIGN **COENG**, which makes the consonant after it a **subscript**, written below or beside the base, is an `Invisible_Stacker`, and so `H`: “We use category H for spec category Coeng” (`hb-ot-shaper-khmer-machine.rl:58`). The consonants are `C`, the independent vowels `V`. The machine exports the categories it uses with the same numbers as the Indic machine’s (`C = 1`, `H = 4`, `Ra = 15`, and so on), since the table holds one number per character for all three shapers, and adds 20 to 27 for its own. The table checks only that Khmer’s and Myanmar’s four vowel categories agree (`hb-ot-shaper-indic-table.cc:61`); the shared numbers are kept equal by hand.

### Syllables

The grammar (`hb-ot-shaper-khmer-machine.rl:79`), “experimentally extracted from what Uniscribe allows”:

```
c = (C | Ra | V);
cn = c.((ZWJ|ZWNJ)?.Robatic)?;
joiner = (ZWJ | ZWNJ);
xgroup = (joiner*.Xgroup)*;
ygroup = Ygroup*;

matra_group = VPre? xgroup VBlw? xgroup (joiner?.VAbv)? xgroup VPst?;
syllable_tail = xgroup matra_group xgroup (H.c)? ygroup;

broken_cluster =	Robatic? (H.cn)* (H | syllable_tail);
consonant_syllable =	(cn|PLACEHOLDER|DOTTEDCIRCLE) broken_cluster;
other =			any;
```

A **Khmer consonant syllable** is a consonant or independent vowel, any number of subscripts (COENG + consonant), at most one vowel sign of each position, with the above signs between them, and the signs after. Compared with the Indic grammar there is no reph, no nukta, and no half form; a vowel is just another consonant, so there are no vowel syllables; joiners appear only before above signs, an above vowel sign, the register shifters, and ROBAT; and the syllable may end with a lone COENG, where Indic would need virama + ZWNJ. Two details go beyond the specification: one more COENG + consonant may follow the vowel signs, and a pre-base and a post-base vowel sign may stand together, which the specification forbids but which the split vowel signs need once they are decomposed. There are three syllable types: consonant syllables, broken clusters (marks with nothing to attach to, which get a dotted circle as in [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html)), and **non-Khmer clusters**, of one character each.

### Features and stages

`collect_features_khmer` (`:101`):

```c++
map->add_gsub_pause (setup_syllables_khmer);
map->add_gsub_pause (reorder_khmer);

/* Testing suggests that Uniscribe does NOT pause between basic
 * features.  Test with KhmerUI.ttf and the following three
 * sequences:
 ...
 * https://github.com/harfbuzz/harfbuzz/issues/974
 */
map->enable_feature (HB_TAG('l','o','c','l'), F_PER_SYLLABLE);
map->enable_feature (HB_TAG('c','c','m','p'), F_PER_SYLLABLE);

unsigned int i = 0;
for (; i < KHMER_BASIC_FEATURES; i++)
  map->add_feature (khmer_features[i]);

/* https://github.com/harfbuzz/harfbuzz/issues/3531 */
map->add_gsub_pause (hb_syllabic_clear_var);

for (; i < KHMER_NUM_FEATURES; i++)
  map->add_feature (khmer_features[i]);
```

(trimmed). The syllables are found and reordered in two pauses before any of the shaper’s lookups. Then `locl`, `ccmp`, and the five basic features, `pref`, `blwf`, `abvf`, `pstf`, and `cfar`, share one stage, confined to the syllable. The syllable byte is cleared, and the presentation features `pres`, `abvs`, `blws`, and `psts` follow, global, with the common and horizontal features. `override_features_khmer` (`:135`) turns `liga` off and `clig` on, since the “Khmer spec has ‘clig’ as part of required shaping features”. All the features have both manual-joiner flags ([Joiners](gsub.html#joiners)). [Feature order](feature-order.html#khmer) lists these stages beside the other shapers’.

Three things differ from the Indic stages. `locl` and `ccmp` come after the reordering, not before, so they see the reordered syllable. The basic features have no pauses between them, so their lookups run in the order of the font’s LookupList, not in the order of the features ([Sorting, and lookups shared by features](from-features-to-lookups.html#sorting-and-lookups-shared-by-features)). [Why shaping exists](why-shaping-exists.html) quoted the reason: Uniscribe was found to work that way. And with the syllable byte gone, the presentation features see across syllables, where the Indic shaper keeps its presentation features within one. The comment above the array still says the basic features “are applied all at once, before reordering”; they run after it.

The basic features have mask bits, and the reordering sets them. `cfar`, “Conjunct Form After Ro”, is the one feature here the Indic shaper doesn’t have.

### Reordering

`reorder_khmer` (`:302`) inserts dotted circles, then calls `reorder_consonant_syllable` (`:206`) on every consonant syllable and broken cluster. Its comment cites Microsoft’s Devanagari specification, but the steps quoted inside are the Khmer specification’s. It does three things.

**Masks.** Every glyph after the first gets `blwf`, `abvf`, and `pstf`. The specification gives each subscript one of the three, by its subscript type; HarfBuzz lets the font’s lookups choose, by which glyphs they match.

**COENG + RO.** A COENG followed by RO is moved, with the RO, to the start of the syllable, and the two get the `pref` mask (`:239`):

```c++
if (info[i].khmer_category() == K_Cat(H) && num_coengs <= 2 && i + 1 < end)
{
  num_coengs++;

  if (info[i + 1].khmer_category() == K_Cat(Ra))
  {
    for (unsigned int j = 0; j < 2; j++)
      info[i + j].mask |= khmer_plan->mask_array[KHMER_PREF];

    /* Move the Coeng,Ro sequence to the start. */
    buffer->merge_clusters (start, i + 2);
    ...
    if (khmer_plan->mask_array[KHMER_CFAR])
      for (unsigned int j = i + 2; j < end; j++)
        info[j].mask |= khmer_plan->mask_array[KHMER_CFAR];

    num_coengs = 2; /* Done. */
  }
}
```

(trimmed). Everything typed after the COENG + RO gets the `cfar` mask, which “allows distinguishing the following cases with MS Khmer fonts”: a subscript after the subscript RO, and one before it.

**Pre-base vowel signs.** A `VPre` is moved to the start, ahead of a COENG + RO moved there before it.

Each move merges clusters from the start of the syllable to the glyph moved. There is no probe: the shaper never asks whether the font’s `pref` would substitute COENG + RO. It moves the pair in every font, and the `pref` mask only tells the font’s lookups where to act. Here are KA + COENG + RO, the same with vowel sign OO, and both in the font with no `pref`:

```shape
khmer.ttf  ក\u17D2រ  --language=km
khmer.ttf  ក\u17D2រ\u17C4  --language=km
khmer-no-pref.ttf  ក\u17D2រ  --language=km
khmer-no-pref.ttf  ក\u17D2រ\u17C4  --language=km
```

Without `pref`, the COENG and RO still stand before KA: a zero-width COENG and a full RO, in front of the consonant they belong under. A Khmer font needs its `pref` lookup.

The trace of NGO, COENG, RO, COENG, KO, and vowel sign OO, from the reordering to the end of GSUB:

```trace
font: khmer.ttf
text: ង\u17D2រ\u17D2គ\u17C4
options: --language=km
from: start reordering khmer
to: end table GSUB
```

The reordering puts the first part of OO, then COENG + RO, before NGO, and merges the syllable into one cluster. Then the lookups run in LookupList order with no pause between them: `pref` makes RO’s pre-base form, `blwf` KO’s subscript, `pstf` the second part of OO, and `cfar` changes KO’s subscript, because it was typed after the COENG + RO. With the subscripts the other way round, it isn’t:

```shape
khmer.ttf  ង\u17D2រ\u17D2គ  --language=km
khmer.ttf  ង\u17D2គ\u17D2រ  --language=km
khmer-late.ttf  ង\u17D2រ\u17D2គ  --language=km
```

`khmer-late.ttf` has the same lookups, with `cfar`’s first in the LookupList. Running first, it finds COENG and KO where it expects KO’s subscript, and does nothing. With a stage for each basic feature, as the Indic and Myanmar shapers have, `cfar`’s lookup would have run after `blwf`’s, wherever it was in the list.

> For type designers: in a Khmer font, the order of the LookupList is the order the basic features’ lookups run in, whatever features they belong to, and `locl` and `ccmp` lookups are in the same stage. A lookup that needs another’s output must come after it in the list. COENG + RO is always moved before the base, so `pref` must turn it into a glyph that looks right there.

### Split vowels

Five vowel signs, U+17BE, U+17BF, U+17C0, U+17C4, and U+17C5, are written in two parts, the first like U+17C1 KHMER VOWEL SIGN E, before the consonant. Unicode doesn’t decompose them. HarfBuzz’s `decompose_khmer` (`:326`) does, into U+17C1 followed by the sign itself, and `compose_khmer` won’t put them back together ([The shapers’ compose and decompose](normalization.html#the-shapers-compose-and-decompose)). U+17C1 is a `VPre`, so the reordering moves it; the sign that is left stands for its own second part, and a font’s `abvf` or `pstf` replaces the whole sign’s glyph with that part, as the Khmer specification says:

```shape
khmer.ttf  ក\u17BE  --language=km
khmer.ttf  ក\u17C4  --language=km
khmer.ttf  \u17C4  --language=km
```

KA with OE gets `abvf`’s above part, KA with OO `pstf`’s right part. Alone, OO is a broken cluster, and its first part goes before the dotted circle. The decomposition is HarfBuzz’s, not the font’s. With the shaper’s normalization mode, `COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT`, it is used whenever the font has glyphs for U+17C1 and the sign, though the font has a glyph for the whole sign too ([The modes](normalization.html#the-modes)).

### Across syllables

The presentation features run after the syllables are cleared. `khmer.ttf`’s `psts` has one contextual rule, which shortens OO’s second part before a KA:

```shape
khmer.ttf  ក\u17C4  --language=km
khmer.ttf  ក\u17C4ក  --language=km
khmer.ttf  ក\u17C4ក  --language=km  --show-flags
```

The KA is in the next syllable, and the rule still matches. In the Indic shaper, whose presentation features are per syllable, it wouldn’t ([GSUB](gsub.html#skipping-step-by-step)). The second KA is marked unsafe to break (`#1`), as any glyph is whose shaping depended on its neighbor. The comment above the pause gives only an issue number, #3531; `NEWS` for 4.2.1 records “Reinstate a pause after basic features in Khmer shaper, fixing a regression introduced in previous release.” That the two are the same change is inferred.

### The subscript count

The test `num_coengs <= 2` is meant to apply the specification’s rule, quoted in the comment above it: a COENG is handled “(and subscript count is less than two)”. But the counter starts at zero and is checked before it is incremented, so a third COENG passes too. And after a COENG + RO the code sets the counter to 2, “Done”, which the next COENG still passes. So a second COENG + RO in one syllable is moved as well, in front of the first:

```shape
khmer.ttf  ក\u17D2រ\u17D2រ  --language=km
khmer.ttf  ក\u17D2ក\u17D2ក\u17D2រ  --language=km
khmer.ttf  ក\u17D2ក\u17D2ក\u17D2ក\u17D2រ  --language=km
```

Two subscript ROs are not good Khmer, and the grammar allows any number of subscripts where the specification allows two, so this only matters for text that is wrong already. Whether Uniscribe did the same isn’t recorded; the comment “Done” suggests the loop was meant to stop (inferred). In the last line the fourth COENG + RO is neither moved nor given `pref`, and is left as COENG and a full RO.

## Myanmar

The shaper is `hb-ot-shaper-myanmar.cc` (390 lines, Zawgyi included) and its grammar `hb-ot-shaper-myanmar-machine.rl`. A font needs lookups under `mym2` to get it ([Myanmar and Zawgyi](choosing-a-script-shaper.html#myanmar-and-zawgyi)).

### Categories

`setup_masks_myanmar` (`:138`) keeps the category in `myanmar_category`, and reserves `myanmar_position`, but like Khmer it discards the table’s position: the reordering assigns positions itself. The vowel signs get `VPre`, `VAbv`, `VBlw`, and `VPst` from their positions, as in Khmer, and Myanmar’s overrides (`gen-indic-table.py:336`), taken from Microsoft’s specification, use those and categories of Myanmar’s own, numbered from 32 up:

| Category | Characters | What they are |
|---|---|---|
| `Ra` | U+1004, U+101B, U+105A | NGA, RA, and MON NGA, which begin a kinzi |
| `As` | U+103A | ASAT |
| `MY`, `MR`, `MW`, `MH`, `ML` | U+103B and two Mon medials; U+103C; U+103D, U+1082; U+103E; U+1060 | the medial consonants: YA, RA, WA, HA, MON LA |
| `A` | U+1032, U+1036 | AI and ANUSVARA |
| `PT` | U+1063, U+1064, U+1069–U+106D, U+AA7B | Pwo and other tones |
| `SM` | U+1038 and Shan tones | VISARGA |
| `VS` | U+FE00–U+FE0F | variation selectors, “not Myanmar-specific” |
| `C` | U+104E | “The spec says C, IndicSyllableCategory says Consonant_Placeholder” |
| `GB` | U+104A, U+2015, U+2022, U+25FB–U+25FE, and the shared placeholders such as NO-BREAK SPACE | placeholders: `PLACEHOLDER` under another name |

U+1039 MYANMAR SIGN VIRAMA, which makes stacked consonants, is `H`; U+1037 DOT BELOW, a `Nukta` in Unicode, is `DB`, the same number as Indic’s `N`. The grammar notes that the specification’s digits `D` are folded into `GB`, and its digit zero `D0` into `D`, because `D0` “is not implemented by Uniscribe”, and its punctuation `P` into `GB` too (`hb-ot-shaper-myanmar-machine.rl:60`).

### Syllables

The grammar (`:93`):

```
j = ZWJ|ZWNJ;			# Joiners
k = (Ra As H);			# Kinzi
sm = SM | SMPst;
c = C|Ra;			# is_consonant

medial_group = MY? As? MR? ((MW MH? ML? | MH ML? | ML) As?)?;
main_vowel_group = (VPre.VS?)* VAbv* VBlw* A* (DB As?)?;
post_vowel_group = VPst MH? ML? As* VAbv* A* (DB As?)?;
tone_group = sm | PT A* DB? As?;

complex_syllable_tail = As* medial_group main_vowel_group post_vowel_group* tone_group* j?;
syllable_tail = (H (c|IV).VS?)* (H | complex_syllable_tail);

consonant_syllable =	(k|CS)? (c|IV|GB|DOTTEDCIRCLE).VS? syllable_tail;
broken_cluster =	k? VS? syllable_tail;
other =			any;

main := |*
	consonant_syllable	=> { found_syllable (myanmar_consonant_syllable); };
	j | SMPst		=> { found_syllable (myanmar_non_myanmar_cluster); };
	broken_cluster		=> { found_syllable (myanmar_broken_cluster); ... };
	other			=> { found_syllable (myanmar_non_myanmar_cluster); };
*|;
```

A **kinzi** is NGA (or RA, or MON NGA) + ASAT + VIRAMA before a consonant, which writes the first consonant as a small mark above the second: it is Myanmar’s counterpart of the reph. A **Myanmar consonant syllable** is an optional kinzi, a consonant, independent vowel, or placeholder, any number of stacked consonants (VIRAMA + consonant), then ASATs, the medials in their Unicode order, the vowel signs, the anusvaras and dot below, any number of post-base vowel groups and tone groups, and a joiner at the end. The tone groups repeat since 10.2.0, which `NEWS` records as “Allow all Myanmar tone marks (including visarga) in any order.” The pattern follows the specification’s cluster rule nearly term for term, without its limit of 31 characters to a sequence; HarfBuzz’s own limit, 64 glyphs to a syllable, applies here as in the Indic shaper ([A limit on syllable length](indic-model.html#a-limit-on-syllable-length)). A joiner, or a post-base syllable modifier, alone is a **non-Myanmar cluster**, not a broken one: it comes before `broken_cluster` in the scanner, and the two match the same length.

### Features and stages

`collect_features_myanmar` (`:111`) is close to the Indic shaper’s: find syllables; `locl` and `ccmp`, per syllable (“The Indic specs do not require ccmp, but we apply it here since if there is a use of it, it’s typically at the beginning”); reorder; then `rphf`, `pref`, `blwf`, and `pstf`, each with a pause after it, “applied in order, one at a time”; clear the syllables; then `pres`, `abvs`, `blws`, and `psts`, “all at once”, outside the syllable. [Feature order](feature-order.html#myanmar) lists these stages beside the other shapers’. The basic features are per syllable but global: none has a mask bit, so every glyph of the syllable may take every one of them, and a font’s lookups must say by their own rules which glyphs they apply to. The features have manual ZWJ but not manual ZWNJ, so a ZWNJ in a rule’s context is passed over. There is no `override_features`, so `liga` stays on: `NEWS` for 2.7.3 says “Don’t disable liga feature in myanmar shaper, to match Uniscribe.” Marks are zeroed by their GDEF class before GPOS (`HB_OT_SHAPE_ZERO_WIDTH_MARKS_BY_GDEF_EARLY`, `:361`, [Zeroing marks](fallbacks.html#zeroing-marks)), where Khmer and Indic zero nothing; the specification too says “mark glyphs have their width set to zero by OTLS”.

### Reordering

`initial_reordering_consonant_syllable` (`:179`) is the only reordering. Its comment cites Microsoft’s Myanmar specification, whose rules are four:

> - Kinzi sequences (K) are reordered directly after the cluster base
> - The medial ra (MR) is reordered before the base consonant
> - Pre-base vowels (VPre) are reordered to the start of the syllable cluster. A sequence of multiple prebase vowels is permitted. Such sequences are moved as a block to the beginning of the cluster
> - Anusvara (A) coming immediately after one or more below-base vowels (VBlw) will reorder immediately before them

First the kinzi and the base. If the syllable starts with `Ra`, `As`, `H`, those three are a kinzi: no font is asked, as the Indic shaper asks `rphf` about a reph. The base is the *first* consonant after it (`:203`), where the Indic base search takes the last that has no below-base or post-base form. Myanmar’s stacked consonants always go below the first, so there is nothing to decide.

Then every glyph gets a position from the Indic list ([Categories and positions](indic-model.html#categories-and-positions)), in a loop that “may be ugly, but it implements all of Myanmar reordering!” (`:213`):

| Glyphs | Position |
|---|---|
| a vowel sign E or other `VPre` | `POS_PRE_M` |
| anything before the base, and medial RA | `POS_PRE_C` |
| the base | `POS_BASE_C` |
| the kinzi, and what follows the base until a below-base vowel sign | `POS_AFTER_MAIN` |
| below-base vowel signs | `POS_BELOW_C` |
| an anusvara after a below-base vowel sign | `POS_BEFORE_SUB` |
| everything after that | `POS_AFTER_SUB` |
| a variation selector | the position of the glyph before it |

A stable sort by position follows (`:273`), “Sit tight, rock ’n roll!”, and moving glyphs merges their clusters. Since the kinzi is the first glyph at `POS_AFTER_MAIN`, it lands just after the base, ahead of the stacked consonants. Last, a run of several pre-base vowel signs is reversed, each with its variation selector, as in the Indic shaper (issue #3863).

Here are GA with a kinzi, KA with medial RA, the same with vowel sign E, and the three together:

```shape
myanmar.ttf  င\u103A\u1039ဂ  --language=my
myanmar.ttf  က\u103C  --language=my
myanmar.ttf  က\u103C\u1031  --language=my
myanmar.ttf  င\u103A\u1039က\u103C\u1031  --language=my
```

The trace of the last:

```trace
font: myanmar.ttf
text: င\u103A\u1039က\u103C\u1031
options: --language=my
from: start reordering myanmar
to: end table GSUB
```

The reordering puts E first, medial RA before KA, and the kinzi’s three characters after KA, in one cluster. Then the basic features run, each in its own stage. `rphf` finds NGA, ASAT, and VIRAMA after the base and ligates them into the kinzi glyph. `myanmar.ttf`’s `pref` is a contextual rule, as the specification says Microsoft’s Myanmar Text font uses it, choosing a wide medial RA when a consonant follows. It matches because the medial RA now stands before KA; in the text it came after it.

The kinzi moves before `rphf` runs, where the Indic reph moves after it, and only if `rphf` made one. So a Myanmar font’s `rphf` lookup must match NGA + ASAT + VIRAMA after the base, and if it has none, the three glyphs stay there unformed. The stacked consonant and the anusvara:

```shape
myanmar.ttf  က\u1039က  --language=my
myanmar.ttf  က\u102F\u1036  --language=my
```

The first KA is the base and the second, after VIRAMA, becomes `blwf`’s subscript. Anusvara, typed after vowel sign U, is put before it.

> For type designers: write a Myanmar font’s lookups for the reordered syllable: E, medial RA, the base, the kinzi, then stacked consonants and the rest. The basic features have no masks, so a lookup for `pref` or `blwf` applies wherever its rule matches in the syllable; give it context if it shouldn’t.

### The Microsoft specification

Of the shapers in this part of the book, Myanmar follows its Microsoft specification most closely. The categories and the grammar are the specification’s, with the folding of `D`, `D0`, and `P` and with Myanmar Text’s and Uniscribe’s behavior where they differ; the four reordering rules are its four; the features are its features, in its order. The specification ends its reordering section with a “pathological” syllable, which `myanmar.ttf` has glyphs for:

```shape
myanmar.ttf  င\u103A\u1039က\u1039က\u103B\u103C\u103D\u1031\u1031\u102D\u102F\u1036\u102C\u1036  --language=my
```

The specification gives the reordered sequence as U+1031 U+1031 U+103C U+1000 U+1004 U+103A U+1039 U+1039 U+1000 U+103B U+103D U+102D U+1036 U+102F U+102C U+1036. HarfBuzz’s result is in the same order, once `rphf` has made the kinzi’s three glyphs one and `blwf` has made VIRAMA + KA a subscript. HarfBuzz adds `ccmp`, which the specification doesn’t list, and zeroes marks, as the specification says OTLS, Microsoft’s layout library, does. The specification inserts a dotted circle for a kinzi with no base, and so does HarfBuzz:

```shape
myanmar.ttf  င\u103A\u1039  --language=my
myanmar.ttf  \u1031  --language=my
```

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-shaper-khmer.cc` | Khmer’s features and stages, the masks, the COENG + RO and pre-base vowel moves, and the split vowels’ `decompose` and `compose` |
| `src/hb-ot-shaper-khmer-machine.rl` | Khmer’s categories and syllable grammar, in Ragel |
| `src/hb-ot-shaper-myanmar.cc` | Myanmar’s features and stages, the reordering, and the Zawgyi shaper |
| `src/hb-ot-shaper-myanmar-machine.rl` | Myanmar’s categories and syllable grammar |
| `src/hb-ot-shaper-khmer-machine.hh`, `src/hb-ot-shaper-myanmar-machine.hh` | the machines Ragel generated, committed |
| `src/gen-indic-table.py` | the category overrides for Khmer and Myanmar, and `position_to_category` |
| `src/hb-ot-shaper-indic-table.cc` | the generated table all three shapers share |
| `src/hb-ot-shaper.hh` | which script gets which shaper |
| `test/shape/data/in-house/tests/khmer-*.tests`, `myanmar-*.tests` | HarfBuzz’s own shaping tests for the two |

## In short

* Khmer and Myanmar share the Indic shaper’s category table, Ragel scanner, syllable byte, and sort, but not its font probes or its final reordering. Each reorders a syllable once, before its basic features, as Microsoft’s specification for the script says.
* Khmer moves COENG + RO and the pre-base vowel signs to the start of the syllable in every font, marks the pair for `pref` and what follows it for `cfar`, and leaves the rest to the font’s lookups. Its split vowels are decomposed by HarfBuzz into vowel sign E and the sign itself.
* Khmer’s `locl`, `ccmp`, and five basic features share one stage, so their lookups run in LookupList order, because Uniscribe was found to do that. Its presentation features see across syllables.
* Myanmar takes a kinzi from the start of the syllable without asking the font, makes the first consonant the base, and sorts E, medial RA, the base, and the kinzi into the specification’s order. Its basic features run one at a time, with no masks.
* The Khmer shaper lets a second COENG + RO and a third subscript through the specification’s limit of two, which only text that is wrong already shows.
