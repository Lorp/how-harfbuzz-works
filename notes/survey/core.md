# Survey: the core object model and the shaping pipeline (HarfBuzz 15.1.0)

Source: `harfbuzz/` at 15.1.0 (NEWS dated 4 Nov 2026). All paths are relative to `src/` unless they say otherwise. Line numbers are for this checkout. “(inferred)” marks a conclusion I drew rather than read directly. Where `docs/` and the code disagree, this follows the code and notes the disagreement.

Out of scope here, as agreed: GSUB/GPOS lookup internals, the script-specific shapers, AAT, subsetting, variation tables, and drawing/painting/raster/vector/gpu. They are mentioned only where the pipeline hands off to them.

---

## 0. The big picture in one paragraph

A **blob** is bytes. A **face** is a blob seen as an sfnt, with tables loaded and sanitized lazily. A **font** is a face at a size, with variation coordinates and synthetic bold/slant, plus a vtable of **font funcs** that answer “which glyph? how wide? what extents?”. A **buffer** holds Unicode in and glyphs out, as parallel `info[]` and `pos[]` arrays, with scratch fields that the pipeline reuses. `hb_shape_full()` gets a **shape plan** from a per-face cache, keyed by segment properties, user features, feature-variation state and shaper. The plan picks a **shaper backend** (normally `ot`). The `ot` backend runs one fixed pipeline, `hb_ot_shape_internal()`: Unicode properties, then clustering, normalization and cmap mapping, then masks, GSUB (or morx), positions, GPOS (or kerx/kern/fallback), and finally cleanup.

---

## 1. hb_blob_t

**Files:** `hb-blob.h`, `hb-blob.hh:39`, `hb-blob.cc`.

* There are four memory modes (`hb-blob.h:70`): `DUPLICATE`, `READONLY`, `WRITABLE`, and `READONLY_MAY_MAKE_WRITABLE`. The header itself tells users to avoid the last one (“very tricky”).
* `hb_blob_create_sub_blob` (`hb-blob.cc:169`) makes zero-copy views. Every table blob is a sub-blob of the file blob (see §2).
* `hb_blob_create_from_file_or_fail` (`hb-blob.cc:789`) tries `mmap` first (`_hb_blob_try_mmap`, :620 on POSIX, :659 on Windows with `MapViewOfFile`), and falls back to reading the file in.
* `try_make_writable` (:473) and `try_make_writable_inplace_unix` (:415, which uses mprotect) still exist.

**Non-obvious, and important for the book:** the sanitizer **no longer edits fonts**. The `hb-sanitize.hh` header comment (≈ lines 30–100) explains why: “Sanitize was named so because it used to try to recover from errors by modifying the data … This is no longer the case, as it could make HarfBuzz hallucinate new rules if there was aliasing.” NEWS 12.3.0 adds that invalid GSUB/GPOS are now *rejected outright* (as in CoreText, unlike DirectWrite and HarfRust). Older descriptions of “neutering” offsets and copy-on-write blobs are therefore out of date. The `HB_SANITIZE_MAX_EDITS` macro (`hb-sanitize.hh:107`) is still defined; it looks like a leftover (inferred).

* The sanitizer’s cost policy is a good subject for the book. It checks GSUB/GPOS/GDEF offsets eagerly, so lookup code never re-checks them. glyf/loca are checked lazily, at glyph-load time, which keeps load O(1) and total cost O(glyphs used) (header comment). Work is bounded by `max_ops`, computed from blob length (`HB_SANITIZE_MAX_OPS_FACTOR` 64, `_MIN` 16384).

---

## 2. hb_face_t

**Files:** `hb-face.h`, `hb-face.hh:47`, `hb-face.cc`, `hb-face-builder.cc`, `hb-ot-face.hh`, `hb-ot-face-table-list.hh`.

* **Struct** (`hb-face.hh:47`). It holds `index`; atomically cached `upem` and `num_glyphs`; a `reference_table_func` plus user_data, the *only* way tables get in; `get_table_tags_func` (since 10.0); `data` (per-shaper face data, §8); `table` (an `hb_ot_face_t`, one lazy loader per table in `hb-ot-face-table-list.hh`); and the **shape-plan cache** `shape_plans` with `last_shape_plan` (§7).
* **`hb_face_create`** (`hb-face.cc:244`) sanitizes only the top-level `OpenTypeFontFile` (the sfnt or TTC directory). It installs `_hb_face_for_data_reference_table` (:185), which returns `hb_blob_create_sub_blob(file, base_offset + table.offset, table.length)`. Each table is sanitized on first access by its lazy loader in `face->table.X`.
* **The face index packs two things.** The low 16 bits select the face in a collection; the closure stores `index & 0xFFFF` (:170). The high 16 bits, minus one, select a **named instance**, which `hb_font_create` applies (`hb-font.cc:2145`). 15.1.0 fixed `hb_face_create_or_fail` (:289) to mask with `0xFFFF` before checking `hb_face_count`.
* **Tables come through a callback.** `hb_face_create_for_tables` (:130) lets an integrator provide tables from anywhere (FreeType, CoreText, a font editor’s in-memory tables). `hb-face-builder.cc` (`hb_face_builder_create`, :215) builds a face from tables you add, and can serialize it to a blob.
* **Face loaders** (11.0): `supported_face_loaders[]` (`hb-face.cc:331`) holds “ot”, plus “ft”, “coretext” and “directwrite” when built. Entry points are `hb_face_create_from_file_or_fail_using` / `hb_face_create_or_fail_using` and `hb_face_list_loaders`.
* The table list (`hb-ot-face-table-list.hh`) is compile-time trimmed by `HB_NO_*` guards. Beyond-64k tables (`GLYF`, `HMTX`, …) have their own types (e.g. `HMTX : hmtxvmtx<HMTX,HHEA,HVAR>` in `hb-ot-hmtx-table.hh:433`). They are **on by default since 15.0**, and off only under `HB_MINI` (`hb-config.hh:96`).
* **Immutability:** `hb_font_create` and `hb_shape_plan_create2` both call `hb_face_make_immutable`. A face you have shaped with can no longer be changed.

**For the book:** “zero-cost font loading” is literal: mmap, sub-blobs, lazy sanitize and lazy accelerators. The face/font split is the thread-safety boundary. Faces are immutable and shared. Fonts carry per-size state.

---

## 3. hb_font_t, font funcs, sub-fonts, variations, synthetics, caching

**Files:** `hb-font.h`, `hb-font.hh`, `hb-font.cc`, `hb-ot-font.cc`, `hb-ot-metrics.cc` (metrics), and `rust/font.rs` (fontations).

### 3.1 The vtable

