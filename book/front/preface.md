# Preface

In 2007 Yannis Haralambous’s *Fonts & Encodings* gave a generation of type designers and programmers one place to learn how characters become glyphs. Much of it has aged well, but its picture of shaping hasn’t. Uniscribe and ATSUI have given way to one open-source engine, HarfBuzz, which now shapes text for almost everything.

HarfBuzz is well documented as a library to call. This book is about what happens inside it. It follows a buffer of characters through HarfBuzz, from the moment text arrives to the moment positioned glyphs leave, and explains each step from the code that does it.

It’s for two kinds of reader:

* **Type designers and font engineers** who want to know why their font shapes the way it does, and what HarfBuzz will do with the tables they write.
* **Programmers** who use HarfBuzz, port it, or want to work on it, and need a map of its source.

## How the book is made

Every claim is meant to be checked against the code. The book names the HarfBuzz version it describes, and quotes the source by file and line at that version. Each chapter has small test fonts, built from feature files in the book’s repository, and every shaping result and trace in a chapter is made by running HarfBuzz on those fonts when the book is built. If HarfBuzz changes, rebuilding the book shows what has changed.
