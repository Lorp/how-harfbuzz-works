# Where metrics come from

A shaper moves glyphs about, but it doesn’t know how big they are. When HarfBuzz needs to know how far a glyph advances, where its origin is in vertical text, or how far its ink reaches, it asks the font object, and the font object passes the question to its font functions. The [previous chapter](fonts-and-font-functions.html) is about that arrangement: the vtable, its tiers, and the choice of implementation. This chapter is about the answers. It follows the functions HarfBuzz installs by default, the **hb-ot** font functions in `hb-ot-font.cc`, as they read `hmtx`, `HVAR`, `gvar`, `VORG`, `glyf`, `CFF`, the color and bitmap tables, `hhea`, `OS/2`, and `MVAR`.

Most of what follows is a chain of fallbacks. For each question there is a table that should answer it, then something that can stand in for that table, then a guess. Which link of the chain answers decides the numbers an application sees, so it’s worth knowing where each chain starts and what it falls back to. Type designers will find here which of the font’s numbers HarfBuzz actually reads, and which it ignores.

The examples use small test fonts made by `fonts/where-metrics-come-from/build-metrics-fonts.py`, whose glyphs are plain rectangles with deliberately chosen metrics, and the variable test fonts shared with the chapters on variations. Every shaping result on this page was produced by HarfBuzz {{hb}} when the page was built.

## Five questions

These are the font functions hb-ot answers about metrics, and where it looks for each answer, in the order it looks:

| Question | Font function | Where hb-ot looks |
|---|---|---|
| horizontal advance | `glyph_h_advances` | `hmtx`; at a non-default location also `HVAR`, or else `gvar`’s phantom points; with no `hmtx`, half an em |
| vertical advance | `glyph_v_advances` | `vmtx`; at a non-default location also `VVAR`, or else `gvar`; with no `vmtx`, the font’s line height |
| vertical origin | `glyph_v_origins` | `VORG` (and `VVAR`); else `vmtx` with `glyf`; else centered from the glyph’s extents |
| glyph extents | `glyph_extents` | `sbix`, `CBDT`, `COLR`, `VARC`, `glyf`, `CFF2`, `CFF `: the first that knows the glyph |
| font extents | `font_h_extents`, `font_v_extents` | `OS/2` typo metrics if `USE_TYPO_METRICS` is set, else `hhea`; `vhea`; plus `MVAR` |

Two things are missing from the list. hb-ot has no horizontal origin function, so every glyph’s horizontal origin is at (0, 0). And it has no kerning function: the old `kern` table is applied by the shaper, not looked up through the font (see [Legacy kern](legacy-kern.html)). The glyph mapping functions, which read `cmap`, are covered with [normalization](normalization.html).

The shaper uses these answers in a few places. Advances and vertical origins are fetched for every glyph when positioning begins (see [the pipeline](pipeline-step-by-step.html)). Glyph extents are used by the fallback mark positioner, when a font has no GPOS mark attachment (see [Fallbacks](fallbacks.html)), and by the vertical-origin fallback below. Font extents are used by the vertical fallbacks, and by applications to space lines.

## Advance widths: hmtx

### The shape of the table

`hmtx` is unusual among OpenType tables: it has no header and no count of its own. Its length comes from two numbers in other tables. `hhea` says how many **long metrics** there are, each an advance and a left side bearing. `maxp` says how many glyphs there are. Glyphs after the last long metric have only a side bearing, and share the last long metric’s advance. The arrangement exists for monospaced fonts, which can store their advance once, but any font whose last glyphs have equal advances can use it: fontTools, for one, trims the trailing run automatically.

HarfBuzz’s struct for the pair is `LongMetric` (`hb-ot-hmtx-table.hh:54`): a `UFWORD advance` and an `FWORD sb`. The same struct serves `vmtx`, so the fields are named for either direction, and the count in `hhea`, which the specification calls `numberOfHMetrics`, is `numberOfLongMetrics` in HarfBuzz, shared with `vhea`.

The test font `metrics.ttf` has nine glyphs. The last three, the figures, have the same advance, 550, so fontTools stored seven long metrics and two bare side bearings. This is its `hmtx`, all 32 bytes of it, laid out by hand from the font:

