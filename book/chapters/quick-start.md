# Quick start: shaping text, then drawing it

The [previous chapter](command-line-tools.html) ran HarfBuzz’s tools: `hb-shape` to see what shaping does to a line of text, and `hb-vector` and `hb-raster` to [draw it](command-line-tools.html#what-does-this-text-look-like-in-this-font). This chapter writes programs that do the same, small versions of those three tools, in four languages:

* **C**, with HarfBuzz itself;
* **JavaScript**, with harfbuzzjs, HarfBuzz compiled to WebAssembly;
* **Python**, with uharfbuzz, HarfBuzz’s Python bindings;
* **Rust**, with HarfRust, a port of HarfBuzz’s shaping to Rust.

Each language’s section starts with the smallest useful HarfBuzz program: it loads a font, shapes a string, and prints the glyphs that come out, as `hb-shape` does. Two more programs then draw those glyphs where shaping put them, as SVG and as a PNG. The rest of the book explains what happens at each step; here the steps are just run.

> This chapter is for programmers who want HarfBuzz in their own software, and for font engineers who script their work: the Python section is the place to start for tests and proofs that shape text in bulk. Its [first program](#glyphs-in-python) is worth trying even for a reader who has never written one. It is 25 lines, it needs one `pip install`, and changing it to shape a whole word list with your own font is a small step. Type designers who only want to see what HarfBuzz does with a font have what they need in the previous chapter’s tools, and can skip ahead. [How to read this book](introduction.html#how-to-read-this-book) says which other chapters a programmer needs.
>
> This book explains what HarfBuzz does inside; it isn’t HarfBuzz’s manual. [HarfBuzz’s own documentation](https://harfbuzz.github.io/), its user manual and API reference, is the definitive account of what each function does and promises, and the place to look things up while programming. The end of this chapter lists the references for the other languages too.

Every program below is in the book’s repository, in [`examples/quick-start/`](https://github.com/Lorp/how-harfbuzz-works/tree/main/examples/quick-start), and is compiled and run when the book is built: what is shown under a listing is that program’s output. The commands around them are hand-written.

All of the examples use Libre Baskerville, a Baskerville by Impallari Type under the SIL Open Font License, and the text “office coffee”, as the previous chapter did. The text is chosen so that shaping shows: the font’s standard ligatures turn the *ffi* of “office” and the *ff* of “coffee” into one glyph each, so the thirteen characters become ten glyphs. The font is in the book’s repository, in [`fonts/quick-start/`](https://github.com/Lorp/how-harfbuzz-works/tree/main/fonts/quick-start), and comes from Google Fonts, which is where to get it:

```
curl -L -o LibreBaskerville.ttf \
  "https://github.com/google/fonts/raw/main/ofl/librebaskerville/LibreBaskerville%5Bwght%5D.ttf"
```

It is a variable font, with weights from 400 to 700, and every program here draws its default, 400.

## In C

The first C program uses HarfBuzz itself, `libharfbuzz`. The two that draw also use HarfBuzz’s drawing libraries: `libharfbuzz-vector` for SVG and `libharfbuzz-raster` for pixels, the ones the two tools are built on.

### Glyphs, as hb-shape prints them

```example
program: quick-start/c/text-to-glyphs.c
args: LibreBaskerville.ttf  office coffee
output: text
same-as: hb-shape --utf8-clusters
```

The program does three things, and every HarfBuzz program does them.

**Load the font.** A [blob](blobs-faces-and-lazy-tables.html) holds the file’s bytes, a face reads the font in it, and a font is the face at a size. Nothing here sets a size, so the font works in font units, and so does everything after it.

**Shape.** The text goes into a [buffer](buffers.html) as UTF-8. `hb_buffer_guess_segment_properties` works out the script, language and direction from the text and the locale. A real application should set them, as [Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told) explains. `hb_shape` turns the characters into glyphs: after it, each `hb_glyph_info_t`’s `codepoint` is a glyph ID, not a character.

**Read the result.** After shaping, the buffer holds two arrays of the same length. Each `hb_glyph_info_t` has the glyph’s ID and its **cluster**, which says where in the text the glyph came from. Each `hb_glyph_position_t` has the glyph’s advance and its offset. The loop prints them in `hb-shape`’s format, which [Reading this book](notation.html#shaping-results) explains: the glyph’s name, `=` and its cluster, `@` and its offset if it has one, `+` and its advance. `hb_font_glyph_to_string` gives the glyph’s name, or `gid` and its number in a font without names. The *ffi* of “office” has become one glyph, `f_f_i`, and the next glyph’s cluster jumps from 1 to 4, because three characters went into it.

Programmers often want glyph IDs, not names, and `hb-shape` prints them with `--no-glyph-names`:

```shape
LibreBaskerville.ttf  office coffee  --no-glyph-names
```

The program can do the same by printing `info[i].codepoint` in place of the name: after shaping, that field holds the glyph ID. The same one-word change works in the other three languages.

The build checks that this output is exactly what `hb-shape` prints for the same font and text. `hb-shape` does it without a loop: `hb_buffer_serialize` writes a buffer in this format (`util/shape-format.hh`).

The clusters count bytes of UTF-8, because that is how the text was given to the buffer. `hb-shape` counts characters unless it is run with `--utf8-clusters`, so for text beyond ASCII the two differ until that option is added. For “office coffee” they agree.

### Building and running

The programs are written for HarfBuzz {{hb}}. First, ask `pkg-config` which HarfBuzz you have:

```
pkg-config --modversion harfbuzz
```

If it prints {{hb}} or later, compile and run against it:

```
cc text-to-glyphs.c $(pkg-config --cflags --libs harfbuzz) -o text-to-glyphs
./text-to-glyphs LibreBaskerville.ttf "office coffee"
```

If it prints an older version, or says the package wasn’t found, build HarfBuzz {{hb}} yourself. It takes a minute or two, and doesn’t touch any HarfBuzz you have installed. You need a C++ compiler, `pkg-config`, Meson and Ninja (`brew install meson ninja pkg-config` on a Mac, `apt install meson ninja-build pkg-config` on Debian and Ubuntu), and for the PNG program below, libpng (`brew install libpng`, or `apt install libpng-dev`). Then, in the folder with the programs:

```
git clone --depth 1 --branch {{hb}} https://github.com/harfbuzz/harfbuzz.git
meson setup harfbuzz/build harfbuzz
ninja -C harfbuzz/build
```

Point `pkg-config` at the build’s `meson-uninstalled` folder ([Building HarfBuzz](building-harfbuzz.html#what-a-build-makes)), and tell the program where the libraries are:

```
export PKG_CONFIG_PATH=$PWD/harfbuzz/build/meson-uninstalled
cc text-to-glyphs.c $(pkg-config --cflags --libs harfbuzz) \
   -Wl,-rpath,$PWD/harfbuzz/build/src -o text-to-glyphs
./text-to-glyphs LibreBaskerville.ttf "office coffee"
```

[Building HarfBuzz](building-harfbuzz.html) explains the build in full, including Windows.

### SVG with hb-vector

The SVG program is the same program with drawing in place of printing:

```example
program: quick-start/c/text-to-svg.c
args: LibreBaskerville.ttf  office coffee
output: svg
```

**Place the glyphs.** Each glyph has an advance, which moves the pen, and an offset, which moves the glyph from the pen without moving the pen. The loop adds them up. That is all the layout a single line needs: the glyphs are already in visual order, so the same loop serves right-to-left text.

**Draw.** `hb_vector_draw_glyph` draws a glyph’s outline at the current transform, and `HB_VECTOR_EXTENTS_MODE_EXPAND` grows the SVG’s box to fit it. `hb_vector_draw_render` returns the document.

It builds as the first program did, with `harfbuzz-vector`, HarfBuzz’s SVG library, in place of `harfbuzz` (and the same `-Wl,-rpath` option, if you built HarfBuzz yourself):

```
cc text-to-svg.c $(pkg-config --cflags --libs harfbuzz-vector) -o text-to-svg
./text-to-svg LibreBaskerville.ttf "office coffee" > office.svg
```

### PNG with hb-raster

The PNG version is the same program with a size and a different drawing context:

```example
program: quick-start/c/text-to-png.c
args: LibreBaskerville.ttf  office coffee  32
output: png
```

Three things change. The font now has a size, set with `hb_font_set_scale` to 64 units a pixel, so that positions keep fractions of a pixel, and `hb_raster_paint_set_scale_factor` tells the rasterizer to divide by 64 again. The image’s size has to be given before drawing: here it is the line’s advance by the font’s ascender and descender, in whole pixels. And it uses a paint context, not a draw context, because only a painted image can be written as PNG (`hb_raster_image_serialize_to_png_or_fail` takes only color images). Painting has a bonus: a color font comes out in color, with no change to the program. [hb-raster](hb-raster.html) explains both contexts.

It builds with `harfbuzz-raster`, and takes a size in pixels as well:

```
cc text-to-png.c $(pkg-config --cflags --libs harfbuzz-raster) -o text-to-png
./text-to-png LibreBaskerville.ttf "office coffee" 32 > office.png
```

If HarfBuzz was built without libpng, it prints “nothing to write”: Meson uses libpng only if it finds it, and says whether it did in the summary it prints at the end of `meson setup`.

## In JavaScript

[harfbuzzjs](https://github.com/harfbuzz/harfbuzzjs) is HarfBuzz compiled to WebAssembly, from the HarfBuzz project, with the C API wrapped in classes. It runs in Node and in browsers. Version 1.6.4, which these programs use, contains HarfBuzz 15.0.0, one release behind this book. It doesn’t include hb-vector or hb-raster, but it gives each glyph’s outline as SVG path data, which is enough for both jobs.

harfbuzzjs names follow HarfBuzz’s with one rule: drop `hb_` and the object’s name, make the function a method of a class (`Blob`, `Face`, `Font`, `Buffer`), and write it in camelCase. So `hb_buffer_guess_segment_properties (buf)` is `buffer.guessSegmentProperties()`, and a position’s `x_advance` is `xAdvance`. The rule works both ways, and it is what to use to find a method in HarfBuzz’s documentation, or a HarfBuzz function in harfbuzzjs: harfbuzzjs’s own documentation doesn’t give the C names. A few names don’t follow it:

| harfbuzzjs | HarfBuzz |
|---|---|
| `addText` | `hb_buffer_add_utf16`, so clusters count UTF-16 code units |
| `glyphName` | `hb_font_glyph_to_string`, which gives `gid` and a number for a glyph without a name |
| `hExtents` | `hb_font_get_h_extents` |
| `face.upem` | `hb_face_get_upem`, as a property |
| `glyphToPath` | none: harfbuzzjs’s own, built on `hb_font_draw_glyph` |

### Glyphs in JavaScript

```example
program: quick-start/js/text-to-glyphs.mjs
args: LibreBaskerville.ttf  office coffee
output: text
same-as: hb-shape
```

It is the C program’s three steps under other names: `Blob`, `Face`, `Font`, `Buffer` and `shape`, then `getGlyphInfos` and `getGlyphPositions` for the result, and `glyphName` for each glyph’s name. JavaScript strings are UTF-16, and `addText` gives the text to HarfBuzz that way, so clusters here count UTF-16 code units: a character outside the Basic Multilingual Plane, such as an emoji, counts as two.

```
npm install harfbuzzjs
node text-to-glyphs.mjs LibreBaskerville.ttf "office coffee"
```

### SVG

```example
program: quick-start/js/text-to-svg.mjs
args: LibreBaskerville.ttf  office coffee
output: svg
```

The first half is the same. Drawing is done by hand: `glyphToPath` returns a glyph’s outline as path data in font units, with y going up, and each path is moved to its pen position. SVG’s y goes down, so the whole line is flipped with `scale(1,-1)`. The box is the line’s advance by the font’s ascender and descender.

```
node text-to-svg.mjs LibreBaskerville.ttf "office coffee" > office.svg
```

### Pixels, in a browser

In a browser, the canvas does the rasterizing: the same path data becomes a `Path2D`, and the canvas fills it. This module exports one function, `drawText`, which shapes a line and draws it on a canvas:

```example
program: quick-start/js/text-to-canvas.mjs
args: LibreBaskerville.ttf
show: source
```

A canvas can be scaled and flipped once, so the glyphs are drawn in font units with y going up, and the canvas turns them into pixels.

A web page uses the module like this:

```example
program: quick-start/js/text-to-canvas.html
args: LibreBaskerville.ttf
show: source
```

The page, `text-to-canvas.mjs` and the font go in one folder. The **import map** tells the browser where to find a module imported by a bare name: when `text-to-canvas.mjs` imports `"harfbuzzjs"`, the browser loads harfbuzzjs 1.6.4 from jsDelivr, a CDN that serves npm packages, so nothing has to be installed. To serve harfbuzzjs yourself, copy `index.mjs`, `harfbuzz.js` and `harfbuzz.wasm` from `node_modules/harfbuzzjs/dist/` into a folder named `harfbuzzjs` beside the page, and change the import map to `"./harfbuzzjs/index.mjs"`. harfbuzzjs loads `harfbuzz.wasm` from beside its own module, wherever that is.

On a high-resolution screen, the canvas should have more pixels than it takes up on the page, `devicePixelRatio` times as many, or the text comes out blurred. The page asks `drawText` for that many pixels, and then sets the canvas’s width in CSS pixels.

Browsers don’t run modules from a page opened as a file, so serve the folder with a local web server, such as Python’s:

```
python3 -m http.server
```

and open `http://localhost:8000/text-to-canvas.html`.

```demo
program: quick-start/js/text-to-canvas.mjs
font: LibreBaskerville.ttf
unicodes: 20-7E
text: office coffee
package: harfbuzzjs@1.6.4
```

<p class="print-only">The web edition of this book runs this program on the page, with a box to type text into.</p>

## In Python

[uharfbuzz](https://github.com/harfbuzz/uharfbuzz) is HarfBuzz’s Python binding, from the HarfBuzz project, and comes ready-built for the common platforms. Version 0.57.0, which these programs use, contains HarfBuzz 15.0.0, one release behind this book. Unlike harfbuzzjs, it includes hb-raster, though not hb-vector.

uharfbuzz keeps HarfBuzz’s names, in snake_case, without the `hb_` and the object’s name, and turns getters into properties (`buf.glyph_infos`, `face.upem`). Each function’s documentation links to the C function it wraps. Two names differ: `add_str` is `hb_buffer_add_utf32`, and `draw_glyph_with_pen` is `hb_font_draw_glyph` with a fontTools-style pen.

### Glyphs in Python

```example
program: quick-start/python/text-to-glyphs.py
args: LibreBaskerville.ttf  office coffee
output: text
same-as: hb-shape
```

The same steps under Python names: `Blob`, `Face`, `Font`, `Buffer` and `shape`, then `glyph_infos` and `glyph_positions` for the result, and `glyph_to_string` for each glyph’s name. `add_str` gives the text to HarfBuzz as UTF-32, so clusters here count characters, as `hb-shape`’s do.

```
pip install uharfbuzz
python text-to-glyphs.py LibreBaskerville.ttf "office coffee"
```

> For type designers: this is the program to try with a font of your own. Put the shaping and printing in a loop over the lines of a word list, and it shapes thousands of words in a second. From there a test is a short step: compare each line with what it printed for the last version of the font, and every word whose glyphs or advances have changed stands out. HarfBuzz’s own [shaping tests](testing-harfbuzz.html#the-shaping-tests) work the same way: a font, some text, and the glyphs expected.

### SVG

```example
program: quick-start/python/text-to-svg.py
args: LibreBaskerville.ttf  office coffee
output: svg
```

The first half is the same. `draw_glyph_with_pen` sends a glyph’s outline to a **pen**, an object whose `moveTo`, `lineTo`, `qCurveTo`, `curveTo` and `closePath` methods are called with each point, in font units and y up. It is the same kind of pen fontTools uses, so a fontTools pen works here too. This one collects the outline as SVG path data, and the rest is as in JavaScript.

```
python text-to-svg.py LibreBaskerville.ttf "office coffee" > office.svg
```

### PNG with hb-raster

Because uharfbuzz includes hb-raster, the PNG version can do what the C program does: give the font a size, paint each glyph with a `RasterPaint`, and render the image. hb-raster’s image comes back as raw pixels, so [Pillow](https://python-pillow.org), Python’s usual imaging library, writes the PNG:

```example
program: quick-start/python/text-to-png.py
args: LibreBaskerville.ttf  office coffee  32
output: png
```

The pixels are blue, green, red and alpha, premultiplied, with the rows from the bottom up ([hb-raster](hb-raster.html)); Pillow’s `BGRa` mode and a negative stride, the `-1`, take them as they are.

```
pip install uharfbuzz pillow
python text-to-png.py LibreBaskerville.ttf "office coffee" 32 > office.png
```

## In Rust

Rust programs usually don’t call HarfBuzz itself. They use HarfRust, a port of HarfBuzz’s shaping to Rust, which matches HarfBuzz {{hb}} but isn’t HarfBuzz: [HarfRust](harfrust.html) counts the differences. It only shapes, so the outlines come from Skrifa, part of the same Rust font libraries (Fontations). For C HarfBuzz itself, the `harfbuzz` crate has bindings, but they are less used.

HarfRust’s API is its own, modeled on HarfBuzz’s but not a binding to it, so its names don’t map one to one. The difference most worth knowing: C’s `codepoint` field, which holds a glyph ID after shaping, is `glyph_id` in HarfRust.

The project’s `Cargo.toml` asks for `harfrust = "0.16.0"`, which is all the first program needs, and for the drawing programs `skrifa = "0.50.0"`, and `tiny-skia` for the PNG version.

### Glyphs with HarfRust

```example
program: quick-start/rust/src/text-to-glyphs.rs
args: LibreBaskerville.ttf  office coffee
output: text
same-as: hb-shape
```

The same steps again, with one fewer name: HarfRust’s `Font` reads the file’s bytes itself, with no blob or face, and a `ShaperFont` is what shapes with it. HarfRust has no font size at all: it always shapes in font units, and a program scales the result. `glyph_name` gives a glyph’s name if the font has one. `push_str` sets each cluster to its character’s byte offset in the UTF-8 string, so clusters count bytes, as the C program’s do. Here the build’s check says something more than in the other languages: a different shaper has produced the same glyphs, clusters and advances as HarfBuzz.

```
cargo run --release --bin text-to-glyphs -- LibreBaskerville.ttf "office coffee"
```

### SVG with HarfRust and Skrifa

```example
program: quick-start/rust/src/text-to-svg.rs
args: LibreBaskerville.ttf  office coffee
output: svg
```

The first half is the same. Skrifa’s `SvgPen` collects one glyph’s outline as path data, and the program writes the rest of the SVG as the JavaScript did.

```
cargo run --release --bin text-to-svg -- LibreBaskerville.ttf "office coffee" > office.svg
```

### PNG with tiny-skia

For pixels, Skrifa draws each outline at the size wanted, and [tiny-skia](https://github.com/linebender/tiny-skia), a small rasterizer, fills it:

```example
program: quick-start/rust/src/text-to-png.rs
args: LibreBaskerville.ttf  office coffee  32
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
* **Color fonts.** The C and Python PNG programs paint them already, since they paint with hb-raster. The SVG programs would need hb-vector’s paint context in C, or a color library in the other languages ([Color](color.html)).
* **Checking the font.** HarfBuzz doesn’t fail on a file that isn’t a font ([Before shipping](for-applications.html#before-shipping) says what happens, and what to check).

For a real program, two places take over from here. HarfBuzz’s [user manual](https://harfbuzz.github.io/) explains how to do each of the things above. [Before shipping](for-applications.html#before-shipping), at the end of For applications, lists the same steps with links to both the manual and this book, and the traps that a program built on these examples can still fall into.

## Documentation

Each library’s own reference is where to go next:

| Language | Library | Reference |
|---|---|---|
| C | HarfBuzz | the [API reference](https://harfbuzz.github.io/reference-manual.html), including [buffers](https://harfbuzz.github.io/harfbuzz-hb-buffer.html), [hb-vector](https://harfbuzz.github.io/harfbuzz-hb-vector.html) and [hb-raster](https://harfbuzz.github.io/harfbuzz-hb-raster.html) |
| JavaScript | harfbuzzjs | its [README](https://github.com/harfbuzz/harfbuzzjs#readme), and the type declarations in `dist/index.d.mts` |
| Python | uharfbuzz, Pillow | [uharfbuzz’s documentation](https://uharfbuzz.readthedocs.io/), and [Pillow’s](https://pillow.readthedocs.io/en/stable/) |
| Rust | HarfRust, Skrifa, tiny-skia | [HarfRust](https://docs.rs/harfrust/0.16.0/harfrust/), [Skrifa](https://docs.rs/skrifa/0.50.0/skrifa/) and [tiny-skia](https://docs.rs/tiny-skia/0.11.4/tiny_skia/) on docs.rs |

## Where to read the source

| File | What it shows |
|---|---|
| [`examples/quick-start/`](https://github.com/Lorp/how-harfbuzz-works/tree/main/examples/quick-start) (in the book’s repository) | the programs on this page, with the JavaScript `package.json`, the Python `requirements.txt` and the Rust `Cargo.toml` |
| `util/hb-shape.cc`, `util/shape-format.hh` | how `hb-shape` prints: the C glyphs program, with options |
| `util/vector-output.hh` | how `hb-vector` draws: the C SVG program, with options |
| `util/raster-output.hh` | how `hb-raster` draws, including its image sizes and margins |
| `src/hb-vector.h`, `src/hb-raster.h` | the drawing libraries’ API |
| `docs/usermanual-getting-started.xml` | HarfBuzz’s own first program, which shapes and prints the glyphs |

## In short

* Every program does the same three things first: load the font (blob, face, font), shape the text in a buffer, and read the glyphs, with their clusters, advances and offsets.
* The smallest program stops there and prints them, as `hb-shape` does. It needs only HarfBuzz itself, in any recent version.
* Clusters count in the units the text was given in: bytes in C and Rust, UTF-16 code units in JavaScript, characters in Python.
* A drawing program walks the glyphs, adding up advances and offsets, and draws each at its pen position.
* In C, hb-vector draws the glyphs as SVG and hb-raster as pixels.
* In JavaScript, harfbuzzjs shapes, and gives outlines as SVG path data, for an SVG file or a canvas.
* In Python, uharfbuzz shapes, draws outlines through a pen, and paints with hb-raster; Pillow writes the PNG.
* In Rust, HarfRust shapes, Skrifa gives the outlines, and a rasterizer such as tiny-skia makes pixels. HarfRust is a port, not HarfBuzz.
* Real programs also set script, language and direction, split mixed text into runs, choose fallback fonts and break lines.
