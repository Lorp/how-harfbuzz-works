# Vertical text

Chinese, Japanese and Korean can be set in columns, read from top to bottom, and so can Mongolian and a few other scripts. HarfBuzz shapes such a column as a run whose direction is **top to bottom** (`HB_DIRECTION_TTB`) or, more rarely, **bottom to top** (`HB_DIRECTION_BTT`). Most of the pipeline doesn’t care: the same steps run, in the same order, on the same buffer. What changes is a handful of decisions spread through it. A different list of features is asked for. Some punctuation is swapped for vertical forms before the `cmap` is read, if the font can’t do it itself. Advances run down the y axis instead of along x, every glyph is hung from a vertical origin, and GPOS reads the other half of each value record.

This chapter collects those decisions. Where vertical advances and origins come from is in [Where metrics come from](where-metrics-come-from.html#vertical-advances-and-origins).

The examples use four small test fonts, built by `fonts/vertical-text/build-fonts.py` from one feature file, `vertical.fea`. Their glyphs are boxes. They have `vhea` and `vmtx`, so every glyph advances 1,000 units down and hangs from a point 880 units above the baseline, half its width across. Every shaping result and trace on this page was produced by HarfBuzz {{hb}} when the page was built.

## What HarfBuzz does, and what it leaves to the application

A vertical run is a run like any other: one font, one script, one language and one direction. HarfBuzz never chooses vertical for itself. When a buffer’s direction is left unset, `hb_buffer_guess_segment_properties` takes the script’s horizontal direction, and left to right if it has none (`hb-buffer.cc:765`). An application that wants a column says so with `hb_buffer_set_direction`, or `hb-shape --direction=ttb`.

In a column of Japanese, most characters stand upright, but Latin words and many symbols are usually turned on their side. HarfBuzz has no notion of that choice. Every glyph in a vertical run is set upright, one below another. A sideways run is a horizontal run, shaped left to right and rotated by the application when it draws it. HarfBuzz’s manual says only that HarfBuzz lays text out “on a single horizontal (or vertical) line”, and that if the direction changes within a string, “you will need to shape each run independently” (`docs/usermanual-what-is-harfbuzz.xml:346`, `:395`). Nor does HarfBuzz carry the data an application needs to choose. The Unicode functions it consults have no Vertical_Orientation property (the list is at `hb-unicode.hh:44`), so splitting a column into upright and sideways runs is the application’s work, done before HarfBuzz is called (inferred from what is missing).

Here is a short Latin word set both ways:

```shape
vertical.ttf  ab  --direction=ttb  --language=en
vertical.ttf  ab  --direction=ltr  --language=en
```

Set vertically, `a` and `b` are stacked, upright and centred, with no ligature and no kerning. Set horizontally, the font’s `liga` turns them into `a_b`, which an application could then rotate.

## Direction

The four directions are numbered so that two bit tests sort them (`hb-common.h:288`): `LTR` is 4, `RTL` 5, `TTB` 6 and `BTT` 7. `HB_DIRECTION_IS_VERTICAL` is true for 6 and 7, and `HB_DIRECTION_IS_BACKWARD` for 5 and 7. So bottom to top is to vertical text what right to left is to horizontal text: the backward direction.

### Bottom to top becomes top to bottom

Step 5 of the pipeline, `hb_ensure_native_direction`, puts the text in the order the font expects. For horizontal text, that depends on the script. For vertical text it doesn’t: everything becomes top to bottom (`hb-ot-shape.cc:635`, trimmed):

```c++
/* TODO vertical:
 * The only BTT vertical script is Ogham, but it's not clear to me whether OpenType
 * Ogham fonts are supposed to be implemented BTT or not.  Need to research that
 * first. */
if ((HB_DIRECTION_IS_HORIZONTAL (direction) &&
     direction != horiz_dir && HB_DIRECTION_IS_VALID (horiz_dir)) ||
    (HB_DIRECTION_IS_VERTICAL   (direction) &&
     direction != HB_DIRECTION_TTB))
{
  _hb_ot_layout_reverse_graphemes (buffer);
  buffer->props.direction = HB_DIRECTION_REVERSE (buffer->props.direction);
}
```

A bottom-to-top run is reversed, grapheme by grapheme, and from then on it *is* a top-to-bottom run. Every lookup, every positioning step, sees TTB. The fonts are written for reading order down the column, and this is the one order they get.

Right-to-left text is reversed back at the end of positioning, so that the glyphs come out in left-to-right visual order. Vertical text isn’t: that reversal tests the buffer’s current direction (`hb-ot-shape.cc:1102`), which by then is TTB. The direction is restored to BTT only as `hb_ot_shape_internal` returns (`:1200`). So a bottom-to-top run comes out top to bottom, its last character first, which is the visual order of a column drawn downwards:

```shape
vertical.ttf  「水」  --direction=ttb  --language=ja
vertical.ttf  「水」  --direction=btt  --language=ja
```

Read from the top, the glyphs and positions are the same. Only the clusters run the other way: in the bottom-to-top run, the glyph at the top is cluster 2, the closing bracket, drawn as an opening one.

### Mirroring a column

The brackets were swapped by step 7, `hb_ot_rotate_chars`, which mirrors characters when the *target* direction, the one the application asked for, is backward ([The pipeline, step by step](the-pipeline-step-by-step.html#mirroring)). BTT is backward, so U+300C 「 became its mirror U+300D 」 before the `cmap` was read, and the other way round. The trace shows it at the first point a trace can see, with the order already reversed:

```trace
font: vertical.ttf
text: 「水」
options: --direction=btt --language=ja
from: start decompose
to: end table GSUB
```

That is what a column read upwards needs. The opening bracket is at the bottom and must open upwards, which is the shape of the closing bracket in a top-to-bottom column (the writer’s reading; HarfBuzz’s source doesn’t say why). The `rtlm` mask bit that mirroring sets on other characters does nothing here, because `rtlm` is only asked for in right-to-left text (`hb-ot-shape.cc:338`).

## The features a vertical run gets

Planning asks for features in a fixed order ([From features to lookups](from-features-to-lookups.html)). A vertical run gets the same list as a horizontal one, with two differences. It gets none of the direction features `ltra`, `ltrm`, `rtla` and `rtlm`. And where a horizontal run gets `calt`, `clig`, `curs`, `dist`, `kern`, `liga` and `rclt`, a vertical run gets one feature (`hb-ot-shape.cc:374`, trimmed):

```c++
if (HB_DIRECTION_IS_HORIZONTAL (planner->props.direction))
  for (unsigned int i = 0; i < ARRAY_LENGTH (horizontal_features); i++)
    map->add_feature (horizontal_features[i]);
else
{
  /* We only apply `vert` feature. See:
   * https://github.com/harfbuzz/harfbuzz/commit/d71c0df2d17f4590d5611239577a6cb532c26528
   * https://lists.freedesktop.org/archives/harfbuzz/2013-August/003490.html */

  /* We really want to find a 'vert' feature if there's any in the font, no
   * matter which script/langsys it is listed (or not) under.
   * See various bugs referenced from:
   * https://github.com/harfbuzz/harfbuzz/issues/63 */
  map->enable_feature (HB_TAG ('v','e','r','t'), F_GLOBAL_SEARCH);
}
```

That is why the test font’s `liga` didn’t apply to `ab` above. `NEWS` for 0.9.34 records the change: “Disable ‘liga’ in vertical text.”

**`vert`** (Vertical Alternates) is the OpenType feature that swaps glyphs for the forms they take upright in a column: punctuation moved to the top right of its em box, brackets and dashes turned. The test font’s `vert` is one single substitution:

```views
font: vertical.ttf
lookup: 1
fea: vertical.fea vert
cpp: SingleSubstFormat1_3
```

```shape
vertical.ttf  水、水。  --direction=ttb  --language=ja
vertical.ttf  水、水。  --direction=ltr  --language=ja
```

### Features HarfBuzz doesn’t turn on

Several other registered features are for vertical text, and HarfBuzz turns on none of them:

| Feature | What it does | The specification’s advice |
|---|---|---|
| `vkrn` | vertical kerning | active by default in most vertical layout |
| `vpal` | proportional vertical metrics | off by default |
| `vhal` | half-height vertical metrics | off by default |
| `valt` | alternate vertical metrics | active by default; fonts with `vmtx` shouldn’t have it |
| `vrt2` | vertical alternates and rotation | active by default, in place of `vert` |
| `vrtr` | alternates for glyphs to be rotated | active by default in sideways runs |

An application that wants them asks for them, as with any feature. The test font has a `vkrn` pair, which brings a closing bracket 300 units closer after a full stop, and a `vpal` value, which halves the comma’s height:

```shape
vertical.ttf  水。」  --direction=ttb  --language=ja
vertical.ttf  水。」  --direction=ttb  --language=ja  --features=vkrn
vertical.ttf  水、水  --direction=ttb  --language=ja  --features=vpal
```

The specification wants four of these on by default ([OpenType features u–z](https://learn.microsoft.com/en-us/typography/opentype/spec/features_uz)). `valt` is meant for fonts without `vmtx`, `vrt2` would replace the `vert` that HarfBuzz always applies, and `vrtr` is for sideways runs, which HarfBuzz never sees. That leaves `vkrn`, which “should be active by default” in most vertical text, and where HarfBuzz departs from the specification. HarfBuzz’s comment above, “We only apply `vert` feature”, points to a 2013 mailing-list thread for the reason. `vkrn` still has a part in the plan: in vertical text the plan’s kerning mask is `vkrn`’s rather than `kern`’s (`hb-ot-shape.cc:127`), so the legacy `kern` table, if a font uses one, applies only where `vkrn` is turned on ([Legacy kern](legacy-kern.html)).

### Finding `vert` anywhere

`F_GLOBAL_SEARCH` is the only flag of its kind, and `vert` the only feature that has it ([From features to lookups](from-features-to-lookups.html)). Every other feature is looked for in the language system HarfBuzz chose for the run. If `vert` isn’t there, in GSUB or GPOS, the map takes the first feature tagged `vert` in the whole FeatureList, whatever script lists it, or none (`hb-ot-map.cc:311`). The comment points to HarfBuzz issue #63 for the fonts that needed it.

`vert-kana.ttf` is the test font with `vert` listed only under `kana`. Its `hani` language system, the one chosen for this text, lists only `liga`:

```shape
vert-kana.ttf  水、水。  --direction=ttb  --language=ja
```

The punctuation is still vertical. A `vkrn` listed only under `kana` would not be found from Han text.

### `vrt2`

**`vrt2`** (Vertical Alternates and Rotation) was registered by Adobe, and the specification calls `vert` its “predecessor”. It does what `vert` does and also replaces proportional glyphs, mostly Latin and half-width katakana, with copies rotated a quarter turn, so that a font can turn sideways text by itself. The specification says it “overrides” `vert`, which is a subset of it, and that the two should never be used together.

HarfBuzz doesn’t look at `vrt2` unless asked. `vrt2.ttf` is the test font with `vrt2` in place of `vert`, and a second lookup in it that turns `a` into a rotated `a.rot`:

```shape
vrt2.ttf  ab、  --direction=ttb  --language=en
vrt2.ttf  ab、  --direction=ttb  --language=en  --features=vrt2
```

The rotated `a` appears only on request. The comma is vertical either way, but not through `vrt2`: the font has no `vert`, so HarfBuzz used the presentation-form fallback of the next section, and the comma arriving at GSUB was already U+FE11, which `vrt2`’s lookup doesn’t cover. In a font with both features, asking for `vrt2` doesn’t turn `vert` off: both run, in lookup order (read from the code). An application that wants `vrt2` *instead* of `vert` has to say `vert=0` too, and that in turn brings in the fallback, as the next section shows.

## The fallback to presentation forms

Unicode encodes vertical forms of some punctuation as characters of their own: U+FE10 to U+FE19 and U+FE30 to U+FE48, the “vertical forms” and the vertical half of the “CJK compatibility forms”. HarfBuzz uses them when a font gives it nothing better. In step 7 (`hb-ot-shape.cc:675`):

```c++
#ifndef HB_NO_VERTICAL
if (HB_DIRECTION_IS_VERTICAL (c->target_direction) && !c->plan->has_vert)
{
  for (unsigned int i = 0; i < count; i++) {
    hb_codepoint_t codepoint = hb_unicode_funcs_t::vertical_char_for (info[i].codepoint);
    if (unlikely (codepoint != info[i].codepoint && c->font->has_glyph (codepoint)))
      info[i].codepoint = codepoint;
  }
}
#endif
```

Three conditions. The run is vertical. The plan has no `vert`: `has_vert` is set when planning gave `vert` a mask (`hb-ot-shape.cc:125`), so it is false when the font has no `vert` feature anywhere, and also when the application turned `vert` off. And the font has a glyph for the presentation form. The replacement is made on characters, before normalization reads the `cmap`, so it works however the font’s glyphs are arranged, and the glyph that comes out is whatever the font maps the presentation form to.

`vertical_char_for` (`hb-unicode.hh:245`) is a hand-written switch, not generated from Unicode data. It has 34 entries:

| Characters | Vertical forms |
|---|---|
| en dash, em dash, two-dot leader, horizontal ellipsis | U+FE32, U+FE31, U+FE30, U+FE19 |
| ideographic comma and full stop | U+FE11, U+FE12 |
| the CJK brackets U+3008 to U+3011, U+3014 to U+3017 | U+FE3F to U+FE44, U+FE3B, U+FE3C, U+FE39, U+FE3A, U+FE17, U+FE18 |
| wavy low line, fullwidth low line | U+FE34, U+FE33 |
| fullwidth ! , : ; ? | U+FE15, U+FE10, U+FE13, U+FE14, U+FE16 |
| fullwidth ( ) [ ] { } | U+FE35 to U+FE38, U+FE47, U+FE48 |

Nothing in ASCII is on the list: `(` stays `(`, because in vertical CJK layout it is usually set sideways, in a run of its own. `novert.ttf` is the test font without `vert`, and like all four fonts it maps the presentation forms:

```shape
novert.ttf  水、「水」。  --direction=ttb  --language=ja
vertical.ttf  水、「水」。  --direction=ttb  --language=ja
vertical.ttf  水、「水」。  --direction=ttb  --language=ja  --features=-vert
novert.ttf  (…)  --direction=ttb  --language=ja
```

The font with `vert` uses its own alternates, `ideocomma.vert` and the rest, even though it maps the presentation forms too: `vert` wins. Turned off, it gives way to the fallback. The trace of `novert.ttf` shows the characters already replaced when normalization starts:

```trace
font: novert.ttf
text: 水、「水」。
options: --direction=ttb --language=ja
from: start decompose
to: end decompose
```

The fallback is the only part of the presentation forms HarfBuzz knows. It never maps them back: text that contains U+FE11 itself is shaped as U+FE11, in either direction.

> For type designers: a CJK font with a `vert` feature gets its own vertical alternates and nothing else, whichever script lists `vert`. A font without one gets the Unicode presentation forms, if it maps them, for these 34 characters only. Glyphs that `vert` would change but that aren’t on the list, such as small kana, stay as they are.

## Shaping the column

### Which shaper

The script shaper is chosen with the direction in hand. Arabic and Syriac get the default shaper in vertical text, because “Arabic shaping is applicable only to horizontal layout” (`hb-ot-shaper.hh:195`; [Choosing a script shaper](choosing-a-script-shaper.html#arabic-and-syriac)). No other script’s choice depends on the direction: Mongolian, which is written in columns, gets the same shaper either way ([The Universal Shaping Engine](the-universal-shaping-engine.html)).

A font with a `morx` table is shaped with it in vertical text only if it has no GSUB (`hb-ot-shape.cc:64`, HarfBuzz issue #2124). In horizontal text `morx` is preferred whenever it is there ([AAT inside HarfBuzz](aat-inside-harfbuzz.html)).

### Advances and origins

In step 15 each glyph gets its vertical advance and an offset that is its vertical origin, negated (`hb-ot-shape.cc:1019`): `0,-1000` and −500, −880 for every full-width glyph in the test fonts, −250, −880 for the 500-unit `a`. From then on, offsets carry the origin with them. GPOS works on top of these offsets, not in place of them. Nothing adds the origins back afterwards, so an application draws each glyph at the pen position plus its offset, just as in horizontal text, and moves the pen down by the advance.

### Value records

GPOS value records have an advance for each direction. `apply_value` uses `xAdvance` only in horizontal text and `yAdvance` only in vertical, and negates `yAdvance`, “y_advance values grow downward but font-space grows upward” (`ValueFormat.hh:115`). Placements apply in both. So the `vkrn` value above, `<0 0 0 -300>`, made the full stop’s advance −700 instead of −1,000, and the `vpal` value `<0 250 0 -500>` moved the comma up 250 and halved its advance. A `kern` pair written with only an x advance does nothing in a column, even when an application asks for `kern`, though a `liga` asked for applies as usual:

```shape
vertical.ttf  ab  --direction=ttb  --language=en  --features=kern
vertical.ttf  ab  --direction=ttb  --language=en  --features=kern,liga
```

### Marks

Anchors are in the glyph’s own coordinates, measured from its horizontal origin, in both directions. The vertical origin doesn’t enter into them. `vertical.fea` attaches the combining voiced sound mark U+3099 to the top right of か:

```fea
markClass dakuten <anchor 150 800> @TOP_RIGHT;
feature mark {
  pos base ka <anchor 950 850> mark @TOP_RIGHT;
} mark;
```

The font has no glyph for the precomposed が, so normalization decomposes it, and either spelling gives the same result:

```shape
vertical.ttf  か\u3099  --direction=ttb  --language=ja
vertical.ttf  が  --direction=ttb  --language=ja
vertical.ttf  が  --direction=ltr  --language=ja
```

When the mark attaches, its offset is set to the distance between the anchors, 800 across and 50 up. Across the column, the base’s offset is added at once: in vertical text that is x, so the mark’s x offset becomes 800 − 500 = 300 (`MarkArray.hh:76`). Along the column, the base’s y offset, −880, is added when attachments are resolved after GPOS, and the advances from the base to the mark are subtracted: the base’s −1,000 (`GPOS.hh:113`). 50 − 880 + 1,000 = 170. It is the same arithmetic as in horizontal text with x and y exchanged, and it puts the two anchors on the same point.

The mark’s advance is zero, although `vmtx` gives it 1,000. The default shaper zeroes the advances of GDEF marks after GPOS, and `zero_mark_width` clears both advances, whatever the direction (`hb-ot-shape.cc:978`). When a font has no GPOS, the mark’s offset is moved back by the advance it had, in y as well as x, so that it hangs over the glyph before it ([Fallbacks](fallbacks.html)).

### Cursive chains

`curs` is one of the horizontal features, so a vertical run doesn’t ask for it. An application that has a font with vertical cursive attachment has to turn it on. The test font’s chain links `l`s from an entry at the top to an exit at the bottom, 200 units to the right:

```fea
feature curs {
  pos cursive l <anchor 400 830> <anchor 600 -70>;
} curs;
```

```shape
vertical.ttf  lll  --direction=ttb  --language=en
vertical.ttf  lll  --direction=ttb  --language=en  --features=curs
```

`apply_cursive_attachment` works along the column as it does along a line, with y for x (`CursivePosFormat1.hh:143`). The first glyph’s advance becomes the distance from its origin down to its exit: −70 plus its y offset of −880, so −950. The second is moved up by its entry’s distance above the origin, 830 − 880 = −50, and its advance shortened to match. Across the column, each child is moved sideways so its entry meets its parent’s exit: the x offset of each `l` is 200 more than the one before.

The function has a branch for each of the four directions, and the bottom-to-top branch is never used: by the time GPOS runs, a bottom-to-top run has become top to bottom. Shaped bottom to top, the chain comes out exactly as the top-to-bottom one, with its clusters numbered from the other end:

```shape
vertical.ttf  lll  --direction=btt  --language=en  --features=curs
```

The unused branch also differs from the others (`CursivePosFormat1.hh:155`, trimmed):

```c++
case HB_DIRECTION_TTB:
  pos[i].y_advance = hb_saturate_add ((hb_position_t) roundf (exit_y), pos[i].y_offset);
  ...
case HB_DIRECTION_BTT:
  ...
  pos[j].y_advance = (hb_position_t) roundf (entry_y);
```

In the other three directions, the advance set from an anchor includes the glyph’s offset along the line, which in vertical text is its origin. Here it doesn’t. If the branch were ever reached, the advance would be wrong by the glyph’s vertical origin. It can’t be reached through `hb_shape`, so it changes nothing today.

## Compiled out

`HB_NO_VERTICAL` removes the vertical support from the font side: the `vhea`, `vmtx` and `VORG` slots on the face ([Blobs, faces and lazy tables](blobs-faces-and-lazy-tables.html)), hb-ot’s vertical advance, origin and font-extents functions, the vertical phantom points of `glyf`, and the presentation-form fallback. `HB_LEAN` sets it. Vertical runs still shape: the planning and positioning above don’t depend on it, and the font object answers for the missing functions with its own defaults ([Fonts and font functions](fonts-and-font-functions.html#the-nil-tier-and-the-default-tier)). Inside `apply_value` it makes every run count as horizontal, so in a column `yAdvance` is ignored and `xAdvance` applied (`ValueFormat.hh:98`).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-common.h` | `hb_direction_t` and the `HB_DIRECTION_IS_*` and `HB_DIRECTION_REVERSE` macros |
| `src/hb-ot-shape.cc` | the vertical feature list and `has_vert`; `hb_ensure_native_direction`; `hb_ot_rotate_chars`; vertical advances and origins in `hb_ot_position_default`; mark zeroing; `_hb_apply_morx` |
| `src/hb-ot-map.cc` | `F_GLOBAL_SEARCH` |
| `src/hb-unicode.hh` | `vertical_char_for` |
| `src/hb-ot-shaper.hh` | Arabic and Syriac falling back to the default shaper |
| `src/hb-font.hh` | adding and subtracting vertical origins, with the font object’s fallbacks |
| `src/OT/Layout/GPOS/ValueFormat.hh` | `yAdvance` and its sign |
| `src/OT/Layout/GPOS/MarkArray.hh`, `GPOS.hh` | marks across and along a vertical line |
| `src/OT/Layout/GPOS/CursivePosFormat1.hh` | cursive chains in TTB and BTT |
| `src/hb-ot-font.cc` | hb-ot’s vertical metrics ([Where metrics come from](where-metrics-come-from.html)) |

## In short

* HarfBuzz shapes a vertical run with every glyph upright. Deciding what is set sideways, and shaping it horizontally to be rotated, is the application’s work.
* Bottom-to-top text is reversed and shaped as top to bottom, and comes out in top-to-bottom order. Its brackets are mirrored on the way in.
* A vertical run gets the common features and `vert`, and none of `liga`, `kern`, `calt`, `curs` and the rest. `vkrn`, `vpal`, `vhal`, `valt` and `vrt2` are off unless asked for.
* `vert` is found under any script if the chosen one lacks it.
* Without `vert`, 34 punctuation characters are replaced by their Unicode vertical presentation forms, if the font maps them.
* Advances are negative y; offsets start as the negated vertical origin and stay that way through GPOS. `yAdvance` is negated, `xAdvance` ignored.
* Marks and cursive chains work as in horizontal text with x and y exchanged.
