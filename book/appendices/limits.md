# Limits

A font is data, but much of it behaves like a program: lookups call lookups, composites contain composites, state machines loop, paint graphs branch. A small file can ask for an enormous amount of work or memory. HarfBuzz’s answer is a set of fixed limits, most of them in one header, `hb-limits.hh`, and the rest beside the code they guard.

This appendix lists them by area, with each one’s value, what it bounds, and what happens when a font or a text reaches it. That last column is the point. Reaching a limit never crashes, but the consequences differ a great deal: a table can be rejected whole, a buffer can be left half shaped, a rule can quietly not apply, a glyph can come out blank. Some of these an application can detect, and many it can’t. Where a chapter shows a limit being reached, the table links to it.

Two kinds of limit appear. A **structural limit** bounds one thing in one subsystem: points in a glyph, nesting depth, subtables in a table. A work budget is a count that every piece of work subtracts from, shared by everything a session does, so that limits which are safe one at a time can’t multiply ([Drawing outlines](drawing-outlines.html#the-budget) introduces them). The buffer’s `max_ops` and the sanitizer’s `max_ops` are older budgets of the same kind.

## What reaching a limit looks like

| What happens | How an application can tell |
|---|---|
| A table is rejected by the sanitizer | Only indirectly: the face behaves as if it had no such table, so `hb_ot_layout_has_substitution` and the like return false. `hb_face_reference_table` still returns the raw bytes. |
| The buffer is marked unsuccessful | `hb_buffer_allocation_successful` returns false. `hb_shape` returns nothing, and `hb_shape_full` still returns true for the `ot` backend ([hb_shape and its backends](hb_shape-and-its-backends.html#running-the-plan-and-failing)). |
| A rule, action, or step is skipped | It can’t: the output is a correct result for a font without that rule. |
| A glyph fails to draw or paint | `hb_font_draw_glyph_or_fail` and `hb_font_paint_glyph_or_fail` return false; the GPU encoders return `NULL`. |
| A subset fails | `hb_subset_or_fail` returns `NULL`. |
| A closure stops early | It can’t: the subset is missing glyphs, which shows only when the subset font is used. |

## Buffers and shaping

The buffer limits are set by `enter` when shaping starts and taken away by `leave` when it ends (`hb-buffer.cc:326`), and they scale with the length of the text. [Buffers](buffers.html#limits) describes them.

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_BUFFER_MAX_LEN_FACTOR`, `_MIN` | 256, 65,536 | glyphs the buffer may grow to, as a multiple of its length at the start, and at least this | `enlarge` fails and the buffer is marked unsuccessful (`hb-buffer.cc:161`) | [Buffers](buffers.html#limits) |
| `HB_BUFFER_MAX_LEN_DEFAULT` | 0x3FFFFFFF | the same, outside shaping, and during it when the multiplication overflows | the same | |
| `HB_BUFFER_MAX_OPS_FACTOR`, `_MIN` | 4,096, 65,536 | `max_ops`, the shaping work budget, per glyph, and at least this | the buffer is marked unsuccessful; remaining lookups do nothing | [Buffers](buffers.html#limits), [GSUB](gsub.html#context-and-chained-context) |
| `HB_BUFFER_MAX_OPS_DEFAULT` | 0x1FFFFFFF | the same, outside shaping | the same | |
| `HB_MAX_NESTING_LEVEL` | 64 | lookups nested inside contextual lookups | the buffer is marked unsuccessful (`hb-ot-layout-gsubgpos.hh:1145`) | [GSUB](gsub.html#context-and-chained-context) |
| `HB_MAX_NESTING_LEVEL` | 64 | chains of GPOS attachments, cursive or mark, resolved after positioning | the offset stops propagating; later glyphs in the chain are misplaced | [GPOS](gpos.html#a-limit-on-the-depth) |
| `HB_MAX_CONTEXT_LENGTH` | 64 | glyphs in a ligature, or in a context rule’s input | the rule never matches (`Ligature.hh:139`, `hb-ot-layout-gsubgpos.hh:1963`) | [GSUB](gsub.html#context-and-chained-context) |
| `HB_MAX_CONTEXT_LENGTH` | 64 | a context match that nested lookups have lengthened | the rule’s remaining nested lookups are skipped (`hb-ot-layout-gsubgpos.hh:2843`) | |
| `HB_MAX_SYLLABLE_LENGTH` | 64 | glyphs in one syllable, for the Indic, Khmer, Myanmar, and USE shapers | the syllable is reordered in pieces of 64, each as if it were a syllable (`hb-ot-layout.hh:174`) | [The Indic model](indic-model.html#a-limit-on-syllable-length), [Khmer and Myanmar](khmer-and-myanmar.html#syllables) |
| `HB_OT_SHAPE_MAX_COMBINING_MARKS` | 32 | a run of marks that normalization sorts by combining class | the run is left in the order typed (`hb-ot-shaper.hh:42`) | [Normalization](normalization.html#round-two-reorder) |
| `HB_OT_MAP_MAX_BITS` | 8 | mask bits for one feature’s value | values above 255 lose their high bits (`hb-ot-map.hh:35`) | [From features to lookups](from-features-to-lookups.html#mask-bits) |
| `HB_OT_MAX_TAGS_PER_SCRIPT`, `_PER_LANGUAGE` | 3, 3 | OpenType tags tried for one script or language | further tags are not tried (`hb-ot-layout.h:99`) | [Choosing a script shaper](choosing-a-script-shaper.html#from-a-script-to-script-tags) |
| `STCH_MAX_GLYPHS` | 256 | glyphs that Syriac `stch` stretching may add | tiles stop being repeated (`hb-ot-shaper-arabic.cc:572`) | [Joining scripts](joining-scripts.html#stretching-stch) |

The mark limit is cheap to show. Here an *a* is followed by 31 acutes and a dot below, a run of 32 marks, and then by 32 acutes and a dot below, a run of 33:

```shape
normalization/norm.ttf  a\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0323  --no-positions  --no-clusters
normalization/norm.ttf  a\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0301\u0323  --no-positions  --no-clusters
```

In the first, the dot below, of class 220, is sorted ahead of the acutes, of class 230, and comes out second. In the second, the run is too long to sort, and the dot below stays last.

### What `max_ops` is charged for

The budget is charged by the work a font controls: merging clusters, moving the output, setting masks over ranges (`hb-buffer.cc`, `hb-buffer.hh:657`), each nested lookup a contextual rule calls (`hb-ot-layout-gsubgpos.hh:1151`), the Indic shaper’s “would substitute” questions to the font (`hb-ot-layout.cc:1595`), and in AAT, a pass over the buffer for every subtable, every DontAdvance transition, and every insertion (next section). Once the buffer is unsuccessful, `apply_forward` stops at once (`hb-ot-layout.cc:1983`), and `sync`, which ends a lookup that writes its output separately, discards that output and keeps the glyphs from before the lookup (`hb-buffer.cc:432`). So the result is the text as far as shaping got, not a mixture.

Nesting is the surprise in the table. A contextual lookup that calls itself at the same position recurses until it is 64 deep, and then the whole buffer fails, not just that rule. The closure in the subsetter, which has its own copy of the limit, just stops following (`hb-ot-layout-gsubgpos.hh:77`).

### A budget that starts negative

`enter` computes the operation budget like this (`hb-buffer.cc:343`):

```c++
if (likely (!hb_unsigned_mul_overflows (len, HB_BUFFER_MAX_OPS_FACTOR, &mul)))
{
  int limit = (int) hb_max (mul, (unsigned) HB_BUFFER_MAX_OPS_MIN);
  max_ops = max_ops < HB_BUFFER_MAX_OPS_DEFAULT ? hb_min (max_ops, limit) : limit;
}
```

`mul` is unsigned. From a length of 524,288 characters, 4,096 times the length no longer fits in an `int`, and the cast makes it negative. Up to 1,048,575 characters, then, the budget is spent before shaping begins. From 1,048,576 the unsigned multiplication overflows too, the branch isn’t taken, and the budget stays at its default of about half a billion. Shaping `fi` repeated with `ligatures.ttf` (tried, not shown: the output is a million glyphs long) gives 262,143 ligatures for 524,286 characters, one ligature and then plain `f` and `i` for 524,290 and for 1,000,000 characters, and 524,286 ligatures again for 1,048,576. This looks like a bug: the line needs a clamp to `INT_MAX` before the cast. `hb-shape` doesn’t report the failure, since it doesn’t call `hb_buffer_allocation_successful`.

> Since {{hb}}: changed on HarfBuzz main by [`339aa68`](https://github.com/harfbuzz/harfbuzz/commit/339aa688fa4dfb4c38591a609f01fd8ca759afdb) (11 November 2026), which charges each lookup pass to the budget: it still starts negative, and 1,000,000 characters get no ligature at all, while 524,290 shape fully, probably because the budget overflows and wraps around.

## Sanitizing

The sanitizer checks a table once, when it is first loaded, and a table that fails is replaced by an empty one ([Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html)). All these limits have that consequence, the whole table and nothing less.

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_SANITIZE_MAX_OPS_FACTOR`, `_MIN`, `_MAX` | 64, 16,384, 0x3FFFFFFF | bytes checked, as a multiple of the table’s length, with a floor and a ceiling | every later check fails, and the table is rejected | [Sanitizer](trust-nothing-the-sanitizer.html#max_ops) |
| `HB_SANITIZE_MAX_SUBTABLES` | 16,384 | lookup subtables in a GSUB or GPOS table | the table is rejected | [Sanitizer](trust-nothing-the-sanitizer.html#max_ops) |
| `HB_MAX_NESTING_LEVEL` | 64 | nesting of COLR `Paint`s and of FeatureVariations `Condition`s | the table is rejected | [Sanitizer](trust-nothing-the-sanitizer.html#recursion) |
| `HB_AAT_MAX_SUBTABLES` | 1,024 | subtables in one `morx`, `mort`, `kerx`, or AAT `kern` | the table is rejected (`hb-aat-layout-morx-table.hh:1501`, `hb-aat-layout-kerx-table.hh:1154`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#before-the-loop), [Legacy kern](legacy-kern.html#two-tables-called-kern) |
| `HB_SANITIZE_MAX_EDITS` | 32 | nothing | never read | [Sanitizer](trust-nothing-the-sanitizer.html#whats-left-of-repairing) |

> Since {{hb}}: fixed on HarfBuzz main by [`9172214`](https://github.com/harfbuzz/harfbuzz/commit/91722141bb48a8414284cb3b4001b0c98cce9a19) (17 November 2026), which removes `HB_SANITIZE_MAX_EDITS` (the table’s last row).

The AAT limit is in the sanitizer for a reason its comment gives: the accelerator keeps one or two glyph sets per subtable, “which can take far more memory than the subtable has bytes” (`hb-limits.hh:95`). A rejected `morx` means the font is shaped as if it had none, with GSUB if it has one. The state machines that pass the sanitizer are then checked as they run, against a sanitizer context with the maximum budget (`hb-aat-layout.cc:71`; [The AAT tables](trust-nothing-the-sanitizer.html#the-aat-tables)).

## Layout queries and closure

These bound the walks that collect features and lookups, and the glyph closure the subsetter computes. They don’t apply during shaping, which builds its map another way.

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_CLOSURE_MAX_STAGES` | 12 | passes of the GSUB glyph closure: at most this plus 2, that is 14 | the closure stops, and glyphs that later passes would add are missing (`hb-ot-layout.cc:1700`) | [Subsetting](subsetting.html#why-fixed-stages-and-not-a-fixpoint) |
| `HB_MAX_LOOKUP_VISIT_COUNT` | 35,000 | lookups visited in one closure pass, or by the lookup closure; lookup indices written in a subset Feature | further lookups are not visited, or not written | |
| `HB_MAX_NESTING_LEVEL` | 64 | nested lookups followed by the closures | deeper lookups are not followed | [hb-depend](hb-depend.html#how-the-graph-is-built) |
| `HB_MAX_SCRIPTS` | 500 | scripts visited by `hb_ot_layout_collect_features` and `_collect_lookups`, and by the subsetter | the rest are not visited; in a subset, they are dropped (`hb-ot-layout.cc:1135`, `hb-ot-layout-common.hh:129`) | |
| `HB_MAX_LANGSYS` | 2,000 | language systems visited, in the same places | the same | |
| `HB_MAX_LANGSYS_FEATURE_COUNT` | 50,000 | feature indices summed over language systems, when the subsetter prunes duplicate language systems | the rest are not pruned (`hb-ot-layout-common.hh:107`) | |
| `HB_MAX_FEATURE_INDICES` | 8,000 | feature indices visited | the rest are not collected; in a subset, the language system is dropped | |

Every one of these fails quietly. A subset that hits one is smaller than it should be, and nothing reports it. The language-system limits exist because a table can point many script records at one LangSys, so that a walk which looks linear is quadratic.

### The comment on `HB_CLOSURE_MAX_STAGES`

The comment on the definition says the value “must be larger than the number of times `add_gsub_pause()` is called in a collect_features call of any shaper” (`hb-limits.hh:65`). The Indic shaper’s `collect_features_indic` calls it 14 times: once before `locl`, once before the basic features, once after each of the 11 basic features, and once before the presentation features (`hb-ot-shaper-indic.cc:249–265`). The USE shaper calls it 8 times, Arabic up to 12. The value is 12, which is smaller than 14, so the comment and the code disagree. As written, the loop runs at most 14 passes, which equals the Indic count rather than exceeding it, so the code may be right by accident; but the reasoning in the comment doesn’t support the number. [Subsetting](subsetting.html#where-the-fixed-order-misses) shows a chain that the 14 passes cut short.

> Since {{hb}}: fixed on HarfBuzz main by [`0209ec2`](https://github.com/harfbuzz/harfbuzz/commit/0209ec2865b55e892897966e95dfb8915a1309e9) (17 November 2026), which raises `HB_CLOSURE_MAX_STAGES` to 16, so main runs at most 18 passes.

## AAT

The AAT state machines are charged to the buffer’s `max_ops`, like the OpenType lookups, but in more places, since a state machine can loop where a lookup can’t.

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `max_ops`, per DontAdvance transition | the buffer’s budget | a state machine reading the same glyph again | DontAdvance is ignored and the machine moves on (`hb-aat-layout-common.hh:1436`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#the-loop) |
| `max_ops`, per subtable | the buffer’s length | a pass over the buffer for each subtable | the buffer is marked unsuccessful, and no later subtable runs (`charge_buffer_pass`, `hb-aat-layout-common.hh:171`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#the-loop) |
| `max_ops`, per insertion | glyphs inserted | `morx` Insertion | the insertion is not made (`hb-aat-layout-morx-table.hh:805`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#insertion) |
| `max_ops`, per kerning value | 1 | values read from a `kerx` format 1 action list | the buffer is marked unsuccessful (`hb-aat-layout-kerx-table.hh:309`) | |
| `max_ops`, per control-point attachment | 512 | `kerx` format 4 attachments to contour points, which may load whole outlines | the attachment is not made (`hb-aat-layout-kerx-table.hh:619`) | |
| `HB_MAX_CONTEXT_LENGTH` | 64 | glyphs between a Rearrangement’s first and last | nothing is rearranged (`hb-aat-layout-morx-table.hh:132`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#rearrangement) |
| `HB_MAX_CONTEXT_LENGTH` | 64 | the stack of glyphs a Ligature subtable has marked | the stack is circular: older positions are overwritten (`hb-aat-layout-morx-table.hh:601`) | |
| `HB_BUDGET_AAT_MAP` | 2²⁴ | compiling feature flags for ranges of text with different features | the last range compiled extends to the end of the text (`hb-aat-map.cc:161`) | [AAT inside HarfBuzz](aat-inside-harfbuzz.html#ranges) |

The DontAdvance case is the one to understand. The machine in `loop.ttf` never advances, so it spends the whole budget on one glyph; the loop ends, but the next subtable’s pass fails, the buffer is marked unsuccessful, and that subtable never runs. The [AAT chapter](aat-inside-harfbuzz.html#the-loop) shows it live.

## Drawing and painting

Drawing and painting have the most limits, because outlines, paint graphs, and renderers drive each other. Each format has structural limits, and since 14.5.0 a session also has a work budget, `HB_BUDGET_GLYPH`, which a client can set with `hb_draw_set_budget` or `hb_paint_set_budget` to a number, to `HB_BUDGET_DEFAULT`, or to `HB_BUDGET_UNLIMITED`, which leaves only the structural limits ([Drawing outlines](drawing-outlines.html#the-budget)).

### Outlines

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_MAX_NESTING_LEVEL` | 64 | composite glyphs nested, in `glyf` and VARC | the glyph fails | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| `HB_MAX_GRAPH_EDGE_COUNT` | 16,384 | glyphs one composite loads, counting repeats | the glyph fails (`Glyph.hh:345`, `VARC.hh:162`) | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| `HB_GLYF_MAX_POINTS` | 200,000 | points in one composite | the glyph fails (`Glyph.hh:558`) | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| `HB_CFF_MAX_OPS` | 200,000 | operators in one charstring, subroutines included; capped further by the remaining budget | the glyph fails (`hb-cff-interp-cs-common.hh:898`) | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| `kMaxCallLimit` | 10 | CFF subroutine nesting | the glyph fails (`hb-cff-interp-cs-common.hh:59`) | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| argument stack | 513 | numbers on a charstring’s stack | the glyph fails (`hb-cff-interp-common.hh:443`) | [Drawing outlines](drawing-outlines.html#limits-and-the-shared-budget) |
| `HB_VAR_COMPOSITE_MAX_AXES` | 4,096 | axis indices a VARC component may set, and coordinates it inherits | a higher index is ignored; above 4,096 inherited coordinates, the component starts from the font’s (`coord-setter.hh:25`, `VARC.cc:396`) | [Variable components](variable-components.html#step-4-the-components-coordinates) |
| `HB_BUDGET_GLYPH` | 2²⁴ | the work of one drawing or painting session | the work in hand fails, and everything after it in the session | [Drawing outlines](drawing-outlines.html#the-budget) |

A composite that contains itself is not a limit but a cycle, and only the component that closes the cycle is skipped. Every other outline limit fails the whole glyph, which then draws as nothing while its extents still come from its header; `hb-shape` and layout see an ordinary glyph.

### Color

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_MAX_NESTING_LEVEL` | 64 | depth of a COLR v1 paint graph while painting | deeper paints are not painted | [Color](color.html#guards) |
| `HB_MAX_GRAPH_EDGE_COUNT` | 16,384 | Paints visited for one glyph | no more are painted | [Color](color.html#guards) |
| `HB_PAINT_MAX_SWEEP_TILES` | 4,096 | tiles one repeating or reflecting sweep gradient is cut into | below an angle of 2π/4,096 per repeat, the circle is filled with the average color; beyond 4,096 tiles, tiling stops (`hb-paint.cc:1220`, `:1280`) | |
| `dupe` chain | 8 | `sbix` records that point at another glyph’s image | the image isn’t found (`sbix.hh:121`) | [Color](color.html#bitmaps-sbix-and-cbdt) |
| `HB_SVG_MAX_DOCUMENT_SIZE` | 16 MiB | one SVG document, after decompression | the document isn’t returned (`svg.hh:63`, `:78`) | |
| `MAX_DEPTH` | 128 | elements nested in an SVG document, when HarfBuzz indexes it by glyph | the document isn’t indexed (`svg.hh:590`), so (inferred) its glyphs aren’t found | |

### Renderers

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_RASTER_MAX_DRAW_EDGES` | 2²⁰ | edges in one hb-raster draw session | drawing stops | [hb-raster](hb-raster.html#limits) |
| `HB_RASTER_MAX_AUTO_DIMENSION` | 4,096 | pixels a side, when the size comes from the font, including a PNG’s header | the surface is clamped; the PNG isn’t decoded | [hb-raster](hb-raster.html#limits) |
| `HB_RASTER_MAX_BUFFER_SIZE` | 1 GiB | one image’s or clip’s buffer | it isn’t allocated | [hb-raster](hb-raster.html#limits) |
| `HB_BUDGET_RASTER_PIXELS`, `_PAINT_PASSES` | 2²⁶, 4 | pixel work: the larger of the first and that many passes over the surface | the image is left blank | [hb-raster](hb-raster.html#the-pixel-budget) |
| `HB_VECTOR_MAX_DOCUMENT_SIZE` | 16 MiB | one SVG or PDF document from hb-vector | the buffer stops growing and drawing stops | [hb-vector](hb-vector.html#limits) |
| transform depth | 64 | transforms nested in hb-vector’s SVG output | further ones are ignored (`hb-vector-paint-svg.cc:372`) | [hb-vector](hb-vector.html#limits-for-color-glyphs) |
| `HB_GPU_DRAW_MAX_CURVES` | 65,536 | curves in one hb-gpu glyph | the encoding fails (`hb-gpu-draw.cc:58`) | [hb-gpu](hb-gpu.html#limits-on-outlines) |
| `HB_GPU_CU2QU_MAX_DEPTH` | 10 | subdivisions of a cubic into quadratics | the last piece is used as it is (`hb-gpu-cu2qu.hh:187`) | [hb-gpu](hb-gpu.html#limits-on-outlines) |
| `HB_GPU_PAINT_MAX_OPS`, `_GROUP_DEPTH`, `_CLIP_DEPTH`, `_SUB_BLOBS` | 32,767, 4, 3, 1,024 | an hb-gpu color glyph’s operations, nested groups, clips per layer, clip blobs | the encoder returns `NULL` (`hb-gpu-paint.cc:51`) | [hb-gpu](hb-gpu.html#limits-on-color-glyphs) |
| `HB_GPU_PAINT_MAX_SUB_BYTES` | 64 MiB | bytes of clip outlines and color stops in one hb-gpu paint | the same (`hb-gpu-paint.hh:276`) | [hb-gpu](hb-gpu.html#limits-on-color-glyphs) |

The rule that runs through the renderers is in a comment on `HB_RASTER_MAX_AUTO_DIMENSION`: sizes that come from the font are capped, but sizes the client sets with `hb_raster_draw_set_extents` aren’t. The font is the attacker; the client is trusted with its own allocations.

## Subsetting and instancing

A subset either succeeds or fails as a whole: when any table fails, `hb_subset_or_fail` returns `NULL` (`hb-subset.cc:495`). Closure limits are the exception, since a closure that stops early fails nothing.

| Limit | Value | What it bounds | When reached | Chapter |
|---|---|---|---|---|
| `HB_MAX_NESTING_LEVEL` | 64 | composite components followed when collecting glyphs | deeper components are not retained (`hb-subset-plan.cc:410`) | [Subsetting](subsetting.html#the-glyph-closure-stage-by-stage) |
| `HB_MAX_COMPOSITE_OPERATIONS_PER_GLYPH` | 64 | components followed from each glyph, times the number of glyphs | the same | [Subsetting](subsetting.html#the-glyph-closure-stage-by-stage) |
| `HB_SUBSET_GLYF_MAX_BYTES_FACTOR` | 16 | bytes of all retained glyphs, as a multiple of the `glyf` table | the plan fails (`hb-subset-plan.cc:516`) | [Subsetting](subsetting.html#the-glyph-closure-stage-by-stage) |
| `HB_BUDGET_SUBSET_GLYF` | 2²⁸ | work to instance every retained `glyf` glyph | the `glyf` table fails (`glyf.hh:128`) | |
| `HB_SUBSET_CBDT_MAX_COPY_FACTOR` | 64 | bytes copied out of `CBDT`, as a multiple of its length | the table fails (`CBDT.hh:460`) | |
| table buffer | 256 × the source table | the buffer a table is written into, doubled each time it runs out | the table fails (`hb-subset-table.hh:61`) | [Writing tables](writing-tables.html#when-writing-fails) |
| `HB_REPACKER_MAX_VERTICES` | 800,000 | objects in the repacker’s graph, including duplicates | repacking fails, and so does the table (`graph/graph.hh:577`) | [Writing tables](writing-tables.html#the-graph) |
| `HB_REPACKER_MAX_SPACES` | 8,000 | spaces reached through 32-bit offsets | the same (`graph/graph.hh:978`) | [Writing tables](writing-tables.html#32-bit-offsets-and-spaces) |
| `HB_REPACKER_MAX_ITERATIONS` | 500 | rounds of the repacker | it stops; if offsets still overflow, the table fails (`hb-repacker.hh:422`) | [Writing tables](writing-tables.html#round-by-round) |
| `MAX_GRID` | 2¹⁴ | grid points used to find a variation’s exact extremes when limiting an axis | a looser, still conservative, estimate is used (`hb-subset-plan-var.cc:183`) | |

The nesting and operation limits share one weakness. A component that wasn’t retained keeps its old glyph ID when its composite is written (`SubsetGlyph.hh:55`), so in the subset it points at whatever glyph now has that ID, or at none (inferred). This needs a composite more than 64 levels deep, which no renderer would draw anyway.

## Limits that cost only speed

Two limits change nothing visible. `HB_CBDT_MAX_INDEX_ENTRIES`, 65,536, caps the index HarfBuzz builds to find a glyph’s bitmap in `CBLC`; a strike that would pass it is searched linearly instead (`CBDT.hh:940`). `max_shared_tuple_count`, 4,096, caps the cache of `gvar`’s shared tuple scalars (`hb-ot-var-gvar-table.hh:645`).

## Limits defined but unused

`HB_SVG_MAX_PATH_SEGMENTS` (262,144, `hb-limits.hh:130`) appears nowhere else in the source, nor in `util/` or the tests. `HB_SANITIZE_MAX_EDITS` (32) is left over from the time the sanitizer repaired fonts. `HB_REPACKER_MAX_VERTICES` is used, but also by `test-repacker.cc`, which fills a graph to the limit to check it.

> Since {{hb}}: fixed on HarfBuzz main by [`9172214`](https://github.com/harfbuzz/harfbuzz/commit/91722141bb48a8414284cb3b4001b0c98cce9a19) (17 November 2026), so main no longer defines `HB_SVG_MAX_PATH_SEGMENTS` or `HB_SANITIZE_MAX_EDITS`.

## Changing a limit

Every limit in `hb-limits.hh`, and the sanitizer’s in `hb-sanitize.hh:107`, is wrapped in `#ifndef`, so a build can set its own value by defining the macro first, with `-DHB_MAX_NESTING_LEVEL=128` or in a configuration header ([Compile-time configuration](compile-time-configuration.html)). The exceptions are the fixed weights `HB_BUDGET_1` to `HB_BUDGET_8192`, which `hb-limits.hh:211` asks to be left alone (“tune the common session cap, not these values”), and everything defined outside these two headers: `HB_OT_SHAPE_MAX_COMBINING_MARKS`, `HB_OT_MAP_MAX_BITS`, the hb-gpu limits, `kMaxCallLimit`, the CFF argument stack, `STCH_MAX_GLYPHS`, the 256 × table buffer, and the SVG depth are plain definitions or literals, and changing them means changing the source. `HB_OT_MAX_TAGS_PER_SCRIPT` and `_PER_LANGUAGE` are public API, sizes for arrays that callers allocate.

At run time, only the drawing and painting budget can be changed, through `hb_draw_set_budget` and `hb_paint_set_budget`. There is no API for the buffer’s limits.

Most limits have grown over the years as real fonts reached them. `NEWS` records the buffer’s work limits raised in 2.7.3, “to handle fonts with many complex lookups”, and its length limits in 11.4.2, “for better handling of fonts that generate huge number of glyphs per codepoint (e.g. Noto Sans Duployan)”; the CFF operand limit raised twentyfold in 10.1.0; and, going the other way, nesting reduced “from 8 to 6” in 1.0.6.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-limits.hh` | most limits and budgets, with comments, and `hb_budget_spend` |
| `src/hb-sanitize.hh` | the sanitizer’s budgets and `check_start_recursion` |
| `src/hb-buffer.cc` | `enter` and `leave`, `enlarge`, and the operations charged to `max_ops` |
| `src/hb-ot-layout-gsubgpos.hh` | nesting and context length during shaping, and the closure contexts |
| `src/hb-ot-layout.cc` | the GSUB closure loop, and the script and language-system counts |
| `src/hb-aat-layout-common.hh`, `src/hb-aat-layout-morx-table.hh` | the AAT driver’s charges, and the subtable limit |
| `src/OT/glyf/Glyph.hh`, `src/hb-cff-interp-cs-common.hh` | the outline limits |
| `src/hb-paint.cc`, `src/OT/Color/COLR/COLR.hh`, `src/OT/Color/svg/svg.hh` | the color limits |
| `src/hb-raster-*.cc`, `src/hb-vector-*.cc`, `src/hb-gpu-*.cc` | the renderers’ limits |
| `src/hb-subset-plan.cc`, `src/hb-subset-table.hh`, `src/graph/graph.hh` | the subsetter’s and repacker’s limits |
| `src/hb-common.h`, `src/hb-draw.h`, `src/hb-paint.h` | `HB_BUDGET_DEFAULT`, `HB_BUDGET_UNLIMITED`, and the budget API |

## In short

* No limit crashes, but the outcomes differ: a table rejected, a buffer marked unsuccessful, a rule skipped, a glyph left blank, a subset failed or quietly incomplete.
* An application can detect a failed buffer with `hb_buffer_allocation_successful`, a failed glyph with the `_or_fail` functions, and a failed subset by its `NULL`. Skipped rules and truncated closures can’t be detected.
* Lookup nesting past 64 fails the whole buffer, not just the rule. AAT state machines charge the same budget, and a loop can starve later subtables.
* From 524,288 to 1,048,575 characters, the buffer’s operation budget starts negative, and shaping stops almost at once: probably a bug.
* `HB_CLOSURE_MAX_STAGES` is 12, though its comment requires it to exceed the Indic shaper’s 14 pauses. `HB_SVG_MAX_PATH_SEGMENTS` and `HB_SANITIZE_MAX_EDITS` are unused.
* The limits in `hb-limits.hh` and `hb-sanitize.hh` can be changed at build time; the others are fixed in the source. Only the drawing and painting budget can be changed at run time.

> Since {{hb}}: fixed on HarfBuzz main by [`0209ec2`](https://github.com/harfbuzz/harfbuzz/commit/0209ec2865b55e892897966e95dfb8915a1309e9) and [`9172214`](https://github.com/harfbuzz/harfbuzz/commit/91722141bb48a8414284cb3b4001b0c98cce9a19) (17 November 2026), so main has `HB_CLOSURE_MAX_STAGES` at 16 and neither unused limit (the item on `HB_CLOSURE_MAX_STAGES`).
