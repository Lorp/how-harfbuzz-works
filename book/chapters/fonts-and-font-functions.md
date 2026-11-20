# Fonts and font functions

A face is a font file’s tables, read lazily and shared. It has no size. It can’t say how wide a glyph is at 12 points, or which glyph a character maps to, without someone doing the arithmetic and reading the right table. That is the job of the **font**, `hb_font_t`: a face at a particular scale, with particular variation coordinates and, if asked, synthetic bold and slant. Every question the shaper asks about glyphs goes to the font, not the face.

The font doesn’t answer those questions itself either. It passes each one to a table of callbacks, the **font functions** (“font funcs”). HarfBuzz’s own implementation, *hb-ot*, reads the font’s OpenType tables. Others ask FreeType, Core Text, DirectWrite, or the Rust Fontations crates. An application can supply its own, or override just one callback and leave the rest alone. The shaper never knows which it is talking to. This split, between asking about glyphs and shaping with the answers, is one of HarfBuzz’s central design choices, and this chapter is about the layer that makes it work: what a font holds, how the callbacks are organized, how a font can delegate to a parent, and where synthetic bold and slant are applied.

How hb-ot actually works out an advance or a bounding box is the subject of the [next chapter](where-metrics-come-from.html). The face underneath, and how its tables are loaded, is the subject of the [previous one](blobs-faces-and-lazy-tables.html). The examples here use a small test font, `funcs.ttf`, built by `fonts/fonts-and-font-functions/build-font.py`. Its em is 1000 units, and its glyphs have deliberately awkward advances: H is 625 units wide and I is 275. It has a GPOS mark rule for a combining acute and one kerning pair, H I, of −25. Every result on this page was produced by HarfBuzz {{hb}} when the page was built.

## What a font holds

`hb_font_t` is defined in `hb-font.hh:111`. Leaving out the object header and the plumbing, it is this (trimmed):

```c++
struct hb_font_t
{
  hb_atomic_t<unsigned> serial;
  hb_atomic_t<unsigned> serial_coords;

  hb_font_t *parent;
  hb_face_t *face;

  int32_t x_scale;
  int32_t y_scale;

  bool is_synthetic;
  float x_embolden, y_embolden;
  bool embolden_in_place;
  int32_t x_strength, y_strength;   /* x_embolden, in scaled units. */
  float slant;
  float slant_xy;

  float x_multf, y_multf;
  int64_t x_mult, y_mult;

  unsigned int x_ppem, y_ppem;
  float ptem;

  unsigned int instance_index;      /* Font variation coordinates. */
  bool has_nonzero_coords;
  unsigned int num_coords;
  int *coords;
  float *design_coords;

  hb_font_funcs_t   *klass;
  void              *user_data;
  hb_destroy_func_t  destroy;

  hb_shaper_object_dataset_t<hb_font_t> data;
};
```

The fields fall into a few groups: three kinds of size, the synthetic settings, the variation coordinates, the font funcs (`klass`, with `user_data` as the per-font data they work on), and `data`, which is where each shaper keeps its own per-font state. The rest of this chapter takes them in turn.

### Three kinds of size

HarfBuzz has three separate notions of how big a font is, and they do different things.

**Scale** is the one that matters. `x_scale` and `y_scale` are the number of output units in one em. Every advance, offset, and extent HarfBuzz returns is in those units. The documentation for `hb_font_set_scale` (`hb-font.cc:2812`) is clear that HarfBuzz attaches no meaning to them: 20 could be 20 pixels, 20 points, or 20 millimeters. A client that wants fractions usually multiplies: `hb_font_set_scale (font, 20 * 64, 20 * 64)` gives a 20-unit font with 6 bits of sub-unit precision, which is what FreeType’s 26.6 numbers expect. A new font’s scale is the face’s units per em, so out of the box HarfBuzz reports positions in font units. `hb-shape` does the same unless it is given `--font-size`, which sets the scale directly:

```shape
funcs.ttf  HIH
funcs.ttf  HIH  --font-size=2000
funcs.ttf  HIH  --font-size=13
funcs.ttf  HIH  --font-size=-1000
```

The first H is 600, not 625, because of the kerning pair. At a scale of 13, the kerning (−0.325 of a unit) rounds away. A negative scale is allowed and simply flips the sign, which is how a client working with a y-down coordinate system can get y values it can use directly. The synthetic code takes care to keep its adjustments pointing the right way when a scale is negative.

**Pixels per em**, `x_ppem` and `y_ppem`, are zero unless a client sets them, and nearly nothing reads them. They exist for the few parts of OpenType that are defined in pixels: the hinting Device tables that GPOS value records and anchors can carry, anchors that name a contour point (AnchorFormat2, which needs a hinted outline to mean anything), and the choice of bitmap strike in `sbix` and `CBDT`. The test font’s kerning pair has a Device table saying “at 12 ppem, one pixel less”:

```shape
funcs.ttf  HI
funcs.ttf  HI  --font-ppem=12
funcs.ttf  HI  --font-ppem=13
funcs.ttf  HI  --font-size=12  --font-ppem=12
```