| Glyph ID | Glyph | Bytes | Advance | Left side bearing |
|---|---|---|---|---|
| 0 | `.notdef` | `01f4 0032` | 500 | 50 |
| 1 | `space` | `00fa 0000` | 250 | 0 |
| 2 | `H` | `0258 0050` | 600 | 80 |
| 3 | `L` | `0230 00a0` | 560 | 160 |
| 4 | `p` | `0230 0050` | 560 | 80 |
| 5 | `x` | `01f4 0064` | 500 | 100 |
| 6 | `zero` | `0226 003c` | 550 | 60 |
| 7 | `one` | `00c8` | (550) | 200 |
| 8 | `two` | `003c` | (550) | 60 |

Shaping the glyphs gives those advances, including the two that aren’t stored. The extents, in angle brackets, come up later:

```shape
metrics.ttf  HLpx012  --show-extents
```

### Reading it

Because `hmtx`’s size depends on other tables, the sanitizer can’t check it on its own. HarfBuzz doesn’t try. Its `sanitize` accepts anything, and a comment says why: “The users of the struct do all the hard work...” The hard work is in the accelerator’s constructor (`hb-ot-hmtx-table.hh:271`), which runs once per face and fits the three counts to the bytes that are really there. Trimmed, it reads:

```c++
unsigned int len = table.get_length ();
if (len & 1)
  len--;

num_long_metrics = num_long_metrics_;            /* from hhea */
if (unlikely (num_long_metrics > len / 4))
  num_long_metrics = len / 4;
len -= num_long_metrics * 4;

num_bearings = face->table.maxp->get_num_glyphs ();
if (unlikely (num_bearings < num_long_metrics))
  num_bearings = num_long_metrics;
if (unlikely ((num_bearings - num_long_metrics) * 2 > len))
  num_bearings = num_long_metrics + len / 2;

/* We MUST set num_bearings to zero if num_long_metrics is zero. */
if (unlikely (!num_long_metrics))
  num_bearings = num_long_metrics = 0;
```

So a `numberOfHMetrics` larger than the table is cut down to what fits, a `maxp` count smaller than it is raised to match, and a table too short for all its side bearings is cut at the last whole one. A font whose `numberOfHMetrics` is zero is treated as having no `hmtx` at all. After that, every lookup is a bounds check and an array read:

```c++
unsigned int get_advance_without_var_unscaled (hb_codepoint_t glyph) const
{
  if (glyph < num_bearings)
    return table->longMetricZ[hb_min (glyph, (uint32_t) num_long_metrics - 1)].advance;

  if (unlikely (!num_advances))
    return default_advance;

  return 0;
}
```

The `hb_min` is the shared advance: any glyph past the last long metric reads the last one.

### Glyphs the table doesn’t cover

A glyph past the end of the side bearings gets an advance of **zero**, not the shared advance. The specification says every glyph shares the last advance, but HarfBuzz only gives it to glyphs that actually have an entry. `metrics-short.ttf` is `metrics.ttf` with its `hmtx` cut two bytes short, so that `two`, the last glyph, has no side bearing:

```shape
metrics.ttf  012  --show-extents
metrics-short.ttf  012  --show-extents
```

The `two` is still there, with its outline, but it takes up no space, and the next glyph would be drawn on top of it. Its x-bearing has become 0 as well, for a reason that comes up in the next section. A glyph ID beyond `maxp`’s count, which a buggy GSUB lookup can produce, gets a zero advance too.

A font with no `hmtx` at all is different: every glyph is given half an em (`hb-ot-font.cc:396`). `metrics-nohmtx.ttf` has no `hmtx`:

```shape
metrics-nohmtx.ttf  HLpx012  --show-extents
```

Every advance is 500, half the 1000-unit em, and, again, every x-bearing is 0.

Fonts with more than 65,535 glyphs can carry `HMTX` and `HHEA` instead, the wider versions from the “beyond 64k” extension, whose count of long metrics is 32 bits. HarfBuzz loads both kinds through one “dual” accelerator (`hb-ot-dual.hh`), which uses the wide table if it’s there and the ordinary one otherwise, so nothing else in this chapter needs to know which it got.

