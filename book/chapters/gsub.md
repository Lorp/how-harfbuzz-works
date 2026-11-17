# Substituting glyphs: GSUB

By the time HarfBuzz opens a font's GSUB table, the hard questions about *characters* have been answered. The text has been segmented, its script and direction are known, it has been normalized, and every character has been mapped to a glyph through `cmap`. What arrives here is a buffer of glyph IDs, each still carrying the cluster number of the character it came from and a set of Unicode properties.

GSUB's job is to change *which* glyphs are in that buffer. It swaps one glyph for another, splits one into several, joins several into one, and does any of those only in certain surroundings. It never moves anything: positions are GPOS's job, in the next chapter. This chapter is about how HarfBuzz reads GSUB and runs it: the order things happen in, which glyphs a lookup can see, and the many small decisions that the OpenType specification leaves open, which HarfBuzz settles in particular ways.

Every example comes from one small test font, built from the feature file `fonts/gsub/ligatures.fea` and two variants of it. Its glyphs are plain boxes, since only their names, their `cmap` and their layout tables matter here. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on those fonts when the page was built.

## The shape of the table

A GSUB table has three lists, plus an optional fourth:

* the **ScriptList**, which says, for each script and language system, which features apply;
* the **FeatureList**, which says, for each feature, which lookups it uses;
* the **LookupList**, which holds the lookups themselves: the actual rules;
* and (in version 1.1) **FeatureVariations**, which swaps in different lookups for a feature in some regions of a variable font's design space.

The first two, together with FeatureVariations, belong to planning. Before shaping starts, HarfBuzz works out from them which lookups this text needs, in what order, and which glyphs each should touch. That is the subject of the chapter on shape plans. This chapter starts where planning ends: with an ordered list of lookups, each tagged with the feature that asked for it, a bit mask, and a few flags.

A **lookup** is a type, a set of flags, and a list of subtables. All of a lookup's subtables have the same type. When a lookup runs, HarfBuzz tries its subtables in order at each glyph, and the first one that does something wins. GSUB has eight lookup types:

| Type | Name | What it does |
|---|---|---|
| 1 | Single | one glyph → one glyph |
| 2 | Multiple | one glyph → a sequence of glyphs |
| 3 | Alternate | one glyph → one of a set of alternatives |
| 4 | Ligature | a sequence of glyphs → one glyph |
| 5 | Context | runs other lookups where an input sequence matches |
| 6 | Chained context | the same, also checking the glyphs before and after |
| 7 | Extension | a wrapper allowing 32-bit offsets to a subtable of another type |
| 8 | Reverse chained single | single substitution in context, run from the end of the text |

Here is the first lookup in the test font, the `liga` lookup. It is the subject of most of this chapter, so it's worth getting to know in each of the views the switch at the top of the page offers:

```views
font: ligatures.ttf
lookup: 0
fea: ligatures.fea liga
cpp: LigatureSubstFormat1_2
```

The **spec-like** view is the book's default. It uses the field names of HarfBuzz's own structs, which follow the OpenType specification nearly field for field. It leaves out what the bytes need but a reader doesn't: counts, which are implied by the lists, and offsets, which are shown by nesting. A ligature set is listed under its first glyph, in brackets, because that glyph is never stored in the ligature itself: it is found through the subtable's coverage table. So `(f)` followed by `[f i] → f_f_i` means "f, then f, then i, becomes f_f_i".

The **feature file** view is the source the font was compiled from. It's how most designers write GSUB, but as we'll see, it hides some things that HarfBuzz depends on. **TTX** is fontTools' XML dump. **Bytes** shows the lookup as it is stored in the font, offset by offset. **HarfBuzz C++** shows the struct that HarfBuzz lays over those bytes, with a link to it in the source.

### Structs over bytes

The C++ view is worth a closer look, because it's how all of HarfBuzz's table code works. `LigatureSubstFormat1_2` is not a class that HarfBuzz fills in by parsing the font. It is a description of the bytes: HarfBuzz points it at the right place in the font's data and reads the fields where they are. `HBUINT16` is a big-endian 16-bit integer that converts itself to a native one when read. An `OffsetTo<Coverage>` is a 16-bit number that knows what it points to, so `this+coverage` gives the Coverage table. There is no copying and no allocation. What makes this safe is the *sanitizer*, which checks every offset and array once, when the table is first loaded, so the code that reads it later can trust it. That's covered in the chapter on reading tables.

