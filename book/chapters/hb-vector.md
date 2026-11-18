# hb-vector: rendering to SVG and PDF

The draw and paint APIs end at a callback. HarfBuzz walks the font’s data and calls the client: move here, curve to there, push this clip, fill with that gradient. What the client does with the calls was, for most of HarfBuzz’s life, someone else’s business. Since 13.0.0 HarfBuzz has its own answers, in three separate libraries: [hb-raster](hb-raster.html), which turns glyphs into pixels on the CPU; **hb-vector**, which writes them out as SVG or PDF; and [hb-gpu](hb-gpu.html), which encodes them for a fragment shader to draw. Each is a client of the APIs that [Drawing outlines](drawing-outlines.html) and [Color](color.html) describe, and nothing more: it sees glyphs exactly as an application would, with variations, synthetic bold and slant and the font’s scale already applied, and without hinting.

hb-vector is the one of the three this book uses throughout. Every drawing in it, from the boxes of the GSUB chapter to the gradients of the Color chapter, is a `draw` block, and each block runs the `hb-vector` tool on a test font when the book is built and puts the SVG it writes into the page (`tools/build-site.mjs`). So what the figures show is hb-vector’s output, including, in places, its limits.

The chapter has two halves. The first, Outlines, is all that a client drawing ordinary text needs. The second, Color glyphs, covers COLR gradients, compositing, bitmaps and palettes, and assumes the [Color](color.html) chapter.

## The library

