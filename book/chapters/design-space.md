# Design space

A variable font is one set of outlines together with instructions for changing them. Where a static font has one weight, a variable font has a **weight axis**, and any position along it, not only the weights the designer drew, is a font. With two axes, weight and width say, every point in a rectangle is a font. That rectangle, or box, or higher-dimensional block, is the font’s **design space**.

Every other chapter in this part is about what happens at a position in the design space: how deltas are found and added to advances, metrics, and outlines. This one is about the position itself: how the numbers an application asks for, like `wght=700`, become the coordinates that the rest of HarfBuzz reads. That takes three tables and three number formats, and it’s where HarfBuzz departs from the specification more often than almost anywhere else in its variation code.

The examples use a small family of test fonts, built for this part of the book in `fonts/variations/` by `tools/build-var-test-fonts.py`. Like a real variable font, they’re made from static masters combined by fontTools’ varLib. They have a weight axis and a width axis, and three glyphs whose shapes make their coordinates easy to read: `I` is one stem, as wide as the weight says; `H` has two stems and a bar, and gets narrower along the width axis; `V` is a stem whose right edge leans as the weight grows.

```draw
font: variations/var.ttf
text: IHV
slider: wght 100 900 25
start: 400
```

Under each drawing is what `hb-shape` says about the same text at the same position: glyph names, clusters, and advances. The advances are the easiest place to watch a position take effect. `I`’s advance is its stem plus 160 units of side bearing.

## Axes: fvar

The axes are listed in the `fvar` table. Each has a tag, a minimum, a default, and a maximum, in **user coordinates**: the numbers people use, like 400 for a regular weight, or 75 for a width that is 75% of normal.

```table
font: variations/var.ttf
table: fvar
```

```info
variations/var.ttf  --list-variations
```

(“Varitation” is a typo in `hb-info`, at `util/hb-info.cc:1190`.) The table also lists **named instances**, positions the designer has given names to. They come later in this chapter.

An axis has a flag, too. `AXIS_FLAG_HIDDEN` (`hb-ot-var-fvar-table.hh:159`) says that an application shouldn’t show the axis to users. HarfBuzz reports the flag and otherwise ignores it: a hidden axis can be set like any other.

## From user coordinates to normalized ones

User coordinates are convenient for people and awkward for arithmetic, since every axis has its own range. So before any deltas are applied, each coordinate is **normalized**: mapped to −1 at the axis minimum, 0 at the default, and +1 at the maximum, in a straight line on each side of the default. Weight 100 becomes −1, 400 becomes 0, 650 becomes 0.5, and 900 becomes 1. Everything else in a variable font, every region and every delta, is written in terms of normalized coordinates.

The whole conversion is one short function, `hb_ot_var_normalize_coords` (`hb-ot-var.cc:323`):

```c++
for (unsigned int i = 0; i < coords_length; i++)
  normalized_coords[i] = roundf (fvar.normalize_axis_value (i, design_coords[i]) * 65536.0f);

face->table.avar->map_coords_16_16 (normalized_coords, coords_length);

// Round to 2.14
for (unsigned i = 0; i < coords_length; i++)
  normalized_coords[i] = (normalized_coords[i] + 2) >> 2;
```

There are three steps: normalize each axis with fvar; let the `avar` table bend the result; round. And three number formats along the way:

* The user’s value is a `float`, and so is fvar’s arithmetic. `normalize_axis_value` (`hb-ot-var-fvar-table.hh:185`) clamps the value to the axis range and divides by the distance from the default to the minimum or the maximum.
* The result is stored in **16.16** fixed point, a 32-bit integer with 16 bits after the binary point, and avar works in that.
* The final coordinates are **2.14**, a 16-bit integer with 14 bits after the point, the format every variation table uses. Normalized coordinate 0.5 is stored as 8192, and 1 as 16384. `(v + 2) >> 2` drops two bits, rounding halves upwards.

The specification describes the same steps, but asks for the normalization itself to be done in 16.16 arithmetic from a 16.16 input. HarfBuzz divides in floating point and rounds the result. The two can differ by one unit of 16.16, which only rarely survives the final rounding to 2.14.

Clamping means a value outside the axis has no further effect. A weight of 2000 is a weight of 900:

```shape
variations/var.ttf  IHV  --variations=wght=900
variations/var.ttf  IHV  --variations=wght=2000
```

There is one more quiet repair. The specification assumes that an axis’s minimum is no greater than its default, and its default no greater than its maximum, but doesn’t say what to do if they aren’t. HarfBuzz fixes them up when it reads them, in `get_coordinates` (`hb-ot-var-fvar-table.hh:208`): a minimum above the default is treated as the default, and so is a maximum below it. The comment says it’s to “simplify client math”. The repaired values are also what `hb_ot_var_get_axis_infos` reports, so an application never sees the font’s real minimum and maximum if they’re out of order.

