# hb-raster: rendering to pixels

The draw and paint APIs end at a callback. HarfBuzz walks the font’s data and calls the client: move here, curve to there, push this clip, fill with that gradient. For most of HarfBuzz’s life, what happened next was someone else’s business: FreeType, cairo, Skia or the platform turned the callbacks into pixels. Since 13.0.0 HarfBuzz has its own renderers, in three separate libraries. **hb-raster** turns glyphs into pixel images on the CPU. [hb-vector](hb-vector.html) writes them out as SVG or PDF. [hb-gpu](hb-gpu.html) encodes them so that a fragment shader can draw them on the GPU. Each is a client of the APIs that [Drawing outlines](drawing-outlines.html) and [Color](color.html) describe, and nothing more.

This chapter is about the first. hb-raster is a small anti-aliasing rasterizer: it makes 8-bit coverage masks from outlines, and premultiplied BGRA images from color glyphs. It sees glyphs exactly as an application would, with variations, synthetic bold and slant ([Fonts and font functions](fonts-and-font-functions.html#synthetic-bold-and-slant)) and the font’s scale already applied. What it doesn’t do is as important as what it does: it doesn’t hint, and text that needs hinting needs FreeType beside it.

The chapter is in two parts, [Outlines](#outlines) and [Color glyphs](#color-glyphs); a reader who draws only ordinary text can stop after the first. Every image on this page is hb-raster’s own PNG output, made by the `hb-raster` tool when the page was built and shown enlarged; the code is hand-written usage.

## The library

hb-raster is a shared library of its own, `libharfbuzz-raster`, with one header, `hb-raster.h`. It is built unless the [Meson option](building-harfbuzz.html#optional-dependencies-and-backends) `raster` is disabled (`meson_options.txt:36`), and uses libpng when it is found (`src/meson.build:757`). It is a young library. It arrived in 13.0.0, its API was reviewed and changed in 14.2.0, and it has been covered by HarfBuzz’s API and ABI stability only since 15.0.0, so code and articles written for earlier versions may not match it (`NEWS`):

| Version | What happened |
|---|---|
| 13.0.0 | hb-raster arrives, “experimental”: A8 and BGRA32 images, outlines, and color glyphs from COLR and SVG |
| 13.1.0 | `CBDT` and `sbix` bitmaps; PNG reading and writing, with libpng; the `hb-raster` tool is installed |
| 13.1.1 | gzip-compressed SVG glyphs, with zlib |
| 14.2.0 | the API review: `_clear`, `_glyph_or_fail`, palette and background setters; SVG glyphs dropped |
| 14.5.0 | work budgets shared with the font code |
| 14.5.1 | accumulator overflows with very many overlapping edges fixed |
| 15.0.0 | “no longer considered experimental”: API and ABI stability now apply |
| 15.1.0 | rotated and skewed rectangle clips fixed |

There are two contexts, one for each API. A **draw context**, `hb_raster_draw_t`, is a set of draw funcs with state: it collects outlines and renders them to an A8 coverage mask. A **paint context**, `hb_raster_paint_t`, is a set of paint funcs with state: it paints color glyphs into a BGRA32 image. Both are ordinary reference-counted HarfBuzz objects, made with `_create_or_fail` and configured with setters: a 2×3 transform, a scale factor that divides it, and the output’s extents.

A context is fed glyphs by `hb_raster_draw_glyph` or `hb_raster_paint_glyph`. These are a “convenience”: `hb_raster_draw_glyph_or_fail (draw, font, glyph)` is documented as equivalent to `hb_font_draw_glyph_or_fail (font, glyph, hb_raster_draw_get_funcs (draw), draw)` (`hb-raster-draw.cc:1195`). So a client can also drive a context through its funcs directly, to draw shapes of its own. Since 14.2.0 the plain `_glyph` functions return nothing, and each has a `_glyph_or_fail` twin that says whether the font had anything to draw or paint.

`_render` turns what has been collected into an `hb_raster_image_t`, and clears the context even when it fails (`hb-raster-draw.cc:1683`, `hb-raster-paint.cc:2566`), so the same context can be used glyph after glyph. `_clear` throws away what has been collected and keeps the settings; `_reset` restores the defaults too. `_recycle_image` hands a finished image back to the context, which reuses its memory for the next render instead of allocating.

Both contexts implement the budget callbacks of [Drawing outlines](drawing-outlines.html#the-budget), and recharge the budget when they are cleared. So one budget of 2²⁴ covers everything drawn between one render and the next, which, as hb-raster is normally used, is one glyph.

## Outlines

### The draw context

Hand-written, the whole path from a glyph to a mask is a handful of calls. This is the sequence the library’s own documentation gives (`hb-raster-image.cc:44`), with the pen position in the transform:

```c
hb_raster_draw_t *draw = hb_raster_draw_create_or_fail ();
hb_raster_draw_set_scale_factor (draw, 64.f, 64.f);  /* font scale is 26.6 */
hb_raster_draw_set_transform (draw, 1, 0, 0, 1, pen_x, pen_y);

hb_glyph_extents_t glyph_extents;
hb_font_get_glyph_extents (font, gid, &glyph_extents);
hb_raster_draw_set_glyph_extents (draw, &glyph_extents);

hb_raster_draw_glyph (draw, font, gid);
hb_raster_image_t *mask = hb_raster_draw_render (draw);   /* A8 */
/* … hb_raster_image_get_buffer (mask), hb_raster_image_get_extents … */
hb_raster_draw_recycle_image (draw, mask);
```

Every point that arrives is multiplied by the transform and then divided by the scale factor (`hb-raster-draw.cc:119`). With neither set, one unit of the font’s scale is one pixel. Setting the scale factor to 64 lets a client keep its font scale in 26.6 fixed point, 64 units to the pixel, as hb-ft does and as the `hb-raster` tool does (`util/raster-output.hh:190`). The pen position can be fractional: nothing rounds it, so glyphs can be placed at any fraction of a pixel.

Several glyphs can be drawn into one context before it is rendered, each with its own transform. The `hb-raster` tool draws a whole line that way, into one mask (`util/raster-output.hh:245`).

### Flattening

`hb_raster_draw_t` doesn’t keep curves. Each segment is transformed to pixel space as it arrives and **flattened**: cut into straight edges close enough to the curve that the difference can’t be seen. A quadratic or cubic is split in half, de Casteljau style, until a flatness test passes or it has been split 16 times (`hb-raster-draw.cc:625`, `:834`). The tests are the ones FreeType uses, according to the comments: for a quadratic, the control point’s distance from the middle of the chord, at most a quarter of a pixel in each direction; for a cubic, a test at the chord’s thirds, at most half a pixel (“FreeType behavior”, `:684`, `:889`). Each split costs one unit of the work budget; when the budget is spent, the rest of the curve becomes its chord.

When the image’s extents are known in advance, a curve whose control points lie entirely outside them is replaced by its chord straight away. The header explains why that is safe: a curve’s crossings of rows outside the image cancel out, so the chord “is exact for coverage inside the box” (`hb-raster.hh:34`).

The edges are stored in 24.8 fixed point, 256 steps to the pixel, each with a direction, up or down. Horizontal edges are dropped, since they cover nothing (`hb-raster-draw.cc:593`).

### Coverage and the nonzero rule

`hb_raster_draw_render` then makes the A8 image with an **analytic coverage** rasterizer. Instead of sampling a few points in each pixel, it computes how much of each pixel’s area the outline covers. The comment above it (`hb-raster-draw.cc:1238`, trimmed) gives the whole method:

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

An edge adds to a row’s cells only where it passes through them. The running sum of cover from the left counts how many times the outline winds around a pixel, up edges against down ones; the area term corrects that count for an edge passing through the pixel itself. Taking the absolute value and capping it at full coverage makes this the **nonzero winding rule**: a pixel is inside if the outline winds around it any number of times, in either direction. It is the rule TrueType and CFF outlines are designed for, and the only one hb-raster has. In this chapter’s test font, `o` is a square with a counter wound the other way, `q` the same square with its counter wound the same way, and `x` two squares that overlap:

```raster
zoom: 4
raster.ttf  oqx  --font-size=40
```

The counter of `o` is a hole; the counter of `q` is filled, because the winding there is 2, not 0. In the overlap of `x` the winding is also 2, and is capped: overlapping contours, which variable fonts often keep, are not drawn darker where they overlap.

Because the coverage is exact area, a glyph’s position within a pixel shows. In the test font, `l` is a bar exactly one pixel wide at 20 pixels per em, and has an advance of 5¼ pixels, so each `l` starts a quarter of a pixel to the right of where the one before did:

```raster
zoom: 10
raster.ttf  llllll  --font-size=20
```

The first bar starts on a pixel boundary and is one black column. The second covers three quarters of one column and a quarter of the next, and is drawn as two grays; the third is two middle grays; the fifth is on a boundary again. Nothing is wrong here: that is what a bar one pixel wide between two pixels covers. It is also the problem that hinting exists to solve, [below](#what-hb-raster-doesnt-do).

Rows are swept with 16-bit accumulators, or 64-bit ones when more than 127 edges are active in a row (`hb-raster-draw.cc:1257`, `:1754`), presumably the fix for the “accumulator overflows” of 14.5.1 (inferred).

### The A8 image

The result is an `hb_raster_image_t` in `HB_RASTER_FORMAT_A8`: one byte of coverage per pixel, 0 for none and 255 for full. Its `hb_raster_extents_t` give its size in pixels, its `stride` in bytes, a multiple of 4 for A8 (`hb-raster-draw.cc:1679`), and its origin: `x_origin` and `y_origin` are the pixel coordinates of its left and bottom edges. The rows are stored bottom to top, as `hb_raster_image_get_buffer` says (`hb-raster-image.cc:1033`), since y goes up in font coordinates. The documentation asks a client that caches glyph images to place them by that origin, not by the glyph’s bearings (`hb-raster-image.cc:74`).

Where the extents come from is up to the client. `hb_raster_draw_set_extents` sets them outright. `hb_raster_draw_set_glyph_extents` takes the glyph’s extents from `hb_font_get_glyph_extents`, puts their corners through the transform and the scale factor, and rounds the box outward to whole pixels (`hb-raster-draw.cc:421`). With neither, `render` uses the bounding box of the edges it collected.

### Limits

Fonts can’t be trusted ([Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html)). Besides the work budget, hb-raster bounds its own work (`hb-limits.hh:184–268`):

| Limit | Value | What it bounds |
|---|---|---|
| `HB_RASTER_MAX_DRAW_EDGES` | 2²⁰ | edges collected between renders |
| `HB_RASTER_MAX_AUTO_DIMENSION` | 4,096 | pixels a side, when the size comes from the font |
| `HB_RASTER_MAX_BUFFER_SIZE` | 1 GiB | one image’s buffer |
| `HB_BUDGET_RASTER_PIXELS`, `HB_BUDGET_RASTER_PAINT_PASSES` | 2²⁶, 4 | pixel work, below |

The **edge limit** counts the straight edges the flattener has made. When it is reached, further edges are silently dropped (`hb-raster-draw.cc:597`), so a glyph with more than a million edges is drawn in part. The dimension cap applies only to sizes that come from the font: from glyph extents, from the edges’ bounding box, or from a PNG’s header. Sizes a client sets with `set_extents` aren’t capped: the client is trusted with its own allocations, the font isn’t.

The sweep visits every edge once for each row it spans, and neither cap bounds that product. So before sweeping, `render` estimates the work, each edge’s height plus its width in pixels, and if that exceeds 2²⁶ units or four passes over the image, whichever is more, it returns a blank image instead of a slow one (`hb-raster-draw.cc:1705`). An unlimited budget turns this check off.

### Checking against FreeType

`hb-ft-raster`, built only with FreeType and not installed, is “like hb-raster but uses FreeType’s rasterizer for pixel-level comparison”: it shapes the same way, then renders each glyph with FreeType’s `FT_Outline_Render` into a gray PPM image (`util/hb-ft-raster.cc:27`). It loads the glyphs with `FT_LOAD_NO_HINTING | FT_LOAD_NO_BITMAP` (`util/hb-ft-raster.cc:209`, `:252`), so it compares unhinted outlines, the only kind hb-raster draws from HarfBuzz’s own font funcs.

Run by hand on `Roboto-Regular.ttf` from HarfBuzz’s test suite, “Hamburgefonts” at 11 pixels, with `hb-raster --ink --margin=0 -O ppm` for the same framing, the two tools make images of the same size, 77 × 12 pixels. 267 of the 924 pixels differ, and none by more than 5 levels out of 255. At 48 pixels the largest difference is 11 levels. Both compute coverage by area, from slightly differently rounded edges.

### What hb-raster doesn’t do

HarfBuzz’s `README.md` is direct about it: “Notable missing feature: font hinting (including autohinting) is not implemented. For hinted rasterization, use FreeType or Skrifa.” In full, hb-raster has none of the following, and nothing in its source mentions them:

* **No hinting of any kind.** No TrueType bytecode interpreter: the `fpgm`, `prep` and `cvt ` tables, and the instructions in each glyph, are never run. HarfBuzz touches `cvt ` only to apply `cvar` deltas when it instances a font (`hb-ot-var-cvar-table.hh`), never to hint. No autohinter, which would detect stems and blue zones in an unhinted font. No CFF or PostScript hints: the charstring interpreter of [Drawing outlines](drawing-outlines.html#cff-and-cff2-running-charstrings) counts the stem hints only to know how long the hint masks after them are, so that it can skip them (`hb-cff-interp-cs-common.hh:371–389`). The outline hb-raster draws is the outline the font funcs give it, scaled and nothing else.
* **No gamma correction.** A pixel’s coverage is its covered area, scaled linearly to 0–255 (`hb-raster-draw.cc:1581`). A display doesn’t turn values into light linearly, so text whose coverage is blended without correction looks thinner or heavier than its outline, depending on the colors. Correcting for that is left to whatever composites the mask. The paint side composites in the same uncorrected values (`hb-raster.hh:73`).
* **No LCD or subpixel rendering.** The only formats are A8, one coverage value per pixel, and BGRA32 color (`hb-raster.h:45`). There is no mode that renders at three times the horizontal resolution for the red, green and blue stripes of an LCD, and no filter for the color fringes that would cause. Subpixel *positioning* is another matter: glyphs can be placed at any fraction of a pixel, as the bars above show.
* **No stem darkening.** Nothing thickens thin stems at small sizes to make up for the lack of gamma correction and hinting. hb-gpu’s shaders offer an optional `hb_gpu_stem_darken` (`hb-gpu.cc:329`); hb-raster has no counterpart.
* **No bi-level rendering.** Every result is anti-aliased. There is no black-and-white mode, and so no TrueType dropout control.

At a large size, or on a screen with many pixels to the inch, none of this matters much: a stem many pixels wide has a gray edge, and nobody can see where within the pixel it fell. At a small size on an ordinary screen, a stem may be about one pixel wide, and then, as the bars above show, whether it is one black column or two gray ones depends on where it falls. Hinting is the font’s way of choosing, at each size, where stems, heights and curves land on the pixel grid. Beat Stamm’s [The Raster Tragedy at Low-Resolution Revisited](http://rastertragedy.com) is the long account: on [what hinting is](http://rastertragedy.com/RTRCh6.htm#Sec0), on [gamma](http://rastertragedy.com/RTRCh5.htm#Sec3), on [subpixel anti-aliasing](http://rastertragedy.com/RTRCh2.htm#Sec2), and on how hinting fights with [fractional advance widths](http://rastertragedy.com/RTRCh3.htm#Sec32).

### When hb-raster is enough

What it does well follows from what it is: exact anti-aliased coverage, fractional positions, full color glyphs, and no dependencies beyond libpng. What it lacks matters most where pixels are few. This is the book’s own assessment, not HarfBuzz’s:

* **High-resolution screens**, such as phones, tablets and laptops at well over 100 pixels per inch, where unhinted anti-aliased text is the norm and an em has enough pixels to draw a letter without help.
* **Large text** at any resolution: headings, display type, generous UI labels. Hinting matters less as the ppem rises.
* **Glyph atlases**, as games and other GPU applications use them: glyphs rasterized once on the CPU, at the sizes needed, and drawn as textured rectangles. Text that zooms or scales continuously is better drawn from outlines on the GPU, by [hb-gpu](hb-gpu.html).
* **Moving text**: animation, zooming and smooth scrolling. Unhinted glyphs at fractional positions move smoothly, where hinted ones snap from one pixel to the next.
* **Images rather than screens**: thumbnails and previews made on a server, font specimens and proofs, figures, visual regression tests, where the same output everywhere matters more than legibility at 9 pixels.
* **Color glyphs and emoji**, where hb-raster implements every composite mode the [Color](color.html) chapter describes.
* **Small or sandboxed builds**, such as WebAssembly, where one library that shapes and draws is simpler than two.

It falls short in the opposite cases. Small text on screens of about 100 pixels per inch looks soft unhinted, as the 11-pixel example below shows. Light text on a dark background, or anything else sensitive to contrast, needs the gamma correction or stem darkening hb-raster doesn’t do, unless the application adjusts the coverage itself. Output with no grays at all, for some e-ink modes, segment displays or printers, needs a bilevel mode it doesn’t have. And a few fonts, mostly older Chinese ones, don’t draw correctly at all without their own hinting: FreeType calls them “tricky” and always hints them, whatever it is asked (`FT_FACE_FLAG_TRICKY` in FreeType 2.15.0’s `freetype.h`). For those, hinting comes from FreeType or Skrifa, and hb-raster can still do the rasterizing, as the next section shows.

### Hinting with FreeType

A text stack that needs hinted text needs a hinting engine beside HarfBuzz: in practice FreeType, or Skrifa, the Rust scaler that `README.md` also names. Skrifa, part of Google’s [Fontations](https://github.com/googlefonts/fontations) crates, is a full alternative to FreeType here: version 0.49, the one HarfBuzz builds against (`src/rust/Cargo.toml:10`), has its own TrueType bytecode interpreter, CFF stem hinting, and an autohinter modeled on FreeType’s, with targets for “Monochrome, grayscale, light grayscale, or horizontal or vertical subpixel rendering” that correspond to FreeType’s load targets (its `src/lib.rs:61`, and `src/outline/glyf/hint/`, `cff/hint.rs` and `autohint/`); its README says it “is tested glyph by glyph against FreeType”. It is also the library behind HarfBuzz’s own `fontations` funcs, but they use it unhinted, “at one pixel per font unit” (`src/rust/font.rs:142`), even for the few fonts whose outlines are only correct once hinted (`:146`). So hinting with Skrifa means calling it directly.

FreeType fits in through hb-ft, the font funcs of [Fonts and font functions](fonts-and-font-functions.html#the-other-funcs). With hb-ft, FreeType answers HarfBuzz’s questions about the font: advances come from `FT_Get_Advance` and outlines from `FT_Load_Glyph` (`hb-ft.cc:557`, `:1026`), each called with the font’s **load flags**. Those default to `FT_LOAD_DEFAULT | FT_LOAD_NO_HINTING` (`hb-ft.cc:130`, `:1926`), so hb-ft is unhinted until a client asks otherwise with `hb_ft_font_set_load_flags`. Turn hinting on, and two things change at once: the outlines that the draw funcs hand to hb-raster are FreeType’s hinted outlines, and the advances that shaping uses are FreeType’s hinted advances, rounded to whole pixels. FreeType does the hinting; hb-raster still does the rasterizing.

The `hb-raster` tool can show this, since it takes `--font-funcs` and `--ft-load-flags`, whose default is 2, `FT_LOAD_NO_HINTING` (`util/font-options.hh:73`). Here is `Roboto-Regular.ttf`, which has TrueType hinting, at 11 pixels per em: first with HarfBuzz’s own `ot` funcs, then with FreeType’s and load flags 0, `FT_LOAD_DEFAULT`, which runs the font’s instructions, then with 65,536, `FT_LOAD_TARGET_LIGHT`, which FreeType’s header describes as “snapping glyphs to the pixel grid only vertically” (`freetype.h` in FreeType 2.15.0):

```raster
hb:test/subset/data/fonts/Roboto-Regular.ttf  Hamburgefonts  --font-size=11
hb:test/subset/data/fonts/Roboto-Regular.ttf  Hamburgefonts  --font-size=11 --font-funcs=ft --ft-load-flags=0
hb:test/subset/data/fonts/Roboto-Regular.ttf  Hamburgefonts  --font-size=11 --font-funcs=ft --ft-load-flags=65536
```

The first is soft. The crossbar of the `H` falls across two rows, and is two mid-grays (coverage 117 and 99 out of 255). In the second, the crossbar is one black row (255), the tops of the lowercase letters are darker, and the text is sharper overall. Some stems have moved sideways too: the stem of the `b`, two columns of 198 and 55 in the first line, is 64 and 191 in the second, though most stems are still a dark column beside a light one. The third also puts the crossbar on one row, at 215, but leaves the stems where the unhinted line has them: the `b`’s are 199 and 56. The hinted line is also one pixel wider, because its advances have changed. `hb-shape`, run by hand from the FreeType build with the same font at the same size, shows how (positions in 64ths of a pixel; the first line from `--font-funcs=ot`, the second from `--font-funcs=ft --ft-load-flags=0`, both with `--font-size=704`):

| | H | a | m | b | u | r | g | e | f | o | n | t | s | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unhinted | 502 | 383 | 617 | 395 | 388 | 231 | 395 | 373 | 244 | 402 | 388 | 230 | 363 | 76.73 px |
| hinted | 512 | 384 | 640 | 384 | 384 | 249 | 384 | 384 | 256 | 384 | 384 | 256 | 384 | 77.89 px |

Every hinted advance is a whole number of pixels, a multiple of 64, except the `r`’s: 249 is 256 less a GPOS kern of 7 against the `g`. HarfBuzz scales GPOS values itself, so kerning stays fractional; with `--features=-kern` the `r` is 256. A line set with hinted advances has a different length, and may break differently: an application has to choose before it shapes, not only before it draws.

A fractional size doesn’t survive hinting either. FreeType keeps a size in two forms: a ppem rounded to the nearest whole pixel, and a fractional scale that outlines and metrics are multiplied by. Unhinted, outlines follow the fractional scale. But a TrueType font with bit 3 of its `head` table’s flags set asks for a whole-number ppem in all its scaling, and when FreeType hints such a font it recomputes the scale from the rounded ppem, so a font requested at 10.5 pixels per em is hinted, drawn and measured at 11. That is in FreeType 2.15.0’s TrueType driver, whose comment says “Nearly all TrueType fonts have this bit set, as hinting won’t work really well otherwise” (its `src/truetype/ttobjs.c`, `tt_size_reset_height` and `tt_size_reset`).

> For programmers: hb-ft passes the font’s scale straight to `FT_Set_Char_Size`, which takes 26.6 fixed point (`hb-ft.cc:190`), so FreeType hints at a size of the scale divided by 64. `hb_ft_font_create_referenced` on an `FT_Face` sized with `FT_Set_Pixel_Sizes` sets the scale that way itself, to the pixel size times 64 (`hb-ft.cc:1509`); `hb-shape`’s `--font-size=704` above is 11 × 64 for the same reason. Then shape with that font, set hb-raster’s scale factor to 64, and draw each glyph at its shaped position. A font whose scale is in pixels or font units gets hinted at a meaningless size; with hinting off, as by default, the size doesn’t matter, which is why hb-ft can leave it so (`hb-ft.cc:75`).

The pairing has costs: hinted outlines and advances are good only at the size they were hinted for, so they can’t be cached once and scaled, and hb-ft takes a lock around every FreeType call (`hb-ft.cc:528`). Where hinting makes no visible difference, HarfBuzz’s own funcs and hb-raster need nothing else.

## Color glyphs

### The paint context

`hb_raster_paint_t` is a set of paint funcs with state, and turns the paint calls of [Color](color.html) into a BGRA32 image. Feeding it is like feeding the draw context, with three more settings: a foreground color, a background color and a palette index. `hb_raster_paint_glyph` sets the extents from the glyph’s, if the client hasn’t set any, pushes the context’s transform, and calls `hb_font_paint_glyph` (`hb-raster-paint.cc:2460`). That call falls back to filling the outline in the foreground color, so a paint context draws ordinary glyphs too. The `_or_fail` twin calls `hb_font_paint_glyph_or_fail`, which doesn’t fall back.

The `hb-raster` tool uses the paint context when the font has COLR or bitmap glyphs (`util/raster-output.hh:85`). Here is the COLR version 1 test font from [Color](color.html#colr-version-1-the-paint-graph): two composite modes, a linear gradient, the three extend modes of a radial gradient, a sweep gradient, and a rotated PaintColrGlyph:

```raster
zoom: 2
color/colr1.ttf  XMLPRFSG  --font-size=48
```

### Transforms, clips and surfaces

The context keeps three stacks (`hb-raster-paint.hh:118`). Transforms are multiplied together as they are pushed. Surfaces are premultiplied BGRA32 images, all the size of the output. Clips are A8 masks, also the size of the output. The first paint call sets up the bottom of each: a surface filled with the background color, and a clip that covers everything (`hb-raster-paint.cc:106`).

A glyph clip is rasterized by a draw context the paint context keeps for the purpose, through the current transform, and multiplied pixel by pixel into the clip below it (`hb-raster-paint.cc:283`). So clips are anti-aliased exactly as outlines are. A rectangle clip is cheaper. One that stays aligned with the pixel axes is kept as a rectangle, rounded outward to whole pixels, until something forces it to become a mask. A rotated or skewed one is made a mask by testing each pixel’s center against the transformed rectangle (`hb-raster-paint.cc:661`), so its edges are not anti-aliased. `fill_glyph`, the call that fills a plain outline, skips the clip stack: it rasterizes the glyph and fills through that mask directly (`hb-raster-paint.cc:934`).

### Groups and the composite modes

`push_group` adds a fresh, transparent surface to the stack; everything painted until the matching `pop_group` goes there. `pop_group` then composites it onto the surface below with the mode it is given (`hb-raster-paint.cc:807`). hb-raster implements all 28 modes of `hb_paint_composite_mode_t` pixel by pixel (`hb-raster-image.cc:411`): the 13 Porter–Duff operators, such as SRC_OVER, DEST_OUT and XOR; the 11 separable blend modes, such as MULTIPLY and SCREEN, computed on unpremultiplied components; and the four non-separable HSL modes. In the drawing above, `X` is a crescent, the blue disc with the red one cut out by DEST_OUT, and `M` darkens where the discs overlap. hb-vector’s SVG can’t express the first; hb-raster draws both as COLR describes them.

### Gradients

Each gradient is computed per pixel, at the pixel’s center, mapped back through the inverse of the current transform into the glyph’s coordinates (`hb-raster-paint.cc:1327`), and drawn through the current clip. Colors between stops are interpolated in premultiplied color, as the COLR specification asks (`hb-raster-paint.cc:1167`). When the clip covers at least 64 × 64 pixels, the color line is first sampled into a table of 256 entries and looked up instead (`hb-raster-paint.cc:1157`). The extend modes, pad, repeat and reflect, are applied to the position along the line before the lookup. Since the gradient is sampled once per pixel, a hard edge inside it, where a repeating gradient starts again, is not anti-aliased: it shows as the stair-steps in the rings of `R` above.

### Images

The `image` callback accepts two formats (`hb-raster-paint.cc:979`): BGRA, raw premultiplied pixels such as hb-ft produces, and PNG, which libpng decodes, after checking that its header promises no more than 4,096 pixels a side. Anything else is refused, and the paint API moves on to the glyph’s next representation, as [Color](color.html#bitmaps-sbix-and-cbdt) describes. That includes SVG, since 14.2.0, and PNG too in a build without libpng. The image is stretched over the glyph’s extents and sampled bilinearly (`hb-raster-paint.cc:1100`). In the test font’s `P`, an sbix glyph, the first image below uses the 100-pixel strike, scaled down; the second, with `--font-ppem=10`, uses the 10-pixel strike, and bilinear sampling blurs its 8 pixels across 48:

```raster
zoom: 3
color/images.ttf  P  --font-size=48
color/images.ttf  P  --font-size=48 --font-ppem=10
```

A CBDT font goes the same way. Here is the subset of Noto Color Emoji from HarfBuzz’s test suite:

```raster
zoom: 2
hb:test/api/fonts/NotoColorEmoji.subset.ttf  89®  --font-size=48
```

### Palettes, foreground and background

`hb_raster_paint_set_palette` chooses the CPAL palette, `hb_raster_paint_set_custom_palette_color` overrides single entries, which the context then hands back through the `custom_palette_color` callback (`hb-raster-paint.cc:1862`), and `hb_raster_paint_clear_custom_palette_colors` drops the overrides. The foreground color, opaque black by default, is what the font’s “text color” entry becomes, and what a glyph without color is filled with. The background, transparent by default (`hb-raster-paint.hh:114`; the tool makes it white), fills the surface before anything is painted. These are the COLR version 0 glyphs of [Color](color.html#palettes-cpal), first in palette 1, then with a red foreground, then with entry 1 replaced:

```raster
zoom: 3
color/colr0.ttf  AB  --font-size=32 --font-palette=1
color/colr0.ttf  AB  --font-size=32 --foreground=C02020
color/colr0.ttf  AB  --font-size=32 --custom-palette=1=#2E8B57
```

### BGRA32 output and PNG

`hb_raster_paint_render` returns the bottom surface: an image in `HB_RASTER_FORMAT_BGRA32`, four bytes a pixel, blue, green, red and alpha, premultiplied, rows bottom to top, its stride four times its width. It returns `NULL` if no extents were set (`hb-raster-paint.cc:2562`). `hb_raster_image_serialize_to_png_or_fail` (13.1.0) turns such an image into a PNG: it flips the rows and divides out the alpha, since PNG stores colors unpremultiplied (`hb-raster-image.cc:709`). It accepts only BGRA32 images, and needs libpng. `hb_raster_image_deserialize_from_png_or_fail` goes the other way, into a BGRA32 image with its origin at (0, 0).

### The pixel budget

A paint session has two budgets, kept apart on purpose (`hb-raster-paint.hh:131`). The outline budget is the shared one of [Drawing outlines](drawing-outlines.html#the-budget): the context hands it to its internal draw context before each glyph clip and reads back what is left (`hb-raster-paint.cc:213`, `:230`), so all the outlines a COLR glyph uses share one budget of 2²⁴. The **pixel budget** counts pixel work instead: clearing a surface, compositing a group, filling a gradient or a solid color over the clip, rendering and applying a mask. It starts, once the surface size is known, at 2²⁶ units or four passes over the surface, whichever is more. When it runs out, further operations are skipped: a hostile COLR graph that asks for thousands of full-surface groups gets a partly painted image, not a long wait. An unlimited budget turns it off.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-raster.h` | the API: images, the draw context, the paint context |
| `src/hb-raster.hh` | the flattening clip box, the pixel-work estimate, premultiplied pixel helpers |
| `src/hb-raster-draw.cc` | flattening, 593–1037; the analytic coverage rasterizer, 1238; `hb_raster_draw_render`, 1631 |
| `src/hb-raster-paint.hh` | the clip, surface and transform stacks; the two budgets |
| `src/hb-raster-paint.cc` | the paint callbacks: clips, 283–775; groups, 787; images, 979; gradients, 1157–1860; `hb_raster_paint_render`, 2562 |
| `src/hb-raster-image.cc` | the library’s overview documentation, 33; the 28 composite modes, 411; PNG through libpng, 542–790 |
| `src/hb-limits.hh` | the edge, size and buffer limits and the pixel budget, 184–268 |
| `src/hb-ft.cc` | load flags, 130 and 283; sizing FreeType from the font’s scale, 177; hinted advances and outlines, 525 and 1012 |
| `util/raster-output.hh`, `util/hb-raster.cc` | the `hb-raster` tool |
| `util/hb-ft-raster.cc` | the FreeType comparison tool |

## In short

* hb-raster is HarfBuzz’s CPU renderer, added in 13.0.0 and stable since 15.0.0. Its draw and paint contexts are draw and paint funcs with state.
* Outlines are flattened into 24.8 fixed-point edges and filled by exact area coverage under the nonzero winding rule, into A8 masks stored bottom to top. Glyphs can be placed at any fraction of a pixel.
* An edge limit, a size cap on font-derived extents, and a pixel budget bound what a font can make it do; it fails toward partial or blank images.
* It doesn’t hint, correct gamma, render for LCD subpixels or darken stems. Hinted text needs FreeType (or Skrifa) beside it: through hb-ft with hinting load flags, FreeType supplies hinted outlines and whole-pixel advances, and hb-raster rasterizes them.
* Color glyphs are painted on premultiplied BGRA32 surfaces, with all 28 composite modes, per-pixel gradients, and bilinearly sampled PNG or BGRA images; SVG glyphs are refused. The result can be written as PNG.