hb-vector is its own shared library, `libharfbuzz-vector`, with one header, `hb-vector.h`, and a [Meson feature option](building-harfbuzz.html#optional-dependencies-and-backends), `vector`, enabled by default (`meson_options.txt:38`). It is a young library. It arrived in 13.0.0, its API was reviewed and changed in 14.2.0, and it has been covered by HarfBuzz’s API and ABI stability only since 15.0.0, so code and articles written for earlier versions may not match it (`NEWS`):

| Version | What happened |
|---|---|
| 13.0.0 | hb-vector arrives, “experimental”, with SVG output only; color glyphs from COLR, `SVG `, `CBDT` and `sbix`; the `hb-vector` tool |
| 13.1.1 | gzip-compressed SVG glyphs, with zlib |
| 14.2.0 | the API review: PDF output; the SVG id prefix; `_clear` functions; funcs getters take the context; `_glyph` functions return nothing, with `_or_fail` twins; glyph paths no longer shared through `<defs>` and `<use>`; SVG glyphs dropped |
| 14.5.0 | the work budget shared with the font code |
| 15.0.0 | “no longer considered experimental”: API and ABI stability apply |
| 15.1.0 | fixes for mirrored path clips in SVG, and for PDF page bounds and misplaced COLR gradients |

It has two contexts. A **draw context**, `hb_vector_draw_t`, turns outlines into filled paths. A **paint context**, `hb_vector_paint_t`, turns the paint calls of a color glyph into layers, clips, gradients and images. Both are ordinary reference-counted HarfBuzz objects, made with `_create_or_fail` and a format, `HB_VECTOR_FORMAT_SVG` or `HB_VECTOR_FORMAT_PDF`, which is fixed for the context’s life. Each context’s funcs getter takes the context, and returns the SVG or the PDF funcs according to its format (`hb-vector-draw.cc:530`, `hb-vector-paint.cc:510`).

A context accumulates many glyphs into one document. The client sets a transform for each glyph, usually a translation to its pen position, and calls `hb_vector_draw_glyph` or `hb_vector_paint_glyph`; at the end, `_render` returns the document as a blob. Here is how the `hb-vector` tool does it for a shaped line, hand-written from `util/vector-output.hh:192–311` and trimmed:

```c
hb_vector_paint_t *paint =
  hb_vector_paint_create_or_fail (HB_VECTOR_FORMAT_SVG);
hb_vector_paint_set_scale_factor (paint, 64.f, 64.f); /* font scale: 64 × size */
hb_vector_paint_set_extents (paint, &extents);        /* of the shaped line */
for (unsigned i = 0; i < count; i++)
{
  hb_vector_paint_set_transform (paint, 1, 0, 0, 1, pen_x[i], pen_y[i]);
  hb_vector_paint_glyph (paint, font, info[i].codepoint,
                         HB_VECTOR_EXTENTS_MODE_NONE);
}
hb_blob_t *svg = hb_vector_paint_render (paint);
```

The document’s bounds are its **extents**, which become the SVG `viewBox` and the PDF media box. The client either sets them, as the tool does, or passes `HB_VECTOR_EXTENTS_MODE_EXPAND`, which unions each glyph’s ink box, under the transform, into them (`hb-vector-internal.hh:185`). A context with no extents renders nothing: `_render` returns `NULL` (`hb-vector-draw.cc:841`). The **scale factor** divides every coordinate on the way out, so a client can give HarfBuzz a font scale of 64 units per pixel, for precise positions, and still get coordinates in pixels.

Rendering clears the context, even when it fails (`hb-vector-draw.cc:935`, `hb-vector-paint.cc:768`), so the extents should be read before it if they are wanted. `_clear` (14.2.0) throws away what has been accumulated and keeps the settings; `_reset` restores the defaults too. `_recycle_blob` hands a finished blob back, and the next render writes into its memory. Every context also implements the budget callbacks of [Drawing outlines](drawing-outlines.html#the-budget), and recharges the budget when it is cleared (`hb-vector-draw.cc:970`). One budget of 2²⁴ therefore covers a whole document, not one glyph: that chapter’s `heavy` glyphs show it running out partway along a line.

The `_glyph` functions are conveniences. `hb_vector_draw_glyph_or_fail (draw, font, glyph, mode)` is documented as `hb_vector_draw_new_path` followed by `hb_font_draw_glyph_or_fail` with the context’s funcs, after the extents update (`hb-vector-draw.cc:563`). A client can drive the funcs itself, to draw shapes of its own into the same document.

## Outlines

### The draw context

The draw context writes one path per glyph, filled with its **foreground** color, opaque black unless set. In SVG each draw callback becomes one path command (`hb-vector-draw.cc:51–89`): `M`, `L`, `Q`, `C` or `Z`. TrueType’s quadratic curves therefore stay quadratic, and CFF’s cubics stay cubic. Here is the book’s variable test font `var.ttf`, from [Design space](design-space.html), with a different foreground for each glyph; the `hb-vector` tool changes the context’s foreground before each glyph when given a list of colors (`util/vector-output.hh:280`):

```draw
font: variations/var.ttf
text: HIH
vector-options: --foreground=C0392B,2E8B57,1B98E0
```

and here is the SVG it wrote, captured when this chapter was written (trimmed; two paths are cut short):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-16 -816 1492 1032" width="1492" height="1032">
<g transform="scale(1,-1)">
<path d="M80,0L80,700L180,700L180,0L80,0ZM420,0L420,700L520,700…Z" fill="#C0392B"/>
<path d="M680,0L680,700L780,700L780,0L680,0Z" fill="#2E8B57"/>
<path d="M940,0L940,700L1040,700L1040,0L940,0ZM1280,0L1280,700…Z" fill="#1B98E0"/>
</g>
</svg>
```

Three things show. SVG’s y axis points down and a font’s points up, so hb-vector writes coordinates as the font has them and wraps the whole body in one `scale(1,-1)` group (`hb-vector-draw.cc:908`); the `viewBox` is the flipped extents. The draw context applies its transform to every point itself (`hb-vector-draw.hh:146`), so the second `H` starts at x = 940, its pen position plus its side bearing, and there is no `<g>` per glyph. And the colors are written as short hex where they can be, with alpha, if any, as a `fill-opacity` (`hb-vector-buf.hh:221`). The path is filled by SVG’s default rule, nonzero, which is what fonts are drawn with.

Each glyph’s path is separate, and the documentation in `hb-vector.cc:73` warns about the consequence: where glyphs overlap and the foreground is semi-transparent, the overlap is darker, because it is painted twice. A client that feeds the funcs itself starts a new path with `hb_vector_draw_new_path` (14.2.0), and setting the foreground closes the current one (`hb-vector-draw.cc:672`), so that colors can change from glyph to glyph.

### Precision

Numbers are written with at most a fixed number of decimal places, the **precision**: 2 by default, at most 12 (`hb_vector_draw_set_precision`, `hb-vector-buf.hh:131`). Trailing zeros are dropped, so a whole number is written as one, and a value that would round to zero is written as `0`, never `-0`. The digits are made with integer arithmetic and the decimal point is always a full stop, whatever the locale (`hb-vector-buf.hh:147–152`). Transform matrices are written with at least 7 places, whatever the precision, so that a small scale isn’t rounded away (`hb-vector-buf.hh:73`).

Precision counts in the output’s units, which are the font’s scale divided by the scale factor. The `hb-vector` tool’s are font units at its `--font-size`, so at a size of 100 per em, precision 0 rounds every point to a hundredth of the em. Here is `spiral64`, from the [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) chapter’s `limits.ttf`, at that size, at precision 0 and then at the default:

```draw
font: drawing-outlines/limits.ttf
text: 1
options: --font-size=100
vector-options: --precision=0 --ink
```

```draw
font: drawing-outlines/limits.ttf
text: 1
options: --font-size=100
vector-options: --ink
```

At precision 0 the small squares near the middle of the spiral have lost their shape: their corners have been pulled to a 100-unit grid. At the default they are square. Output that will be scaled up after the fact, as this book’s figures are, wants a large font scale or a high precision.

### ids and the prefix

The draw context’s SVG has no ids at all. Before 14.2.0 hb-vector wrote each distinct glyph once in `<defs>` and referred to it with `<use>`; that was removed, and every glyph is now written inline (`NEWS`). So any number of draw-context documents can be pasted into one HTML page.

The paint context’s SVG does have ids, for its clips and gradients, and numbers them from zero in every document. Two such documents in one page then fight over the same names. `hb_vector_paint_set_svg_prefix` (14.2.0) puts a string of the client’s choosing in front of every id and every reference to one (`hb-vector-paint.cc:644`). A client that paints all its text, to have one code path, needs it even for plain glyphs, since a paint context wraps a glyph’s outline in a clip whenever the font’s color data asks for one. This book has the same problem, and since the `hb-vector` tool has no option for the prefix, the build adds one to each figure’s ids itself (`tools/build-site.mjs`).

### PDF

The PDF writer (14.2.0) makes a complete one-page PDF 1.4 file, with the extents as its media box (`hb-vector-draw.cc:727`). PDF’s y axis points up, as a font’s does, so nothing is flipped. Each glyph is a fill color (`rg`), its path, and `f`, PDF’s nonzero fill; a semi-transparent foreground gets an ExtGState with `/ca` (`hb-vector-draw.hh:111`). PDF has no quadratic curve, so the PDF funcs leave `quadratic_to` unset, and HarfBuzz’s default turns each quadratic into the identical cubic, as [Drawing outlines](drawing-outlines.html#callbacks-a-client-leaves-out) describes (“No quadratic_to — null fallback auto-promotes to cubic”, `hb-vector-draw.cc:110`).

### Limits

Every document is capped at 16 MiB (`HB_VECTOR_MAX_DOCUMENT_SIZE`, `hb-limits.hh:181`). Once a buffer would pass it, it stops growing, stays in error until the context is cleared, and tells the outline code to stop by emptying the budget (`hb-vector-buf.hh:76`, `hb-vector-draw.hh:74`). The work budget, as above, is per document. A document that hits either limit is cut short, not refused: what was written before is rendered.

## Color glyphs

### The paint context

The paint context is a set of paint funcs, one for SVG and one for PDF. `hb_vector_paint_glyph` pushes the context’s transform, calls `hb_font_paint_glyph` with the context’s palette index and foreground, and pops the transform (`hb-vector-paint.cc:526`). Since `hb_font_paint_glyph` falls back to filling the outline with the foreground ([Color](color.html#the-paint-api)), the paint context draws plain glyphs too; `hb_vector_paint_glyph_or_fail` uses `hb_font_paint_glyph_or_fail` instead and draws nothing for them. The `hb-vector` tool uses its paint context when the font has COLR, `CBDT` or `sbix` data, and its draw context otherwise (`util/vector-output.hh:225`); `--paint` and `--draw` override that.

Unlike the draw context, the paint context writes transforms as transforms: the glyph’s position is a `<g transform="matrix(…)">` in SVG and a `cm` in PDF, and an identity transform is skipped in SVG (`hb-vector-paint-svg.cc:378`).

### Color glyphs in SVG

The SVG paint funcs translate the paint calls one by one into SVG elements, held in two buffers: the body and the `<defs>` the body refers to (`hb-vector-paint-svg.cc:310`).

| Callback | SVG |
|---|---|
| `push_transform` | `<g transform="matrix(…)">` |
| `push_clip_glyph` | the outline as a `<path id="p…">` and a `<clipPath id="clip-p…">` in `<defs>`; `<g clip-path="url(#…)">` |
| `push_clip_rectangle` | a `<rect>` in a `<clipPath id="c…">` |
| `push_clip_path_start`, `_end` | a `<path>` in a `<clipPath id="cp…">` |
| `fill_glyph` | a filled `<path>` |
| `color` | a filled `<rect>` 65,534 units square, cut down by the clip |
| `linear_gradient`, `radial_gradient` | a `<linearGradient>` or `<radialGradient id="gr…">` in `<defs>`, filling the same rectangle |
| `sweep_gradient` | wedges of solid color |
| `image` | PNG only: an `<image>` with the PNG inline, base64 encoded |
| `push_group`, `pop_group` | `<g style="mix-blend-mode:…">` |
| `custom_palette_color` | the context’s overrides |
| `color_glyph` | declined |

Here is the start of `hb-vector`’s output for `M` in the Color chapter’s `colr1.ttf`, two discs composited with MULTIPLY, captured when this chapter was written (trimmed; the path data is cut short):

```xml
<defs>
<clipPath id="c0"><rect x="1.56" y="0" width="12.5" height="12.5"/></clipPath>
</defs>
<g transform="scale(1,-1)">
<g transform="matrix(64,0,0,64,0,0)">
<g clip-path="url(#c0)">
<g style="mix-blend-mode:normal">
<g transform="matrix(0.015625,0,0,0.015625,0,0)">
<path d="M638.5,507Q683,400 638.5,293…Z" fill="#1B98E0"/>
</g>
<g style="mix-blend-mode:multiply">
<g transform="matrix(0.015625,0,0,0.015625,0,0)">
<path d="M878.5,507Q923,400 878.5,293…Z" fill="#D7263D"/>
```

The structure is the paint graph’s. The ClipBox is a clip rectangle; the PaintComposite is two groups, the source inside the backdrop; and each PaintGlyph of a PaintSolid is one filled path, through `fill_glyph`. The 64 and 1/64 are the font transform and its inverse around the glyph ([Color](color.html#the-walk)). The scale factor divides coordinates, but not the entries of matrices, so the ClipBox’s 100 font units appear as 1.56.

### Compositing modes

`pop_group` is where SVG runs short. Its `mix-blend-mode` has the separable and non-separable blend modes of the W3C compositing specification, but none of the Porter–Duff operators, which in SVG would need masks or filters. hb-vector’s answer is a table (`hb-vector-paint-svg.cc:75`):

| COLR mode | SVG |
|---|---|
| SRC_OVER, and the 15 blend modes from SCREEN to HSL_LUMINOSITY | themselves (`normal`, `screen`, …, `luminosity`) |
| PLUS | `screen`, “a plausible color-blend analog” |
| XOR | `difference` |
| CLEAR, SRC, DEST, DEST_OVER, SRC_IN, DEST_IN, SRC_OUT, DEST_OUT, SRC_ATOP, DEST_ATOP | none: the group is painted source-over |

`modes.ttf`, this chapter’s test font, has the same pair of discs, a blue backdrop and a red source, composited with SRC_OVER, SRC_IN, DEST_OUT, XOR, PLUS, SCREEN and DIFFERENCE, on `N`, `I`, `O`, `X`, `P`, `S` and `D`:

```draw
font: modes.ttf
text: NIOXPSD
```

`N`, `I` and `O` are identical, though SRC_IN should leave only the lens where the discs overlap, in red, and DEST_OUT only the blue crescent. `X` is drawn as DIFFERENCE, the same as `D`, where XOR should have left the lens empty. `P` is drawn as SCREEN, the same as `S`; PLUS would have added the colors, which here comes to nearly the same thing. [hb-raster](hb-raster.html) draws all seven as the specification says.

Every color glyph in these fonts also has an outline, the Color chapter’s cut-cornered square. `--draw` forces the draw context, which ignores color and draws the outline:

```draw
font: modes.ttf
text: NIOXPSD
vector-options: --draw
```

### Gradients

SVG’s gradients take their stops at offsets from 0 to 1, and clamp the rest. COLR’s stops can lie anywhere, so hb-vector sorts and rescales them with `hb_paint_normalize_color_line` and moves the gradient’s ends to match, so that the colors stay where they were (`hb-vector-paint-svg.cc:694`). A linear gradient’s three COLR points are reduced to SVG’s two with `hb_paint_reduce_linear_anchors`. The extend mode becomes `spreadMethod`, which has pad, repeat and reflect, so nothing is lost: the Color chapter’s `R` and `F` are drawn with their rings ([Color](color.html#gradients-and-color-lines)).

SVG has no conic gradient. A sweep is cut into tiles by `hb_paint_sweep_gradient_tiles`, which deals with the extend mode, and each tile into wedges no wider than π/16, each a pie slice 32,767 units in radius filled with the color at its middle (`hb-vector-paint-svg.cc:174`). So a sweep in SVG is a fan of flat colors: smooth enough at text sizes, banded when enlarged.

### Images

The `image` callback accepts PNG and nothing else: the PNG is copied into the SVG unchanged, base64 encoded, scaled to the glyph’s extents (`hb-vector-paint-svg.cc:628`). It refuses SVG documents (since 14.2.0) and the raw BGRA images FreeType’s font functions produce. A refusal is part of the protocol: HarfBuzz goes on to the next color table, and finally to the outline, as [Which picture gets painted](color.html#which-picture-gets-painted) shows with `images.ttf`.

### Palettes and the foreground

The palette index is the context’s (`hb_vector_paint_set_palette`, 0 unless set) and is passed to `hb_font_paint_glyph`. Single entries can be overridden with `hb_vector_paint_set_custom_palette_color`, which the SVG funcs report through `custom_palette_color` (`hb-vector-paint-svg.cc:292`). The [Color](color.html#palettes-cpal) chapter shows both, with `hb-vector`’s `--font-palette` and `--custom-palette`.

The foreground color (`hb_vector_paint_set_foreground`) is what HarfBuzz uses for palette entry 0xFFFF, and for plain glyphs painted through the fallback. Here is `colr0.ttf`, whose bar is in entry 0xFFFF, with a red foreground:

```draw
font: color/colr0.ttf
text: AB
vector-options: --foreground=C0392B
```

hb-vector writes the color the paint calls give it, and ignores `is_foreground`, so the foreground is fixed in the document. This book’s build rewrites black fills to `currentColor` (`tools/build-site.mjs`), which is why its drawings follow the color of the text, and why that trick only works for the default foreground.

### Color glyphs in PDF

The PDF paint funcs map the same calls onto PDF’s graphics state (`hb-vector-paint-pdf.cc:389–1646`):

| Callback | PDF |
|---|---|
| `push_transform` | `q` and a `cm` |
| `push_clip_glyph`, `_rectangle`, `_path` | `q`, the path or `re`, then `W n` |
| `color`, `fill_glyph` | `rg` and a fill; alpha by an ExtGState with `/ca` |
| `linear_gradient`, `radial_gradient` | axial and radial shadings (types 2 and 3), with stitched functions for the stops |
| `sweep_gradient` | a mesh of Coons patches (shading type 6) |
| `image` | an image XObject, `Do` |
| `push_group_for`, `pop_group` | `q`, an ExtGState with `/BM` for the mode, then `Q` |

Color stops with alpha get a second, gray shading, used as a luminosity soft mask. Groups use `push_group_for` (14.2.0), which tells the client the compositing mode before the group is painted, since PDF sets the blend mode before painting, not after ([Color](color.html#the-paint-api)). The mode table is SVG’s in PDF’s names, with the same approximations for PLUS and XOR (`hb-vector-paint-pdf.cc:1556`). A sweep is meant to be a closer approximation than SVG’s: each patch interpolates its colors smoothly, so there are no bands. But in {{hb}} the colors are wrong. Each patch’s colors come from `hb_color_lerp` (`hb-paint.hh:292`), which assembles its result with the bytes in reverse order, so a red stop comes out as a cyan-blue: `colr1.ttf`’s `S` is cyan and purple in both poppler and Ghostscript. The same function also colors the SVG tiles of a sweep that crosses 0° or 360°, so those are wrong in SVG too. (The comment at the top of the file still says sweeps are “approximated via solid fallback”: it is out of date.) Extra objects, shadings, functions, soft masks and images, count against the same 16 MiB cap as the content (`hb-vector-paint-pdf.cc:91`).

`NEWS` says what the PDF writer is for: color-glyph artwork “that can be embedded directly in PDF documents. Useful for PDF producers such as LibreOffice.” In {{hb}} it falls short in five ways. The book’s figures can’t show PDF; the results below come from `hb-vector -O pdf` on the Color chapter’s fonts and this chapter’s, rendered with poppler’s `pdftoppm` while this chapter was written.

* **Extend modes.** PDF’s axial and radial shadings can stop at their ends or pad beyond them, and nothing else. hb-vector pads when the color line says pad, and otherwise stops (`hb-vector-paint-pdf.cc:1098, 1199`), so a repeating or reflecting gradient is painted only between its first and last stops. `R` and `F` in `colr1.ttf` become the inner disc alone. Repeating would need the stops written out over the whole visible range.
* **Compositing is not isolated.** The blend mode is set in the graphics state and the group is only a `q`…`Q`, not a transparency group, so the source blends with everything already on the page, not only with its backdrop (inferred from the code at `hb-vector-paint-pdf.cc:1607`). In `modes.ttf`, the part of `S`’s red disc outside the overlap blends with the white page and disappears, and `D`’s turns cyan. In SVG, in Chrome at least, the same glyphs keep their red, presumably because the ClipBox’s clip group is a stacking context, which isolates what is inside it (inferred).
* **PNG alpha.** PNG images are embedded without being decoded: the compressed image data is copied into the PDF with a matching predictor, which keeps the file small, and only 8-bit PNGs are accepted (`hb-vector-paint-pdf.cc:806`). An indexed PNG with transparency gets a soft mask, built with zlib. But for an RGBA or gray-and-alpha PNG the alpha is ignored (`(void) has_alpha`, `:305`): the image is declared as RGB or gray, while its data still has four or two components per pixel. The RGBA PNG of `P` in `images.ttf` comes out as stripes, where the SVG shows a green disc. Bitmap color glyphs are nearly always RGBA. `NEWS` for 14.2.0 promises “PNG images with transparency”, so this is a bug.
* **Custom palettes.** The PDF funcs don’t set `custom_palette_color` at all (`hb-vector-paint-pdf.cc:1650`), so `hb_vector_paint_set_custom_palette_color` has no effect on PDF. `colr0.ttf` with `--custom-palette=1=#2E8B57` has a green disc in SVG and a blue one in PDF. This too looks like a bug.
* **Sweeps near their center.** Each Coons patch runs from half a unit to 32,767 units from the center. Both poppler and Ghostscript leave a square hole about 64 units wide at the center of `S` in `colr1.ttf`, and the cause is the mesh’s coordinates, not the renderers: they are stored in 16 bits over a range of 65,536 units and painted under a scale of 64, so the grid they snap to is 64 font units, and the patches’ inner ends, half a unit from the center, round to the corners of one unpainted grid square.

### Limits for color glyphs

The SVG writer nests transforms at most 64 deep, and ignores further ones, and their pops, until it is back within the limit (`hb-vector-paint-svg.cc:372`); the PDF writer has no such limit. Both decline `color_glyph`, so a PaintColrGlyph is painted inline under COLR’s own guards, instead of starting a fresh walk, with fresh limits, for every reference: a graph that fans out f ways over n levels would otherwise be walked fⁿ times (`hb-vector-paint-svg.cc:891`). When the budget is spent, outlines are skipped but the document’s structure is kept, so a glyph clip with no outline clips everything out (`hb-vector-paint-svg.cc:474`). Sweep meshes and images, which the budget can’t see, are bounded by the 16 MiB cap.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-vector.h`, `src/hb-vector.cc` | the API, its overview documentation, and the locale’s decimal point |
| `src/hb-vector-draw.hh`, `src/hb-vector-draw.cc` | the draw context; SVG and PDF path callbacks; writing the two document formats, 727 and 838 |
| `src/hb-vector-path.hh`, `src/hb-vector-path.cc` | the path sink the paint context draws clips and fills through |
| `src/hb-vector-paint.hh`, `src/hb-vector-paint.cc` | the paint context, its settings, the SVG id prefix |
| `src/hb-vector-paint-svg.cc` | SVG paint callbacks: the compositing table, 75; sweep wedges, 174; rendering, 903 |
| `src/hb-vector-paint-pdf.cc` | PDF paint: ExtGStates, shadings, Coons meshes, embedded PNGs; rendering, 1697 |
| `src/hb-vector-buf.hh` | the output buffer, its 16 MiB cap, and locale-free numbers |
| `src/hb-vector-internal.hh` | blob recycling, transforms and extents shared by both contexts |
| `src/hb-limits.hh` | `HB_VECTOR_MAX_DOCUMENT_SIZE`, 181, and the budgets |
| `util/hb-vector.cc`, `util/vector-output.hh` | the tool, and how it drives its contexts |

## In short

* hb-vector is a separate library, from 13.0.0 and stable since 15.0.0, that writes glyphs as SVG or PDF. It draws every figure in this book.
* A draw context writes one filled path per glyph, with the transform applied to the points: quadratics stay quadratic in SVG and become cubics in PDF. Numbers have at most `precision` decimals, counted in output units, and never a locale’s comma.
* Contexts gather a whole document between renders: one set of extents, one work budget, one 16 MiB cap.
* A paint context writes a color glyph’s paint calls as nested groups, clips, gradients and inline PNGs. Its ids need `hb_vector_paint_set_svg_prefix` when documents share a page; the draw context’s output has none.
* SVG has the blend modes but no Porter–Duff operators: PLUS and XOR become screen and difference, and the rest source-over. Sweeps become fans of flat wedges.
* PDF keeps sweeps smooth but, in {{hb}}, paints them in the wrong colors with a hole at the center, loses repeat and reflect, composites without isolation, drops the alpha of RGBA PNGs, and ignores custom palette colors.
