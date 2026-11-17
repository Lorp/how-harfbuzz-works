# How HarfBuzz Works

*From Unicode to positioned glyphs, and everything in between*

Read it [online](https://lorp.github.io/how-harfbuzz-works/) or as a [PDF](https://lorp.github.io/how-harfbuzz-works/print/how-harfbuzz-works.pdf).

A book about the inside of [HarfBuzz](https://github.com/harfbuzz/harfbuzz), written from its source code (version 15.1.0), for type designers, font engineers and programmers.

Every shaping result and trace in the book is made by running HarfBuzz on small test fonts when the book is built, and every view of a font table is made from the compiled font, so the text can’t drift from what HarfBuzz actually does.

## Layout

* `book/toc.txt`: the order of the book
* `book/front/`, `book/chapters/`, `book/end/`: one Markdown file per page
* `book/book.json`: title, subtitle, and the HarfBuzz version described
* `fonts/<page>/`: each chapter’s feature files, the fonts built from them, and `build.sh`
* `tools/`: building HarfBuzz (`build-harfbuzz.sh`), the site (`build-site.mjs`, Node), and the test fonts and their views (`build-test-font.py`, `font-views.py`, Python)
* `notes/`: research towards the book, such as the survey of the source

## Building

The site is built with Node. Only the test fonts need Python.

```sh
tools/build-harfbuzz.sh   # HarfBuzz 15.1.0 into .cache/harfbuzz (twice: plain, and with detailed traces)
npm install               # once
npm run build             # the book as HTML, into site/
```

`tools/build-harfbuzz.sh` needs `meson`, `ninja` and a C++ compiler (`brew install meson ninja` on a Mac).

The test fonts are committed, so Python is only needed when a feature file changes. Then run the chapter’s `build.sh`, which needs Python 3 with `fonttools`:

```sh
fonts/gsub/build.sh       # a chapter's test fonts, and their FONT.views.json
```

Each `FONT.views.json` holds the views made from the compiled font: spec-like, TTX and bytes. It’s committed beside the font, and the site build stops with a message if a font has changed since its views were written.

## Writing a chapter

Beside ordinary Markdown, a chapter can use three kinds of fenced block, run against its fonts when the book is built: `views` (the switchable views of a lookup), `shape` (hb-shape runs) and `trace` (hb-shape --trace, cut down). See the top of `tools/build-site.mjs`.
