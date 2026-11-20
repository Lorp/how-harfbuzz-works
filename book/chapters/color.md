# Color

A font can hold more than one picture of a glyph. Besides the outline there may be a set of colored layers, a graph of gradients, clips, and transforms, a PNG image at one or more sizes, or a whole SVG document. OpenType has five tables for these: `COLR` (in two very different versions) with its palettes in `CPAL`, `sbix`, `CBDT` with its index `CBLC`, and `SVG `. They were added at different times by different companies, and a font usually has one of them, sometimes two.

HarfBuzz doesn’t shape with any of them: shaping only needs glyph IDs and advances. What it offers is a way of *painting* a glyph, the paint API, which turns whichever color data a font has into one sequence of calls to the client: push a transform, clip to this glyph, fill with this gradient, composite this group. The client turns those calls into pixels, PDF operators, or SVG elements. HarfBuzz’s own renderers are clients like any other ([hb-raster](hb-raster.html), [hb-vector](hb-vector.html), and [hb-gpu](hb-gpu.html)), and so is the extents code that [Where metrics come from](where-metrics-come-from.html#glyph-extents) described.

The drawings on this page come from four small fonts built with fontTools from `fonts/color/build-color-fonts.py`, and one from HarfBuzz’s own test suite. Each color glyph in the chapter’s fonts also has an ordinary outline, a black square with one corner cut off, so that a drawing shows at once when HarfBuzz has fallen back to it.

## The paint API

`hb_paint_funcs_t` is a table of callbacks, built the same way as the font functions of [Fonts and font functions](fonts-and-font-functions.html): `hb_paint_funcs_create`, one setter per callback, each with its own user data, then `hb_paint_funcs_make_immutable`. A callback left unset does nothing, or returns false. The list is in `hb-paint.hh:33`:

| Callback | Since | What the client does |
|---|---|---|
| `push_transform`, `pop_transform` | 7.0.0 | multiply the current transform by a 2×3 matrix; restore it |
| `push_clip_glyph`, `push_clip_rectangle`, `pop_clip` | 7.0.0 | intersect the clip with a glyph’s outline or a rectangle; restore it |
| `color` | 7.0.0 | fill everything inside the current clip with one color |
| `linear_gradient`, `radial_gradient`, `sweep_gradient` | 7.0.0 | fill everything inside the clip with a gradient |
| `image` | 7.0.0 | paint a PNG, BGRA, or SVG image |
| `push_group`, `pop_group` | 7.0.0 | paint into a new layer; composite it onto the one below with a given mode |
| `custom_palette_color` | 7.0.0 | optionally replace a palette entry |
| `color_glyph` | 8.2.0 | optionally paint a whole color glyph itself |
| `push_group_for` | 14.2.0 | `push_group`, but told the compositing mode in advance |
| `push_clip_path_start`, `push_clip_path_end` | 14.2.0 | clip to an arbitrary path, drawn through the returned draw funcs |
| `fill_glyph` | 14.3.0 | fill a glyph’s outline with one color |
| `set_budget`, `get_budget`, `get_budget_remaining` | 14.5.0 | share a work budget with HarfBuzz |

The calls are always properly nested, as the header comment in `hb-paint.h` promises, so a client can keep transforms, clips, and groups on a single stack. Nothing in the API is a scene description that the client could inspect as a whole: HarfBuzz walks the font’s data and calls back as it goes, and the client renders, or measures, as the calls arrive.

Two entry points start the walk. **`hb_font_paint_glyph_or_fail`** (11.2.0) paints the glyph’s color version and returns false if there is none. **`hb_font_paint_glyph`** (7.0.0) does the same but never fails: if there is no color version, it calls `fill_glyph` with the outline and the foreground color (`hb-font.cc:1687`). So every glyph with an outline can be painted, and a client that only wants one code path for text can paint everything. Both take a palette index and a **foreground color**, the color the text would be in if it had no color of its own.

Colors are `hb_color_t`, 32 bits holding blue, green, red, and alpha, with the components not premultiplied. Every color callback also gets an `is_foreground` flag. When it’s set, the color came from the font’s “use the text color” sentinel, and the color passed is already the foreground with the paint graph’s own alpha applied. A client that renders the same glyph in several text colors, or that leaves the color to CSS, can substitute its own foreground there, keeping the alpha, as the comment on `hb_paint_color_func_t` explains.

Some callbacks have defaults that call others. The default `fill_glyph` is `push_clip_glyph`, `color`, and `pop_clip` (`hb-paint.cc:64`); a client implements `fill_glyph` itself only to fill an outline more cheaply than by clipping. The default `push_group_for` calls `push_group` (`:145`). `push_clip_glyph` hands over only a glyph ID and the font: the client fetches the outline itself, through the draw API of [Drawing outlines](drawing-outlines.html), at the font’s scale and through the current transform.

> For programmers: what a client must implement depends on what it will meet. An outline glyph needs only `fill_glyph` or the clip and color callbacks. COLR version 0 needs no more. Version 1 needs transforms, rectangle clips, gradients, and groups. `image` is needed only for bitmap and SVG fonts. The rest are optional.

Not everything in `hb-paint.h` is for fonts. Nothing in HarfBuzz’s font code calls `push_clip_path_start`: it’s for clients that drive a renderer themselves, such as the extents overlay in `util/`. And three functions from 14.2.0 help renderers turn COLR’s gradients into the forms other graphics libraries expect: `hb_paint_reduce_linear_anchors`, `hb_paint_normalize_color_line`, and `hb_paint_sweep_gradient_tiles`. They come up with the gradients below.

Two other paint-funcs implementations live inside HarfBuzz and aren’t public. `hb-paint-extents.cc` keeps a stack of clip boxes and transforms and records the box that paint would cover, which is how a COLR glyph without a ClipBox gets its extents. `hb-paint-bounded.cc` only answers whether a paint graph is bounded, a question that comes up with ClipBoxes below.

## Which picture gets painted

The hb-ot font functions paint a glyph with `hb_ot_paint_glyph_or_fail` (`hb-ot-font.cc:951`). Trimmed of its `#ifdef`s, and with `font->face->table` shortened, it is a list:

```c++
auto &t = font->face->table;
if (t.COLR->paint_glyph (font, glyph, paint_funcs, paint_data,
                         palette, foreground)) return true;
if (t.SVG->paint_glyph (font, glyph, paint_funcs, paint_data)) return true;
if (t.sbix->paint_glyph (font, glyph, paint_funcs, paint_data)) return true;
if (t.CBDT->paint_glyph (font, glyph, paint_funcs, paint_data)) return true;
return false;
```

COLR first, then SVG, then the two bitmap tables. COLR answers for itself. The other three answer with whatever the client’s `image` callback returns (`svg.hh:235`, `sbix.hh:248`, `CBDT.hh:1089`). An `image` callback that returns false is saying “I can’t paint this”, and HarfBuzz goes on to the next table, then, in `hb_font_paint_glyph`, to the outline. That makes refusing an image part of the protocol, not an error.

The font `images.ttf` shows it. `S` has an SVG document, `T` has an SVG document and an `sbix` bitmap, `P` has only the bitmap, and `N` has nothing but its outline:

```draw
font: images.ttf
text: STPN
```

hb-vector, like hb-raster, refuses SVG images (since 14.2.0, below), so `S` falls back to its outline and `T` to its bitmap, the green disc. Glyph extents are tried from `sbix`, `CBDT`, then `COLR` ([Where metrics come from](where-metrics-come-from.html#glyph-extents)), and `hb_ot_color_glyph_reference_png` tries `sbix` before `CBDT` too (`hb-ot-color.cc:417`). Before 15.2.0, painting tried `CBDT` first, so for a glyph in both tables the picture painted and the extents and image reported could come from different tables ([HHW-26](bugs-this-book-found.html#hhw-26)).

## Palettes: CPAL

`COLR` doesn’t store colors. It stores indices into a **palette**, and `CPAL` holds the palettes: a font may have several, each with the same number of entries, so that a glyph can be drawn in another color scheme by choosing another palette. Each entry is four bytes, blue, green, red, alpha. HarfBuzz reads it as a big-endian 32-bit number, which is exactly `hb_color_t`’s layout, so a palette is an array of colors with no conversion (`CPAL.hh:190`). Version 1 of the table adds, for each palette, a type (usable on a light background, on a dark one, or neither stated) and a name ID in the `name` table, and a name ID for each entry. `hb-info` lists them:

```info
colr0.ttf  --list-palettes
```

The palettes aren’t stored one by one. `CPAL` has a single array of color records, and each palette is a starting index into it (`colorRecordIndices`), so every palette has the same number of entries, and two palettes could start at the same record or overlap to share colors. In `colr0.ttf` there are four records, and the two palettes start at records 0 and 2. TTX shows the palettes as a reader would think of them, each with its own colors:

```table
font: colr0.ttf
table: CPAL
```

The API is `hb_ot_color_has_palettes`, `hb_ot_color_palette_get_count`, `hb_ot_color_palette_get_colors`, `hb_ot_color_palette_get_flags`, `hb_ot_color_palette_get_name_id`, and `hb_ot_color_palette_color_get_name_id`, all from 2.1.0. They report what the font says and choose nothing. The palette a glyph is painted with is the index the client passes to `hb_font_paint_glyph`. HarfBuzz doesn’t look at the types to choose one for a dark background: that is the client’s job, and HarfBuzz’s own tools use palette 0 unless told otherwise. A palette index the font doesn’t have also means palette 0 (`COLR.hh:104`, after HarfBuzz issue #5116). An entry index past the end of the palette reads as zero, which is transparent black (`hb-array.hh:88`).

Here is `colr0.ttf` with palette 0, and then with palette 1, the one marked for a dark background, chosen with hb-vector’s `--font-palette`:

```draw
font: colr0.ttf
text: AB
```

```draw
font: colr0.ttf
text: AB
vector-options: --font-palette=1
```

The client can also override single entries. Before it reads a palette entry, HarfBuzz calls `custom_palette_color` with the entry’s index, and uses the color the client gives if it returns true (`COLR.hh:138`). hb-vector’s `--custom-palette` works this way: here entry 1, “Disc”, is replaced with green in palette 0, and entry 0 keeps the palette’s color:

```draw
font: colr0.ttf
text: AB
vector-options: --custom-palette=1=#2E8B57
```

Entry 0xFFFF is never looked up: it is the foreground.

> For type designers: palette 0 is what a client gets unless it chooses another, so it should be the palette that works on the most common background. The light and dark flags in CPAL version 1 are information for an application to act on; HarfBuzz itself passes them on and does nothing else with them.

## COLR version 0: layers

Version 0 of `COLR` is a list of base glyphs, each with a run of layer records, and each layer record is a glyph ID and a palette entry. The base glyph is drawn by filling each layer glyph’s outline, in order, bottom first. In `colr0.ttf`, `A` is a square in entry 0, a disc in entry 1, and a bar in entry 0xFFFF; `B` has the same layers with the square last, so it covers the others, as the drawings above show.

HarfBuzz paints a version 0 glyph with one `fill_glyph` per layer (`COLR.hh:3276`), each with the layer’s color, or with the foreground color and `is_foreground` set for entry 0xFFFF. The bar takes the foreground color, which hb-vector draws as black and this book shows in the color of its text. Nothing else is called: no transform, no clip, no group. `hb_ot_color_glyph_get_layers` returns the same layer list for clients that want to do it all themselves, as they had to before 7.0.0.

## COLR version 1: the paint graph

Version 1 keeps version 0’s lists, for older readers, and adds a **paint graph** for each base glyph. Each node is a Paint table, one of 33 formats, and most have a child offset, so the graph is a tree that can share subtrees. Five lists hang off the table header: the BaseGlyphList, from base glyph to root Paint; the LayerList, of Paints shared between glyphs; the **ClipList**, of boxes per glyph range; and, for variable fonts, a DeltaSetIndexMap and an ItemVariationStore. A glyph in the BaseGlyphList is painted from its graph, and only a glyph that isn’t is looked up in the version 0 list (`COLR.hh:3225`).

The formats come in families, nearly all in pairs of a fixed format and a variable one:

| Formats | Paint | Callbacks HarfBuzz makes |
|---|---|---|
| 1 | ColrLayers | its layers from the LayerList, painted in turn |
| 2, 3 | Solid | `color` |
| 4, 5 | LinearGradient | `linear_gradient` |
| 6, 7 | RadialGradient | `radial_gradient` |
| 8, 9 | SweepGradient | `sweep_gradient` |
| 10, 33 | Glyph | `push_clip_glyph` … `pop_clip`, or `fill_glyph` |
| 11 | ColrGlyph | `color_glyph`, or the other glyph’s graph |
| 12–31 | Transform, Translate, Scale (four kinds), Rotate (two), Skew (two) | `push_transform` … `pop_transform` |
| 32 | Composite | two groups |

Format 33 is PaintGlyph with a 24-bit glyph ID, for fonts beyond 65,535 glyphs; a build with `HB_NO_BEYOND_64K` leaves it out. In the `Paint` union (`COLR.hh:2267`) each variable format is the fixed one wrapped in `Variable<T>`, which adds one field, `varIdxBase`; the fixed one is wrapped in `NoVariable<T>`, which supplies `0xFFFFFFFF`, “no variation”, so that one `paint_glyph` serves both.

### The walk

`COLR::paint_glyph` (`COLR.hh:3202`) starts every version 1 glyph the same way. It pushes the font transform, a scale from font units to the font’s scale, so the whole graph can be painted in font units. If the glyph has a ClipBox, it pushes a rectangle clip. Then it calls `recurse` on the root Paint, which dispatches on the format, and each format calls back and recurses into its children. A transform, say, is a push, a recursion, and a pop:

```c++
void paint_glyph (hb_paint_context_t *c, uint32_t varIdxBase) const
{
  float ddx = dx + c->instancer (varIdxBase, 0);
  float ddy = dy + c->instancer (varIdxBase, 1);

  c->funcs->push_translate (c->data, ddx, ddy);
  c->recurse (this+src);
  c->funcs->pop_transform (c->data);
}
```

(`PaintTranslate`, trimmed.) The other transforms are the same, with `push_scale`, `push_rotate`, `push_skew`, or their “around center” forms, which conjugate the transform with a translation. Angles are F2DOT14 numbers in half-turns: 0.5 is 90°. An Affine2x3 is passed through as six numbers.

**PaintGlyph** is where an outline enters, and where the [Drawing outlines](drawing-outlines.html) chapter takes over. `push_clip_glyph` expects the outline at the font’s scale, not in font units, so HarfBuzz pushes the inverse font transform around it, then pushes the font transform again for the child (`COLR.hh:3325`). When the child is a PaintSolid, as it is for most layers, it calls `fill_glyph` instead of a clip, a fill, and a pop.

**PaintColrGlyph** paints another color glyph inside this one, as a component. HarfBuzz first offers it to the client through `color_glyph`, so that a client that has cached that glyph’s rendering can use it; if the client returns false, HarfBuzz paints the other glyph’s graph itself, inside that glyph’s ClipBox (`COLR.hh:3366`).

**PaintComposite** paints its backdrop in one group and its source in a second group, inside the first, then pops the source with the composite mode and the backdrop with ordinary source-over (`COLR.hh:1961`). The modes are the 28 of the W3C compositing specification, numbered as in `hb_paint_composite_mode_t`; a number HarfBuzz doesn’t know becomes CLEAR, as a comment on the struct says it should.

```draw
font: colr1.ttf
text: XMG
```

`X` and `M` are the same two discs composited with DEST_OUT and with MULTIPLY. MULTIPLY darkens the overlap. DEST_OUT should leave only the part of the blue disc the red one doesn’t cover, a crescent, but the drawing shows both discs: HarfBuzz asked for DEST_OUT, and hb-vector’s SVG writer has no way to say it. SVG’s `mix-blend-mode` has the blend modes but none of the Porter–Duff ones, so it draws them as ordinary source-over, except PLUS and XOR, which it approximates with `screen` and `difference` (`hb-vector-paint-svg.cc:75`, and [hb-vector](hb-vector.html#compositing-modes)). `G` is a PaintColrGlyph of `L`, below, inside a PaintRotateAroundCenter of 30°.

### Gradients and color lines

A gradient’s colors are a **color line**: a list of stops, each an offset, a palette entry, and an alpha, plus an **extend mode** that says what happens beyond the first and last stop: pad with the end colors, repeat, or reflect. HarfBuzz doesn’t copy the stops for the client. It passes an `hb_color_line_t`, which the client reads with `hb_color_line_get_color_stops` and `hb_color_line_get_extend` during the callback, and only then: the stops are resolved against the palette, the custom palette, and the variation coordinates as they are read (`COLR.hh:631`). The offsets needn’t lie between 0 and 1, nor be sorted. `hb_paint_normalize_color_line` sorts them and rescales them to 0–1 for libraries that need that. The stops are given unpremultiplied, but, as the documentation of `hb_color_stop_t` notes, the specification says to interpolate between them in premultiplied color.

```draw
font: colr1.ttf
text: LPRFS
```

*Linear* (`L`, a smaller square than the others, so that it stays inside the ClipBox when `G` and `V` turn it): three points. The gradient runs from P0 to P1, and P2 sets the angle of the lines of equal color, which run parallel to P0–P2, so a skewed gradient needs no transform. Most graphics libraries want two points instead, and `hb_paint_reduce_linear_anchors` computes them. *Radial* (`P`, `R`, `F`): two circles, color 0 on the first and color 1 on the second. Here the first has radius 0 and the second radius 160, so the extend mode decides everything outside the second circle: pad, repeat, and reflect, from left to right. *Sweep* (`S`): a center and two angles. The font stores each angle less 180°, in half-turns, so that the F2DOT14 range covers 0° to 360°; HarfBuzz adds the half-turn back and passes radians (`COLR.hh:1212`). `hb_paint_sweep_gradient_tiles` cuts a sweep into wedges, for renderers that have no conic gradient.

### ClipBoxes, and unbounded paint

A ClipBox is a rectangle per glyph range, in the ClipList. It does two jobs: it tells a renderer how big a surface the glyph needs, and it gives the glyph its extents without painting it ([Where metrics come from](where-metrics-come-from.html#glyph-extents)). It has a variable form, whose deltas are rounded outwards. HarfBuzz clips to it whenever it exists. The Null ClipRecord isn’t all zeros, for the reason [Fonts as bytes](fonts-as-bytes.html) gives.

A glyph without one may have a graph that paints everywhere: a PaintSolid with no PaintGlyph above it fills the whole plane. Before painting such a glyph, HarfBuzz runs its graph through the bounded-paint context first, which follows the specification’s rules for boundedness: a fill is unbounded unless a clip is active, and each composite mode combines its two sides in its own way (`hb-paint-bounded.hh:71`). If the graph is unbounded, HarfBuzz paints nothing at all, but still reports success. `U` is a PaintSolid with no ClipBox; `C` is the same PaintSolid with one:

```draw
font: colr1.ttf
text: UC
```

`U` paints nothing. Its extents are zero, too, because COLR answers for them before the outline is asked:

```shape
colr1.ttf  UC  --show-extents
```

> For type designers: give every COLR version 1 glyph a ClipBox. It costs a few bytes and saves every renderer a walk of the graph just to find out how big the glyph is. fontTools’ `buildCOLR` takes them as `clipBoxes`.

### Variable paints

In a variable format, `varIdxBase` is the index of the first delta set; the paint’s varying fields use consecutive ones, in order. `PaintVarTranslate` has two, dx at `varIdxBase` and dy at `varIdxBase + 1`, which is what the `instancer (varIdxBase, 1)` above reads. Each color stop of a variable color line has a base of its own, for its offset and alpha. If the table has a DeltaSetIndexMap, each index is mapped through it first; if not, it is used as an index into the item variation store directly (`hb-ot-layout-common.hh:4325`). At the default location no deltas are applied at all. The store is the same machinery as everywhere else ([Deltas](deltas.html)), and the deltas are in the units of the field: an angle’s delta of 8192 is half a turn of F2DOT14, 90°.

`V` in `colr1.ttf` is `L` inside a PaintVarRotateAroundCenter whose angle is 0, plus a delta of 8192 at the end of the SPIN axis:

```draw
font: colr1.ttf
text: V
slider: SPIN 0 1 0.125
print: 0 0.5 1
```

The square turns from 0° at SPIN 0 to 45° at 0.5 and 90° at 1.

### Guards

A paint graph is a graph, and fonts can make it cyclic or enormous. The [sanitizer](trust-nothing-the-sanitizer.html) checks Paint tables to a depth of 64 and charges PaintComposite against its operation budget, but it can’t see cycles that go through a glyph ID, so painting has guards of its own, in `hb_paint_context_t` (`COLR.hh:65`):

* `recurse` stops at a depth of 64 (`HB_MAX_NESTING_LEVEL`) and after 16,384 Paints in all (`HB_MAX_GRAPH_EDGE_COUNT`) (`COLR.hh:3315`).
* Two cycle detectors, one for glyph IDs reached through PaintColrGlyph and one for layer indices reached through PaintColrLayers, refuse to enter one twice on the same path. They are `hb_decycler_t`: Floyd’s tortoise and hare, adapted to a depth-first walk, which needs no memory beyond the stack (`hb-decycler.hh`).
* A work budget, shared with the client. If the paint funcs offer `get_budget_remaining`, HarfBuzz charges the client’s counter, so outline drawing, painting, and the client’s own work share one limit; otherwise it uses its own, `HB_BUDGET_GLYPH`, 2<sup>25</sup>. Each color stop read costs 16, and once the budget is spent, `recurse` paints no more. [Drawing outlines](drawing-outlines.html) describes the budgets.

Version 1 glyphs and synthetic bold and slant meet in [Fonts and font functions](fonts-and-font-functions.html#slant): the slant is one transform pushed around the whole glyph, and the glyph’s layers are painted with a sub-font that has the synthetic settings turned off (`COLR.hh:115`), so that nothing is slanted twice.

## Bitmaps: sbix and CBDT

`sbix`, Apple’s table, and `CBDT` with `CBLC`, Google’s, store bitmaps in **strikes**, one per size in pixels per em. HarfBuzz chooses the strike as [Where metrics come from](where-metrics-come-from.html#glyph-extents) describes: the smallest at least as big as the font’s ppem, or the largest if none is, or if the font has no ppem set (`sbix.hh:282`). `P` in `images.ttf` has a strike at 10 ppem, with an 8-pixel image, and one at 100 ppem, with an 80-pixel image. The first drawing has no ppem set, the second `--font-ppem=10`:

```draw
font: images.ttf
text: P
```

```draw
font: images.ttf
text: P
options: --font-ppem=10
```

The `image` callback gets the image, untouched, in a blob; its width and height in pixels; the format tag; and the glyph’s extents at the font’s scale. HarfBuzz pushes no transform for an image. The client scales the pixels to fill the extents, which already include the origin offsets and the strike’s scale. Only PNG is handed over, as `HB_PAINT_IMAGE_FORMAT_PNG`:

* From `sbix`, only images whose graphic type is `png `. A `dupe` record, which says “the same image as glyph *n*”, is followed, up to eight times (`sbix.hh:121`). JPEG, TIFF, and the rest are ignored, as is the table’s flag that asks for the outline to be drawn as well.
* From `CBDT`, the PNG image formats, 17, 18, and 19 (`CBDT.hh:1038`), found through CBLC index subtables of formats 1, 2, 3, and 5 (`CBDT.hh:396`); format 4 isn’t read. The uncompressed bitmap formats `CBDT` inherits from `EBDT` aren’t read. HarfBuzz paints an image only if it can also find its extents. Formats 17 and 18 carry their metrics beside the image; format 19 keeps them in the index, in subtable formats 2 and 5, which HarfBuzz reads since 15.2.0 (`CBDT.hh:384`). Before, a format 19 image could be fetched but wasn’t painted ([HHW-25](bugs-this-book-found.html#hhw-25)). The subsetter still writes only index formats 1 and 3, and leaves out the subtables of the others (`CBDT.hh:689`). Only the first 256 strikes are considered when one is chosen (`HB_CBLC_MAX_STRIKES`, `hb-limits.hh:198`).

`HB_PAINT_IMAGE_FORMAT_BGRA`, raw premultiplied pixels, never comes from the hb-ot font functions. FreeType’s functions (`hb-ft.cc`) produce it, from what FreeType has already decoded. A `CBDT` font from HarfBuzz’s test suite, a subset of Noto Color Emoji with a single 109-ppem strike:

```draw
font: hb:test/api/fonts/NotoColorEmoji.subset.ttf
text: 89®
```

That font has no `glyf` table, so it has no outlines to fall back to. Outside painting, `hb_ot_color_has_png` and `hb_ot_color_glyph_reference_png` (2.1.0) fetch the same PNGs for clients that want them directly; set the font’s ppem first, or they return the largest.

## SVG

HarfBuzz doesn’t render SVG. When a glyph has a document in the `SVG ` table, painting it is one call: `image`, with the format `HB_PAINT_IMAGE_FORMAT_SVG`, a width and height of zero, and no extents (`svg.hh:235`). The blob is the whole document as the font stores it. It may be gzip-compressed, and it may hold many glyphs, each in an element whose `id` is `glyph` and the glyph ID; finding the right one, and drawing it, is the client’s job. `hb_ot_color_glyph_reference_svg` returns the same blob, and since 12.1.0 and 13.0.0 `hb_ot_color_get_svg_document_count`, `hb_ot_color_glyph_get_svg_document_index`, and `hb_ot_color_get_svg_document_glyph_range` say which document covers which glyphs.

HarfBuzz’s own renderers rendered SVG glyphs for a while: 13.0.0 introduced them with SVG support, and 13.1.1 added gzip. 14.2.0 dropped it from both (`NEWS`), and their `image` callbacks now refuse SVG, which is why `S` above was drawn as its outline. Code to decompress and index documents is still in `svg.hh`, but nothing in {{hb}} calls it. Nor does HarfBuzz read extents from an SVG document: an SVG glyph has its outline’s extents.

## Compiled out

A build with `HB_NO_PAINT` has no paint API, and `HB_NO_DRAW` implies it. `HB_NO_COLOR` removes the color tables and `hb-ot-color.cc`; `HB_NO_SVG` removes only `SVG `; and `HB_NO_BITMAP` (through `HB_NO_OT_FONT_BITMAP`) removes `sbix` and `CBDT` from the font functions. `HB_LEAN` turns color, drawing, and painting off unless the build also makes one of the cairo, raster, vector, or GPU libraries (`hb-config.hh:85`). The [Compile-time configuration](compile-time-configuration.html) appendix has the rest.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-paint.h`, `src/hb-paint.hh`, `src/hb-paint.cc` | the callbacks, their defaults, color lines, composite modes, and the gradient helpers |
| `src/hb-paint-extents.{hh,cc}`, `src/hb-paint-bounded.{hh,cc}` | the internal paint funcs that measure a paint graph and decide whether it is bounded |
| `src/hb-ot-font.cc` | `hb_ot_paint_glyph_or_fail`: the order of the tables |
| `src/hb-font.cc`, `src/hb-font.hh` | `hb_font_paint_glyph` and its fallback to the outline; synthetic slant around paint |
| `src/OT/Color/COLR/COLR.hh` | versions 0 and 1: every Paint format, color lines, ClipList, the paint context and its guards |
| `src/OT/Color/CPAL/CPAL.hh` | palettes, types, and labels |
| `src/OT/Color/sbix/sbix.hh`, `src/OT/Color/CBDT/CBDT.hh` | strikes and PNG images |
| `src/OT/Color/svg/svg.hh` | SVG documents |
| `src/hb-ot-color.h`, `src/hb-ot-color.cc` | the `hb_ot_color_*` API |
| `src/hb-decycler.hh` | the cycle detector |

## In short

* The paint API turns any kind of color glyph into one nested sequence of callbacks: transforms, clips, fills, gradients, images, and groups. The client renders; HarfBuzz walks the font’s data.
* HarfBuzz tries COLR, then SVG, then sbix, then CBDT. An `image` callback that returns false passes the glyph on to the next table, and `hb_font_paint_glyph` ends with the outline.
* CPAL palettes are arrays of `hb_color_t`. The client chooses the palette; HarfBuzz defaults to none of them except 0, and entry 0xFFFF is the foreground color.
* COLR version 0 is a `fill_glyph` per layer. Version 1 is a graph of 33 Paint formats, walked in font units under the font transform, clipped to its ClipBox, and painted not at all if it is unbounded.
* Variable paints read consecutive delta sets from `varIdxBase`. Depth, size, cycles, and work are all limited while painting.
* Bitmaps are handed over as PNG blobs from the chosen strike, with their extents. SVG documents are handed over whole, and HarfBuzz’s own renderers refuse them.