* **`HB_FONT_FUNCS_IMPLEMENT_CALLBACKS`** (`hb-font.hh:46`) is the complete list: font_h/v_extents, nominal_glyph(s), variation_glyph, glyph_h/v_advance(s), glyph_h/v_origin(s) (the plural *origins* funcs are new in 11.3), glyph_h_kerning, glyph_v_kerning (deprecated), glyph_extents, glyph_contour_point, glyph_name, glyph_from_name, `draw_glyph_or_fail`, and `paint_glyph_or_fail` (the `_or_fail` forms are from 11.2; the old draw/paint funcs are deprecated).
* **Three tiers of implementation** per slot (`hb-font.cc`):
  * `*_nil` implementations return “nothing”. The h-advance one returns `x_scale` (1 em) (`hb-font.cc:220`; `:229` is the default one).
  * `*_default` implementations (`_hb_font_funcs_default`, :827) **delegate to the parent font** and rescale with `parent_scale_x_distance` etc. (`hb-font.hh:170`).
  * The single and batch forms fall back on each other. `nominal_glyph_default` calls `nominal_glyphs` if *that* is set, and vice versa (:152–193). Advances work the same way (:229–297). An implementer only has to provide one of each pair.
* `has_func_set` compares the slot against the default table pointer (`hb-font.cc:1086`). `has_func` also walks up parents.

### 3.2 Sub-fonts

`hb_font_create_sub_font` (`hb-font.cc:2195`) copies scale, embolden, slant, ppem, ptem and coords from the parent, and keeps a reference to it. Its funcs start as `_hb_font_funcs_default`, so every query goes to the parent until you override a slot. This is the mechanism for “override only cmap” (the user manual covers it, `docs/usermanual-fonts-and-faces.xml` ≈ line 308). Since 11.2, a sub-font’s *own* synthetic bold/slant is honoured instead of the parent’s (NEWS).

### 3.3 Creation and choosing funcs

`hb_font_create` (`hb-font.cc:2145`) works in four steps:
1. It calls `_hb_font_create`, which sets scale = upem, `embolden_in_place = true`, and `instance_index = HB_FONT_NO_VAR_NAMED_INSTANCE`.
2. It calls `hb_font_set_funcs_using(font, nullptr)`.
3. If the face index has high bits, it applies that named instance (`hb_font_set_var_named_instance`).
4. Otherwise it calls `hb_font_set_variations(font, nullptr, 0)`, which picks up fvar defaults and avar.

`hb_font_set_funcs_using` (:2692) picks from `supported_font_funcs[]` (:2608): “ot”, “ft”, “fontations”, “coretext”, “directwrite”. The `HB_FONT_FUNCS` environment variable sets the default (:2638), and `hb_font_list_funcs()` lists them (11.0). The default for most users is therefore **hb-ot**, not FreeType.

`hb_font_set_face` is **deprecated in 15.0**. It now resets the funcs to the defaults for the new face (`hb-font.cc:2486–2509`).

### 3.4 Scale and the mults

`hb_font_t::changed()` (`hb-font.hh:1143`) recomputes the scale factors from `x_scale/upem`:
* the float `x_multf`;
* the 16.16 fixed-point `x_mult`, used by `em_mult`: `(v*mult + 32768) >> 16`;
* `x_strength = round(|x_scale| * x_embolden)`;
* `slant_xy = slant * x_scale / y_scale`.

It then **frees all per-shaper font data** (`data.fini()`) and bumps `serial`. `_hb_font_adopt_var_coords` (`hb-font.cc:2166`) sets `has_nonzero_coords` and syncs `serial_coords`. Changing a font while another thread shapes with it is therefore unsafe (inferred from `data.fini()` running inside `changed()`).

### 3.5 Synthetic bold and slant live in the font layer

Since 11.0.1, emboldening and slant are applied in `hb_font_t`, not in hb-ot or hb-ft, so they work with any funcs (NEWS 11.0.1). Slant also changes shaping output: at the end of GPOS, each glyph with a y offset in horizontal text has `slant_xy × y_offset` added to its x offset (`OT/Layout/GPOS/GPOS.hh:189`, called from `hb-ot-shape.cc:1082`).
* The advance getters add `x_strength` unless `embolden_in_place` (`hb-font.hh:355–430`).
* `get_glyph_extents` (`hb-font.hh:586`) tries the funcs’ own extents first, **unless the font is synthetic**. For a synthetic font it computes extents by *painting*, then by *drawing*, and only last from funcs extents plus `synthetic_glyph_extents` (:214).
* Slant is applied around the horizontal origin (12.3), not to the glyph origin (12.2).

### 3.6 Variations

* `hb_font_set_variations` (`hb-font.cc:3099`) is **not additive**. It starts from the fvar defaults, or from the named instance if one is set, then applies the list. `hb_font_set_variation` (singular, 7.1) *is* additive.
* `hb_font_set_var_coords_normalized` stores NaN design coords.
* Coords are stored twice: as normalized 2.14 ints (`coords`) and as `design_coords` (`hb-font.hh:147–151`).

### 3.7 hb-ot font funcs: where metrics come from (`hb-ot-font.cc`)

**Caches** (`struct hb_ot_font_t`, :71):
* A per-font, per-direction 1 KB **advance cache** (`hb_cache_t<24,16>`, :66) and a **v-origin cache** (`hb_cache_t<20,20>`).
* Item-variation-store scalar caches, and a gvar scalar cache.
* Each cache is held in an atomic slot and “acquired” by swapping it out with `cmpexch`, then released back. This lock-free borrow pattern lets concurrent shaping on one font work: a second thread just allocates a temporary cache (inferred from the acquire/release code).
* `check_serial` (:290) clears the origin caches when `serial` changes, and the advance/var caches only when `serial_coords` changes. Advances are cached *unscaled*, which is why a scale change does not invalidate them.

**h-advances** (`hb_ot_get_glyph_h_advances`, :382):
* no `hmtx` → every glyph gets **upem/2**;
* non-variable → hmtx scaled, uncached;
* variable → `HVAR` if present, else **gvar phantom points** (`glyf.get_advance_with_var_unscaled`), cached.

v-advances (:506) work like h-advances: `vmtx`, plus `VVAR` or `gvar` phantom points away from the default; with no `vmtx`, the font’s ascender-to-descender height. v-origins (:633) are a separate chain: `VORG` (+ VVAR `vorgMap`), else `vmtx` top side bearing *only with `glyf`*, else the glyph’s extents centered in the line, else the ascender. A CFF font without VORG ignores its vmtx tsb. (“Half the advance, ascender”, `hb-font.hh:858`, is the font object’s own guess when no funcs answer, not hb-ot’s.) A glyph past the end of `hmtx`’s side bearings gets advance 0, not the shared last advance.

**Extents** (`hb_ot_get_glyph_extents`, :811) are tried in this fixed order: `sbix` → `CBDT` → `COLR` → `VARC` → `glyf` → `CFF2` → `CFF `. Glyph names come from `post`, then CFF1.

**cmap** has its own 1 KB per-face cache (`hb-ot-cmap-table.hh:2172`). It chooses the best subtable, with symbol fonts mapped through a 0xF000 PUA shift and **legacy Arabic PUA** fonts through `_hb_arabic_pua_*_map` (:2210–2230).

**What hb-ot does *not* implement:** h_origin, contour_point (commented out, :991) and h_kerning. Legacy `kern` is applied by the shaper, not through font funcs.