> For type designers: a font tool that writes `hmtx` too short, or a `maxp` count that disagrees with it, doesn’t make HarfBuzz fail. It makes the last glyphs zero-width, which is easy to miss in a proof that doesn’t use them.

## Side bearings, and a glyph that moves

hb-ot never reads the right side bearing, and it reads the left side bearing only for TrueType outlines. But there it matters more than its name suggests.

In a `glyf` font, the left side bearing in `hmtx` and the `xMin` in the glyph’s header ought to be the same number. When they aren’t, HarfBuzz does what the TrueType rasterizers do, which no specification describes: it moves the outline so that `xMin` becomes the left side bearing. A comment in `OT/glyf/GlyphHeader.hh:20` calls it “undocumented rasterizer behavior”. The extents read the bearing instead of `xMin`:

```c++
/* Undocumented rasterizer behavior: shift glyph to the left by (lsb - xMin), i.e., xMin = lsb */
int lsb = hb_min (xMin, xMax);
(void) glyf_accelerator.hmtx->get_leading_bearing_without_var_unscaled (gid, &lsb);
extents->x_bearing = lsb;
```

and the drawing code shifts every point by the difference (`OT/glyf/Glyph.hh:587`). The `L` in the test font is drawn from x = 80, but `hmtx` says its left side bearing is 160. Its extents, above, start at 160, and when HarfBuzz draws it, so does its outline:

```draw
font: metrics.ttf
text: HLx
```

The same glyphs, drawn from CFF outlines in `metrics-cff.otf`, with the same `hmtx`, aren’t moved. CFF has no `xMin` to disagree with, and HarfBuzz doesn’t look at its side bearings at all:

```draw
font: metrics-cff.otf
text: HLx
```

(The third glyph differs too: in `metrics.ttf`, `x` is a color glyph, which comes up under glyph extents.)

This also explains the zero x-bearings in `metrics-short.ttf` and `metrics-nohmtx.ttf`. A glyph with no side bearing in `hmtx` is given a bearing of 0 (`hb-ot-hmtx-table.hh:315`), so its outline is moved to start at x = 0. Extents and drawing agree with each other, which is the point: whatever HarfBuzz reports as the ink is where it draws the ink.

> For type designers: in a TrueType font, the left side bearing in `hmtx` wins over the outline. Font compilers keep the two equal, so this only shows when a tool edits one and not the other.

## Advances in variable fonts

In a variable font, an advance can change across the design space. hb-ot has three ways to find it, and tries them in this order (`hb-ot-font.cc:382`).

First, it checks whether the font is at its default location. `has_nonzero_coords` is set when the font’s variation coordinates are stored (`hb-font.cc:2177`), and is false when every normalized coordinate is zero. Then the plain `hmtx` value is right, whatever variation tables the font has, and nothing is cached: an array read is as fast as a cache.

Otherwise, if the font has an **HVAR** table, HarfBuzz adds HVAR’s delta to the `hmtx` advance (`hb-ot-hmtx-table.hh:475`):

```c++
unsigned int advance = get_advance_without_var_unscaled (glyph);
return hb_clamp_to<unsigned> (advance + roundf (var_table->get_advance_delta_unscaled (glyph,
                                                font->coords, font->num_coords,
                                                store_cache)));
```

The delta comes from an item variation store: HVAR maps the glyph to a delta-set index, through its `advMap` if it has one or straight from the glyph ID if it doesn’t, and the store adds up that row’s deltas, each weighted by how much of its region the current location is in. How that weighting works is the subject of [Deltas](deltas.html). HVAR can also hold deltas for the side bearings, in `lsbMap` and `rsbMap`. HarfBuzz’s font functions never read them, though the subsetter keeps them.

If there is no HVAR but there is a **gvar** table, the advance comes from the outlines’ **phantom points**. Every TrueType glyph has four points that aren’t part of any contour: one at the left edge of its advance, one at the right, one at the top, and one at the bottom of its vertical advance. HarfBuzz builds them from `hmtx`, `vmtx`, and the glyph’s header (`OT/glyf/Glyph.hh:391`, trimmed):