The struct is a template on `Types`, which is either `SmallTypes` (16-bit glyph IDs and offsets, the OpenType you know) or `MediumTypes` (24-bit). The second exists for the "beyond 64k" extension to OpenType, which allows fonts with more than 65,535 glyphs and gives GSUB new subtable formats for them: SingleSubst formats 3 and 4, ChainContext formats 4 and 5, and so on. The same code reads both. A build of HarfBuzz with `HB_NO_BEYOND_64K` defined leaves the wider formats out.

The names differ a little between the views. For this lookup:

| OpenType spec | HarfBuzz struct | TTX |
|---|---|---|
| `coverageOffset` | `coverage` | (merged into `LigatureSet glyph=`) |
| `ligatureSetOffsets[]` | `ligatureSet` | `<LigatureSet>` |
| `ligatureGlyph` | `ligGlyph` | `glyph=` |
| `componentCount`, `componentGlyphIDs[]` | `component` (a `HeadlessArray16Of`) | `components=` |

`HeadlessArray16Of` is HarfBuzz's name for an array whose count includes a first element that isn't stored. That's exactly what a ligature's component list is: `componentCount` counts the first glyph too, but only the second and later glyphs follow it. In the code it's read as `component.lenP1`, "length plus one".

## The order lookups run in

Planning hands over the lookups in **stages**, separated by pauses where a script shaper can step in (an Indic shaper, for example, reorders glyphs between stages). Within a stage, HarfBuzz sorts the lookups by their index in the LookupList (`hb-ot-map.cc:389`). It doesn't sort them by feature, and it doesn't keep the order in which the features were asked for.

For the default shaper, which handles Latin, nearly every feature is in the same stage. So `ccmp`, `liga`, `calt` and the rest are not applied one feature after another: their lookups are merged into one list and run in lookup order. The test font's `ccmp` turns `x` into `f i`. It comes after `liga` in the feature file, so its lookup is lookup 4, after `liga`'s lookup 0. The font `ccmp-first.ttf` is the same except that the `ccmp` block comes first in its feature file:

```shape
ligatures.ttf  x
ccmp-first.ttf  x
```

In `ligatures.ttf`, `liga` has already run by the time `ccmp` makes the `f` and the `i`, so they stay apart. Moving the feature block is enough to change the result, because feaLib numbers lookups in the order it meets them. The trace for `ligatures.ttf` shows the order:

```trace
font: ligatures.ttf
text: x
from: start table GSUB
to: end table GSUB
skipped: yes
```

> For type designers: in one stage, the order of lookups in the LookupList is what counts. A lookup whose output another lookup should see must come first in the list, whatever features they belong to. In a feature file, that means writing it first.

The trace also shows HarfBuzz skipping lookups "because no glyph matches". That's the first of several shortcuts, which come next.

## Running one lookup

The loop that runs a lookup over the buffer is short enough to read in full. It's `apply_forward` in `hb-ot-layout.cc`, and here it is with the caching details left out:

```c++
while (buffer->successful)
{
  /* Skip ahead over glyphs this lookup can't touch. */
  unsigned j = buffer->idx;
  while (j < buffer->len &&
         !(accel.digest.may_have (info[j].codepoint) &&
           (info[j].mask & c->lookup_mask) &&
           c->check_glyph_property (&info[j], c->lookup_props)))
    j++;
  buffer->next_glyphs (j - buffer->idx);   /* copy them to the output */
  if (buffer->idx >= buffer->len)
    break;

  /* Try each subtable here; if none applies, move on one glyph. */
  if (!accel.apply (c))
    buffer->next_glyph ();
}
```

Four ideas are packed into it.

### An input buffer and an output buffer

A forward GSUB lookup reads from the buffer's glyphs and writes to a second, *output* array as it goes. `buffer->idx` is the position in the input. `next_glyph()` copies the current glyph to the output unchanged and moves on. A substitution writes its result to the output instead, and moves `idx` past whatever it consumed. At the end, `buffer->sync()` makes the output the new contents of the buffer. This is why a multiple substitution can grow the text without shuffling the whole array along.

It also decides what a lookup can see. Glyphs before `idx` are in the output, so they are *already* processed by this lookup. Glyphs from `idx` on are not processed yet. So a lookup never revisits its own output at the same position, but its output does affect matches further on, when a later rule looks *backwards*. The test font's `calt` lookup changes `e` to `e.init` after a space or after an `e.init`:

```views
font: ligatures.ttf
lookup: 3
fea: ligatures.fea calt
```

```shape
ligatures.ttf   eee
```

