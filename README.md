# How HarfBuzz Works

*From Unicode to positioned glyphs, and everything in between*

A book about the inside of [HarfBuzz](https://github.com/harfbuzz/harfbuzz), written from its source code (version 15.1.0), for type designers, font engineers and programmers.

Every shaping result and trace in the book is made by running HarfBuzz on small test fonts when the book is built, and every view of a font table is made from the compiled font, so the text can't drift from what HarfBuzz actually does.

## Layout

* `book/toc.txt`: the order of the book
* `book/front/`, `book/chapters/`, `book/end/`: one Markdown file per page
* `book/book.json`: title, subtitle, and the HarfBuzz version described
* `fonts/<page>/`: each chapter's feature files, the fonts built from them, and `build.sh`
* `tools/`: building HarfBuzz, the test fonts, the views and the site
* `notes/`: research towards the book, such as the survey of the source

## Building

Needs Python 3 with `fonttools` and `markdown`, plus `meson`, `ninja` and a C++ compiler for HarfBuzz.

```sh
tools/build-harfbuzz.sh        # HarfBuzz 15.1.0 into .cache/harfbuzz (twice: plain, and with detailed traces)
fonts/gsub/build.sh            # a chapter's test fonts
python3 tools/build-site.py    # the book as HTML, into site/
```

## Writing a chapter

Beside ordinary Markdown, a chapter can use three kinds of fenced block, run against its fonts when the book is built: `views` (the switchable views of a lookup), `shape` (hb-shape runs) and `trace` (hb-shape --trace, cut down). See the top of `tools/build-site.py`.