```c++
int h_delta = (int) header->xMin - lsb;
int v_orig  = (int) header->yMax + tsb;
phantoms[PHANTOM_LEFT].x   = h_delta;
phantoms[PHANTOM_RIGHT].x  = (int) h_adv + h_delta;
phantoms[PHANTOM_TOP].y    = v_orig;
phantoms[PHANTOM_BOTTOM].y = v_orig - (int) v_adv;
```

`gvar` stores deltas for these four points just as it does for the outline’s, so after the deltas are applied, the distance from the left phantom point to the right one is the advance at that location (`OT/glyf/glyf.hh:468`). The result is rounded to a whole number of font units. In a composite glyph, a component with the `USE_MY_METRICS` flag gives the composite its phantom points, and with them its advance.

If there’s neither, which can happen with a CFF2 font that leaves out HVAR although the specification requires it, the advance is the unvaried `hmtx` one.

The variable test fonts have a weight axis from 100 to 900, with the default at 400. `var.ttf` has HVAR. `var-nohvar.ttf` is the same font with HVAR removed, so its advances come from phantom points. `var-badhvar.ttf` has HVAR with every delta doubled, so that HVAR and the outlines disagree:

```shape
variations/var.ttf  IHV  --variations=wght=400
variations/var-nohvar.ttf  IHV  --variations=wght=400
variations/var-badhvar.ttf  IHV  --variations=wght=400
variations/var.ttf  IHV  --variations=wght=900
variations/var-nohvar.ttf  IHV  --variations=wght=900
variations/var-badhvar.ttf  IHV  --variations=wght=900
```

At the default weight all three agree, because none of the variation tables is read. At 900, HVAR and the phantom points give the same advances, as they should: varLib made both from the same masters. The font with the doubled deltas gets advances 100 to 300 units too wide, though its outlines are the same as `var.ttf`’s. HarfBuzz doesn’t compare HVAR with `gvar`. If HVAR is there, it’s believed.

### What the phantom points cost

HVAR exists because the phantom-point route is slow. To find one advance from HVAR, HarfBuzz looks up the glyph’s delta-set index and adds up one row of deltas. To find it from phantom points, it has to find the glyph’s variation data in `gvar`, work out a scalar for every tuple variation that the glyph has, and read the deltas in each tuple up to the four phantom points, which come last, through the deltas of every outline point before them. For a composite glyph it has to descend into the component whose metrics it uses.

HarfBuzz keeps that work as small as it can. When only phantom points are wanted, the outline’s points are reserved but never decoded (`OT/glyf/SimpleGlyph.hh`), only the last four deltas are kept, and a composite is followed only into its last `USE_MY_METRICS` component. But the packed deltas still have to be read through to reach the ones it wants. And this happens for every advance the shaper asks for, which is every glyph in every run. A variable TrueType font without HVAR can shape correctly and still be slow.

### Caches

Variable advances are cached, per font object and per direction, in an **advance cache** (`hb-ot-font.cc:65`): a `hb_cache_t<24, 16>`, which is 256 slots of 32 bits, 1 KB in all. A glyph’s slot is chosen by the low 8 bits of its ID. The rest of the ID is stored in the slot beside the value, so a lookup is one memory read and a comparison. Glyph IDs of 24 bits or more, and advances of 65,536 units or more, aren’t cached.

Beside it are two caches for the variation data: a **varStore cache**, which holds the scalar of each of the item variation store’s regions at the current location, so that each is worked out once, and a **gvar cache**, which does the same for `gvar`’s shared tuples. Advances are cached in font units, before scaling. So changing the font’s size doesn’t clear them: only a change of variation coordinates does, which `check_serial` notices by comparing the font’s `serial_coords` with the one it saw last (`hb-ot-font.cc:290`).

Each cache sits in an atomic pointer, and is borrowed rather than locked. A caller swaps the pointer for null, uses the cache, and swaps it back. If another thread got there first, the second one finds null, allocates a cache of its own for the call, and frees it afterward if the slot has been refilled in the meantime. So two threads can shape with the same font object at once, at the cost of a cache each.

