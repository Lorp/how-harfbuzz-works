# Introduction

Type the word “office” in a good serif font and you get four glyphs, not six: the *f*, *f* and *i* have become one ligature. Type an Arabic word and each letter takes a different shape depending on whether it joins the letters on either side. In Devanagari, a vowel sign that is typed after a consonant is drawn before it. None of this is in the text. The text is a sequence of Unicode characters, and Unicode deliberately says nothing about how they look. Turning characters into the right glyphs, in the right order and in the right places, is **shaping**, and HarfBuzz is the program that does it for most of the world’s software.

## What HarfBuzz is given, and what it gives back

HarfBuzz’s job is narrower than it looks from the outside. It is handed a **run** of text: some characters that all use one font, one script, one direction and one language. Deciding where those runs begin and end is someone else’s job. So is the bidirectional algorithm that decides the order of right-to-left and left-to-right runs on a line, and the line breaking that decides where lines end. HarfBuzz shapes one run and hands back a list of glyphs. For each glyph it gives:

* its **glyph ID** in the font;
* its **cluster**: which characters of the input it came from;
* its **advance**, how far to move before drawing the next glyph, and an **offset** from where it would otherwise be drawn;
* a few **flags**, saying for example where the run could safely be cut and reshaped in parts.

Everything in this book happens between those two points: a buffer of characters going in, a buffer of positioned glyphs coming out.

## How a run is shaped

The work is split into the parts this book follows, after a first part for getting started. [Part I](why-shaping-exists.html) says why shaping exists at all, then how to build HarfBuzz and how to use the command-line tools that come with it, which every later chapter uses to show what HarfBuzz does.

The font comes first. Before it can shape anything, HarfBuzz has to read the font, which is a file of binary tables, and it has to do so safely, since fonts come from anywhere. [Part II](fonts-as-bytes.html) covers how HarfBuzz lays its data structures over the bytes of a font without copying them, how the sanitizer makes that safe, and where a glyph’s metrics come from.

Then the text. [Part III](unicode-inside-harfbuzz.html) is about the buffer: what HarfBuzz knows about each character, the cluster levels that decide how characters and glyphs are grouped, and how `hb_shape` chooses which shaper runs.

Then a plan. Shaping the same kind of text with the same font is common, so HarfBuzz works out once which features apply, which lookups they use and in what order, and keeps the result as a **shape plan**. [Part IV](shape-plans-and-their-cache.html) covers planning, including how the script shaper is chosen.

Then the pipeline itself, in [Part V](the-pipeline-step-by-step.html). Characters are normalized and mapped to glyphs. GSUB substitutes glyphs, GPOS positions them, and fallbacks step in where the font has no tables for something. Each of those steps has its own chapter.

Some scripts need more than the font’s tables can say on their own: Arabic letters have to know which of their neighbors they join, and Indic syllables have to be found and reordered before any lookup sees them. [Part VI](joining-scripts.html) covers the script shapers. [Part VII](aat-inside-harfbuzz.html) covers Apple’s own layout tables, which HarfBuzz runs in place of GSUB and GPOS when a font has them.

[Part VIII](design-space.html) is about variable fonts, which affect nearly every step above. [Part IX](drawing-outlines.html) is about drawing: HarfBuzz can now produce outlines and images of glyphs as well as positions, with three renderers of its own. [Part X](subsetting.html) covers HarfBuzz’s other library, which writes fonts instead of reading them: subsetting a font down to the glyphs a document needs, and instancing a variable font. [Part XI](for-applications.html) is about using HarfBuzz in an application: what to do with its output, how it plugs into FreeType, cairo, ICU and the platforms’ own text libraries, and the tables it reads for applications rather than for shaping. [Part XII](testing-harfbuzz.html) is about HarfBuzz and its relatives: how it is tested, HarfRust, its Rust port, and the other software built on it.

## How to read this book

The chapters are meant to be read in order, but each stands on its own well enough to be read on its own, with links back to what it depends on. A type designer who wants to know why a ligature didn’t form can start at the GSUB chapter. A programmer who wants a map of the source might start with Part II. Anyone who wants to run the examples should start with Part I.

Every chapter that shows a font table uses small test fonts, built from feature files in the book’s repository, and every shaping result and trace in it is produced by running HarfBuzz {{hb}} on those fonts when the book is built. When the book says HarfBuzz does something, the output on the page is HarfBuzz doing it. [Notation](notation.html) explains how tables, shaping results and traces are shown.