## Bending an axis: avar

A straight line from the default to each end is rarely what a designer wants. On a weight axis, the step from 400 to 500 might need to be smaller than the step from 800 to 900, or the designer may want the user’s 600 to be the design they drew at 750. The `avar` table bends each axis. For each axis it gives a **segment map**: pairs of normalized coordinates, from and to, with straight lines between them.

The test font `var-avar.ttf` is `var.ttf` with one segment map added, built from a designspace that says user weight 600 is design weight 750:

```table
font: variations/var-avar.ttf
table: avar
```

In normalized coordinates that’s 0.4 to 0.7: halfway between 0 and 0.4 becomes halfway between 0 and 0.7, and so on. The two fonts agree at the default and at the ends, and disagree in between:

```shape
variations/var.ttf  I  --variations=wght=600
variations/var-avar.ttf  I  --variations=wght=600
variations/var.ttf  I  --variations=wght=750
variations/var.ttf  I  --variations=wght=900
variations/var-avar.ttf  I  --variations=wght=900
```

At 600, `var-avar.ttf` gives the stem that `var.ttf` gives at 750. <span class="screen-only">Drag the slider here and compare it with the one at the top of the chapter:</span><span class="print-only">Compare the frames at 600 here with those at the top of the chapter:</span> this axis gets heavy sooner.

```draw
font: variations/var-avar.ttf
text: IHV
slider: wght 100 900 25
start: 400
print: 100 400 600 900
```

### A more forgiving avar than the specification’s

The specification is strict about segment maps. Each must map −1 to −1, 0 to 0, and +1 to +1, and a map that doesn’t is to be ignored: “no modification” for that axis. Its from-coordinates must increase. And the result is clamped to the range −1 to +1.

HarfBuzz does something else, and says so. The comment in `SegmentMaps::map_float` (`hb-ot-var-avar-table.hh:152`) reads: “Core Text is wild... PingFangUI avar needs all this special-casing... So we implement an extended version of the spec here, which is more robust and more likely to be compatible with the wild.” What it implements:

* A map with no pairs leaves the axis alone. A map with one pair shifts the whole axis by that pair’s difference.
* If the first pair is −1→−1 and the next pair also starts at −1, the first is skipped. That’s the PingFang case: a font that maps −1 to −1 and then −1 to −0.5 means that −1 goes to −0.5. The same goes for +1 at the other end.
* If several pairs share a from-coordinate, one of them is chosen: the middle of three, the last of a run below 0, the first above 0. At 0 itself, the one whose result is nearer 0, and on a tie the later one. (The comment there says “So we’ll just return the smallest one. lol”, and it is followed by four lines that can never run: the function has already returned.)
* A value before the first pair or after the last is *shifted* by that pair’s difference, not clamped.
* Otherwise, HarfBuzz interpolates between the two pairs on either side, whether or not the map follows the rules.

Nothing on this path clamps. With a malformed map, a coordinate can end up beyond ±1, and even the default can be mapped away from 0. In other words, a broken avar is used rather than ignored, and it is used the way Core Text uses it, so that a font looks the same in HarfBuzz as on Apple’s systems. That’s a choice of compatibility over the letter of the specification, and it’s typical of HarfBuzz.

### avar version 2

Version 1 bends each axis on its own. **Version 2** lets an axis’s final position depend on all the others. A width axis can make narrow designs lighter, so that stems don’t clog as letters get narrower; an optical size axis can drive weight and contrast together; and a font can have “parametric” axes, hidden from users, that the visible axes move in combination.

After its segment maps, a version 2 table has two more things: an **item variation store**, the same structure that holds advance and metric deltas (the subject of [the next chapter](deltas.html)), and an index map that says which entry in the store belongs to each axis. The store’s regions are written in normalized coordinates, so the deltas it gives can depend on any axis.

`var-avar2.ttf` maps every weight lighter at the narrowest width, in a designspace “mapping” from (wght 400, wdth 75) to (wght 300, wdth 75), and the same for the other weights:

```table
font: variations/var-avar2.ttf
table: avar
```

```shape
variations/var.ttf  IHV  --variations=wdth=75
variations/var-avar2.ttf  IHV  --variations=wdth=75
variations/var.ttf  IHV  --variations=wght=900,wdth=75
variations/var-avar2.ttf  IHV  --variations=wght=900,wdth=75
```

Nothing has changed except the width, but `I`, whose stem only follows the weight, is thinner. <span class="screen-only">Here the slider moves the width:</span><span class="print-only">Here the width changes, from 75 to 100:</span>

```draw
font: variations/var-avar2.ttf
text: IHV
variations: wght=900
slider: wdth 75 100 5
start: 100
print: 75 85 100
```