> For programmers: a font object’s caches belong to its variation coordinates. An application that shapes the same variable font at several locations does better with one font object for each location than with one font object whose coordinates keep changing.

## Vertical advances and origins

### Advances

Vertical advances come from `vmtx`, which has the same layout as `hmtx`, with `vhea` giving its count of long metrics. In a variable font, VVAR and phantom points play the same parts they do horizontally (`hb-ot-font.cc:506`). The one difference is the sign: HarfBuzz’s y axis points up, and vertical text runs down, so a vertical advance is negative.

A font with no `vmtx`, which is most fonts, gets the same advance for every glyph: the distance from the font’s horizontal ascender to its descender (`hb-ot-font.cc:520`). These come from `hhea` or `OS/2`, as described under font extents below, and the line gap is left out. In `metrics.ttf`, whose `hhea` ascender and descender are 900 and −300, that is 1,200 units.

### Origins

Glyphs are drawn from their horizontal origin, at the left end of the baseline. In vertical text they should hang from a different point, the **vertical origin**, usually centered above the glyph. The shaper moves each glyph by the difference between the two (`hb-ot-shape.cc:1022`). Since hb-ot’s horizontal origin is always (0, 0), the offsets `hb-shape` prints for vertical text are just the vertical origin, negated.

The x of the vertical origin is always half the glyph’s horizontal advance (`hb-ot-font.cc:649`). The y comes from the first of three sources that is there:

1. **VORG**, if the font has one. It lists a vertical origin for some glyphs and a default for the rest, and is meant for CFF fonts. In a variable font, VVAR’s `vorgMap` gives deltas for it.
2. Otherwise, if the font has both `vmtx` and `glyf`, the **top phantom point**: the glyph’s `yMax` plus its top side bearing from `vmtx`, with `gvar`’s deltas if the font is variable (`hb-ot-font.cc:725`).
3. Otherwise, a guess from the **glyph’s extents**: the glyph is centered in the font’s line height, so that the space above it equals the space below. If the glyph has no extents, the origin is the ascender.

Here are the same glyphs, set vertically, in four fonts. `metrics.ttf` has no vertical tables. `metrics-vert.ttf` has `vhea` and `vmtx`, with every advance 1000 and every top side bearing chosen to put the top of the glyph at 880. `metrics-cff.otf` has the same metrics with CFF outlines and a VORG whose default is 880, with 800 for `p`. `metrics-cff-novorg.otf` is that font without VORG:

```shape
metrics.ttf  HLpx  --direction=ttb
metrics-vert.ttf  HLpx  --direction=ttb
metrics-cff.otf  HLpx  --direction=ttb
metrics-cff-novorg.otf  HLpx  --direction=ttb
```

In vertical output, the advance is a pair: `+0,-1200` moves the pen 1,200 units down. In `metrics.ttf`, every glyph advances by the line height, and every origin is a guess from its extents: 950 for `H`, whose ink is 700 tall in a line 1,200 tall, but 745 for `p`, which is shorter and reaches below the baseline. With `vmtx`, every glyph hangs from 880, as the top side bearings say. The CFF font with VORG does what VORG says, `p` included. Without VORG, the CFF font falls back to guessing from extents, as `metrics.ttf` did, although it has the same `vmtx` as `metrics-vert.ttf`: HarfBuzz reads top side bearings only for `glyf` outlines.

Vertical origins are cached too, in a second 1 KB cache per font. Unlike advances, they’re cached after scaling, so any change to the font clears them, not only a change of coordinates.

> For type designers: a CFF font meant for vertical text needs VORG. Its `vmtx` gives the advances, but HarfBuzz won’t take the origins from it.

## Glyph extents

A glyph’s **extents** are the box around its ink, as `hb_glyph_extents_t`: `x_bearing` and `y_bearing` are the box’s top-left corner, relative to the glyph’s origin, and `width` and `height` its size. Since the y axis points up and the box is measured from its top, `height` is negative. `hb-shape --show-extents` prints them in that order, as `<x_bearing,y_bearing,width,height>`.