**Font extents** go through `_hb_ot_metrics_get_position_common`, which reads OS/2/hhea with MVAR (:875).

**For the book:** separating “font funcs” from “shaping” is HarfBuzz’s central design choice. The same `ot` shaper runs on top of hb-ot, FreeType, fontations (Skrifa/read-fonts, Rust), CoreText or DirectWrite funcs, and `hb-shape --font-funcs=` makes the difference visible.

---

## 4. hb_buffer_t

**Files:** `hb-buffer.h`, `hb-buffer.hh`, `hb-buffer.cc`, `hb-buffer-serialize.cc`, `hb-buffer-deserialize-*.rl`, `hb-buffer-verify.cc`.

### 4.1 Layout

* `hb_glyph_info_t` (`hb-buffer.h:62`): `codepoint`, `mask` (private), `cluster`, `var1`, `var2`. `hb_glyph_position_t` (:191): advances, offsets, `var`.
* Both structs are 20 bytes (`hb-buffer.hh:38`, a static_assert). **That equality is essential**, because the `pos` array is reused as the output info array (below).
* Fields of `struct hb_buffer_t` (`hb-buffer.hh:70`):
  * `unicode` (funcs), `flags`, `cluster_level`;
  * `replacement` (U+FFFD), `invisible`, `not_found`, `not_found_variation_selector` (10.0);
  * `props` (direction, script, language);
  * `idx`, `len`, `out_len`, `info`, `out_info`, `pos`;
  * **pre/post context, 5 codepoints each** (`CONTEXT_LENGTH`, :109);
  * `digest`, `allocated_var_bits`, `serial`, `random_state`, `scratch_flags`, `max_len`, `max_ops`;
  * the message callback and the `changed_func` (13.0).

### 4.2 In-place input/output

`clear_output()` starts a pass with `out_info == info`.
* `next_glyph()` copies only if output and input have diverged (:357).
* `make_room_for` (`hb-buffer.cc:207`): the first time output would overtake input, **`out_info` is pointed at the `pos` array** and the output so far is copied there.
* `sync()` (:424) swaps the arrays back.

This is why positions do not exist during GSUB, and why `clear_positions()` starts the positioning phase.

### 4.3 The var1/var2 scratch registers

They are allocated byte by byte with `allocated_var_bits` and asserted with `HB_BUFFER_ALLOCATE_VAR/ASSERT_VAR` (`hb-buffer.hh:724`). The allocations:

| field | slot | lifetime | defined at |
|---|---|---|---|
| `unicode_props()` | var2.u16[0] | the whole shape | `hb-ot-layout.hh:154` |
| `glyph_props()` (GDEF class) | var1.u16[0] | GSUB+GPOS | :157 |
| `lig_props()` | var1.u8[2] | GSUB+GPOS | :158 |
| `syllable()` | var1.u8[3] | from a syllabic shaper’s first GSUB pause to `hb_syllabic_clear_var` at the end of GSUB; also borrowed as a ClassDef cache by format 2 context lookups when free (`hb-ot-layout-gsubgpos.hh:3079`) | :159 |
| `normalizer_glyph_index()` | var1.u32 | normalization only, then copied into codepoint | `hb-ot-shape-normalize.hh:35` |
| shaper category/aux | var2.u8[2], u8[3] | per shaper | `hb-ot-shaper.hh:38` |
| `attach_chain()`, `attach_type()` | pos.var | GPOS | `OT/Layout/GPOS/Common.hh:17` |

`unicode_props` packs data compactly (`hb-ot-layout.hh:186–220`):
* the low byte holds a 5-bit “modified” General_Category, plus IGNORABLE, HIDDEN and CONTINUATION bits;
* the high byte holds the modified combining class (for marks), ZWJ/ZWNJ/VS/AAT-deleted flags (for Cf), or a space-fallback type (for Zs);
* variation selectors are re-labeled from Mn to Cf so their flag fits.

### 4.4 The mask

* Bits 0–2 are public **glyph flags** (`HB_GLYPH_FLAG_UNSAFE_TO_BREAK` 1, `UNSAFE_TO_CONCAT` 2, `SAFE_TO_INSERT_TATWEEL` 4; `hb-buffer.h:161`).
* Bit 31 is the **global feature bit**.
* Features are allocated bits starting at `popcount(DEFINED)+1`, which is bit 4 (§9).
* `set_cluster()` *replaces* the glyph flags with the mask it is given when a cluster value changes (`hb-buffer.hh:642`); `delete_glyph` passes the deleted glyph’s flags. Note `_infos_set_glyph_flags`/`_infos_find_min_cluster` (`:664`, `:694`) test `== CHARACTERS`, not `!IS_MONOTONE`, so level 3 takes the monotone shortcut (draft bug report 5, `notes/upstream-bug-reports.md`).

### 4.5 Clusters

* `hb_buffer_add_utf*` (`hb-buffer.cc:1868`) sets `cluster` to the **code-unit offset** in the caller’s string (bytes for UTF-8). It stores up to 5 codepoints of pre-context (only when the buffer is empty and `item_offset > 0`) and of post-context. Invalid input becomes `replacement`.
* **Four cluster levels** (`hb-buffer.h:461`): 0 MONOTONE_GRAPHEMES (default), 1 MONOTONE_CHARACTERS, 2 CHARACTERS, and **3 GRAPHEMES (new in 11.0)**. The predicate macros `HB_BUFFER_CLUSTER_LEVEL_IS_MONOTONE/IS_GRAPHEMES/IS_CHARACTERS` (:478–509) are also 11.0. Code should test these predicates rather than compare the level to numbers.
* `merge_clusters` (`hb-buffer.hh:396`) merges only in monotone levels; otherwise it just marks unsafe-to-break. `merge_grapheme_clusters` merges only in grapheme levels. `merge_clusters_impl` (`hb-buffer.cc:569`) extends over neighboring runs with the same cluster, into the out-buffer if needed, and charges the work to `max_ops`.
* The header doc recommends level 1 for new clients. The user manual’s clusters chapter (`docs/usermanual-clusters.xml`) does not mention level 3: **the docs lag the code here.**

### 4.6 Flags

`HB_BUFFER_FLAG_*` (`hb-buffer.h:397`; `NEWS` dates BOT, EOT and PRESERVE to 0.9.7, though the header says 0.9.20). In the `ot` shaper only `hb_insert_dotted_circle` reads BOT, and nothing reads EOT; the verifier reads both. BOT, EOT, PRESERVE_ and REMOVE_DEFAULT_IGNORABLES, DO_NOT_INSERT_DOTTED_CIRCLE, VERIFY, PRODUCE_UNSAFE_TO_CONCAT, PRODUCE_SAFE_TO_INSERT_TATWEEL.
* The unsafe flags are set “interior” (`_set_glyph_flags_impl`, `hb-buffer.hh:445`). The cluster with the minimum value is spared, and the cluster level changes the logic.
* Ranges longer than 255 are ignored (:494).
* `unsafe_to_concat` is a no-op unless the client asked for it (:526).

### 4.7 Limits

