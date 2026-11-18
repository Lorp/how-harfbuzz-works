# Legacy kern

Before GPOS, a TrueType font kerned with a table of its own, `kern`: a list of glyph pairs and the amount to move each pair closer or apart. Fonts still carry one. Some are old, and some are new fonts that keep a `kern` table beside GPOS for software that reads nothing else (HarfBuzz issue #5607 is about such fonts). HarfBuzz reads the table, but it doesn’t always use it: it depends on what else the font has, on which language system GPOS chose, and since 12.2.0, on the script.

This chapter is about that table: its two incompatible versions, the four subtable formats HarfBuzz reads, the coverage bits, the plan’s decision whether to use it, and the loop that applies it. Kerning that comes from an application’s font functions, when a font has no kerning table of any kind, is in [Fallbacks](fallbacks.html). Apple’s newer `kerx` table shares most of its code with `kern`, and has a chapter of its own, [AAT positioning](aat-positioning.html).

The examples come from one test font, `kern.ttf`, built by `fonts/legacy-kern/build-fonts.py`, and eight variants of it. It has box glyphs for a few Latin letters, a combining acute, and two letters each of Thai, Devanagari and Hebrew. It has no GSUB and no GPOS, only a `kern` table. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on those fonts when the page was built.

## Two tables called kern

There are two `kern` tables. Microsoft’s, which the OpenType specification describes, starts with a 16-bit version, 0, and a 16-bit count of subtables. Apple’s, in the TrueType Reference Manual, starts with a 32-bit version, 1.0 (`0x00010000`), and a 32-bit count. Their subtable headers differ too:

| | OpenType, version 0 | Apple, version 1.0 |
|---|---|---|
| table header | `version` (16 bits), `tableCount` (16) | `version` (32 bits), `tableCount` (32) |
| subtable header | `versionZ`, `length` (16), `format`, `coverage` | `length` (32), `coverage`, `format`, `tupleIndex` |
| header size | 6 bytes | 8 bytes |
| HarfBuzz struct | `KernOTSubTableHeader` (`hb-ot-kern-table.hh:204`) | `KernAATSubTableHeader` (`:259`) |

HarfBuzz tells them apart by the first 16 bits. The struct `kern` (`hb-ot-kern-table.hh:313`) is a union of the two, and `get_type` reads its first `HBUINT16`: 0 is the OpenType table, 1 is the first half of Apple’s `0x00010000`. Anything else is neither, and nothing in it is read. Each version is then a `KerxTable` (`hb-aat-layout-kerx-table.hh:999`), the template that `kerx` uses too, given its own header type. So the same code walks the subtables of all three tables; only the header and the sizes of the fields change.

`kern.ttf` has the OpenType version and `apple.ttf` the Apple one, with the same pairs. In TTX:

```table
font: kern.ttf
table: kern
```

```table
font: apple.ttf
table: kern
```

They kern alike:

```shape
kern.ttf  AVTo  --language=en
apple.ttf  AVTo  --language=en
```

Each pair moves by its full value, but not in the way GPOS would move it: A’s advance has lost 40 units and V has lost 40 of advance *and* 40 of offset. That is the subject of the last section. A table with no subtables counts as no table at all: `hb_ot_layout_has_kerning` is true only if the first 32 bits aren’t zero (`:317`), which for the OpenType version means a count of at least one.

Checking the table is the [sanitizer](trust-nothing-the-sanitizer.html)’s work, as for any table. Each subtable is checked inside its own `length`, except the last, whose length is ignored because an OpenType subtable longer than 64 KB can’t state it; [A smaller window](trust-nothing-the-sanitizer.html#a-smaller-window) tells that story. A table that declares more than `HB_AAT_MAX_SUBTABLES` subtables, 1,024, is rejected whole (`hb-aat-layout-kerx-table.hh:1154`), because HarfBuzz keeps two glyph sets for each.

## Four subtable formats

`KernSubTable::dispatch` (`hb-ot-kern-table.hh:141`) chooses by the subtable’s `format`, and reads four:

| Format | What it holds | Specified for | HarfBuzz struct |
|---|---|---|---|
| 0 | ordered pairs: left glyph, right glyph, value | both | `KerxSubTableFormat0` |
| 1 | a state machine that pushes glyphs and pops values | Apple | `KerxSubTableFormat1` |
| 2 | a left class table, a right class table, and an array of values | both | `KerxSubTableFormat2` |
| 3 | a class for every glyph on each side, and a matrix of indices into a list of values | Apple | `KernSubTableFormat3` |

Formats 0, 1 and 2 are `kerx`’s own structs, made with the `kern` header and `ObsoleteTypes`: 16-bit offsets, and class values that are byte offsets rather than indices. Only format 3 has a struct of its own. HarfBuzz doesn’t check which header a format came under, so it would run a format 1 or 3 subtable in a Microsoft table too. A build with `HB_NO_AAT_SHAPE` leaves out formats 1 and 3 and the Apple header with them (`:148`), so an Apple `kern` table is then ignored.

Format 0 is the common one. Its pairs are a `BinSearchArrayOf`, with the usual `searchRange`, `entrySelector` and `rangeShift`, and `KerxSubTableFormat0::get_kerning` finds a pair by binary search (`hb-aat-layout-kerx-table.hh:101`). That only works if the pairs are sorted, by left glyph ID and then right, as the specification requires. `unsorted.ttf` has `kern.ttf`’s pairs in descending order, and none of them is found:

```shape
unsorted.ttf  AVTo  --language=en
```

```table
font: unsorted.ttf
table: kern
```

> For type designers: TTX doesn’t show the order. It lists pairs by glyph name, whatever order they are in, and fontTools sorts them by glyph ID again when it compiles. A `kern` table from a tool that writes its own bytes is worth checking another way.

Format 2 sorts glyphs into classes. A left class table and a right class table each cover a range of glyphs, and each glyph’s class value is already a byte offset: the left one to the start of a row, the right one to a column within the row. HarfBuzz counts their sum from the start of the subtable (`:464`). The OpenType specification’s wording, “adding the class values to the address of the array”, suggests counting from the array instead; a font built that way doesn’t kern in HarfBuzz, because every sum falls before the array, where HarfBuzz finds no value. A glyph outside a class table has class 0, and is not kerned on that side. Format 3 gives every glyph a left class and a right class, one byte each, and a matrix of one-byte indices into a list of at most 255 values (`hb-ot-kern-table.hh:48`). `format2.ttf` and `format3.ttf` are `kern.ttf` with the Latin pairs written in each format, byte by byte, because fontTools writes only format 0:

```shape
format2.ttf  AVTo  --language=en
format2-array.ttf  AVTo  --language=en
format3.ttf  AVTo  --language=en
```

`format2-array.ttf` is `format2.ttf` with its left class values counted from the array. The specification also says “Format 0 is the only subtable format supported by Windows.”

Format 1 isn’t a list of pairs at all. It is a state machine of the kind `morx` uses ([AAT inside HarfBuzz](aat-inside-harfbuzz.html)): an entry can push the current glyph on a stack of up to eight, and an action pops glyphs and adds a value to each. In `kern`, the last value of an action has its low bit set (`hb-aat-layout-kerx-table.hh:345`). A popped glyph gets the whole value, on its advance and its offset alike, not half on each of two glyphs. This font from HarfBuzz’s tests has one format 1 subtable, under the Apple header:

```shape
hb:test/shape/data/in-house/fonts/a5baedaf2c0f467d6a08701309a177dbd7e6156d.ttf  ab
```

The first glyph’s advance has dropped by 100 and it has moved 100 left. HarfBuzz {{hb}}’s `NEWS` lists a fix for `kern` state machines whose initial state isn’t the first one, which were being ignored.

## Coverage bits

Each subtable has a byte of coverage flags. The two headers define different bits, and put the byte in different places: in the OpenType header it is the low byte of a 16-bit field whose high byte is the format; in the Apple header it is the high byte, and the format the low one. HarfBuzz’s structs read each as two separate bytes, so neither needs masking.

| Bit | OpenType | Apple | What HarfBuzz does |
|---|---|---|---|
| direction | `Horizontal` (0x01): set for horizontal data | `Vertical` (0x80): set for vertical data | runs the subtable only in text of that direction (`:1078`) |
| `CrossStream` | 0x04 | 0x40 | moves glyphs across the line instead of along it |
| `Minimum` | 0x02 | none | ignored |
| `Override` | 0x08 | none | ignored |
| `Variation` | none | 0x20 | skips the subtable |
| `tupleIndex` | none | header field | not read: “We don’t implement” (`hb-ot-kern-table.hh:287`) |

`KernOTSubTableHeader` defines `Minimum` and `Override` (`:215`), and nothing reads them. The specification says that with the override bit “the value in this table should replace the value currently being accumulated”, and that a subtable with the minimum bit holds minimum values, which limit how far kerning and tracking together may move a pair. HarfBuzz runs each subtable in its own pass over the buffer, so values always add up. `override.ttf` has `kern.ttf`’s subtable and then one with A V −30 and the override bit:

```shape
kern.ttf  AV  --language=en
override.ttf  AV  --language=en
```

The pair has moved by −110, not −30. A comment on the sanitizer (`hb-aat-layout-kerx-table.hh:1161`) says Microsoft’s implementation reads only one subtable, of format 0, and the specification agrees, so a font that relies on more than one is relying on something few readers do. A subtable with `Minimum` set is kerned like any other, its limits added as kerning values.

### Cross-stream

A **cross-stream** subtable moves glyphs across the line: up and down in horizontal text, sideways in vertical. HarfBuzz’s `NEWS` for 2.1.2, which added it, calls it “cursive positioning, etc”. HarfBuzz gives it the meaning `kerx` has. The first time it meets a cross-stream subtable, it links every glyph to the one before it as if by a cursive attachment (`:1103`). The value is then written into the second glyph’s offset across the line, and when the links are resolved after positioning, each glyph carries the offsets of the ones before it. `cross.ttf` adds a cross-stream subtable to `kern.ttf`, with A V +100, and T o with the value 0x8000:

```shape
cross.ttf  AVAT  --language=en
cross.ttf  AVAV  --language=en
cross.ttf  AVTo  --language=en
```

The V is raised by 100, and so is everything after it, until another pair raises it again. The ordinary subtable before it has still kerned A V along the line. The specification says “The value 0x8000 in the kerning data resets the cross-stream kerning back to 0.” Only the format 1 state machine knows that (`hb-aat-layout-kerx-table.hh:360`). The kern machine, which runs formats 0, 2 and 3, takes 0x8000 as −32,768, so the `o` ends up 32,668 units below the line instead of on it. That looks like a HarfBuzz bug. A plan with cross-stream `kern` doesn’t move marks back by their advance when it zeroes them, nor position them itself (`hb-ot-shape.cc:198`), and a plan with a format 1 subtable doesn’t zero marks at all (`:189`). [The pipeline, step by step](the-pipeline-step-by-step.html#gpos-and-what-surrounds-it) shows where those steps are.

### Vertical subtables

The direction bit means that an OpenType subtable without `Horizontal` is for vertical text. In practice it is never used. In vertical text the plan’s kerning feature is `vkrn`, not `kern` (`hb-ot-shape.cc:127`), and `vkrn` is neither turned on by default nor kept, as `kern` is, when the font lacks it. So the kerning mask is zero, and no format 0, 2 or 3 subtable kerns (read from the code). The test fonts’ subtable is horizontal, and is skipped in vertical text as it should be:

```shape
kern.ttf  AV  --language=en  --direction=ttb
```

[Vertical text](vertical-text.html) has the rest.

## When the plan uses kern

Whether `kern` runs is decided when the shape plan is made, in `hb_ot_shape_planner_t::compile` (`hb-ot-shape.cc:127`–`187`), along with GPOS, `kerx` and fallback kerning; [Fallbacks](fallbacks.html#who-decides) quotes the code. The legacy `kern` table is used when all of these are true:

1. The font has no `kerx`. Any `kerx` that the first test passed over is taken up in the second, so a font with both never uses `kern`.
2. GPOS isn’t being used, or it is but has no `kern` feature in the language system it chose. `has_gpos_kern` asks the map, so it looks only at GPOS’s choice of script and language, not at the whole table.
3. The font has a `kern` table with at least one subtable.
4. The script shaper allows it: its `fallback_position` setting is true.

`plan->position` (`hb-ot-shape.cc:271`) then runs GPOS or `kerx`, and after it `kern` or fallback kerning. GPOS and `kern` aren’t exclusive. When both are applied, each does its own part, and `kern` comes second.

### Alongside GPOS

`both.ttf` is `kern.ttf` with a GPOS added, from `fonts/legacy-kern/both.fea`. Latin’s default language system has `kern` (A V −50) and `mark`. Its Turkish language system, `TRK`, has `mark` only, as it would if a tool had forgotten it. Devanagari has `dist` (ka ka −30) and no `kern`:

```shape
both.ttf  AVTo  --language=en
both.ttf  AVTo  --language=tr
both.ttf  A\u0301V  --language=tr
```

In English, GPOS has a `kern` feature, so the `kern` table is left alone: A V gets GPOS’s −50, and T o isn’t kerned, because GPOS doesn’t kern it. In Turkish, the same text in the same font gets the `kern` table’s values. With an acute, GPOS places the mark and the `kern` table kerns A V across it: the two tables have each done part of the job. The mark stays over the A, though the A’s advance shrank after GPOS had placed it. That’s because `kern` runs before attachments are resolved, and resolving them adds up the advances as they are then ([Resolving attachments](positioning-glyphs-gpos.html#resolving-attachments)).

This is the behavior since HarfBuzz 2.0.0. Before it, the `kern` table was used only in a font with no GPOS at all. The commit that changed it says why: it applies to “Arial, Times New Roman, etc in Win7”, which have a GPOS without kerning in it, and were “not kerning before” (commit e655fd38, October 2018).

### The kern feature and its mask

`kern` is one of the default horizontal features, with `F_HAS_FALLBACK` ([From features to lookups](from-features-to-lookups.html#the-flags)): it gets a mask bit even when neither GSUB nor GPOS has it, because the `kern` table and fallback kerning both read that bit. `kern_mask` is the bit, and `requested_kerning` says whether there is one. Turning the feature off for the whole text removes it from the map. Then formats 0, 2 and 3 return at once (`hb-aat-layout-kerx-table.hh:109`); format 1 still runs if it is cross-stream (`:422`).

Turned off for part of the text, the feature clears the bit on those glyphs, and a pair is kerned only if *both* its glyphs have it. The second glyph is found by the skipping iterator, which won’t match a glyph without the mask:

```shape
kern.ttf  AVAV  --language=en  --features=-kern
kern.ttf  AVAV  --language=en  --features=kern[0:1]=0
kern.ttf  AVAV  --language=en  --features=kern[1:]=0
```

Turning off `kern` also hides GPOS’s `kern` feature from `has_gpos_kern`, so in `both.ttf` the plan applies the `kern` table, and then the table does nothing because kerning wasn’t requested. The trace shows the table and its subtable start and end with nothing done. (The empty script tag in GPOS’s message is a slip in the message, which prints GSUB’s choice of script, `hb-ot-layout.cc:2149`; this font has no GSUB.)

```trace
font: both.ttf
text: AV
options: --language=en --features=-kern
from: start table GPOS
to: end table kern
```

### Which shapers apply it

`fallback_position` is one of the four settings of a script shaper ([What the choice decides](choosing-a-script-shaper.html#what-the-choice-decides)). It also decides whether marks are positioned by HarfBuzz when there is no GPOS. In {{hb}} it is:

| Shaper | `fallback_position` | Legacy `kern` |
|---|---|---|
| default | true | yes |
| Arabic (Arabic, and Syriac when GSUB has a Syriac script; horizontal text only) | true | yes |
| Hebrew | true | yes |
| Hangul | true | yes |
| Thai (also Lao) | false | no |
| Indic | false | no |
| Khmer | false | no |
| Myanmar, and Myanmar Zawgyi | false | no |
| USE | false | no |
| dumber | false | (not consulted) |

The planner reads it from the shaper it first chose, as `script_fallback_position` (`hb-ot-shape.cc:94`), before an AAT font’s shaper is replaced by `dumber` ([AAT fonts](choosing-a-script-shaper.html#aat-fonts)). So a `morx` font with a `kern` table and no `kerx` kerns Latin and Hebrew, but not Devanagari or Thai (read from the code; no test font here has `morx`).

`kern.ttf` has a pair in each of four scripts:

```shape
kern.ttf  กก  --language=th
kern.ttf  कक  --language=hi
kern.ttf  גב  --language=he
kern.ttf  בג  --language=he
both.ttf  कक  --language=hi
```

Thai and Devanagari aren’t kerned, though their pairs are in the table. Hebrew is kerned, and only one way round, which the next section explains. In `both.ttf`, Devanagari gets GPOS’s `dist`, −30, and nothing from the `kern` table.

## What changed in 12.2

12.2.0’s `NEWS` says: “Disable legacy `kern` table for most shapers, enabling it only for default, Arabic, Hangul, and Hebrew shapers.” Until then, the plan’s line was `plan.apply_kern = true`.

The reason was double kerning. HarfBuzz issue #5607 reported that the legacy table was being used “in more common scenarios” than the manual said: whenever the chosen language system has no `kern` feature. Fonts compiled by ufo2ft for scripts such as Devanagari kern with `dist` instead, so there is no `kern` feature, and the same pairs, often between characters common to several scripts, were also in the `kern` table that the font carried for older software. HarfBuzz applied both. Behdad Esfahbod suggested reusing the shaper’s `fallback_position`, then true only for the default, Hebrew and Arabic shapers, and the change was made in pull request #5609. Jonathan Kew asked in its review whether Hangul should keep the table too, since `dist` is meant for Indic and other Brahmi-derived scripts, and Hangul’s `fallback_position` was turned on (commit 63e8c13e), which also gave Hangul fallback mark positioning. A second commit made fallback kerning, through the font functions, follow the same setting (5973479e, [Fallbacks](fallbacks.html)).

So the rule isn’t about `dist`. A Thai or Indic font with a `kern` table and no GPOS at all isn’t kerned either, as `kern.ttf` shows. Apart from Hangul, the shapers that lost the table are the ones that already left mark positioning to the font. The test suite has the case from the issue (`test/shape/data/in-house/tests/per-script-kern-fallback.tests`).

HarfBuzz’s manual hasn’t caught up. `docs/usermanual-opentype-features.xml` still says that HarfBuzz uses the `kern` table “if neither table is found”, meaning `kerx` and GPOS, which hasn’t been true since 2018 and says nothing of the shapers.

> For type designers: in HarfBuzz, a `kern` table is a fallback for Latin, Cyrillic, Greek, Arabic, Hebrew, Hangul and the other scripts the default shaper handles, and only where GPOS has no `kern` feature in the language system it chooses. Every language system needs its `kern` feature, or that language gets the old table instead, with its own values. For Thai, Lao, Khmer, Myanmar and the Indic and USE scripts, kerning has to be in GPOS.

## How the kerning is applied

Every format but 1 ends in the same loop, the **kern machine**, `hb_kern_machine_t::kern` (`hb-kern.hh:46`). It is a template over a *driver* with a `get_kerning (left, right)` method: each subtable format is a driver, and so is fallback kerning, whose driver asks the font functions. Trimmed of the vertical case, the cross-stream case and scaling’s on-off switch, and with its `goto` written as an `if`:

```c++
buffer->unsafe_to_concat ();
OT::hb_ot_apply_context_t c (1, font, buffer, hb_blob_get_empty ());
c.set_lookup_mask (kern_mask);
c.set_lookup_props (OT::LookupFlag::IgnoreMarks);
auto &skippy_iter = c.iter_input;

for (unsigned int idx = 0; idx < count;)
{
  if (!(info[idx].mask & kern_mask)) { idx++; continue; }

  skippy_iter.reset_fast (idx);
  unsigned unsafe_to;
  if (unlikely (!skippy_iter.next (&unsafe_to))) { idx = unsafe_to; continue; }

  unsigned int i = idx, j = skippy_iter.idx;
  hb_position_t kern = driver.get_kerning (info[i].codepoint, info[j].codepoint);
  if (kern)
  {
    kern = font->em_scale_x (kern);
    hb_position_t kern1 = kern >> 1;
    hb_position_t kern2 = kern - kern1;
    pos[i].x_advance = hb_saturate_add (pos[i].x_advance, kern1);
    pos[j].x_advance = hb_saturate_add (pos[j].x_advance, kern2);
    pos[j].x_offset  = hb_saturate_add (pos[j].x_offset, kern2);
    buffer->unsafe_to_break (i, j + 1);
  }
  idx = skippy_iter.idx;
}
```

Five things follow from it.

**It is GPOS’s iterator.** The context is made for table 1, GPOS, with the lookup flag `IgnoreMarks` and the kerning mask. So the second glyph of a pair is found as a GPOS pair lookup with `IgnoreMarks` would find it: marks are passed over, and so are ZWJ, ZWNJ and the other default ignorables ([What a lookup passes over](positioning-glyphs-gpos.html#what-a-lookup-passes-over)). A `kern` table has no lookup flags of its own; this is HarfBuzz’s choice for it:

```shape
kern.ttf  A\u0301V  --language=en
kern.ttf  A\u200CV  --language=en
kern.ttf  A V  --language=en
```

A space is a glyph like any other, so A and V either side of one aren’t a pair.

**The value is split.** Half goes on the first glyph’s advance, rounded down; the rest goes on the second glyph’s advance and, to put it back where it would have been, on its offset. Every glyph after the pair moves by the whole value, and so does the second glyph’s drawing, so it looks the same as GPOS’s kerning; but the change is shared between the two glyphs’ advances, which moves the boundary between them, where a caret goes, halfway. That was the reason 4.0.0’s `NEWS` gave for splitting GPOS kerning the same way, “for improved cursor positioning”. GPOS does it now only in a build with `HB_SPLIT_KERN`, which is off ([Safe to break](positioning-glyphs-gpos.html#safe-to-break)); the kern machine always does it. Compare the English and Turkish results for `both.ttf` above: −50 all on A from GPOS, −80 shared from `kern`.

**Every glyph starts a pair.** After a pair, the loop moves to its second glyph, which then starts the next: A V A V is tried as A V, V A and A V. Each subtable runs over the whole buffer in its own pass, from `KerxTable::apply` (`hb-aat-layout-kerx-table.hh:1055`).

**Pairs are left and right.** In right-to-left text, `KerxTable::apply` reverses the buffer into visual order before a subtable runs and back afterward (`:1091`), so the first glyph of a pair is always the left-hand one, as both specifications define it. GPOS works in logical order instead. In the Hebrew example above, the pair is bet then gimel, left to right, so it kerns “גב”, typed gimel first, and not “בג”. A pair moved from a `kern` table to GPOS for a right-to-left script has to be turned round.

**It marks the buffer.** A kerned pair is unsafe to break from its first glyph to its second. And before any subtable runs, the whole buffer is marked unsafe to concatenate, once in `KerxTable::apply` and again in the kern machine, whether or not anything is kerned:

```shape
kern.ttf  AVTo  --language=en  --show-flags  --unsafe-to-concat
kern.ttf  oA  --language=en  --show-flags  --unsafe-to-concat
both.ttf  oA  --language=en  --show-flags  --unsafe-to-concat
```

`o A` isn’t a pair in either font. With GPOS kerning only A is marked, by the pair lookup that tried it; with the `kern` table, both glyphs are, and they would be with `-kern` in `both.ttf` too, since the plan then still runs the table. Unsafe to concatenate is only a hint that reshaping may be needed, so this costs an application work, not correctness. [Buffers](buffers.html#glyph-flags) explains the flags.

The trace shows the table, its subtable and the machine, each with its own messages:

```trace
font: kern.ttf
text: AVTo
options: --language=en
from: start table kern
to: end table kern
```

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-kern-table.hh` | `kern`: the union of the two versions, `KernOTSubTableHeader` and `KernAATSubTableHeader` with their coverage bits, `KernSubTable` and its dispatch, `KernSubTableFormat3`, the accelerator |
| `src/hb-aat-layout-kerx-table.hh` | `KerxTable`, shared by `kern` and `kerx`: subtable iteration, direction and cross-stream handling, sanitizing; `KerxSubTableFormat0`, `1` and `2` |
| `src/hb-kern.hh` | `hb_kern_machine_t`, the pair loop |
| `src/hb-ot-shape.cc` | the plan’s choice between GPOS, `kerx`, `kern` and fallback kerning (`:127`), and `hb_ot_shape_plan_t::position` (`:271`) |
| `src/hb-ot-layout.cc` | `hb_ot_layout_has_kerning`, `has_machine_kerning`, `has_cross_kerning`, and `hb_ot_layout_kern` (`:130`) |
| `src/hb-ot-shaper-*.cc` | each shaper’s `fallback_position` |
| `test/shape/data/in-house/tests/` | `per-script-kern-fallback.tests`, `tt-kern-gpos.tests`, `kern-format1.tests`, `kern-format2.tests` |

`HB_NO_OT_KERN` leaves the `kern` table out of the build. `HB_NO_LEGACY` sets it, and `HB_MINI` sets that (`hb-config.hh:150`).

## In short

* There are two `kern` tables, Microsoft’s version 0 and Apple’s version 1.0, told apart by their first 16 bits. HarfBuzz reads formats 0, 1, 2 and 3 under either.
* Format 0 is searched by binary search, so its pairs must be sorted. Format 2 class values count from the start of the subtable. Subtables always add up: the override and minimum bits are ignored. Cross-stream values shift every later glyph, and outside format 1 nothing resets them.
* The table is used when the font has no `kerx`, GPOS has no `kern` feature in the language system it chose (or isn’t used), and the shaper’s `fallback_position` is true: the default, Arabic, Hebrew and Hangul shapers.
* Since 12.2.0, Thai, Lao, Indic, Khmer, Myanmar and USE text never uses it, because fonts for those scripts kerned the same pairs twice, in `dist` and in `kern`.
* The kern machine passes over marks, needs the `kern` mask on both glyphs, reads pairs left to right, and splits each value between the two glyphs’ advances.