hb-ot asks each kind of glyph data in a fixed order, and the first that knows the glyph answers (`hb-ot-font.cc:811`):

```c++
if (ot_face->sbix->get_extents (font, glyph, extents)) return true;
if (ot_face->CBDT->get_extents (font, glyph, extents)) return true;
if (ot_face->COLR->get_extents (font, glyph, extents)) return true;
if (ot_face->VARC->get_extents (font, glyph, extents)) return true;
if (ot_face->glyf->get_extents (font, glyph, extents)) return true;
if (ot_face->cff2->get_extents (font, glyph, extents)) return true;
if (ot_face->cff1->get_extents (font, glyph, extents)) return true;
return false;
```

(trimmed of the `#ifdef`s that leave out each part in smaller builds). Bitmaps come first, then color, then outlines. So in a font with both a color version of a glyph and an outline, the extents are the color glyph’s.

**glyf.** At the default location, the extents are the box in the glyph’s header, with the left edge taken from `hmtx` as described above. HarfBuzz doesn’t recompute it from the points. At any other location it has to: it applies `gvar`’s deltas to every point and takes the box around them, rounded to whole font units (`OT/glyf/glyf.hh:527`). In both cases the box includes the off-curve points: the header’s box does by definition, and the computed one is taken around every point. A curve rarely reaches its control points, so this box can be larger than the ink. An empty glyph, like `space`, has extents of zero.

**CFF and CFF2.** HarfBuzz runs the glyph’s charstring with operators that collect a bounding box instead of drawing (`hb-ot-cff1-table.cc:410`, `hb-ot-cff2-table.cc:106`). Like `glyf`’s, the box includes the curves’ control points. A CFF2 charstring is run at the font’s variation coordinates. Neither looks at `hmtx`, which is why the CFF `L` above has its ink at 80.

**COLR.** A color glyph’s extents are its ClipBox, if COLR version 1 gives it one. Otherwise HarfBuzz paints the glyph into a context that records extents instead of pixels (`hb-paint-extents.hh`), so they are the box around every layer. In `metrics.ttf`, `x` has a small box as its outline, but it’s also a COLR glyph made of an `H` and a `p`:

```shape
metrics.ttf  Hpx  --show-extents
```

Its extents are the union of the other two, from the top of the `H` to the bottom of the `p`. Its own outline, a 300-unit square, isn’t consulted.

**sbix and CBDT.** Bitmap extents are in the pixels of one strike. HarfBuzz chooses the strike from the font’s ppem: the smallest strike at least that size, or the largest if none is big enough or the font has no ppem set. It then converts from the strike’s pixels to the font’s scale. For `sbix` it reads the size of the PNG image and the origin offsets beside it, and only PNG images are supported. For `CBDT` it reads the glyph’s metrics from beside the image, which it can do only for image formats 17 and 18. A glyph in another format has no bitmap extents, and the outlines answer instead. The [Color](color.html) chapter covers these tables.

**VARC**, variable composites, have extents worked out from their components; see [Variable components](variable-components.html). `SVG` glyphs are missing from the list: HarfBuzz doesn’t read extents from SVG documents, so an SVG glyph has the extents of its outline.

One thing happens before any of this. When a font has synthetic bold or slant, `hb_font_t` doesn’t ask the font functions for extents first: it paints the glyph, or failing that draws it, so that the extents include the synthetic changes (`hb-font.hh:586`). That belongs to the font object, and is in the [previous chapter](fonts-and-font-functions.html).

## Font extents

**Font extents** are three numbers for the whole font: the ascender, the descender, and the line gap, as `hb_font_extents_t`. Applications use them to space lines. HarfBuzz itself uses them only in the vertical fallbacks above.

OpenType gives three sets of candidates. `hhea` has `ascender`, `descender`, and `lineGap`. `OS/2` has the “typographic” `sTypoAscender`, `sTypoDescender`, and `sTypoLineGap`, and the Windows `usWinAscent` and `usWinDescent`. Which a program uses has always varied, and bit 7 of `OS/2.fsSelection`, `USE_TYPO_METRICS`, added in version 4 of the `OS/2` table, lets a font ask for the typographic ones. HarfBuzz follows the bit, and otherwise uses `hhea` (`hb-ot-metrics.cc:85`):

