# hb-depend: the glyph dependency graph

When HarfBuzz subsets a font, it works out which glyphs the subset must keep: the glyphs the requested characters map to, and everything those glyphs can turn into or are built from. [Subsetting](subsetting.html) describes that glyph closure. It is computed for one request, from one set of characters, and thrown away when the subset is written.

**hb-depend** computes the relationships themselves, once, as a graph. Each node is a glyph. Each edge says that one glyph can lead to another: through a substitution, as a component, as a color layer, or as a mathematical variant. With the graph in hand, a program can compute a closure for any set of characters by walking it, without running the subsetter at all. The API arrived in HarfBuzz 14.3.0 and is still experimental: it is compiled only when HarfBuzz is built with `-Dexperimental_api=true`.

This chapter covers what the graph holds, how HarfBuzz builds it, how a closure is computed from it, and where that closure differs from the subsetter’s. The book’s own HarfBuzz build doesn’t enable experimental APIs, so nothing on this page is a live block except one shaping result. The graph and closures shown were produced by a small program, `fonts/hb-depend/depend-graph.cc`, compiled against the same HarfBuzz {{hb}} source with the API switched on.

## Who needs a graph

A closure answers “starting from these glyphs, what can be reached?”. A **glyph dependency graph** answers the question behind it, for every glyph at once. Take a ligature rule, `f i → f_i`. The closure of `{f}` is just `{f}`: the `i` is missing, so the ligature can’t form (`Ligature.hh:35`). The graph records two edges, `f → f_i` and `i → f_i`, and remembers that both are needed. It doesn’t depend on any starting set.

Building the graph costs one pass over the font. After that, each closure costs only the edges it follows. That trade is worth making for a program that needs many closures of the same font. The documentation names the uses it has in mind (`docs/depend-api.md`): deciding what a subset must keep; finding which glyphs each feature or script needs; **font segmentation**, splitting a font into pieces that each hold the glyphs reachable from some set of characters, “enabling more efficient font delivery for web applications”; and checking that an edit to a font hasn’t broken a substitution chain. NEWS for 14.3.0 describes it as an API “that applications can use to compute glyph closures themselves without running the subsetter”. Incremental font transfer, which serves a font in segments, is the obvious client of segmentation, though HarfBuzz’s documents for the API don’t name it (inferred).

## Nodes and edges

The graph’s nodes are glyph IDs and nothing else. There are no character nodes: `cmap` isn’t in the graph, and a program maps its characters to glyphs itself, with `hb_font_get_nominal_glyph()`. Variation sequences are left out too (`hb-depend.cc:77`). Whoever walks the graph adds the glyph for each base character and variation selector with `hb_font_get_variation_glyph()`.

The public header is `hb-subset-depend.h`, included through `hb-subset.h`. It has four functions:

| Function | What it does |
|---|---|
| `hb_subset_depend_from_face_or_fail (face)` | builds the graph for a face, or returns `NULL` |
| `hb_subset_depend_lookup_glyph (depend, gid, start, &count, entries)` | a glyph’s outgoing edges, in the usual HarfBuzz array-getter form; returns how many there are |
| `hb_subset_depend_lookup_set (depend, index, set)` | copies one of the graph’s glyph sets into an `hb_set_t` |
| `hb_subset_depend_destroy (depend)` | frees it |

Each edge comes back as an `hb_subset_depend_entry_t` (`hb-subset-depend.h:102`):

```c
typedef struct {
  hb_tag_t table_tag;                     /* the table the edge comes from */
  hb_codepoint_t dependent;               /* the glyph it leads to */
  hb_tag_t layout_tag;                    /* GSUB: the feature */
  hb_codepoint_t ligature_set_index;      /* GSUB ligatures: the components */
  hb_codepoint_t context_set_index;       /* GSUB contexts: what must be around */
  hb_subset_depend_edge_flags_t flags;
} hb_subset_depend_entry_t;
```

The edge runs from the glyph asked about to `dependent`. What “leads to” means depends on the table:

| `table_tag` | Edge from → to | Where it’s made |
|---|---|---|
| `GSUB` | a glyph a lookup can act on → a glyph it can produce | `OT/Layout/GSUB/*.hh`, `hb-ot-layout-gsubgpos.hh` |
| `glyf` (or `GLYF`) | a composite glyph → each of its components | `OT/glyf/glyf.hh:273` |
| `CFF ` | a glyph drawn with the `seac` operator → its base and accent | `hb-ot-cff1-table.hh:1566` |
| `COLR` | a color glyph → each v0 layer glyph, each glyph a v1 `PaintGlyph` fills, and each glyph a `PaintColrGlyph` reuses | `OT/Color/COLR/COLR.hh:2698`, `colrv1-depend.hh` |
| `MATH` | a glyph → its size variants and the parts of its assembly | `hb-ot-math-table.hh:1216` |
| `VARC` | a glyph → each of its variable components | `OT/Var/VARC/VARC.cc:194` |

Only GSUB edges use the other fields. `layout_tag` is the feature whose lookup made the edge. A lookup that several features use gets one edge for each feature (`add_gsub_lookup`, `hb-depend-data.hh:559`), so a program can drop edges for features it doesn’t want. For the other tables `layout_tag` is `HB_CODEPOINT_INVALID`, 0xFFFFFFFF.

The two set indices point into one array of glyph sets that the graph owns. A **ligature set** is every glyph a ligature’s components use, the first glyph included (`Ligature.hh:41`). Each component gets an edge to the ligature, and all those edges carry the same set: the ligature belongs in a closure only once every glyph in its set is there. A **context set** is what a contextual rule needs around the glyph: its backtrack, its lookahead, and its other input positions. Its members are of two kinds, told apart by the top bit (`HB_DEPEND_CONTEXT_SET_FLAG`, `hb-depend-data.hh:55`). A plain glyph ID must itself be present. A value with the top bit set is the index of another set in the same array, of which any one glyph will do. The context is satisfied when every member is. Ignoring context sets is allowed, and gives a closure that is larger but never too small.