`enter()` and `leave()` run around *every* shaper execution, including `hb_shape_plan_execute()` (`hb-shape-plan.cc:440`, `hb-buffer.cc:326`):
* `max_len = max(len*256, 65536)`;
* `max_ops = max(len*4096, 65536)` (`hb-limits.hh`).

Running out sets `successful = false`. Shaping still “returns true”, and callers must check `hb_buffer_allocation_successful()`. Since 15.1, the HarfRust backend reports its failures the same way (`hb-harfrust.cc`).

### 4.8 Messages and tracing

* `hb_buffer_set_message_func` sets the callback. `buffer->message()` (`hb-buffer.hh:622`) formats into a **100-byte buffer** (`hb-buffer.cc:2439`).
* **If the callback returns false, HarfBuzz skips that step**: a whole GSUB or GPOS table, a single lookup (`hb-ot-layout.cc:2093`), decompose/reorder/compose, fallback mark positioning, and so on.
* There are messages for: decompose/reorder/compose, preprocess-text, `start table GSUB script tag 'xxxx'`, `start lookup N feature 'xxxx'`, `skipped lookup … because no glyph matches`, and postprocess-glyphs.
* Since 12.0, the very detailed per-subtable messages need a build with `HB_BUFFER_MESSAGE_MORE=1` (`hb-debug.hh:452`).
* Since 13.0, a callback that edits glyph ids must call `hb_buffer_changed()` (`hb-buffer.cc:2433`). By default that refreshes the digest. A callback may not install another callback (`message_depth`, :2396).
* `hb-shape --trace` prints exactly these messages.

### 4.9 Verification

`HB_BUFFER_FLAG_VERIFY` makes `hb_shape_full` keep a copy of the text and call `buffer->verify` (`hb-buffer-verify.cc:380`), which runs three checks:
1. clusters are monotone;
2. re-shaping each safe-to-break fragment and concatenating reproduces the result;
3. (if PRODUCE_UNSAFE_TO_CONCAT) the odd/even segment interleave test described at :215–235.

Failures go to the message callback, or to stderr. `hb-shape --verify` uses this, and NEWS says the whole test suite passes with it.

### 4.10 Serialization

* There are TEXT and JSON formats (`hb-buffer.h:705`). The text form looks like `[gid1=0+561<46,545,434,-555>#flags|…]`.
* `--ned` prints absolute `@x,y` positions.
* The new 15.1 APIs `hb_buffer_deserialize_glyphs2/_unicode2` report the consumed byte offset, for introspection bindings.
* The deserializers are Ragel machines (`*.rl`). 15.0 rewrote the *number* parser without Ragel (NEWS).
* `hb_buffer_diff` (:851) compares buffers with a position fuzz, used by testing tools.

---

## 5. hb_shape / hb_shape_full

**File:** `hb-shape.cc`.

`hb_shape_full` (:127):
1. returns early if `len == 0`;
2. if VERIFY, copies the text;
3. calls `hb_shape_plan_create_cached2(face, props, features, coords **only if has_nonzero_coords**, shaper_list)`;
4. calls `hb_shape_plan_execute`, then destroys the plan;
5. runs verify.

`hb_shape` is the same with `shaper_list = NULL`. `hb_shape_list_shapers` (:102) returns the compiled-in list.

`hb_shape_justify` (:255, experimental API) varies the `jstf` or `wdth` axis with an ITP root-finder until the line advance hits a target. It is a nice example of using variations for justification.

---

## 6. Shaper backends (`hb-shaper-list.hh`)

Order matters. **With no shaper list, the first backend whose *face data* can be created wins** (`hb_shape_plan_key_t::init`, `hb-shape-plan.cc:75`). The `HB_SHAPER_LIST` environment variable reorders the list (`hb-shaper.cc:48`).

| order | shaper | build flag | what it is | when it is picked by default |
|---|---|---|---|---|
| 1 | `wasm` | `HAVE_WASM` (`-Dwasm`, “experimental”) | Runs a `shape` function exported by WebAssembly inside the font’s `Wasm` table, under wasm-micro-runtime (`hb-wasm-shape.cc`, `hb-wasm-api*.hh`, `docs/wasm-shaper.md`). Hardened in 15.0; can read user features since 14.3.1. | only fonts with a `Wasm` table (:168) |
| 2 | `graphite2` | `HAVE_GRAPHITE2` | SIL Graphite engine (`hb-graphite2.cc`). | only fonts with `Silf` (:114) |
| 3 | `ot` | default | **HarfBuzz’s own OpenType/AAT shaper.** Its face data always succeeds (`hb-ot-shape.cc:413`). Its font data is a GDEF ItemVariationStore cache (:433). | everything else |
| 4 | `uniscribe` | `HAVE_UNISCRIBE` (`-Dgdi`) | Calls Windows Uniscribe. | never (comes after `ot`) |
| 5 | `directwrite` | `HAVE_DIRECTWRITE` | Calls DirectWrite (`hb-directwrite-shape.cc`); not experimental since 11.0, supports variations and features. | never |
| 6 | `coretext` | `HAVE_CORETEXT` | Calls CoreText (`hb-coretext-shape.cc`). | never |
| 7 | `harfrust` | `HAVE_HARFRUST` | **HarfRust**, the Rust port of HarfBuzz shaping (currently 0.15, `rust/Cargo.toml`). It is called through `rust/shape.rs`, uses HarfBuzz’s *own* font funcs for cmap, advances and extents (`HBHarfBuzzFontFuncs`, `shape.rs:120–195`), and caches its plan in `hb_shape_plan_t::harfrust_data` (`hb-shape-plan.hh`). Used mainly for testing parity. | never |
| 8 | `kbts` | `HAVE_KBTS` | Single-header `kb_text_shape` 2.28g (`hb-kbts.cc`), with variations since 15.0. NEWS 11.4.0: “purely for testing and performance evaluation … NOT recommend[ed]”. | never |
| 9 | `fallback` | default | Plain cmap plus advances, nothing else. Default-ignorables become the space glyph (`hb-fallback-shape.cc:90`). | only if `ot` is compiled out |

“fontations” is **not a shaper**. It is a *font-funcs* backend (Skrifa/read-fonts, `rust/font.rs`, 11.0). The pairing “harfrust shaper + fontations funcs” is the all-Rust configuration.

**Surprises worth explaining:**
* Because `ot` always succeeds, the platform shapers (and harfrust/kbts) run **only when explicitly requested**: through a shaper list, `HB_SHAPER_LIST`, or `hb-shape --shapers=`.
* At execute time, `font->data.<shaper>` is created lazily. If *font* data creation fails, `hb_shape_plan_execute` returns false. It does **not** fall through to the next shaper (`hb-shape-plan.cc:433–446`, confirmed in the code). Note also that `hb_shape_plan_create2` builds the `ot` part of every plan, whichever backend will run it (`hb-shape-plan.cc:280`).
* Failed lazy creations of *shaper data* are remembered (`tag_null = true`, `hb-shaper.hh:104`). For tables the mechanism is different: a missing or broken table is stored as the empty blob, an ordinary value, so it is not looked for again. `tag_null` is used only when `create()` returns NULL (allocation failure).

