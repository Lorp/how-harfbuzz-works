# AAT inside HarfBuzz

Apple’s fonts don’t carry GSUB. Their substitutions are in `morx`, the extended glyph metamorphosis table, and its older form `mort`: a list of state machines that walk along the glyphs and change, join, insert or reorder them as they go. OpenType asks the shaping engine to know how a script behaves; `morx` puts that knowledge in the font ([Where the rules live](why-shaping-exists.html#where-the-rules-live) has the history).

HarfBuzz has no separate AAT shaper and no AAT backend. A font with `morx` is shaped by the same `ot` pipeline as any other, and at one step, where GSUB would run, `morx` runs instead. When it does, GSUB doesn’t run at all. This chapter is about that step: when HarfBuzz takes it, how a `morx` table is laid out, how OpenType feature tags reach it, the loop that drives every state machine, and the five kinds of subtable that loop runs. Positioning with `kerx`, `ankr` and `trak` is the next chapter’s subject, [AAT positioning](aat-positioning.html).

The examples come from small test fonts built by `fonts/aat-inside-harfbuzz/build-fonts.py`, whose `morx` tables are written as TTX and compiled by fontTools, and from a few of HarfBuzz’s own test fonts. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on those fonts when the page was built.

## When morx is used

The decision is made once, when the shape plan is made, by `_hb_apply_morx` (`hb-ot-shape.cc:60`):

```c++
return hb_aat_layout_has_substitution (face) &&
       (HB_DIRECTION_IS_HORIZONTAL (props.direction) ||
        !hb_ot_layout_has_substitution (face));
```

`hb_aat_layout_has_substitution` is true if the font has a `morx` or a `mort` table (`hb-aat-layout.cc:278`). So in horizontal text, `morx` wins whenever it is there, whatever else the font has. In vertical text it is used only if there is no GSUB (HarfBuzz issue #2124). If a font has both `morx` and `mort`, only `morx` is read (`hb-aat-layout.cc:299–327`).

That wasn’t always so. HarfBuzz 2.0.0 added AAT shaping, used only when GSUB and GPOS were missing, with an environment variable, `HB_OPTIONS=aat`, to prefer `morx` and `kerx`. Since 2.6.5, “AAT is now always preferred for horizontal scripts when both AAT and OT layout tables exist at the same time” (`NEWS`). The variable is gone: nothing in {{hb}}’s source reads an `aat` option.

`latin-gsub.ttf` has a `morx` that makes f i into f_i, and a GSUB whose `ccmp` makes f l into f_l:

```shape
latin-gsub.ttf  fi fl
latin-gsub.ttf  fi fl  --direction=ttb
```

Horizontally, only `morx`’s ligature is made. Vertically, the font’s GSUB rules out `morx`, and only GSUB’s is.

When the plan uses `morx`, step 13 of [the pipeline](the-pipeline-step-by-step.html#substituting) calls `hb_aat_layout_substitute` (`hb-ot-shape.cc:916`) instead of the GSUB lookups. Four things follow:

* **No GSUB.** Not one GSUB lookup runs, not even `ccmp` or `rvrn`. The OpenType map is still built, from the same features, because GPOS may still use it.
* **The `dumber` shaper.** The planner replaces any script shaper but the default one with `dumber`, which reorders nothing and inserts no dotted circles ([AAT fonts](choosing-a-script-shaper.html#aat-fonts)). The font is expected to do all of that itself.
* **Glyph classes.** If the font has no GDEF classes, they are made from Unicode before `morx` runs, as they would be for GSUB. If it has GDEF, every glyph `morx` writes gets its class from GDEF (`hb-aat-layout-common.hh:202–281`).
* **Deleted glyphs.** Glyphs that `morx` deletes stay in the buffer, marked, until GPOS is about to run, or until after positioning if it isn’t ([step 22](the-pipeline-step-by-step.html#after-positioning)).

Whether GPOS, `kerx` or `kern` then positions the glyphs is decided separately: see [AAT positioning](aat-positioning.html), and [Fallbacks](fallbacks.html) for marks.

## Chains, flags and features

A `morx` table is a version (2 or 3; `mort` is version 1) and a list of **chains**. Each chain holds:

* **default flags**, a 32-bit mask;
* **feature entries**, each a feature type and setting, with an enable mask and a disable mask;
* subtables, each with a coverage field, its type, and its own 32-bit **sub-feature flags**.

The chains are independent. For each, HarfBuzz works out a set of flags, and each subtable in the chain runs if its sub-feature flags share a bit with them. The flags start as the default flags, and each feature entry whose type and setting were asked for changes them: `flags = (flags & disable) | enable` (`Chain::compile_flags`, `hb-aat-layout-morx-table.hh:1138`). The chain of `latin.ttf` has three subtables, with flags 0x1 (a ligature), 0x4 (word-final e) and 0x2 (small capitals), and these default flags and feature entries:

```table
font: latin.ttf
table: morx chain 0 features
```

The default flags, 0x5, turn on the ligature and the final e. Asking for feature type 37 (Lower Case) with setting 1 (Small Caps) adds 0x2; setting 0 takes it away again.

Subtables run in order, chain after chain, each over the whole buffer. The trace names them `chainsubtable` and numbers them through the whole table, not per chain:

```trace
font: latin.ttf
text: ae
from: start table morx
to: end table morx
```

Two subtables don’t run here, for different reasons. Subtable 0 is skipped “because no glyph matches”: no glyph in the buffer can start its machine. Subtable 2, the small capitals, is skipped without a message, because its flag is off.

### Coverage

The top byte of a subtable’s coverage field (`ChainSubtable::Coverage`, `hb-aat-layout-morx-table.hh:1055`) says which text it applies to and in which order it reads the glyphs:

| Bit | Name | Meaning |
|---|---|---|
| 0x80 | `Vertical` | applies only to vertical text; if clear, only to horizontal text |
| 0x40 | `Backwards` | reads the glyphs in the opposite order |
| 0x20 | `AllDirections` | applies to both, and `Vertical` is ignored |
| 0x10 | `Logical` | reads in logical order instead of layout order |

The buffer is in logical order during substitution. HarfBuzz reverses it before a subtable that wants the other order, and back when a later one does, or the chain ends (`:1239`):

| `Logical` | `Backwards` | Order | Buffer reversed when |
|---|---|---|---|
| 0 | 0 | layout order (left to right) | the text is right to left |
| 0 | 1 | reverse layout order | the text is left to right |
| 1 | 0 | logical order | never |
| 1 | 1 | reverse logical order | always |

## From feature tags to feature types

AAT has no feature tags. Its features are numbered **feature types**, each with numbered **selectors** (also called settings): type 1 is Ligatures, whose selector 2 turns common ligatures on and 3 off. A request for `liga` or `smcp` has to be translated.

The translation is a table of 78 entries, `feature_mappings` (`hb-aat-layout.cc:106–186`), “Table data courtesy of Apple”, sorted by tag and searched by `hb_aat_layout_find_feature_mapping` (`:200`). A few of its rows:

| Tag | Feature type | Selector to enable | Selector to disable |
|---|---|---|---|
| `liga` | 1 Ligatures | 2 common ligatures on | 3 common ligatures off |
| `rlig` | 1 Ligatures | 0 required ligatures on | 1 required ligatures off |
| `vert` | 4 Vertical Substitution | 0 on | 1 off |
| `onum` | 21 Number Case | 0 lower case numbers | 2 (none) |
| `ss01` | 35 Stylistic Alternatives | 2 alternative one on | 3 off |
| `calt` | 36 Contextual Alternatives | 0 on | 1 off |
| `smcp` | 37 Lower Case | 1 small caps | 0 default lower case |

Some features are exclusive: one of their selectors is always in force, and there is no “off”. For those, the table sometimes gives a disabling selector that doesn’t exist, like Number Case’s 2, so turning the feature off matches no feature entry and leaves the chain’s default. `aalt` isn’t in the table: `hb_aat_map_builder_t::add_feature` (`hb-aat-map.cc:43`) sends it to type 17, Character Alternatives, with the feature’s value as the selector.

### Only what the application asks for

The OpenType features HarfBuzz turns on by itself, `liga`, `calt`, `ccmp` and the rest, never reach `morx`. The plan’s own AAT map, `plan->aat_map`, is compiled with no features at all (`hb-ot-shape.cc:114`), so it holds the chains’ default flags and nothing else. Only when the application passes features does `hb_aat_layout_substitute` build a map of its own, for that call (`hb-aat-layout.cc:291–298`). A feature turned on selects the mapping’s enabling selector, and one with value 0 its disabling one.

### Only with a feat table

`add_feature` starts with this line (`hb-aat-map.cc:41`):

```c++
if (!face->table.feat->has_data ()) return;
```

and then drops any feature whose type the font’s `feat` table doesn’t list. `feat` names a font’s features for a user interface, and HarfBuzz reads it as the list of features the font accepts. (One exception: a request for small caps is let through if `feat` lists only the deprecated Letter Case type, because `compile_flags` matches a chain’s old Letter Case small-caps entries against the new Lower Case ones; issues #1342 and #2307.) `latin-nofeat.ttf` is `latin.ttf` without its `feat` table:

```shape
latin.ttf  fife  --features=-liga,smcp
latin-nofeat.ttf  fife  --features=-liga,smcp
```

The same chain, the same feature entries, and without `feat` neither request does anything.

> For type designers: a `morx` font whose features should be reachable from OpenType tags needs a `feat` table that lists each feature type. Without one, HarfBuzz shapes it with its default flags, always.

### Ranges

A feature can apply to part of the text, as it can for GSUB (a range in `hb_feature_t`, `smcp[1:2]` in `hb-shape`’s syntax). Since 7.0.0, `hb_aat_map_builder_t::compile` (`hb-aat-map.cc:85`) sorts the features’ starts and ends, and compiles each chain’s flags once for every stretch of text with the same active features, giving each chain a list of flags and the clusters they cover (`mortmorx::compile_flags`, `hb-aat-layout-morx-table.hh:1426`). A budget, `HB_BUDGET_AAT_MAP` (2²⁴), limits the work; when it runs out, the last range compiled is stretched to the end of the text.

While a subtable runs, the driver looks up each glyph’s cluster in that list. Where the subtable’s flag is off, the machine goes back to its start state and the glyph passes untouched:

```shape
latin.ttf  aaa  --features=smcp[1:2]
latin.ttf  fifi  --features=-liga[1:2]
```

In the second line the `i` of cluster 1 is outside the ligature’s flags, so the first f i can’t ligate; the second pair can.

### Asked for twice

When the same feature is asked for twice, the OpenType map lets the later request win ([When a tag is asked for twice](from-features-to-lookups.html#when-a-tag-is-asked-for-twice)). The AAT map does the opposite. `compile` sorts the active features by type, by selector pair, and then by the order they were asked for, and keeps the first request for each feature (`hb-aat-map.cc:139–155`):

```shape
latin.ttf  fifi  --features=-liga,liga
latin.ttf  fifi  --features=liga,-liga
gsub/ligatures.ttf  fi  --features=-liga,liga
```

The same request turns ligatures off in a `morx` font and on in a GSUB font. Nothing in the source says this is intended.

## The state machine

Every `morx` subtable but one is a **state machine**, a finite-state transducer, and HarfBuzz runs them all with one loop. A machine’s `StateTable` (`hb-aat-layout-common.hh:920`) has four parts:

* a **class table**, an AAT lookup table ([Arrays](fonts-as-bytes.html#arrays)) that gives each glyph a class;
* a **state array**, one row per state and one column per class, each cell the index of an entry;
* an **entry table**, each entry a new state, 16 bits of flags, and, for some subtable types, a few more fields;
* `nClasses`, the width of a row.

The first four classes are reserved (`:912`):

| Class | Name | Given to |
|---|---|---|
| 0 | end of text | nothing: it is fed once, after the last glyph |
| 1 | out of bounds | any glyph the class table doesn’t list |
| 2 | deleted glyph | the glyph 0xFFFF, which an earlier subtable deleted |
| 3 | end of line | nothing in HarfBuzz |

Two states are reserved too: 0, start of text, and 1, start of line. HarfBuzz always starts in state 0, and reaches state 1 only if the font’s entries lead there.

### The loop

`StateTableDriver::drive` (`:1282`) is that loop. Trimmed of the range check, a fast path and the safe-to-break bookkeeping, with two of its variables written out, it is:

```c++
int state = STATE_START_OF_TEXT;
for (buffer->idx = 0; buffer->successful;)
{
  unsigned klass = buffer->idx < buffer->len ?
                   machine.get_class (buffer->cur().codepoint, num_glyphs, cache) :
                   CLASS_END_OF_TEXT;
  const Entry &entry = machine.get_entry (state, klass);
  int next_state = machine.new_state (entry.newState);

  c->transition (buffer, this, entry);   /* the subtable's own action */
  state = next_state;

  if (buffer->idx == buffer->len)
    break;

  if (!(entry.flags & DontAdvance) || buffer->max_ops-- <= 0)
    buffer->next_glyph ();
}
```

At each glyph it finds the class and the entry, lets the subtable act, and moves to the new state. When the glyphs run out, it makes one more transition, with class 0, so a machine can finish what it started, and stops.

An entry with the **DontAdvance** flag doesn’t move on: the machine reads the same position again, in its new state. That is how a font runs two rules on one glyph, and how it could loop for ever, so each such transition takes one from the buffer’s operations budget, `max_ops` (4,096 per glyph, at least 65,536; `hb-limits.hh:41–45`), and once that is spent, DontAdvance is ignored. `loop.ttf` has a subtable in which `a`, in state 0, marks itself and goes back to state 0 without advancing, and after it a second subtable that makes every `e` into `e.sc`:

```shape
loop.ttf  ae
```

The loop ends, but the budget is gone. Before each subtable HarfBuzz charges a pass over the buffer (`charge_buffer_pass`, `hb-aat-layout-common.hh:171`), and that fails, so the buffer is marked as failed and the second subtable never runs: the `e` stays an `e`.

The fast path, from 12.3.0, skips runs of glyphs of one class that lead from the start state back to it and do nothing.

### Deleted glyphs are still there

A glyph deleted by a ligature or replaced by 0xFFFF isn’t taken out of the buffer until after `morx` ([Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#the-hidden-ones) explains how it is marked). Later subtables see it, as class 2, and a font has to say what to do with it, usually nothing: stay in the same state. `deva.ttf` does that in every state. `deva-deleted.ttf` is the same font, except that its second and third subtables treat class 2 like any glyph they don’t know, and go back to state 0:

```shape
deva.ttf  \u0915\u094D\u0937\u093F  --language=hi
deva-deleted.ttf  \u0915\u094D\u0937\u093F  --language=hi
```

The first subtable makes `ka virama ssa` into `k_ssa`, followed by two deleted glyphs. In `deva-deleted.ttf` they reset the later machines, so the vowel sign seems to have no consonant: it gets a dotted circle, and moves before that instead of the conjunct. The trace of `deva.ttf` shows the deleted glyphs, as `gid65535`:

```trace
font: deva.ttf
text: \u0915\u094D\u0937\u093F
options: --language=hi
from: start table morx
to: end table morx
```

> For type designers: give class 2, deleted glyph, a “stay where you are” entry in every state of every subtable that comes after one that can delete.

### Before the loop

Each chain has an accelerator, made when it is first used (`hb-aat-layout-morx-table.hh:998`). For each subtable it collects the glyphs whose class, in state 0, leads to another state, an action, or a mark or push (`StateTable::collect_initial_glyphs`, `hb-aat-layout-common.hh:934`), and a subtable is skipped if the buffer holds none of them: the “no glyph matches” of the trace above. `morx` version 3 adds a glyph coverage table per subtable for the same purpose; HarfBuzz checks it and doesn’t otherwise read it. The accelerator also caches glyph classes.

The machine itself is mostly checked as it runs, since the entries and actions it reaches depend on the text ([The AAT tables](trust-nothing-the-sanitizer.html#the-aat-tables)). A table has at most 1,024 subtables (`HB_AAT_MAX_SUBTABLES`, `hb-limits.hh:98`), and one known-broken `morx`, that of AALMAGHRIBI.ttf, is ignored (`hb-aat-layout.cc:215`, issue #4108).

## The five kinds of subtable

A subtable’s type is the low byte of its coverage field: 0 Rearrangement, 1 Contextual, 2 Ligature, 4 Noncontextual, 5 Insertion. Type 3 is unused, and a subtable of an unknown type is skipped (`ChainSubtable::dispatch`, `hb-aat-layout-morx-table.hh:1080`). Each state-machine type has a `driver_context_t` whose `transition` is called by the loop.

### Rearrangement

A **Rearrangement subtable** moves glyphs within a stretch of text. Its entries have three flags: **MarkFirst** marks the current glyph as the first of the stretch, **MarkLast** marks it as the last, and the low four bits are a **verb**, which says what to do with the stretch once both are marked. Each verb moves one or two glyphs from one end to the other, sometimes swapping them as they go (`:106`):

| Verb | Change | Verb | Change |
|---|---|---|---|
| 0 | no change | 8 | AxCD ⇒ CDxA |
| 1 | Ax ⇒ xA | 9 | AxCD ⇒ DCxA |
| 2 | xD ⇒ Dx | 10 | ABxD ⇒ DxAB |
| 3 | AxD ⇒ DxA | 11 | ABxD ⇒ DxBA |
| 4 | ABx ⇒ xAB | 12 | ABxCD ⇒ CDxAB |
| 5 | ABx ⇒ xBA | 13 | ABxCD ⇒ CDxBA |
| 6 | xCD ⇒ CDx | 14 | ABxCD ⇒ DCxAB |
| 7 | xCD ⇒ DCx | 15 | ABxCD ⇒ DCxBA |

`x` is everything in between, of any length, including nothing. HarfBuzz works in place, merges the clusters of the whole stretch, and does nothing if the stretch is longer than 64 glyphs (`HB_MAX_CONTEXT_LENGTH`).

The third subtable of `deva.ttf` marks the first consonant of a cluster as first, and the vowel sign I as last, with verb 2, which moves the last glyph to the front:

```shape
deva.ttf  \u0915\u093F  --language=hi
deva.ttf  \u0915\u094D\u0915\u093F  --language=hi
```

In the second, the stretch is `ka virama ka iMatra`, and the vowel sign moves before all of it. This is the work the Indic shaper does for an OpenType font; for this font, HarfBuzz’s `dumber` shaper does none of it.

### Contextual

A **Contextual subtable** replaces glyphs, one at a time, according to what came before. Its entries have a **SetMark** flag, which remembers the current glyph as the **marked glyph**, and two indices: one says how to replace the marked glyph, the other how to replace the current one. In `morx` each index chooses one of the subtable’s lookup tables, and 0xFFFF means no replacement. In `mort` they are offsets into one shared array of glyphs instead. So a contextual subtable can change a glyph *after* it has seen what follows it, by changing the marked one.

The second subtable of `latin.ttf` marks every `e`. When the glyph after a marked `e` is one it has no class for, such as a space, or when the text ends, it replaces the marked glyph with `e.fina`:

```shape
latin.ttf  fe fee
```

HarfBuzz has one rule here that doesn’t come from Apple’s specification. At the end of text, it makes no replacement at all unless a glyph has been marked: “Looks like CoreText applies neither mark nor current substitution for end-of-text if mark was not explicitly set” (`:252`). A replaced marked glyph is flagged unsafe to break from it to the current position.

### Ligature

A **Ligature subtable** joins glyphs. Its machine pushes glyphs on a stack and pops them when it has seen enough. **SetComponent** pushes the current glyph’s position. **PerformAction**, in `morx` (in `mort`, a non-zero action offset), runs a list of **ligature actions**, each a 32-bit word:

* popping one glyph from the stack;
* adding `component[glyph + offset]` to a running ligature index, where the offset is a signed 30-bit number in the action;
* and, if the action has its Store or Last bit, replacing that glyph with `ligature[index]`.

Last ends the list. When a ligature is stored, it takes the place of the earliest glyph it was made from, and the others popped since are deleted: they become 0xFFFF, and their clusters are merged into the ligature’s (`:561–583`). The ligature itself stays on the stack, so a later action can join it again.

`latin.ttf`’s first subtable has two classes, f and i, and three states:

| State | f | i | anything else |
|---|---|---|---|
| 0, start of text | push, go to 2 | stay | stay |
| 1, start of line | push, go to 2 | stay | stay |
| 2, after f | push, stay | push, act, go to 0 | go to 0 |

The action pops the i and then the f. Both actions’ offsets point at the same entry of `component`, whose value is 0, so the index is 0, and `ligature[0]` is `f_i`:

```shape
latin.ttf  fi
latin.ttf  ffi
```

In `ffi`, both fs and the i are pushed, and the action pops only two. The stack is a ring of 64 positions, so pushing more overwrites the oldest; popping from an empty one clears it and stops the action. An action on the end-of-text transition is ignored, “TODO Work on previous instead?” (`:520`), so a font can’t finish a ligature there.

### Noncontextual

A **Noncontextual subtable** is not a state machine. It is one lookup table, from glyph to glyph, applied to every glyph in the buffer, in place (`:641`). `latin.ttf`’s small capitals are one, and so are the subtables of the `ltag` example below. It obeys feature ranges with its own copy of the driver’s range check.

### Insertion

An **Insertion subtable** adds glyphs. Each entry can insert a list of up to 31 glyphs at the current glyph, at the marked glyph, or both, before or after it, depending on its flags (CurrentInsertBefore, MarkedInsertBefore). The counts are five-bit fields in the flags, and the lists are runs of glyphs in one shared array.

The second subtable of `deva.ttf` inserts a dotted circle before a vowel sign I that follows no consonant:

```shape
deva.ttf  \u093F  --language=hi
deva.ttf  \u0915\u093F \u093F  --language=hi
```

The circle takes the vowel sign’s cluster, and the rearrangement after it then moves the vowel sign in front, as it would for a consonant. With an OpenType font, HarfBuzz would insert the circle itself ([Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html)); with `morx`, only the font does.

After an insertion at the current glyph, HarfBuzz moves past the inserted glyphs, unless the entry has DontAdvance; then the first inserted glyph is the next one read (`:853–868`, issue #1224, reading an ambiguous specification). Apple’s two styles of insertion, “kashida-like” and “split-vowel-like”, are ignored: “TODO We ignore KashidaLike setting” (`:818`). Each inserted glyph costs one of `max_ops`. Insertion at the end of the text was fixed in 14.3.1.

## mort

`mort` is the older form, from QuickDraw GX ([Apple: GX, AAT and ATSUI](why-shaping-exists.html#apple-gx-aat-and-atsui)). HarfBuzz reads it with the same templates, `mortmorx<…, ObsoleteTypes>` instead of `ExtendedTypes` (`hb-aat-layout-common.hh:1195–1269`). The differences are in the sizes and in how things are found:

| | `morx` (`ExtendedTypes`) | `mort` (`ObsoleteTypes`) |
|---|---|---|
| lengths, counts, coverage | 32 bits | 16 bits |
| class table | an AAT lookup table | a first glyph and an array of 8-bit classes |
| cells of the state array | 16-bit entry indices | 8-bit entry indices |
| new state | an index | a byte offset, made into an index |
| contextual replacements | per-entry lookup tables | offsets into one glyph array |
| ligature actions | an index, with a PerformAction flag | an offset in the low 14 bits of the flags |

A state given as an offset can come before the first state: some Apple `kern` tables start that way, and HarfBuzz allows such negative states in `kern` and `mort` alike (`StateTable::sanitize`, `:999`). 15.1.0 fixed those tables, which had been ignored. The `mort` font of the text-rendering tests in HarfBuzz’s test suite has one chain of five subtables, one of each kind:

```trace
font: hb:test/shape/data/text-rendering-tests/fonts/TestAATMort.ttf
text: ABCEFGX
from: start table mort
to: end table mort
```

A B is rearranged into B A, C is replaced by D, E F become `one` and a deleted glyph, G becomes H, and Y is inserted after X.

## feat and ltag

Two small tables complete the picture.

**feat**, the feature name table, lists a font’s feature types, their selectors, whether they are exclusive and which is the default, and `name` IDs for a menu (`hb-aat-layout-feat-table.hh`). Besides being the gate described above, it is what three functions read for applications, since 2.2.0: `hb_aat_layout_get_feature_types`, `hb_aat_layout_feature_type_get_name_id` and `hb_aat_layout_feature_type_get_selector_infos` (`hb-aat-layout.cc:423–482`). The last gives each selector’s name ID and the selectors that enable and disable it: for an exclusive feature, the disabling one is the default; otherwise it is the selector plus one, by Apple’s convention that “on” selectors are even and “off” ones odd. The AAT map relies on that convention when it treats two selectors that differ only in the lowest bit as one feature (`hb-aat-map.cc:149–152`).

**ltag**, the language tag table, is a list of language-tag strings such as `sr` or `zh-Hant` (`hb-aat-ltag-table.hh`). HarfBuzz uses it twice. A `name` record on platform 0 (Unicode) has its language ID looked up in it (`OT/name/name.hh:109`). And in `morx`, a feature entry of type 39, Language Tag, with setting *n*, applies when the buffer’s language matches tag *n* − 1, with or without any feature request, and with or without `feat` (`hb-aat-layout-morx-table.hh:1168`). The match is “rudimentary”, as the source says: the font’s tag, lower-cased, must be the buffer’s language or a prefix of it ending at a hyphen (`ltag::matches_language`, `hb-aat-ltag-table.hh:79`). This test font from HarfBuzz has tags `sr` and `Zh_Hant`, and a Noncontextual subtable for each:

```shape
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=en
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=sr
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=sr-Latn-RS
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=srb
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=zh-hant
hb:test/shape/data/in-house/fonts/882a555639995ed746c7575416acb689ecb9549d.ttf  A  --language=zh
```

`sr-Latn-RS` matches `sr`, but `srb` doesn’t, and `zh` doesn’t match `zh-hant`. Language-specific forms in AAT came in 5.0.0. HarfBuzz uses no other AAT table for substitution: `bsln` and `just` are compiled “just so we compile it; unused otherwise” (`hb-aat-layout.cc:32–34`).

## Clusters and safe breaking

Ligatures merge the clusters of their components, rearrangement those of its whole stretch, and an inserted glyph takes the cluster of the glyph it was inserted at. Deleted glyphs, when they are finally removed, hand their clusters to a neighbor (`hb-buffer.cc:694`).

For safe breaking, `morx` is careless in one way and careful in another. Before it runs anything, `mortmorx::apply` marks the whole buffer unsafe to concatenate (`hb-aat-layout-morx-table.hh:1465`). A GSUB font marks only the glyphs a lookup looked at:

```shape
gsub/ligatures.ttf  la la  --show-flags  --unsafe-to-concat
latin.ttf  la la  --show-flags  --unsafe-to-concat
```

Unsafe to break is worked out glyph by glyph, as precisely as the driver can (issue #2860). Breaking before the current glyph is safe only if this transition has no action, if starting afresh from state 0 here would reach the same state, with the same DontAdvance and no action, and if the current state’s end-of-text entry has no action (`hb-aat-layout-common.hh:1366–1426`):

```shape
latin.ttf  fife fee  --show-flags
latin.ttf  fife fee  --verify
```

The second `e` of `fee` is flagged: breaking before it would leave the first `e` at the end of a text, and make it final. The space is flagged more cautiously than it needs to be, because the `e` before it was replaced on the space’s transition. `--verify` reshapes wherever nothing is flagged, and finds no difference ([Buffers](buffers.html#glyph-flags) explains the flags).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-shape.cc` | `_hb_apply_morx` (`:60`), the swap to `dumber` (`:100`), the plan’s AAT map (`:114`), the call to `hb_aat_layout_substitute` (`:916`) and the removal of deleted glyphs (`:945`, `:954`) |
| `src/hb-aat-layout.cc` | the feature mapping table (`:106`), the `morx` blocklist, `hb_aat_layout_substitute`, the `feat` API, and the apply context’s sanitizer |
| `src/hb-aat-map.cc`, `src/hb-aat-map.hh` | the AAT map builder: features to type and selector, `feat` as a gate, ranges, and the budget |
| `src/hb-aat-layout-morx-table.hh` | the five subtable types and their `transition`s, `ChainSubtable` and its coverage, `Chain::compile_flags` and `Chain::apply`, `mortmorx` and its accelerator |
| `src/hb-aat-layout-common.hh` | the apply context, AAT lookup tables, `StateTable`, the reserved classes and states, `ObsoleteTypes` and `ExtendedTypes`, and `StateTableDriver` |
| `src/hb-aat-layout-feat-table.hh`, `src/hb-aat-ltag-table.hh` | `feat` and `ltag` |
| `test/shape/data/in-house/tests/aat-morx.tests`, `test/shape/data/text-rendering-tests/tests/MORX-*.tests`, `test/shape/data/text-rendering-tests/tests/MORT-1.tests` | HarfBuzz’s `morx` and `mort` tests |

`HB_NO_AAT_SHAPE` leaves `morx`, `mort`, `kerx` and `trak` shaping out of the build; `HB_NO_AAT` does that and also leaves out the `feat` and `ltag` API and `ltag`’s use in `name` (`HB_NO_OT_NAME_LANGUAGE_AAT`). `HB_MINI` sets `HB_NO_AAT`, and `HB_NO_SHAPER` and `HB_NO_OT_SHAPE` set `HB_NO_AAT_SHAPE` (`hb-config.hh:94–171`). `HB_NO_AAT_LAYOUT_BLOCKLIST`, set by `HB_NO_LEGACY`, keeps AALMAGHRIBI.ttf’s `morx`. The feature mapping table is compiled whenever AAT is in, or Core Text is, since the `coretext` backend uses it to pass features to Core Text (`hb-coretext-shape.cc:220`).

## In short

* There is no AAT shaper. In the `ot` pipeline, `morx` (or `mort`, if there is no `morx`) replaces GSUB in horizontal text whenever it is present, and in vertical text when there is no GSUB. GSUB then doesn’t run at all, and the script shaper becomes `dumber`.
* A `morx` table is chains of subtables. Each chain’s flags start from its default flags, and feature entries for the features asked for change them; a subtable runs if its flags share a bit with the chain’s.
* OpenType tags reach `morx` through a fixed mapping to feature types and selectors, only when the application asks for them, and only if the font’s `feat` table lists the type. Of two requests for one feature, the first wins.
* One loop drives every state machine: class, entry, action, new state, and a last transition at the end of text. DontAdvance re-reads a glyph, bounded by the buffer’s operations budget. Deleted glyphs stay in the buffer, as class 2, until after `morx`.
* The five kinds rearrange (16 verbs), replace the marked or current glyph, ligate through a stack, replace glyph for glyph, and insert up to 31 glyphs.
* `ltag` lets feature entries apply by language. A `morx` buffer is wholly unsafe to concatenate, but unsafe to break is set glyph by glyph.
