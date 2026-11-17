# Survey: reading, writing and rendering font data (HarfBuzz 15.1.0)

Scope: table-reading machinery, variations, outlines and colour, the output
libraries (raster/vector/GPU), subsetting/instancing/repacking/depend, and
testing/robustness. GSUB/GPOS lookups, the shaping pipeline, script shapers and
AAT are excluded.

All paths are relative to the checkout's `src/` unless they start with
`docs/`, `test/` or a top-level file. Line numbers are for the 15.1.0 checkout
(commit `3df40d9`). "(inferred)" marks conclusions I drew rather than read.

---

## 0. Things older descriptions get wrong (read this first)

| Topic | Old belief | 15.1.0 reality | Evidence |
|---|---|---|---|
| Sanitizer edits | Sanitize "neuters" bad offsets in place (writable blob, `may_edit`, `HB_SANITIZE_MAX_EDITS`) | No editing at all. A table that fails `sanitize()` is replaced by the empty blob. `HB_SANITIZE_MAX_EDITS` is still `#define`d (hb-sanitize.hh:108) but nothing reads it | hb-sanitize.hh:97-102 (the "Note:" in the header comment), `sanitize_blob` hb-sanitize.hh:405-438; NEWS 12.3.0 ("Invalid font tables (eg. GSUB/GPOS) are outright rejected") |
| Kahn's algorithm in repacker | docs/repacker.md: Kahn first, then shortest-distance | Only `sort_shortest_distance()` exists; no Kahn anywhere in code | `grep -i kahn` hits only docs/repacker.md; hb-repacker.hh:407 |
| Raster/vector SVG glyphs | 13.1.1 added SVG-in-OT rendering to raster and vector | Dropped in 14.2.0. Their `image` callbacks accept only PNG/BGRA; an SVG image returns false so painting falls through | hb-raster-paint.cc:1002,1022; hb-vector-paint-svg.cc:643; NEWS 14.2.0 |
| Raster/vector/GPU status | "experimental" | Stable API/ABI since 15.0.0 | NEWS 15.0.0 |
| Beyond-64K and cubic `GLYF` | experimental, off by default | On by default since 15.0.0; only `HB_MINI` disables them | hb-config.hh:93-97; NEWS 15.0.0 |
| `avar` v2 instancing | full instancing only (12.3.0) | Partial instancing too (14.3.0) | AVAR2-INSTANCING.md; hb-ot-var-avar-table.hh:803 `_subset_avar2` |
| Work limits | per-subsystem limits only | Cumulative **budgets** (14.5.0) shared across nested draw/paint/VARC/glyf/CFF work, exposed through public `hb_draw_*_budget` / `hb_paint_*_budget` | hb-limits.hh:197-282; hb-draw.hh:41-43,197-200 |
| hb-depend | n/a (new) | Experimental, compiled only with `-Dexperimental_api=true` (`HB_NO_SUBSET_DEPEND` otherwise) | hb-config.hh:38-40; docs/depend-api.md:27 |

Doc/code mismatches a book should not copy:
* docs/repacker.md:86-94 (Kahn) is stale (see above).
* docs/serializer.md:107 links to `reapcker.md` (typo).
* test/fuzzing/README.md says the depend fuzzer needs `-Ddepend_api=true`; the
  real meson option is `experimental_api` (meson_options.txt:65).
* The `hb-sanitize.hh` header comment still says sanitize returns "either the
  sanitized blob, or empty blob", which is correct; but its name history ("used
  to try to recover from errors by modifying the data") is the only remaining
  trace of edit-on-sanitize.

---

## 1. The table-reading machinery

### Key files

* `hb-open-type.hh` (2173 lines): the OpenType data types.
* `hb-null.hh`, `hb-static.cc:51-61`: Null and Crap pools.
* `hb-machinery.hh`: `StructAtOffset`/`StructAfter`, `DEFINE_SIZE_*`, lazy loaders.
* `hb-sanitize.hh`: the sanitizer.
* `hb-dispatch.hh`: the generic dispatch context (60 lines).
* `hb-open-file.hh`: the sfnt container (TTC, dfont, OTTO, 'true', 'typ1').
* `hb-ot-face.hh`, `hb-ot-face-table-list.hh`, `hb-ot-face.cc`: per-face lazy tables.
* `hb-ot-dual.hh`: `SmallTypes`/`MediumTypes` and the beyond-64K "dual" accelerator.
* `hb-face.cc`, `hb-face-builder.cc`, `hb-blob.cc`.

### The "struct over bytes" idiom

* Integer types are `NumType<BE, Type, Size>` (hb-open-type.hh:57-113),
  typedef'd as `HBUINT8/16/24/32/64`, `HBINT*`, little-endian `*LE` variants
  and float types (hb-open-type.hh:115-137). Storage is a byte array
  (`HBInt` in hb-algs.hh, with a bswap fast path under `HB_FAST_NUM_ACCESS`),
  so structs have **no alignment requirement** and can be laid directly over
  mmap'd font bytes. Conversion out is via `operator WideType ()`.
* There is no signed 24-bit type, on purpose (comment at hb-open-type.hh:123).
* `HBUINT32VAR` (hb-open-type.hh:149-232) is a 1–5-byte variable-length
  integer (prefix-coded in the top bits of the first byte), used by VARC.
* Fixed types: `HBFixed<Type, bits>` with `F2DOT14`, `F4DOT12`, `F6DOT10`,
  `F16DOT16` (hb-open-type.hh:246-269).
* `Offset<Type, has_null>` and `OffsetTo<Type, OffsetType, BaseType, has_null>`
  (hb-open-type.hh:326-539). `base+offset` (friend `operator+`) resolves an
  offset; a zero offset yields `Null(Type)` (const) or `Crap(Type)` (mutable).
  `NNOffsetTo` (non-nullable) variants exist. A `static_assert`
  (hb-open-type.hh:417) refuses nullable offsets to types whose Null object
  can't be safely defined.
* Arrays: `UnsizedArrayOf` (556), `ArrayOf<Type, LenType>` (712) with
  `Array16Of/24Of/32Of`, `HeadlessArrayOf` (898; count includes the implicit
  first element), `ArrayOfM1` (994; count minus one), `SortedArrayOf` (1048)
  with binary search, `BinSearchArrayOf`, `VarSizedBinSearchArrayOf` (1168,
  AAT), `CFFIndex<COUNT>` (1261), and `TupleValues` (1506) / `TupleList` (2134)
  — the packed-delta codec shared by gvar/cvar/VARC/MultiItemVariationStore.
* Size declarations (hb-machinery.hh:~112-140): `DEFINE_SIZE_STATIC`,
  `DEFINE_SIZE_MIN`, `DEFINE_SIZE_ARRAY`, `DEFINE_SIZE_UNION`,
  `DEFINE_SIZE_UNBOUNDED`. They create `static_size`/`min_size`/`null_size`
  that the sanitizer (`check_struct` uses `min_size`) and the Null machinery
  read via SFINAE (hb-null.hh:42-107).