The order of operations is in the second half of `map_coords_16_16` (`hb-ot-var-avar-table.hh:545`):

```c++
hb_vector_t<int> coords_2_14;
coords_2_14.resize (coords_length);
for (unsigned i = 0; i < coords_length; i++)
  coords_2_14[i] = roundf (coords[i] / 4.f); // 16.16 -> 2.14

hb_vector_t<int> out;
out.alloc (coords_length);
for (unsigned i = 0; i < coords_length; i++)
{
  int v = coords[i];
  uint32_t varidx = varidx_map.map (i);
  float delta = var_store.get_delta (varidx, coords_2_14.arrayZ, coords_2_14.length, var_store_cache);
  float d = hb_clamp (delta * 4, -(float) (1<<17), +(float) (1<<17)); // 2.14 -> 16.16
  v += (int) roundf (d);
  v = hb_clamp (v, -(1<<16), +(1<<16));
  out.push (v);
}
```

First every axis goes through its version 1 segment map. Then the store is evaluated once, at those results rounded to 2.14, and each axis’s delta is added to its *unrounded* 16.16 value. Only the sum is clamped, to ±1, “matching fontTools”, as the comment above the clamp says. The results go into a separate array, so no axis sees another’s version 2 result: there is one pass, not an iteration until things settle.

For years the only description of avar 2 was a proposal, and HarfBuzz’s comment still points to it: `/* "Spec": https://github.com/be-fonts/boring-expansion-spec/issues/14 */` (`hb-ot-var-avar-table.hh:46`). Microsoft’s OpenType 1.9.1 still has only version 1. The 2026 edition of the ISO standard, ISO/IEC 14496-22, describes version 2 in clause 7.3.1, and HarfBuzz differs from it in three small ways:

* The standard adds each delta to the version 1 result already rounded to 2.14. HarfBuzz adds it to the 16.16 value and rounds once, at the end. The two can differ by one unit of 2.14.
* The standard clamps only when there is a variation store. HarfBuzz’s version 2 path always clamps, store or not.
* The standard requires avar to have as many segment maps as fvar has axes. HarfBuzz doesn’t check, for either version: it maps as many axes as both tables have.

There is also a second implementation in the same file, `map_coords_2_14` (`hb-ot-var-avar-table.hh:625`), which rounds to 2.14 before adding the deltas, and has a comment to deprecate it “once fonttools is updated to use 16.16 normalization”. Only the subsetter uses it, when instancing. So the subsetter and the shaper can put the same user position one 2.14 unit apart.

## Named instances

A named instance is a position in the design space with a name, like “Bold”, for menus. `fvar` stores a name ID and a full set of user coordinates for each, and, if its records are long enough, a PostScript name ID (`get_instance_postscript_name_id`, `hb-ot-var-fvar-table.hh`). The test font has four: Light, Regular, Bold, and Narrow.

```shape
variations/var.ttf  IHV  --named-instance=2
variations/var.ttf  IHV  --variations=wght=700
```

Choosing an instance doesn’t only set a position. HarfBuzz *remembers* the choice, and later settings are made on top of it. Here is `hb_font_set_variations` (`hb-font.cc:3099`), which is what `--variations` calls:

```c++
/* Initialize design coords. */
for (unsigned int i = 0; i < coords_length; i++)
  design_coords[i] = axes[i].get_default ();
if (font->instance_index != HB_FONT_NO_VAR_NAMED_INSTANCE)
{
  unsigned count = coords_length;
  /* This may fail if index is out-of-range;
   * That's why we initialize design_coords from fvar above
   * unconditionally. */
  hb_ot_var_named_instance_get_design_coords (font->face, font->instance_index,
                                              &count, design_coords);
}

for (unsigned int i = 0; i < variations_length; i++)
{
  const auto tag = variations[i].tag;
  const auto v = variations[i].value;
  for (unsigned axis_index = 0; axis_index < coords_length; axis_index++)
    if (axes[axis_index].axisTag == tag)
      design_coords[axis_index] = v;
}
```

Axes start at their defaults, then take the named instance’s values if one has been chosen, then the values asked for. So asking the Bold instance for a narrower width keeps its weight:

```shape
variations/var.ttf  IHV  --named-instance=2  --variations=wdth=75
variations/var.ttf  IHV  --variations=wght=700,wdth=75
variations/var.ttf  IHV  --variations=wdth=75
```

That’s useful, but the documentation above the function says something else: “Axes not included in @variations will be effectively set to their default values.” That’s only true when no instance has been chosen. Two more details of the same kind:

* `hb_font_set_var_named_instance` (`hb-font.cc:3272`) returns at once if the index is the one already chosen, even if the coordinates have been changed since. Choosing Bold, then setting some other weight, then choosing Bold again leaves the other weight in place.
* The loop above sets *every* axis with a matching tag. The ISO standard now allows a font to have several axes with one tag, to be moved together, and this is what it asks for. But `hb_ot_var_normalize_variations` (`hb-ot-var.cc:274`), the face-level version, sets only the first.

The 2026 ISO standard also gives instances a flag, `REPRESENTATIVE_INSTANCE`, meaning that this instance’s values should stand in for the defaults of axes the user hasn’t set. HarfBuzz doesn’t read it. Its struct still describes the field as “Reserved for future use — set to 0” (`hb-ot-var-fvar-table.hh:142`).

## Five ways to set a position

The public API has five functions for choosing a position, and they don’t all go through the steps above:

| Function | Starts from | fvar and avar | Notes |
|---|---|---|---|
| `hb_font_set_variations` | defaults, then the chosen named instance | yes | the usual way; `--variations` in the tools |
| `hb_font_set_variation` | the font’s current design coordinates | yes | changes one axis |
| `hb_font_set_var_coords_design` | defaults | yes | a full array of user coordinates; ignores the named instance |
| `hb_font_set_var_named_instance` | defaults | yes | then calls `hb_font_set_variations` with nothing |
| `hb_font_set_var_coords_normalized` | zeros | **no** | final 2.14 values, used as given |

The last one is for callers that have done the normalization themselves. It applies no avar, so a version 2 font loses its cross-axis effects, and no clamping, so out-of-range values pass straight through. It doesn’t know what user coordinates those values came from, so it sets the font’s design coordinates to NaN, “not a number”, as the documentation of `hb_font_get_var_coords_design` admits. That has a consequence the documentation doesn’t mention: a later `hb_font_set_variation` starts from those NaN values, and clamping NaN to an axis gives its minimum, since `hb_max` compares with `>=`. So setting one axis after setting normalized coordinates sends every other axis to its minimum.

## What the rest of HarfBuzz sees

All five functions end in `_hb_font_adopt_var_coords` (`hb-font.cc:2166`):

```c++
font->coords = coords;
font->design_coords = design_coords;
font->num_coords = coords_length;
font->has_nonzero_coords = hb_any (hb_array (coords, coords_length));

font->changed ();
font->serial_coords = font->serial;
```

The normalized 2.14 coordinates are the only thing the variation code reads: gvar for outlines, HVAR and VVAR for advances, MVAR for metrics, GDEF and GPOS device tables, CFF2 blends, COLRv1 paints, VARC, and FeatureVariations, which chooses different GSUB and GPOS lookups at different positions. The design coordinates are kept only to be handed back to the caller, and to FreeType when the FreeType font functions are in use.

`has_nonzero_coords` is HarfBuzz’s test for “the default instance”, and it saves work everywhere. A font at its default, whether or not any variations were set, takes the same paths as a static font: advances straight from `hmtx`, no deltas computed. It is also why shape plans don’t multiply. `hb_shape_full` passes the coordinates to the shape-plan cache only when they aren’t all zero (`hb-shape.cc:143`), and even then the cache’s key doesn’t hold them: it holds which FeatureVariations records they select, so every position that selects the same records shares a plan ([Shape plans and their cache](shape-plans-and-their-cache.html)). (A broken avar that maps the default away from 0 turns all of this off, as well as moving the default.)

Last, the two serial numbers. Every change to a font bumps `serial`, and a change of position also sets `serial_coords`. HarfBuzz’s own font functions keep caches of advances and outlines, and they check `serial_coords` to know when to throw them away (`hb-ot-font.cc:290`). A change of size alone keeps the advance cache, because the cached advances are in font units, before scaling.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-font.cc` | the five setters, from 3099; `_hb_font_adopt_var_coords`, 2166 |
| `src/hb-ot-var.cc` | `hb_ot_var_normalize_coords`, 323, and the face-level API |
| `src/hb-ot-var-fvar-table.hh` | axes, instances, `normalize_axis_value`, `get_coordinates` |
| `src/hb-ot-var-avar-table.hh` | segment maps and `map_float`, 152; version 2 in `map_coords_16_16`, 545; the instancer’s `map_coords_2_14`, 625 |

## In short

* User coordinates are normalized per axis to −1, 0, and +1, bent by avar, and rounded to 2.14. Normalization is done in floating point, avar in 16.16.
* HarfBuzz clamps to the axis range, repairs axes whose minimum or maximum is on the wrong side of the default, and uses malformed avar maps the way Core Text does, without clamping.
* avar version 2 adds deltas from an item variation store, evaluated once at the version 1 results, so any axis can depend on all of them. It’s in the 2026 ISO standard, not in Microsoft’s OpenType 1.9.1.
* A chosen named instance becomes the base for later settings, whatever the documentation says.
* Setting normalized coordinates directly skips avar and clamping.
