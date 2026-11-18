# Preface

In 2007 Yannis Haralambous’ *Fonts & Encodings* gave a generation of type designers and programmers one place to learn how characters become glyphs. Much of its 1,000 pages has aged well, but its picture of shaping hasn’t. Uniscribe and ATSUI have given way to one open-source engine, HarfBuzz, which now shapes text for almost everything.

Simon Cozens’ [*Fonts and Layout for Global Scripts*](https://simoncozens.github.io/fonts-and-layout/) is the closest book since, written 2016–2021 and published on GitHub. It teaches the font maker’s side: how to write OpenType features for the world’s scripts, and check them with HarfBuzz. It was to go on to the programs that use fonts, with a chapter on HarfBuzz, but that half was never written. This book is about that side.

HarfBuzz is well documented as a library to call. This book is about what happens inside it. It follows a buffer of characters through HarfBuzz, from the moment text arrives to the moment positioned glyphs leave, and explains each step from the code that does it.

It’s for two kinds of reader:

* **Type designers and font engineers** who want to know why their font shapes the way it does, and what HarfBuzz will do with the tables they write.
* **Programmers** who use HarfBuzz, port it, or want to work on it, and need a map of its source.

## How the book is made

Every claim is meant to be checked against the code. The book names the HarfBuzz version it describes, and quotes the source by file and line at that version. Each chapter has small test fonts, built from feature files in the book’s repository, and every shaping result and trace in a chapter is made by running HarfBuzz on those fonts when the book is built. If HarfBuzz changes, rebuilding the book shows what has changed.

The code is the main source, but not the only one. Reading it shows what HarfBuzz does, not whether that is what the standard says, or what other engines do. For those, the book goes to the [OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/) and its registries, the 2026 ISO standard, Microsoft’s script development specifications, Apple’s TrueType Reference Manual, and HarfBuzz’s own history: its `NEWS`, its manual, and the issues and pull requests where decisions were argued. The [bibliography](bibliography.html) lists them. Where HarfBuzz goes beyond the specification, with an experiment, a tag no registry lists, or a behavior of its own, the book means to say so.

The book was drafted by Claude, an AI model made by Anthropic, working with Laurence Penney, who planned it, directed its revisions and checked it. HarfBuzz’s author, Behdad Esfahbod, has read it in draft, suggested chapters, and fixed many of the bugs that writing it turned up ([Testing HarfBuzz](testing-harfbuzz.html#the-bugs-this-book-found)). Mistakes that remain are the book’s. If you find one, whether a false claim, a misleading or unclear phrase, or something the code can’t tell you and the book should, please [open an issue](https://github.com/Lorp/how-harfbuzz-works/issues) in its repository.