* `hb-ot-dual.hh:38-74`: `Layout::SmallTypes` (16-bit glyph ids/offsets) and
  `MediumTypes` (24-bit glyph ids and offsets, 32-bit "long" offsets) let a
  single template body produce both the classic tables and the OFF 5th-edition
  beyond-64K ones (`gvar`/`GVAR`, `glyf`/`GLYF`, `hmtx`/`HMTX`, 24-bit
  GSUB/GPOS formats, COLR `PaintGlyph2` = format 33).

### Null objects (hb-null.hh)

* `_hb_NullPool` is a 640-byte all-zero static array (`HB_NULL_POOL_SIZE`,
  hb-null.hh:39; defined hb-static.cc:51). `Null(T)` reinterprets it as a `T`.
  Because counts and offsets in a zeroed struct are 0, a Null table "behaves
  like an empty table" with no branches at call sites.
* Types whose zero bytes would mean something wrong get explicit Null bytes
  (hb-static.cc:54-61): `Index` and `VarIdx` are all 0xFF (= "no index"),
  `LangSys` has reqFeatureIndex 0xFFFF, `RangeRecord`/`ClipRecord` start with
  0x01 (so start > end, an empty range), etc.
* `Crap(T)` (hb-null.hh:165-188) is a *writable* scratch copy of Null, used
  when code writes through a null offset. Deliberately not thread-local (it
  "only exists to catch and divert program logic bugs", hb-null.hh:166-169).
* `hb_nonnull_ptr_t` (hb-null.hh:196-218) is a pointer that reads as Null when nullptr.
* Not every struct can be nullable: a struct that defines `min_size` but not
  `null_size` is declaring itself non-nullable (hb-null.hh:61-63).

### Sanitizing (hb-sanitize.hh)

* Contract (header comment, hb-sanitize.hh:69-96): `sanitize()` returns true iff
  it is safe to call the object's other methods. What it checks depends on what
  the accessors assume: GSUB/GPOS/GDEF check every offset up front (simpler
  accessors); glyf/loca do **not** (O(1) load, checks at glyph load), because
  checking loca would cost O(num-glyphs).
* `hb_sanitize_context_t` (123) is a dispatch context returning bool.
  `sanitize_blob<T>` (405-438) casts the blob to `T*`, calls `t->sanitize(this)`,
  and on failure destroys the blob and returns `hb_blob_get_empty()`. On
  success it makes the blob immutable. `reference_table<T>` (441) also sets
  `num_glyphs` from the face first, so tables can range-check glyph ids.
* Work limits:
  * `max_ops` is set in `start_processing` (230-252) to `length × 64` clamped
    to [16384, 0x3FFFFFFF] (`HB_SANITIZE_MAX_OPS_*`, 111-119). Note that
    `check_range` (276-294) decrements `max_ops` **by the number of bytes
    checked**, not by one per call, so the budget is "bytes examined ≈ 64×
    table size".
  * `max_subtables` with `HB_SANITIZE_MAX_SUBTABLES` 0x4000 via
    `visit_subtables` (147-151).
  * `check_start_recursion`/`end_recursion` (380-390) bound recursion.
  * `check_range_fast` skips the ops charge; `check_struct` (393-402) only
    checks a pointer on 64-bit (since `min_size` is small, it relies on the
    one-past check) (inferred from code shape).
  * Multiplications use `hb_unsigned_mul_overflows` (check_range overloads 334-354).
* `hb_barrier()` (hb-atomic.hh:188) is a compiler read barrier inserted after
  every `check_*` and before using a format/version switch (e.g.
  hb-open-type.hh:180-186, hb-open-file.hh:281). Its purpose, as I read it, is
  to stop the compiler from hoisting reads of not-yet-validated data above the
  check (inferred; no comment states it).
* `set_object`/`hb_sanitize_with_object_t` (191-226, 455-466) temporarily
  narrow the sanitize range to one sub-object (used e.g. by CFF).
* `lazy_some_gpos` (hb-sanitize.hh:470): the GSUB/GPOS accelerator sets it
  (hb-ot-layout-gsubgpos.hh:6713) so that heavy GPOS value-record checks
  (PairSet, PairPosFormat2, ValueFormat, Anchor, Cursive) are skipped at load
  and done lazily at apply time. So the "check everything up front for GPOS"
  rule now has exceptions (OT/Layout/GPOS/PairSet.hh:112 etc.).
* Since 12.3.0 a failed table is dropped entirely, matching Core Text and not
  DirectWrite/HarfRust (NEWS). A side effect noted in NEWS 13.0.0: overly
  strict checks then reject whole tables (cmap regression fixed).

### Dispatch (hb-dispatch.hh)

* `hb_dispatch_context_t<Context, Return, MaxDebugDepth>` (CRTP): every table
  struct implements `template <typename context_t> dispatch(context_t *c)`, and
  format unions switch on `u.format` and forward to `c->dispatch(u.formatN)`.
  `may_dispatch` lets the sanitizer check the format field before switching
  (hb-sanitize.hh:136-141). The same tables are thereby walked by
  sanitize, subset, closure, collect-glyphs, apply, depend, etc. (one schema,
  many visitors). The sanitizer's own `_dispatch` prefers `obj.sanitize(...)`
  and falls back to `obj.dispatch(...)` via `hb_priority` (hb-sanitize.hh:154-165).
* COLR `Paint` is a good example of a big format switch (OT/Color/COLR/COLR.hh:~2280-2320).

### Container (hb-open-file.hh)

* `OpenTypeFontFile` (485) switches on the first tag: 'OTTO', 0x00010000,
  'true', 'typ1' (single face), 'ttcf' (TTC), 0x00000100 (Mac dfont resource fork).
* `TTCHeaderVersion1` (219-262): with `version.minor >= 1` (OFF 5th ed.
  "extended TTC"), a second directory list follows the first (plus a 12-byte
  gap for major version 2) and is the one used.
* `OpenTypeOffsetTable::serialize` (~120-200) writes a font, computing table
  checksums and `head.checkSumAdjustment = 0xB1B0AFBA − sum`.
* Face index: low 16 bits are the TTC face index; the upper bits select a named
  instance (hb-face.cc:170, 293; hb-font.cc:2156 `(face->index >> 16) - 1`).
  15.1.0 fixed `hb_face_create_or_fail()` rejecting indices with named-instance bits set.

### Lazy table loading (hb-machinery.hh, hb-ot-face.hh)

* `hb_ot_face_t` (hb-ot-face.hh:46-71) is generated by X-macros from
  `hb-ot-face-table-list.hh`: each table becomes an
  `hb_table_lazy_loader_t<T, ORDER>` (a sanitized blob) or each accelerated
  table an `hb_face_lazy_loader_t<T_accelerator_t, ORDER>`.
* **Pointer-math trick**: loaders don't store a face pointer. `hb_face_t *face`
  is declared immediately before the loaders ("MUST be JUST before",
  hb-ot-face.hh:61), and each loader finds it at
  `((Data **) this) - WheresData` where `WheresData` is the table's ordinal in
  the enum (hb-machinery.hh:155-167). One pointer per table, no back-pointer.
