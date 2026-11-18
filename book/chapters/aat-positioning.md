# AAT positioning

Apple’s fonts position glyphs with tables of their own. `kerx`, the extended kerning table, does what Apple’s `kern` did and more: pairs, classes, state machines, and attaching one glyph to a point on another, with `ankr` holding the points. `trak` adds space between letters, or takes it away, by an amount that depends on the point size. HarfBuzz reads all three, in the same step of the pipeline as GPOS ([The pipeline, step by step](pipeline-step-by-step.html), step 17).

`kerx` is mostly `kern` with wider fields, and HarfBuzz runs both with the same code. [Legacy kern](legacy-kern.html) explains that code: the subtable loop, the kern machine that applies a pair, the coverage bits, cross-stream kerning. This chapter says what is different for `kerx`, then covers what only `kerx` has, when the plan uses it, and `trak`. The state-machine driver that `kerx` formats 1 and 4 run on is in [AAT inside HarfBuzz](aat-inside-harfbuzz.html).

The examples use fonts built by `fonts/aat-positioning/build-fonts.py`. All are derived from the box-glyph font of [Legacy kern](legacy-kern.html), `kern.ttf`, with its `kern` table taken out and other tables put in; in those with marks, the combining acute is a small box above the line, hanging to the left of its origin. A few fonts come from HarfBuzz’s own tests. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on them when the page was built.

## What kerx changes

The **`kerx`** table, Apple’s extended kerning table, has the layout of Apple’s version 1.0 `kern` with every count, length and offset widened to 32 bits. The header is a 16-bit version (2, 3 or 4), 16 bits of padding and a 32-bit count of subtables. Each subtable starts with a 12-byte header: a 32-bit length, 32 bits of coverage, whose low byte is the format, and a 32-bit `tupleCount`. HarfBuzz’s struct is `kerx` (`hb-aat-layout-kerx-table.hh:1238`), another `KerxTable` beside the two `kern` versions, with `KerxSubTableHeader` (`:884`) as its header and the 32-bit `ExtendedTypes` for its fields. A version below 2 fails the sanitizer and the table is ignored (`minVersion`, `:1243`). Version 3 adds an array after the subtables saying which glyphs each subtable covers; HarfBuzz sanitizes it (`:1179`) and doesn’t use it.

`kerx.ttf` has one format 0 subtable with `kern.ttf`’s five pairs. `fontTools` doesn’t decode `kerx`, so this listing, and the others on this page, are made from the font’s bytes by `fonts/aat-positioning/views.py`:

```table
font: kerx.ttf
table: kerx
```