Each `e` sees the `e.init` that the same lookup has just written before it, so the change runs all the way along. If the rule had looked ahead instead, at glyphs not yet processed, it would only ever see the original `e`s.

Reverse chained single substitutions (type 8) work the other way. They run from the end of the buffer to the start, in place, with no output buffer, and their rules look ahead at glyphs they have already changed. That direction is the whole reason the type exists: it lets a choice made at the end of a word, as in Nastaliq, depend on the glyphs after it.

### Three filters before any real work

Most lookups don't apply to most glyphs, so HarfBuzz tries hard not to do the work of finding that out. Each lookup has a **set digest**: a tiny summary, three 64-bit masks, of every glyph its subtables' coverage tables contain. It's like a Bloom filter. Asking whether it *may* contain a glyph costs a few bit operations. "No" is always right, while "maybe" can be wrong, which costs only time. The buffer keeps a digest of its glyphs too, updated as substitutions happen. The digests are checked at three levels:

1. Before a lookup runs at all, its digest is compared with the buffer's. If they have nothing in common, the lookup is skipped: "skipped lookup … because no glyph matches".
2. In the loop above, each glyph is checked against the lookup's digest, so glyphs it can't touch are skipped in a tight loop.
3. Each subtable has its own digest, checked before its coverage table is searched.

The digest is fast when a lookup covers a compact range of glyph IDs and useless when it covers glyphs from all over the font, as `hb-set-digest.hh` says. Ligature lookups also get a digest of the glyphs that can come *second* in a ligature, so HarfBuzz can see that an `f` followed by an `o` can't start any ligature without looking at any.

### The mask

Every glyph in the buffer carries a 32-bit **mask**. During planning, each feature gets one or more bits of it, and each glyph's mask has those bits set where the feature is on. A feature applied to the whole text, like `liga`, sets them on every glyph. A feature applied to a range sets them only on the glyphs from those clusters. A lookup runs with its feature's bits as `lookup_mask`, and a glyph whose mask doesn't share any of them isn't touched.

A feature with a value other than 1 gets more than one bit, and the value is stored in them. Alternate substitution reads it to choose which alternative to use: `salt=2` means the second alternate. A value larger than the number of alternates means no substitution at all.

```views
font: ligatures.ttf
lookup: 1
fea: ligatures.fea salt
```

```shape
ligatures.ttf  a
ligatures.ttf  a  --features=salt
ligatures.ttf  a  --features=salt=3
ligatures.ttf  a  --features=salt=4
```

The `rand` feature takes this one step further. HarfBuzz turns it on with the largest possible value, which Alternate substitution reads as "choose at random". It picks using a simple pseudo-random generator, `minstd_rand`, whose state is kept in the buffer and starts at 1, so the same text shaped the same way gives the same "random" result. Applications can set the state with `hb_buffer_set_random_state`. Each choice moves the state on, so a later choice depends on every earlier one, and HarfBuzz marks the whole buffer unsafe to break: no part of it can be reshaped on its own and be sure of coming out the same. (The test font has no `rand` lookup.)

### Glyph properties

Last, `check_glyph_property` asks whether the glyph is one this lookup ignores. That depends on the lookup's flags and on the glyph's class, and it's the subject of the next section.

## Which glyphs a lookup sees

A ligature lookup for `f i` would be fairly useless if an accent between the two letters stopped it working. OpenType's answer is the **lookup flag**. A lookup can ignore base glyphs, ligatures or marks, ignore all marks except one attachment class, or ignore all marks except those in one mark-filtering set. Whether a glyph is a base, a ligature or a mark comes from its class in the GDEF table.

HarfBuzz reads those classes into each glyph's *glyph properties* (`glyph_props`) just before GSUB starts, in `_hb_ot_layout_set_glyph_props`. A font with no GDEF classes gets classes worked out from Unicode instead (`hb_synthesize_glyph_classes`): non-spacing marks are marks, and everything else is a base, with one exception. Default-ignorable characters, such as the combining grapheme joiner and the Mongolian variation selectors, are never classed as marks, even though they are non-spacing. A comment in the source explains that some Mongolian fonts without GDEF rely on this.

When a substitution puts in a new glyph, HarfBuzz looks up that glyph's GDEF class, and also records how it got there: the property bits `SUBSTITUTED`, `LIGATED` and `MULTIPLIED` stay with the glyph from then on. The Indic and USE shapers use them: if a consonant has been ligated, for example, the Indic shaper stops treating it as a plain consonant (`hb-ot-shaper-indic.cc:56`).