* `hb_lazy_loader_t::get_stored` (hb-machinery.hh:230-250) is lock-free:
  acquire-load; if null, create; publish with `cmpexch(nullptr, p)`; on a race,
  destroy own copy and retry. Failures are cached as a *tagged* Null pointer
  (low bit set, `tag_null`, 273-284) so a failed load isn't retried and so a
  per-library Null object from another library is still recognized.
* `hb_table_lazy_loader_t::create` (330-335) is just `hb_sanitize_context_t().reference_table<T>(face)`.
* What's **not** in the list: HVAR/VVAR (loaded inside the hmtx/vmtx
  accelerators, hb-ot-hmtx-table.hh:486,496), `GLYF`/`LOCA` (loaded by the glyf
  accelerator itself), the `GVAR` dual (gvar accelerator). JSTF and opbd are
  commented out.
* `hb_dual_accelerator_t<Lower, Upper>` (hb-ot-dual.hh:78-110): if the
  uppercase (beyond-64K) table has data, the lowercase one is initialized from
  the *empty face* — the classic table is ignored entirely.

### Suggested sections

1. Bytes in memory: blobs, mmap, immutability, sub-blobs.
2. Types over bytes: NumType, fixed types, offsets, arrays, the size macros.
3. Null and Crap: why HarfBuzz code rarely checks for missing tables.
4. Sanitize: the contract, what is checked when, budgets, `hb_barrier`, and
   the 12.3.0 shift from "repair" to "reject" (with the harfbust history).
5. Dispatch: one schema, many visitors (sanitize/subset/closure/apply/depend).
6. The container: sfnt, TTC (incl. extended TTC), dfont; face indices and
   named-instance bits.
7. Lazy loading and accelerators: the pointer-math loader, lock-free
   publication, tagged nulls; beyond-64K dual tables.

---

## 2. Variations

### Key files

* `hb-ot-var-fvar-table.hh` (`fvar` 272; `AxisRecord::normalize_axis_value` 185-198).
* `hb-ot-var-avar-table.hh` (`SegmentMaps` 150, `avarV2Tail` 47, `avar::map_coords_16_16` 545-596, `_subset_avar2` 803).
* `hb-ot-var-gvar-table.hh` (`gvar_GVAR<T, Types>` 318, `accelerator_t` 639, `apply_deltas_to_points` 769, `gvar`/`GVAR` 1074-1082, `gvar_accelerator_t` 1084).
* `hb-ot-var-cvar-table.hh` (`cvar` 40, `add_cvt_and_apply_deltas` 172).
* `hb-ot-var-hvar-table.hh` (`HVARVVAR` 317, `get_advance_delta_unscaled` 436), `hb-ot-var-mvar-table.hh` (`MVAR` 72, `get_var` 132).
* `hb-ot-var-common.hh` (2482 lines): `TupleVariationHeader` 40 (`calculate_scalar` 113), `tuple_delta_t` 276, `TupleVariationData` 937, `item_variations_t` 1788 — the last two are mostly for *writing* (instancing).
* `hb-ot-layout-common.hh`: the item variation store lives here, not in var-common: `VarRegionAxis` 2547, `SparseVarRegionAxis` 2594, `hb_scalar_cache_t` 2637, `VarRegionList` 2728, `VarData` 3054, `MultiVarData` 3442, `ItemVariationStore` 3553, `MultiItemVariationStore` 3858, `DeltaSetIndexMap` 4126, `ItemVarStoreInstancer` 4209.
* `OT/Var/VARC/` (`VARC.hh`, `VARC.cc`, `VARC-subset.hh`, `coord-setter.hh`).
* `hb-font.cc` (coords on the font), `hb-ot-var.cc` (`hb_ot_var_normalize_coords` 323).

### How normalized coords flow into a font

1. `hb_font_set_variations` / `set_variation` / `set_var_coords_design` /
   named instance (hb-font.cc:~3100-3250) build a full design-coordinate array
   (starting from fvar defaults or the named instance), then call
   `hb_ot_var_normalize_coords`.
2. `hb_ot_var_normalize_coords` (hb-ot-var.cc:323-337): fvar normalization
   (clamp to [min,max], piecewise-linear to [-1,1]) in **16.16**, then
   `avar->map_coords_16_16`, then rounding to **2.14** (`(v + 2) >> 2`).
   Doing avar in 16.16 keeps precision through avar v2 (inferred motive).