```c++
case HB_OT_METRICS_TAG_HORIZONTAL_ASCENDER:
  return (face->table.OS2->use_typo_metrics () && GET_METRIC_Y (OS2, sTypoAscender)) ||
         GET_HEA_METRIC_Y (hhea, ascender);
```

The descender and line gap are chosen the same way. The Windows metrics are never used for font extents. They can be asked for separately, as the “clipping” ascent and descent, by `hb_ot_metrics_get_position` with the tags `hcla` and `hcld`. HarfBuzz also forces the signs: the ascender is made positive and the descender negative, whatever the font says (`hb-ot-metrics.cc:46`).

`metrics.ttf` has an `hhea` ascender and descender of 900 and −300, typographic metrics of 800, −200, and a line gap of 100, and Windows metrics of 950 and 350. `metrics-typo.ttf` is the same font with `USE_TYPO_METRICS` set:

```info
metrics.ttf  --show-extents  --get-metric=hcla
metrics-typo.ttf  --show-extents  --get-metric=hcla
```

If the font has no `hhea` and doesn’t ask for typographic metrics, hb-ot has no answer, and the font object makes one up: an ascender of 0.8 em and a descender of −0.2 em, with no line gap (`hb-font.hh:785`). Vertical font extents come from `vhea` only, and without it are half an em either side.

### MVAR

In a variable font, MVAR can vary any of these numbers. It holds a list of records, each a four-letter tag (`hasc` for the horizontal ascender, `xhgt` for the x-height, and so on) and an index into an item variation store. HarfBuzz finds the record by binary search and adds its delta to the value from `hhea` or `OS/2` before scaling (`hb-ot-var-mvar-table.hh:132`). The same goes for the other metrics `hb_ot_metrics_get_position` can fetch: x-height, cap height, sub- and superscript sizes, strikeout, and underline. The variable test fonts vary their x-height:

```info
variations/var.ttf  --get-metric=xhgt  --variations=wght=100
variations/var.ttf  --get-metric=xhgt  --variations=wght=900
```

When a metric isn’t in the font, `hb_ot_metrics_get_position_with_fallback` guesses: the x-height is the top of the glyph for `x`, the cap height is worked out from the glyph for `O`, and the underline is an eighteenth of an em thick. These fallbacks are for applications. The shaper doesn’t use them.

## Scaling and rounding

Everything above is in font units. The font object has a **scale**, usually set by the application to the size it wants multiplied by some power of two for subpixel precision, and everything hb-ot returns is converted to it at the last moment. HarfBuzz doesn’t hint, so the font’s ppem plays no part in this. In these functions it is read only to choose a bitmap strike.