---

## 7. Shape plans and their cache

**Files:** `hb-shape-plan.h/.hh/.cc`, `hb-ot-shape.hh` (`hb_ot_shape_plan_key_t`).

* **Key** (`hb_shape_plan_key_t`, `hb-shape-plan.hh:34`): segment props, user features, the `ot` key, and the shaper func. `equal` is at `hb-shape-plan.cc:177`.
* **User features match only on tag, value, and *whether they are global*.** Ranges are not part of the key (`user_features_match`, :159), because ranges are applied per buffer as masks (§9). (The normalization loop at :94 writes `features[0]` instead of `features[i]`. It looks like a harmless typo, since start/end are never compared; inferred.)
* **Variation coords are not in the key.** The key holds the *outcome* of FeatureVariations: `variations_index[2]`, plus, new with FeatureVariations 1.1 (14.6), the sorted list of true condition offsets `lookup_conditions[2]` (`hb-ot-shape.hh:51`). Two different coordinate sets that select the same feature variations share one plan.
* **The cache** (`hb_shape_plan_create_cached2`, `hb-shape-plan.cc:538`) is a lock-free singly-linked list on the face, prepended with `cmpexch` and retried on races, with a **one-entry `last_shape_plan` fast path** (added for 15.1’s “speed up shaping on faces with many shape plans”; `hb-face.hh:75`). Plans are **never evicted** while the face lives. A program that shapes with many feature combinations will slowly fill this list (inferred).
* `hb_shape_plan_create2` (:240) returns the empty plan for an invalid direction. It makes the face immutable and builds `ot` (`hb_ot_shape_plan_t::init0`, `hb-ot-shape.cc:227`), which runs the planner (§9) and compiles the map.
* `hb_shape_plan_execute` (:470) asserts that the plan’s face and props equal the font’s and buffer’s. It wraps the call in `buffer->enter()/leave()` and marks the content type GLYPHS.

---

## 8. Per-shaper data plumbing

`hb-shaper.hh` builds the per-object data. `HB_SHAPER_DATA_INSTANTIATE_SHAPERS` (`hb-shaper.hh:77`) generates a lazy loader per (shaper × {face, font}) inside `hb_shaper_object_dataset_t` (:112), which `hb_face_t::data` and `hb_font_t::data` both use. `HB_SHAPER_DATA_SUCCEEDED` is the pointer value 2 (:72). It is the “I have nothing to store but I’m fine” marker, which `ot`’s face data uses.

---

## 9. The `ot` planner and hb_ot_map

**Files:** `hb-ot-shape.cc`, `hb-ot-shape.hh`, `hb-ot-map.hh`, `hb-ot-map.cc`, `hb-ot-layout.cc` (map application, :2069).

### 9.1 Planner decisions (`hb_ot_shape_planner_t`, `hb-ot-shape.cc:83`, and `compile`, :106)

* The script shaper is chosen by `hb_ot_shaper_categorize(script, direction, chosen GSUB script tag)` (`hb-ot-shaper.hh:177`).
* **morx is applied** if the font has morx and (the text is horizontal *or* the font has no GSUB) (`_hb_apply_morx`, :60). In that case any non-default script shaper is replaced by `_hb_ot_shaper_dumber`.
* **Glyph classes** come from GDEF, or are synthesized from Unicode (`fallback_glyph_classes`, `hb_synthesize_glyph_classes` :856: Mn → mark, but never a default-ignorable).
* **Positioning** follows a precise decision tree (:162–220), sketched after this list.
* **Disabling GPOS:** a shaper’s `gpos_tag` (Hebrew uses `'hebr'`) turns off GPOS when the font’s chosen GPOS script differs (:131).
* **Mark zeroing:** `zero_marks` depends on the shaper (`zero_width_marks`: NONE, BY_GDEF_EARLY or BY_GDEF_LATE). It is suppressed under kerx, and under legacy kern that uses state machines.
* **`trak`** is applied only if the font has trak *and* a STAT table (“modern fonts”, :210).

The positioning decision tree (:162–220):
* kerx wins, unless the font has both GSUB and GPOS;
* otherwise GPOS;
* if GPOS has no kern feature, the next choice is kerx, then legacy `kern`, and **legacy `kern` only for shapers with `fallback_position`** (default, Arabic, Hangul, Hebrew; 12.2.0);
* otherwise “fallback kern” through the deprecated h_kerning font func.

Fallback *mark* positioning needs `!apply_gpos && !apply_kerx && (no kern or kern without cross-stream)` and a shaper with `fallback_position`. **A font with a GPOS table but no mark feature gets no fallback mark positioning.**

### 9.2 Feature collection order (`hb_ot_shape_collect_features`, :321)

1. `rvrn` (global), then **a GSUB pause**, so rvrn’s lookups form their own stage before everything else;
2. direction features: `ltra`/`ltrm` for LTR; `rtla` global and `rtlm` as a mask-controlled feature for RTL;
3. `frac`, `numr`, `dnom`, added non-global and masked later around U+2044;
4. `rand`, with `F_RANDOM` and max value 255;
5. **`Harf` and `HARF`**, after which the shaper’s `collect_features` runs, followed by **`Buzz` and `BUZZ`**. These private tags bracket the script shaper’s features, so a font can hook lookups in “before shaper” and “after shaper” positions (the comments say “considered required/discretionary”). The book could explain them; they are very rarely documented;
6. common features: `abvm blwm ccmp locl mark mkmk rlig` (mark and mkmk with manual joiners);
7. horizontal: `calt clig curs dist kern liga rclt`. Vertical: only `vert`, with **`F_GLOBAL_SEARCH`**, meaning “find any vert anywhere in the font if the LangSys lacks it”;
8. user features (global if their range is the whole buffer);
9. the shaper’s `override_features`.

The user manual’s list (`docs/usermanual-opentype-features.xml` :142–152) omits rvrn, the direction features, rand and the Harf/Buzz tags.

### 9.3 Map building (`hb_ot_map_builder_t`, `hb-ot-map.cc`)

* The constructor turns script and language into tags (§11). It selects the script in GSUB and GPOS separately, falling back DFLT → dflt → latn (`hb_ot_layout_table_select_script`, `hb-ot-layout.cc:564`), then selects the LangSys, falling back to dflt.
* `add_feature` records the current stage per table. `add_gsub_pause` / `add_gpos_pause` end a stage and may attach a **pause callback**.
* `compile` (:186):
  * sorts features (skipped in the “is_simple” case) and merges duplicates: a later global setting overrides, otherwise max_value wins and the lowest stage wins;
  * allocates mask bits. A **global feature with value 1 shares bit 31**. Others get `bit_storage(max_value)` bits, at most 8 (`HB_OT_MAP_MAX_BITS`), starting at bit 4. **When bits run out, the feature is dropped silently** (`next_bit + bits_needed >= global_bit_shift`, :263);
  * skips features absent from the font unless they have `F_HAS_FALLBACK` (e.g. `kern`);
  * puts the LangSys **required feature** in stage 0, unless its tag matches a known feature, in which case it goes in that feature’s stage.
