# Subsetting

A web page that uses a font for one heading doesn’t need the font’s two thousand other glyphs. A **subsetter** takes a font and a description of what to keep, usually a set of characters, and writes a new, smaller font that still does for those characters what the original did: maps them to glyphs, substitutes and positions those glyphs, draws them.

HarfBuzz’s subsetter is a separate library, `harfbuzz-subset`, with its own header, `hb-subset.h`. It was declared stable in 3.0.0, whose NEWS credits Garret Rieger and Qunxin Liu of Google Fonts and earlier work by Michiharu Ariza of Adobe. It reads fonts with the table structs shaping uses, through one more dispatch context, `subset` ([Fonts as bytes](fonts-as-bytes.html#dispatch-contexts)), and writes them with the serializer and repacker of [the next chapter](writing-tables.html).

It works in two phases. First it makes a **plan**: everything that can be decided before a byte is written, above all which glyphs to keep. Then it executes the plan, table by table. The heart of the plan is the glyph closure: a fixed sequence of stages, each run once, with a bounded loop only inside GSUB. That is usually enough, and this chapter shows where it isn’t.

The examples use small fonts made by `fonts/subsetting/build-subsetting-fonts.py`, and subsets of them cut by HarfBuzz’s own [`hb-subset` tool](command-line-tools.html#hb-subset) in `fonts/subsetting/build.sh` when the fonts are built. Every block on this page reads them with `hb-info` and `hb-shape` from HarfBuzz {{hb}}. Each subset was made with `--glyph-names`, so that glyph names survive: by default they don’t.

## Four calls

The simplest use is four calls (hand-written, not from a test):

```c
hb_subset_input_t *input = hb_subset_input_create_or_fail ();
hb_set_add_range (hb_subset_input_unicode_set (input), 'a', 'z');
hb_subset_input_set_flags (input, HB_SUBSET_FLAGS_NO_HINTING);
hb_face_t *subset = hb_subset_or_fail (face, input);
```

`hb_subset_or_fail` returns a new [face builder](blobs-faces-and-lazy-tables.html), or `NULL`; `hb_face_reference_blob` turns it into the bytes of a font file. The work can also be split in two, `hb_subset_plan_create_or_fail` and `hb_subset_plan_execute_or_fail` (4.0.0), so that a program can ask the plan in between which glyph IDs the new font will use (`hb_subset_plan_old_to_new_glyph_mapping` and two siblings). The `hb-subset` tool takes the same input as options.

## The input

An `hb_subset_input_t` is eight sets and a word of flags. Each set is an `hb_set_t` the caller edits in place, reached through `hb_subset_input_set` (`hb-subset.h`). The defaults are set in the constructor (`hb-subset-input.cc:33`):

| Set | What it holds | Default |
|---|---|---|
| `UNICODE` | the characters to keep | empty |
| `GLYPH_INDEX` | glyph IDs to keep as well | empty |
| `DROP_TABLE_TAG` | tables to leave out | `morx`, `mort`, `kerx`, `kern`, `JSTF`, `DSIG`, `EBDT`, `EBLC`, `EBSC`, `SVG `, `PCLT`, `LTSH`, and the Graphite tables |
| `NO_SUBSET_TABLE_TAG` | tables to copy unchanged | `gasp`, `fpgm`, `prep`, `VDMX`, `DSIG` |
| `NAME_ID` | `name` records to keep | IDs 0 to 6 |
| `NAME_LANG_ID` | their languages | 0x409 (English, United States) |
| `LAYOUT_FEATURE_TAG` | GSUB and GPOS features to keep | about eighty: see below |
| `LAYOUT_SCRIPT_TAG` | scripts to keep | all (an inverted, empty set) |

A table in both lists, like `DSIG`, is dropped: dropping is checked first.

The default features are a list “copied from `_layout_features_groups` in fonttools” (`hb-subset-input.cc:81`): the features HarfBuzz’s shapers turn on by themselves (`ccmp`, `locl`, `liga`, `kern`, `mark`, the script features), the direction, vertical, and fraction features, `rand`, `jalt`, the East Asian spacing features (`palt` since 14.2.1), and HarfBuzz’s private `Harf`/`HARF`/`Buzz`/`BUZZ`. Features a user must switch on are left out: `smcp`, `onum`, `dlig`, stylistic sets, character variants, `ssty`, and the other math features. A subset made with the defaults shapes like the original *with default features*.

`hb_subset_input_keep_everything` (7.0.0) makes six of the sets hold everything, empties the drop list, and sets five flags.

The flags (`hb_subset_flags_t`) are booleans, all off by default:

| Flag | Effect |
|---|---|
| `NO_HINTING` | drop the hinting tables (`fpgm`, `prep`, `cvt `, `cvar`, `hdmx`, `VDMX`), glyf instructions, CFF hints, and GPOS device tables; ignored for fonts that need their hinting (see below) |
| `RETAIN_GIDS` | keep every glyph at its old glyph ID; set by the plan itself when a kept table can’t be renumbered (see below) |
| `DESUBROUTINIZE` | inline CFF and CFF2 subroutines |
| `NAME_LEGACY` | keep non-Unicode `name` records |
| `SET_OVERLAPS_FLAG` | mark every simple glyf glyph as overlapping |
| `PASSTHROUGH_UNRECOGNIZED` | copy tables the subsetter doesn’t know, instead of dropping them |
| `NOTDEF_OUTLINE` | keep the outline of `.notdef` (otherwise it is emptied, in glyf, CFF, and CFF2 alike) |
| `GLYPH_NAMES` | keep `post` glyph names |
| `NO_PRUNE_UNICODE_RANGES` | leave the `OS/2` Unicode range bits alone |
| `NO_LAYOUT_CLOSURE` (7.2.0) | don’t add glyphs that GSUB can produce |
| `OPTIMIZE_IUP_DELTAS` (8.5.0) | re-optimize `gvar` deltas |
| `NO_BIDI_CLOSURE` (11.1.0) | don’t add the mirrors of the requested characters |
| `DOWNGRADE_CFF2` (13.0.0), `CFF_IDENTITY_CHARSET` (14.3.0) | CFF conversions |

Two more need `HB_EXPERIMENTAL_API` (`hb-subset.h:89`): `IFTB_REQUIREMENTS` forces long outline offsets, for incremental font transfer, and `RETAIN_NUM_GLYPHS` keeps the glyph count with `RETAIN_GIDS`. `hb_subset_input_set_flags` replaces the whole word, so setting one flag clears the others.

Three things in the input aren’t sets. The axis settings, from `hb_subset_input_pin_axis_location` and its relatives, turn subsetting into instancing; they are inputs to the plan here, and [Instancing](instancing.html) is about what they do. A glyph map (`hb_subset_input_old_to_new_glyph_mapping`, 7.3.0) asks for particular new glyph IDs. And with the experimental API, `hb_subset_input_override_name_table` replaces, adds, or removes a `name` record.

## The plan

The plan is built by the constructor of `hb_subset_plan_t` (`hb-subset-plan.cc:773`); any failure clears its `successful` flag, and `hb_subset_plan_create_or_fail` then returns `NULL`. It copies the input, and since 15.2.0 it corrects two of the flags first. It clears `NO_HINTING` for a font that needs its hinting to render correctly (`hb-subset-plan.cc:779`): a glyf font whose family name, or the checksums of its `cvt `, `fpgm`, and `prep`, are on a list of legacy CJK fonts, such as MingLiU and DFKai-SB, taken from FreeType, which loads these fonts only with their hinting (`hb-subset-hinting.hh`, from FreeType’s `ttobjs.c`). And it sets `RETAIN_GIDS` when a table that refers to glyphs but can’t be subset is going to be kept (`:795`): `EBDT`, `EBLC`, `JSTF`, `LTSH`, `SVG `, the AAT layout tables, Apple’s bitmap and other glyph tables, or the Graphite tables, kept because the caller passes them through (the list is `unsubsettable_glyph_tables`, `:713`). Such a table is copied as it is, so its glyph IDs must still be right. Then the constructor creates an empty face builder for the output, and refuses to pass a `VARC` table through unchanged while glyph IDs change or axes are instanced. It normalizes the axis settings, then works out the characters to keep (`_populate_unicodes_to_retain`), the glyphs to keep (`_populate_gids_to_retain`), and their new IDs (`_create_old_gid_to_new_gid_map`). Last, it collects what particular tables will need, such as the GDEF mark glyph sets still in use and, when instancing, new metrics. The result is sixty-six members (`hb-subset-plan-member-list.hh`): glyph maps and sets, the lookups and features kept and their new indices, COLR layers and palettes, `name` IDs, axis locations, a cache of sanitized source tables. Each table’s `subset` reads what it needs from there.

## Characters first

`_populate_unicodes_to_retain` (`hb-subset-plan.cc:248`) maps the requested characters to glyphs through `cmap`, and drops any the font doesn’t have. Before that, `_unicode_closure` adds to them. Since 11.1.0 it adds the **bidi closure**: the mirror of each character, from the Unicode Bidi_Mirroring_Glyph property, so that ( brings ) with it. Shaping right-to-left text replaces a character with its mirror when the font has one ([The pipeline, step by step](pipeline-step-by-step.html#mirroring)), so a subset without the mirror would draw an unmirrored glyph. `paren.ttf` was cut from the demo font with the text `(`, and `paren-nobidi.ttf` the same way with `--no-bidi-closure`:

```shape
demo.ttf  (  --direction=rtl
paren.ttf  (  --direction=rtl
paren-nobidi.ttf  (  --direction=rtl
```

Requested glyph IDs go in too, with every `cmap` entry that maps to one of them. That is all the character closure does. Its own comment says what it doesn’t:

```c++
// TODO: we may want to also consider pulling in reachable unicode composition and decompositions.
//       see: https://github.com/harfbuzz/harfbuzz/issues/2283
```

[Normalization](normalization.html) decomposes a character the font has no glyph for, and composes a sequence when the font has a glyph for the whole. The subsetter does neither. The demo font has no glyph for Á, so shaping decomposes it into A and a combining acute, which the font does have. A subset cut for the text Á keeps neither, since neither is the glyph of Á:

```info
aacute.ttf  --list-glyphs
```

```shape
demo.ttf  \u00C1
aacute.ttf  \u00C1
```

The other direction changes the result too. The font has a precomposed é, and shaping composes e followed by U+0301 into it. A subset cut for those two characters keeps `e` and `acutecomb`, but not `eacute`, which is the glyph of another character. Its GPOS still puts the accent on the e, so the result looks much the same here; but it isn’t the glyph the designer drew:

```shape
demo.ttf  e\u0301
e-acute.ttf  e\u0301
```

The user manual says that `hb-subset` makes a font “that covers the input text exactly like the input font does” (`docs/usermanual-utilities.xml:152`). It covers the input *characters*. Text that arrives in another normalization form can come out differently.

> For type designers and web developers: when subsetting for text you don’t control, list both forms of every accented letter, or ask for the base letters and combining marks as well. Nothing in the subsetter will add them for you.

## The glyph closure, stage by stage

The **glyph closure** is the set of glyphs the subset must contain for the requested characters to work: their own glyphs, and every glyph that can come from them. `_populate_gids_to_retain` (`hb-subset-plan.cc:453`) builds it in stages. Here it is, trimmed to its structure:

```c++
plan->_glyphset_gsub.add (0); // Not-def
_cmap_closure (plan->source, &plan->unicodes, &plan->_glyphset_gsub);

if (!drop_tables->has (HB_OT_TAG_MATH))
  _math_closure (plan, &plan->_glyphset_gsub);

layout_populate_gids_to_retain (plan, drop_tables);   /* GSUB, then GPOS */

/* GSUB outputs can have MATH metrics and variants of their own. */
plan->_glyphset_mathed = plan->_glyphset_gsub;
if (!drop_tables->has (HB_OT_TAG_MATH))
  _math_closure (plan, &plan->_glyphset_mathed);

hb_set_t cur_glyphset = plan->_glyphset_mathed;
if (!drop_tables->has (HB_OT_TAG_COLR))
  _colr_closure (plan, &cur_glyphset);
plan->_glyphset_colred = cur_glyphset;

if (!drop_tables->has (OT::VARC::tableTag))
  plan->source->table.VARC->closure_glyphs (&cur_glyphset);
plan->_glyphset_varced = cur_glyphset;

_nameid_closure (plan, drop_tables);
for (hb_codepoint_t gid : cur_glyphset)        /* glyf composites */
  _glyf_add_gid_and_children (glyf, gid, &plan->_glyphset, ...);
for (hb_codepoint_t gid : cur_glyphset)        /* CFF seac accents */
  _add_cff_seac_components (*cff, gid, &plan->_glyphset);
```

Each stage reads the set the stages before it built and adds to it. Only MATH runs twice, before and after GSUB; the others run once. A stage is skipped when its table is being dropped (5.3.0 fixed glyphs being added from dropped MATH and COLR tables). After the layout stage and the stages after it, the set is copied into a member of the plan, a snapshot, and the snapshots are the key to the design:

| Stage | Adds | Snapshot | Read later by |
|---|---|---|---|
| `.notdef`, `cmap` | glyph 0, the characters’ glyphs (found earlier), and `cmap` format 14 variation glyphs | | |
| MATH | size variants and assembly parts of those glyphs | | |
| layout | glyphs GSUB can produce | `_glyphset_gsub` | GSUB, GPOS, GDEF, MATH’s glyph variants |
| MATH again | size variants and assembly parts of the glyphs GSUB added | `_glyphset_mathed` | MATH’s glyph info |
| COLR | COLRv0 layers and every glyph a COLRv1 paint graph uses ([Color](color.html)) | `_glyphset_colred` | COLR |
| VARC | the components of [variable composites](variable-components.html) | `_glyphset_varced` | VARC |
| glyf, CFF | composite components; the two glyphs of a CFF `seac` accent | `_glyphset` | everything else |

The `name` stage in the middle collects no glyphs: it keeps the `name` IDs that STAT, fvar, CPAL, and the kept GSUB and GPOS features refer to.

The order follows how a glyph reaches each table. Text becomes glyphs through `cmap`; MATH comes next, so that GSUB is closed over its size variants too, and again after GSUB, for the variants of the glyphs GSUB produces. After GSUB, the stages add glyphs that are only *drawn*: a size variant a math engine picks, a color layer, a component, an accent CFF builds from two glyphs. None is ever in a buffer, so none goes back to GSUB, and GSUB, GPOS, and GDEF are subset against `_glyphset_gsub`, without them: a kerning pair only a COLR layer could use is dropped (inferred from the snapshots; no comment states the reason).

The demo font’s ★ is a COLRv0 glyph with two layers. The second, `star.ring`, is a glyf composite of two copies of `dot`. Cutting a subset for ★ runs three stages: `cmap` finds `star`, COLR adds the two layers, and glyf adds `dot`, which COLR has never heard of:

```info
star.ttf  --list-glyphs
```

```table
font: star.ttf
table: COLR
```

The glyf stage has limits. Components are followed `HB_MAX_NESTING_LEVEL` (64) deep, within a budget of `HB_MAX_COMPOSITE_OPERATIONS_PER_GLYPH` (64) operations per glyph in the set; and the kept glyphs’ bytes may add up to at most `HB_SUBSET_GLYF_MAX_BYTES_FACTOR` (16) times the glyf table’s size, or the plan fails (`hb-limits.hh:178`), since a `loca` could point many glyph IDs at the same bytes.

## The layout stage

The layout stage (`hb-subset-plan-layout.cc`) does more than add glyphs. For GSUB and then GPOS, `_closure_glyphs_lookups_features` (`:405`) decides which features and lookups survive:

1. **Collect.** The table’s feature and script tags are filtered by the input’s sets, and `hb_ot_layout_collect_features` turns the survivors into feature indices, from every language system of the kept scripts. Their lookups are collected, including lookups that FeatureVariations can substitute.
2. **Close the glyphs.** For GSUB only, unless `NO_LAYOUT_CLOSURE` is set, `hb_ot_layout_lookups_substitute_closure` adds every glyph those lookups can produce (`:431`).
3. **Close the lookups.** `closure_lookups` adds the lookups that contextual lookups call, then removes every lookup whose coverage doesn’t intersect the glyph set: those can never fire.
4. **Prune features.** `prune_features` drops a feature that has no lookups left, with two exceptions (`hb-ot-layout-gsubgpos.hh:6908`): a `size` feature with parameters, and `pref`, which is kept even when empty because HarfBuzz chooses its Khmer shaper by whether the font has it (“Never ever drop feature 'pref'”). Then features with the same tag and, after subsetting, the same lookups are merged (12.0.0), and language systems are pruned.

[GPOS](gpos.html) takes part in steps 1, 3, and 4, but adds no glyphs. Since GSUB is closed first, GPOS’s step 3 sees every glyph that can reach it.

The demo font has `liga` and `dlig`. A subset for `ct` loses `dlig`, which is not a default feature, and with it the `c_t` ligature; asking for it with `--layout-features+=dlig` keeps both. Its kerning and mark lookups go too, since their glyphs are gone, and with them the GPOS features:

```info
demo.ttf  --list-features
ct.ttf  --list-features
ct-dlig.ttf  --list-features
```

```shape
demo.ttf  ct  --features=dlig
ct.ttf  ct  --features=dlig
ct-dlig.ttf  ct  --features=dlig
```

### How the GSUB closure works

The closure is another dispatch context, `hb_closure_context_t` (`hb-ot-layout-gsubgpos.hh:68`): each subtable has a `closure` method that adds what it could produce from the glyphs in the set. For the lookup types of [GSUB](gsub.html): a single or alternate substitution adds the substitute of each covered glyph that is in the set; a multiple substitution adds its sequence; a ligature adds its ligature glyph when *every* component is in the set; a contextual rule calls its nested lookups when its input, backtrack, and lookahead can all be matched from the set.

It works on sets, not strings. It doesn’t know in what order the glyphs come, or whether they ever meet. The subset `if.ttf` was cut for the text “if”, which never forms the `fi` ligature, but `f` and `i` are both in the set, so `f_i` is kept and its rule with it, while `f_l` is not:

```info
if.ttf  --list-glyphs
```

```views
font: if.ttf
lookup: 0
```

```shape
demo.ttf  fi
if.ttf  fi
```

So the closure over-approximates on purpose. Keeping a glyph that turns out not to be needed costs bytes; dropping one that is needed changes the text.

The function that runs it is short (`hb-ot-layout.cc:1670`, trimmed):

```c++
do
{
  c.reset_lookup_visit_count ();
  glyphs_length = glyphs->get_population ();
  for (auto lookup_index : *lookups)
    gsub.get_lookup (lookup_index).closure (&c, lookup_index);
} while (iteration_count++ <= HB_CLOSURE_MAX_STAGES &&
         glyphs_length != glyphs->get_population ());
```

Each pass runs every lookup in index order, and each lookup’s output is added to the set as soon as it finishes (`c->flush ()` in `SubstLookup::closure`), so a later lookup in the same pass sees it. A lookup that has already run with the same set of input glyphs is skipped. Passes repeat while the set grows, but at most `HB_CLOSURE_MAX_STAGES` + 2 times: 18. Since 15.2.0 the closure also has a work budget, `HB_BUDGET_LAYOUT_CLOSURE` (2²⁸ units, `hb-limits.hh:389`), charged for every subtable it visits and every coverage it walks; when it is spent, the closure stops where it is, as it does at the limit on lookup visits.

## Why fixed stages, and not a fixpoint

A **fixpoint** would be the obvious design: run every closure again and again until a whole round adds nothing. HarfBuzz doesn’t, at either level.

Between tables, the order above makes most of a loop unnecessary: what later stages add is drawn, not shaped. Within GSUB, the bound is explained by the comment on its definition (`hb-limits.hh:69`):

```c++
/*
 * The maximum number of times a lookup can be applied during shaping.
 * Used to limit the number of iterations of the closure algorithm.
 * This must be larger than the number of times add_gsub_pause() is
 * called in a collect_features call of any shaper.
 */
#define HB_CLOSURE_MAX_STAGES 16
```

The reasoning is that shaping itself runs in stages. Within a stage, lookups run once each, in index order, which is the order of one pass. A lookup can run again only in a later stage, after a pause ([From features to lookups](from-features-to-lookups.html#stages-and-pauses)), so a chain of substitutions that goes back to a lower lookup index needs one more pass per stage, and no more passes are needed than there are stages.

The second reason is in `SubstLookup.hh:209`, where a contextual lookup calls a nested one. The nested lookup’s output is *not* added to the set straight away, only when the outer lookup finishes:

```c++
/* Keep global flushing outside recursion so a recursive lookup cannot
 * keep expanding the global set. Contextual sequences include pending
 * outputs when revisiting an input position. */
```

The second sentence is new in 15.2.0. When a rule applies a second nested lookup at a position an earlier one has already changed, `context_closure_recurse_lookups` (`hb-ot-layout-gsubgpos.hh:2486`) lets it see the earlier lookups’ pending output as well as the set, so a chain of nested lookups at one position is followed in a single pass. Before 15.2.0 each pass got one step further along such a chain, and the pass limit cut it short ([HHW-43](bugs-this-book-found.html#hhw-43)).

The limit is a defense against hostile fonts as much as a shortcut: a closure run to a fixpoint could be made to run for a very long time (8.1.0 reverted an optimization that “could cause timeout during subsetting with malicious fonts”). [hb-depend](hb-depend.html) takes the other side: its closure follows edges “to a fixed point”, while “the subsetter’s iterative closure (`HB_CLOSURE_MAX_STAGES`) truncates these chains” (`docs/depend-for-closure.md`).

### Testing the closure

The fixed order and the pass limit are judgments, and they can be tested. `nested.ttf` has one contextual rule in `ccmp` that applies twenty single substitutions to the same glyph, one after another, `a` → `s1` → `s2` … → `s20`. Its feature file (`fonts/subsetting/nested.fea`) defines the twenty lookups `L19` down to `L0`, and then:

```
feature ccmp {
  sub a' lookup L0 lookup L1 lookup L2 … lookup L19;
} ccmp;
```

Shaping applies all twenty. The closure applies `L0` to `a`, and `L1`, at the same position, sees `L0`’s pending `s1`, and so on down the rule, so one pass reaches `s20`, and the subset keeps `a`, all twenty substitutes, and `.notdef`, and shapes as the original does:

```info
nested.ttf  --show-glyph-count
nested-a.ttf  --show-glyph-count
```

```shape
nested.ttf  a
nested-a.ttf  a
```

Before 15.2.0, `L1` didn’t see `s1` until the next pass, each pass added one glyph, and the closure stopped with `s14`, so the subset shaped differently from the original ([HHW-43](bugs-this-book-found.html#hhw-43)). The bound also left less margin than its comment asks for, 12 against the Indic shaper’s 14 calls to `add_gsub_pause` (`hb-ot-shaper-indic.cc:249`–`265`); 15.2.0 raised it to 16 ([HHW-44](bugs-this-book-found.html#hhw-44)). A chain that runs backwards through the lookup list, one stage at a time, across more than 18 stages would still be cut, though the Indic shaper, for one, pauses only 14 times.

The order between tables is tested by MATH. `math.ttf` has an integral, a display-size variant of it, and an `rtlm` feature (a default one) that replaces both with mirrored forms for right-to-left math. All four glyphs have italics corrections, and both integrals have a list of sizes. Cut for ∫, the subset keeps all four glyphs and shapes as the original does:

```info
math-integral.ttf  --list-glyphs
```

```shape
math.ttf  ∫  --direction=rtl
math-integral.ttf  ∫  --direction=rtl
```

It keeps their MATH data too. MATH’s glyph variants and assemblies are subset against `_glyphset_gsub`, and its italics corrections, accent positions, and kerning against `_glyphset_mathed` (`hb-ot-math-table.hh:1064`, `:232`), both taken after GSUB. No HarfBuzz tool prints a MATH table, so here is fontTools reading the original and the subset (`fonts/subsetting/math-summary.txt`, written by `build.sh`):

```
math.ttf
  italics correction: integral, integral.size1, integral.rtlm, integral.rtlm.size1
  vertical variants:
    integral -> integral, integral.size1
    integral.rtlm -> integral.rtlm, integral.rtlm.size1
math-integral.ttf
  italics correction: integral, integral.size1, integral.rtlm, integral.rtlm.size1
  vertical variants:
    integral -> integral, integral.size1
    integral.rtlm -> integral.rtlm, integral.rtlm.size1
```

Before 15.2.0, MATH was subset against snapshots taken before GSUB ran, and this subset lost the mirrored integral’s sizes and both mirrored glyphs’ italics corrections: a math engine laying out right-to-left display math would have found no larger integral ([HHW-45](bugs-this-book-found.html#hhw-45)).

> For programmers: if a subset must work with features or engines beyond plain shaping, check it the way this page does: shape the same text with both fonts, with the same features. `hb-shape --verify` checks a font against itself; only a comparison checks a subset.

## The glyph map

`_create_old_gid_to_new_gid_map` (`hb-subset-plan.cc:592`) numbers the kept glyphs, in one of three ways:

* By default, the kept glyphs are numbered from 0 in their old order, so `.notdef` stays 0 and nothing else keeps its number.
* With `RETAIN_GIDS`, every glyph keeps its number, and the font has as many glyphs as the highest one kept, plus one. The gaps are empty glyphs. This is for glyph IDs that are stored outside the font, or that must match across several subsets of one font: NEWS for 8.0.1 speaks of “retain-gid (used for IFT)”, incremental font transfer.
* With a glyph map from the input, the mapped glyphs get the IDs asked for and the rest follow the highest of them. The map must be one-to-one, can’t be combined with `RETAIN_GIDS`, and since 15.1.0 can’t give glyph 0 to anything but `.notdef`.

The same “fi” subset with `--retain-gids` keeps `f`, `i`, and `f_i` at 6, 7, and 12. The `post` table names the empty glyphs `.notdef`:

```info
fi-retain.ttf  --list-glyphs
```

The documentation of `hb_subset_input_old_to_new_glyph_mapping` allows a map that changes the order of glyphs, but much of the layout subsetting assumes it doesn’t. A typical `subset` method walks its table in old glyph order, maps each glyph, and writes the results in that order, which is new glyph order only if the map keeps the order, as the default one does (`hb-subset-plan.cc:668`). The Coverage serializer notices and sorts (`CoverageFormat2.hh:117`). A kerning pair set doesn’t (`PairSet.hh:255`), though its records must be sorted by second glyph, because shaping finds them by binary search. `kern.ttf` kerns A against eight glyphs, each by its own amount; `kern-map.ttf` was cut with a `--gid-map` numbering those eight backwards:

```info
kern-map.ttf  --list-glyphs
```

```shape
kern.ttf  ACAGAOAQATAVAWAY
kern-map.ttf  ACAGAOAQATAVAWAY
```

Of the eight pairs, only the one the binary search reaches first survives. Class definitions are written the same way (`ClassDef_remap_and_serialize`, `hb-ot-layout-common.hh:1500`), and a font kerned by classes loses most of its classes (tested, not shown). This looks like a bug; meanwhile a custom map is safe only if it keeps the old order.

> Since {{hb}}: changed on HarfBuzz main by [#6831](https://github.com/harfbuzz/harfbuzz/pull/6831) (20 November 2026): the documentation of `hb_subset_input_old_to_new_glyph_mapping` and `hb-subset --help` now say that a map that reorders glyphs breaks pair kerning and class definitions, and is safe only when the layout tables are dropped; the behavior is unchanged.

## Writing the tables

`hb_subset_plan_execute_or_fail` (`hb-subset.cc:441`) lists the source font’s tables and asks of each whether it is dropped, in `_should_drop_table` (`:221`):

* any table in the input’s drop set;
* the hinting tables `cvt `, `fpgm`, `prep`, `hdmx`, and `VDMX` with `NO_HINTING`, and `cvar` with `NO_HINTING` or when every axis is pinned;
* `avar`, `fvar`, `gvar`, `HVAR`, `VVAR`, and `MVAR` when every axis is pinned, because the font is no longer variable;
* in a build with `HB_NO_SUBSET_LAYOUT`, GDEF, GSUB, GPOS, `kern`, and the AAT layout tables.

The rest go into a set of pending tables, and a loop subsets each table whose dependencies are met (`_dependencies_satisfied`, `:267`), until none is left. A table waits for what another table’s subsetting computes: when instancing, `hmtx`, `vmtx`, `maxp`, and `OS/2` wait for `glyf`, whose instanced outlines give new metrics; GSUB and GPOS wait for GDEF unless every axis is pinned; and with `avar` version 2, the variation tables wait for `avar`. A round that makes no progress fails the subset. Within a round, tables go in tag order as numbers, so capitalized tags (`COLR`, `GSUB`, `OS/2`) come before lower-case ones (`cmap`, `glyf`).

For each table, `_subset_table` (`:309`) chooses:

* **Passed through.** A table in the no-subset set is copied unchanged.
* **Subset.** A table HarfBuzz knows is subset by its own `subset` method, through one of five families of dispatchers (`hb-subset-table-{layout,var,cff,color,other}.cc`). Some tables are written by others: `loca` and `head` by `glyf` (`head` by itself when there is no `glyf`), `hhea` by `hmtx`, `vhea` by `vmtx`, `CBDT` by `CBLC`. `fvar`, `avar`, `STAT`, `cvar`, and `MVAR` are copied unless axes are being instanced, and `cvt ` unless `cvar` deltas must be applied to it.
* **Dropped.** Anything else is dropped, unless `PASSTHROUGH_UNRECOGNIZED` is set.

AAT and Graphite tables aren’t subset; `hb-subset.cc` advises such fonts to “configure the subset to pass through the unsupported tables untouched”, and since 15.2.0 the plan then keeps the glyph IDs by itself, as above.

A table whose `subset` returns false, meaning nothing of it is left, is left out of the font. The demo font loses `COLR` and `CPAL` when ★ isn’t asked for, and `fpgm` and `prep`, which are passed through by default, go with `--no-hinting`:

```info
demo.ttf  --list-tables
if.ttf  --list-tables
if-nohint.ttf  --list-tables
```

Each table is serialized into a buffer of a guessed size (`_hb_subset_estimate_table_size`, `hb-subset-table.hh:78`): 8 KiB plus the source table’s size times the square root of the fraction of glyphs kept, or plus the whole size for GSUB, GPOS, GDEF, and `name`. If it runs out of room, the buffer is doubled and the table subset again, up to 256 times the source table’s size or 1 MiB, whichever is larger (`HB_SUBSET_MAX_TABLE_SIZE_FACTOR` and `HB_SUBSET_MAX_TABLE_SIZE_MIN`, `hb-subset-table.hh:54`; the floor is new in 15.2.0, for small tables that grow when renumbered); if an offset overflows, the repacker rearranges the table’s objects. [Writing tables](writing-tables.html) is about both.

A face made with `hb_face_create_for_tables` may be unable to list its tables. The subsetter then asks it for each tag in its own list of known tables (`known_tables`, `hb-subset.cc:74`) and in the no-subset set, so an unknown table in such a face is lost even with `PASSTHROUGH_UNRECOGNIZED`.

The source tables are read through the plan’s `source_table`, which sanitizes each one once and caches it. It uses a plain sanitizer, without the `lazy_some_gpos` flag that shaping uses, so a GPOS that shaping tolerates can be rejected here ([Trust nothing](trust-nothing-the-sanitizer.html) has the details).

The result is the builder face holding the new tables, or `NULL`: a subset fails if the source font has no glyphs (since 10.0.0), if the plan fails, if a table fails to subset or repack, or if table dependencies can’t be met.

## Table by table

Each table’s `subset` keeps what refers to kept glyphs, characters, lookups, or `name` IDs, renumbers it, and rewrites the fields that depend on the numbering. Fields that summarize the whole font, such as `head`’s bounding box, the maxima in `maxp` and `hhea`, and `OS/2`’s `xAvgCharWidth`, are recomputed only when instancing; on a plain subset most stay true, as bounds that are no longer tight (inferred).

| Table | What its subset does | Source |
|---|---|---|
| `cmap` | keeps the Unicode subtables, (0, 3), (0, 4), (3, 1), (3, 10), and format 14, and the symbol subtable (3, 0); drops a format 12 that would map nothing beyond its format 4 sibling; if format 4 overflows, falls back to format 12 alone | `hb-ot-cmap-table.hh` |
| `glyf`, `loca`, `head` | copies the kept glyphs, trims their padding, drops instructions with `NO_HINTING`, empties `.notdef`; chooses short `loca` offsets when the glyphs total less than 0x1FFFF bytes and sets `head.indexToLocFormat` | `OT/glyf/glyf.hh` |
| `hmtx`, `hhea` (and vertical) | metrics of the kept glyphs; trailing glyphs with the same advance as the last long metric are written short | `hb-ot-hmtx-table.hh` |
| `maxp` | `numGlyphs`; resets the hinting maxima with `NO_HINTING` | `hb-ot-maxp-table.hh` |
| `OS/2` | `usFirstCharIndex` and `usLastCharIndex` from the kept characters; clears Unicode range bits no kept character needs, never sets one | `hb-ot-os2-table.hh` |
| `post` | version 3, without names, unless `GLYPH_NAMES` | `hb-ot-post-table.hh` |
| `name` | records with kept IDs and languages; only Unicode and Windows ones unless `NAME_LEGACY` | `OT/name/name.hh` |
| `hdmx`, `VORG` | rows or entries for the kept glyphs | `hb-ot-hdmx-table.hh`, `hb-ot-vorg-table.hh` |
| GDEF | classes, attachment points, and carets of `_glyphset_gsub`; only the mark glyph sets still used, renumbered; the lowest version that holds what is left | `OT/Layout/GDEF/GDEF.hh` |
| BASE | records of kept scripts; reference glyphs renumbered | `hb-ot-layout-base-table.hh` |
| MATH | against the early snapshots, as above | `hb-ot-math-table.hh` |
| COLR, CPAL | records, layers, and paints of kept glyphs; every palette, but only the color entries still used, renumbered | `OT/Color/COLR/COLR.hh`, `OT/Color/CPAL/CPAL.hh` |
| CBLC, CBDT, `sbix` | each strike’s bitmaps for the kept glyphs | `OT/Color/CBDT/CBDT.hh`, `OT/Color/sbix/sbix.hh` |
| CFF, CFF2 | charstrings of the kept glyphs; the subroutines they still call, renumbered, or none with `DESUBROUTINIZE`; hints dropped with `NO_HINTING`; empties `.notdef` | `hb-subset-cff1.cc`, `hb-subset-cff2.cc`, `hb-subset-cff-common.hh` |
| VARC | records of kept glyphs with the conditions, axis lists, and variation data they use | `OT/Var/VARC/VARC-subset.hh` |
| `gvar`, HVAR, VVAR | variation data of the kept glyphs ([Instancing](instancing.html) has the rest) | `hb-ot-var-gvar-table.hh`, `hb-ot-var-hvar-table.hh` |

Two rows changed in 15.2.0. The first is `cmap`’s list of subtables (`hb-ot-cmap-table.hh:2573`), which now has a symbol font’s (3, 0). Before, a font whose only subtable was (3, 0) lost its `cmap` altogether ([HHW-51](bugs-this-book-found.html#hhw-51)). fontTools’ subsetter drops (3, 0) by default, and keeps it with `--symbol-cmap`. A symbol font maps its characters into the Private Use Area: `symbol.ttf` maps U+F061, which shaping also finds for “a” (`_hb_symbol_pua_map`), and the plan now adds U+F061 to the characters to keep when “a” is asked for and only U+F061 is mapped (`closure_symbol_unicodes`, `hb-ot-cmap-table.hh:2414`). The legacy Arabic fonts of [Joining scripts](joining-scripts.html#legacy-encodings) are symbol fonts too. Cut for “a”, the subset keeps the glyph and the way to it:

```info
symbol-a.ttf  --list-tables
```

```shape
symbol.ttf  a
symbol-a.ttf  a
```

The second is `.notdef`. `NOTDEF_OUTLINE` is now read by the CFF and CFF2 code as well as by glyf and `gvar` (`hb-subset-cff-common.hh:446`), so a CFF `.notdef` is emptied like a glyf one, as fontTools’ subsetter does (`fontTools/subset/cff.py`); before 15.2.0 it kept its outline either way ([HHW-52](bugs-this-book-found.html#hhw-52)). Here are `if.ttf` and a CFF subset, each shaping a character it lacks:

```shape
if.ttf  Z  --show-extents
cff-o.otf  Z  --show-extents
```

## Preprocessing

A server that cuts many subsets from one font can do part of the work once. `hb_subset_preprocess` (6.0.0) is itself a subset, with `keep_everything` and a flag that attaches an **accelerator** (`hb_subset_accelerator_t`) to the new face: the `cmap` maps, the sanitized tables, the parsed CFF, and whether it uses `seac` (`hb-subset-accelerator.hh`). It also writes `glyf` with long offsets and no padding, so that later subsets can skip trimming (`hb-subset-input.cc:1138`). Later subsets of that face use the accelerator. `docs/subset-preprocessing.md` says the result “should be identical”, and that CFF fonts gain most.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-subset.h` | the public API: flags, sets, plan functions |
| `src/hb-subset-input.cc` | the input, its defaults, `keep_everything`, axis settings, `hb_subset_preprocess` |
| `src/hb-subset-plan.cc` | the plan: characters, the glyph closure stages, the glyph map |
| `src/hb-subset-hinting.hh` | the fonts that keep their hinting with `NO_HINTING` |
| `src/hb-subset-plan-layout.cc` | which GSUB and GPOS features and lookups survive |
| `src/hb-subset-plan-member-list.hh` | everything the plan holds |
| `src/hb-ot-layout.cc` | `hb_ot_layout_lookups_substitute_closure`, the pass loop |
| `src/hb-ot-layout-gsubgpos.hh` | the closure contexts, contextual closure, `prune_features` |
| `src/OT/Layout/GSUB/SubstLookup.hh` | where nested lookups aren’t flushed |
| `src/hb-limits.hh` | `HB_CLOSURE_MAX_STAGES` and the glyf budgets |
| `src/hb-subset.cc` | table order, dropping, passing through, the execute loop |
| `src/hb-subset-table.hh`, `src/hb-subset-table-*.cc` | one table’s subset: buffer, retry, repack; the dispatch by tag |
| `src/hb-ot-cmap-table.hh` | `cmap`’s subset and the subtables it keeps |
| `src/OT/glyf/glyf.hh`, `src/hb-subset-cff1.cc`, `src/hb-subset-cff-common.hh` | outlines, `.notdef`, subroutines |
| `src/OT/Layout/GPOS/PairSet.hh`, `src/hb-ot-layout-common.hh` | pair sets and class definitions, written in old glyph order |
| `src/hb-subset-accelerator.hh` | what preprocessing caches |
| `docs/subset-preprocessing.md`, `docs/depend-for-closure.md` | preprocessing; how hb-depend’s closure compares |

## In short

* A subset is planned, then written. The plan decides the characters, the glyphs, their new IDs, and the features and lookups that survive.
* Characters gain their bidi mirrors, but not their decompositions or compositions, so text in another normalization form can shape differently.
* The glyph closure runs in a fixed order: `cmap`, MATH, GSUB, MATH again, COLR, VARC, glyf and CFF components. Later stages add glyphs that are drawn, not shaped, and GSUB, GPOS, and GDEF are subset against the set taken after GSUB.
* The GSUB closure works on sets, not strings, for at most 18 passes. Since 15.2.0 a chain of nested lookups at one position is followed in a single pass.
* Since 15.2.0, glyphs only GSUB produces, such as `rtlm` forms, keep their MATH data.
* Default subsets keep only the features shaping turns on by itself.
* A custom glyph map that reorders glyphs breaks pair kerning and class definitions.
* Tables are dropped, passed through, or subset; each subset renumbers what it keeps, unless a kept table can’t be renumbered, and then every glyph keeps its ID.
