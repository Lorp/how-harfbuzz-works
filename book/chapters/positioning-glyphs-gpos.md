# GPOS: positioning glyphs

When GPOS starts, the glyphs are settled. GSUB has chosen them, and the positions array has been cleared and filled with each glyph’s advance from the font ([The pipeline, step by step](the-pipeline-step-by-step.html#advances)). GPOS never changes which glyphs there are. It changes four numbers per glyph, the advance and the offset in each direction, and it records which glyph is attached to which, so that the attachments can be worked out once all its lookups have run.

GPOS has the same structure as GSUB, and HarfBuzz runs it with the same machinery, so this chapter covers only what is different: the nine lookup types as HarfBuzz runs them, then the last step, in which a tree of attachments becomes offsets an application can draw with.

The examples come from one test font, `gpos.ttf`, built from `fonts/positioning-glyphs-gpos/gpos.fea`, and three variants of it. It has the GSUB chapter’s `f`, `i` and their ligatures, a few letters to kern, two combining marks, and letters that join in a cursive chain. Its glyphs are boxes. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on those fonts when the page was built.

## What changes from GSUB

A GPOS table has a ScriptList, a FeatureList, a LookupList and optional FeatureVariations, exactly as GSUB does ([The shape of the table](gsub.html#the-shape-of-the-table)). Its lookups have nine types:

| Type | Name | What it does |
|---|---|---|
| 1 | Single adjustment | moves one glyph, or changes its advance |
| 2 | Pair adjustment | the same for two glyphs in sequence: kerning |
| 3 | Cursive attachment | joins a glyph’s exit point to the next glyph’s entry point |
| 4 | Mark-to-base attachment | puts a mark’s anchor on a base glyph’s anchor |
| 5 | Mark-to-ligature attachment | the same, on one component of a ligature |
| 6 | Mark-to-mark attachment | puts a mark on the mark before it |
| 7 | Context | runs other lookups where an input sequence matches |
| 8 | Chained context | the same, also checking the glyphs before and after |
| 9 | Extension | a wrapper allowing 32-bit offsets |

Types 1 to 6 have beyond-64k formats too: SinglePos and PairPos formats 3 and 4, and format 2 of the others.

Each lookup runs through GSUB’s `apply_forward` loop, with its digests, mask test and glyph-property test ([Running one lookup](gsub.html#running-one-lookup)). The second-glyph digest holds a pair subtable’s second glyphs and a mark subtable’s bases, so a mark lookup is skipped for a buffer with none of its bases. Planning puts all of GPOS in **one stage**: no script shaper pauses between GPOS lookups, so they all run in LookupList order ([From features to lookups](from-features-to-lookups.html#stages-and-pauses)).

### One array, in place

GSUB reads from the buffer and writes to a second array ([An input buffer and an output buffer](gsub.html#an-input-buffer-and-an-output-buffer)). GPOS never needs to, since it never adds or removes a glyph. The proxy through which HarfBuzz applies GPOS says so with one constant (`hb-ot-layout.cc:1965`):

```c++
struct GPOSProxy
{
  static constexpr unsigned table_index = 1u;
  static constexpr bool always_inplace = true;
  typedef OT::PosLookup Lookup;
  /* … (trimmed) */
};
```

With `always_inplace`, `apply_string` skips `clear_output` and `sync`, and `next_glyph` just moves `idx` on. Glyphs before `idx` and after it are in the same array, so a lookup that looks backwards, as cursive and mark attachment do, reads the glyphs directly. There are no reverse lookups: `PosLookup::is_reverse` always returns false.

### What a lookup passes over

Lookup flags and GDEF classes work as in GSUB ([Which glyphs a lookup sees](gsub.html#which-glyphs-a-lookup-sees)). Default ignorables are treated differently. The matcher sets its rules from the table it is in (`hb-ot-layout-gsubgpos.hh:844`):

```c++
/* Ignore ZWNJ if we are matching GPOS, or matching GSUB context and asked to. */
ignore_zwnj = c->table_index == 1 || (context_match && c->auto_zwnj);
/* Ignore ZWJ if we are matching context, or asked to. */
ignore_zwj = context_match || c->auto_zwj;
/* Ignore hidden glyphs (like CGJ) during GPOS. */
ignore_hidden = c->table_index == 1;
```

So in GPOS, compared with [the GSUB table](gsub.html#joiners):

| | ZWJ | ZWNJ | Hidden: CGJ, Mongolian FVS1–4, TAG characters | Other default ignorables |
|---|---|---|---|---|
| input | passed over, unless the feature has manual ZWJ | passed over | passed over | passed over |
| context | passed over | passed over | passed over | passed over |

A ZWNJ asks for no *joining*, a matter for GSUB, so it never stops kerning. Hidden characters have been passed over since 10.0.0 ([Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#in-gpos) shows kerning across each). For the default shaper only `mark` and `mkmk` have manual ZWJ (`hb-ot-shape.cc:302`), so a ZWJ between a base and its mark keeps them apart. The per-syllable rule of the syllabic shapers applies only to GSUB.

## Value records

Single and pair adjustments say what to change in a **value record**: up to eight fields, of which only those named in a **ValueFormat** are stored. Four are numbers in font units: `xPlacement` and `yPlacement`, which move the glyph without moving anything after it, and `xAdvance` and `yAdvance`, which change its advance. The other four are offsets to Device tables, one for each of those. To find a record’s length, HarfBuzz counts only the eight defined bits: the specification says every set bit takes two bytes, but a comment (`ValueFormat.hh:61`) cites Microsoft developers saying only the defined fields count.

Single adjustment, type 1, applies one value record to every glyph in its coverage (format 1) or one record per glyph (format 2). The test font’s first lookup moves `a` 40 units right and 100 up:

```views
font: gpos.ttf
lookup: 0
fea: gpos.fea ss01
```

```shape
gpos.ttf  a
gpos.ttf  a  --features=ss01
```

`apply_value` (`ValueFormat.hh:87`) scales each number with `em_scale_x` or `em_scale_y` and adds it, saturating rather than overflowing. Placements apply in either direction of text. `xAdvance` applies only in horizontal text and `yAdvance` only in vertical, negated, because HarfBuzz’s vertical advances grow downwards ([Vertical text](vertical-text.html)).

### Device tables

A Device table is read only if the font has a ppem set or variation coordinates that aren’t all zero (`ValueFormat.hh:123`). Two kinds share the offset. A hinting Device table, formats 1 to 3, gives a correction in pixels for a range of sizes, scaled into the font’s units ([Fonts and font functions](fonts-and-font-functions.html#three-kinds-of-size) shows one). A **VariationIndex** table, format 0x8000, holds an index into GDEF’s item variation store ([Deltas](deltas.html#item-variation-stores)); its delta is scaled, then rounded.

`var-kern.ttf` is the shared variable font `variations/var.ttf` with one kerning pair added. Its value is −20 at the lightest weight, −60 at the default, −150 at the heaviest, and its spec-like view shows the VariationIndex behind it:

```views
font: var-kern.ttf
lookup: 0
```

```shape
var-kern.ttf  HV  --variations=wght=100  --features=-kern
var-kern.ttf  HV  --variations=wght=100
var-kern.ttf  HV  --variations=wght=650  --features=-kern
var-kern.ttf  HV  --variations=wght=650
var-kern.ttf  HV  --variations=wght=900  --features=-kern
var-kern.ttf  HV  --variations=wght=900
```

Halfway between the default and the heaviest weight, the kern is halfway between −60 and −150: H’s 660 becomes 555. A value record’s Device offsets count from its nearest parent table: the subtable, or in glyph-pair kerning the PairSet.

The sanitizer doesn’t follow these offsets when GPOS is loaded. It checks them when they are first used, and treats a bad one as missing ([Some of GPOS](trust-nothing-the-sanitizer.html#some-of-gpos)).

## Pair adjustment

Pair adjustment is how fonts kern. A subtable covers the first glyph of a pair; HarfBuzz finds the second with the skipping iterator, so a lookup with `IgnoreMarks` kerns across marks. The test font’s kerning lookup has both formats:

```views
font: gpos.ttf
lookup: 1
fea: gpos.fea kern
cpp: PairPosFormat1_3
```

Format 1 lists pairs of glyphs. The first glyph’s coverage index chooses a **PairSet**, a list of second glyphs, each with a value record for the first glyph and one for the second, searched by binary search (`PairSet.hh:173`). Format 2 kerns classes: two class definitions, and a matrix with a pair of value records for each pair of classes. Class 0 is every glyph not given a class.

### Glyph pairs first, then classes

The formats differ in when they decline. Format 1 declines when the second glyph isn’t in the pair set, and the next subtable gets a chance. Format 2 has a value for every pair of classes, zero or not, so once its coverage has the first glyph and a second is found, it applies, and no later subtable is tried. That is how kerning exceptions work: `pos V e 0` is a glyph pair, found first, whose zero stops the class pair `[T V] [a e o]` from applying. feaLib always puts the glyph pairs first. `class-first.ttf` is the same font with the two subtables swapped:

```shape
gpos.ttf  To
class-first.ttf  To
gpos.ttf  Ve
class-first.ttf  Ve
```

In `class-first.ttf`, the class subtable claims every pair that starts with `T` or `V`, so `T o` gets the class value, −60, instead of its own −100, and `V e` is kerned though the font says it shouldn’t be.

> For type designers: in a lookup, a class-pair subtable ends the search for every glyph in its coverage, whatever the second glyph is. Exceptions have to come before it.

### The second glyph

If a pair has a value record for the second glyph, its ValueFormat is nonzero, and HarfBuzz moves on past the second glyph after applying the pair (`PairSet.hh:210`). The second glyph has been positioned already, so it can’t start a pair of its own. If the second ValueFormat is zero, the next pair starts at the second glyph. That depends on the format, not on the values. `second-value.ttf` is `gpos.ttf` with its glyph-pair subtable given a second value record, `xAdvance` 0, for every pair:

```shape
gpos.ttf  AVa
second-value.ttf  AVa
```

In `gpos.ttf`, `A V` is kerned by −80 and then `V a` by −60. In `second-value.ttf` the pair `A V` takes the `V` with it, so `V a` is never tried.

### Safe to break

A pair whose values changed something is unsafe to break. A pair whose values are all zero is only unsafe to concatenate (`PairSet.hh:207`: “Even a zero-valued pair record is a concat hazard”). When the second glyph had a value record, the glyph after it is marked unsafe to break too (HarfBuzz issues #3824 and #3888):

```shape
gpos.ttf  To  --show-flags  --unsafe-to-concat
gpos.ttf  Ve  --show-flags  --unsafe-to-concat
second-value.ttf  AVaa  --show-flags
```

`#1` is unsafe to break, `#2` unsafe to concatenate ([Buffers](buffers.html#glyph-flags)). HarfBuzz 4.0.0 split a simple kern between the two glyphs of a pair, “for improved cursor positioning”, its `NEWS` says. The code is still in `PairPosFormat2.hh:280`, behind `HB_SPLIT_KERN`, and off: “Disabled, because causes issues… :-(” (HarfBuzz issue #3408).

Pair adjustment is also cached. Each of a lookup’s first eight subtables gets a small cache of coverage lookups (`hb-ot-layout-gsubgpos.hh:1570`), and either a digest of each pair set’s second glyphs, which rejects most absent pairs without a search, or caches of the two class definitions. `HB_NO_OT_LAYOUT_LOOKUP_CACHE` leaves them out.

## Anchors

The other four positioning types work with **anchors**: points on a glyph, in font units, where something attaches. There are three formats:

* **Format 1**: x and y.
* **Format 2**: x, y and the index of a point in the glyph’s outline. If the font has a ppem and the font funcs can find the point, its position is used instead (`AnchorFormat2.hh:41`). The point differs from x and y only in a hinted outline, and HarfBuzz’s own `hb-ot` funcs don’t implement `get_glyph_contour_point` (`hb-ot-font.cc:991` is commented out), so in practice it is used only with FreeType’s funcs. `HB_NO_HINTING` makes format 2 read as format 1.
* **Format 3**: x and y, with a Device table for each, followed under the same conditions as a value record’s.

Anchors are scaled to floats, and kept as floats until two of them are subtracted: the difference is rounded, not each anchor (`hb-ot-layout-common.hh:6374`). An anchor offset that is null, in a cursive record or in a mark lookup’s matrix, means there is no anchor, and the subtable declines, so the next subtable gets a chance at the glyph (`MarkArray.hh:144`).

## Cursive attachment

A cursive lookup gives each glyph it covers an **entry anchor** and an **exit anchor**, and joins each glyph’s exit to the entry of the glyph after it. In the test font, `n` enters at (50, 0) and exits 100 units higher, at (450, 100), so a run of them climbs:

```views
font: gpos.ttf
lookup: 2
fea: gpos.fea curs
cpp: CursivePosFormat1_2
```

```shape
gpos.ttf  nnnn
```

`CursivePosFormat1::apply` (`CursivePosFormat1.hh:275`) takes the current glyph’s entry anchor and looks back, with the skipping iterator, for the previous glyph’s exit, which must be in the same subtable. `apply_cursive_attachment` then works along the line and across it.

Along the line, it changes advances so the two anchors meet. In left-to-right text, the first glyph’s advance becomes its exit’s x, 450, and the second glyph is moved back by its entry’s x, 50, its advance shortened to match. Each `n` in the middle gets both: moved back 50, with an advance of 450 − 50. Right-to-left text mirrors this, and vertical text does it with y.

Across the line, one glyph has to move so that its anchor is level with the other’s. Which one moves is set by the lookup’s **RightToLeft** flag, the only lookup flag that isn’t about skipping glyphs. HarfBuzz thinks of the moved glyph as a child attached to a parent (`CursivePosFormat1.hh:164`):

```c++
unsigned int child  = i;
unsigned int parent = j;
hb_position_t x_offset = (hb_position_t) roundf (entry_x - exit_x);
hb_position_t y_offset = (hb_position_t) roundf (entry_y - exit_y);
if  (!(c->lookup_props & LookupFlag::RightToLeft))
{
  unsigned int k = child;
  child = parent;
  parent = k;
  x_offset = -x_offset;
  y_offset = -y_offset;
}
```

`i` is the earlier glyph, in logical order. Without the flag the later glyph is the child, so a chain’s first glyph stays on the baseline and each later one hangs from the one before. With it, the *last* glyph stays on the baseline, as a Nastaliq font wants: an Urdu word ends on the baseline and climbs toward its start. Lookup 3 is lookup 2 with the flag set:

```shape
gpos.ttf  ببب  --language=ar
gpos.ttf  ببب  --language=ar  --features=-curs,ss03
gpos.ttf  nnnn  --features=-curs,ss03
```

Read the Arabic from the right. Without the flag the first beh, `beh=0` on the right, is on the baseline. With it the last, on the left, is.

The child stores the offset across the line, and a link to its parent in two fields that GPOS keeps in the spare `var` of each position, set to zero by `position_start` before GPOS starts (`OT/Layout/GPOS/Common.hh:17`):

* **`attach_chain`**: how far away the parent is, in glyphs, negative for one before it;
* **`attach_type`**: `ATTACH_TYPE_CURSIVE` or `ATTACH_TYPE_MARK`.

The offset is relative to the parent; chains are added up at the end of GPOS. When a child that already has a parent gets a new one, from a second cursive lookup, `reverse_cursive_minor_offset` reverses every link of its old chain, so its whole old tree hangs from the new parent. If the new parent was its child, that link is cut (HarfBuzz issue #2469). The join is unsafe to break. Marks may be attached cursively too, since 1.2.0.

## Mark to base

A mark-to-base subtable has two coverages, for marks and for bases. Each mark has a class and an anchor, and each base has one anchor for each class:

```views
font: gpos.ttf
lookup: 4
fea: gpos.fea mark
cpp: MarkBasePosFormat1_2
```

```shape
gpos.ttf  a\u0301
```

### Finding the base

When the current glyph is in the mark coverage, HarfBuzz looks back for the nearest glyph that isn’t a mark, using the skipping iterator’s matcher with its lookup props replaced by `IgnoreMarks` alone: the lookup’s own flags don’t say what counts as a base. Instead of the iterator’s `prev`, which the comment says would be O(n²), it has a loop of its own (`MarkBasePosFormat1.hh:113`), which remembers what it found in two fields of the apply context, **`last_base`** and `last_base_until`. Each mark in a run after one base then searches only the glyphs not yet searched. The cache is reset for each lookup.

The glyph found needn’t be a GDEF base (that check “is too strong; disabled”), only in the base coverage. One kind of non-mark is passed over: the second or later glyph of a multiple substitution, so that a mark after `x` decomposed into `f i` would attach to the `f` (HarfBuzz issue #740). The rule, `accept` (`:75`), stops at a mark inside the sequence (#1020), and since #4124 doesn’t pass over a glyph that is itself in the base coverage.

The loop only stops at a glyph that matches. A glyph that doesn’t, because its mask lacks the lookup’s bit, is passed over like a mark, though `prev` would have stopped there. With `mark` turned off for the `e` alone, the acute after it is attached to the `a` instead:

```shape
gpos.ttf  ae\u0301  --cluster-level=1
gpos.ttf  ae\u0301  --cluster-level=1  --features=mark[1:2]=0
```

(Cluster level 1 keeps the acute in a cluster of its own, so the range covers only the `e`.) The acute is now 750 units back, over the `a`. This looks like a bug: elsewhere the matchers treat a glyph without the lookup’s mask bit as one that doesn’t match, and stop.

### Attaching

Once the base is found and in the coverage, the base’s anchor for the mark’s class is fetched, and `apply_mark_attachment` (`MarkArray.hh:41`) sets the mark’s offset to the base anchor minus the mark anchor. It sets it: whatever offset the mark had from earlier lookups is replaced. The mark then points to its base with `attach_chain` and `ATTACH_TYPE_MARK`. Here the base anchor of `a` is (250, 500) and the acute’s anchor (0, 0), so its offset is (250, 500) for now, and becomes (−250, 500) once the base’s advance is taken off, at the end.

The two directions are treated differently. Across the line, the base’s offset is added now, including all the offsets up its cursive chain (`resolve_cross_offset`, `MarkArray.hh:12`). Along the line, the base’s offset is added only at the end. So a mark follows a base that a later lookup moves along the line, but not one it moves across:

```shape
gpos.ttf  a\u0301  --features=ss01
gpos.ttf  a\u0301  --features=ss02
gpos.ttf  nn\u0301
```

`ss01` (lookup 0) and `ss02` (lookup 7) both move `a` by (40, 100). After `ss01`, which runs before the marks, the acute follows both; after `ss02`, only the 40. The acute on the second `n` follows it up the cursive chain, which was made first. This is from 14.3.0, for compatibility with DirectWrite and Core Text, whose `NEWS` says “marks no longer follow a cross-direction shift that a later lookup applies to the base”.

The attachment makes the base and mark unsafe to break apart. Joiners behave as the table near the start of this chapter says:

```shape
gpos.ttf  a\u200D\u0301
gpos.ttf  a\u200C\u0301
gpos.ttf  a\u034F\u0301
```

The ZWJ stops the attachment: with manual ZWJ it isn’t passed over, so it is the glyph the base search finds, and it isn’t in the base coverage. The ZWNJ and the combining grapheme joiner are passed over.

## Mark to ligature

A mark-to-ligature subtable is the same, except that each ligature has a row of anchors for each of its components. Which row a mark uses comes from GSUB. When `ligate_input` made the ligature, it gave the ligature a ligature ID, and gave each mark it passed over the same ID and the number of the component it followed ([Matching, and the marks in between](gsub.html#matching-and-the-marks-in-between)). The choice is in `MarkLigPosFormat1.hh:156`:

```c++
if (lig_id && lig_id == mark_id && mark_comp > 0)
  comp_index = hb_min (comp_count, _hb_glyph_info_get_lig_comp (&buffer->cur())) - 1;
else
  comp_index = comp_count - 1;
```

A mark with the ligature’s ID goes on its own component. Any other mark, such as one typed after the whole ligature, goes on the last. The GSUB chapter could show this only with HarfBuzz’s fallback positioning, which divides a ligature into equal parts. `gpos.ttf` has the same ligatures, with anchors:

```views
font: gpos.ttf
lookup: 5
fea: gpos.fea mark
cpp: MarkLigPosFormat1_2
```

```shape
gpos.ttf  f\u0301i
gpos.ttf  fi\u0301
gpos.ttf  f\u0301f\u0301i
```

The anchors are where the fallback positioner puts marks, a quarter and three quarters along `f_i`, so the acutes land where the GSUB chapter’s did, −675 and −225; but now they come from the font, and on `f_f_i` they are at 150 and 450, not at thirds. A trace shows each mark’s offset from its component’s anchor, before anything is added up:

```trace
font: gpos.ttf
text: f\u0301i\u0301
from: start lookup 5
to: end lookup 5
```

If the chosen component has no anchor for the mark’s class, the subtable declines. The base search, the cache and the multiple-substitution rule are the same as for mark-to-base.

## Mark to mark

Mark-to-mark attaches a mark to a mark before it, usually to stack accents:

```views
font: gpos.ttf
lookup: 6
fea: gpos.fea mkmk
cpp: MarkMarkPosFormat1_2
```

This search uses the iterator’s `prev`, with the lookup’s flags minus the three Ignore flags (`MarkMarkPosFormat1.hh:87`), so a mark-filtering set or mark attachment class still decides which marks are passed over, and the glyph found must be a mark: a base ends the search. Then the two marks must belong together (`:108`): both with ligature ID 0, on the same base; or on the same component of one ligature; or, if their IDs differ, one must be a ligature of marks, with an ID and component number 0.

```shape
gpos.ttf  a\u0301\u0301
gpos.ttf  f\u0301\u0301i
gpos.ttf  f\u0301i\u0301
```

The first two stack the second acute on the first, 150 units up. In the third, the two acutes end up next to each other after `f_i`, the first belonging to component 1 and the second to component 2. They have the same ligature ID and different component numbers, so `mkmk` leaves them alone, and the acute typed over the `i` stays where mark-to-ligature put it.

## Context, chained context and extension

Types 7 to 9 are the same code as GSUB’s types 5 to 7 ([Context and chained context](gsub.html#context-and-chained-context)). Nested positioning lookups never change the buffer’s length, so the guessing that `apply_lookup` does after a nested GSUB lookup never comes up.

## Resolving attachments

After GPOS, and after the shaper has zeroed the advances of marks ([The pipeline, step by step](the-pipeline-step-by-step.html#gpos-and-what-surrounds-it)), `position_finish_offsets` (`OT/Layout/GPOS/GPOS.hh:164`) turns relative offsets into offsets from each glyph’s own pen position, if an attachment set the buffer’s `HAS_GPOS_ATTACHMENT` scratch flag. For each glyph with an `attach_chain`, `propagate_attachment_offsets` (`:75`) resolves the parent first, recursively, and then:

* for a cursive child, adds the parent’s offset across the line;
* for a mark, adds the base’s offset along the line, and subtracts the advances from the base to the mark: in forward text the base’s and any between; in backward text those after the base up to and including the mark’s own, since the mark will be drawn left of the base.

Each link is cleared as it is resolved, so nothing is added twice. In the trace above the acutes left GPOS at x 225 and 675; taking off the ligature’s 900 gives −675 and −225. The code also handles a mark whose base comes *after* it, which `kerx` can produce ([AAT positioning](aat-positioning.html)). Last comes synthetic slant ([Fonts and font functions](fonts-and-font-functions.html#slant)).

### A limit on the depth

The recursion is bounded by `HB_MAX_NESTING_LEVEL`, 64, and the glyphs are visited in the buffer’s direction: from the start in left-to-right text, from the end in right-to-left (`GPOS.hh:177`). That order came from `kerx`, whose cross-stream kerning links every glyph to its neighbor and was losing a link every 64 glyphs (HarfBuzz issue #5514): visited in order, each parent is resolved before its child, and the recursion stays shallow.

A cursive chain can point the other way. In left-to-right text with the RightToLeft flag, every glyph’s parent comes after it, so resolving the first glyph recurses down the whole chain, and gives up at depth 64. In right-to-left text it is a chain *without* the flag, the usual kind in Arabic, that does this. Here are 67 `n`s with the flag set:

```shape
gpos.ttf  nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn  --features=-curs,ss03
```

Each glyph should be 100 units below the next. Glyphs 64 and 65 are both at −100: the recursion stopped at glyph 64 before adding glyph 65’s offset, so glyphs 0 to 64 are all 100 units too high. Chains that long are rare, but this looks like a bug of the same kind as #5514, left for chains that run against the buffer’s direction.

> For programmers: a message callback that reads positions during GPOS sees attachments still relative to their parents, with the links in `var`, not the offsets the application will get.

## Where to read the source

| File | What’s there |
|---|---|
| `src/OT/Layout/GPOS/*.hh` | one file per subtable type and format, with its `apply`; value records, anchors, and `MarkArray.hh` (`apply_mark_attachment`, `resolve_cross_offset`) |
| `src/OT/Layout/GPOS/CursivePosFormat1.hh` | `apply_cursive_attachment`, the RightToLeft flag, `reverse_cursive_minor_offset` |
| `src/OT/Layout/GPOS/GPOS.hh` | `position_start`, `position_finish_offsets`, `propagate_attachment_offsets` |
| `src/OT/Layout/GPOS/Common.hh` | `attach_chain`, `attach_type` |
| `src/hb-ot-layout-gsubgpos.hh` | what GSUB and GPOS share: the matcher’s GPOS rules, the skipping iterator, the subtable caches, `last_base` |
| `src/hb-ot-layout.cc` | `GPOSProxy`, `apply_string`, `hb_ot_map_t::position` |
| `src/hb-ot-layout-common.hh` | `Device`, `HintingDevice`, `VariationDevice` |
| `src/hb-ot-shape.cc` | where GPOS runs in the pipeline; the `mark`, `mkmk`, `curs` and `kern` features |

## In short

* GPOS works in place, in one stage, with GSUB’s loop, digests and flags.
* In GPOS, ZWNJ and hidden characters are always passed over; ZWJ is too, except by `mark` and `mkmk`.
* Value records are scaled and added; Device tables are read only with a ppem or variation coordinates.
* A class-pair subtable applies to every pair whose first glyph it covers, so kerning exceptions must come before it. A pair with a value for its second glyph moves past it.
* A cursive chain hangs from its first glyph, or from its last with the RightToLeft flag.
* A mark looks back past marks for its base, and on a ligature uses the component GSUB recorded. Across the line its offset is fixed when it attaches; along the line it follows its base.
* Attachments are stored as links and added up after GPOS, in `propagate_attachment_offsets`.