3. `avar` v1: `SegmentMaps::map_float` (hb-ot-var-avar-table.hh:152-~260) is a
   deliberately *extended* version of the spec ("CoreText is wild... PingFangUI
   avar needs all this special-casing", 172-176): it tolerates maps with fewer
   than 3 entries, repeated boundary entries, and runs of identical
   `fromCoord`s (fixed in 14.4.0).
4. `avar` v2 (545-596): after the v1 segment maps, every axis gets
   `delta = varStore.get_delta(varIdxMap.map(i), coords_2_14)`; the delta is
   computed from the **v1-mapped coords of all axes**, added unclamped, and
   only the result is clamped to [-1,1] ("matching fontTools"). So avar2 lets
   any axis's final position depend on all the others.
5. `_hb_font_adopt_var_coords` (hb-font.cc:2166-2180) stores `coords` (int
   2.14), `design_coords`, `has_nonzero_coords`, and bumps the font serial so
   caches (advance caches, gvar scalar caches) invalidate.
6. Consumers read `font->coords` directly: gvar (glyph points), HVAR/VVAR
   (advances), MVAR (`hb-ot-metrics.cc:68,117`), GDEF/GPOS device tables,
   CFF2 blends, COLRv1 variable paints, VARC, `FeatureVariations`.

### Item Variation Store (IVS)

* `VarRegionAxis::evaluate` (hb-ot-layout-common.hh:2549-2573): the standard
  tent, plus robustness: invalid regions (start>peak, peak>end, or a region
  crossing zero) evaluate to **1** (i.e. ignore the axis), not 0.
* `VarData` stores word/byte (and with the LONG_WORDS bit, 32/16-bit) delta
  rows; `get_delta` multiplies each region's scalar by its delta.
* `hb_scalar_cache_t` (2637-2726): a per-call array of region scalars, NaN
  meaning "not computed", atomics so it can be shared; up to 128 entries on
  the stack (`STATIC_LENGTH`). Created per font/coords and cached in
  `hb_ot_font_t` (hb-ot-font.cc:78-111 acquire/release pattern).
* `DeltaSetIndexMap` (formats 0/1) maps glyph/axis indices to (outer, inner).
* `MultiItemVariationStore`/`MultiVarData`/`SparseVarRegionList`: a newer IVS
  whose rows are *vectors* of deltas (TupleList = CFF2Index of TupleValues),
  used by VARC. 14.6.0 changed it to a "revised variation-store format
  incompatible with the previous one" (NEWS).

### gvar (and GVAR)

* `gvar_GVAR<T, Types>` is one template for both `gvar` (16-bit glyph count)
  and OFF5 `GVAR` (24-bit). `gvar_accelerator_t` is a dual.
* `apply_deltas_to_points` (hb-ot-var-gvar-table.hh:769-~1000): iterate tuple
  variations; `calculate_scalar` (hb-ot-var-common.hh:113-207); skip zero
  scalars; decode shared or private point numbers; decode x then y deltas;
  apply to all points or accumulate per referenced point and then run IUP
  (`infer_delta`, 664-685) on unreferenced points per contour.
* Fast paths a book should mention:
  * When a tuple applies to all points and no tuple in the glyph has private
    points, deltas are added straight into the points as they're decoded
    (`decompile_deltas_add_to_points`, 693-765) — no intermediate arrays.
  * Shared-tuple scalars are cached per font (scalar cache sized to
    `min(sharedTupleCount, 0x1000)`). **Intermediate tuples are not cached**
    against the shared index, because the intermediate region belongs to the
    tuple, not the shared peak (hb-ot-var-common.hh:146-152). 15.1.0's NEWS
    "Fix wrong outlines in gvar fonts with intermediate tuples" is very likely
    this (inferred).
  * For ≥16 axes it skips zero peaks four at a time with a 64-bit read (171-184).
  * `phantom_only` mode only computes the four phantom points (used for
    variable advances without HVAR).
* `TupleValues` supports a `VALUES_ARE_LONGS` (0xC0) run type (32-bit deltas)
  in addition to bytes/words/zeros (hb-open-type.hh:1506-1514). This is not in
  the classic OpenType `gvar` packed-delta spec (inferred: comes from the
  VARC/OFF5 TupleValues encoding, and the gvar decoder accepts it too).

### Advances: HVAR or phantom points

`hb-ot-font.cc:436-499`: horizontal advances use HVAR if present; otherwise,
if gvar is present, glyf's **phantom points** with gvar deltas
(`glyf.get_advance_with_var_unscaled`, 484); otherwise unvaried hmtx. Same for
vertical (562-609). Phantom points are built in `Glyph::get_points`
(OT/glyf/Glyph.hh:392-414) from hmtx/vmtx and the glyph bbox.

### cvar

HarfBuzz doesn't hint, so `cvar` is only used by the subsetter/instancer: when
fully instancing, deltas are applied into `cvt ` (hb-subset.cc:349-356,
`cvar::add_cvt_and_apply_deltas`). Its table entry in hb-ot-face exists for that.

### VARC (variable composites)

* Spec: boring-expansion-spec VARC.md (comment at OT/Var/VARC/VARC.hh:21).
  Enabled by default since 12.0.0; `HB_NO_VAR_COMPOSITES` disables it.
* Table: `coverage`, `MultiItemVariationStore varStore`, `ConditionList`,
  `TupleList axisIndicesList`, `CFF2Index glyphRecords` (VARC.hh:306-312).
* A glyph record is a sequence of `VarComponent`s, each a packed record with
  flags (VARC.hh:54-71: axes, axis-value variations, transform fields
  translate/rotate/scale/skew/tcenter, condition, 24-bit gid) and
  `HBUINT32VAR` fields.
* `VarComponent::get_path_at` (VARC.cc:344-466): evaluate the optional
  condition; decode axis indices and values, add their variations (from the
  multi-IVS at the *parent's* coords); build a new coordinate vector
  (`coord_setter_t`, which can address axes **beyond fvar's axis count**, up
  to `HB_VAR_COMPOSITE_MAX_AXES` 4096 — hidden per-component axes);
  `RESET_UNSPECIFIED_AXES` decides whether unspecified axes reset to 0 or
  inherit; compute the transform (with variations), compose, and recurse.
* Leaves are drawn by glyf → CFF2 → CFF1 **at the component's coordinates**
  through a transforming pen (VARC.cc:487-504). So VARC is a layer above the
  outline formats and never sees GSUB.
* Draw order in `hb_ot_draw_glyph_or_fail` (hb-ot-font.cc:900-934): VARC first,
  then glyf, CFF2, CFF1. A VARC-covered glyph shadows its glyf/CFF outline.
* 15.0.0: instancing can now drop axes not referenced by retained VARC data;
  VARC subsetting came in 14.5.0 (`VARC-subset.hh`).

### Suggested sections

1. Design space to normalized space: fvar, avar v1 (and the real-world
   special cases), avar v2; 16.16 vs 2.14; named instances.
2. Regions and scalars: tents, intermediate regions, odd-region robustness,
   scalar caches.
3. Item Variation Stores: VarData, DeltaSetIndexMap, HVAR/VVAR/MVAR, multi-IVS.
4. gvar: tuple headers, shared tuples, point numbers, packed deltas, IUP,
   phantom points; the fast paths; GVAR.
5. cvar and hinting (or rather, why HarfBuzz only writes it).
6. VARC: variable components, hidden axes, conditions, transforms; why it's a
   draw-time feature only.

---

## 3. Outlines and colour

### Key files

* Draw API: `hb-draw.h`, `hb-draw.hh`, `hb-draw.cc`.
* glyf: `OT/glyf/glyf.hh` (`glyf`, `GLYF` 198, `glyf_accelerator_t` 204),
  `Glyph.hh` (`get_points` 327), `SimpleGlyph.hh` (flags 14-24,
  `read_flags` 126), `CompositeGlyph.hh` (`CompositeGlyphRecord` 13,
  `transform_points` 125, `get_transformation` 217), `path-builder.hh`,
  `loca.hh`, `SubsetGlyph.hh`, `glyf-helpers.hh`.
* CFF: `hb-cff-interp-common.hh` (`number_t` 220 [double], `arg_stack_t`
  443 [limit 513], `interpreter_t` 655), `hb-cff-interp-cs-common.hh`
  (`kMaxCallLimit` 10 at 59, `path_procs_t` 459, `cs_interpreter_t` 883),
  `hb-cff-interp-dict-common.hh`, `hb-cff1-interp-cs.hh`, `hb-cff2-interp-cs.hh`
  (`blend_arg_t` 37), `hb-ot-cff-common.hh`, `hb-ot-cff1-table.{hh,cc}`
  (seac: `process_seac` .cc:528), `hb-ot-cff2-table.{hh,cc}` (`get_path_at` .cc:228).
* Paint API: `hb-paint.h`, `hb-paint.hh` (callback list 33-55), `hb-paint.cc`,
  `hb-paint-extents.{hh,cc}`, `hb-paint-bounded.{hh,cc}`.
* Colour tables: `OT/Color/COLR/COLR.hh` (3402 lines; `COLR` 2542),
  `colrv1-closure.hh`, `colrv1-depend.hh`, `CPAL/CPAL.hh`, `CBDT/CBDT.hh`,
  `sbix/sbix.hh`, `svg/svg.hh`; public `hb-ot-color.h`.
* Synthetic emboldening/slant: `hb-outline.{hh,cc}`; `hb-font.hh:690-748`.

### hb-draw

* Callbacks: move_to, line_to, quadratic_to, cubic_to, close_path, plus (14.5.0)
  set_budget/get_budget/get_budget_remaining (hb-draw.hh:35-44).
* **move_to is lazy**: `hb_draw_funcs_t::move_to` only records the point;
  the client's move_to is emitted on the first segment (`start_path`), and
  close_path inserts a closing line_to if the contour isn't closed
  (hb-draw.hh:112-178). So clients never see empty contours or unclosed paths.
* `hb_draw_session_t` (hb-draw.hh:194-252) carries the draw state and a
  pointer to the live budget (a backend's, or a local `HB_BUDGET_GLYPH` 2^24).
* Synthetic slant/embolden: when the font has them, the outline is first
  recorded into an `hb_outline_t`, slanted around the glyph's horizontal
  origin, then emboldened (`hb_outline_t::embolden`), then replayed
  (hb-font.hh:690-748). Slant before embolden "produces nicer results".

### glyf

* Contour points are `contour_point_t` with flags; 4 phantom points are
  appended to every glyph (Glyph.hh:21-25, 392-414).
* Composite components are loaded recursively (`HB_MAX_NESTING_LEVEL` 64,
  `HB_MAX_GRAPH_EDGE_COUNT` 16384, `hb_decycler_t` for cycles,
  `HB_GLYF_MAX_POINTS` 200000, budgets).
* **Each component contributes one "point" to the composite's own point list
  — its offset** — so gvar can vary component offsets and phantoms
  (`points[old_length + comp_index]` in Glyph.hh:~520). USE_MY_METRICS copies
  the component's phantoms. Anchored (point-matching) components are supported.
* Point-to-path: `path_builder_t::consume_point` (path-builder.hh:39-~170),
  based on ttf-parser, handles implied on-curve midpoints, all-off-curve
  contours, and **cubic** off-curve pairs.
* Contour start rotation: if a contour starts off-curve, the code feeds the
  last point first to match FreeType/Core Text, *unless* it's a cubic pair
  (rotating by one would re-pair the cubic controls) (glyf.hh:330-385; note
  the dead `if (false)` branch at 311 kept for reference).
* **Cubic glyf**: `SimpleGlyph::FLAG_CUBIC` = 0x80. `read_flags` masks it off
  unless `extended` (SimpleGlyph.hh:137-138), and `extended` is true only when
  the glyphs come from the uppercase `GLYF`/`LOCA` tables (glyf.hh:226-239). So
  bit 0x80 in a lowercase `glyf` is ignored; cubic TrueType outlines only
  exist in `GLYF`. (Relevant to FontPen's own format rules.)
* glyf accelerator prefers `GLYF`+`LOCA` when both are present, else `glyf`+`loca`.
  `num_glyphs` is clamped by loca length and maxp (glyf.hh:254-255).
* No hinting: glyph instructions are never executed (inferred; there is no
  TrueType interpreter in src/). Subsetting can drop them (`NO_HINTING`).

### CFF / CFF2

* A shared interpreter framework: `interp_env_t` with an argument stack
  (513), `call_stack_t` (10 levels), opset templates for DICT and
  charstrings; `path_procs_t` implements each path operator in terms of
  `moveto/line/curve` callbacks; separate param/procs for **extents** and
  **path** (hb-ot-cff1-table.cc:316-577).
* Numbers are doubles (`number_t`), clamped when converted to int/fixed.
* `cs_interpreter_t::interpret` (hb-cff-interp-cs-common.hh:883-930) bounds
  operator count by `min(budget, HB_CFF_MAX_OPS=200000)` and charges ops used
  back to the shared budget.
* CFF1 `seac` (endchar with 4 args) draws base and accent via recursion with
  `in_seac` set, offset by the accent delta (hb-ot-cff1-table.cc:528-545).
* CFF2 `blend`: `blend_arg_t` keeps the per-region deltas *unresolved* on the
  stack alongside the default value (hb-cff2-interp-cs.hh:37-69); `vsindex`
  selects the VarData. Keeping deltas lets the subsetter/instancer reuse the
  same interpreter (inferred). Partially instancing or desubroutinizing CFF2
  with nested blends now *fails* rather than changing outlines (15.1.0).

### hb-paint and colour

* Paint callbacks (hb-paint.hh:33-55): transforms, clips (glyph, rectangle,
  and since 14.2.0 arbitrary path via `push_clip_path_start/_end`), color,
  image, linear/radial/sweep gradients, groups (`push_group_for` new),
  custom palette colours, `fill_glyph` (14.3.0), and budgets.
* `fill_glyph`'s default decomposes into push_clip_glyph + color + pop_clip
  (hb-paint.cc:63-75); backends override it to fill a glyph outline directly.
* Glyph source order (`hb_ot_paint_glyph_or_fail`, hb-ot-font.cc:939-957):
  COLR → SVG → CBDT → sbix. If none applies, `hb_font_t::paint_glyph`
  (hb-font.cc:1687-1699) falls back to `fill_glyph` with the foreground —
  every glyph with an outline paints.
* **A backend refusing an image is a protocol**: SVG/CBDT/sbix `paint_glyph`
  return the result of `funcs->image(...)` (svg.hh:233-253). The in-tree raster
  and vector backends return false for SVG, so the chain falls through to the
  next source and finally the outline (inferred consequence).
* COLRv1: 33 Paint formats (Paint union, COLR.hh:~2280-2350; format 33 is
  `PaintGlyph` with 24-bit gid = OFF5 `PaintGlyph2`); variable formats wrap
  `Variable<T>` with a VarIdx base into the IVS through a DeltaSetIndexMap;
  ClipList boxes; LayerList; recursion depth `HB_MAX_NESTING_LEVEL`.
  `hb-paint-extents` computes extents by simulating paint; `hb-paint-bounded`
  decides whether a paint graph is bounded.
* SVG documents may be gzip-compressed; `svg.hh:59-70` decompresses with zlib
  when available (13.1.1). Public API can inspect documents and glyph ranges
  (hb-ot-color.h:137-154).
* sbix picks a strike by ppem (indexed by ppem; largest if ppem 0)
  (sbix.hh:200-300); CBDT has an index cache (`HB_CBDT_MAX_INDEX_ENTRIES`).

### Suggested sections

1. The draw API contract (lazy move_to, closing, sessions, budgets).
2. TrueType outlines: simple glyphs, flags, coordinates, implied points;
   composites, transforms, anchors; phantom points; cubic GLYF.
3. CFF and CFF2: INDEX/DICT parsing, charstring interpreter, subroutines,
   seac, hints-as-stems, blends and vsindex.
4. Synthetic slant and emboldening.
5. The paint API: a tree-walking protocol rather than a renderer.
6. COLR v0/v1 and CPAL, variable paints, clip boxes.
7. Bitmap and SVG glyphs: CBDT, sbix, SVG (and the fallthrough protocol).

---

## 4. Output libraries: hb-raster, hb-vector, hb-gpu (and hb-outline/geometry)

All three are separate shared libraries (`libharfbuzz-raster`, `-vector`,
`-gpu`), stable since 15.0.0, built by default (meson_options.txt:36-41).
Each implements `hb_draw_funcs_t` and `hb_paint_funcs_t` that you pass to
`hb_font_draw_glyph`/`hb_font_paint_glyph`; the `*_glyph()` helpers are "thin
convenience wrappers" over that (NEWS 14.2.0). Getters for funcs take the
instance (const) since 14.2.0.

### hb-raster (hb-raster.h, hb-raster-draw.cc, hb-raster-paint.cc, hb-raster-image.cc)

* Output: `hb_raster_image_t` in A8 or BGRA32 (hb-raster.h:38-47); PNG
  serialize/deserialize with libpng (13.1.0).
* Draw: curves are flattened on the fly (flatness 0.25 px) into edges in
  24.8 fixed point (hb-raster-draw.cc:42-60); then an **analytic coverage
  rasterizer** (comment at 1236-1251): per cell accumulate `cover` (signed dy)
  and `area` (twice the trapezoid area), then a left-to-right sweep
  `α = min(|cover_accum·2·ONE − area|, FULL)` — nonzero-winding with
  absolute value (inferred from the formula). NEON/SSE2 paths (30-39).
  Curves outside a clip box collapse to their chord (exact for coverage, 332).
* Paint: a compositing stack of surfaces with clips as alpha masks;
  gradients; images (PNG/BGRA only); bitmap colour glyphs since 13.1.0.
* Limits: `HB_RASTER_MAX_DRAW_EDGES` 2^20, `HB_RASTER_MAX_AUTO_DIMENSION` 4096
  for extents derived from font data, `HB_RASTER_MAX_BUFFER_SIZE` 1 GiB, pixel
  budgets (hb-limits.hh:184-262).

### hb-vector (hb-vector.h, hb-vector-draw.cc, hb-vector-paint*.cc, hb-vector-path.cc)

* Formats: `HB_VECTOR_FORMAT_SVG` and `HB_VECTOR_FORMAT_PDF` (14.2.0)
  (hb-vector.h:45-47). Draw produces path data; paint produces a full
  document with gradients, clipPaths, blend modes, embedded PNGs (base64 in
  SVG, hb-vector-paint-svg.cc:643-664).
* Precision setting (renamed from `svg_set_precision`, 14.2.0); SVG id prefix
  for embedding multiple outputs; glyph dedup with `<defs>/<use>` was removed in
  14.2.0 (each glyph emitted inline).
* Caps: `HB_VECTOR_MAX_DOCUMENT_SIZE` 16 MiB.

### hb-gpu (hb-gpu.h, hb-gpu-draw.cc, hb-gpu-paint.cc, hb-gpu.cc, shaders)

* Based on Eric Lengyel's **Slug** algorithm (NEWS 14.0.0): outlines are
  encoded on the CPU into a blob of RGBA16I texels (hb-gpu-draw.cc:425-450)
  and rasterized per-pixel in the fragment shader — no glyph atlas of bitmaps.
* Encoding: everything becomes **quadratic** curves; lines are degenerate
  quadratics (`acc_emit_conic`); cubics are converted by `hb-gpu-cu2qu.hh`
  (tolerance 0.5 font units, max depth 10). Coordinates are quantized to
  1/4 font unit (`HB_GPU_UNITS_PER_EM` 4, hb-gpu-draw.hh:38). Curves are
  binned into up to 16 horizontal and 16 vertical bands ("capped at 16 per
  Slug paper", hb-gpu-draw.cc:510-514). Max 65536 curves per glyph.
* Shaders in GLSL, WGSL, MSL, HLSL (`hb-gpu-*.glsl` etc., embedded as `.hh`
  by `gen-gpu-shader-artifacts.py`); `hb_gpu_shader_source(stage, lang)`.
  Fragment helpers include MSAA-aware coverage, ppem, and
  `hb_gpu_stem_darken` (hb-gpu-fragment.glsl:39-53).
* `hb_gpu_paint_t` (14.2.0) encodes COLRv0/v1 paint trees into a blob of
  layer ops interpreted by `hb_gpu_paint()` in the shader: ≤ 32767 ops,
  ≤ 4 nested groups, ≤ 3 intersected clip outlines; `PaintImage` unsupported;
  `push_clip_rectangle` ignored; some composite modes approximated (NEWS
  14.2.0; hb-gpu-paint.cc:49-53).

### hb-outline and hb-geometry

* `hb_outline_t` (hb-outline.hh) is a recorded path (points + contour ends)
  used by the core library for synthetic slant/embolden and by the WASM API;
  `hb_outline_recording_pen_get_funcs()` records any draw into it.
* `hb-geometry.hh`: `hb_extents_t` (35), `hb_transform_t` (136),
  `hb_bounds_t` (338), `hb_transform_decomposed_t` (385; VARC's
  translate/rotate/scale/skew/tcenter form). Shared by paint-extents, VARC,
  and the renderers.

### Suggested sections

1. The renderer pattern: a renderer is just draw/paint funcs + state.
2. hb-raster: flattening, analytic coverage, compositing COLR.
3. hb-vector: SVG and PDF output; colour fonts as resolution-independent artwork.
4. hb-gpu: Slug, bands, quadratic-only encoding, cu2qu, the paint VM.
5. Budgets and limits: why renderers share one work counter with font code.

---

## 5. Subsetting, serializing, repacking, instancing, depend

### Key files

* API: `hb-subset.h` (flags 105-123), `hb-subset-input.{hh,cc}`,
  `hb-subset-serialize.h` (public object-graph serializer, 10.2.0),
  `hb-subset-depend.h`.
* Driver: `hb-subset.cc` (`_dependencies_satisfied` 264, `_subset_table`
  307, `hb_subset_or_fail` 405, `hb_subset_plan_execute_or_fail` 439),
  `hb-subset-table.hh` (buffer estimate/retry, `_hb_subset_repack` 114,
  `_hb_subset_table` 139), `hb-subset-table-{layout,var,cff,color,other}.cc`.
* Plan: `hb-subset-plan.{hh,cc}` (`_populate_gids_to_retain` 448),
  `hb-subset-plan-member-list.hh`, `hb-subset-plan-layout.cc`,
  `hb-subset-plan-var.cc`, `hb-subset-accelerator.hh` (preprocess cache).
* Serializer: `hb-serialize.hh` (`hb_serialize_context_t` 55, `pop_pack` 370,
  `add_virtual_link` 487, `add_link` 533, `resolve_links` 577).
* Repacker: `hb-repacker.hh` (`hb_resolve_graph_overflows` 401,
  `hb_resolve_overflows` 479), `graph/graph.hh` (`graph_t` 43,
  `sort_shortest_distance` 740, `duplicate` 1344-1509, `assign_spaces` 939),
  `graph/{gsubgpos,pairpos,markbasepos,ligature,coverage,classdef}-graph.hh`,
  `graph/graph-result.hh` (error enum), `graph/serialize.hh`.
* Instancing: `hb-subset-instancer-solver.{hh,cc}` (`rebase_tent`),
  `hb-subset-instancer-iup.{hh,cc}` (IUP optimization ported from fontTools),
  `tuple_delta_t`/`TupleVariationData::tuple_variations_t`/`item_variations_t`
  in hb-ot-var-common.hh, `AVAR2-INSTANCING.md` (top level).
* CFF subsetting: `hb-subset-cff-common.{hh,cc}`, `hb-subset-cff1.cc`,
  `hb-subset-cff2.cc` (2130 lines), `hb-cff-specializer.hh`,
  `hb-cff-width-optimizer.hh`, `hb-subset-cff2-to-cff1.hh`, `hb-subset-cff2-round.hh`.
* Depend: `hb-depend.{hh,cc}`, `hb-depend-data.hh`, table `depend()` methods
  (e.g. glyf.hh:269-279, OT/Color/COLR/colrv1-depend.hh); docs/depend-*.md.

### Plan: glyph closure is a staged pipeline

`_populate_gids_to_retain` (hb-subset-plan.cc:448-545), in order:
.notdef (gid 0) → cmap (plus bidi-mirror closure of unicodes) → MATH →
GSUB closure (layout) → COLR (v0 layers, v1 paint graph; also collects
palette, layer and variation indices) → VARC components → glyf composites
(byte-budgeted) or CFF seac components → layout variation indices (GDEF).
Each stage feeds the next; **there is no fixpoint loop back**: a glyph
introduced by COLR or VARC is not re-run through GSUB closure (inferred from
the straight-line code). The plan also builds the old↔new glyph maps
(RETAIN_GIDS keeps ids), and as of 15.1.0 rejects a mapping that assigns
another glyph to gid 0.

### Executing: tables with dependencies, buffers that grow

* `hb_subset_plan_execute_or_fail` (hb-subset.cc:439-511) loops over pending
  tables, subsetting each whose dependencies are satisfied (264-304): when
  instancing glyf, hmtx/vmtx/maxp/OS/2 wait for glyf (glyf instancing
  recomputes metrics); GSUB/GPOS wait for GDEF unless all axes pinned; with
  avar2, all variation tables wait for avar. A round with no progress fails.
* Each table gets a buffer sized by `_hb_subset_estimate_table_size`
  (GSUB/GPOS/GDEF/name get source size); `ran_out_of_room` doubles it and
  retries (up to 256× the source table) (hb-subset-table.hh:~40-70).
* Only if the serializer flagged `OFFSET_OVERFLOW` is the repacker invoked
  (`_hb_subset_repack`, hb-subset-table.hh:114-129).
* Output is an `hb_face_builder` face; serializing it writes table checksums and
  `checkSumAdjustment` (hb-open-file.hh:~140-195).

### The serializer (docs/serializer.md is accurate)

* One buffer, two stacks: in-progress objects grow from the head, packed
  objects from the tail. `push()` starts a child object, `pop_pack()` finishes
  it, **deduplicating** against already-packed identical objects (same bytes
  and same links) via `packed_map`, and returns its object index; parents then
  `add_link(offset_field, objidx)`. Links record width, signedness,
  `whence` (Head/Tail/Absolute) and bias (hb-serialize.hh:59-63,141-160).
* `add_virtual_link` (487) adds an ordering-only edge with no offset field
  (used to keep objects in a required order, inferred from name/usage).
* Errors are a bitmask (`OTHER`, `OFFSET_OVERFLOW`, `OUT_OF_ROOM`,
  `INT_OVERFLOW`, `ARRAY_OVERFLOW`, 46-51); `snapshot()/revert()` roll back
  partial writes.

### The repacker

* `hb_resolve_graph_overflows` (hb-repacker.hh:401-461): shortest-distance
  topological sort (Dijkstra-like, edge weight = child size + 2^16 or 2^32);
  if anything overflows and the table is GSUB/GPOS, run the
  "specialization": split oversized subtables (PairPos, MarkBasePos,
  Ligature) and promote lookups to Extension; then iterate up to `max_rounds`
  (32 for subsetting; 20 with extension recalculation for the public
  `hb_subset_serialize_or_fail`) and `HB_REPACKER_MAX_ITERATIONS` 500:
  isolate subgraphs under 32-bit offsets into separate "spaces", else
  duplicate shared children or raise priorities; re-sort. If it still
  overflows and extensions weren't tried, recurse with them on.
* Limits: `HB_REPACKER_MAX_VERTICES` 800000, `MAX_SPACES` 8000 (hb-limits.hh:283-293).
* Errors are a `graph_result_t` (hb-result.hh) with an enum including
  `CYCLE_DETECTED`, `ORPHANED_NODES`, `OVERFLOW_RESOLUTION_FAILED`.

### Instancing

* HarfBuzz's instancer is **fused with the subsetter**: each table's
  `subset()` both drops glyphs and instances variations (stated in
  AVAR2-INSTANCING.md "Key architectural difference").
* Axis limits are (min, default, max) `Triple`s; `rebase_tent`
  (hb-subset-instancer-solver.hh:94-106, ported from fontTools) re-expresses
  each region (tent) under new limits as a list of (scalar, new tent) pairs,
  where an empty tent is a constant "gain" added to defaults.
* gvar/cvar: `tuple_variations_t` (TupleVariationData) decompiles tuples into
  `tuple_delta_t`s, rebases them, merges equal regions, optionally re-runs IUP
  optimization (`hb-subset-instancer-iup.cc`; contours over 512 points keep
  all explicit deltas, 364-371), then recompiles with shared tuples/points.
* IVS tables: `item_variations_t` rebuilds VarData with fontTools-like row
  encoding optimization (`delta_row_encoding_t`, hb-ot-layout-common.hh:2367).
* Full instancing of glyf recomputes bboxes, metrics, maxp/head maxima
  (`head_maxp_info_t` through `Glyph::get_points`), and uses one cumulative
  `HB_BUDGET_SUBSET_GLYF` (2^28) for the whole table (hb-limits.hh:240-251).
* avar2 partial instancing: "offset compensation" (AVAR2-INSTANCING.md).
* CFF2: instancing; `DOWNGRADE_CFF2` converts a pinned CFF2 to CID-keyed CFF1
  (`hb-subset-cff2-to-cff1.hh`); `CFF_IDENTITY_CHARSET` (14.3.0) for PDF.
* CFF subsetting: subroutine closure and renumbering, or desubroutinize; a
  "specializer" (generalize then re-specialize charstrings, after fontTools,
  hb-cff-specializer.hh) and width optimizer; 15.0.0+ fails if subroutine
  calls aren't preceded by an immediate number (unless desubroutinizing).

### Preprocessing

`hb_subset_preprocess` builds an `hb_subset_accelerator_t` attached to the face
as user data (hb-subset.cc:65,366; docs/subset-preprocessing.md), caching
closures, cmap maps and especially parsed CFF, for repeated subsets.

### hb-depend (experimental)

* Purpose: extract the font's full **glyph dependency graph** once (edges
  gid → dependent gid, tagged by table: GSUB with feature tag, glyf/GLYF
  composites, CFF seac, COLR, MATH; UVS excluded), so applications (e.g.
  font segmentation for incremental font transfer) can compute closures
  themselves without running the subsetter (NEWS 14.3.0; docs/depend-api.md).
* Difference from closure: depend records every lookup's edges independently
  (no sequential accumulation); ligatures carry a set of required co-glyphs,
  contextual rules a context set; edge flags `FROM_CONTEXT_POSITION` and
  `FROM_NESTED_CONTEXT` mark expected over-approximation
  (hb-subset-depend.h:40-70; docs/depend-implementation.md).
* Built only with `-Dexperimental_api=true`; `util/hb-subset-depend.cc` CLI;
  `test/fuzzing/hb-depend-closure-parity.cc` checks closure-from-depend
  against the real subsetter closure on valid fonts.

### Suggested sections

1. What subsetting is for (web fonts, PDF embedding, IFT) and the API
   (input sets, flags, axis pinning/ranges, plans, preprocess).
2. The plan: closures in stages, glyph maps, table dropping.
3. Writing tables: the serializer, packing, dedup, links.
4. Offsets that don't fit: the repacker (with an honest note about the docs).
5. Instancing: tents and rebasing, gvar/IVS recompilation, IUP, full vs
   partial, avar2 offset compensation, CFF2 → CFF.
6. CFF subsetting and charstring specialization.
7. hb-depend: graphs instead of closures.

---

## 6. Testing and robustness

### Layout of test/

* `test/api/`: C unit tests per API (`test-draw.c`, `test-paint.c`,
  `test-ot-color.c`, `test-raster.cc`, `test-gpu.cc`, `test-subset-*.c`,
  `test-instance-cff2.c`, `test-draw-varc.c`, ...), fonts in `test/api/fonts`,
  paint expectations in `results-paint/`, and Python generators for synthetic
  edge-case fonts (`generate-cff2-nested-delta-font.py`, etc.).
* `test/shape/`: `run-tests.py` over `data/{in-house,aots,text-rendering-tests}`;
  `.tests` files are `font;options;unicodes;expected-glyphs` lines (with
  comments), plus `hb-diff*` tools.
* `test/subset/`: `run-tests.py` over `data/tests/*.tests` (104 files) of the form
  `FONTS:` / `PROFILES:` / `SUBSETS:` (and instancing options), comparing
  against `data/expected/`; profiles are hb-subset flag files; `repack_tests`
  and `run-repack-tests.py` for the repacker; `generate-expected-outputs.py`
  regenerates with fontTools.
* `test/vector/`: golden-file tests of `hb-vector` CLI output
  (`font;options;unicodes;expected-file`).
* `test/threads/`: multithreaded shaping/subsetting.
* `test/fuzzing/`: libFuzzer targets for shape, subset, repacker, raster,
  vector, gpu, depend, plus closure-parity; `fonts/` (532 seeds) and
  `graphs/`; `main.cc` runs the corpus as regular tests (inferred).
* In-source unit tests: `src/test-*.cc` (repacker, serialize, item-varstore,
  tuple-varstore, instancer solver, cff, colr, raster-paint, vector, geometry...).

### Robustness mechanisms

* `hb-limits.hh`: all hard caps in one place, overridable at build time
  (buffer limits, nesting 64, graph edges 16384, `HB_GLYF_MAX_POINTS`,
  `HB_CFF_MAX_OPS`, VARC 4096 axes, SVG/raster/vector/GPU caps, repacker caps).
* **Budgets** (hb-limits.hh:197-282, 14.5.0): when one subsystem drives
  another (COLR → paint backend → glyf/CFF; VARC → glyf/CFF), per-subsystem
  limits multiply, so each top-level session carries one decrement-only
  counter (`HB_BUDGET_GLYPH` 2^24) shared with nested work; exhaustion skips
  further work best-effort. Charged in fixed weights (`HB_BUDGET_1..8192`) via
  `hb_budget_spend`. Public in draw/paint APIs (`HB_BUDGET_DEFAULT`,
  `HB_BUDGET_UNLIMITED`).
* Sanitizer ops/subtable/recursion limits (section 1); saturating arithmetic
  (`hb_unsigned_mul_add_saturate`, etc.) throughout since 14.2.1.
* `hb-decycler.hh`: cycle detection for glyf composites, COLR, VARC.
* **failing-alloc** (`src/failing-alloc.c`): when building fuzzers
  (`fuzzer_ldflags` set), HarfBuzz is compiled with `HB_CUSTOM_MALLOC` and
  this file, whose `hb_malloc/calloc/realloc_impl` fail pseudo-randomly about
  1 in 16 calls, seeded by `alloc_state` (src/meson.build:658-664). Each fuzzer
  sets `alloc_state = _fuzzing_alloc_state(data, size)`, which disables
  failures for half the inputs (last byte < 0x80) (test/fuzzing/hb-fuzzer.hh:28-37).
  So every allocation-failure path is exercised deterministically per input.
* "_or_fail" naming: functions that can fail have `_or_fail` variants; since
  14.2.0 the renderers' `*_glyph()` return void and have `_or_fail` twins.
* `src/check-*.py` scripts check symbols, headers, static initializers,
  libstdc++ linkage (e.g. the 14.2.1 replacement of `std::sort` to avoid
  leaking `std::` symbols).

### Suggested sections

1. Assume malice: the threat model of a font parser.
2. Sanitize + Null + lazy checks as a design, not a patch.
3. Limits and budgets: bounding work when subsystems nest.
4. Fuzzing with failing allocators; ClusterFuzz/OSS-Fuzz testcases in-tree.
5. Correctness tests: shape, subset (vs fontTools), vector golden files,
   closure parity.

---

## Suggested chapter breakdown for this area

1. **Fonts as bytes** — blobs, the sfnt container, types-over-bytes, offsets,
   Null objects. (§1)
2. **Trust nothing: sanitizing** — the contract, budgets, `hb_barrier`, lazy
   GPOS checks, reject-not-repair. (§1, §6)
3. **Faces and lazy tables** — `hb_ot_face_t`, lazy loaders, accelerators,
   beyond-64K dual tables. (§1)
4. **Design space** — fvar, avar v1/v2, normalization, named instances, how
   coords reach every table. (§2)
5. **Deltas** — regions and scalars, item variation stores (HVAR/VVAR/MVAR,
   GDEF), multi-IVS. (§2)
6. **Varying outlines** — gvar/GVAR, IUP, phantom points, cvar. (§2, §3)
7. **Drawing TrueType outlines** — the draw API, glyf simple/composite,
   cubic GLYF. (§3)
8. **Drawing PostScript outlines** — CFF/CFF2 interpreters, subrs, seac, blend. (§3)
9. **Variable components** — VARC. (§2, §3)
10. **Colour** — the paint API, COLR/CPAL, CBDT/sbix/SVG, fallbacks. (§3)
11. **Rendering in HarfBuzz** — hb-raster, hb-vector (SVG/PDF), hb-gpu
    (Slug), budgets. (§4)
12. **Subsetting** — inputs, plan and closures, table scheduling. (§5)
13. **Writing tables** — serializer and repacker. (§5)
14. **Instancing** — tent rebasing, recompiling variations, avar2, CFF2→CFF. (§5)
15. **Dependency graphs** — hb-depend. (§5)
16. **How HarfBuzz is tested** — test suites, fuzzing, failing-alloc, limits. (§6)

(Chapters 2 and 16 could merge; 9 could sit inside 6 or 7.)