`HintingDevice::get_delta` (`hb-ot-layout-common.hh:6351`) turns the pixel delta into scaled units as `pixels * scale / ppem`. At a scale of 1000 and 12 ppem, one pixel is 83 units, so H’s advance drops from 600 to 517. At 13 ppem the table has nothing to say. At a scale of 12 and 12 ppem, one pixel is one unit. With no ppem set, the Device table isn’t even looked at (`ValueFormat.hh:145`; the same field can instead hold a variation index, which is why a variable font with non-default coordinates reads it anyway).

**Point size**, `ptem`, is also zero unless set. It is the size in typographic points, and only three things read it: AAT’s `trak` table, whose tracking values are given per point size (`hb-aat-layout-trak-table.hh:226`); the Core Text integration, which needs a real size to create a `CTFont` (`hb-coretext-shape.cc:68`); and `hb_style_get_value`, which reports `ptem` as the optical size of a font that has no `opsz` axis (`hb-style.cc:98`). When it isn’t set, the first two use 12 points, Core Text’s own default. Setting `ptem` does *not* set an `opsz` axis: choosing an optical size is left to the client.

> For programmers: the three are independent. Setting the scale doesn’t set ppem, and setting ppem doesn’t change the scale. A client that wants hinting Device tables to apply has to set both.

### The mults, and rounding

Every time a setting changes, the font recomputes its scale factors in `hb_font_t::changed` (`hb-font.hh:1167`):

```c++
void changed ()
{
  float upem = face->get_upem ();

  x_multf = x_scale / upem;
  y_multf = y_scale / upem;
  x_mult = (int64_t) x_scale * 0x10000 / upem;
  y_mult = (int64_t) y_scale * 0x10000 / upem;

  is_synthetic =  x_embolden || y_embolden || slant;

  x_strength = roundf (abs (x_scale) * x_embolden);
  y_strength = roundf (abs (y_scale) * y_embolden);

  slant_xy = y_scale ? slant * x_scale / y_scale : 0.f;

  data.fini ();

  serial++;
}
```

There are two multipliers for each direction. `x_mult` is a 16.16 fixed-point number, and `x_multf` is a float. The font offers a small family of conversions built on them (`hb-font.hh:161–170`):

| Function | Takes | Gives | How |
|---|---|---|---|
| `em_scale_x` | integer font units | integer | `(v * x_mult + 32768) >> 16` |
| `em_scalef_x` | float font units | integer | `roundf (v * x_multf)` |
| `em_fscale_x` | integer font units | float | `v * x_multf`, unrounded |
| `em_fscalef_x` | float font units | float | `v * x_multf`, unrounded |

Integer metrics such as `hmtx` advances go through `em_scale_x`. Values that are already fractional, such as the result of applying variation deltas, go through `em_scalef_x`. GPOS anchors are scaled to floats with `em_fscale_x` and only rounded when the final offset is worked out, so two anchors don’t each pick up a rounding error.

The fixed-point path has a quirk worth knowing. The multiplier itself is truncated when it is computed: at a scale of 12 and 1000 units per em, the exact multiplier is 786.432/65536 and the stored one is 786/65536. The rounding afterward is round-half-up. So an advance that should come out at exactly one half can fall just short of it:

```shape
funcs.ttf  H  --font-size=12
funcs.ttf  H  --font-size=13
```

