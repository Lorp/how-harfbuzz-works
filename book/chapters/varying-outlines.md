# Varying outlines

The outlines of a TrueType variable font vary in their own table, `gvar`, which doesn’t use the item variation stores of [the previous chapter](deltas.html). It has to store far more deltas than any other table, two for every point of every glyph at every master, and it is built to keep them small: deltas can be left out and worked out from their neighbors, tuples can share their positions, and runs of small numbers are packed into bytes. This chapter follows HarfBuzz from a request to draw a glyph at some position to the points it draws, and then looks at the two other kinds of variable outline data, CFF2’s blends and `cvar`, which HarfBuzz reads differently or not at all.

## A glyph’s points, and four more

Drawing a glyph, measuring its extents and, when there’s no HVAR, finding its advance all go through one function, `Glyph::get_points` (`OT/glyf/Glyph.hh:326`). For a simple glyph, it reads the outline’s points into an array of floats. Then it adds four **phantom points**, which aren’t part of the outline but stand for the glyph’s metrics (`Glyph.hh:391`):

```c++
int h_delta = (int) header->xMin - lsb;
...
int v_orig  = (int) header->yMax + tsb;
unsigned h_adv = glyf_accelerator.hmtx->get_advance_without_var_unscaled (gid);
...
phantoms[PHANTOM_LEFT].x = h_delta;
phantoms[PHANTOM_RIGHT].x = (int) h_adv + h_delta;
phantoms[PHANTOM_TOP].y = v_orig;
phantoms[PHANTOM_BOTTOM].y = v_orig - (int) v_adv;
```

The left phantom is where the glyph’s origin is, and the right one is where its advance ends; top and bottom do the same vertically. gvar gives deltas for the phantom points like any others, so a glyph’s metrics vary with its outline. The advance, when it comes from the outlines, is the distance between the left and right phantoms.

The test font’s `V` has seven points on its one contour, numbered from 0: two up the left side, then five down the right side, from the top. The phantoms are points 7 to 10.

## Tuples

For each glyph, gvar stores a list of **tuple variations**. Each says where in the design space it applies, as a peak and, optionally, a start and end on each axis, the same tents as in the previous chapter. Each then gives x and y deltas, for every point or for some of them. Here is `V` in `var.ttf`:

```table
font: variations/var.ttf
table: gvar
glyph: V
```

There are four tuples: one for the light master, peaking at weight −1; two for the heavier masters, including the intermediate one, with its own start and end; and one for the narrow master. The light and narrow tuples list only points 1, 6, and 8.

### Shared tuples, and a bug fixed in 15.1.0

Most glyphs in a font vary at the same places, so gvar has a list of **shared tuples**: peaks that any glyph can refer to by index instead of storing its own. HarfBuzz computes the scalar for a shared peak once per position, in the same kind of cache as the item variation stores use, and every glyph that refers to that peak can reuse it.

But a tuple can take its peak from the shared list and still have its *own* start and end, for an intermediate region. Its scalar then depends on more than the peak. HarfBuzz 15.1.0’s release notes list “Fix wrong outlines in `gvar` fonts with intermediate tuples”, and the fix is the first thing in `calculate_scalar` (`hb-ot-var-common.hh:112`):

```c++
/* The gvar shared-tuple cache is clamped to the 12-bit tuple-index range.
 * Only PrivatePointNumbers may accompany a cached shared-tuple index; any
 * other flag sets a bit at or above 0x1000, making this range test fail.
 */
bool plain_shared_tuple = (tuple_index & ~TupleIndex::PrivatePointNumbers) < shared_tuple_scalar_cache->length;
if (likely (plain_shared_tuple))
{
  float scalar;
  if (likely (shared_tuple_scalar_cache->get (index, &scalar)))
    return scalar;
}
```

and, further down, for a tuple with an intermediate region:

```c++
/* Intermediate regions belong to this tuple, not the shared peak. */
shared_tuple_scalar_cache = nullptr;
```

A tuple’s index field holds the shared tuple’s number in its low 12 bits and flags above them. The cache is used only when the field, ignoring the flag for private point numbers, is a plain index, and an intermediate tuple never stores its scalar there. Before the fix, an intermediate tuple and a plain one with the same shared peak could read each other’s scalars from the cache. Which one was wrong depended on which glyph was drawn first.