The flags mark edges that a static graph can’t get exactly right, which [below](#where-the-graph-is-approximate) explains.

## The graph of one small font

The font for this chapter is the [GSUB chapter’s](gsub.html) test font, `ligatures.ttf`, with one glyph added: `aacute`, mapped to U+00E1, a TrueType composite of `a` and `acutecomb` (`fonts/hb-depend/build-font.py`). Its GSUB comes from this feature file (an excerpt of `fonts/gsub/ligatures.fea`, trimmed):

```fea
feature liga {
  lookupflag IgnoreMarks;
  sub f i by f_i;
  sub f f i by f_f_i;
  sub f l by f_l;
  sub f f by f_f;
} liga;

feature salt {
  sub a from [a.alt1 a.alt2 a.alt3];
} salt;

lookup INIT {
  sub e by e.init;
} INIT;

feature calt {
  sub [space e.init] e' lookup INIT;
} calt;

feature ccmp {
  sub x by f i;
} ccmp;
```

This is the whole graph, as `depend-graph` prints it. It isn’t a live block: it was produced by `fonts/hb-depend/run.sh`, which compiles `depend-graph.cc` against HarfBuzz {{hb}} with `HB_EXPERIMENTAL_API`. Its format is that of HarfBuzz’s `hb-subset-depend` utility: each source glyph, then one line for each edge, with the table, the feature for GSUB, the dependent glyph, the ligature set and its members, and the context set in brackets, where `(a|b)` means either glyph.

```
2 (a):
  GSUB salt -> a.alt1
  GSUB salt -> a.alt2
  GSUB salt -> a.alt3

3 (e):
  GSUB calt -> e.init  ((space|e.init))

4 (f):
  GSUB liga -> f_f_i  lig[0]
    lig[0]: f i
  GSUB liga -> f_i  lig[0]
  GSUB liga -> f_l  lig[1]
    lig[1]: f l
  GSUB liga -> f_f  lig[2]
    lig[2]: f

5 (i):
  GSUB liga -> f_f_i  lig[0]
  GSUB liga -> f_i  lig[0]

6 (l):
  GSUB liga -> f_l  lig[1]

7 (x):
  GSUB ccmp -> f
  GSUB ccmp -> i

17 (aacute):
  glyf -> a
  glyf -> acutecomb
```

Seven of the eighteen glyphs have edges. The others lead nowhere: `.notdef`, `space`, `acutecomb`, the ligatures, and the alternates are ends of paths. Four things in this output are worth a closer look.

**The alternates.** An alternate substitution gives an edge to every alternate. A closure can’t know which one an application will choose.

**The nested lookup.** `e → e.init` is tagged `calt`, though the lookup that does it, `INIT`, belongs to no feature. HarfBuzz walks only lookups that some feature uses (`hb-ot-layout-gsub-table.hh:196`). It reaches `INIT` through `calt`’s chained rule, and an edge found inside a rule takes the feature of the lookup the walk started from. The edge also carries the rule’s backtrack, `[space e.init]`, as a context set with one member: a set of two glyphs, either of which will do.

**The ligature sets.** A ligature set is a set, not a sequence. `f f i → f_f_i` needs `{f, i}`, the same set as `f i → f_i`, so the two share `lig[0]`. Sets are stored once, by content. `f f → f_f` needs only `{f}`, so one `f` in a closure brings `f_f` with it. A closure works with which glyphs are present, never how many, and the subsetter’s does the same.

**The composite.** `aacute` depends on `a` and `acutecomb` through `glyf`, with no feature and no conditions.

The `ccmp` rule `x → f i` gives `x` two edges. Together with the ligature edges, they say that `x` can lead to `f_i`. In this font it never does, as shaping shows:

```shape
depend.ttf  x  --language=en
```

The `liga` lookup comes before the `ccmp` lookup in the LookupList, so it has already run when `x` becomes `f i` ([The order lookups run in](gsub.html#the-order-lookups-run-in) has the details). The graph doesn’t record lookup order, so this is one way it errs on the side of keeping a glyph. The subsetter’s closure, which follows substitutions without simulating shaping, keeps `f_i` too, as the next section shows.

## How the graph is built

`hb_subset_depend_from_face_or_fail()` makes one vector of edges for each glyph in the face and asks each table to fill it in (`hb-depend.cc:74`, trimmed):

```cpp
bool
hb_depend_data_builder_t::compile (hb_face_t *face)
{
  if (hb_ot_layout_has_substitution (face))
    face->table.GSUB.get_relaxed ()->depend (this, face);
  face->table.MATH->depend (this);
  face->table.COLR->depend (this);
  face->table.glyf->depend (this);
  OT::cff1_subset_accelerator_t (face).depend (this);
  face->table.VARC->depend (this);
  return successful;
}
```

The non-GSUB tables are simple walks. `glyf` goes through every glyph and records each composite’s components; CFF asks each glyph for `seac` components; `MATH` walks its vertical and horizontal constructions; `VARC` decodes each glyph’s component records. `COLR` records every v0 layer, then walks each v1 base glyph’s paint graph. Its context counts operations against a budget proportional to the table’s size, limits nesting to `HB_MAX_NESTING_LEVEL`, and skips paints it has already visited for this base glyph. A `PaintGlyph` that fills the base glyph’s own outline isn’t recorded, since that is a use of geometry, not a dependency (`colrv1-depend.hh:54`). A `PaintColrGlyph` is recorded even when it points at itself. The specification forbids cycles in paint graphs, but a broken font can have them, and the graph reports what the font says. Anything that walks it has to guard against cycles (`docs/depend-api.md`).

GSUB is where the work is. It comes in two steps (`GSUB_accelerator_t::depend`, `hb-ot-layout-gsub-table.hh:119`).

**Features to lookups.** For each feature tag, HarfBuzz collects that feature’s lookups under every script and language system, and under every FeatureVariations record, and stores a map from each lookup to the tags that use it. Scripts and languages are merged here: the graph says which feature an edge belongs to, never which script.

**Each lookup, with every glyph active.** Each lookup that some feature uses is then walked by dispatching a **depend context**, `hb_depend_context_t` (`hb-ot-layout-gsubgpos.hh:402`), over it: one more visitor in the dispatch family that [Fonts as bytes](fonts-as-bytes.html) describes. Each subtable type has a `depend()` method beside its `closure()` method, built the same way. The difference is the starting set. A closure starts from the request’s glyphs. A depend walk starts from every glyph in the font (`hb-ot-layout-gsub-table.hh:186`), so every rule that could ever match is visited, and each records an edge for each glyph it covers.

Contextual rules need more care. When a Context or ChainContext rule calls a lookup at some position, the walk narrows the active glyphs to what can be at that position, as the closure does, and builds a context set from what must surround it (`context_depend_recurse_lookups`, `hb-ot-layout-gsubgpos.hh:2472`). The context set gathers the backtrack and lookahead, and the glyphs the rule’s other input positions require. A position that needs one particular glyph adds that glyph; a position that any of several glyphs can fill adds a set reference. Every edge recorded inside the called lookup carries that context set. Rules longer than `HB_MAX_CONTEXT_LENGTH` (64) are skipped, since they can never apply.

The walk doesn’t do what HarfBuzz’s own closure does inside a rule. The closure feeds each lookup’s output to the lookups after it in the same rule; the depend walk records every lookup’s edges independently, from what the rule’s coverage allows at each position (`docs/depend-implementation.md`). Recursion is guarded against loops: a lookup already on the call stack isn’t entered again (`recurse`, `:517`). Finished walks are memoized by lookup, active glyphs, call path, and context, so a shared lookup isn’t walked twice in the same state.

Every edge goes through a deduplicating hash table before it is stored, and sets are stored once by content (`add_edge`, `hb-depend-data.hh:508`). The hash table and the feature map are temporary: they belong to a builder that is freed when the graph is done, leaving only the edge lists and the sets.

## From graph to closure

`docs/depend-for-closure.md` describes how to compute a closure from the graph, and `test/fuzzing/hb-depend-closure-parity.cc` holds HarfBuzz’s reference implementation, `compute_depend_closure()`. The steps:

1. Map the characters to glyphs through `cmap`, add the glyphs of any variation sequences, and add `.notdef`.
2. Follow GSUB edges until nothing changes. Skip an edge whose feature isn’t wanted; skip a ligature edge until all of its ligature set is present; skip an edge whose context set isn’t satisfied.
3. Follow MATH edges once, from the glyphs present before this step only.
4. Follow COLR, VARC, `glyf`, and CFF edges to the end, with no conditions.

There is no going back to GSUB after the components: a component glyph is part of a drawing, not an input to shaping. `depend-graph --closure` does exactly this, with the subsetter’s default feature list, and prints the result beside the glyphs `hb_subset_plan_create_or_fail()` keeps for the same text. This is its output (`fonts/hb-depend/closures.txt`, made by `run.sh`; not live):

```
text "xe":
from the graph: .notdef e f i x f_i f_f f_f_i
the subsetter: .notdef e f i x f_i f_f f_f_i
text " e":
from the graph: .notdef space e e.init
the subsetter: .notdef space e e.init
text "á":
from the graph: .notdef a acutecomb aacute
the subsetter: .notdef a acutecomb aacute
text "xe", contexts ignored:
from the graph: .notdef e f i x f_i f_f f_f_i e.init
the subsetter: .notdef e f i x f_i f_f f_f_i
```

The two agree on every text. For “xe”, `x` brings `f` and `i`, and with both present the ligature sets let in `f_i`, `f_f`, and `f_f_i`. `salt` isn’t among the subsetter’s default features, so no alternates come in. `e.init` stays out, because neither `space` nor `e.init` is present to satisfy the context. For “ e” the space is there, and `e.init` comes in. For “á”, the composite brings its components. The last run follows edges whatever their context, and `e.init` comes in where it isn’t needed: larger, but still safe.

## Where the graph is approximate

Two kinds of edge can’t be modeled exactly by a graph built once from the font’s structure, and HarfBuzz flags them so that a program comparing its closure with the subsetter’s can tell an expected difference from a bug (`hb-subset-depend.h`, `hb-ot-layout-gsubgpos.hh:2641`):

* **`FROM_CONTEXT_POSITION`.** The edge comes from a contextual rule with more than one input position. The graph assumes each position can hold anything its coverage allows. In shaping, an earlier lookup in the rule may already have changed the glyph there.
* **`FROM_NESTED_CONTEXT`.** The edge comes from a contextual rule called from inside another contextual rule. It carries the inner rule’s context, but the outer rule’s is lost.

HarfBuzz’s notes name two more places where a closure from the graph can come out larger than the subsetter’s (`docs/depend-implementation.md`). A lookup whose output is in its own coverage makes a chain, `A → B → C`, that the graph follows to the end, while the subsetter stops after a fixed number of rounds. And MATH edges have to be followed only once, as step 3 does, because the subsetter keeps a variant’s glyph but drops that variant’s own MATH data.

## How the two closures differ

Both closures answer the same question, and on valid fonts HarfBuzz tests that they give the same answer: the parity test builds both and compares them. They get there differently.

| | The subsetter | A closure from the graph |
|---|---|---|
| Work for each request | walks the font’s tables again | follows edges in a graph built once |
| Characters | `cmap`, variation sequences, bidi mirroring, all inside the plan | the caller’s job |
| GSUB inside a rule | feeds each lookup’s output to the next | every lookup’s edges recorded independently |
| GSUB rounds | until stable, but at most `HB_CLOSURE_MAX_STAGES` + 2 = 14 passes (`hb-ot-layout.cc:1700`) | until stable |
| Scripts and languages | can be limited, in the subset input | merged when the graph is built |
| Features | the requested list | any list: each GSUB edge carries its feature |
| Order of stages | `.notdef`, `cmap`, MATH, GSUB, COLR, VARC, then `glyf` or CFF (`hb-subset-plan.cc:448`) | whatever the caller does; the reference does GSUB before MATH |
| Composites | `glyf` within a byte budget | edges, with no budget |

The last two rows are where differences could appear. The subsetter runs its MATH stage before GSUB, so a glyph that GSUB adds doesn’t get its math variants. The reference closure, in the parity test, runs MATH after GSUB, and its comments say that this mirrors the subsetter’s order (`hb-depend-closure-parity.cc:27`), which it doesn’t. A font where a substitution produces a glyph with math variants would give the graph’s closure more glyphs (inferred from the code; not tried). Neither closure models lookup order, so both can keep glyphs that shaping never produces, as `f_i` above shows.

> Since {{hb}}: changed on HarfBuzz main by [`0209ec2`](https://github.com/harfbuzz/harfbuzz/commit/0209ec2865b55e892897966e95dfb8915a1309e9) (17 November 2026): `HB_CLOSURE_MAX_STAGES` is 16, so the subsetter’s GSUB rounds (the table’s fourth row) stop at 18 passes.

## Status and limits

The API is experimental. `hb-config.hh:38` defines `HB_NO_SUBSET_DEPEND` unless `HB_EXPERIMENTAL_API` is defined, and the Meson option `experimental_api` (off by default; [Building HarfBuzz](building-harfbuzz.html#a-build-for-development)) defines it. Only the public functions are guarded: the `depend()` methods are compiled into `libharfbuzz-subset` either way, and the book’s build has them, but not the functions that call them. The command-line `hb-subset-depend` utility (`util/hb-subset-depend.cc`) is built only with the same option. The documentation warns that the API “may change significantly in future releases”. In 14.4.0, NEWS records only “faster extraction of the experimental glyph dependency graph”. The code’s copyright line is Adobe’s, 2024, with Skef Iterum as author.

What the graph leaves out:

* **No GPOS and no AAT tables.** Positioning doesn’t add glyphs, and `morx` isn’t walked. `docs/depend-implementation.md` lists both as possible additions.
* **No CFF2.** CFF2 has no `seac`, so there is nothing to record. Only CFF1 `seac` edges appear.
* **No character-level information.** No `cmap`, no variation sequences, no script.
* **No reference counting.** `hb_subset_depend_t` has `destroy` but no `reference` and no user data.
* **No partial failure.** If memory runs out while the graph is built, `hb_subset_depend_from_face_or_fail()` returns `NULL` rather than a partial graph.

A few of HarfBuzz’s own descriptions don’t match the code, which this chapter follows. The header says that `layout_tag` is 0 for edges from tables other than GSUB, but it is `HB_CODEPOINT_INVALID`, as `depend-api.md` says and the program above confirms. `depend-implementation.md` shows each edge taking only the first feature that uses its lookup, where the code makes one edge for each such feature. It names the header `hb-depend.h`, which is now `hb-subset-depend.h`, and calls the utility “TODO”, though it exists. And `test/fuzzing/README.md` asks for a meson option `depend_api`, which doesn’t exist: the option is `experimental_api`.

> Since {{hb}}: fixed on HarfBuzz main by [`88bb79a`](https://github.com/harfbuzz/harfbuzz/commit/88bb79a408620943fb475857777c2eceabb76ffb) and [`202b3e2`](https://github.com/harfbuzz/harfbuzz/commit/202b3e2c282a36f710834e61f460d8f48e6a10b9) (17 November 2026), so main’s header, `depend-implementation.md`, and fuzzing README match the code.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-subset-depend.h` | the public API: the entry struct, the edge flags, four functions |
| `src/hb-depend.cc` | `compile`, which calls each table, and the public functions |
| `src/hb-depend-data.hh` | the graph (`hb_depend_data_t`), and the builder: deduplication, sets, context sets, the lookup-to-feature map |
| `src/hb-ot-layout-gsub-table.hh` | `GSUB_accelerator_t::depend`: features to lookups, then each lookup |
| `src/hb-ot-layout-gsubgpos.hh` | `hb_depend_context_t`; contextual rules (`context_depend_recurse_lookups`) |
| `src/OT/Layout/GSUB/*.hh` | each subtable type’s `depend()`, beside its `closure()` |
| `src/OT/glyf/glyf.hh`, `src/hb-ot-cff1-table.hh`, `src/hb-ot-math-table.hh`, `src/OT/Var/VARC/VARC.cc` | the other tables’ `depend()` |
| `src/OT/Color/COLR/COLR.hh`, `src/OT/Color/COLR/colrv1-depend.hh` | COLR v0 layers and the v1 paint walk |
| `util/hb-subset-depend.cc` | the command-line utility |
| `test/fuzzing/hb-depend-closure-parity.cc` | the reference closure, `compute_depend_closure()`, checked against the subsetter |
| `docs/depend-api.md`, `docs/depend-implementation.md`, `docs/depend-for-closure.md` | HarfBuzz’s own notes |

The program that made this chapter’s output is `fonts/hb-depend/depend-graph.cc`. `fonts/hb-depend/run.sh` compiles it with HarfBuzz’s amalgamated `src/harfbuzz-subset.cc` and `HB_EXPERIMENTAL_API`, because the book’s libraries don’t export the functions.

## In short

* hb-depend builds a font’s glyph dependency graph once. Its nodes are glyphs, and its edges come from GSUB, `glyf`, CFF `seac`, COLR, MATH, and VARC. `cmap` and variation sequences are left to the caller.
* GSUB edges carry the feature that made them, the components a ligature needs, and the context a rule needs. A closure follows an edge only when those are met, or ignores the context and keeps a little more.
* The graph is built by a depend context dispatched over every lookup that a feature uses, with every glyph active, recording each lookup’s edges independently.
* A closure from the graph matches the subsetter’s on HarfBuzz’s tests. Flags mark the edges where it may come out larger.
* The API is experimental, compiled only with `-Dexperimental_api=true`, and may change.