625 × 12/1000 is exactly 7.5, which would round to 8. With the truncated multiplier it is 625 × 786/65536 = 7.496, a hair under the half, so it rounds to 7. At 13, 8.125 rounds to 8 either way. Nobody should depend on which way a half goes, but it explains results that look one unit off. Glyph extents are scaled differently again, in floats, and rounded outwards across but not up and down (`scale_glyph_extents`, `hb-font.hh:201`); the [next chapter](where-metrics-come-from.html#scaling-and-rounding) shows the difference.

> For type designers: at small integer scales, the rounding of each advance can add up across a line. That’s why clients that care set a scale with fractional bits (a multiple of 64, say) rather than the pixel size itself.

### Serial numbers

`changed()` ends by freeing every shaper’s per-font data and incrementing `serial`. Every setter that alters the font (`hb_font_set_scale`, `set_ppem`, `set_ptem`, `set_synthetic_bold`, `set_synthetic_slant`, `set_funcs`, `set_parent`, and the variation setters) checks first whether the value is actually different, and calls `changed()` only if it is. A client whose font data changes behind HarfBuzz’s back can call `hb_font_changed` to bump the serial itself. `hb_font_get_serial` returns it.

The serial is how font funcs know when their caches are stale. hb-ot compares it at the start of each call that uses a cache (`check_serial`, `hb-ot-font.cc:290`). There is a second serial, `serial_coords`, that changes only when the variation coordinates do (`_hb_font_adopt_var_coords`, `hb-font.cc:2191`). hb-ot caches advances in font units, before scaling, so a change of scale needn’t throw them away: those caches are keyed on `serial_coords`, and only the vertical-origin cache, which holds scaled values, is keyed on `serial`. The `fontations` funcs use the public serial in the same way to decide when to rebuild their Rust-side instance (`rust/font.rs:75`).

Because `changed()` frees shared state, changing a font while another thread is shaping with it isn’t safe. A font can be made immutable with `hb_font_make_immutable`, which also freezes its parents (`hb-font.cc:2382`). After that every setter is a no-op, and the font can be shared between threads freely.

## The font funcs

### One list of callbacks

The callbacks a font can have are listed once, in a macro at `hb-font.hh:46`:

```c++
#define HB_FONT_FUNCS_IMPLEMENT_CALLBACKS \
  HB_FONT_FUNC_IMPLEMENT (get_,font_h_extents) \
  HB_FONT_FUNC_IMPLEMENT (get_,font_v_extents) \
  HB_FONT_FUNC_IMPLEMENT (get_,nominal_glyph) \
  HB_FONT_FUNC_IMPLEMENT (get_,nominal_glyphs) \
  HB_FONT_FUNC_IMPLEMENT (get_,variation_glyph) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_h_advance) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_v_advance) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_h_advances) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_v_advances) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_h_origin) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_v_origin) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_h_origins) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_v_origins) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_h_kerning) \
  HB_IF_NOT_DEPRECATED (HB_FONT_FUNC_IMPLEMENT (get_,glyph_v_kerning)) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_extents) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_contour_point) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_name) \
  HB_FONT_FUNC_IMPLEMENT (get_,glyph_from_name) \
  HB_FONT_FUNC_IMPLEMENT (,draw_glyph_or_fail) \
  HB_FONT_FUNC_IMPLEMENT (,paint_glyph_or_fail) \
  /* ^--- Add new callbacks here */
```

This is an *X macro*. The file defines `HB_FONT_FUNC_IMPLEMENT` to mean one thing, expands the list, undefines it, and does the same again with another meaning. `hb_font_funcs_t` (`hb-font.hh:70`) is built that way three times over: once for a struct of user-data pointers, once for a struct of destroy callbacks, and once for the function pointers themselves, which sit in a union with a plain array so that a slot can be found by its index. In `hb-font.cc` the same list generates every public `hb_font_funcs_set_*_func` setter, and the nil and default tables described next. Adding a callback to HarfBuzz means adding a line here.

What they answer, in groups:

| Callbacks | The question |
|---|---|
| `font_h_extents`, `font_v_extents` | ascender, descender, and line gap for the font as a whole |
| `nominal_glyph(s)`, `variation_glyph` | which glyph a character maps to, alone or with a variation selector: the `cmap` |
| `glyph_h_advance(s)`, `glyph_v_advance(s)` | how far the pen moves after a glyph |
| `glyph_h_origin(s)`, `glyph_v_origin(s)` | where a glyph’s origin is for that direction, relative to its horizontal origin |
| `glyph_h_kerning`, `glyph_v_kerning` | a kerning value for a pair: only for the fallback `kern` path, and the vertical one is deprecated |
| `glyph_extents` | a glyph’s ink bounding box |
| `glyph_contour_point` | the position of one outline point, for AnchorFormat2; none of HarfBuzz’s own funcs sets it in {{hb}} |
| `glyph_name`, `glyph_from_name` | names to IDs and back |
| `draw_glyph_or_fail`, `paint_glyph_or_fail` | the outline, or the color glyph, for the [drawing](drawing-outlines.html) and [color](color.html) APIs |

Several came later than the rest. The batch forms of the cmap and advance callbacks were added so that a shaper can ask for a whole buffer at once. The batch origin callbacks are from 11.3.0, and the `_or_fail` draw and paint callbacks from 11.2.0, when the earlier `draw_glyph` and `paint_glyph` ones were deprecated (`NEWS`).

The shaper never calls a slot directly. A comment in the struct says so: “Don’t access these directly. Call `font->get_*()` instead.” Those wrapper methods in `hb_font_t` are where synthetic bold and slant are applied, after the callback has answered, which is why they work whichever funcs are installed.

### The nil tier and the default tier

`hb-font.cc` has two complete implementations of the list, and every slot of every font funcs object holds a function from one of them or a real implementation.

The **nil** functions answer “nothing”. They are named `hb_font_get_*_nil` and live in the Null `hb_font_funcs_t` (`hb-font.cc:812`). Most return false and zeros. A few return something more useful: the horizontal advance is a full em (`return font->x_scale;`, `hb-font.cc:220`), the vertical advance is minus one em, and the horizontal origin is (0, 0), returned as success.

The **default** functions, `hb_font_get_*_default`, delegate. They ask the font’s *parent* and rescale the answer. They fill `_hb_font_funcs_default` (`hb-font.cc:827`), and every new funcs object starts as a copy of that table (`hb_font_funcs_create`, `hb-font.cc:852`). Setting a callback to `NULL` puts the default back (`hb-font.cc:1072`). Confusingly, `hb_font_funcs_get_empty` returns the *default* table, not the nil one (`hb-font.cc:874`).

The two tiers meet at the bottom of a chain of parents. A font made with `hb_font_create` has as its parent the empty font, `hb_font_get_empty`, which is the static Null `hb_font_t` (`hb-font.cc:2061`), with a scale of 1000 and the nil funcs. So any question that a font’s own funcs don’t answer goes up to its parent, and so on, until it reaches the Null font, where the nil functions answer it. A font with no real funcs at all still works: every glyph is .notdef, and every advance is one em.

### Single and batch forms fall back on each other

Five callbacks come in pairs: `nominal_glyph`/`nominal_glyphs`, the two advance pairs, and the two origin pairs. An implementation needs to provide only one of each pair, because the default of each calls the other if that one is set. Here is the single advance (`hb-font.cc:229`):

```c++
static hb_position_t
hb_font_get_glyph_h_advance_default (hb_font_t *font, void *font_data,
                                     hb_codepoint_t glyph, void *user_data)
{
  if (font->has_glyph_h_advances_func_set ())
  {
    hb_position_t ret;
    font->get_glyph_h_advances (1, &glyph, 0, &ret, 0, false);
    return ret;
  }
  return font->parent_scale_x_distance (font->parent->get_glyph_h_advance (glyph, false));
}
```

The batch default does the mirror image, looping over the single callback if *that* is set, and otherwise asking the parent for the whole batch. hb-ot provides only the batch advances (`hb-ot-font.cc:986`), so a client calling `hb_font_get_glyph_h_advance` for one glyph goes through the default, which calls the batch with a count of one.

`has_func_set` decides whether a slot is “set” by comparing it with the default table (`hb-font.cc:1084`):

```c++
bool hb_font_t::has_func_set (unsigned int i)
{ return this->klass->get.array[i] != _hb_font_funcs_default.get.array[i]; }

bool hb_font_t::has_func (unsigned int i)
{
  return has_func_set (i) ||
         (parent && parent != &_hb_Null_hb_font_t && parent->has_func (i));
}
```

The first asks whether *this* font implements a slot. The second asks whether anything in the chain above it does, short of the Null font. The pair fallback uses the first. The shaper uses the second, to skip work: `hb_ot_position_default` only applies horizontal origins if some font in the chain provides them (`hb-ot-shape.cc:1016`), since without them every horizontal origin is zero.

There is one more detail that stops the pairs from recursing for ever. For the batch slots, the nil function *is* the default function (`#define hb_font_get_nominal_glyphs_nil hb_font_get_nominal_glyphs_default`, `hb-font.cc:165`, and the same for advances and origins). On the Null font, the single nil function counts as “set”, because it isn’t the default one, so the batch default loops over it. The chain always ends.

> For programmers: when you write your own funcs, implement the batch forms of the cmap and advance callbacks if you can. The shaper asks for whole buffers at once (`hb-ot-shape.cc:1013`), and a batch implementation can keep its lookups and caches warm across the loop.

## Parents and sub-fonts

The parent pointer is more than a way to reach the nil functions. `hb_font_create_sub_font` (`hb-font.cc:2220`) makes a new font whose parent is an existing one. It copies the parent’s scale, ppem, ptem, synthetic settings, and variation coordinates, and its funcs are the default table, so at first every question goes straight through to the parent.

The point is to override a little and inherit the rest. A client that wants to map characters through its own table, but get everything else from the font, makes a sub-font, gives it funcs with only `nominal_glyph` set, and shapes with the sub-font. Every other question still reaches the parent’s hb-ot funcs.

A sub-font can also have a different scale from its parent. Each default function converts the parent’s answer with `parent_scale_x_distance` and friends (`hb-font.hh:173`):

```c++
hb_position_t parent_scale_x_distance (hb_position_t v)
{
  if (unlikely (parent && parent->x_scale && parent->x_scale != x_scale))
    return (hb_position_t) (v * (int64_t) this->x_scale / this->parent->x_scale);
  return v;
}
```

The parent’s value has already been rounded to the parent’s scale, and this division truncates. So a sub-font at a different scale doesn’t give quite the same answers as a font made at that scale directly. `hb-shape` has a hidden `--sub-font` option that shows it: it makes a sub-font, then sets the *parent* to twice the scale (`util/font-options.hh:138`), so every answer is worked out at double size and halved:

```shape
funcs.ttf  HIH  --font-size=13
funcs.ttf  HIH  --font-size=13  --sub-font
```

Directly, I is 275 × 13/1000 = 3.575, which rounds to 4. Through the parent, it is 7.15 at a scale of 26, which rounds to 7, and 7 × 13/26 = 3.5 truncates to 3. Outlines and color glyphs are rescaled in floats instead, by wrapping the client’s draw funcs in an adaptor that multiplies every coordinate (`hb_font_draw_glyph_or_fail_default`), or by pushing a scale transform onto the paint funcs.

When a default function delegates, it asks the parent *without* synthetic settings (the `false` in `get_glyph_h_advance (glyph, false)`), and the sub-font’s own wrapper then applies its own. Since 11.2.0 that is the rule for advances, extents, contour points, font extents, and outlines, so a sub-font’s synthetic bold and slant are the ones that count, not its parent’s (`NEWS`). HarfBuzz uses this itself: when it paints a COLR glyph for a synthetic font, it makes a sub-font with bold and slant turned off, so that the synthetic settings, already applied to the glyph as a whole, aren’t applied again to each of its layers (`OT/Color/COLR/COLR.hh:115`).

A sub-font copies its parent’s coordinates but not its named-instance index. `hb_font_set_parent` (`hb-font.cc:2456`) replaces a font’s parent later, and refuses to make a cycle.

## Synthetic bold and slant

A family that has no bold or italic can still be shown in one, by thickening or shearing the regular outlines. HarfBuzz can do both, and since 11.0.1 it does them in the font layer, in the `hb_font_t` wrappers, rather than in hb-ot or hb-ft, so they work with any funcs (`NEWS`). They are set with `hb_font_set_synthetic_bold` and `hb_font_set_synthetic_slant`. The question for a type designer is what they change, and the answer is: rather more than the outlines.

### Bold, and grade

`hb_font_set_synthetic_bold (font, x_embolden, y_embolden, in_place)` takes two fractions of the em. `changed()` turns them into `x_strength` and `y_strength`, rounded to whole units of the current scale. The outline is made that much wider and taller: the drawing code is a port of FreeType’s `FT_Outline_EmboldenXY`, with permission (`hb-outline.cc:122`), which moves each edge outwards by half the strength.

The `in_place` flag decides what happens to the spacing. If it is false, the glyph is bold in the usual sense: its advance grows by the strength, and the outline is shifted right by half the strength so that the left side bearing stays the same. If it is true, the advance is left alone and the outline grows equally in both directions about where it was. That second mode simulates **grade**, a heavier weight that doesn’t reflow text. `hb-shape` has an option for each: `--font-bold` sets bold with `in_place` false, and `--font-grade` sets it with `in_place` true (`util/font-options.hh:264–282`). (The C API’s own default, for a font nobody has set, is `in_place` true.)

```shape
funcs.ttf  HÍ  --show-extents
funcs.ttf  HÍ  --font-bold=0.02  --show-extents
funcs.ttf  HÍ  --font-grade=0.02  --show-extents
```

The strength is 0.02 × 1000 = 20 units. With `--font-bold`, H and I are 20 units wider, but the acute, whose advance is zero, isn’t: the wrappers add the strength only to advances that aren’t zero (`advance = hb_saturate_add (advance, advance ? strength : 0)`, `hb-font.hh:387`), so that marks stay on their bases. The ink boxes are 20 wider and 20 taller, and their left edge hasn’t moved. With `--font-grade`, the advances are unchanged, and each box has grown 10 units to the left and 10 to the right. In both, the bottom of each box stays on the baseline and the top rises by 20.

The mark’s offset changes too, from 12 to −8, though nothing about the mark’s anchor did. GPOS places it relative to the I’s anchor, measured back from the pen position after the I, and the I’s advance is now 20 units longer. When the glyphs are drawn, both the I and the mark are shifted right by 10, so the two anchors still meet. Grading changes nothing in the positions at all.

Here is everything synthetic bold touches, from the wrappers in `hb-font.hh`:

| What | Bold (`in_place` false) | Grade (`in_place` true) |
|---|---|---|
| horizontal advances | + x strength, if not zero (`:383`) | unchanged |
| vertical advances | + y strength, if not zero (`:400`) | unchanged |
| glyph origins, when the funcs supply them | moved by the strength (`:474`) | unchanged |
| glyph extents | wider by x strength, taller by y strength (`:255`) | the same, centered horizontally |
| contour points | moved right by x strength (`:681`) | unchanged |
| font h-extents | ascender + y strength (`:308`) | the same |
| font v-extents | ascender + x strength (`:325`) | split between ascender and descender |
| outlines | emboldened and shifted (`:754`) | emboldened in place |

### Slant

`hb_font_set_synthetic_slant (font, slant)` takes a ratio: 0.2 means x moves right by 0.2 units for every unit of y, about 11.3°. `changed()` stores it as `slant_xy`, adjusted for the ratio of the two scales so that it shears correctly when x and y are scaled differently. Slant never changes an advance. What it does change is spread more widely than bold’s effects:

* **Outlines.** `draw_glyph_or_fail` shears every point (`hb-font.hh:745`). It does so around the glyph’s horizontal origin, which for nearly every font is (0, 0), so the baseline stays put. That has been the rule in the draw API since 12.3.0 (`NEWS`). It slants before it emboldens, which, says a comment, “produces nicer results”. Color glyphs get the same shear as a paint transform (`:779`).
* **Extents**, of which more below.
* **Contour points**, sheared like the outline (`:677`).
* **Mark positions after GPOS.** At the very end of GPOS, in `GPOS::position_finish_offsets` (`OT/Layout/GPOS/GPOS.hh:198`), which `hb-ot-shape.cc:1084` calls whether or not the font has GPOS, every glyph with a vertical offset in horizontal text has its horizontal offset adjusted to match:

  ```c++
  if (unlikely (font->slant_xy) &&
      HB_DIRECTION_IS_HORIZONTAL (direction))
  {
    /* Slanting shaping results is only supported for horizontal text,
     * as it gets weird otherwise. */
    for (unsigned i = 0; i < len; i++)
      if (unlikely (pos[i].y_offset))
        pos[i].x_offset = hb_clamp_to<hb_position_t> ((double) pos[i].x_offset +
                                                      (double) roundf (font->slant_xy * pos[i].y_offset));
  }
  ```

* **Caret slope**, in `hb_ot_metrics_get_position` (`hb-ot-metrics.cc:180`): the horizontal caret run is increased to match the slant, scaled up first if the font’s caret rise is small, so that the ratio survives in integers.
* **Slant angle.** `hb_style_get_value` adds the synthetic slant to the slant angle wherever that comes from: a `slnt` axis, STAT, or `post` (`_hb_style_apply_synthetic_slant`, `hb-style.cc:59`; [Other tables](other-tables.html)). Before 15.2.0 only `post`’s angle got it. The same total, as a ratio, is reported under the tag `Slnt`.

Glyph origins are expressly not slanted: “Slant is ignored as it does not affect glyph origin” (`hb-font.hh:471`). Before 12.2.0 they were, which shifted slanted glyphs sideways (`NEWS`).

```shape
funcs.ttf  HÍ  --show-extents
funcs.ttf  HÍ  --font-slant=0.2  --show-extents
```

The advances are the same. The ink boxes are 140 units wider, which is 0.2 × 700, the cap height: the tops of the letters have moved right. The acute’s offset has gone from 12 to 2. Its anchor puts it 50 units lower than where it is drawn in the font, and lower, on a slanted line, is further left: 0.2 × −50 = −10.

The caret and style values change in the same way:

```info
funcs.ttf  --get-metric=hcrs --get-metric=hcrn --get-style=slnt
funcs.ttf  --get-metric=hcrs --get-metric=hcrn --get-style=slnt --font-slant=0.2
```

The font’s `hhea` caret is upright (rise 1, run 0). With slant, the rise is multiplied up to 256 and the run is 0.2 of that, and the slant angle is −11.3°: negative for a lean to the right, as in `post`.

> For type designers: a synthetically slanted font keeps its upright spacing. Its marks stay attached to their bases, because both the GPOS result and the drawing are sheared by the same amount, and its caret leans with it. What it can’t do is anything a real italic does differently: cursive forms, different spacing, narrower letters.

### Extents of a synthetic font

Working out the ink box of a slanted or emboldened glyph is harder than adjusting a box: a sheared rectangle has a different bounding box from a sheared circle. So `get_glyph_extents` (`hb-font.hh:608`) takes a different route for a synthetic font. It doesn’t ask the funcs for extents at all. It first tries to *paint* the glyph into a context that only measures, then to *draw* it into one, and only if both fail does it ask the funcs for extents and adjust the box arithmetically with `synthetic_glyph_extents` (`:236`):

```c++
if (!is_synthetic &&
    klass->get.f.glyph_extents (this, user_data, glyph, extents, ...))
  return true;

/* Try getting extents from paint(), then draw(), *then* get_extents()
 * and apply synthetic settings in the last case. */
```

Painting and drawing both go through the synthetic wrappers, so the box is measured from the outline as it would actually be drawn. This has been the case since 11.2.0, whose `NEWS` says extents for synthetic fonts “are now accurately calculated”. It costs an outline decode per glyph, which matters to anything that asks for extents often. One thing that does is HarfBuzz’s own fallback mark positioning, used when a font has no GPOS, which centers each mark’s ink box over its base. The same glyphs in `funcs-nogpos.ttf`, which has no GPOS:

```shape
funcs-nogpos.ttf  HÍ
funcs-nogpos.ttf  HÍ  --font-slant=0.2
```

Slanted, the acute’s ink box is measured from the sheared outline. The acute sits high, at 750 to 900 units, so shearing moves its box about 165 units right, and the positioner moves the mark 165 units left to center it again (12 − 165 = −153). When it is drawn, the shear moves it back.

## hb-ot, the default funcs

`hb_font_create` (`hb-font.cc:2159`) makes a font in four steps. `_hb_font_create` sets the scale to the face’s units per em, makes the empty font its parent and the default table its funcs. Then `hb_font_set_funcs_using (font, nullptr)` installs the default funcs. Then, if the face index has anything in its top 16 bits, that number minus one is taken as a named instance and applied; otherwise `hb_font_set_variations (font, nullptr, 0)` puts the font at the default position in its design space.

`hb_font_create_without_funcs_or_fail` (`hb-font.cc:2171`), new in 15.2.0, does the same without the second step, for a client that is about to install funcs of its own: setting up the default funcs only to replace them costs time, and, for hb-ot, a font’s worth of caches. It doesn’t read `HB_FONT_FUNCS`. Until funcs are installed, its slots hold the default table, so every question goes up to the empty font, and every glyph is .notdef with an advance of one em. Unlike `hb_font_create`, it returns `NULL` rather than the empty font when it runs out of memory, including when it can’t allocate the variation coordinates. HarfBuzz uses it itself: `hb_ft_font_create` makes its font this way before installing the FreeType funcs (`hb-ft.cc:1490`), which, says `NEWS`, stops it loading a second FreeType face, and so does `hb-shape` when `--font-funcs` names the funcs (`util/font-options.hh:84`).

For nearly every build, the default funcs are hb-ot. They are made once, lazily, as a static immutable `hb_font_funcs_t` shared by every font (`hb-ot-font.cc:975`). What varies per font is the data handed to them, an `hb_ot_font_t` holding a pointer to the face’s tables and the font’s caches (`hb_ot_font_set_funcs`, `hb-ot-font.cc:1044`). Here is what hb-ot sets, and what it leaves to the default tier:

| Set by hb-ot | Left to the defaults |
|---|---|
| `nominal_glyph`, `nominal_glyphs`, `variation_glyph` | |
| `font_h_extents`, `font_v_extents` | |
| `glyph_h_advances`, `glyph_v_advances` | the single forms, which call these |
| `glyph_v_origins` | `glyph_v_origin`, which calls it |
| | `glyph_h_origin(s)`: every horizontal origin is (0, 0) |
| | `glyph_h_kerning`: hb-ot applies `kern` in the shaper instead |
| `glyph_extents` | |
| | `glyph_contour_point`: written, but never installed (`if (false)`, `hb-ot-font.cc:1004`), so AnchorFormat2 falls back to its coordinates |
| `glyph_name`, `glyph_from_name` | |
| `draw_glyph_or_fail`, `paint_glyph_or_fail` | |

The blank rows go up the parent chain to the Null font. How each of the set callbacks gets its answer, from `cmap`, `hmtx`, `HVAR`, `gvar`, `glyf`, `CFF`, and the rest, is the subject of the [next chapter](where-metrics-come-from.html).

## The other funcs

HarfBuzz {{hb}} has four more implementations of the same list, each optional at build time:

| Name | Source | Build option | What it asks |
|---|---|---|---|
| `ot` | `hb-ot-font.cc` | on unless `HB_NO_OT_FONT` | HarfBuzz’s own table code |
| `ft` | `hb-ft.cc` | `-Dfreetype` (auto) | FreeType |
| `fontations` | `rust/font.rs` | `-Dfontations` (off) | the Rust crates read-fonts and skrifa |
| `coretext` | `hb-coretext-font.cc` | `-Dcoretext` (off) | Apple’s Core Text |
| `directwrite` | `hb-directwrite-font.cc` | `-Ddirectwrite` (off) | Microsoft’s DirectWrite |

**hb-ft** is the oldest. For a long time it was the usual way to use HarfBuzz, and the `hb-shape` and `hb-view` tools only switched their default from FreeType to `ot` in 4.0.0 (`NEWS`). It sets FreeType’s character size from the font’s scale whenever the serial changes (`hb-ft.cc:260`), and takes a lock around its FreeType calls (`hb-ft.cc:437` and on), since FreeType itself isn’t thread-safe. It is the only implementation that sets `glyph_h_kerning` (`hb-ft.cc:1171`), so it is the only one that can feed HarfBuzz’s fallback kerning. It used to set `glyph_contour_point` as well, and was the only one that did; 15.2.0 left its implementation in place but stopped installing it (`if (false)`, `:1174`), as hb-ot and fontations do with theirs, so in {{hb}} no built-in funcs answer for contour points. That is for kerning HarfBuzz can’t read as a table, such as a Type 1 font’s (`NEWS` 2.5.2): a font with a `kern` table has it applied directly, and the fallback never runs ([Fallbacks](fallbacks.html), [Legacy kern](legacy-kern.html)). It can wrap an `FT_Face` the client already has (`hb_ft_font_create`), or make its own from the face’s blob (`hb_ft_font_set_funcs`, `hb-ft.cc:1931`).

**`fontations`** is a font-funcs backend, not a shaper. It was added in 11.0.0, along with the DirectWrite funcs, and `NEWS` for that release announces the Core Text funcs with them, describing all three as “mostly useful for performance and correctness testing” (the Core Text function itself, `hb_coretext_font_set_funcs`, had appeared in 10.1.0: `hb-coretext-font.cc:522`). [Integrations](integrations.html) covers what each of these layers offers an application. It wraps the face’s blob in a read-fonts `Font`, draws outlines with skrifa, and implements the cmap, advance, vertical origin, extents, font extents, draw, paint, and name callbacks, built into a static funcs object on first use (`rust/font.rs:1395`). Paired with the HarfRust shaper, which is covered in [hb_shape and its backends](hb_shape-and-its-backends.html), it gives an all-Rust path through HarfBuzz.

**Core Text** and **DirectWrite** funcs ask the platform. Both use the per-font data of the matching *shaper* to get their native font object (`font->data.coretext`, `font->data.directwrite`), which is why Core Text needs `ptem`. One detail shows how much the two layers have to agree: Core Text applies AAT tracking to the advances it reports, and HarfBuzz’s shaper applies `trak` itself, so the Core Text funcs subtract the tracking from Core Text’s advances to stop it being applied twice (`hb-coretext-font.cc:213`). Core Text adds the horizontal track in vertical text too, and since 15.2.0 that is what the vertical advances have taken off (`get_coretext_tracking`, `hb-aat-layout-trak-table.hh:207`).

### Choosing funcs

Since 11.0.0, funcs can be chosen by name. The compiled-in names are in a table, in order of preference (`hb-font.cc:2606`):

```c++
static const struct supported_font_funcs_t {
	char name[16];
	void (*func) (hb_font_t *);
} supported_font_funcs[] =
{
#ifndef HB_NO_OT_FONT
  {"ot",	hb_ot_font_set_funcs},
#endif
#ifdef HAVE_FREETYPE
  {"ft",	hb_ft_font_set_funcs},
#endif
  /* ... fontations, coretext, directwrite, each under its own #ifdef */
};
```

`hb_font_list_funcs` returns those names. `hb_font_set_funcs_using (font, name)` (`hb-font.cc:2690`) installs the one with that name, and returns false if there is none. With a null or empty name, it reads the environment variable `HB_FONT_FUNCS` (once, at first use, `hb-font.cc:2636`) and uses that name instead. If that names an entry, the entry is used, even if it fails. If it is unset or names nothing in the table, HarfBuzz walks the table and keeps the first entry that works. An implementation that fails, as hb-ft does when FreeType can’t open the blob, leaves the font with the empty funcs (`hb-ft.cc:1947`), and that is how the loop can tell. So the default is `ot`, unless `HB_FONT_FUNCS` says otherwise, and a misspelt `HB_FONT_FUNCS` is silently ignored.

`hb-shape` exposes the same choice as `--font-funcs`, and `--list-font-funcs` prints the table. The HarfBuzz this book is built with is configured with FreeType turned off and the other optional backends left at their defaults (`tools/build-harfbuzz.sh`), so it lists only `ot`:

```shape
funcs.ttf  HI  --font-funcs=ot
```

`hb_font_set_funcs` itself, the lower-level call, takes any funcs object and the data that goes with it. It is how an application installs its own funcs, or puts the default table back with a null `klass`. `hb_font_set_face`, deprecated in 15.0.0, does nothing since 15.2.0 (`hb-font.cc:2510`): its documentation says to make a new font with `hb_font_create` instead. Before, it swapped the font’s face; in 15.0.0 and 15.1.0 it also threw the funcs away and ran `hb_font_set_funcs_using` again, because the old funcs might point into the old face, a use-after-free that 15.0.0’s `NEWS` reports fixing.

## Variation coordinates, as the font holds them

A variable font’s position in its design space belongs to the font, not the face, so one face can back fonts at several positions at once. The font keeps it in two forms: `design_coords`, one float per `fvar` axis in the axis’s own units, and `coords`, the same position normalized to −1…1 in 2.14 fixed point after `avar`, which is what every variation table uses. `has_nonzero_coords` is true if any normalized coordinate isn’t zero, and the hb-ot funcs check it first so that a font at its default position takes the fast, non-variable paths. `instance_index` holds a named-instance number, or `HB_FONT_NO_VAR_NAMED_INSTANCE`.

The setters differ in a way that catches people out:

* `hb_font_set_variations` (`hb-font.cc:3097`) is not additive. It starts every axis from its default, or from the named instance if one is set, then applies the list it is given. Axes not in the list go back to the base.
* `hb_font_set_variation` (`:3159`), singular, *is* additive: it starts from the font’s current design coordinates and changes one axis.
* `hb_font_set_var_coords_design` sets every axis from a list in axis order.
* `hb_font_set_var_coords_normalized` sets the normalized coordinates directly and fills `design_coords` with NaN, since there is no way back through `avar`.
* `hb_font_set_var_named_instance` records the index and calls `hb_font_set_variations` with an empty list.

All of them end in `_hb_font_adopt_var_coords` (`hb-font.cc:2191`), which swaps in the new arrays, calls `changed()`, and copies the new serial into `serial_coords`. How the coordinates are normalized, and what avar does to them, is the subject of [Design space](design-space.html).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-font.hh` | `hb_font_t`, the callback list, the `em_scale` family, `parent_scale_*`, every synthetic wrapper, `changed()` |
| `src/hb-font.cc` | the nil and default tiers, `has_func`, the public setters, `hb_font_create`, `hb_font_create_sub_font`, `hb_font_set_funcs_using`, `hb_font_list_funcs`, variation setters |
| `src/hb-font.h` | the public API, with the callback typedefs |
| `src/hb-ot-font.cc` | the hb-ot funcs, their caches, and `check_serial` |
| `src/hb-ft.cc`, `src/rust/font.rs`, `src/hb-coretext-font.cc`, `src/hb-directwrite-font.cc` | the other funcs |
| `src/hb-outline.cc` | recording outlines, slanting and emboldening them |
| `src/OT/Layout/GPOS/GPOS.hh` | `position_finish_offsets`, where slant adjusts mark offsets |
| `src/hb-ot-metrics.cc`, `src/hb-style.cc` | caret slope and slant angle under synthetic slant |
| `util/font-options.hh` | how `hb-shape` sets up a font: `--font-size`, `--font-bold`, `--font-grade`, `--font-slant`, `--font-funcs`, `--sub-font` |

The user manual’s chapter on fonts and faces (`docs/usermanual-fonts-and-faces.xml`) walks through sub-fonts and custom funcs from the client’s side.

## In short

* A font is a face at a scale. Scale sets the output units; ppem matters only to hinting Device tables, contour-point anchors, and bitmap strikes; ptem only to `trak`, Core Text, and the reported optical size.
* Scaling integer metrics uses a truncated 16.16 multiplier and rounds half up, so exact halves can round down.
* Every setter bumps the font’s serial and frees shaper data. Funcs compare serials to know when their caches are stale.
* Every callback slot holds a real function, a default that asks the parent and rescales, or a nil that answers “nothing” (one em, for advances). Single and batch forms fall back on each other.
* A sub-font inherits everything and overrides what it sets. Rescaling through a parent truncates, so it can differ by a unit.
* Synthetic bold changes advances (unless in place), extents, font extents, and outlines. Slant changes outlines, extents, caret slope, the slant angle, and mark offsets after GPOS, but never advances or origins. Extents of a synthetic font are measured from the drawn outline.
* hb-ot is the default funcs, chosen as the first working entry in a table, unless `HB_FONT_FUNCS` names another. `hb_font_create_without_funcs_or_fail` (15.2.0) skips them, for a client that installs its own; `hb_font_set_face` now does nothing.