* Per stage, it collects lookup indices from FeatureVariations (1.1 lookup variations through `get_lookup_variations`, else `hb_ot_layout_feature_with_variations_get_lookups`). It **sorts them by lookup index and merges duplicates** (OR-ing masks, AND-ing auto-zwj/zwnj). Within a stage, lookups therefore run in **lookup-list order, not feature order**: the key OpenType rule, made concrete.

### 9.4 Applying the map (`hb_ot_map_t::apply`, `hb-ot-layout.cc:2069`)

* It loops over stages and the lookups in each stage. A lookup is skipped when the buffer’s glyph-set digest misses the lookup’s digest; under PRODUCE_UNSAFE_TO_CONCAT a second-glyph digest is also checked.
* For each lookup it sets mask, auto_zwj/zwnj, random and per_syllable, then runs `apply_string`.
* After a stage it runs the pause func, and refreshes the digest if that func reports new glyphs.
* The digest is a three-way bit-pattern filter (`hb-set-digest.hh` header comment).

### 9.5 Masks at run time

`hb_set_unicode_props` gives every glyph `global_mask`. `hb_ot_shape_setup_masks` (`hb-ot-shape.cc:750`) then does three things:
* the fraction masks;
* the shaper’s `setup_masks` (e.g. Arabic joining forms);
* non-global user features, through `buffer->set_masks(value << shift, mask, start, end)`, where **start/end are compared against cluster values, not glyph indices** (`hb-buffer.cc:539`).

---

## 10. hb_ot_shape_internal, end to end (`hb-ot-shape.cc:1171`)

1. Save `target_direction`. Allocate `unicode_props`.
2. **`hb_set_unicode_props`** (:471): set mask to global, compute unicode_props, and mark grapheme *continuations*: marks; emoji modifiers; ZWJ, and the Extended_Pictographic after it; the second of a regional-indicator pair; U+FF9E/F; tag characters. Set the `HAS_FRACTION_SLASH` scratch flag.
3. **`hb_insert_dotted_circle`** (:552): if BOT, no pre-context, the first character is a mark, and the font has U+25CC, insert a dotted circle.
4. **`hb_form_clusters`** (:581): `merge_grapheme_clusters` over each grapheme (does nothing in the CHARACTERS levels except set unsafe-to-break).
5. **`hb_ensure_native_direction`** (:591): if the run’s direction is not the script’s native direction, reverse *graphemes* and flip `props.direction`. Digit-only or RI-only runs in RTL scripts are treated as native LTR. Vertical always becomes TTB. **Later stages see text in the script’s native order.**
6. The shaper’s `preprocess_text` (Arabic, Hangul, Thai, the Indic family…).
7. **`hb_ot_substitute_pre`** (:936):
   * `hb_ot_rotate_chars`: if the target direction is backward, mirror characters with Bidi_Mirroring_Glyph when the font has the mirror, else set the `rtlm` mask bit. In vertical text without `vert`, map to the U+FE1x/FE3x vertical forms (`vertical_char_for`);
   * **normalization** (§12), which also does the **cmap lookup** into `normalizer_glyph_index`;
   * `setup_masks` (§9.5);
   * fallback-mark recategorization of combining classes (only when fallback mark positioning will run);
   * `hb_ot_map_glyphs_fast`: copy the glyph index into `codepoint`, content becomes GLYPHS;
   * allocate the gsubgpos vars;
   * set GDEF glyph props and the digest, or synthesize classes;
   * **GSUB** (`map.substitute`), or **morx**. With morx followed by GPOS, deleted glyphs are removed here.
8. **`hb_ot_position`** (:1094):
   * `clear_positions`;
   * `hb_ot_position_default`: batch advances, and subtract h_origins (only if the funcs provide them) or v_origins (always, for vertical); then the **space fallback** widths (`_hb_ot_shape_fallback_spaces`: em/2, em/3 … figure, punctuation and narrow spaces);
   * `hb_ot_position_plan`:
     * add h_origins (GPOS works in horizontal-origin space);
     * `position_start`;
     * zero marks EARLY;
     * **GPOS**, or kerx, then kern or fallback kern, then trak;
     * zero marks LATE;
     * `position_finish_advances`, then zero the width of default-ignorables, then `position_finish_offsets` (this order is required);
     * subtract h_origins;
     * **fallback mark positioning**;
   * if the direction is backward, **reverse the buffer**. This is the only point where HarfBuzz output becomes visual (left-to-right) order.
9. **`hb_ot_substitute_post`** (:951): remove AAT deleted glyphs (morx without GPOS). Replace unmatched variation selectors with `not_found_variation_selector`, if set. **Hide default-ignorables**: replace them with `buffer->invisible` or the space glyph, or delete them if REMOVE_DEFAULT_IGNORABLES. Then the shaper’s `postprocess_glyphs`. (Default-ignorables are hidden *after* positioning, so they take part in GSUB/GPOS context and kerning.)
10. **`hb_propagate_flags`** (:1109): OR the glyph flags across each cluster. Mask out UNSAFE_TO_CONCAT unless requested. Reconcile SAFE_TO_INSERT_TATWEEL with UNSAFE_TO_BREAK.
11. Deallocate the vars and restore the original `props.direction`.

You can see most steps with `build/util/hb-shape --trace` (output checked on `test/shape/data/in-house/fonts/NotoSans-VF.abc.ttf` and `NotoNastaliqUrdu-Regular.ttf`).

---

**Additions from chapter 13** (checked against the code):
* The final reversal is `hb_buffer_reverse` over whole glyphs, not graphemes, so in an RTL run a mark is listed before its base.
* Mirroring uses `target_direction`, not the possibly flipped `props.direction`: an Arabic run given as LTR is reversed but not mirrored. Every non-mirrored character gets the `rtlm` mask bit.
* `position_finish_advances` is empty in 15.1.0 (`OT/Layout/GPOS/GPOS.hh:158`).
* Marks are zeroed EARLY by USE and Myanmar; Indic, Khmer, Hangul and dumber use NONE.
* With hb-ot funcs the h-origin steps never run: hb-ot sets only `v_origins` (`hb-ot-font.cc:979`).

## 11. Script and language tags (`hb-ot-tag.cc`, `hb-ot-tag-table.hh`)

* **Script → tags** (`hb_ot_all_tags_from_script`, :157). For the Indic scripts and Myanmar, the order is **`xxx3`** (except Myanmar), then **`xxx2`**, then the old tag (e.g. `dev3, dev2, deva`). The old tag is ISO 15924 with the first letter lowercased, plus exceptions: `kana` for Hiragana and Hrkt (14.2.1); `lao `, `yi  `, `nko `, `vai ` (space-padded); `math`. (Whether any fonts actually use `dev3` I didn’t check; the code asks for it first.)
* **Language → tags** (:322). The input is a BCP 47 string, matched in this order:
  * multi-subtag “complex” matches;
  * an extlang subtag if present;
  * a binary search of `ot_languages2` (two-letter codes, which can give several tags) and `ot_languages3`, with a one-entry “poor man’s cache” each;
  * a blocked list;
  * otherwise an **unknown 3-letter code is upper-cased and used as is**.