The research for this chapter reproduced the bug. It changed one tuple in one of HarfBuzz’s test fonts, `TestGVARFour.ttf`, so that one shared peak was used plainly by `O` and as an intermediate by `I`. HarfBuzz 12.3.0 drew `I` correctly on its own and wrongly in “OI” and “IO”. 15.1.0 draws it the same in every case, and agrees with fontTools.

## Points that aren’t there: IUP

A tuple can list the points it gives deltas for, instead of giving deltas for all of them. For the points it leaves out, the deltas are worked out by **interpolation of untouched points**, IUP, which comes from TrueType hinting. On each contour, an unlisted point takes its delta from the nearest listed points on either side, going round the contour:

* if it lies between them, in x (or in y, for the y delta), its delta is interpolated between theirs;
* if it lies beyond both, it takes the delta of the nearer one;
* if the two have the same coordinate, it takes their delta when they agree, and 0 when they don’t.

That is `infer_delta` (`hb-ot-var-gvar-table.hh:665`):

```c++
if (prev_val == next_val)
  return (prev_delta == next_delta) ? prev_delta : 0.f;
else if (target_val <= hb_min (prev_val, next_val))
  return (prev_val < next_val) ? prev_delta : next_delta;
else if (target_val >= hb_max (prev_val, next_val))
  return (prev_val > next_val) ? prev_delta : next_delta;

/* linear interpolation */
float r = (target_val - prev_val) / (next_val - prev_val);
return prev_delta + r * (next_delta - prev_delta);
```

varLib left points out of `V`’s light tuple because IUP gets them right. Point 1, the top left, has delta 0, and point 6, the bottom right, has −60. The points from 2 to 5, down the right side, all have the same x as point 6 at the default, which is beyond point 1’s, so they take point 6’s delta, and the whole right edge moves 60 units left. Point 0, the bottom left, is at point 1’s x, below point 6’s, so it takes point 1’s delta of 0. The right phantom, point 8, is listed with −60, so the advance shrinks with the stem.

```draw
font: variations/var.ttf
text: V
slider: wght 100 900 25
start: 400
```

Toward the heavy end, varLib *did* list every point, even though the middle ones lie on a straight line and IUP could have found them: their deltas grow evenly down the edge, 300, 262, 225, 188, 150. It chooses whichever encoding is smaller, and listing which points are present costs bytes too. A font can’t be told from its outlines whether IUP was used.

HarfBuzz runs IUP on each contour separately. It stops at the last contour’s end, so the phantom points are never inferred: a phantom that isn’t listed gets no delta, which is what the specification intends. A contour with no listed points is left alone; a contour with only one listed point moves as a whole, since every other point takes that point’s delta. And the inference is made against the glyph’s *default* points, not points already moved by earlier tuples, which is right, and which shapes the fast path below.

The specification infers from each tuple’s deltas before multiplying them by the tuple’s scalar. HarfBuzz infers from deltas already multiplied. The two are equal, apart from floating-point rounding.

### The fast path

Most tuples in most fonts give deltas for every point. For those, `apply_deltas_to_points` (`hb-ot-var-gvar-table.hh:769`) doesn’t build any arrays: it decodes each delta, multiplies it by the scalar, and adds it straight into the point (`decompile_deltas_add_to_points`, 692). But that’s only safe if no later tuple needs IUP, because IUP needs the default points, and the fast path has changed them. So before taking the fast path, HarfBuzz looks ahead: if any remaining tuple, with a scalar that isn’t 0, has its own list of points, it takes the slow path, which keeps the deltas apart until a copy of the default points has been made.

## Composites

A composite glyph is made of other glyphs, each placed at an offset. Under gvar, each component counts as one point, its offset, so a tuple can move a component as a whole. One of HarfBuzz’s test fonts, `TestGVAR-Composite-0.ttf` from the Unicode text-rendering tests, has an `Ö` built from an `O` and a diaeresis, and a tuple on its slant axis that moves only the diaeresis:

```draw
font: hb:test/shape/data/text-rendering-tests/fonts/TestGVAR-Composite-0.ttf
text: Ö
slider: slnt -15 0 1
start: 0
print: -15 -7 0
```

The diaeresis’s offset goes from 52 units at slant 0 to 92 at −15. Each component’s point is marked as the end of its own contour (`OT/glyf/CompositeGlyph.hh:244`), so IUP never moves a component that a tuple doesn’t list. A component with the `USE_MY_METRICS` flag gives the composite its metrics, so its phantom points are copied to the composite’s, and the composite’s own phantom deltas aren’t used, as the specification says.

## Where the outline lands

