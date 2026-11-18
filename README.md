# How HarfBuzz Works

*From Unicode to positioned glyphs, and everything in between*

Read it [online](https://lorp.github.io/how-harfbuzz-works/) or as a [PDF](https://lorp.github.io/how-harfbuzz-works/print/how-harfbuzz-works.pdf).

A book about the inside of [HarfBuzz](https://github.com/harfbuzz/harfbuzz), written from its source code (version 15.1.0), checked against the OpenType specification and other sources, for type designers, font engineers and programmers.

“I skimmed a few chapters. Genuinely useful to aspiring HarfBuzz developers.”  
— *Behdad Esfahbod*

Every shaping result and trace in the book is made by running HarfBuzz on small test fonts when the book is built, and every view of a font table is made from the compiled font, so the text can’t drift from what HarfBuzz actually does.

## Layout

* `book/toc.txt`: the order of the book
* `book/front/`, `book/chapters/`, `book/end/`: one Markdown file per page
* `book/book.json`: title, subtitle, and the HarfBuzz version described
* `book/cover.png`, `book/cover-back.png`: the front and back covers, for the PDF
* `fonts/<page>/`: each chapter’s feature files, the fonts built from them, and `build.sh`
* `examples/`: whole example programs, in C, JavaScript, Python and Rust, which the build compiles and runs (needs a C compiler, npm, Python 3 and cargo)
* `tools/`: building HarfBuzz (`build-harfbuzz.sh`), the site (`build-site.mjs`, Node), and the test fonts and their views (`build-test-font.py`, `font-views.py`, Python)
* `notes/`: research toward the book, such as the survey of the source

## Building

The site is built with Node. Only the test fonts need Python.

```sh
tools/build-harfbuzz.sh   # HarfBuzz 15.1.0 into .cache/harfbuzz (twice: plain, and with detailed traces)
npm install               # once
npm run build             # the book as HTML, into site/
npm run pdf               # the book as a PDF, with its .pages.txt, into site/print/ (needs Chrome)
```

## Publishing

```sh
npm run pdf               # first, if the PDF should be updated too
npm run publish           # builds the site afresh and pushes it, with site/print/'s PDF, to gh-pages
```

GitHub Pages serves the `gh-pages` branch at <https://lorp.github.io/how-harfbuzz-works/>. The branch is replaced on each publish by a single commit, so it never grows; `main` holds only the source. `npm run publish` warns if `book/`, `fonts/` or `tools/` have changed since the PDF was made.

`tools/build-harfbuzz.sh` needs `meson`, `ninja` and a C++ compiler (`brew install meson ninja` on a Mac).

The test fonts are committed, so Python is only needed when a feature file changes. Then run the chapter’s `build.sh`, which needs Python 3 with `fonttools`:

```sh
fonts/gsub/build.sh       # a chapter's test fonts, and their FONT.views.json
```

Each `FONT.views.json` holds the views made from the compiled font: spec-like, TTX and bytes. It’s committed beside the font, and the site build stops with a message if a font has changed since its views were written.

## Writing a chapter

A chapter is ordinary Markdown, in `book/chapters/`. What makes this book different is that its examples aren’t typed in by hand: you describe what you want to show, and the build runs HarfBuzz to produce it. If HarfBuzz’s behavior changes, the book changes with it.

Each chapter has its own small test fonts in `fonts/<chapter>/`, named after the chapter’s file (so `gsub.md` uses `fonts/gsub/`). The kinds of code block below use them.

### Show what HarfBuzz does: `shape`

Write one font and one piece of text per line, and the build puts HarfBuzz’s output in the page:

````markdown
```shape
ligatures.ttf  ffi
ligatures.ttf  ffi  --features=-liga
```
````

Put **two or more spaces** between the font, the text and any `hb-shape` options. Text can include `\u0301` or `\u{1F600}` for characters that are hard to type.

### Show how it got there: `trace`

This shows HarfBuzz’s own step-by-step log (`hb-shape --trace`) for one run, cut down to the part you’re talking about:

````markdown
```trace
font: ligatures.ttf
text: ffi
from: start lookup 0
to: end lookup 0
```
````

`from` and `to` are bits of text from the log’s lines. The extract starts at the first line containing `from` and ends at the first line after it containing `to`. Lookups that were skipped are left out; add `skipped: yes` to keep them. Add `options:` for any other `hb-shape` options, such as `options: --script=arab`.

### Show what’s in the font: `views`

This shows one lookup from the compiled font, with tabs to switch between a spec-like table, TTX, and the raw bytes:

````markdown
```views
font: ligatures.ttf
lookup: 0
fea: ligatures.fea liga
cpp: LigatureSubstFormat1_2
```
````

`fea` names the feature file and the block in it the lookup came from, and `cpp` names the HarfBuzz struct that reads it. In the PDF only one view can be shown; add `print: spec fea` (for example) to choose which. The default is the spec-like table.

These views come from a `FONT.views.json` file next to each font, which the chapter’s `build.sh` writes. So after changing a feature file, rebuild that chapter’s fonts (see above); the site build stops and tells you if you forget.

### Show a command and what it gives: `command`

This shows one command line exactly as a reader would type it, runs it when the book is built, and shows what it produces under it: `hb-shape`’s output as text, or the SVG or PNG the command writes, captioned with the file’s name.

````markdown
```command
font: quick-start/LibreBaskerville.ttf
$ hb-raster LibreBaskerville.ttf "office coffee" --font-size=32 -o office.png
```
````

`font:` says where the font named in the command really is (found as in the other blocks); a path starting `test/` is a font in HarfBuzz’s own source. `zoom:` enlarges a PNG (default 2), and `show: no` shows the command without running it. The tools it can run are `hb-shape`, `hb-vector`, `hb-raster` and `hb-info`.

### Show a whole program: `example`

This shows a program from `examples/`, and what it outputs. The build compiles and runs it (C against the HarfBuzz in `.cache/harfbuzz`, JavaScript with npm, Python in a virtual environment from its `requirements.txt`, Rust with cargo, all built in `.cache/examples/`), so the listing and the picture can’t disagree:

````markdown
```example
program: quick-start/c/text-to-svg.c
args: LibreBaskerville.ttf  office coffee
output: svg
```
````

`args` are the program’s arguments, with two or more spaces between them; the first is a font, found as in the other blocks (`hb:` means HarfBuzz’s own source tree). `output` is `svg` or `png`. Add `show: source` for the listing alone, or `show: output` for the picture alone. Outputs are kept in `.cache/examples/out/` and rerun only when the program, its `package.json` or `Cargo.toml`, or the arguments change.

### Let the reader try it: `demo`

This runs a JavaScript module from `examples/` in the reader’s browser, with a box to type text into. The module exports `drawText(canvas, fontData, text, pixels)`; the font is cut down with `hb-subset` and carried in the page, and the package comes from jsDelivr. Demos appear on screen only, so the text around one should still make sense in print.

````markdown
```demo
program: quick-start/js/text-to-canvas.mjs
font: LibreBaskerville.ttf
unicodes: 20-7E
text: office coffee
package: harfbuzzjs@1.6.4
```
````

The other blocks, `raster`, `draw`, `info` and `table`, are described with the rest at the top of `tools/build-site.mjs`.

`tools/build-site.mjs` has the full details at the top.