* The table comes from the IANA subtag registry (File-Date 2026-09-17).
* **Private-use overrides:** `x-hbscXXXX` forces a script tag and `x-hbotXXXX` a language tag (`parse_private_use_subtag`, :444). Hex forms like `-hbsc-64657633` are also accepted.
* The reverse mapping is `hb_ot_tags_to_script_and_language` (:653).
* NEWS 14.5.1 adds `fonupa` → `UPPH`. 15.1 speeds up `hb_language_from_string` (in `hb-common.cc`, not surveyed).

---

## 12. Normalization (`hb-ot-shape-normalize.cc`)

The design comment (:36–75) is worth quoting in the book: it is “like Unicode normalization”, except that decomposition and recomposition **only happen if the font has the resulting glyphs**. There are three rounds, each with a message.

1. **Decompose** (:323). Runs of non-marks short-circuit through batch `get_nominal_glyphs`. For each character:
   * `decompose_current_character` (:150) prefers the character itself (in shortest mode), otherwise a recursive 1:2 canonical decomposition the font supports;
   * otherwise the space fallback: a Zs character maps to the space glyph and is tagged for width adjustment later;
   * otherwise U+2011 → U+2010;
   * otherwise .notdef (`buffer->not_found`).
   * Clusters containing a **variation selector skip normalization**. If `get_variation_glyph` succeeds, base+VS collapse to one glyph (`replace_glyphs(2,1)`). Otherwise both go through and the VS is flagged (for `not_found_variation_selector`) (:204).