### Skipping, step by step

When a lookup matches a sequence, the second glyph onwards is found by a **skipping iterator**, `skipping_iterator_t` in `hb-ot-layout-gsubgpos.hh`. For each glyph it comes to, it asks two questions, and the answers have three values each, not two.

*May this glyph be skipped?* `SKIP_YES` if the lookup flags say to ignore it. `SKIP_MAYBE` if it's a default-ignorable character that this lookup is allowed to pass over (more on which in a moment). `SKIP_NO` otherwise.

*Does it match?* If the rule names glyphs, they're compared: `MATCH_YES` or `MATCH_NO`. If it doesn't (some fast paths just want "the next glyph"), it's `MATCH_MAYBE`. A glyph whose mask lacks the lookup's bits, or one in a different syllable when the lookup works per syllable, is always `MATCH_NO`.

The answers are then combined like this:

| | skip: YES | skip: MAYBE | skip: NO |
|---|---|---|---|
| **match: YES** | skip | match | match |
| **match: MAYBE** | skip | skip | match |
| **match: NO** | skip | skip | fail |

The middle column is the subtle one. A joiner is passed over, unless the rule actually asks for it, in which case it matches. So a font can have a rule that deliberately uses a zero-width joiner, and still have its other rules work across one.

### Joiners

Which default ignorables can be passed over depends on whether the glyph is part of the input or of the context, and on two flags a feature can be given during planning, "manual ZWJ" and "manual ZWNJ" (`F_MANUAL_ZWJ` and `F_MANUAL_ZWNJ` in `hb-ot-map.hh`). In GSUB:

| | ZWJ | ZWNJ | Hidden: CGJ, Mongolian FVS1–4, TAG characters | Other default ignorables |
|---|---|---|---|---|
| input | passed over, unless the feature has manual ZWJ | blocks | block | passed over |
| context | passed over | passed over, unless the feature has manual ZWNJ | block | passed over |

So, in the default case, a zero-width joiner doesn't stop a ligature, and a zero-width non-joiner does. That's what they are for: ZWNJ asks for *no* joining. The "hidden" characters are default ignorables too, but they're there to change the shaping, so GSUB never looks past them. The combining grapheme joiner, for example, is how a writer stops two marks from being reordered or combined (HarfBuzz issue #554). GPOS has rules of its own, covered in the next chapter.

```shape
ligatures.ttf  fi
ligatures.ttf  f‍i
ligatures.ttf  f‌i
```

The joiners are still in the output. They have no glyph in this font, and late in shaping HarfBuzz replaces default ignorables with an invisible glyph of zero width, here the space glyph. The ZWJ comes after the ligature, in the same cluster. Where glyphs that a ligature passed over end up is the next subject.

The flags come from planning. For the default shaper, only `mark` and `mkmk` have them. The Arabic shaper gives manual ZWJ to nearly all its features, so that a ZWJ there really does block a ligature, and the Indic shaper gives both flags to its basic forms features (`nukt`, `akhn`, `rphf` and the rest). One further rule only applies to GSUB: in scripts whose shaper splits text into syllables, a lookup can be limited to one syllable at a time, so that no rule can match across a syllable boundary. The matcher checks for that too.

## The lookup types, as HarfBuzz runs them

### Single substitution

The simplest type. Format 1 stores a single number, `deltaGlyphID`, which is added to the glyph ID of every glyph in its coverage. Format 2 stores a list of output glyphs, one for each covered glyph.

```views
font: ligatures.ttf
lookup: 2
fea: ligatures.fea INIT
cpp: SingleSubstFormat1_3
```

feaLib chose format 1 here because `e.init` happens to be 13 glyphs after `e`. HarfBuzz does the addition modulo 2<sup>16</sup> (2<sup>24</sup> for the wide format 3), with `(glyph_id + delta) & mask`. So a negative delta, or a sum past the end of the range, wraps around. That's what the specification says, but not every implementation has always done it.

### Multiple substitution

One glyph becomes several. In the test font, `ccmp` turns `x` into `f i`:

```views
font: ligatures.ttf
lookup: 4
fea: ligatures.fea ccmp
```

```shape
ligatures.ttf  x
```

Both output glyphs keep the cluster of the input, 0. Each is marked as a component of the original, with `MULTIPLIED` and a component number, so that later lookups and GPOS can tell they came from one character. If the font has no GDEF classes to say what the new glyphs are, and the input glyph was a ligature, they are classed as bases.

