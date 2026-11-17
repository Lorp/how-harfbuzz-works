# Rendering

The draw and paint APIs end at a callback. HarfBuzz walks the font’s data and calls the client: move here, curve to there, push this clip, fill with that gradient. What happens next was, for most of HarfBuzz’s life, someone else’s business: FreeType, cairo, Skia or the platform turned the callbacks into pixels. Since 13.0.0 HarfBuzz has its own answers, in three separate libraries: **hb-raster**, which turns glyphs into pixel images on the CPU; **hb-vector**, which writes them out as SVG or PDF; and **hb-gpu**, which encodes them so that a fragment shader can draw them on the GPU.

All three are clients of the APIs that [Drawing outlines](drawing-outlines.html) and [Colour](colour.html) describe, and nothing more. They see the glyphs exactly as an application would: with variations, synthetic bold and slant ([Fonts and font functions](fonts-and-font-functions.html#synthetic-bold-and-slant)) and the font’s scale already applied, and without hinting.

Only hb-vector is built for this book, as the `hb-vector` tool that draws every figure in it. hb-raster and hb-gpu are described from their source; the code shown for them is hand-written usage, not output.

## The three libraries

Each library is a shared library of its own (`libharfbuzz-raster`, `libharfbuzz-vector`, `libharfbuzz-gpu`), with its own header (`hb-raster.h`, `hb-vector.h`, `hb-gpu.h`) and a Meson feature option, `raster`, `vector` and `gpu`, all enabled by default (`meson_options.txt:36–41`). Their history is short and fast, all of it in 2026:

| Version | What happened (`NEWS`) |
|---|---|
| 13.0.0 | hb-raster and hb-vector arrive, “experimental”; SVG output only; colour glyphs from COLR and SVG |
| 13.1.0 | hb-raster paints `CBDT` and `sbix` bitmaps, and reads and writes PNG, with libpng; `hb-raster` tool installed |
| 13.1.1 | gzip-compressed SVG glyphs, with zlib |
| 14.0.0 | hb-gpu arrives, for outlines only, with the `hb-gpu` tool |
| 14.2.0 | the API review: hb-vector gains PDF output and the SVG id prefix; hb-gpu gains colour glyphs; both CPU libraries drop SVG glyphs |
| 14.5.0 | work budgets shared between the font code and the renderers |
| 15.0.0 | “no longer considered experimental”: API and ABI stability now apply |

Most of the API changed in 14.2.0, after “several rounds of code review and cleanup”, just before it froze.

The three share a shape. Each has a **draw context**, for outlines, and a **paint context**, for colour glyphs: `hb_raster_draw_t` and `hb_raster_paint_t`, `hb_vector_draw_t` and `hb_vector_paint_t`, `hb_gpu_draw_t` and `hb_gpu_paint_t`. Each context is an ordinary reference-counted HarfBuzz object, made with a `_create_or_fail` function, configured with setters, fed glyphs, and asked for its result:

| | Feed it | Ask for the result | It returns |
|---|---|---|---|
| hb-raster | `hb_raster_draw_glyph`, `hb_raster_paint_glyph` | `hb_raster_draw_render`, `hb_raster_paint_render` | `hb_raster_image_t`, A8 or BGRA32 pixels |
| hb-vector | `hb_vector_draw_glyph`, `hb_vector_paint_glyph` | `hb_vector_draw_render`, `hb_vector_paint_render` | a blob of SVG or PDF |
| hb-gpu | `hb_gpu_draw_glyph`, `hb_gpu_paint_glyph` | `hb_gpu_draw_encode`, `hb_gpu_paint_encode` | a blob of 16-bit integer texels |

The `_glyph` functions are, in the documentation’s word, “convenience”. `hb_raster_draw_glyph_or_fail (draw, font, glyph)` is documented as equivalent to `hb_font_draw_glyph_or_fail (font, glyph, hb_raster_draw_get_funcs (draw), draw)`, and the others likewise. So a client can also drive a context through its funcs directly, to draw shapes of its own or clip to an arbitrary path. Since 14.2.0 the `_glyph` functions return nothing, and each has a `_glyph_or_fail` twin that reports whether the font had anything to draw or paint.

The paint contexts draw plain glyphs too. Their `_glyph` functions call `hb_font_paint_glyph`, which, as [Colour](colour.html#the-paint-api) explains, falls back to filling the outline with the foreground colour; the `_or_fail` twins call `hb_font_paint_glyph_or_fail`, which doesn’t. So a client that wants one code path can paint every glyph, at some cost: hb-gpu’s documentation says its draw path is “meaningfully faster than Paint on monochrome fonts”.

`_clear` (14.2.0) throws away what has been accumulated and keeps the settings; `_reset` restores the defaults as well. Rendering or encoding clears the context even when it fails, so a context can be reused glyph after glyph, and `_recycle_image` or `_recycle_blob` hands a finished result back for its memory to be reused.

Every context also implements the budget callbacks of [Drawing outlines](drawing-outlines.html#the-budget). Its count is recharged when it is cleared, so one budget of 2²⁴ covers everything drawn into the context between one render and the next: one glyph in hb-raster and hb-gpu as they are normally used, a whole document in hb-vector.

## hb-raster

hb-raster is a small CPU rasterizer. It makes 8-bit coverage masks from outlines and premultiplied BGRA images from colour glyphs, anti-aliased, unhinted and without gamma correction. For hinting, HarfBuzz’s `README.md` says, “use FreeType or Skrifa”.

### Outlines to coverage

`hb_raster_draw_t` doesn’t keep curves. As each segment arrives, it is transformed to pixel space, by the context’s 2×3 transform and then divided by its scale factor, and **flattened**: cut into straight edges short enough that the curve never strays far from them. A quadratic or cubic is split in half, de Casteljau style, until it passes a flatness test or has been split 16 levels deep; the tests are the ones FreeType uses, according to the comments (“FreeType behavior”, `hb-raster-draw.cc:684, 889`). Each split costs a unit of the work budget, and a curve whose control points lie wholly outside the image is replaced by its chord, which, says the header, “is exact for coverage inside the box” (`hb-raster.hh:34`). The edges are stored in 24.8 fixed point, 256 steps to the pixel; horizontal ones are dropped, since they cover nothing.

`hb_raster_draw_render` then makes an A8 image with an **analytic coverage** rasterizer: instead of sampling points in each pixel, it computes how much of each pixel’s area the outline covers. The comment above it (`hb-raster-draw.cc:1238`, trimmed) gives the whole method:

```c++
/*
 * For each line-segment edge and each pixel row it crosses, we compute
 * exact area/cover contributions per pixel cell.  A left-to-right sweep
 * then converts accumulated (area, cover) into alpha values.
 *
 *   cover[x] = Σ dy · wind        — signed vertical extent per cell
 *   area[x]  = Σ (fx₀+fx₁)·dy·wind — twice the signed trapezoidal area
 *
 * Sweep:
 *   cover_accum += cover[x]
 *   α = min(|cover_accum·(2·ONE_PIXEL) − area[x]|, FULL_COVERAGE)
 *       · 255 / FULL_COVERAGE
 */
```

Each edge adds to a row’s cells only where it crosses them. The running sum of cover from the left says how many times the outline winds round a pixel, and the area term corrects it for the edge passing through the pixel itself. Taking the absolute value and capping it at full coverage makes this the **nonzero winding rule**: a pixel is inside if the outline winds round it any number of times in either direction. That is the rule both TrueType and CFF outlines are designed for, and the only one hb-raster has. Rows are swept in two widths of accumulator, 16-bit and, when more than 127 edges are active in a row, 64-bit; the wide ones are presumably the fix for “accumulator overflows … with very many overlapping edges” in 14.5.1 (inferred).

The image is A8, one byte per pixel, with rows stored bottom to top (`hb_raster_image_get_buffer`) and each row padded to a multiple of 4 bytes. Its size is set with `hb_raster_draw_set_extents`, or from the glyph’s extents with `_set_glyph_extents`, or else is the bounding box of the edges. Without a transform, one unit of the font’s scale is one pixel. Hand-written, the outline path looks like this:

```c
hb_raster_draw_t *r = hb_raster_draw_create_or_fail ();
hb_raster_draw_set_transform (r, 1, 0, 0, 1, pen_x, pen_y);
hb_raster_draw_glyph (r, font, gid);
hb_raster_image_t *img = hb_raster_draw_render (r);  /* A8 */
/* … use hb_raster_image_get_buffer (img), _get_extents (img) … */
hb_raster_draw_recycle_image (r, img);
```

### Painting

`hb_raster_paint_t` keeps three stacks: transforms, clips and surfaces. Every surface is a premultiplied BGRA32 image the size of the output. Every clip is an A8 mask of the same size, except that a plain rectangle stays a rectangle until something forces it to be a mask. A glyph clip is rasterized by an internal `hb_raster_draw_t` and multiplied into the mask below it; a rectangle under a rotation or skew becomes a mask too. Fills and gradients are drawn through the current clip onto the top surface.

`push_group` adds a fresh surface; `pop_group` composites it onto the one below with the mode it is given. hb-raster implements all 28 modes of `hb_paint_composite_mode_t` per pixel, the Porter–Duff ones, the separable blends and the four HSL ones (`hb-raster-image.cc:411`), so it is the one renderer in HarfBuzz that paints every COLR version 1 composite as the specification describes. Gradients are looked up in a 256-entry table per colour line, interpolated in premultiplied colour, as the COLR specification asks (`hb-raster-paint.cc:1157`). Images are taken as BGRA pixels, or as PNG decoded with libpng; a build without libpng refuses PNG, and the glyph falls back to whatever comes next. SVG images are refused always (`:1037`), for the reason [Colour](colour.html#svg) gives.

The paint context also has a foreground colour, a background colour that fills the surface first, a palette index and custom palette entries. `hb_raster_image_serialize_to_png_or_fail` turns a BGRA32 image, and only a BGRA32 one, into a PNG.

### Limits

Pixels are bounded separately from outlines. Besides the outline budget, every hb-raster session has a pixel budget, of 2²⁶ units or four passes over the surface, whichever is more (`hb-limits.hh:258`), charged for each surface cleared, composited or filled. A render whose sweep would cost more than that produces a blank image rather than a slow one. The other limits:

| Limit | Value | What it bounds |
|---|---|---|
| `HB_RASTER_MAX_DRAW_EDGES` | 2²⁰ | edges in one draw session |
| `HB_RASTER_MAX_AUTO_DIMENSION` | 4,096 | pixels a side, when the size comes from the font |
| `HB_RASTER_MAX_BUFFER_SIZE` | 1 GiB | one image’s buffer |
| `HB_BUDGET_RASTER_PIXELS` | 2²⁶ | the pixel budget’s floor |

Sizes a client sets explicitly aren’t capped: the client is trusted with its own allocations, the font isn’t.

### The tools

`hb-raster`, installed since 13.1.0, renders shaped text as PNG, PPM or, in a terminal, through the chafa library. `hb-ft-raster`, built only with FreeType and not installed, is “like hb-raster but uses FreeType’s rasterizer for pixel-level comparison”: a testing tool, not a variant of the library.

## hb-vector

hb-vector writes glyphs out as SVG or PDF, so that a colour glyph keeps its gradients and layers at any size. The format is fixed when a context is made, `hb_vector_draw_create_or_fail (HB_VECTOR_FORMAT_SVG)` or `HB_VECTOR_FORMAT_PDF`, and `hb_vector_paint_get_funcs` returns different funcs for each; that is why, since 14.2.0, every context’s funcs getter takes the context.

Both contexts accumulate many glyphs into one document, each placed by the context’s transform, and grow the document’s bounds as they go if asked to (`HB_VECTOR_EXTENTS_MODE_EXPAND`). The `hb-vector` tool sets the bounds itself, from the shaped line, and moves the transform to each glyph’s pen position.

### Outlines

The draw context turns the draw callbacks into path data, as text, and writes one path per glyph. In SVG each callback is one command, `M`, `L`, `Q`, `C` or `Z`, so TrueType’s quadratic curves stay quadratic. PDF has no quadratic operator, so the PDF funcs leave `quadratic_to` unset and let HarfBuzz’s default turn each quadratic into a cubic, as [Drawing outlines](drawing-outlines.html#callbacks-a-client-leaves-out) describes (“No quadratic_to — null fallback auto-promotes to cubic”, `hb-vector-draw.cc:110`). Each path is filled with the context’s foreground colour, by SVG’s default rule and by PDF’s `f` operator, both nonzero.

SVG’s y axis points down, so hb-vector writes coordinates y up and wraps the document in a `scale(1,-1)` group. Numbers are written with a fixed number of decimal places, the **precision**, 2 by default and at most 12 (`hb_vector_draw_set_precision`), and with a full stop whatever the locale. Precision counts in the output’s units, which are the font’s scale: at a font size of 100 per em, precision 0 rounds every point to a hundredth of the em. Here is `spiral64`, from the [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) chapter’s `limits.ttf`, at that size, at precision 0 and at the default:

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

At precision 0 the small squares near the middle of the spiral have lost their shape: their corners have been pulled to whole units of a 100-unit grid. At the default they are square. A renderer that will be scaled up after the fact, as `hb-vector`’s figures are here, wants the font’s scale large or the precision high.

Each glyph’s path is separate, so, as the `hb-vector.cc` documentation warns, where glyphs overlap and the foreground is semi-transparent, the overlaps are darker. `hb_vector_draw_new_path` closes one path and starts another, for clients that feed the funcs themselves.

### Colour glyphs, in SVG

The SVG paint context translates the paint callbacks one by one into SVG elements, held in two buffers: the body and the `<defs>` the body refers to.

| Callback | SVG |
|---|---|
| `push_transform` | `<g transform="matrix(…)">`, skipped when it is the identity |
| `push_clip_glyph`, `push_clip_path_*` | the outline as a `<path>` and a `<clipPath>` in `<defs>`; `<g clip-path="url(#…)">` |
| `push_clip_rectangle` | a `<rect>` in a `<clipPath>` |
| `color`, `fill_glyph` | a filled `<rect>` or `<path>` |
| `linear_gradient`, `radial_gradient` | a `<linearGradient>` or `<radialGradient>` in `<defs>`, filling a rectangle 65,534 units square, cut down by the clip |
| `sweep_gradient` | wedges of solid colour, none wider than π/16 |
| `image` | PNG only: an `<image>` with the PNG inline, base64 encoded |
| `push_group`, `pop_group` | `<g style="mix-blend-mode:…">` |
| `color_glyph` | declined, so HarfBuzz paints the referenced glyph inline |

SVG has no conic gradient, so a sweep is cut into wedges by `hb_paint_sweep_gradient_tiles`, and each wedge into slices no wider than π/16, each filled with the colour at its middle (`hb-vector-paint-svg.cc:174`). Gradient stops are sorted and rescaled into 0–1 first, since SVG clamps offsets outside that range, and the gradient’s ends are moved to match.

Here is the start of `hb-vector`’s output for `M` in `colr1.ttf`, captured when this chapter was written (trimmed; the path data is cut short):

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

The structure is the paint graph’s: the ClipBox is a clip rectangle, the PaintComposite two groups, the source inside the backdrop, and each PaintGlyph of a PaintSolid one filled path, through `fill_glyph`. The 64 and 1/64 are the font transform and its inverse around the glyph ([Colour](colour.html#the-walk)): `hb-vector` scales the font by 64 and sets a scale factor of 64, which divides coordinates on output but not matrices, so the ClipBox’s 100 font units appear as 1.56.

### Compositing modes

`pop_group` is where the formats part company. SVG’s `mix-blend-mode` has the separable and non-separable blend modes of the W3C compositing specification, but none of the Porter–Duff operators, which in SVG need masks or filters. hb-vector’s answer is a table (`hb-vector-paint-svg.cc:75`): the blend modes are written as themselves; PLUS becomes `screen` and XOR becomes `difference`, “a plausible color-blend analog”; the other nine Porter–Duff modes become ordinary source-over. Its PDF writer has the same table, in PDF’s names (`hb-vector-paint-pdf.cc:1556`). `modes.ttf` has the same pair of discs, a blue backdrop and a red source, composited with SRC_OVER, SRC_IN, DEST_OUT, XOR, PLUS, SCREEN and DIFFERENCE, on `N`, `I`, `O`, `X`, `P`, `S` and `D`:

```draw
font: modes.ttf
text: NIOXPSD
```

`N`, `I` and `O` are identical, though SRC_IN should leave only the lens where the discs overlap, in red, and DEST_OUT only the blue crescent. `X` is drawn as DIFFERENCE, the same as `D`, where XOR should have left the lens empty. `P` is drawn as SCREEN, the same as `S`; PLUS would have added the colours, which here reaches nearly the same result. hb-raster draws all seven as the specification says. hb-gpu has its own table, below.

Every glyph also has an outline, the cut-cornered square of the [Colour](colour.html) chapter. `hb-vector` uses its paint context for a font that has COLR, CBDT or sbix data, and its draw context otherwise. `--draw` forces the draw context, which ignores colour and draws the outline:

```draw
font: modes.ttf
text: NIOXPSD
vector-options: --draw
```

### ids, and the prefix

Clip paths and gradients are found by `id`, and hb-vector numbers them from zero in every document: `c0`, `p0`, `clip-p0`. Two documents in one web page then fight over the same names. `hb_vector_paint_set_svg_prefix` (14.2.0) puts a string of the client’s choosing in front of every `id` and every reference to one. This book’s pages have the same problem, and since the `hb-vector` tool has no option for the prefix, the build rewrites each figure’s ids itself (`tools/build-site.mjs`). The draw context’s output has no ids, and no prefix.

### PDF

The PDF writer (14.2.0) makes a complete one-page PDF 1.4 file whose media box is the document’s bounds. `NEWS` says what it is for: colour-glyph artwork “that can be embedded directly in PDF documents. Useful for PDF producers such as LibreOffice.”

The paint funcs map to PDF’s graphics state: `q` and `Q` for transforms and groups, `W n` for clips, an ExtGState with `/ca` for alpha and with `/BM` for a blend mode, set by `push_group_for`, which tells a client the mode before the group is painted ([Colour](colour.html#the-paint-api)). Linear and radial gradients become PDF axial and radial shadings (types 2 and 3); colour stops with alpha get a second, grey shading used as a soft mask. A sweep becomes a mesh of Coons patches (shading type 6), a close approximation of a conic gradient, where SVG has to make do with wedges of flat colour. (The comment at the top of the file still says sweeps are “approximated via solid fallback”: it is out of date.)

Two things are lost in PDF and not in SVG:

* **Extend modes.** PDF’s axial and radial shadings can only stop at their ends or pad beyond them. hb-vector pads when the colour line says pad, and otherwise stops (`hb-vector-paint-pdf.cc:1099, 1200`), so a repeating or reflecting gradient is painted only between its first and last stops. `R` and `F` in `colr1.ttf` become the inner disc alone.
* **PNG alpha.** PNG images are embedded without being decoded: the compressed IDAT data is copied into the PDF with a matching predictor, which keeps the file small. An indexed PNG with transparency gets a soft mask, which needs zlib to build. But for an RGBA or grey-and-alpha PNG, the alpha is ignored (`(void) has_alpha`, `:305`), and the image is declared as RGB or grey while its data still has four or two components per pixel. In a test made while writing this chapter, the RGBA PNG of `P` in `images.ttf` came out of `hb-vector -O pdf` as stripes, in poppler’s `pdftoppm`, where the SVG shows a green disc. Bitmap colour glyphs are nearly always RGBA, so this is probably a bug.

### Limits

Every document is capped at 16 MiB (`HB_VECTOR_MAX_DOCUMENT_SIZE`, `hb-limits.hh:181`). That bounds what the outline budget can’t see: gradient meshes, embedded images, and the bytes of path text. When a buffer reaches the cap it stops growing, and the context stops drawing outlines. In PDF the extra objects are counted against the same cap. The work budget is per document, as [Drawing outlines](drawing-outlines.html#the-budget) showed with `limits.ttf`. Transforms nest at most 64 deep in the SVG writer, and further ones are ignored. And the paint context declines `color_glyph`, so a PaintColrGlyph is painted inline under COLR’s own guards, instead of starting a fresh walk with fresh limits for every reference (`hb-vector-paint-svg.cc:885`).

## hb-gpu

hb-gpu doesn’t render on the CPU at all, and doesn’t make an atlas of glyph bitmaps. It encodes each glyph’s curves into a compact blob, and a fragment shader works out, for each pixel, how much of it the curves cover. The method is **Slug**, Eric Lengyel’s algorithm, which hb-gpu implements with credit in its shader source (`hb-gpu-fragment.glsl:3–6`). Since coverage is computed from the curves at whatever size the glyph lands on screen, one encoding serves every size, rotation and perspective.

### Encoding outlines

`hb_gpu_draw_t` accumulates curves through its draw funcs, and `hb_gpu_draw_encode (draw, &extents)` packs them into a blob and returns the glyph’s extents. Everything becomes a quadratic: a line is a quadratic whose control point is its start, and a cubic is converted by an implementation of **cu2qu**, the cubic-to-quadratic conversion familiar from fontTools, in `hb-gpu-cu2qu.hh`. Its tolerance is half a font unit, and it splits a cubic up to 10 levels deep; a cubic whose control points lie within that tolerance of the chord is drawn as a line. So CFF and cubic `GLYF` outlines are approximated, to well within a unit, and TrueType outlines are encoded exactly.

Coordinates are quantized to 16-bit integers, at 4 per unit (`HB_GPU_UNITS_PER_EM`, `hb-gpu-draw.hh:38`): a quarter of a unit’s precision, over a range of about ±8,000 units. That is why the documentation asks for the font to be left at its default scale, the upem, and for scaling to happen in the vertex shader. The glyph is then cut into **bands**: up to 16 horizontal strips and 16 vertical ones (“capped at 16 per Slug paper”, `hb-gpu-draw.cc:510`). Each band lists the curves that reach into it, twice: once sorted by their right or top end, once by their left or bottom end. A pixel needs only the curves in its own two bands, and each band also stores a split point, and a pixel on one side of it casts its ray to the left and reads one list, on the other side to the right and reads the other, stopping as soon as the curves are out of reach. Bounds are computed from the quantized points, so that the shader and the encoder agree on which band a curve is in; a comment records what happened when they didn’t: “a thin black line through the glyph”.

The blob is an array of **texels** of four signed 16-bit numbers (RGBA16I, 8 bytes each): a header, the band headers, the band lists, and the curves. A glyph’s blob can hold at most 65,536 texels, since its offsets are 16-bit, and at most 65,536 curves (`HB_GPU_DRAW_MAX_CURVES`). A glyph with no ink encodes as an empty blob, and a failure as `NULL`.

### The shaders

The shaders come with the library, in four languages: GLSL (OpenGL 3.3, OpenGL ES 3.0, WebGL 2), WGSL (WebGPU), MSL (Metal) and HLSL (Direct3D). They are compiled into the library as strings, by `gen-gpu-shader-artifacts.py`. A client builds its shaders by concatenating, in order, a version line, `hb_gpu_shader_source (stage, lang)` (helpers shared by both renderers), `hb_gpu_draw_shader_source` or `hb_gpu_paint_shader_source`, and its own `main`. All the blobs go into one texture buffer, an “atlas” of encoded curves rather than pixels, and each glyph is drawn as one quad with its blob’s offset as a vertex attribute.

The vertex helper, `hb_gpu_dilate`, widens each quad by half a pixel on screen, correctly under perspective, so that anti-aliased edges aren’t cut off at the quad’s edge; a client that doesn’t need perspective can pad by a fixed amount instead. The fragment helper `hb_gpu_draw` returns coverage between 0 and 1. A minimal fragment shader, from the documentation in `hb-gpu.cc`:

```glsl
in vec2 v_texcoord;
flat in uint v_glyphLoc;
out vec4 fragColor;

void main () {
  float coverage = hb_gpu_draw (v_texcoord, v_glyphLoc);
  fragColor = vec4 (0.0, 0.0, 0.0, coverage);
}
```

Inside, `_hb_gpu_slug_single` (`hb-gpu-fragment.glsl:185`) casts one horizontal and one vertical ray from the pixel, solves each curve’s quadratic for where it crosses the ray, and adds up signed partial coverage for the crossings within half a pixel; the two directions are averaged with weights that favour whichever is nearer an edge. Below 16 pixels per em, it blends in four more samples, fully so by 8 ppem (`:314`); `HB_GPU_NO_MSAA` turns that off. `hb_gpu_stem_darken` (`:344`), optional, adjusts coverage at small sizes, raising it for dark text so that thin stems aren’t washed out and lowering it for light text, and fades out by 48 ppem. Nothing in hb-gpu hints.

### Colour glyphs

`hb_gpu_paint_t` (14.2.0) encodes a colour glyph for `hb_gpu_paint`, a fragment-shader function that the design notes in `hb-gpu-paint.hh` describe plainly: “The fragment shader is the interpreter: it walks a flat op stream per pixel, maintains a small group stack, and composites the result.” The encoder flattens the paint graph into four kinds of operation: a solid layer, a gradient layer, push group and pop group. Each layer carries the clip outline it is painted through, encoded as a Slug blob of its own, with the transforms already applied; gradients carry their inverse transform, geometry and stops. Palette colours, custom ones included, are baked into the blob, so changing the palette means encoding again. The foreground colour isn’t: a layer marked as foreground is coloured by a shader argument, “so dark-mode and color-change toggles take effect without re-encoding”.

The encoder can’t represent everything, and when it meets something it can’t, the whole glyph fails: `hb_gpu_paint_encode` returns `NULL`.

| Limit (`hb-gpu-paint.cc:51`) | Value |
|---|---|
| operations per glyph | 32,767 |
| groups nested | 4 |
| glyph or path clips intersected per layer | 3 |
| clip blobs per glyph | 1,024 |
| bytes of clip and gradient data (`HB_GPU_PAINT_MAX_SUB_BYTES`) | 64 MiB |

Images aren’t supported at all, so bitmap and SVG glyphs fail, and the caller learns that “the glyph won’t render rather than getting a partial blob” (`:1072`). Rectangle clips, ClipBoxes among them, are ignored: “output is bigger than it should be, but renders”. The shader composites the Porter–Duff modes, PLUS, SCREEN, DARKEN, LIGHTEN and MULTIPLY exactly, approximates OVERLAY, COLOR_BURN and HARD_LIGHT with MULTIPLY and COLOR_DODGE and SOFT_LIGHT with SCREEN, and draws DIFFERENCE, EXCLUSION and the HSL modes as source-over (`hb-gpu-paint-fragment.glsl:196`). So each renderer gets a different subset of `modes.ttf` right: hb-gpu every letter but `D`, hb-vector only `N`, `S` and `D`.

### The tools

`hb-gpu`, installed since 14.0.0, is an interactive viewer for shaped text, built when GLEW, GLFW and OpenGL are found (the `gpu_demo` option); since 14.2.0 it can also write one frame to a PPM file. `NEWS` gives a web version, `https://harfbuzz.github.io/hb-gpu-demo/`. Neither is built for this book.

## Building them

| Option or macro | Effect |
|---|---|
| `-Draster=disabled`, `-Dvector=disabled`, `-Dgpu=disabled` | leave out a library and its tool |
| `-Dgpu_demo` | the `hb-gpu` viewer; `auto` builds it when its dependencies are found |
| `-Dpng`, `-Dzlib` | libpng, for hb-raster’s PNG images; zlib, for hb-vector’s PDF masks of indexed PNGs |
| `HB_HAS_RASTER`, `HB_HAS_VECTOR`, `HB_HAS_GPU` | defined in `hb-features.h` when a library is built |
| `HB_GPU_NO_MSAA`, `HB_GPU_ATLAS_2D` | defined by a client before the shader source: no extra samples at small sizes; a 2D texture instead of a texture buffer, for WebGL 2 |

There are no `HB_NO_RASTER`-style macros: the libraries are in or out by build option. `HB_LEAN` is meant to keep drawing and painting when one of them is built: it defines `HB_NO_COLOR`, `HB_NO_DRAW` and `HB_NO_PAINT` only when none of `HB_HAS_CAIRO`, `HB_HAS_RASTER`, `HB_HAS_VECTOR` or `HB_HAS_GPU` is defined (`hb-config.hh:85`). But those are defined only in `hb-features.h`, which the library’s own sources don’t include, so in an ordinary Meson build `HB_LEAN` removes drawing and painting even with the libraries built. Only a `harfbuzz-world.cc` build sees them ([Compile-time configuration](compile-time-configuration.html)). Since 14.0.0, `harfbuzz-world.cc` can build any selection of the libraries as a single source file.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-raster.h` | the raster API: images, draw and paint contexts |
| `src/hb-raster-draw.cc` | flattening, 623–1037; the analytic coverage rasterizer, 1238; `hb_raster_draw_render`, 1631 |
| `src/hb-raster-paint.hh`, `src/hb-raster-paint.cc` | the clip, surface and transform stacks; the paint callbacks; gradients, 1157; images, 979 |
| `src/hb-raster-image.cc` | images, PNG through libpng, and the 28 compositing modes, 411 |
| `src/hb-vector.h`, `src/hb-vector.cc` | the vector API and its overview documentation |
| `src/hb-vector-draw.hh`, `src/hb-vector-draw.cc` | SVG and PDF path callbacks; writing the two document formats, 727 and 838 |
| `src/hb-vector-paint.cc`, `src/hb-vector-paint-svg.cc` | the paint context, the SVG id prefix; SVG paint callbacks, compositing table, 75 |
| `src/hb-vector-paint-pdf.cc` | PDF paint: ExtGStates, shadings, Coons meshes, embedded PNGs |
| `src/hb-vector-buf.hh` | the output buffer, its 16 MiB cap, and locale-free numbers |
| `src/hb-gpu.h`, `src/hb-gpu.cc` | the GPU API, and its long usage documentation |
| `src/hb-gpu-draw.hh`, `src/hb-gpu-draw.cc`, `src/hb-gpu-cu2qu.hh` | accumulating quadratics, cu2qu, quantizing and banding, `hb_gpu_draw_encode`, 451 |
| `src/hb-gpu-paint.hh`, `src/hb-gpu-paint.cc` | the paint blob’s design notes; the encoder and its limits, 51 |
| `src/hb-gpu-*.glsl`, `.wgsl`, `.msl`, `.hlsl` | the shaders: shared helpers and Slug, draw, paint, vertex |
| `src/hb-limits.hh` | the renderers’ limits and budgets, 135–268 |
| `util/hb-raster.cc`, `util/hb-vector.cc`, `util/hb-gpu.cc`, `util/hb-ft-raster.cc` | the tools; `util/vector-output.hh` for how `hb-vector` drives its contexts |

## In short

* hb-raster, hb-vector and hb-gpu are separate libraries, added in 13.0.0 and 14.0.0 and stable since 15.0.0. Each has a draw context and a paint context that are just draw and paint funcs with state, and its `_glyph` calls are shorthand for `hb_font_draw_glyph` and `hb_font_paint_glyph`.
* hb-raster flattens curves into fixed-point edges and computes exact area coverage with the nonzero rule, into A8 masks; it paints colour glyphs on premultiplied BGRA surfaces with every COLR compositing mode. It doesn’t hint, and bounds pixels and outlines with separate budgets.
* hb-vector writes SVG or PDF, one path per glyph. SVG keeps quadratics; PDF gets cubics. Porter–Duff modes become source-over, except PLUS and XOR, which become screen and difference. `hb_vector_paint_set_svg_prefix` keeps ids apart. PDF loses repeat and reflect, and, in {{hb}}, the alpha of RGBA PNGs.
* hb-gpu encodes outlines as quantized quadratics in bands, converting cubics with cu2qu, for a Slug fragment shader in GLSL, WGSL, MSL or HLSL. Its colour encoder is an op stream with baked palettes, at most four nested groups, no images, no rectangle clips, and approximate blend modes.
* Only `hb-vector` is built for this book; hb-raster and hb-gpu are described from their source.
