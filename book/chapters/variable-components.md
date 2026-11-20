# VARC: variable components

A CJK font has tens of thousands of glyphs, but far fewer distinct parts: the same radicals and strokes appear again and again, in different sizes and positions, and often slightly reshaped to fit. A TrueType composite glyph can reuse a part, but only as it is, moved and perhaps scaled. **VARC**, the variable composites table, lets a glyph be built from components that are each placed with a full transform, rotation and skew included, and each drawn at *its own* position in the design space. A component can be bolder, narrower, or bent differently from the glyph it’s part of, and it can have axes of its own that no user ever sees.

VARC came out of the “boring expansion” work on OpenType, and HarfBuzz’s code still points there: `VARC -- Variable Composites` / `https://github.com/harfbuzz/boring-expansion-spec/blob/main/VARC.md` (`OT/Var/VARC/VARC.hh:19`). It is now part of the 2026 ISO standard, in clause 7.3.10, but not of Microsoft’s OpenType 1.9.1. HarfBuzz 6.0.0 had an experimental first form of it, “Variable Composites” inside `glyf`, with a Hangul test font that NEWS says came out “over 90% smaller” than its ordinary OpenType equivalent. 9.0.0 replaced that with VARC, still experimental, and 12.0.0 turned it on by default. It can be turned off with `HB_NO_VAR_COMPOSITES`.

The examples use test fonts from HarfBuzz’s own test suite. The drawings and shaping results are HarfBuzz’s; the decoded tables are not, but come from `fonts/variable-components/varc-dump.py`, which reads the bytes in HarfBuzz’s order, with help from fontTools.

## Why not composite glyphs?