Two cases are special. A sequence of just one glyph is treated as a single substitution, in place, and the glyph isn't marked as multiplied. A sequence of *no* glyphs deletes the glyph. The specification doesn't allow that, but Uniscribe does, and fonts rely on it, so HarfBuzz follows Uniscribe (HarfBuzz issue #253).

### Alternate substitution

Covered above, under "The mask": the feature's value picks the alternate, and `rand` picks one at random.

### Ligature substitution

Ligatures are where most of GSUB's subtleties are, and HarfBuzz's source says so: the comment above `match_input` calls ligating "perhaps the trickiest part of OpenType".

#### First match wins

A subtable's coverage finds the ligature set for the first glyph. HarfBuzz then tries the ligatures in the set *in the order they are stored*, and the first that matches is used. The specification says ligatures should be ordered by preference, but HarfBuzz does no sorting of its own. If `f f` came before `f f i`, then `ffi` would become `f_f` followed by `i`.

You can't write that font in a feature file. feaLib sorts each set longest first whatever order the rules are written in: the feature file above has `sub f i` first and `sub f f i` second, and the compiled lookup has them the other way round. The font `shortest-first.ttf` was built by reversing the sets after compiling:

```views
font: shortest-first.ttf
lookup: 0
```

```shape
ligatures.ttf  ffi
shortest-first.ttf  ffi
```

> For type designers: the feature file view hides the order HarfBuzz uses. If a font's ligatures come from somewhere other than feaLib or a tool like it, look at the order in TTX or in the spec-like view.

#### The second-glyph fast path

Since most ligature sets hold several ligatures and most attempts fail, `LigatureSet::apply` first finds the glyph after the current one, with skipping, and only tries ligatures whose second component is that glyph. If the next glyph might be skipped (a joiner, say), it falls back to trying every ligature in order. This is purely a speed-up, but it's why the code has two loops where one would seem enough.

#### Matching, and the marks in between

`Ligature::apply` calls `match_input`, which finds each remaining component with the skipping iterator and records where it found it. In the test font, the `liga` lookup has the flag `IgnoreMarks`, so a combining acute between `f` and `i` is passed over:

```trace
font: ligatures.ttf
text: f́i
from: start lookup 0
to: end lookup 0
```

The trace says "ligating glyphs at 0,2": the components were found at positions 0 and 2, with the mark at 1 passed over. `ligate_input` then does three things:

1. It merges the clusters of everything from the first component to the last, so the ligature, and the mark inside it, all belong to cluster 0.
2. It writes the ligature glyph in place of the first component and removes the others. The glyphs that were passed over aren't removed: they are kept, in order, *after* the ligature.
3. It gives the ligature a new **ligature ID**, and records its number of components. Each passed-over mark gets the same ligature ID and the number of the component it followed.

That last step is what lets a mark find the right part of a ligature later on. GPOS's mark-to-ligature attachment uses it to choose which of the ligature's anchors to use. This font has no GPOS, so HarfBuzz positions the mark with its *fallback* positioner, which divides the ligature into equal parts, one for each component. Even so, the effect shows:

```shape
ligatures.ttf  f́i
ligatures.ttf  fí
ligatures.ttf  f́f́i
```

The same ligature glyph, with the same accent, but the accent sits over a different part of it: −675 when it was typed after the `f`, −225 when it was typed after the `i`. That's half the ligature's 900-unit width apart. With three components, the two accents are a third of the width apart.

#### Edge cases the code handles

The comments in `match_input` and `ligate_input` are a list of real fonts that broke, and each is a rule HarfBuzz now follows:

* **Marks belong to one ligature.** Glyphs attached to *different* components of an earlier ligature can't be ligated together. With LAM, SHADDA, LAM, FATHA, HEH, where LAM-LAM-HEH has already formed a ligature, the SHADDA and FATHA are left belonging to different components of it, and mustn't then form a ligature of their own. There are two exceptions: a ligature formed with marks that belong to it, which Indic fonts need, and marks whose base ligature this lookup ignores anyway (HarfBuzz issue #545).
* **A base and its marks make a base.** If a base glyph and marks ligate, the result is treated as a base, not a ligature, so later marks can still attach to it (issue #1109).
* **Marks make a mark.** If every component is a mark, the result is a mark ligature. It keeps the ligature ID it had, so it can still attach to the ligature it sat on.
* **Ligatures of ligatures.** When a ligature is formed from components that are themselves ligatures with marks attached, the marks have to be renumbered to the right component of the new, larger ligature, including marks that come after the end of the matched sequence. `ligate_input` loops forward to find them.
* **A ligature of one.** A ligature with one component is a single substitution, done in place, and isn't marked as ligated.

A ligature formed from a non-spacing mark has its Unicode general category changed to "other letter", so that later steps stop treating it as a mark.

### Context and chained context

Types 5 and 6 don't substitute anything themselves. They match a pattern and then run other lookups, the *nested* lookups, at chosen positions inside it. Type 5 matches only an input sequence. Type 6 matches a backtrack sequence before it and a lookahead sequence after it as well. Each has three formats: rules listed per first glyph (format 1), rules written in glyph classes (format 2), and one rule written as a coverage table per position (format 3). The beyond-64k formats 4 and 5 are 1 and 2 with wider glyph IDs. feaLib wrote the test font's `calt` rule as a format 3 subtable:

```views
font: ligatures.ttf
lookup: 3
fea: ligatures.fea calt
```

Matching uses the same skipping iterator as ligatures, with two differences for the backtrack and lookahead. Their glyphs need not have the lookup's mask bits, because a context isn't part of what's being changed. And ZWJ is always passed over there. As shown earlier, the backtrack is matched against the *output* buffer, so it sees glyphs this lookup has already changed.

Once a rule matches, `apply_lookup` runs each nested lookup in turn, at the position its `lookupRecord` gives:

```trace
font: ligatures.ttf
text:  e
from: start lookup 3
to: end lookup 3
```

A nested lookup may change the length of the buffer, by ligating or multiplying, and `apply_lookup` then has to work out where the later positions in the pattern have moved to. It assumes that new glyphs were added straight after the current position, and that removed ones were the positions after it. A long comment in the source explains that this guess is not always right (HarfBuzz discussion #3538) and how it could be improved.

Nesting is limited. A lookup can nest 64 deep at most (`HB_MAX_NESTING_LEVEL`). A pattern can be at most 64 glyphs long (`HB_MAX_CONTEXT_LENGTH`). And the buffer has a budget of operations (`max_ops`): 4,096 for each glyph, and at least 65,536. A font built to make shaping run for ever just stops when it runs out. These limits are in `hb-limits.hh`.

### Extension

An Extension subtable holds a 32-bit offset to a subtable of another type. It exists only because 16-bit offsets can't reach far enough in large fonts. HarfBuzz follows the offset and carries on as if the subtable were there. Nothing else in this chapter changes for extension lookups.

## Clusters and safe breaking

Each substitution that combines glyphs merges their clusters, so every glyph keeps pointing at the text it came from. HarfBuzz also flags places where the text can't be cut and reshaped in parts without changing the result: `unsafe_to_break`, and the weaker `unsafe_to_concat`. Matching records these even when it fails. A ligature that *almost* matched marks its glyphs as unsafe to join, because different text there might complete it. That's why the second-glyph fast path takes care to flag what it looked at. The chapter on clusters explains what applications do with these flags.

## Where to read the source

| File | What's there |
|---|---|
| `src/OT/Layout/GSUB/*.hh` | one file per subtable type and format: the structs, and their `apply` |
| `src/hb-ot-layout-gsubgpos.hh` | what GSUB and GPOS share: the apply context, the skipping iterator, `match_input`, `ligate_input`, contexts, `apply_lookup`, the lookup accelerator |
| `src/hb-ot-layout.cc` | `apply_forward`, `apply_backward`, `apply_string`, and `hb_ot_map_t::apply`, which runs a plan's lookups stage by stage |
| `src/hb-ot-map.cc` | turning features into the sorted, staged list of lookups |
| `src/hb-set-digest.hh` | the set digests |
| `src/hb-limits.hh` | nesting, length and operation limits |

To watch any of this happen, run `hb-shape` with `--trace`. For the more detailed messages shown on this page ("ligating glyphs at 0,2"), HarfBuzz has to be built with `HB_BUFFER_MESSAGE_MORE` defined, as this book's `tools/build-harfbuzz.sh` does.

## In short

* Within a stage, lookups run in LookupList order, not feature order.
* A forward lookup reads the input and writes the output. Its backtrack sees what it has already written, and its lookahead sees what it hasn't reached yet.
* Lookup flags and GDEF classes decide what is passed over. Joiners have their own rules: in GSUB input, ZWJ is passed over and ZWNJ blocks.
* Ligatures are tried in the order they're stored, and the first match wins. Marks that a ligature passed over stay after it, and remember which component they belong to.
* Glyph deletion by an empty multiple substitution is allowed, because Uniscribe allows it.
