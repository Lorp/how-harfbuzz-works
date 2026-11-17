# Reading this book

## The views of a table

Font data can be shown in several ways, and different readers know different ones. <span class="screen-only">Wherever this book shows a lookup, it starts in the spec-like view, and its tabs switch it to the others. Each lookup’s tabs change only that lookup.</span><span class="print-only">In print, a lookup is shown in the spec-like view, and where the text discusses other views, in those too, each labelled. The web edition has all five for every lookup.</span>

* **Spec-like**: the book’s own notation, and the default. It uses the field names of HarfBuzz’s structs, which follow the OpenType specification, and leaves out what only the bytes need (counts, offsets). Lists of glyphs are in square brackets. In a ligature, the first glyph is in round brackets, because it isn’t stored in the ligature itself.
* **Feature file**: the AFDKO feature-file source the test font was compiled from, by fontTools’ feaLib.
* **TTX**: fontTools’ XML dump of the compiled table.
* **Bytes**: the table as it is in the font, field by field. Offsets are counted from the start of the table (GSUB, for example).
* **HarfBuzz C++**: the struct HarfBuzz lays over those bytes, linked to the source.

A view that doesn’t exist for a particular table (bytes, say, for a kind of subtable the book doesn’t decode) falls back to the spec-like view.

None of the views is written by hand. Each is made from the compiled font, or from the HarfBuzz source, when the book is built.

## Shaping results

Results are shown as `hb-shape` prints them:

```
[f_i=0+900|acutecomb=0@-675,562+0]
```

Each glyph is `name=cluster`, then `@x,y` if it is offset, then `+advance`. Glyphs are listed in visual order. Text that is hard to see is spelt out: `◌́` is a combining mark on a dotted circle, `⟨ZWJ⟩` and `⟨ZWNJ⟩` are the joiners, and `␣` is a space. The Unicode code points are listed under each piece of text.

## Traces

A trace is HarfBuzz’s own account of what it did, from `hb-shape --trace`: each step’s name, and the buffer after it. Traces in this book come from a HarfBuzz built with `HB_BUFFER_MESSAGE_MORE`, which adds detail inside lookups (“ligating glyphs at 0,2”).

## Drawings

Some figures draw glyphs, with `hb-vector`, and show `hb-shape`’s result beneath each drawing. A drawing of a variable font shows it at more than one position in its design space. <span class="screen-only">Its slider moves along one axis, and every position it can show was drawn when the book was built.</span><span class="print-only">In print, a row of frames shows a few positions along one axis, each labelled with its value; the web edition has a slider, with every position drawn.</span>