Two steps happen after the deltas are applied. First, at the top level, every point is shifted by the varied left phantom (`Glyph.hh:585`), under a comment that reads “Undocumented rasterizer behavior: Shift points horizontally by the updated left side bearing”. So a delta on phantom 0 moves the outline, not just the metrics.

Second, the points stay floats. Drawing doesn’t round them at all, while extents and advances are rounded in font units, before the font’s size is applied:

```shape
variations/var.ttf  V  --variations=wght=613  --show-extents  --font-size=100000
```

At weight 613, `V`’s right edge is drawn at fractional positions: in `hb-vector`’s output, the top right corner is at x = 316.33. But at 100 times the font’s size, its extents come out as multiples of 100: a width of 23600, not 23633. A renderer that draws the outline and an application that lays out boxes from the extents see slightly different glyphs.

## When things go wrong

HarfBuzz treats damage to gvar in two ways. If a glyph’s variation header can’t be read, its variations are dropped and the glyph is drawn at the default, with the comment “so isn’t applied at all”. But if the data inside a tuple is broken, a run that is too long or a list of points that runs off the end, the whole glyph fails: it isn’t drawn, and if its advance came from the phantoms, it falls back to half an em.

Some other robustness choices: a point number past the end of the glyph is skipped; a point listed twice gets both deltas added; gvar’s own glyph count is never read, and the face’s glyph count is used instead (`hb-ot-var-gvar-table.hh:659`). And HarfBuzz accepts one encoding the specification doesn’t have. The packed deltas in gvar have three kinds of run: zeros, bytes, and 16-bit words. HarfBuzz reads them with the same decoder as VARC’s data, which has a fourth, 32-bit run, marked by both flag bits. No conforming font has one in gvar, since to a reader that follows the specification those bits mean a run of zeros.

## GVAR

A font with more than 65,535 glyphs uses `GVAR`, from the 2026 ISO standard. In HarfBuzz both tables come from one template, `gvar_GVAR<T, Types>` (`hb-ot-var-gvar-table.hh:318`), with `SmallTypes` for gvar and `MediumTypes` for GVAR, as in the GSUB chapter’s beyond-64k formats. The glyph count is 24-bit in GVAR, and so is the offset to each glyph’s serialized data, which the standard’s table says too, although a note beside it says the glyph count is the only difference. The standard also says that “bit 1” of the flags selects long offsets, where Microsoft’s specification and HarfBuzz use bit 0.

## CFF2

CFF2 outlines vary differently. There are no stored deltas per point. Instead, a charstring’s `blend` operator takes a default value and one delta for each region, and the region scalars come from an item variation store. HarfBuzz computes the scalars once for each charstring, at its first `blend`, and adds the deltas without rounding (`hb-cff2-interp-cs.hh`). It ignores blended values in the Private DICT, which are hinting values, with the comment “Hint values are ignored here”.

## cvar

`cvar` varies the control values that TrueType hinting instructions read. HarfBuzz doesn’t hint, so its font functions never read cvar. The only user is the subsetter: when it makes a static instance of a variable font, it adds the cvar deltas at that position into a copy of `cvt `, rounded (`hb-subset.cc:347`), so the instance hints the way the variable font would have there.

## Where to read the source

| File | What’s there |
|---|---|
| `src/OT/glyf/Glyph.hh` | `get_points`, 326: phantom points, composites, the left-side-bearing shift |
| `src/OT/glyf/glyf.hh` | drawing, extents, and advances from phantom points |
| `src/hb-ot-var-gvar-table.hh` | `apply_deltas_to_points`, 769; `infer_delta`, 665; the fast path, 692; GVAR |
| `src/hb-ot-var-common.hh` | `calculate_scalar`, 112, and the shared-tuple cache; point numbers |
| `src/hb-cff2-interp-cs.hh` | CFF2 `blend` and `vsindex` |
| `src/hb-ot-var-cvar-table.hh`, `src/hb-subset.cc` | cvar, used only when instancing |

## In short

* gvar varies every point, including four phantom points for the metrics. Without HVAR, advances come from the phantoms.
* Points a tuple doesn’t list are inferred per contour from their neighbors, against the default outline. Phantom points are never inferred.
* Shared peaks have cached scalars. In 15.1.0, tuples with their own intermediate regions stopped using that cache, which fixed wrong outlines.
* A component of a composite glyph moves as one point.
* Outlines are drawn unrounded; extents and advances are rounded in font units.
* Broken tuple data makes a glyph vanish; a broken header only drops its variations.