Integer values are scaled with a 16.16 fixed-point multiplier, and values that can have fractions, such as metrics with MVAR deltas, VORG origins, and origins from phantom points, in floating point. [Fonts and font functions](fonts-and-font-functions.html#the-mults-and-rounding) shows both, and the half that can round down.

Variable advances are different. HVAR’s delta, and the phantom points’ distance, are rounded to a whole font unit *before* they are scaled, because the advance cache stores whole font units. At a large scale, the fraction is lost. The MVAR x-height isn’t rounded first, and keeps it:

```shape
variations/var.ttf  IHV  --variations=wght=777  --font-size=1000000
```

```info
variations/var.ttf  --get-metric=xhgt  --variations=wght=777  --font-size=1000000
```

At weight 777, the `I`’s advance interpolates to about 385.4 units, but at a scale of a million units per em it comes out as exactly 385,000. The x-height, about 522.6 units, comes out to the nearest millionth of an em.

Glyph extents are scaled by `scale_glyph_extents` (`hb-font.hh:201`), which finds the box’s corners in floating point, takes the floor of the left and top edges and the ceiling of the right and bottom ones, and works the width and height out from the rounded corners. At small sizes this shows:

```shape
metrics.ttf  HLp  --font-size=13  --show-extents
```

At 13 units per em, the `H` runs from 1.04 to 6.76 across, and is reported as 1 to 7: wider, so that it covers the ink. Up and down, the same rule has the opposite effect. Because y grows upwards, the top edge is the larger number, and taking its floor moves it down. The `p` runs from −2.73 to 6.5, and is reported as −2 to 6: smaller than its ink at both ends. The 14.2.1 release notes say that extents are scaled “so the reported box always covers the glyph”, and across, it does. Up and down, as of {{hb}}, it doesn’t.

> Since {{hb}}: fixed on HarfBuzz main by [#6707](https://github.com/harfbuzz/harfbuzz/pull/6707) (17 November 2026), so main rounds the box outwards up and down too: the `p` is reported as −3 to 7.

Bitmap extents are converted from the strike’s pixels in two steps, each rounded: from pixels to font units, then from font units to the font’s scale.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-font.cc` | the hb-ot font functions: advances, origins, extents, font extents, and the caches in `hb_ot_font_t` |
| `src/hb-ot-hmtx-table.hh` | `hmtx`, `vmtx`, and their wide versions; the accelerator that fits the counts to the table |
| `src/hb-ot-hhea-table.hh` | `hhea`, `vhea`, and their wide versions |
| `src/hb-ot-var-hvar-table.hh` | HVAR and VVAR, including VVAR’s vertical origin deltas |
| `src/OT/glyf/Glyph.hh`, `src/OT/glyf/glyf.hh` | phantom points, advances and origins from `gvar`, and `glyf` extents |
| `src/OT/glyf/GlyphHeader.hh` | extents from the glyph’s header, with `xMin` replaced by the left side bearing |
| `src/hb-ot-vorg-table.hh` | VORG |
| `src/hb-ot-cff1-table.cc`, `src/hb-ot-cff2-table.cc` | CFF and CFF2 extents |
| `src/OT/Color/COLR/COLR.hh`, `src/OT/Color/CBDT/CBDT.hh`, `src/OT/Color/sbix/sbix.hh` | color and bitmap extents, and strike choice |
| `src/hb-ot-metrics.cc` | font extents, `USE_TYPO_METRICS`, MVAR, and the other metrics with their fallbacks |
| `src/hb-ot-os2-table.hh`, `src/hb-ot-var-mvar-table.hh` | OS/2 and MVAR |
| `src/hb-font.hh` | scaling (`em_mult`, `scale_glyph_extents`) and the font object’s own fallbacks |
| `src/hb-cache.hh` | the small lock-free cache used for advances and origins |

To see these numbers for any font, run `hb-shape` with `--show-extents`, with `--direction=ttb` for vertical metrics, and `hb-info` with `--show-extents` or `--list-metrics` for font-wide ones. `hb-info` marks metrics that came from a fallback rather than the font with an asterisk.

## In short

* Advances come from `hmtx`. Glyphs past the last long metric share its advance, but a glyph with no entry at all gets zero, and a font with no `hmtx` gets half an em for every glyph.
* In a `glyf` font, the left side bearing in `hmtx` wins over the outline’s `xMin`: the outline is moved to match.
* At a non-default location, advances come from HVAR if it’s there and from `gvar`’s phantom points if not. HVAR is believed without being checked, and the phantom points are much slower. Variable advances are cached in whole font units.
* Vertical origins come from VORG, else from `vmtx` with `glyf`, else from centering the glyph’s extents in the line. A CFF font needs VORG.
* Glyph extents are tried from `sbix`, `CBDT`, `COLR`, `VARC`, `glyf`, `CFF2`, and `CFF`, in that order. Outline extents include control points.
* Font extents are `OS/2`’s typographic metrics if `USE_TYPO_METRICS` is set, and `hhea`’s otherwise. The Windows metrics are never used for them. MVAR varies them.
* Scaled extents are rounded outwards across, but inwards up and down.

> Since {{hb}}: fixed on HarfBuzz main by [#6707](https://github.com/harfbuzz/harfbuzz/pull/6707) (17 November 2026), so main rounds scaled extents outwards in both directions (the item on scaled extents).
