# AGENTS.md

We are creating a book about HarfBuzz, the text shaping engine used by Chrome, Firefox, Android, GNOME, LibreOffice and most other software that puts text on a screen. It explains how HarfBuzz transforms Unicode text into positioned glyphs, from the moment text arrives to the moment it leaves the library.

## Writing for the book

Before writing or editing anything in `book/`, read `notes/writing-brief.md`: it is the book’s style guide and method, for a one-word fix as much as for a new chapter. The rules easiest to break in a quick edit:

* Typographic quotes and apostrophes (“ ” ‘ ’) in prose; straight ones only in code.
* American spelling: color, behavior, center.
* Plain headings that say what the section is about; no wordplay.
* Bold only where a term is defined, since the index and glossary are made from bold terms.
* `{{hb}}` for the HarfBuzz version the book describes.
* As long as the subject needs: no padding, and no length limit.
* Anything shown as HarfBuzz’s output is a live block, made when the book is built (`README.md` explains the blocks).

`notes/outline.md` has the plan of the book, and `notes/upstream-bug-reports.md` the bugs it has found.

## Resources that can help us

* [OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/)
* [fontTools documentation](https://fonttools.readthedocs.io/en/latest/index.html)
* [fontc documentation](https://deepwiki.com/googlefonts/fontc)
* ISO Open Font Format specification
* This book as a PDF, with its page-numbering file, in `resources/how-harfbuzz-works/` (a snapshot, so it may lag behind the Markdown)
* [The Raster Tragedy at Low-Resolution Revisited](http://rastertragedy.com) — Beat Stamm on rasterizing and hinting (© all rights reserved, don’t quote at length)
* [Fonts and Layout for Global Scripts](https://simoncozens.github.io/fonts-and-layout/) — Simon Cozens on fonts, OpenType and feature programming from the font maker’s side; a copy is in `resources/fonts-and-layout/`. A second opinion on what the book tells font makers. CC BY-SA 4.0: cite and quote briefly with credit, but don’t adapt its text, or ShareAlike applies. Written 2016–2021, and its chapters on HarfBuzz, FreeType and Raqm are empty. `notes/fonts-and-layout.md` lists where it differs from HarfBuzz today
* [OpenType registries](https://learn.microsoft.com/en-us/typography/opentype/spec/ttoreg) — script, language system, feature, baseline and axis tags. What is registered, as against what HarfBuzz accepts; their tags are in `tools/registries.json`, checked by `tools/check-tags.mjs`
* [Microsoft’s script development specifications](https://learn.microsoft.com/en-us/typography/script-development/standard) — how Windows (Uniscribe, DirectWrite) shapes each complex script. What HarfBuzz is compatible with, and where it differs
* [Apple’s TrueType Reference Manual](https://developer.apple.com/fonts/TrueType-Reference-Manual/) — AAT tables and Apple’s tags
* [HarfBuzz issues, discussions and pull requests](https://github.com/harfbuzz/harfbuzz/issues) — where decisions were argued and made: why a behavior exists, whether it is experimental, what other engines do. `gh` can search them
* [Microsoft typography issues](https://github.com/MicrosoftDocs/typography-issues/issues) — known problems and proposals in the OpenType specification

## Beyond the code

The code is the book’s main source, but it can’t say what is standard. HarfBuzz supports experiments, private extensions and other engines’ behaviors alongside the specification, and from the code they look the same. Treat the resources above as sources to check, not background reading: wherever the book describes a tag, table, feature or behavior, say whether it is standard, ISO-only, Apple’s or HarfBuzz’s own, and, where it matters to a font maker, what DirectWrite and Core Text do, with a source. `notes/writing-brief.md` has the details.