A pair is applied by the same kern machine as in `kern`, so the value is split between the two glyphs’ advances, marks are passed over, and pairs are read left to right, which in Hebrew is the reverse of the logical order ([How the kerning is applied](legacy-kern.html#how-the-kerning-is-applied)). The difference is which scripts get it. The plan doesn’t ask the script shaper before using `kerx`, as it does for `kern` ([When the plan uses kern](legacy-kern.html#when-the-plan-uses-kern)), so Thai and Devanagari are kerned too:

```shape
kerx.ttf  AVTo  --language=en
kerx.ttf  กก  --language=th
kerx.ttf  कक  --language=hi
kerx.ttf  גב  --language=he
kerx.ttf  AVTo  --language=en  --features=-kern
```

Turning off `kern` turns off pair kerning, as with the `kern` table: formats 0, 2 and 6 check `requested_kerning` and the glyphs’ `kern` mask (`:109`).

### Coverage

The coverage bits are those of Apple’s `kern` with one more, moved to the top of a 32-bit field (`:891`):

| Bit | Meaning | What HarfBuzz does |
|---|---|---|
| `Vertical` (0x80000000) | the subtable is for vertical text | runs it only in vertical text, and the other subtables only in horizontal (`:1078`) |
| `CrossStream` (0x40000000) | values move glyphs across the line | as in `kern`; see [Cross-stream](#cross-stream) |
| `Variation` (0x20000000) | values vary | runs the subtable, unlike in `kern`, which skips it (`:1075`); see [Tuples](#tuples) |
| `Backwards` (0x10000000) | process the glyphs from last to first | formats 1 and 4: the buffer is reversed before the subtable; formats 0, 2 and 6: the subtable is skipped (`:112`) |

In horizontal text the buffer is put in left-to-right order before a subtable runs, reversing a right-to-left buffer, and `Backwards` reverses that once more: in right-to-left text, a subtable with `Backwards` set sees the glyphs in logical order (`:1091`). HarfBuzz’s comment on the bit says it “only applies to state-table based ‘kerx’ subtables (types 1 and 4)” (`:896`), and its pair formats return without kerning when it is set. `backwards.ttf` is `kerx.ttf` with the bit set:

```shape
backwards.ttf  AVTo  --language=en
```

As in `kern`, the vertical formats 0, 2 and 6 can only kern when `vkrn` is asked for, since the kerning mask in vertical text is `vkrn`’s, and it isn’t on by default ([Vertical subtables](legacy-kern.html#vertical-subtables); read from the code).

### Tuples

With a non-zero `tupleCount`, every kerning value in the subtable is instead the offset of an array of `tupleCount` values, which Apple meant for kerning that varies with the font’s variation axes. HarfBuzz reads the first value of the array and nothing else (`kerxTupleKern`, `:47`). Its `NEWS` for 2.0.1 calls this “variation-kerning format in kerx table, although without variation”, and 2.1.0’s says reading tuples “Fixes kerning with Apple default San Francisco fonts”. `tuples.ttf` has the `Variation` bit and three values for each pair, the second and third twice and three times the first:

```table
font: tuples.ttf
table: kerx
```

```shape
tuples.ttf  AVTo  --language=en
```

The pairs get the first value. Kerning in a variable font with `kerx` doesn’t vary in HarfBuzz.

## Five formats

`KerxSubTable::dispatch` (`:927`) reads formats 0, 1, 2, 4 and 6. A subtable of any other format is skipped.

| Format | What it holds | Applied by | Runs with `kern` off |
|---|---|---|---|
| 0 | sorted pairs | the kern machine | no |
| 1 | a state machine that pushes glyphs and applies lists of values | the state-machine driver | only if cross-stream |
| 2 | a left and a right class table, and an array | the kern machine | no |
| 4 | a state machine that attaches a glyph to a point on another | the state-machine driver | yes |
| 6 | a row and a column lookup, and an array of 16- or 32-bit values | the kern machine | no |

Format 3, `kern`’s compact format, has no `kerx` version. Formats 4 and 6 are new.

Before running a subtable, `KerxTable::apply` checks whether any glyph in the buffer could start an action, or be the first glyph of a pair, from sets gathered once per face. If none can, the trace says “skipped subtable *n* because no glyph matches” (`:1085`).

### Formats 0, 2 and 6

Format 0 is `kern`’s format 0 with a 32-bit count and search fields; the pairs themselves are still two 16-bit glyph IDs and a 16-bit value, and they must still be sorted. Format 2 is `kern`’s class array, with AAT lookup tables for its classes. Format 6 is new: a row lookup gives the left glyph a value, a column lookup gives the right glyph one, and the kerning value is the entry of the array at their sum (`:759`). A flag, `ValuesAreLong`, makes the lookups and the array 32-bit. `format2.ttf` and `format6.ttf` hold the Latin pairs in each format:

```table
font: format6.ttf
table: kerx
```

```shape
kerx.ttf  AVTo  --language=en
format2.ttf  AVTo  --language=en
format6.ttf  AVTo  --language=en
```

In format 6 the row value is already an index into the array, a row number times `columnCount`, so A’s 3 and V’s 1 find −80. HarfBuzz doesn’t check the sum against `rowCount` and `columnCount`, only that the value it finds is inside the table (read from the code). A glyph missing from either lookup counts as 0, and so takes the value in the array’s first row or column, which should be 0.

Format 2 counts differently in `kerx`. In `kern`, a class value is a byte offset from the start of the subtable ([Four subtable formats](legacy-kern.html#four-subtable-formats)); in `kerx`, HarfBuzz takes the sum of the two class values as a byte offset from the start of the array, and halves it to get an index (`ExtendedTypes::byteOffsetToIndex`, `hb-aat-layout-common.hh:1255`). So A’s row is at 6 and T’s at 12, as `format2.ttf`’s listing shows:

```table
font: format2.ttf
table: kerx
```

HarfBuzz {{hb}}’s `NEWS` lists a fix for “wrong `kerx` kerning (formats 1 and 2)”, and HarfBuzz’s tests have a format 2 font built by hand to check the counting, with the comment “Left offsets: 0,6,12,0,0; right offsets: 0,0,2,4,0” (`test/shape/data/in-house/tests/aat-kerx.tests`, issue #6461).

### Format 1

Format 1 is the state machine of `kern`’s format 1 ([Four subtable formats](legacy-kern.html#four-subtable-formats)): an entry can push the current glyph, and an action applies a list of values to the glyphs pushed, the whole value to each glyph’s advance and offset. In `kerx` three things differ:

* An action is an index into the array of values, not a byte offset; and the array’s own offset counts from the start of the state machine, not of the subtable: “Discovered via testing”, says the comment (`:254`).
* A list ends with the value 0xFFFF, where `kern` marks the last value by its low bit (`:320`).
* The glyphs are not popped off the stack. HarfBuzz keeps the last eight pushed in a ring, and each action walks back through it from the latest; `kern` pops them. The comment says this is what Core Text does, “Contrary to the kerx spec’s destructive pops” (`:300`), and the 35 cases in `aat-kerx.tests` that check it “were measured on macOS 15.8.2 and 26.6.2”. The entry’s `Reset` flag, which should empty the stack, is ignored, because “CoreText ignores the kerx Reset flag” (`:269`).

A value is applied only to a glyph that has the `kern` mask, and a glyph that gets one is unsafe to break from there to the current glyph. This font from those tests gives three glyphs values of 50, 40 and 31; a `kern` list couldn’t hold the odd 31, since its low bit would end the list:

```shape
hb:test/shape/data/in-house/fonts/36f8d640bc42f35a59e607bcf7c4aa70b63d4ef4.ttf  aab  --language=en
```

## Attachment: format 4 and ankr

Format 4 doesn’t kern. It attaches: it moves a glyph so that a point on it sits on a point on another glyph, as GPOS’s mark attachment does. Its state machine has one flag of its own, `Mark`, which remembers the current glyph as the **marked glyph**. An entry with an action then positions the current glyph against the marked one. Each action names two points, one on each glyph, and how the points are found depends on the subtable’s action type, the top two bits of a 32-bit flags field that follows the state machine’s header (`:582`):

| Action type | An action holds | The point comes from |
|---|---|---|
| 0, control point actions | two point numbers | the glyph’s outline, through the font funcs |
| 1, anchor point actions | two anchor numbers | the `ankr` table |
| 2, control point coordinate actions | two pairs of coordinates | the action itself |

The low 24 bits of the flags give the offset of the actions, from the start of the state machine.

The **`ankr`** table, Apple’s anchor point table, lists points for each glyph that needs them: a lookup table from glyph to an offset, and at each offset a 32-bit count and that many x, y pairs in font units (`hb-aat-layout-ankr-table.hh:59`). An anchor number is an index into a glyph’s list. A glyph that isn’t in the lookup, or an index past the end of its list, gives the point (0, 0) (`:63`). The table must have version 0, or the sanitizer rejects it. Only `kerx` format 4 reads it.

`anchors.ttf` has a format 4 subtable whose machine puts A, T, V and o in one class and the acute in another. A letter is marked; an acute after it gets action 0, which names anchor 0 on each glyph:

```table
font: anchors.ttf
table: kerx
```

```table
font: anchors.ttf
table: ankr
```

The action, trimmed to the anchor case and what follows it, with its namespaces shortened (`:641`–`693`):

```c++
case 1: /* Anchor Point Actions. */
{
  const HBUINT16 *data = &ankrData[entry.data.ankrActionIndex * 2];
  unsigned int markAnchorPoint = *data++;
  unsigned int currAnchorPoint = *data++;
  const Anchor &markAnchor = c->ankr_table->get_anchor (c->buffer->info[mark].codepoint,
                                                        markAnchorPoint, num_glyphs);
  const Anchor &currAnchor = c->ankr_table->get_anchor (c->buffer->cur ().codepoint,
                                                        currAnchorPoint, num_glyphs);

  o.x_offset = hb_saturate_sub (c->font->em_scale_x (markAnchor.xCoordinate),
                                c->font->em_scale_x (currAnchor.xCoordinate));
  o.y_offset = hb_saturate_sub (c->font->em_scale_y (markAnchor.yCoordinate),
                                c->font->em_scale_y (currAnchor.yCoordinate));
}
break;
/* … */
o.attach_type() = ATTACH_TYPE_MARK;
o.attach_chain() = (int) mark - (int) buffer->idx;
```

So the acute’s offset becomes the difference between the two anchors, and it is linked to the marked glyph as a GPOS mark is linked to its base. When attachments are resolved after positioning, the advances between the two are taken off ([Resolving attachments](gpos.html#resolving-attachments)). The trace shows the offsets as the subtable leaves them, before that:

```trace
font: anchors.ttf
text: A\u0301o\u0301
options: --language=en
from: start table kerx
to: end table kerx
```

```shape
anchors.ttf  A\u0301o\u0301  --language=en
anchors.ttf  A\u0301o\u0301  --language=en  --features=-kern
```

On A the acute moves up 80 units, to A’s higher anchor; on the narrower o it moves right by 50, to o’s center. Format 4 doesn’t look at the `kern` feature or the kerning mask at all (`:713`), so `-kern` changes nothing.

```draw
font: anchors.ttf
text: A\u0301o\u0301
options: --language=en
```

Coordinate actions put the two points in the action. `coords.ttf` has the same machine with A’s point and the acute’s point as coordinates:

```shape
coords.ttf  A\u0301o\u0301  --language=en
```

The acute on A is placed as before; on o it is placed as if o were A, 100 to the right and 80 up. The coordinates belong to the action, not to the glyphs, so a font with coordinate actions needs an entry and an action for every combination that is placed differently.

Control point actions ask the font funcs for a point of the glyph’s outline, with `get_glyph_contour_point_for_origin`. HarfBuzz’s own `hb-ot` funcs don’t implement it (`hb-ot-font.cc:991` is commented out), and FreeType’s are the only ones that do ([Fonts and font functions](fonts-and-font-functions.html#the-other-funcs)). If either point can’t be found, the action does nothing (`hb-aat-layout-kerx-table.hh:626`). `points.ttf` names A’s point 1, its top left corner, and the acute’s point 0:

```shape
points.ttf  A\u0301o\u0301  --language=en
```

With the default funcs, nothing is attached, and the acutes are left where their outlines put them. This book’s build of HarfBuzz has no FreeType, so the same font with `--font-funcs=ft` can’t be shown here. GPOS’s anchor format 2, which also names an outline point, falls back to its x and y when the point can’t be found ([Anchors](gpos.html#anchors)); a `kerx` control point action has nothing to fall back to.

### Before and after

The marked glyph can come after the glyph attached to it. In left-to-right text with `Backwards` set, the machine walks the buffer from the end, so the glyph it marks is later in the text than the one it then positions. GPOS can’t do that, but the code that resolves attachments allows it, adding the advances between the two instead of taking them off: “This can happen with `kerx`: a mark attaching to a base after it in the logical order” (`OT/Layout/GPOS/GPOS.hh:133`). This font from HarfBuzz’s tests has a cross-stream format 0 subtable, then a cross-stream format 1, then a format 4 with `Backwards` set, which attaches the `m` at the start of the text to the first `b`, two glyphs later:

```shape
hb:test/shape/data/in-house/fonts/1bfb8aab9b49ef30e8deae3db271ca3dbc6208a1.ttf  xzbb  --language=en
```

The `m` is moved 925 units right, past its own advance and the `c`’s, onto the `b`; the last `b` has been raised 100 by the cross-stream subtable.

In right-to-left text it is the other way round. The buffer has been reversed into left-to-right order, so a subtable without `Backwards` would meet each Arabic mark before its base. Setting `Backwards` puts the glyphs back in logical order, base first. This Arabic font from HarfBuzz’s tests has two format 4 subtables, both with `Backwards` set, which place the vowel marks on the letters and the second damma on the shadda:

```shape
hb:test/shape/data/in-house/fonts/a8b4a746c2d1a1fd5d5d6108e366e79c0ae74ef5.ttf  \u0643\u064F\u0644\u064F\u0651  --language=ar
```

```draw
font: hb:test/shape/data/in-house/fonts/a8b4a746c2d1a1fd5d5d6108e366e79c0ae74ef5.ttf
text: \u0643\u064F\u0644\u064F\u0651
options: --language=ar
```

An attached glyph also takes the cross-stream offset of the glyph it is attached to, followed back along any cross-stream links (`resolve_cross_offset`, `OT/Layout/GPOS/MarkArray.hh:12`, called at `hb-aat-layout-kerx-table.hh:682`), so a mark stays on a base that cross-stream kerning has raised. Its own cross-stream link is replaced by the attachment.

> For type designers: format 4 sets only the attached glyph’s offset. It doesn’t zero its advance, and a plan that runs `kerx` doesn’t zero marks either (next section). A mark meant to be attached by `kerx` needs an advance of 0 in `hmtx`.

## Cross-stream

A cross-stream subtable in `kerx` works as it does in `kern` ([Cross-stream](legacy-kern.html#cross-stream)). At the first one, every glyph is linked to the glyph before it as if by a cursive attachment (`:1100`). A value is written into the second glyph’s offset across the line, and when the links are resolved, each glyph carries the offsets of the glyphs before it. `cross.ttf` is `kerx.ttf` with a second, cross-stream subtable that has A V +100 and bet gimel +100:

```table
font: cross.ttf
table: kerx
```

```shape
cross.ttf  AVAT  --language=en
cross.ttf  גבגב  --language=he
```

```draw
font: cross.ttf
text: AVAT
options: --language=en
```

The V is raised, and everything after it. In Hebrew the pairs are read left to right, so the raise builds up leftwards: the second pair, at the left end, is 200 up. The links are always set for the buffer’s logical order, even when an earlier subtable has left the buffer turned round, and they are resolved in that order, so it makes no difference whether the cross-stream subtable comes first; `cross-first.ttf` has the two subtables the other way round:

```shape
cross-first.ttf  גבגב  --language=he
```

In formats 0, 2 and 6 the kern machine *sets* the second glyph’s cross-stream offset to the value, rather than adding to it (`hb-kern.hh:96`), so of two cross-stream subtables that kern the same pair, the later one wins. It takes the value 0x8000 as −32,768, as in `kern` (read from the code). Format 1 adds its values, and treats 0x8000 as a reset: the glyph’s link is cut and its offset set to 0. The comment calls this “undocumented in the spec, but described in the ‘kern’ table example” (`hb-aat-layout-kerx-table.hh:358`). Format 1 also kerns across a vertical line, where the comment says “CoreText doesn’t do crossStream kerning in vertical. We do.” (`:383`).

## When kerx is used

The plan chooses between GPOS, `kerx`, `kern` and fallback kerning once, when it is made (`hb-ot-shape.cc:153`–`187`). [Fallbacks](fallbacks.html#who-decides) quotes the code; for `kerx` it comes to two tests:

1. If the font has `kerx` and doesn’t have both GSUB and GPOS, `kerx` is used. GSUB counts only if it will be applied, which it isn’t when the font is shaped with `morx` ([AAT inside HarfBuzz](aat-inside-harfbuzz.html)).
2. Otherwise, if GPOS isn’t used or has no `kern` feature in the language system it chose, and the font has `kerx`, `kerx` is chosen too.

The first test is HarfBuzz issue #3008: “Prefer GPOS over kerx if GSUB is present”. Its `NEWS` entry, in 2.8.2, says “GPOS is preferred over kerx, if GSUB was applied”. A font with `kerx` never uses its `kern` table, and never gets fallback kerning. `plan->position` (`:271`) then runs GPOS if the plan chose it, and otherwise `kerx`: never both.

| The font has | Positioning |
|---|---|
| `kerx` | `kerx` |
| `kerx` and GPOS | `kerx` |
| `kerx`, GSUB and GPOS | GPOS |
| `kerx`, `morx`, GSUB and GPOS | `kerx` (GSUB isn’t applied) |
| `morx` and GPOS, no `kerx` | GPOS (since 3.1.0) |

`kerx-gpos.ttf` is `kerx.ttf` with a GPOS that has `kern` (A V −50) and `mark`; `kerx-gsub-gpos.ttf` adds a GSUB, whose one feature is off by default; `morx-kerx.ttf` adds a `morx` table that does nothing to this text; `morx-gpos.ttf` is that without `kerx`:

```shape
kerx-gpos.ttf  AVTo  --language=en
kerx-gsub-gpos.ttf  AVTo  --language=en
morx-kerx.ttf  AVTo  --language=en
morx-gpos.ttf  AVTo  --language=en
```

With `kerx`, A V is −80, split, and T o is kerned; with GPOS, A V is GPOS’s −50, all on the A, and T o isn’t kerned. The two tables are never combined.

### What else kerx turns off

The plan treats a font with `kerx` as positioning its own marks. When `apply_kerx` is set, marks aren’t zeroed, zeroed marks aren’t moved back, and there is no fallback mark positioning (`:189`–`207`; the table in [Who decides](fallbacks.html#who-decides) lists them). In `kerx.ttf`, whose `kerx` attaches nothing, nothing places the acute:

```shape
kerx.ttf  A\u0301V  --language=en
```

The second test above has an odd result. With GSUB and GPOS, and a GPOS that has no `kern` feature in the language system chosen, the first test chooses GPOS and the second sets `apply_kerx` as well. `position` runs only GPOS, but the mark decisions are made as if `kerx` ran. `mark-gpos.ttf` has a GSUB, a GPOS with `mark` and no `kern`, and an acute with an advance of 200; `mark-gpos-kerx.ttf` is the same with `kerx.ttf`’s `kerx` added:

```shape
mark-gpos.ttf  A\u0301V  --language=en
mark-gpos-kerx.ttf  A\u0301V  --language=en
mark-gpos-kerx.ttf  AVTo  --language=en
```

With `kerx` in the font, GPOS still attaches the acute, but its 200-unit advance is no longer zeroed, and the `kerx` pairs aren’t applied either. That looks like a HarfBuzz bug. The second test seems meant to let a font whose GPOS doesn’t kern fall back on another table for kerning (inferred); with `kerx`, the fallback never runs, and the marks lose their zeroing.

## Tracking: trak

**Tracking** is a uniform change to the space between letters: looser at small sizes, where letters need room to stay legible, and tighter at display sizes. Apple’s **`trak`** table, the tracking table, gives the amount per point size, so that a font can carry its own size-dependent spacing.

The table has a header (version 1.0, a format of 0, and offsets to horizontal and vertical data) and, for each direction, a list of point sizes and a list of **tracks**. A track is a degree of tightness, such as −1 for tight, 0 for normal and 1 for loose, with a name, and a value in font units for each size (`hb-aat-layout-trak-table.hh:46`–`189`). `trak.ttf` has three horizontal tracks over four sizes, and one vertical track:

```table
font: trak.ttf
table: trak
```

### Which value

HarfBuzz always uses track 0 (`hb_aat_layout_track` passes no other, `hb-aat-layout.cc:398`), so `Tight` and `Loose` are never read. If a font had no track 0, `TrackData::get_tracking` would interpolate between the tracks either side of it, and a table with only one track uses that one, whatever its value (`:132`).

The point size is the font’s `ptem`, or 12 points if it isn’t set, Core Text’s default (`HB_CORETEXT_DEFAULT_FONT_SIZE`, `hb-aat-layout.hh:36`; [Three kinds of size](fonts-and-font-functions.html#three-kinds-of-size)). Below the first size in the table the first size’s value is used, above the last the last one’s, and in between the value is interpolated in a straight line between the two sizes either side (`TrackTableEntry::get_value`, `hb-aat-layout-trak-table.hh:75`). The result is scaled from font units like any other value:

```shape
trak.ttf  AV  --language=en  --font-ptem=3
trak.ttf  AV  --language=en  --font-ptem=6
trak.ttf  AV  --language=en  --font-ptem=9
trak.ttf  AV  --language=en
trak.ttf  AV  --language=en  --font-ptem=18
trak.ttf  AV  --language=en  --font-ptem=72
trak.ttf  AV  --language=en  --font-ptem=144
```

At 3 points the letters get 6 points’ +50; at 9, halfway between 6 and 12, +25; with no size set, 12 points’ 0; at 18, halfway between 12 and 24, −10; at 144, 72 points’ −40. HarfBuzz’s own test, `aat-trak.tests`, does the same with the font `TRAK.ttf`. The values are not extrapolated beyond the table’s sizes.

### Where the space goes

`trak::apply` (`:220`) adds the value to the advance of the first glyph of each grapheme, found by the continuation bits that [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#continuations-just-enough-of-graphemes) describes. A mark doesn’t start a grapheme, so it gets nothing. (The acute’s offset here is fallback mark positioning’s, which runs later and centers it over the tracked A.)

```shape
trak.ttf  A\u0301V  --language=en  --font-ptem=6
trak.ttf  גב  --language=he  --font-ptem=6
```

The space is added to an advance, so it lies to the right of each grapheme in the output. In left-to-right text that is after each one, and the line ends with it; in right-to-left text it is before each one in reading order, between a letter and the one read before it, and the line starts with it. Within a grapheme of several glyphs only the first glyph’s advance changes, so its glyphs aren’t pulled apart.

`trak` runs last in step 17, after GPOS or `kerx` and after `kern` (`hb-ot-shape.cc:289`), but before attachments are resolved. A mark attached to a base is placed from the base’s advance as it is then, tracking included, so it stays on its base.

### Vertical tracking

In vertical text the value comes from the vertical track table and is added to the vertical advance (`hb-aat-layout-trak-table.hh:242`). `trak.ttf`’s vertical track is +100 at every size:

```shape
trak.ttf  AV  --language=en  --direction=ttb
```

The advance has gone from −1,000 to −900. Vertical advances are negative, growing downwards, so adding a positive value brings the glyphs *closer*. GPOS negates a vertical advance from a value record for this reason, “y_advance values grow downward but font-space grows upward” (`ValueFormat.hh:114`); `trak` doesn’t. A positive value, which loosens horizontal text, tightens a column, which looks like a bug (inferred: Core Text’s behavior in vertical text hasn’t been checked here).

> Since {{hb}}: fixed on HarfBuzz main by [`45c7759`](https://github.com/harfbuzz/harfbuzz/commit/45c7759a025ace1fd7ca632114ec7111808d5fc5) and [`1e2cf5d`](https://github.com/harfbuzz/harfbuzz/commit/1e2cf5dafa790d809dec0ef05850b1dd3703d1b5) (17 November 2026), so main adds vertical tracking in the direction of the advance: here the advances become −1,100.

### When it applies

The plan applies `trak` when the font has one and also has a STAT table (`hb-ot-shape.cc:216`):

```c++
/* According to Ned, trak is applied by default for "modern fonts", as detected by presence of STAT table. */
#ifndef HB_NO_STYLE
  plan.apply_trak = hb_aat_layout_has_tracking (face) && face->table.STAT->has_data ();
#else
  plan.apply_trak = false;
#endif
```

`trak-nostat.ttf` is `trak.ttf` without STAT:

```shape
trak.ttf  AV  --language=en  --font-ptem=6
trak-nostat.ttf  AV  --language=en  --font-ptem=6
```

Nothing else is asked. A font doesn’t need `morx` or `kerx` for its `trak` to apply, nor to be shaped without GPOS, and no feature turns it off. 10.3.0 moved tracking out of shaping and into the advances that the `hb-ot` font funcs return, and dropped “The ‘trak’ pseudo OpenType feature that could be used to disable ‘trak’ table application”; 11.0.1 moved it back, because the change “required every font functions implementation to handle it”, and the feature didn’t come back (`NEWS`).

The same test is in `trak::get_tracking` (`hb-aat-layout-trak-table.hh:207`), which the Core Text font funcs use to take Core Text’s own tracking back out of the advances it reports ([The other funcs](fonts-and-font-functions.html#the-other-funcs)). `hb_aat_layout_has_tracking`, public since 2.3.0, says only whether the table is there.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-aat-layout-kerx-table.hh` | `kerx` and `KerxTable`, shared with `kern`: the header, coverage bits, subtable loop, cross-stream links and sanitizing; formats 0, 1, 2, 4 and 6; `kerxTupleKern` |
| `src/hb-aat-layout-ankr-table.hh` | `ankr` and `get_anchor` |
| `src/hb-aat-layout-trak-table.hh` | `trak`: choosing a track, interpolating between sizes, `apply` |
| `src/hb-aat-layout.cc` | `hb_aat_layout_position` (`:363`), which sets up `ankr` for `kerx`; `hb_aat_layout_track` (`:398`) |
| `src/hb-aat-layout-common.hh` | `ExtendedTypes`, the lookup tables, the state-machine driver |
| `src/hb-kern.hh` | the kern machine, used by formats 0, 2 and 6 |
| `src/hb-ot-shape.cc` | the plan’s choice of positioning (`:153`), `trak` (`:216`), `hb_ot_shape_plan_t::position` (`:271`) |
| `src/OT/Layout/GPOS/GPOS.hh`, `MarkArray.hh` | resolving attachments, including a base after its mark; `resolve_cross_offset` |
| `test/shape/data/in-house/tests/` | `aat-kerx.tests`, `aat-trak.tests` |

`HB_NO_AAT_SHAPE` leaves out `kerx`, `ankr` and `trak` with the rest of AAT shaping; `HB_NO_AAT` sets it, and `HB_MINI` sets that (`hb-config.hh:130`). `HB_NO_STYLE`, which `HB_LEAN` sets (`:80`), turns `trak` off. A `kerx` table may have at most `HB_AAT_MAX_SUBTABLES`, 1,024, subtables, or it is rejected whole (`hb-limits.hh:98`).

## In short

* `kerx` is Apple’s `kern` with 32-bit fields. HarfBuzz runs it with the same code, so its pairs are split, pass over marks and read left to right; but it is used for every script, not only those whose shaper allows `kern`.
* It reads formats 0, 1, 2, 4 and 6. Pair formats skip a subtable marked `Backwards`; format 2 counts class offsets from the array; format 1 follows Core Text rather than the specification; tuple values are read as their first value, so `kerx` doesn’t vary.
* Format 4 attaches a glyph to a marked one, through `ankr` anchors, coordinates in the action, or outline points; the last needs font funcs that find points, which `hb-ot`’s don’t. It runs even with `kern` off.
* `kerx` is used unless the font has both GSUB and GPOS (GSUB not counting under `morx`); a font that has it never uses `kern`. A plan with `kerx` leaves marks to the font, including, through a quirk, when GPOS runs in its place.
* `trak` adds track 0’s value at the font’s point size (12 if unset), interpolated between the table’s sizes, to the first glyph of each grapheme, after all other positioning. It applies only if the font also has STAT, and nothing turns it off.
