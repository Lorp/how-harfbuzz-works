# hb-gpu: rendering on the GPU

The draw and paint APIs end at a callback. HarfBuzz walks the font’s data and calls the client: move here, curve to there, push this clip, fill with that gradient. Since 13.0.0 HarfBuzz has had renderers of its own, in three separate libraries: [hb-raster](hb-raster.html), which turns glyphs into pixel images on the CPU; [hb-vector](hb-vector.html), which writes them out as SVG or PDF; and hb-gpu, which arrived in 14.0.0. All three are clients of the APIs that [Drawing outlines](drawing-outlines.html) and [Color](color.html) describe, and nothing more. They see a glyph as an application would, with variations, synthetic bold and slant ([Fonts and font functions](fonts-and-font-functions.html#synthetic-bold-and-slant)) and the font’s scale already applied, and without hinting.

**hb-gpu** draws text on the GPU without first making bitmaps of its glyphs. It encodes each glyph’s curves on the CPU into a small block of integers, and a fragment shader, run for every pixel the glyph covers, works out from those curves how much of the pixel is inside the glyph. The method is **Slug**, Eric Lengyel’s algorithm, which hb-gpu implements with credit in its shader source (`hb-gpu-fragment.glsl:3–6`). Since coverage is computed from the curves wherever the glyph lands on screen, one encoding serves every size, rotation and perspective. HarfBuzz supplies the encoder and the shader functions; the application supplies the rest.

Nothing here can run in the book’s build, which has no GPU. The shader code is quoted from the source. The dumps of encoded glyphs were made by hand, with a short program, `fonts/hb-gpu/dump-gpu-blob.c`, run on the test fonts of earlier chapters.

## The library

The library is `libharfbuzz-gpu`, with the header `hb-gpu.h`, built when the [Meson option](building-harfbuzz.html#optional-dependencies-and-backends) `gpu` is enabled, as it is by default (`meson_options.txt:40`). The option `gpu_demo`, `auto` by default (`:42`), adds `hb-gpu`, an interactive viewer for shaped text that needs GLEW, GLFW, OpenGL and GLib (`util/meson.build:231`). It isn’t built here, because GLEW isn’t installed. An uninstalled tool, `hb-gpu-encode-all`, encodes every glyph of a font and reports sizes and times. `hb-features.h` is meant to define `HB_HAS_GPU` when the library is built, but in {{hb}} Meson never sets it: the book’s build has `#undef HB_HAS_GPU` there (`build/src/hb-features.h:100`).

It is the youngest of the three rendering libraries. It arrived in 14.0.0, its API was reviewed and changed in 14.2.0, and it has been covered by HarfBuzz’s API and ABI stability only since 15.0.0 (`NEWS`):

| Version | What happened |
|---|---|
| 14.0.0 | `libharfbuzz-gpu` arrives, for outlines only, with shaders in four languages and the `hb-gpu` viewer |
| 14.1.0 | extra samples at small sizes; the font’s scale stored in the encoded glyph |
| 14.2.0 | the API review: color glyphs, “based on design by Lê Duy Quang”; encoding returns the extents and clears the encoder; shader sources chosen by stage |
| 14.5.0 | work budgets, shared with the font code |
| 14.5.1 | a heap buffer overflow with malicious `COLR` fonts fixed |
| 15.0.0 | “no longer considered experimental”: API and ABI stability now apply |
| 15.1.0 | “wrong clipping of `COLR` layers” fixed |

There are two contexts. An **`hb_gpu_draw_t`** (14.0.0) encodes outlines; an **`hb_gpu_paint_t`** (14.2.0) encodes color glyphs. Each is an ordinary reference-counted HarfBuzz object, made with `_create_or_fail`, and each returns its result as an `hb_blob_t`. They are fed through their draw or paint funcs, from `hb_gpu_draw_get_funcs` or `hb_gpu_paint_get_funcs`, or through the convenience calls `hb_gpu_draw_glyph` and `hb_gpu_paint_glyph`. Those set the context’s scale from the font, then call `hb_font_draw_glyph_or_fail` or `hb_font_paint_glyph` (`hb-gpu-draw.cc:1073`, `hb-gpu-paint.cc:1460`). Since 14.2.0 they return nothing; each has an `_or_fail` twin that says whether the font had anything to draw or paint.

`_encode` packs what has been fed into a blob. It clears the context on the way out, whether it succeeded or not (`hb-gpu-draw.cc:457`, `hb-gpu-paint.cc:1509`), so one context serves glyph after glyph. `_clear` throws away what has been fed and keeps the settings; `_reset` restores the defaults as well. `_recycle_blob` takes a finished blob back, once its contents have been uploaded, and the next encode reuses its memory (`hb-blob.hh:220`). The documentation of `hb_gpu_draw_recycle_blob` still says that it “simply destroys the blob”, which was once true.

Both contexts implement the budget callbacks of [Drawing outlines](drawing-outlines.html#the-budget), and clearing recharges the budget. So one budget of 2²⁴ covers one glyph, as the contexts are normally used. The draw context charges one unit for every curve it stores and for every step of cubic conversion (`hb-gpu-draw.cc:55`, `hb-gpu-cu2qu.hh:176`).

The two contexts make different blobs for different shader functions. An application usually picks one per font: the documentation says the draw path is “meaningfully faster than Paint on monochrome fonts” (`hb-gpu.cc:54`). The `hb-gpu` viewer paints when the face has a `COLR` paint graph or layers, and draws otherwise (`util/gpu-output.hh:154`).

## Outlines

### The draw context

`hb_gpu_draw_t` keeps every piece of the outline as a quadratic Bézier curve, since quadratics are all the shader knows. A line becomes a quadratic whose control point is its start (`hb-gpu-draw.cc:116`). A quadratic is kept as it is. A cubic is converted by **cu2qu**, the cubic-to-quadratic conversion familiar from fontTools, in its own implementation (`hb-gpu-cu2qu.hh`). It tries one quadratic, and if that strays more than half a font unit from the cubic, splits the cubic in two and tries again, up to 10 levels deep; a piece that still doesn’t fit at the bottom becomes a straight line (`:187`). A cubic whose control points lie within that half unit of its chord is drawn as a line at once (`hb-gpu-draw.cc:155`). So TrueType outlines are encoded exactly, and CFF and cubic `GLYF` outlines to within half a unit. Closing a path adds the closing line, and a curve of zero length is dropped (`:85`).

The encoder works in whatever coordinates it is given, and the documentation asks for the font to be left at its default scale, the upem, with scaling done in the vertex shader (`hb-gpu.cc:221`). The reason is quantization. Every coordinate is stored as a 16-bit integer, in quarters of a unit (`HB_GPU_UNITS_PER_EM`, `hb-gpu-draw.hh:38`): a precision of 0.25 and a range of about ±8,000 units. Font units suit that; coordinates from 0 to 1 would vanish, as a comment in `hb-gpu.h` warns.

`hb_gpu_draw_encode (draw, &extents)` returns the blob, and the glyph’s extents, rounded outward to whole units (`hb-gpu-draw.cc:400`). Those extents are what the application builds the glyph’s quad from. A glyph with no ink, like a space, encodes as the empty blob, of length zero; a failure returns `NULL` (`:440`).

### Bands

Walking every curve of a glyph at every pixel would be slow, so the encoder divides the glyph’s box into **bands**: horizontal strips and vertical strips of equal size, as many as there are curves, up to 16 each way (“capped at 16 per Slug paper”, `hb-gpu-draw.cc:510`). Each band lists the curves that reach into it. A horizontal band doesn’t list horizontal lines, and a vertical band doesn’t list vertical ones, since a ray along a band can never cross them (`:541`).

Each band has its list twice. One copy is sorted by the curves’ right (or top) ends, largest first, the other by their left (or bottom) ends, smallest first (`:626`). The band also stores a split point, chosen so that the longer of the two lists a pixel might need is as short as possible (`:793`). A pixel on the near side of the split looks one way along the band and reads one list; a pixel on the far side looks the other way and reads the other. Either way, the curves come nearest first, and the shader can stop as soon as they are out of reach.

Bands are worked out from the quantized points, not the original ones, because the shader only ever sees the quantized ones. A comment records what happened when the two disagreed: a curve left out of a band it reached into, wrong winding numbers in that sliver, and “a thin black line through the glyph” (`:357`).

### The blob

The blob is an array of **texels**, the elements of a GPU texture or buffer: here each is four signed 16-bit integers, the format OpenGL calls RGBA16I, 8 bytes in all (`hb-gpu.cc:70`). In order, it holds:

| Texels | Contents |
|---|---|
| 0 | the glyph’s box: minimum x and y, maximum x and y, in quarter units |
| 1 | the number of horizontal and vertical bands; the font’s x and y scale |
| one per band | the band’s curve count, the offsets of its two lists, and its split point |
| the lists | one curve offset per texel |
| the curves | the control points, shared between neighbors |

A curve is three points, but neighbors on one contour share one. The first texel of a contour holds the first curve’s start and control point. Every texel after it holds one curve’s end and the next curve’s control point, which is also where the next curve starts (`hb-gpu-draw.cc:752`). So a contour of *n* curves takes *n* + 1 texels, and a curve’s offset points at the texel with its start. Offsets are stored as 16-bit numbers less 32,768 (`:352`), so a glyph’s blob can be at most 65,536 texels long (`:706`).

Here is the blob for the `square` glyph of [Drawing outlines](drawing-outlines.html)’ `limits.ttf`, a square 100 units on a side drawn as four lines, trimmed in the middle. It was made by hand with `dump-gpu-blob limits.ttf square`, not when the page was built:

```text
square: 376 bytes, 47 texels
  0:      0      0    400    400
  1:      4      4   1000   1000
  2:      2 -32758 -32756    200
  3:      2 -32754 -32752    200
   …
  9:      2 -32730 -32728    200
 10: -32724      0      0      0
 11: -32726      0      0      0
   …
 41: -32725      0      0      0
 42:      0      0      0      0
 43:      0    400      0    400
 44:    400    400    400    400
 45:    400      0    400      0
 46:      0      0      0      0
```

Texel 0 is the box, from 0 to 400 quarter units. Texel 1 has four bands each way, one per curve, and the font’s scale of 1,000. Texels 2 to 5 are the horizontal bands and 6 to 9 the vertical ones. Each band holds two curves, its two lists start at texels 10 and 12 (−32,758 + 32,768 and −32,756 + 32,768), and it splits at 200, the square’s middle. The horizontal bands all list the two vertical sides, at texels 44 and 42; the vertical bands list the top and bottom, at 43 and 45. The curves start at texel 42: (0, 0) with its control point (0, 0), on to (0, 400) with the next control point (0, 400), and so round the square to (0, 0) again.

Four lines take 376 bytes. Most of them go on the lists, where each texel uses only its first component (`:815`): 32 of the 47 texels here. Other glyphs from the same chapter’s fonts, by the same program:

| Glyph | Font | Curves | Bytes |
|---|---|---|---|
| `square` | `limits.ttf` | 4 lines | 376 |
| `i` | `outlines.ttf` | stem and dot | 992 |
| `b` | `outlines.ttf` | bowl and stem, quadratics | 1,592 |
| `o` | `cff.otf` | cubics, through cu2qu | 3,552 |

### What the application supplies

The shaders come with the library, in four languages: GLSL (OpenGL 3.3, OpenGL ES 3.0, WebGL 2), WGSL (WebGPU), MSL (Metal) and HLSL (Direct3D) (`hb-gpu.h:37`). They are compiled in as strings by `gen-gpu-shader-artifacts.py` (`src/meson.build:835`). `hb_gpu_shader_source (stage, lang)` returns the helpers both renderers share, and `hb_gpu_draw_shader_source` the draw renderer’s part, an empty string for the vertex stage. An application builds each of its shaders by joining a version line, those two, and a `main` of its own (`hb-gpu.cc:119`).

Everything outside the shader functions is the application’s. Following the documentation (`hb-gpu.cc:95`), that is:

* **The atlas.** All the blobs go into one buffer, an **atlas** of encoded curves rather than of pixels, each at an offset the application chooses. In OpenGL it is a texture buffer of RGBA16I, bound to the uniform `hb_gpu_atlas`. WebGL 2 has no texture buffers, so defining `HB_GPU_ATLAS_2D` before the shader source makes the atlas a 2D integer texture instead, with its width in the uniform `hb_gpu_atlas_width` (`hb-gpu-fragment.glsl:60`). In WGSL the atlas is a storage buffer, passed to each function as a pointer; in MSL a `device` pointer; in HLSL a `StructuredBuffer`.
* **The vertices.** Each glyph is one quad, two triangles, built from its extents and the pen position from shaping, scaled by font size over upem. Each corner carries its position, its texture coordinate (the corner of the glyph’s box in font units), an outward normal, the inverse of the font-unit-to-screen scale, and the glyph’s offset in the atlas, which the vertex shader passes on as a flat varying (`hb-gpu.cc:157`).
* **The uniforms.** The model-view-projection matrix and the viewport size in pixels, for the vertex helper.
* **Blending.** Coverage comes back as alpha, to blend with `GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA` or multiply with any color.

The vertex helper, `hb_gpu_dilate` (`hb-gpu-vertex.glsl:43`), moves each corner out by half a pixel on screen, correctly under perspective, and its texture coordinate with it. Without that, the soft edge of a glyph would be cut off at the edge of its quad. An application that only draws flat text can instead pad every quad by half a pixel at the smallest size it expects, at the cost of shading more empty pixels at larger sizes (`hb-gpu.cc:264`). The fragment helper is `hb_gpu_draw`, and the documentation’s minimal fragment shader (`hb-gpu.cc:314`) is:

```glsl
in vec2 v_texcoord;
flat in uint v_glyphLoc;
out vec4 fragColor;

void main () {
  float coverage = hb_gpu_draw (v_texcoord, v_glyphLoc);
  fragColor = vec4 (0.0, 0.0, 0.0, coverage);
}
```

### What the fragment shader computes

`hb_gpu_draw` measures the size of a pixel in font units with `fwidth`, then calls the shared Slug code (`hb-gpu-draw-fragment.glsl:34`). That reads the blob’s two header texels and picks the pixel’s horizontal and vertical band from its position (`hb-gpu-fragment.glsl:142`). Then, in `_hb_gpu_slug_single` (`:185`), it casts a ray along each band from the pixel’s center, in the direction the band’s split point chooses, and walks that band’s list, trimmed here:

```glsl
for (int ci = 0; ci < hCurveCount; ci++)
{
  …
  if (hLeftRay) {
    if (min (min (p12.x, p12.z), p3.x) * pixelsPerEm.x > 0.5) break;
  } else {
    if (max (max (p12.x, p12.z), p3.x) * pixelsPerEm.x < -0.5) break;
  }

  uint code = _hb_gpu_calc_root_code (p12.y, p12.w, p3.y);
  if (code != 0U)
  {
    …
    vec2 r = _hb_gpu_solve_horiz_poly (a, b, p12.xy) * pixelsPerEm.x;
    vec2 cov = hLeftRay ? clamp (vec2 (0.5) - r, 0.0, 1.0)
                        : clamp (r + vec2 (0.5), 0.0, 1.0);
    …
  }
}
```

The `break` is why the lists are sorted: once one curve is more than half a pixel behind the ray’s start, so are the rest. For each curve still in reach, the signs of its three points relative to the ray say which of its two possible crossings count, and in which direction, without solving anything (`_hb_gpu_calc_root_code`, `:78`). For those, the shader solves the quadratic for where the curve crosses the ray, in pixels from the center. A crossing more than half a pixel ahead counts fully, one more than half a pixel behind not at all, and one in between in proportion. Added up with their signs, the crossings give the winding number, blurred across one pixel: 0 outside the glyph, 1 inside, a fraction at an edge.

The vertical ray does the same, and `_hb_gpu_calc_coverage` (`:122`) combines the two, weighting each by how close its nearest crossing was to the pixel’s center, since the ray across an edge measures it better than the ray along it. The result is the absolute value, clamped to 0 to 1, so overlapping contours wound the same way don’t add up to more than full coverage: in effect the nonzero fill rule.

### Small sizes

At small sizes a pixel can hold several stems, and `_hb_gpu_slug` (`hb-gpu-fragment.glsl:314`) takes four more samples, a third of a pixel from the center diagonally, and blends their average in below 16 pixels per em, fully so by 8. Defining `HB_GPU_NO_MSAA` turns that off, in the GLSL and HLSL shaders; the WGSL and MSL ones have no switch.

The pixels per em come from the font scale in the blob’s header and the pixel size in font units (`hb_gpu_ppem`, `:167`). `hb_gpu_draw_glyph` stores the font’s scale; an application that feeds its own shapes through the draw funcs should call `hb_gpu_draw_set_scale` first. Otherwise the scale is 0, the size always comes out as 0 pixels per em, and every pixel takes the extra samples.

`hb_gpu_stem_darken (coverage, brightness, ppem)` (`:344`) is optional. It raises an edge pixel’s coverage under dark text and lowers it under light text, so that thin stems keep their weight, and fades out between 8 and 48 pixels per em. The documentation computes its `ppem` argument as `1.0 / max (fwidth (v_texcoord).x, fwidth (v_texcoord).y)` (`hb-gpu.cc:349`), and so does the `hb-gpu` viewer (`util/gpu/demo-fragment.glsl:35`). With texture coordinates in font units, as the documentation sets them up, that is pixels per unit, not per em, a thousand times too small for a 1,000-unit font, so the darkening never fades out (inferred from the code; it can’t be run here). `hb_gpu_ppem` returns the true figure. Gamma correction is left to the application, as in the documentation’s example (`hb-gpu.cc:512`).

Nothing in hb-gpu hints, and nothing renders for the subpixels of an LCD.

### Limits on outlines

| Limit | Value | When it’s reached |
|---|---|---|
| `HB_GPU_DRAW_MAX_CURVES` (`hb-limits.hh:135`) | 65,536 curves | the encoder returns `NULL` (`hb-gpu-draw.cc:58`) |
| texels in one blob | 65,536 | the same (`:706`) |
| coordinates | −8,192 to 8,191.75 units, the int16 range in quarters | the same (`:491`) |
| `HB_GPU_CU2QU_MAX_DEPTH` (`hb-gpu-cu2qu.hh:48`) | 10 splits | the remaining piece becomes a line |
| the budget | 2²⁴ | curves stop being stored |

The texel limit comes first. Each curve takes a texel of its own and an entry in two lists for every band it reaches, in each direction, so a glyph runs out of texels somewhere below 22,000 curves (inferred from the layout).

## Color glyphs

### The paint context

`hb_gpu_paint_t` turns a color glyph into a blob for the shader function `hb_gpu_paint`. Its design notes put the idea in one sentence: “The fragment shader is the interpreter: it walks a flat op stream per pixel, maintains a small group stack, and composites the result” (`hb-gpu-paint.hh:41`). The context implements the paint callbacks of [Color](color.html#the-paint-api) and keeps a transform stack and a stack of up to three pending clips. Each clip is a glyph, or since 14.2.0 a path drawn through `push_clip_path_start`. When a color or gradient callback arrives, it becomes one layer, painted through every clip on the stack.

Each clip’s outline is encoded as a draw blob of its own, by a draw context the paint context keeps for the purpose, with the transform that was current when the clip was pushed applied to every point (`hb-gpu-paint.cc:529`). A glyph clip is encoded the first time a layer needs it and reused for the other layers under it (`:598`). The same outline at two different translations is encoded twice: the design notes leave sharing those for a “v2” (`hb-gpu-paint.hh:117`).

Colors are settled when the glyph is encoded. `hb_gpu_paint_set_palette` chooses the palette and `hb_gpu_paint_set_custom_palette_color` overrides entries; both are kept across clears, and changing either means encoding the glyphs again. The foreground color is the exception. A layer or color stop marked as foreground is colored by an argument to the shader, with the alpha from the paint graph, “so dark-mode and color-change toggles take effect without re-encoding” (`hb-gpu.cc:403`). That is why `hb_gpu_paint_glyph` asks HarfBuzz to paint with opaque black as the foreground (`hb-gpu-paint.cc:1480`): only the alpha of a foreground color goes into the blob.

`hb_gpu_paint_glyph` calls `hb_font_paint_glyph`, so a glyph with no color version is painted as its outline, filled with the foreground: one layer. `hb_gpu_paint_glyph_or_fail` calls `hb_font_paint_glyph_or_fail` instead, and reports when a glyph has no color version. Neither reports the encoder’s own limits: those surface as `hb_gpu_paint_encode` returning `NULL` (`:1415`).

### The paint blob

The paint blob has the same texel format as the draw blob, so both kinds can share one atlas. It starts with three header texels: the number of operations, the ink box in font units, and the offset of the first operation (`hb-gpu-paint.cc:1575`). Then come the operations, four kinds (`:41`):

| Operation | Texels | Contents |
|---|---|---|
| solid layer | 3 | flags; the offsets of up to three clip outlines; the color, as four 15-bit fractions |
| gradient layer | 3 | the gradient’s kind and flags; up to three clip offsets; the offset of its parameters, its extend mode and number of stops |
| push group | 1 | nothing more |
| pop group | 1 | the composite mode, numbered as in `hb_paint_composite_mode_t` |

After the operations come the clip outlines, each a complete draw blob, and the gradients’ parameters. Offsets inside a paint blob are 32-bit, made of two 16-bit halves, so a paint blob can be longer than a draw blob. A gradient’s parameters hold its origin, already transformed, and its axis, radii or angles in the gradient’s own coordinates, with the inverse of the transform’s linear part as four fixed-point numbers with 10 fractional bits. Each stop takes two texels: its offset, a foreground flag, and its color (`:715`). Geometry is stored in whole font units (`:797`).

The design notes in `hb-gpu-paint.hh` describe an earlier layout (one-texel operations, 16.16 transforms, palette indices in stops); the code is what {{hb}} writes.

A plain glyph through the paint context shows the layout at its smallest. Here is `square` again, from `dump-gpu-blob limits.ttf square paint`, made by hand and trimmed:

```text
square: 424 bytes, 53 texels
  0:      1      0      0      0
  1:      0      0    100    100
  2:      3      0      0      0
  3:      0      1      0      6
  4:      0      0      0      0
  5:      0      0      0  32767
  6:      0      0    400    400
  7:      4      4   1000   1000
   …
```

One operation; the box from (0, 0) to (100, 100); operations from texel 3. The operation is a solid layer (type 0) with the foreground flag (1), clipped by the outline at texel 6 and by nothing else, in black at full alpha. From texel 6 on, the draw blob from before follows unchanged. So a plain glyph costs six texels more on the paint path. The test glyphs of [Color](color.html) encode at 480 to 504 bytes for one gradient through one clip (`L`, `P`, `R`, `F`, `S`) and 1,944 bytes for two discs and a PaintComposite (`X`, `M`).

### The paint shader

`hb_gpu_paint_shader_source` adds the paint interpreter to the shared helpers. Its documentation puts the draw source between them; the overview in `hb-gpu.cc:440` leaves it out. The interpreter calls only the shared Slug code, so both work. The entry point is

```glsl
vec4 hb_gpu_paint (vec2 renderCoord, uint glyphLoc, vec4 foreground,
                   out float coverage);
```

and it walks the operations in order, for every pixel (`hb-gpu-paint-fragment.glsl:296`). A layer’s coverage is the product of its clips’ coverages, each computed as in the draw shader, and skipped for a clip whose box, plus two pixels, doesn’t contain the pixel (`:254`). Its color is the baked color, or the foreground argument, or a gradient evaluated at the pixel. The pixel’s position is taken back through the stored inverse into the gradient’s own coordinates, so a gradient under a shear or uneven scale is exact, not approximated (`:102–191`). The extend modes pad, repeat and reflect are all applied (`:49`), and stops are interpolated in premultiplied color, as the `COLR` specification requires (`:76`). The layer is then composited over what has accumulated, with ordinary source-over.

A push saves the accumulated color on a stack of four and starts afresh. A pop composites the group onto what was saved with its mode, in `_hb_gpu_composite` (`:196`):

| Modes | In the shader |
|---|---|
| CLEAR, SRC, DEST, the OVER, IN, OUT and ATOP pairs, XOR, PLUS | exact |
| SCREEN, DARKEN, LIGHTEN, MULTIPLY | exact |
| OVERLAY, COLOR_BURN, HARD_LIGHT | drawn as MULTIPLY |
| COLOR_DODGE, SOFT_LIGHT | drawn as SCREEN |
| DIFFERENCE, EXCLUSION, the four HSL modes | drawn as SRC_OVER |

`hb_gpu_paint` returns premultiplied color, to blend with `GL_ONE, GL_ONE_MINUS_SRC_ALPHA`. Its `coverage` output is the largest coverage of any layer at the pixel. The documentation’s example applies stem darkening and gamma to that, and scales the color to match, only at edge pixels, so that the colors inside a glyph are left as the font gave them (`hb-gpu.cc:493`).

### What isn’t supported

**Images.** The paint context’s `image` callback marks the glyph as unsupported, so a glyph from `sbix`, `CBDT` or `SVG ` encodes as `NULL` (`hb-gpu-paint.cc:1077`). The callback returns false, so HarfBuzz goes on to the next table and finally the outline, as [Color](color.html#which-picture-gets-painted) explains, but the mark stays, and the glyph still fails: the caller learns that “the glyph won’t render rather than getting a partial blob”. In `images.ttf` from [Color](color.html), `S`, `T` and `P` encode as `NULL`. An application can fall back to the draw context, as `hb-gpu-encode-all` does, or draw images some other way.

**Rectangle clips.** ClipBoxes and PaintClipBox reach the paint context as rectangle clips, and it ignores them: “output is bigger than it should be, but renders” (`:1074`). That holds when a glyph or path clip is also on the stack. A fill whose only clip is a rectangle is dropped, because a layer needs at least one outline to be painted through (`:673`). So `C` in [Color](color.html#clipboxes-and-unbounded-paint)’s `colr1.ttf`, a PaintSolid inside its ClipBox, encodes as the empty blob, where the other renderers paint a square.

**Variations.** A blob is made from the outlines and paint graph at the font’s current variation coordinates, so each instance of a variable font needs its own encoding.

### Limits on color glyphs

Each of these makes `hb_gpu_paint_encode` return `NULL` rather than a blob that would render wrongly (`hb-gpu-paint.cc:48`):

| Limit | Value |
|---|---|
| `HB_GPU_PAINT_MAX_OPS` (`hb-gpu-paint.cc:51`) | 32,767 operations |
| `HB_GPU_PAINT_MAX_GROUP_DEPTH` (`:52`) | 4 nested groups, the shader’s stack |
| `HB_GPU_PAINT_MAX_CLIP_DEPTH` (`:53`) | 3 clips intersected for one layer |
| `HB_GPU_PAINT_MAX_SUB_BLOBS` (`:54`) | 1,024 clip outlines and gradients |
| `HB_GPU_PAINT_MAX_SUB_BYTES` (`hb-limits.hh:158`) | 64 MiB of clip outlines and gradients |
| the budget | 2²⁴ for the whole walk |

Only the last two are in `hb-limits.hh`, where an application can change them; the others match fixed sizes in the shader or the blob. The budget is shared by everything the walk does: the paint graph, every clip outline drawn into the scratch draw context, and every layer’s use of a clip, charged by the clip’s size in texels, since the shader walks a clip’s bands again for every layer painted through it (`:627`).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-gpu.h`, `src/hb-gpu.cc` | the API, and its long usage documentation: atlas, vertex attributes, dilation, fragment shaders, stem darkening |
| `src/hb-gpu-draw.hh`, `src/hb-gpu-draw.cc` | the draw context; quantizing, banding and packing, `hb_gpu_draw_encode`, 451 |
| `src/hb-gpu-cu2qu.hh` | cubics to quadratics |
| `src/hb-gpu-fragment.glsl` | the shared fragment helpers: atlas access, Slug, the extra samples, stem darkening |
| `src/hb-gpu-draw-fragment.glsl`, `src/hb-gpu-vertex.glsl` | `hb_gpu_draw`; `hb_gpu_dilate` |
| `src/hb-gpu-paint.hh`, `src/hb-gpu-paint.cc` | the paint context, its design notes, the encoder and its limits, 48 |
| `src/hb-gpu-paint-fragment.glsl` | the interpreter: gradients, composite modes, `hb_gpu_paint` |
| `src/hb-gpu-*.wgsl`, `.msl`, `.hlsl` | the same shaders in the other three languages |
| `src/gen-gpu-shader-artifacts.py` | turns each shader into a C string |
| `util/gpu-output.hh`, `util/gpu/` | the `hb-gpu` viewer, and its renderers for OpenGL, Metal and Direct3D |
| `util/hb-gpu-encode-all.cc` | encodes every glyph of a font, for sizes and timing |

## In short

* hb-gpu encodes glyphs on the CPU for a fragment shader to draw on the GPU, with Eric Lengyel’s Slug algorithm. One encoding serves every size and transform. It arrived in 14.0.0, gained color glyphs in 14.2.0, and has been stable since 15.0.0.
* `hb_gpu_draw_t` turns an outline into quadratics, converting cubics with cu2qu to within half a unit, quantizes them to quarter units, and packs them into a blob of RGBA16I texels: a header, up to 16 bands each way with two sorted lists each, and curves that share their endpoints.
* The application uploads the blobs into one atlas, draws one quad per glyph, and joins HarfBuzz’s shader source, in GLSL, WGSL, MSL or HLSL, with its own `main`. `hb_gpu_dilate` pads each quad by half a pixel; `hb_gpu_draw` returns coverage from a winding number blurred over one pixel, with four more samples below 16 pixels per em.
* `hb_gpu_paint_t` turns a color glyph into a stream of layers and groups for an interpreter in the shader. Palettes are baked in; the foreground color stays a shader argument. Gradients are exact under any transform, and most composite modes are.
* Images make the encoder fail, rectangle clips are ignored, and five composite modes are approximated and six drawn as source-over. A color glyph may nest four groups and intersect three clips per layer.
* Nothing in hb-gpu hints. Gamma correction, and the stem darkening the library offers, are the application’s choice.