2. **Reorder** (:370). Sort by *modified* combining class for runs up to `HB_OT_SHAPE_MAX_COMBINING_MARKS` = 32 (longer runs are left alone), then the shaper’s `reorder_marks` hook. A CGJ that blocked no reordering becomes skippable (#554).
3. **Recompose** (:415). Only in COMPOSED_DIACRITICS modes. Only *marks* compose with the preceding starter, never base+base (“desired for Hangul”). Composition also needs the font to have the composite glyph.

* **Modes** (`hb-ot-shape-normalize.hh:40`): NONE, DECOMPOSED, COMPOSED_DIACRITICS, COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT (used by Indic, Khmer, Myanmar and USE), and AUTO. **AUTO resolves to COMPOSED_DIACRITICS whether or not the plan has a `mark` feature.** The branch that once chose DECOMPOSED is commented out (:289–297); old descriptions saying “HarfBuzz decomposes when the font has GPOS mark” are wrong.
* **Modified combining classes** (`hb-unicode.hh:106`, table `hb-unicode.cc:500`) reorder Hebrew, Arabic, Thai, Lao and Tibetan classes so the result suits fonts. There are special cases for SAKOT (U+1A60) and PADMA (U+0FC6), both to 254, and U+0F39 (to 127).
* Shapers can replace `decompose` and `compose` (the Indic family does, e.g. to avoid recomposing split matras).

---

**Corrections from chapter 14:** the third round’s trace messages are “start compose” / “end compose”; the rounds start at :322, :372, :420. The batch fast path runs only in the short-circuiting modes. Clusters with marks are decomposed non-shortest except in NONE mode; round 3 also needs `!all_simple`; NONE still decomposes what the font lacks, and still reorders. No shaper uses DECOMPOSED; `dumber` uses AUTO, and AUTO always resolves to COMPOSED_DIACRITICS (issue #653). The not-found glyph doesn’t apply in variation-selector clusters (draft report 11). The modified classes don’t change Lao (identity, `hb-unicode.cc:559`) and do change Telugu (84, 91 → 4, 5). Hebrew’s `compose` still uses `has_gpos_mark`.

## 13. hb-unicode and the UCD tables

* **The vtable** (`hb-unicode.hh:41`): combining_class, general_category, mirroring, script, compose, decompose. eastasian_width and decompose_compatibility are deprecated. A parent lets you override single callbacks, but unlike font funcs the child *copies* the parent’s pointers at creation and never delegates at shaping time (`hb-unicode.cc:182`, `:386`). `hb_unicode_funcs_get_empty` returns the nil funcs (`hb_font_funcs_get_empty` returns the default ones).
* **The default** (`hb_unicode_funcs_get_default`, `hb-unicode.cc:152`) is **hb-ucd** (built-in tables), else GLib, else ICU. Building with none is an `#error`.
* **`hb-ucd.cc`** reads compact tables generated by `gen-ucd-table.py` from `ucd.nounihan.grouped.xml`. The checkout is at **Unicode 18.0.0** (`hb-ucd-table.hh` header; NEWS 14.5.0). Hangul composition and decomposition are algorithmic (`hb-ucd.cc` ≈ :55–100). Mirroring is stored as a delta (`unicode + _hb_ucd_bmg(u)`). Emoji Extended_Pictographic comes from `hb-unicode-emoji-table.hh`.
* **Properties hard-coded in hb-unicode.hh, not taken from the funcs:**
  * `is_default_ignorable` (:167) is a hand-written switch that *differs* from Unicode’s DI property: Mongolian FVS and CGJ are “hidden but not ignored” for GSUB;
  * `space_fallback_type` (:219);
  * `vertical_char_for` (:245);
  * `is_variation_selector`.
  These do not change even if a client replaces the Unicode funcs. (Worth noting for integrators who use ICU funcs.)
* **The script itemizer is not in HarfBuzz.** `guess_segment_properties` (`hb-buffer.cc:746`) only takes the first strong script, then derives direction, then the locale language.

---

## 14. Fallback positioning (`hb-ot-shape-fallback.cc`)

* **Mark positioning** (`_hb_ot_shape_fallback_mark_position`, :470): marks are clustered around the preceding base (skipping hidden and default-ignorable glyphs). Each mark is placed from **glyph extents only**, using its recategorized combining class:
  * the class is mapped to above, below, left, right or attached (`recategorize_combining_class`, :35, with Thai and Lao per-character cases);
  * the mark is centered or aligned left or right on the base’s ink box (:211);
  * a gap of y_scale/16 is added, and stacked marks grow the box;
  * below-marks are never shifted up, and above-marks are not shifted far down.
  This makes it *font-extents-dependent*, so results differ between font-func backends (inferred).
* **Fallback kern** (:523): only through the deprecated `get_glyph_h_kerning` font func (e.g. FreeType’s), driven by the generic `hb_kern_machine_t`. It does nothing with hb-ot funcs.
* **Space widths** (:559): 1/n em for the EM_n spaces, 4/18 em for MMSP, the width of a digit for FIGURE SPACE, of `.` or `,` for PUNCTUATION SPACE, half the space for NNBSP. If the font lacks U+0020 and `invisible` was used, the space gets 1/4 em.

---

## 15. Things that look new or changed (versus older descriptions of HarfBuzz)

| Area | Now (15.1) | Older descriptions say | Since |
|---|---|---|---|
| Sanitize | Never edits data; invalid GSUB/GPOS rejected outright | “neuters” bad offsets, makes blobs writable | 12.3 (rejection); header comment |
| Default font funcs | `hb_font_create` installs hb-ot (or `HB_FONT_FUNCS`); there are 5 named backends (ot, ft, fontations, coretext, directwrite) | FreeType via hb-ft is the norm | 11.0 |
| Face loaders | `hb_face_create_from_file_or_fail_using`, loaders by name | only blob + index | 10.1/11.0 |
| `hb_font_set_face` | deprecated; resets funcs | supported | 15.0 |
| Synthetic bold/slant | applied in hb_font_t for any funcs; per sub-font; extents via paint/draw | backend-specific | 11.0 / 11.2 |
| Cluster levels | adds level 3 `GRAPHEMES` and `IS_*` predicate macros | three levels | 11.0 |
| Buffer messages | the step can be skipped; `hb_buffer_changed()`; “more” messages need `HB_BUFFER_MESSAGE_MORE` | always verbose | 12.0 / 13.0 |
| Buffer work limits | `enter()/leave()` also around `hb_shape_plan_execute` | only hb_shape | (code comment, `hb-buffer.cc:330`) |
| Shape plan key | holds FeatureVariations *condition outcomes* (1.1 lookup variations) | variations_index only | 14.6 |
| Plan cache | adds a one-entry last-plan fast path | linear list | 15.1 |
| Legacy `kern` | applied only by default, Arabic, Hangul and Hebrew shapers | all shapers | 12.2 |
| Context matching in syllabic shapers | backtrack and lookahead confined to the syllable (as DirectWrite) | can cross syllables | 12.2 (GSUB internals; noted for cross-reference) |
| Mark positioning across the line | cross-direction shifts from later lookups no longer drag marks | | 14.3 |
| `trak` | back to being applied during shaping (not in advances), only with STAT | applied in font funcs (10.3 only) | 11.0.1 |
| Shapers list | harfrust (Rust port), kbts (testing only), wasm, directwrite no longer experimental | ot/graphite/uniscribe/coretext/fallback | 11.2–15.0 |
| Allocation | `ot` shaping, hb-ot drawing and painting are malloc-free once warmed | | 11.0 |
| Positions | saturating arithmetic for positions and extents | wraparound | 14.4 |
| Glyph extents | rounded (not floor/ceil) in hb-ot and hb-ft; later, float scaling then rounding outwards across but *inwards* up and down (floor of top, ceil of bottom, `hb-font.hh:201`) | floor/ceil | 11.0 / 14.2.1 |
| `HB_OT_SHAPE_BUFFER_FORMAT_SERIAL` | serial number for the internal info/pos layout (value 1) | | 13.2 |
| Beyond-64k glyphs, cubic `GLYF` | on by default (OFF 5th edition) | experimental | 15.0 |
| Unicode | 18.0 data | | 14.5 |
| Glyph origins | batch `get_glyph_h/v_origins` funcs | single only | 11.3 |
| Arabic Windows-1256 fallback | enabled on all platforms | Windows only | 14.4 |
| Normalization AUTO | always COMPOSED_DIACRITICS | DECOMPOSED when GPOS mark exists | (code; date unknown) |

**Where the docs disagree with the code:**
* `docs/usermanual-getting-started.xml` :71 calls DirectWrite integration experimental; NEWS 11.0 says it graduated.
* The clusters chapter omits level 3.
* The features chapter omits rvrn, the direction features, rand and the Harf/Buzz tags, and simplifies the kerx/GPOS/kern precedence.

---

## 16. Suggested chapter and section breakdown for this area

**Part: The object model**
1. *Bytes, faces and tables*: blobs and memory modes; mmap and sub-blobs; lazy table loaders; the sanitize contract (and why it stopped editing); collections and the named-instance bits in the face index; `create_for_tables` and the face builder; face loaders.
2. *Fonts*: scale, ppem and ptem; the 16.16 mults; the font-funcs vtable and its nil/default/parent tiers; sub-fonts as overrides; the font-funcs backends (hb-ot, hb-ft, fontations, CoreText, DirectWrite); serials and caches; synthetic bold and slant; variation coordinates (design versus normalized; set_variations is not additive).
3. *Where metrics come from*: hb-ot in detail. cmap subtable choice (with symbol and Arabic-PUA quirks); hmtx/HVAR/gvar phantom points; vertical origins (VORG, vmtx, fallbacks); the extents priority chain; font extents and MVAR.
4. *Unicode inside HarfBuzz*: hb_unicode_funcs; the UCD tables and their generator; HarfBuzz’s own default-ignorable, space, vertical-form and modified-combining-class rules; script and direction guessing.
5. *Buffers*: info and pos; clusters (all four levels, with worked examples); context; flags; the in-place output trick; the var1/var2 register file; glyph flags (unsafe-to-break, unsafe-to-concat, tatweel) and how they are propagated; limits and error reporting; serialization formats; buffer diff.

**Part: The shaping pipeline**

6. *hb_shape and the backends*: shaper selection, `HB_SHAPER_LIST`, what each backend is, and the all-Rust (harfrust + fontations) configuration.
7. *Shape plans*: what a plan is; its key (and what is not in it); the cache and its lifetime; executing a plan directly.
8. *From features to lookups: hb_ot_map*: tags (script and language selection, `x-hbsc`/`x-hbot`); feature collection order (rvrn, direction, Harf/Buzz, common, horizontal or vertical, user, overrides); stages and pauses; mask-bit allocation and its limits; required features; FeatureVariations; lookup ordering within a stage; digests.
9. *The pipeline, step by step*: §10 as a walkthrough with `hb-shape --trace` output at each stage, including native-direction reversal, mirroring and vertical forms, dotted circles, grapheme clusters, normalization and cmap, masks, GSUB or morx, positioning (origins, zeroing marks, finishing), reversal to visual order, hiding default-ignorables, and flag propagation.
10. *Normalization*: font-aware NFC/NFD, the three rounds, the modes per shaper, variation selectors, CGJ.
11. *When the font lacks something: fallbacks*: synthesized GDEF classes, the space-width fallback, fallback mark positioning by combining class, fallback kern, legacy kern, and the decision tree for who positions.
12. *Seeing inside: tracing and verification*: message callbacks (including skipping steps), `hb_buffer_changed`, `HB_BUFFER_MESSAGE_MORE`, `HB_BUFFER_FLAG_VERIFY` and the three invariants, `hb-shape` options (`--trace`, `--verify`, `--show-flags`, `--cluster-level`, `--shapers`, `--font-funcs`, `--ned`).
13. *Appendix: compile-time configuration*: `HB_NO_*`, `HB_LEAN`, `HB_MINI`, `HB_TINY` and their effect on the table list and the pipeline (only touched on here; `CONFIG.md` covers it).


[Corrections from chapter 40: `hb_buffer_diff` is at `hb-buffer.cc:2278`; `hb_buffer_append` has copied context since 2.9.1 (`hb-buffer.cc:2139`–`2154`); context is read only by Arabic joining, the dotted-circle test and harfrust; `hb_shape_justify` needs `-Dexperimental_api`.]
