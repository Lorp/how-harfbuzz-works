# Quick start: from text to SVG and PNG

This chapter puts a line of text on the screen, the shortest way there is, three times: in C with HarfBuzz itself, in JavaScript with harfbuzzjs, and in Rust with HarfRust. Each program loads a font, shapes a string, and draws the glyphs where shaping put them, first as SVG and then as a PNG. The rest of the book explains what happens at each step; here the steps are just run.

Every program below is in the book’s repository, in [`examples/quick-start/`](https://github.com/Lorp/how-harfbuzz-works/tree/main/examples/quick-start), and is compiled and run when the book is built: each picture under a listing is that program’s output. The commands around them are hand-written.

All of them use Roboto Regular, which is in HarfBuzz’s source as `test/subset/data/fonts/Roboto-Regular.ttf`, and the text “office coffee”. The text is chosen so that shaping shows: Roboto has an *ffi* ligature, so “office” comes out as four glyphs, not six. Roboto has no *ff* ligature, and “coffee” keeps both its f’s.

## From the command line

With HarfBuzz’s tools installed ([Building HarfBuzz](building-harfbuzz.html) shows how, and most package managers have them), it takes one command for each:

```
hb-vector Roboto-Regular.ttf "office coffee" -o office.svg
hb-raster Roboto-Regular.ttf "office coffee" --font-size=32 -o office.png
```

`hb-vector` writes SVG, in font units unless `--font-size` is given. `hb-raster` writes PNG, at 32 pixels to the em here:

```raster
zoom: 2
hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee  --font-size=32
```

Both tools arrived in HarfBuzz 13.0.0, and both libraries have been stable since 15.0.0, so a packaged HarfBuzz older than that doesn’t have them. `hb-raster` writes PNG only if HarfBuzz was built with libpng. [The command-line tools](command-line-tools.html) explains their options.

## In C

The C programs use HarfBuzz’s own drawing libraries: `libharfbuzz-vector` for SVG and `libharfbuzz-raster` for pixels, the ones the two tools are built on.

### SVG with hb-vector

```example
program: quick-start/c/text-to-svg.c
args: hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee
output: svg
```

The program does four things, and every HarfBuzz program does the first three.

**Load the font.** A [blob](blobs-faces-and-lazy-tables.html) holds the file’s bytes, a face reads the font in it, and a font is the face at a size. Nothing here sets a size, so the font works in font units, and so does everything after it.

**Shape.** The text goes into a [buffer](buffers.html) as UTF-8. `hb_buffer_guess_segment_properties` works out the script, language and direction from the text and the locale. A real application should set them, as [Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told) explains. `hb_shape` turns the characters into glyphs: after it, each `hb_glyph_info_t`’s `codepoint` is a glyph ID, not a character.

**Place the glyphs.** Each glyph has an advance, which moves the pen, and an offset, which moves the glyph from the pen without moving the pen. The loop adds them up. That is all the layout a single line needs: the glyphs are already in visual order, so the same loop serves right-to-left text.

**Draw.** `hb_vector_draw_glyph` draws a glyph’s outline at the current transform, and `HB_VECTOR_EXTENTS_MODE_EXPAND` grows the SVG’s box to fit it. `hb_vector_draw_render` returns the document.

To build it against an installed HarfBuzz, `pkg-config` supplies the flags:

```
cc text-to-svg.c $(pkg-config --cflags --libs harfbuzz-vector) -o text-to-svg
./text-to-svg Roboto-Regular.ttf "office coffee" > office.svg
```

To build it against a HarfBuzz that was built but not installed, point `pkg-config` at the build’s `meson-uninstalled` folder ([Building HarfBuzz](building-harfbuzz.html#what-a-build-makes)), and tell the program where the libraries are:

```
export PKG_CONFIG_PATH=$HOME/harfbuzz/build/meson-uninstalled
cc text-to-svg.c $(pkg-config --cflags --libs harfbuzz-vector) \
   -Wl,-rpath,$HOME/harfbuzz/build/src -o text-to-svg
```

### PNG with hb-raster

The PNG version is the same program with a size and a different drawing context:

```example
program: quick-start/c/text-to-png.c
args: hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee  32
output: png
```

Three things change. The font now has a size, set with `hb_font_set_scale` to 64 units a pixel, so that positions keep fractions of a pixel, and `hb_raster_paint_set_scale_factor` tells the rasterizer to divide by 64 again. The image’s size has to be given before drawing: here it is the line’s advance by the font’s ascender and descender, in whole pixels. And it uses a paint context, not a draw context, because only a painted image can be written as PNG (`hb_raster_image_serialize_to_png_or_fail` takes only color images). Painting has a bonus: a color font comes out in color, with no change to the program. [hb-raster](hb-raster.html) explains both contexts.

It builds the same way, with `harfbuzz-raster` in place of `harfbuzz-vector`.

## In JavaScript

[harfbuzzjs](https://github.com/harfbuzz/harfbuzzjs) is HarfBuzz compiled to WebAssembly, from the HarfBuzz project, with the C API wrapped in classes. It runs in Node and in browsers. Version 1.6.4, which these programs use, contains HarfBuzz 15.0.0, one release behind this book. It doesn’t include hb-vector or hb-raster, but it gives each glyph’s outline as SVG path data, which is enough for both jobs.

### SVG

```example
program: quick-start/js/text-to-svg.mjs
args: hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee
output: svg
```

It is the C program’s first three steps under other names: `Blob`, `Face`, `Font`, `Buffer` and `shape`. Drawing is done by hand: `glyphToPath` returns a glyph’s outline as path data in font units, with y going up, and each path is moved to its pen position. SVG’s y goes down, so the whole line is flipped with `scale(1,-1)`. The box is the line’s advance by the font’s ascender and descender.

```
npm install harfbuzzjs
node text-to-svg.mjs Roboto-Regular.ttf "office coffee" > office.svg
```

### Pixels, in a browser

In a browser, the canvas does the rasterizing: the same path data becomes a `Path2D`, and the canvas fills it.

```example
program: quick-start/js/text-to-canvas.mjs
args: hb:test/subset/data/fonts/Roboto-Regular.ttf
show: source
```

```demo
program: quick-start/js/text-to-canvas.mjs
font: hb:test/subset/data/fonts/Roboto-Regular.ttf
unicodes: 20-7E
text: office coffee
package: harfbuzzjs@1.6.4
```

<p class="print-only">The web edition of this book runs this program on the page, with a box to type text into.</p>

A canvas can be scaled and flipped once, so the glyphs are drawn in font units with y going up, and the canvas turns them into pixels. On a high-resolution screen, the canvas should have more pixels than it takes up on the page, `devicePixelRatio` times as many, or the text comes out blurred. The page above does that around `drawText`.

## In Rust

Rust programs usually don’t call HarfBuzz itself. They use HarfRust, a port of HarfBuzz’s shaping to Rust, which matches HarfBuzz {{hb}} but isn’t HarfBuzz: [HarfRust](harfrust.html) counts the differences. It only shapes, so the outlines come from Skrifa, part of the same Rust font libraries (Fontations). For C HarfBuzz itself, the `harfbuzz` crate has bindings, but they are less used.

### SVG with HarfRust and Skrifa

The project’s `Cargo.toml` asks for `harfrust = "0.16.0"` and `skrifa = "0.50.0"`, and `tiny-skia` for the PNG version.

```example
program: quick-start/rust/src/text-to-svg.rs
args: hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee
output: svg
```

The same steps again. HarfRust has no font size at all: it always shapes in font units, and a program scales the result. Skrifa’s `SvgPen` collects one glyph’s outline as path data, and the program writes the rest of the SVG as the JavaScript did.

```
cargo run --release --bin text-to-svg -- Roboto-Regular.ttf "office coffee" > office.svg
```

### PNG with tiny-skia

For pixels, Skrifa draws each outline at the size wanted, and [tiny-skia](https://github.com/linebender/tiny-skia), a small rasterizer, fills it:

```example
program: quick-start/rust/src/text-to-png.rs
args: hb:test/subset/data/fonts/Roboto-Regular.ttf  office coffee  32
output: png
```

The pen is the only new part. Skrifa calls a pen’s `move_to`, `line_to`, `quad_to`, `curve_to` and `close` with each point of the outline, y up and already scaled to pixels; this one adds the glyph’s position and turns y down, and builds one path for the whole line. It sizes its image as the C program does, and the two PNGs come out the same size.

## What these programs leave out

They are as short as they can be, and a real program needs more. In rough order of how soon it matters:

* **Script, language and direction**, set from what the application knows, not guessed. A string that mixes scripts or directions has to be split into runs first, each shaped on its own ([Why shaping exists](why-shaping-exists.html)).
* **Features**, such as small caps or old-style figures, passed to `hb_shape` ([From features to lookups](from-features-to-lookups.html)).
* **Fallback fonts.** A glyph ID of 0 means the font has no glyph for a character, and the application should find a font that does.
* **Line breaking.** HarfBuzz shapes a line; deciding where lines end is the application’s job, helped by the safe-to-break flags ([For applications](for-applications.html)).
* **Variable fonts**, set to a position with `hb_font_set_variations` ([The design space](design-space.html)).
* **Hinting and small sizes.** hb-raster and tiny-skia don’t hint. For hinted text, FreeType draws the outlines ([hb-raster](hb-raster.html) explains the trade).
* **Color fonts.** The C PNG program paints them already; the SVG programs would need hb-vector’s paint context, or a color library in JavaScript and Rust ([Color](color.html)).

## Where to read the source

| File | What it shows |
|---|---|
| [`examples/quick-start/`](https://github.com/Lorp/how-harfbuzz-works/tree/main/examples/quick-start) (in the book’s repository) | the programs on this page, with the JavaScript `package.json` and the Rust `Cargo.toml` |
| `util/vector-output.hh` | how `hb-vector` draws: the C SVG program, with options |
| `util/raster-output.hh` | how `hb-raster` draws, including its image sizes and margins |
| `src/hb-vector.h`, `src/hb-raster.h` | the drawing libraries’ API |
| `docs/usermanual-getting-started.xml` | HarfBuzz’s own first program, which shapes and prints the glyphs |

## In short

* Every program does the same three things first: load the font (blob, face, font), shape the text in a buffer, and walk the glyphs, adding up advances and offsets.
* In C, hb-vector draws the glyphs as SVG and hb-raster as pixels, and both are stable since HarfBuzz 15.0.0.
* In JavaScript, harfbuzzjs shapes, and gives outlines as SVG path data, for an SVG file or a canvas.
* In Rust, HarfRust shapes, Skrifa gives the outlines, and a rasterizer such as tiny-skia makes pixels. HarfRust is a port, not HarfBuzz.
* Real programs also set script, language and direction, split mixed text into runs, choose fallback fonts and break lines.
