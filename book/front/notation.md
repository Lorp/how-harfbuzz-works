# Reading this book

## The views of a table

Font data can be shown in several ways, and different readers know different ones. <span class="screen-only">Wherever this book shows a lookup, it starts in the spec-like view, and its tabs switch it to the others. Each lookup’s tabs change only that lookup.</span><span class="print-only">In print, a lookup is shown in the spec-like view, and where the text discusses other views, in those too, each labeled. The web edition has all five for every lookup.</span>

* **Spec-like**: the book’s own notation, and the default. It uses the field names of HarfBuzz’s structs, which follow the OpenType specification, and leaves out what only the bytes need (counts, offsets). Lists of glyphs are in square brackets. In a ligature, the first glyph is in round brackets, because it isn’t stored in the ligature itself.
* **Feature file**: the feature-file source the lookup was compiled from, by fontTools’ feaLib. [Reading feature files](reading-feature-files.html) explains enough of the language to follow it.
* **TTX**: fontTools’ XML dump of the compiled table.
* **Bytes**: the table as it is in the font, field by field. Offsets are counted from the start of the table (GSUB, for example).
* **HarfBuzz C++**: the struct HarfBuzz lays over those bytes, linked to the source.

A view that doesn’t exist for a particular table (bytes, say, for a kind of subtable the book doesn’t decode) falls back to the spec-like view.

None of the views is written by hand. Each is made from the compiled font, or from the HarfBuzz source, when the book is built.

## Shaping results

Results are shown as `hb-shape` prints them ([The command-line tools](command-line-tools.html#reading-the-output) explains all its switches):

```
[f_i=0+900|acutecomb=0@-675,562+0]
```

Each glyph is `name=cluster`, then `@x,y` if it is offset, then `+advance`. Glyphs are listed in visual order. Text that is hard to see is spelled out: `◌́` is a combining mark on a dotted circle, `⟨ZWJ⟩` and `⟨ZWNJ⟩` are the joiners, and `␣` is a space. The Unicode code points are listed under each piece of text.

## Traces

A trace is HarfBuzz’s own account of what it did, from `hb-shape --trace`: each step’s name, and the buffer after it. Traces in this book come from a HarfBuzz built with `HB_BUFFER_MESSAGE_MORE`, which adds detail inside lookups (“ligating glyphs at 0,2”); [Building HarfBuzz](building-harfbuzz.html#a-second-build-for-traces) shows how, and [The command-line tools](command-line-tools.html#traces) how to ask for a trace.

## Drawings

Some figures draw glyphs, with `hb-vector`, and show `hb-shape`’s result beneath each drawing. A drawing of a variable font shows it at more than one position in its design space. <span class="screen-only">Its slider moves along one axis, and every position it can show was drawn when the book was built.</span><span class="print-only">In print, a row of frames shows a few positions along one axis, each labeled with its value; the web edition has a slider, with every position drawn.</span>

## Links and source references

References to HarfBuzz’s source give a file and a line, such as `hb-ot-map.cc:389`, and always mean HarfBuzz {{hb}}: the line can be found in its repository at github.com/harfbuzz/harfbuzz, under the tag {{hb}}.<span class="screen-only"> Each one links to that line.</span><span class="print-only"> On screen, each one links to that line.</span>

<span class="screen-only">Links to other chapters, and out of the book, work as on any web page.</span><span class="print-only">Links to other parts of the book are in color, followed by the page they lead to, such as “(p. 121)”. Links out of the book are in color with a small note number, and their addresses are listed, by number, at the end of the chapter, under “Links”.</span>