A TrueType [composite glyph](drawing-outlines.html#composite-glyphs) is a list of other glyphs, each with an offset and, optionally, a scale or a 2×2 matrix. That is enough for an accent over a letter. For the parts of a CJK character it falls short in two ways:

* **Only the offset can vary.** Under gvar, each component of a composite counts as one point, its offset ([Varying outlines](varying-outlines.html#composites)). Nothing varies its scale or matrix, so a part can’t get wider, or turn further, as the weight changes.
* **The component is drawn where the composite is.** At weight 600, a composite’s components are at weight 600 too. The ㄱ of 가 shares its width with ㅏ; the ㄱ of 고 has the whole width. To composites, those are two glyphs, and the font must store both, and every other shape of ㄱ it needs.

VARC removes both limits. A component’s transform is stored as separate numbers (translation, rotation, scales, skews, and a center), each of which can vary. And each component sets some axes to values of its own, which can vary too, to say where in the design space its glyph is drawn. So a font stores each part once, as a small variable glyph whose axes are the ways it can change, and each glyph that uses it says where on those axes to draw it.

> For type designers: HarfBuzz’s NEWS for 12.0.0 compares VARC to the “smart components” some font editors offer. Without VARC, a compiled font can hold them only as plain outlines or composites.

## A glyph made of variable parts

`varc-ac00-ac01.ttf` has two Hangul syllables, 가 and 각, built from components. Its `fvar` has eight axes: the weight and optical size that a user sees, and six more, `0000` to `0005`, which exist only for the components to use.

```info
hb:test/api/fonts/varc-ac00-ac01.ttf  --list-variations
```

```draw
font: hb:test/api/fonts/varc-ac00-ac01.ttf
text: 가각
slider: wght 356.5 840.3 24.19
start: 356.5
print: 356.5 598.4 840.3
```

As the weight changes, the components move and reshape: each is drawn at its own coordinates, which VARC works out from the glyph’s.

### Inside 가

가 is glyph 1. Here is what VARC says about it at weight 598.4, normalized 0.5, as `varc-dump.py` works it out:

```
glyph 1, at: wght 0.5
  component 0: glyph 3
    glyph 3, at: wght 0.5
      component 0: glyph 4
        axis-value deltas, region 0 (wght 0…1…1), scalar 0.5: [0, -327, 0]
        axis values (2.14): 0000 -4227, 0001 819 - 163.5 = 655.5 → 656, 0002 -8484
        transform: translateX -10, translateY 24
        leaf: glyph 4, drawn from glyf at: wght 0.5, 0000 -0.258, 0001 0.04004, 0002 -0.5178
              through the matrix (1, 0, 0, 1) and offset (-10, 24)
  component 1: glyph 5
    glyph 5, at: wght 0.5
      component 0: glyph 6
        axis values (2.14): 0002 3537
        transform: translateX -13
        leaf: glyph 6, drawn from glyf at: wght 0.5, 0002 0.2159
              through the matrix (1, 0, 0, 1) and offset (-13, 0)
```

가’s components, glyphs 3 and 5, are the jamo ㄱ and ㅏ. They set nothing themselves: they are VARC glyphs too, and their own components draw glyphs 4 and 6, plain `glyf` outlines with gvar variations, with axes set and small offsets. Here are the jamo on their own, then 가:

```draw
font: hb:test/api/fonts/varc-ac00-ac01.ttf
text: gid3|gid5|gid1
options: --glyphs
variations: wght=598.4
```

Glyph 4 is a ㄱ designed to be reshaped. With its axes at their defaults it is wide; at the coordinates 가’s component gives it, it is 가’s narrower ㄱ:

```draw
font: hb:test/api/fonts/varc-ac00-ac01.ttf
text: gid4
options: --glyphs
at: wght=598.4; wght=598.4,0000=-0.258,0001=0.04004,0002=-0.5178
```

Its axes are the ways it can change. Here it is at the font’s defaults, then with each of the three axes 가 sets pushed to its end:

```draw
font: hb:test/api/fonts/varc-ac00-ac01.ttf
text: gid4
options: --glyphs
at: 0000=0; 0002=-1; 0000=-1; 0001=1
```

`0002` narrows the ㄱ, `0000` shortens its downstroke, and `0001` straightens it. 가 asks for half the narrowing and a quarter of the shortening; 각, which needs room for a final ㄱ underneath, sets `0000` to −0.54. One outline serves both.

> For type designers: this font’s part axes are ordinary `fvar` axes, with no hidden flag, so an application could offer them to users, and setting `0003`, which 가’s ㄱ doesn’t set, changes 가. A font needn’t expose them; see [Hidden axes](#hidden-axes).

## How HarfBuzz draws a VARC glyph

VARC comes first. When HarfBuzz’s font functions draw a glyph, they try VARC before any outline format (`hb-ot-font.cc:931`):

```c++
#ifndef HB_NO_VAR_COMPOSITES
  if (font->face->table.VARC->get_path (font, glyph, draw_session)) return true;
#endif
  // Keep the following in synch with VARC::get_path_at()
  if (font->face->table.glyf->get_path (font, glyph, draw_session, gvar_cache,
                                       &draw_session.get_budget ())) return true;
```

A glyph that VARC covers is drawn from VARC, whatever `glyf` or CFF has for it. A glyph it doesn’t cover falls through to the usual formats. Extents are worked out the same way, after the color and bitmap tables.

A VARC glyph is a list of **components**. Each is a packed record (`VarComponent::decompile_record`, `OT/Var/VARC/VARC.cc:31`): flags, a glyph ID, and only the fields the flags say are there:

* a **condition**, which decides whether the component is drawn at all;
* **axis values**: settings for some of the axes, to draw the component at;
* indices into VARC’s own variation store, for variations of those values and of the transform;
* a **transform**: translation, rotation, scale, skew, and a center for rotating and scaling around.

`VarComponent::get_path_at` (`VARC.cc:367`) takes a component through six steps. Here they are for glyph 3’s component, 가’s ㄱ, at weight 598.4.

### Step 1: the parent’s coordinates

`get_path_at` is handed `coords`, the normalized position of the glyph the component belongs to, its **parent**: the font’s position for a glyph in the text, or whatever the level above worked out. 가 sets no axes for glyph 3, so glyph 3 is where 가 is: weight 0.5, everything else 0. The condition and all the deltas are evaluated there.

### Step 2: the condition

A condition is a small expression over the coordinates: an axis in a range, or a value from the variation store above zero, combined with *and*, *or*, and *not*. It is evaluated at the parent’s coordinates (`VARC.cc:400`), and a component whose condition is false isn’t drawn, so a glyph can change its structure, as a heavy weight might drop a stroke.

Glyph 3’s component has no condition. In `varc-ac01-conditional.ttf`, 각’s middle component is drawn only above a certain weight:

```draw
font: hb:test/api/fonts/varc-ac01-conditional.ttf
text: 각
at: wght=590; wght=610
```

Between weight 590 and 610, the glyph goes from two contours to four.

### Step 3: the axis values and their deltas

The component sets `0000`, `0001`, and `0002` to −4227, 819, and −8484 in 2.14 units: −0.258, 0.05, and −0.5178. Its flags say these vary, and give index 0 into the variation store, where the item has three numbers for each region (decoded by `varc-dump.py`, with fontTools reading the store):

```
── item 0:0 (VarIdx 0): 3 numbers for each of 3 regions
region 0 (wght 0…1…1): [0, -327, 0]
region 1 (opsz 0…1…1): [1704, 0, 0]
(and 1 more region, all 0)
```

Regions work as in [Deltas](deltas.html#regions-and-scalars). At the parent’s weight of 0.5, the weight region counts by half and the others not at all, so `0001` becomes 819 − 0.5 × 327 = 655.5. The code is one call, with the parent’s `coords` (`VARC.cc:407`, trimmed):

```c++
// Apply variations if any
if ((flags & (unsigned) flags_t::AXIS_VALUES_HAVE_VARIATION) &&
    show && !axisValues.in_error ())
{
  ...
  varStore.get_delta (component.axis_values_var_idx, coords,
                      axisValues.as_array (), cache);
}
```

One index gives deltas for all three values; [the multiple item variation store](#the-multiple-item-variation-store) explains how.

### Step 4: the component’s coordinates

Now the coordinates to draw the component at (`VARC.cc:417`, trimmed):

```c++
auto component_coords = coords;
/* Copying coords is expensive; so we have put an arbitrary
 * limit on the max number of coords for now. */
if ((flags & (unsigned) flags_t::RESET_UNSPECIFIED_AXES) ||
    coords.length > HB_VAR_COMPOSITE_MAX_AXES)
  component_coords = hb_array (c.font->coords, c.font->num_coords);
...
coord_setter_t coord_setter (axisIndices ? component_coords : hb_array<int> ());
for (unsigned i = 0; i < axisIndices.length; i++)
  coord_setter[axisIndices[i]] = hb_clamp_to<int> (round (axisValues[i]));
```

A component starts from its parent’s coordinates, or, with the `RESET_UNSPECIFIED_AXES` flag, from the font’s, as the user set them. Then it sets the axes it names, each rounded to a whole 2.14 unit. The ㄱ starts from weight 0.5 and will be drawn at weight 0.5, `0000` −0.258, `0001` 0.04004 (655.5 rounded to 656), and `0002` −0.5178. The weight passes through, so glyph 4’s own weight variations apply.

Three more things about this step:

* **Axes beyond fvar.** `coord_setter_t` (`OT/Var/VARC/coord-setter.hh`) grows its array when an axis past the end is set, and fills the gap with zeros. A component can set axis 17 in a font whose fvar has two, and its outline’s variations, in gvar or CFF2, can depend on that axis. Indices go up to 4095: `HB_VAR_COMPOSITE_MAX_AXES` is 4096 (`hb-limits.hh`), and the setter ignores any index past it.
* **No clamping.** Axis values are rounded but not clamped to ±1, so a component can be drawn outside the design space the font declares.
* **An undocumented limit.** Above 4096 incoming coordinates, the component resets to the font’s coordinates as if the flag were set. The comment presents it as a shortcut, to avoid copying, but it changes what is drawn.

### Step 5: the transform

The transform is stored as separate values, in fixed-point formats suited to each: translations in font units, rotation and skew in half-turns as 4.12 numbers, scales as 6.10. The ㄱ stores only a translation, (−10, 24), whose deltas are (0, 0) for weight and (0, 16) for optical size: it moves up with optical size, not weight.

With the deltas added and the values converted, the parts are put together in this order (`hb_transform_decomposed_t::to_transform`, `hb-geometry.hh:409`):

```c++
t.translate (translateX + tCenterX, translateY + tCenterY);
t.rotate (rotation);
t.scale (scaleX, scaleY);
t.skew (-skewX, skewY);
t.translate (-tCenterX, -tCenterY);
```

That is the standard’s pseudo-code exactly, negated horizontal skew included. Read upwards, it is what happens to a point: move the center to the origin, skew, scale, rotate, move back, and translate. A missing field is 0, or 1 for a scale, except that a horizontal scale with no vertical one is used for both (`VARC.cc:468`). The result is multiplied onto the levels above (`VARC.cc:475`); for the ㄱ, it is simply a move by (−10, 24).

`varc-6868.ttf`, a single Chinese character, 桨, uses much more: components rotated by 52°, 90°, and −231°, scaled unevenly, transformed about a center, and three levels deep, with 31 axes, 29 of them private:

```draw
font: hb:test/api/fonts/varc-6868.ttf
text: 桨
slider: wght 400 700 25
start: 400
print: 400 550 700
```

### Step 6: the leaf

Last, `VARC::get_path_at` is called for glyph 4, with the component’s coordinates and transform. VARC doesn’t cover glyph 4, so it is a **leaf**, drawn by `glyf`, CFF2, or CFF, in that order, through a pen that transforms every point. Drawn by `hb-vector` at step 4’s coordinates and moved by (−10, 24), glyph 4 lands on the ㄱ of `hb-vector`’s 가 to within a hundredth of a unit.

A leaf needn’t be a different glyph. `VARC::get_path_at` won’t recurse into the glyph it’s already drawing (`VARC.cc:499`):

```c++
// Don't recurse on the same glyph.
unsigned idx = glyph == parent_glyph ?
               NOT_COVERED :
               (this+coverage).get_coverage (glyph);
```

so a component that names its own glyph is drawn from `glyf` or CFF, as a leaf, and a VARC glyph can add components to its own outline, or draw it elsewhere in the design space. `varc-static-gvar.ttf` has no fvar at all, but its gvar has one axis. Its glyph `a` is a VARC glyph with one component: itself, with axis 0 set to 0.5. The `glyf` outline is a triangle from x = 0 to 400, which gvar moves 100 units right at axis 0 = 1. So VARC draws it 50 units right, while `b`, the same triangle without VARC, stays put:

```draw
font: hb:test/api/fonts/varc-static-gvar.ttf
text: ab
```

```shape
hb:test/api/fonts/varc-static-gvar.ttf  ab  --show-extents
```

### Two sets of coordinates

The condition and the deltas (steps 2, 3, and 5) are evaluated at the parent’s coordinates; the outline (step 6) is drawn at the component’s. That is on purpose. The deltas say how the parent wants its part placed and shaped as *the parent* changes; the component’s coordinates describe the part’s own shape, which knows nothing of where it’s used. It also lets a glyph’s components share one cache of region scalars (`VARC.cc:570`).

In 가 the two agree on everything the store’s regions use, weight and optical size. In 桨 they don’t. 桨’s third component is 木, glyph 7, and 木’s fifth is its stem: glyph 9, a plain 1000-unit square, scaled to a thin upright. At weight 700, `varc-dump.py` finds:

| Axis | 木’s coordinates: the stem’s deltas are evaluated here | The stem’s coordinates: its outline is drawn here |
|---|---|---|
| `wght` | 1 | 1 |
| `0000` | 0.081 | 0 |
| `0012`, `0014`, `0016`, `0017`, `0022` | 0.047, 0.216, 0.139, 0.542, 0.307 | 0 |
| `0018` | 0.420 | 0 |
| `0019` | 0.514 | 0 |
| `0020` | 0.060 | 0 |

The left column is what 桨 set for 木. On the right, the stem sets its four axes to 0 and, having `RESET_UNSPECIFIED_AXES`, takes the font’s coordinates for the rest. Its horizontal scale, stored as 72/1024, has deltas read from the left column; the one on `0018` adds 0.42 × 117, and the stem is 115 units wide, where at weight 400 it is 71. Its outline doesn’t change at all: it gets bolder because 木’s parameters say so.

### Recursion, and its limits

A component can itself be a VARC glyph, so drawing recurses, with each level’s transform applied after its parent’s. HarfBuzz bounds it in several ways: 64 levels deep, 16,384 component edges in all, a cycle detector, and the shared work budget that every drawing call has (see [Drawing outlines](drawing-outlines.html)). All of them fail quietly: drawing simply stops, and what has been drawn so far is the glyph. HarfBuzz never falls back to the glyph’s `glyf` outline instead.

## Hidden axes

A part has its own parameters. A stroke is curved or straight, tapered or blunt; a radical is tall or squat, its strokes heavy or light. They make sense only for that part, and there may be dozens: a designer doesn’t want them among the font’s axes, as sliders meaning nothing to a user. Each part should have them privately, and each glyph that uses it set them, so that the one 木 the font stores can be full height in one character and squat in another. Axes used this way are VARC’s **hidden axes**.

桨’s components are glyphs 2, 5, and 7: 夕, 丬, and 木. Each is a VARC glyph made of strokes, and the strokes are leaves, among them a straight bar 1,000 units long (glyphs 3 and 8) and the square (glyph 9). The parts on their own, at the font’s defaults, then 桨:

```draw
font: hb:test/api/fonts/varc-6868.ttf
text: gid2|gid5|gid7|gid1
options: --glyphs
```

In 桨, 木 sits under the other two and is squat, yet its component has no scale: it only moves 木 down 100 units. The squatness is 木’s axis `0019`, which 桨 sets to 0.494:

```draw
font: hb:test/api/fonts/varc-6868.ttf
text: gid7
options: --glyphs
at: 0019=0; 0019=0.25; 0019=0.494
```

The parameter lowers the crossbar and shortens the strokes, but leaves the crossbar and stem as thick as they were, which a vertical scale wouldn’t. Stroke weight is a parameter too: `0018`, which widened the stem above.

The leaves have parameters of their own. Glyph 3, the bar, has a dozen. Here it is at its default, then with `0000`, `0002`, and `0012` at 1:

```draw
font: hb:test/api/fonts/varc-6868.ttf
text: gid3
options: --glyphs
at: 0000=0; 0000=1; 0002=1; 0012=1
```

`0000` bends it, `0002` makes it an S, and `0012` thickens it. Each part uses the numbers as it likes: `0019`, 木’s squatness, is also one of the axes 桨 sets on 夕.

Like `varc-ac00-ac01.ttf`, this font lists its private axes in fvar, as `0000` to `0028`. A font can hide them completely: a component can set any axis index up to 4095, and gvar and CFF2 can vary on it, with no fvar entry. `varc-static-gvar.ttf` ([above](#step-6-the-leaf)) does just that.

avar version 2 has hidden axes too ([Design space](design-space.html#avar-version-2)), but they are fvar axes, usually flagged as hidden, that avar2 sets once for the whole font from the user’s axes: every glyph sees the same value. VARC’s are set per use: at one position, `0019` can be 0.494 for the 木 in 桨 and 0 for a 木 standing alone. avar2 builds a design space from parameters; VARC builds glyphs from parameterized parts.

### RESET_UNSPECIFIED_AXES

When the same axis number means different things in different parts, a part mustn’t inherit its parent’s settings. 桨 sets 木’s `0019` to 0.494; a stroke inside 木 that inherited it, and varied on its own `0019`, would change shape for no reason of its own. With `RESET_UNSPECIFIED_AXES`, the component starts from the font’s coordinates instead, and sets its own axes on top. Every component in `varc-6868.ttf` has the flag. Here is a copy made by `fonts/variable-components/no-reset.py`, with the flag cleared on the components of the three parts:

```draw
font: varc-6868-no-reset.ttf
text: 桨
at: wght=400; wght=700
```

The strokes now take 夕’s, 丬’s, and 木’s settings as their own, and bend, swell, and twist. Compare [the slider above](#step-5-the-transform).

The flag resets to the font’s coordinates, not to zero, so the component still follows the weight and any axis the user set; it drops only the parent’s own settings. Leaving it off is right when parent and part share an axis’s meaning, so that a setting should flow down: in `varc-ac00-ac01.ttf`, glyph 3 only wraps glyph 4, and a syllable that set `0003` on glyph 3 would reach glyph 4 through it.

## The multiple item variation store

VARC’s deltas come from a **multiple item variation store** (`hb-ot-layout-common.hh:3926`), a variant of the item variation store of HVAR, MVAR, and GDEF ([Deltas](deltas.html#item-variation-stores)), with two differences.

**Items are lists.** In the ordinary store, an item is one number, such as a glyph’s advance. Here it is a list: one for a component’s axis values, another for its transform. They vary together, over the same regions, so each region’s scalar is worked out once for the list. `MultiVarData::get_delta` (`hb-ot-layout-common.hh:3513`, trimmed) walks the regions, and for each either skips its numbers or adds them all in:

```c++
for (unsigned regionIndex = 0; regionIndex < regionCount; regionIndex++)
{
  float scalar = regions.evaluate (regionIndices.arrayZ[regionIndex],
                                   coords, coord_count,
                                   cache);
  // We skip lazily. Helps with the tail end.
  if (scalar == 0.0f)
    skip += out.length;
  else
  {
    ...
    values_iter.add_to (out, scalar);
  }
}
```

So the numbers are stored region by region. In an ordinary store, 木’s fourteen axis values would need fourteen items, fourteen indices, and fourteen lookups.

**Regions name only the axes they use.** An ordinary region has an entry for every fvar axis; here a region lists only its own, by index (`SparseVarRegionAxis`, `hb-ot-layout-common.hh:2653`). 桨’s 39 regions each name one or two of its 31 axes. A region that names no axes counts everywhere, with a scalar of 1, even at the default. That lets a static VARC font have “deltas” that are really constants, and it’s why `MultiItemVarStoreInstancer` applies deltas even when every coordinate is 0 (`hb-ot-layout-common.hh:4369`), which an ordinary store never does.

Here is the item for 木’s axis values in 桨, decoded by `varc-dump.py`. Each region has fourteen numbers, for `0000`, `0003`, `0005`, `0007`, `0011`, `0012`, `0014`, `0016`, `0017`, `0018`, `0019`, `0020`, `0022`, and `0023`:

```
── item 0:4 (VarIdx 4): 14 numbers for each of 3 regions
region 0 (wght 0…1…1): [-1442, -836, 0, 0, -1081, 98, -491, 1163, 8241, 6504, 327, 721, 1933, -2343]
region 1 (opsz 0…1…1): [0, 0, 4375, 3375, 0, 0, 0, 0, -639, -213, 0, 0, -2409, 0]
region 2 (wght 0…1…1 × opsz 0…1…1): [0, 0, -4375, -246, 0, 0, 0, 1491, -2507, -1097, 0, 0, -983, 0]
```

At weight 700, normalized 1, only the first region counts, in full. `0018`, tenth, goes from 377 to 377 + 6504 = 6881, 0.023 to 0.42; `0017`, ninth, from 0.039 to 0.542. Both thicken 木’s strokes (as drawings of 木 at each show), and that is how 桨 gets bold: its leaves have no weight variations. In `varc-ac00-ac01.ttf` it’s the other way round: the leaves vary with weight, and the components pass the weight through.

The stem’s transform item, four numbers per region for `translateX`, `translateY`, `scaleX`, and `scaleY`, shows how sparse such data is:

```
── item 3:7 (VarIdx 196615): 4 numbers for each of 25 regions
region 3 (0000 0…1…1): [0, 484, 0, -564]
region 23 (0018 0…1…1): [-59, 0, 117, 0]
region 25 (0019 0…1…1): [1, -54, -2, -461]
region 26 (0020 0…1…1): [19, 304, -35, -533]
region 27 (0021 0…1…1): [280, 0, -5, 41]
(and 20 more regions, all 0)
```

On `0018`, `translateX` moves the stem left by half as much as `scaleX` widens it, keeping it centered; on `0019`, `scaleY` shrinks. The numbers are packed in runs, like gvar’s deltas, so empty regions cost little.

HarfBuzz 14.6.0 changed VARC to “the revised variation-store format. The new format is incompatible with the previous one.” A VARC font made for HarfBuzz before 14.6.0 doesn’t draw correctly in later versions.

## The compact encoding

With tens of thousands of glyphs, each of several components, VARC packs its records tightly. Here is the ㄱ’s component record, as `varc-dump.py` reads it, in `decompile_record`’s order:

```
── glyph 3, component 0 (offsets from the start of VARC)
00f3  3e              flags = 0x3e: HAVE_AXES, AXIS_VALUES_HAVE_VARIATION, TRANSFORM_HAS_VARIATION, HAVE_TRANSLATE_X, HAVE_TRANSLATE_Y
00f4  00 04           gid = 4
00f6  00              axisIndicesIndex = 0 → axes 0000, 0001, 0002
00f7  42              axisValues: run of 3 words
00f8  ef 7d 03 33 de dc axisValues: -4227, 819, -8484
00fe  00              axisValuesVarIndex = 0
00ff  01              transformVarIndex = 1
0100  ff f6           translateX = -10
0102  00 18           translateY = 24
```

Seventeen bytes, for three varying axes and a varying offset.

**Variable-length integers.** The flags and indices are each an `HBUINT32VAR` (`hb-open-type.hh:149`), one to five bytes. The first byte’s leading 1 bits say how many follow: below `0x80`, none; `10`, one; `110`, two; `1110`, three; `11110000`, a plain 32-bit number. Most indices take one byte; in 桨, whose store has four data lists, they carry an outer part and take three (196608, outer 3 and inner 0, is `c3 00 00`).

**Flags ordered by frequency.** The commonest flags are the low 7 bits, which fit in one byte: resetting, having axes, the two kinds of variation, translations, and rotation (`VarComponent::flags_t`, `VARC.hh:51`). A condition, scales, a center, skews, or a 24-bit glyph ID need two: 木’s first stroke’s flags, `0xf7f`, are `8f 7f`. For each reserved bit (15 and up) that is set, HarfBuzz skips one more variable-length integer (`VARC.cc:139`), so later fields can be stepped over.

**Only the fields that are there.** The glyph ID is 16 bits unless `GID_IS_24BIT` is set; each 16-bit transform field is stored only if flagged. A record doesn’t store its length: decoding it finds the next.

**Shared, packed lists.** The record doesn’t list its axes: it gives an index into a list of axis lists, where `0000, 0001, 0002` is stored once for the three records in this font that use it. The values are `TupleValues` (`hb-open-type.hh:1513`), the run encoding of gvar’s deltas: `42` is `0x40`, “words”, and a count of 2 + 1. A run of zeros is just its control byte: the stem’s four axis values are `83`.

## What VARC doesn’t touch

VARC is only about drawing. It doesn’t change advances, which still come from `hmtx` and HVAR, or from the phantom points of the glyph’s own `glyf` entry:

```shape
hb:test/api/fonts/varc-ac00-ac01.ttf  가각  --variations=wght=356.5  --show-extents
hb:test/api/fonts/varc-ac00-ac01.ttf  가각  --variations=wght=840.3  --show-extents
```

The extents change with the weight, but the advances stay at 920. And GSUB and GPOS never see components: shaping works on glyph IDs, and a VARC glyph is one glyph. The subsetter does look inside VARC, so that the components a glyph needs are kept with it, as does [hb-depend](hb-depend.html).

The extents are a union of each leaf’s box, transformed as a box. Each leaf’s box is scaled to the font’s size first and then rounded outward, to whole units (`glyf.hh:460`, `hb-font.hh:214`). For a rotated component, a rotated box is bigger than the outline inside it, so a VARC glyph’s extents can be looser than its outline: for `varc-6868.ttf`, about 8 units on the left and 10 on the right.

## HarfBuzz and the standard

In a few places, HarfBuzz doesn’t do what the 2026 ISO standard says.

**The missing scale.** HarfBuzz uses a lone horizontal scale for both directions (`VARC.cc:468`), as fontTools and the boring-expansion text do; a reader of the ISO standard alone would take the missing value to be 1.

**Mixed leaves.** The standard says a glyph’s leaves mustn’t mix outline formats. HarfBuzz tries every format for every leaf, so it tolerates fonts that do, and it accepts CFF leaves, which the standard doesn’t list.

**Side bearings.** The standard says that TrueType’s left-side-bearing shift ([Varying outlines](varying-outlines.html#where-the-outline-lands)) doesn’t apply to components loaded by VARC. HarfBuzz’s leaves go through the same `glyf` code as any glyph, and are shifted. `varc-static-gvar-lsb.ttf`, made by `fonts/variable-components/lsb.py`, gives `a` and `b` a side bearing of 100 in `hmtx`, though their outlines still start at 0:

```shape
varc-static-gvar-lsb.ttf  ab  --show-extents
```

`b` moves to 100, as any `glyf` glyph would. By the standard, `a` should stay at 50; HarfBuzz draws it at 150. It matters only for fonts whose side bearings differ from their outlines’ left edges.

**The layout.** In two places HarfBuzz, fontTools, and the test fonts agree with each other and not with the standard: the standard’s list of conditions has no count field, and it measures the offsets in a region from the list of regions rather than from the region. Both look like errors in the standard.

And one bug, which no standard would allow. A leaf’s outline is scaled to the font’s size before the transform is applied, and HarfBuzz scales only the transform’s translation to match (`VARC.cc:511`):

```c++
hb_transform_t<> leaf_transform = transform;
leaf_transform.x0 *= c.font->x_multf;
leaf_transform.y0 *= c.font->y_multf;
```

That’s right when the font is scaled equally both ways. Otherwise a component that rotates or skews comes out wrong, rotated after the stretch. Here is 桨 twice as wide as it is high:

```draw
font: hb:test/api/fonts/varc-6868.ttf
text: 桨
options: --font-size=2000,1000
```

丬’s long vertical stroke is a leaf squashed into a flat bar and rotated by 90°, so the horizontal stretch lengthens it instead of thickening it: it should be 453 units tall, and it is 906. Fonts whose components don’t rotate or skew, like `varc-ac00-ac01.ttf`, are unaffected.

## Where to read the source

| File | What’s there |
|---|---|
| `src/OT/Var/VARC/VARC.hh` | the table, the component flags, the records |
| `src/OT/Var/VARC/VARC.cc` | decoding a component, 31; `get_path_at` for a component, 343, and for a glyph, 467 |
| `src/OT/Var/VARC/coord-setter.hh` | coordinates that grow to take hidden axes |
| `src/hb-geometry.hh` | the transform, 406 |
| `src/hb-ot-layout-common.hh` | sparse regions, 2594; `MultiVarData`, 3442; the multiple item variation store, 3858 |
| `src/hb-open-type.hh` | variable-length integers (`HBUINT32VAR`), 149; packed values (`TupleValues`), 1506 |
| `src/hb-ot-font.cc` | VARC before `glyf` and CFF, 919 |

## In short

* A VARC glyph is a list of components, each with a condition, its own axis settings, and a full transform, all of which can vary.
* A component’s condition and deltas are evaluated at its parent’s coordinates; its outline is drawn at its own.
* Hidden axes, up to 4096 and unclamped, are each part’s private parameters, set per use; `RESET_UNSPECIFIED_AXES` stops a part inheriting its parent’s.
* The multiple item variation store gives a component one list of deltas for all its values, over regions naming only the axes they use.
* Records are packed tightly. A glyph that names itself as a component is drawn from its own outline.
* VARC changes drawing and extents only, never advances or shaping.
* HarfBuzz differs from the 2026 standard on side bearings, mixed leaf formats, and a missing scale default, and it draws rotated components wrongly when the font is scaled unevenly.
