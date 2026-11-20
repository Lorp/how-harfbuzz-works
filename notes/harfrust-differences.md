# HarfRust and HarfBuzz: every `shape` example, run through both

Results of running every line of every `shape` block in `book/**/*.md` through HarfBuzz’s `ot` shaper and through HarfRust, for chapter 47 ([HarfRust](../book/chapters/harfrust.md)). Run on 18 November 2026, against HarfBuzz 15.1.0; rerun on 20 November 2026, against 15.2.0, below. The sections after the rerun describe the 18 November run.

## Rerun on 20 November 2026: HarfBuzz 15.2.0 and HarfRust 0.16.1

The book moved to HarfBuzz 15.2.0, whose `harfrust` backend builds HarfRust 0.16.1 (`src/rust/Cargo.toml:7`), tagged 19 November 2026, whose README says “Matches HarfBuzz 15.2.0”. So the backend no longer lags a release behind. The script and results of the rerun are `compare.py` and `results.json` in the session scratchpad (`/private/tmp/claude-501/-Users-lorp-GitHub-how-harfbuzz-works/17a92970-ea22-4179-9301-0a97040b8812/scratchpad/harfrust2/`); 0.16.1 was cloned and built there too, as `hr-0.16.1/`.

| | Lines |
|---|---|
| `shape` lines in the book | 913 |
| not compared (own `--shapers`, `--list-shapers`) | 11 |
| identical, backend against `ot` | 887 |
| differ: options the backend doesn’t pass on (invisible glyph, ppem, slant) | 6 |
| differ: real divergences | 9 |

The nine: seven malformed fonts, the unsorted PairSet, and the `kerx` tuple offset. Three of the 18 November divergences are gone: HarfRust 0.16.1 fixed the `morx` noncontextual feature ranges and the `kerx` control-point action (items 1 and 3 of “Possible upstream reports” below), and HarfBuzz’s #6696 (HHW-1) makes `null-coverage-f1.ttf` agree. The backend now passes the not-found glyph (`src/rust/shape.rs:374`).

`hr-shape` 0.16.1 against `ot`: 883 lines ran, 870 identical, and 4 differ only in metrics.

The HarfRust chapter was rewritten from this rerun.

## What was run

* **HarfBuzz 15.1.0, `ot`.** `.cache/harfbuzz/build/util/hb-shape`, as the book uses.
* **HarfBuzz 15.1.0, `harfrust` backend.** `.cache/harfbuzz/build-harfrust/util/hb-shape --shapers=harfrust`, built by the fourth step of `tools/build-harfbuzz.sh` (`-Dharfrust=enabled`, Rust nightly, bindgen 0.73.2). HarfBuzz 15.1.0’s `src/rust/Cargo.toml:7` asks for `harfrust = { version = "0.15.0" }`, which Cargo resolves to **HarfRust 0.15.0**, with read-fonts 0.46.0 and skrifa 0.49.0. HarfRust’s `CHANGELOG.md` says 0.15.0 “matches HarfBuzz v15.0.0”. This is the primary comparison, because the backend gives HarfRust the same font functions as `ot` (`src/rust/shape.rs:116`, `:422`), so a difference is a difference in shaping.
* **HarfRust 0.16.0, `hr-shape`.** The pinned release: tag `0.16.0`, commit `0de7fe25`, 11 November 2026, cloned to `.cache/harfrust/`, built with `cargo build --release -p hr-shape`. It is the release in step with 15.1.0: its `README.md:20` says “Matches HarfBuzz v15.1.0”, and so does its `CHANGELOG.md` entry. HarfBuzz 15.1.0 can’t build against it (it asks for 0.15, and 0.16 needs read-fonts 0.47), so it runs through its own command-line tool, which uses HarfRust’s built-in font metrics, not HarfBuzz’s.
* **HarfRust main, `hr-shape`**, commit `38340b57` (17 November 2026), to see what has been ported since 0.16.0.
* **HarfBuzz 15.0.0, `ot`**, built from `/Users/lorp/GitHub/harfbuzz` at the tag, to sort out lag: a difference where the backend’s output equals HarfBuzz 15.0.0’s, and 15.0.0’s differs from 15.1.0’s, is HarfRust being one release behind.

All with `LC_ALL=C.UTF-8`, fonts resolved as `fontPath` in `tools/build-site.mjs` does. The script is `compare.py` in the session scratchpad (`/private/tmp/claude-501/-Users-lorp-GitHub-how-harfbuzz-works/17a92970-ea22-4179-9301-0a97040b8812/scratchpad/harfrust/`); it writes `results.json` with every output.

## Numbers

### The `harfrust` backend (HarfRust 0.15.0) against `ot`

| | Lines |
|---|---|
| `shape` lines in the book | 880 |
| not compared: the line picks its own shaper with `--shapers` | 10 |
| not compared: `--list-shapers` (lists the build’s shapers, not a shaping result) | 1 |
| compared | 869 |
| identical | 843 |
| different | 26 |
| … lag: HarfRust 0.15.0 gives HarfBuzz 15.0.0’s output | 4 |
| … an option the backend doesn’t pass on to HarfRust | 7 |
| … real divergences | 15 |
| … … of which fixed in HarfRust 0.16.0 | 3 (one of them only down to lag) |

**Lag, in a sentence.** All four are AAT fixes listed in HarfBuzz 15.1.0’s `NEWS` (“wrong `kerx` kerning (formats 1 and 2)”, “ignored `kern` and `mort` tables with a non-first initial state”) or made in its git log (each applied AAT subtable pass charged to `max_ops`, 663a004d7), which HarfRust 0.15.0, matching 15.0.0, doesn’t have yet; 0.16.0 has three of them. The four: `loop.ttf  ae` (aat-inside-harfbuzz.md:205), `format2.ttf  AVTo` (aat-positioning.md:93), the kerx format 1 test font `36f8d640…ttf  aab` (aat-positioning.md:119), and the `kern` state-table font `a5baedaf…ttf  ab` (legacy-kern.md:84).

### HarfRust 0.16.0’s `hr-shape` against `ot`

| | Lines |
|---|---|
| `shape` lines | 880 |
| can’t run: `hr-shape` has no such option | 28 |
| can’t run: face index with named-instance bits (`--face-index=65536` …) | 4 |
| run | 848 |
| identical | 826 |
| different | 22 |
| … HarfRust’s own font metrics, not shaping | 8 |
| … shaping, the same as the backend’s remaining real divergences | 12 |
| … `loop.ttf`, lag in 0.15.0 still not matched | 1 |
| … the Arabic `kerx` format 4 font: lag, ported after 0.16.0 | 1 |

The options `hr-shape` 0.16.0 lacks: `--shapers` (10 lines), `--list-shapers` (1), `--output-format=json` (2), `--font-bold` (3), `--font-grade` (1), `--font-slant` (2), `--font-ppem` (3), `--invisible-glyph` (3), `--sub-font` (1), `--not-found-glyph` (2). HarfRust main adds `--not-found-glyph` (commit 38340b57, “Add configurable not-found glyph”).

HarfRust main: 830 run, 828 identical. The Arabic format 4 font now matches (commit aec3d280, “Apply kerx cross-direction mark offsets immediately”, the port of HarfBuzz’s #6537). One new difference, from the new not-found glyph: `norm.ttf  x\uFE00  --not-found-glyph=27` gives `[missing=0|space=0]` where HarfBuzz gives `[.notdef=0|space=0]`. The book (normalization.md:224) shows HarfBuzz’s as a gap: a base before a variation selector doesn’t get the not-found glyph. HarfRust main doesn’t have the gap.

## Options the backend doesn’t pass on

The backend copies the buffer’s flags, cluster level, not-found variation-selector glyph and context into a HarfRust buffer (`src/rust/shape.rs:336`–`411`), and gives HarfRust the font’s scale and point size and its font funcs (`:220`, `:422`). It doesn’t pass the buffer’s invisible glyph or not-found glyph, the font’s ppem, or its synthetic slant. HarfRust 0.15.0 has `Buffer::set_invisible_glyph`; it got a not-found glyph only after 0.16.0; it has no ppem and no slant.

| Line | Option | `ot` | backend |
|---|---|---|---|
| fallbacks.md:350 | `no-space.ttf  \u0020  --invisible-glyph=4` | `[o=0+250]` | `[.notdef=0+500]` |
| fallbacks.md:351 | `no-space.ttf  \u2003  --invisible-glyph=4` | `[o=0+1000]` | `[.notdef=0+500]` |
| fallbacks.md:352 | `no-space.ttf  \u202F  --invisible-glyph=4` | `[o=0+125]` | `[.notdef=0+500]` |
| normalization.md:220 | `norm.ttf  x\u0301  --not-found-glyph=27` | `[missing=0\|acutecomb=0]` | `[.notdef=0\|acutecomb=0]` |
| fonts-and-font-functions.md:73 | `funcs.ttf  HI  --font-ppem=12` | `[H=0+517\|I=1+275]` | `[H=0+600\|I=1+275]` |
| fonts-and-font-functions.md:75 | `funcs.ttf  HI  --font-size=12  --font-ppem=12` | `[H=0+6\|I=1+3]` | `[H=0+7\|I=1+3]` |
| fonts-and-font-functions.md:335 | `funcs.ttf  HÍ  --font-slant=0.2  --show-extents` | acute `@2,-50` | acute `@12,-50` |

The ppem lines lose the GPOS Device table’s pixel delta (`HintingDevice::get_delta`, `hb-ot-layout-common.hh:6239`, needs ppem). The slant line loses the adjustment that `GPOS::position_finish_offsets` makes to y-offset marks when the font is slanted (`OT/Layout/GPOS/GPOS.hh:189`), which is in `ot` only. Synthetic bold and grade do reach HarfRust, through the font funcs: those lines are identical.

**Possible HarfBuzz backend gap** (not filed): passing `hb_buffer_get_invisible_glyph` and `hb_buffer_get_not_found_glyph` to HarfRust’s buffer would close four of these.

## Real divergences

Each against HarfBuzz 15.1.0 `ot`. “0.15” is the backend, “0.16” is `hr-shape` 0.16.0, “main” is `hr-shape` at 38340b57.

### AAT

1. **`morx` feature ranges in noncontextual subtables.** aat-inside-harfbuzz.md:137, `latin.ttf  aaa  --features=smcp[1:2]`. `ot`: `[a=0+500|a.sc=1+450|a=2+500]`. 0.15, 0.16, main: `[a=0+500|a=1+500|a=2+500]`. Cause (read from the code): HarfRust’s `apply_noncontextual` (`harfrust/src/aat/morx.rs:811`) loops over the glyphs with `i` but looks up the range with `ac.buffer.cur(0)?.cluster` (`:827`), the cluster of the glyph at `buffer.idx`, which doesn’t move in that loop; so every glyph gets the first glyph’s range. HarfBuzz uses `info[i].cluster` (`hb-aat-layout-morx-table.hh:661`). Tested: `smcp[0:1]` makes all three small caps in HarfRust, `smcp[1:3]` none. `-liga[1:2]` on `fifi` (ligature subtable, a state machine) matches. **Looks like a HarfRust bug.**
2. **`kerx` tuple values, from where the offset counts.** aat-positioning.md:61, `tuples.ttf  AVTo`. `ot`: `[A=0+560|V=1@-40,0+560|T=2+550|o=3@-50,0+450]`. 0.15, 0.16, main: `[A=0+550|V=1@-50,0+550|…]`. The A–V pair’s value is offset 58, the start of `[-80, -160, -240]`. HarfBuzz reads it from the start of the subtable (`kerxTupleKern (v, …, this, c)`, `hb-aat-layout-kerx-table.hh:102`) and finds −80. HarfRust reads it from `Subtable0::offset_data()` (`harfrust/src/aat/kerx.rs:173`, `:186`), and read-fonts gives the format 0 subtable the bytes after the 12-byte subtable header (`read-fonts/src/tables/kerx.rs:64`, `:92`, read-fonts 0.47.0), so it reads 12 bytes further on, the −100 of another pair. (T–o’s −100 is right in both by coincidence of the test font’s layout: its offset 64 + 12 lands on another −100.) Apple’s spec doesn’t say which base, so this is a disagreement, not clearly a bug in either; HarfBuzz’s reading is the one its `NEWS` (2.1.0) says fixed San Francisco.
3. **`kerx` format 4 control-point actions.** aat-positioning.md:206, `points.ttf  A\u0301o\u0301`. `ot`: `[A=0+600|acutecomb=0+0|o=2+500|acutecomb=2+0]`. 0.15, 0.16, main: `[A=0+600|acutecomb=0@-600,0+0|o=2+500|acutecomb=2@-500,0+0]`. HarfBuzz’s default funcs can’t find a contour point, so the action does nothing and nothing is attached (`hb-aat-layout-kerx-table.hh:626`). HarfRust’s `Driver4::perform_action` (`harfrust/src/aat/kerx.rs:702`) handles anchor-point and coordinate actions; a control-point action falls into `_ => {}` (`:762`) and then the glyph is still marked attached with offset 0 (`:765`–`767`), which puts each acute at its base’s origin. **Looks like a HarfRust bug.**
4. **`morx` loop budget.** aat-inside-harfbuzz.md:205, `loop.ttf  ae`. `ot` 15.1.0: `[a=0+500|e=1+500]`; 15.0.0, 0.15, 0.16, main: `[a=0+500|e.sc=1+450]`. Lag for 0.15 (HarfBuzz 663a004d7 charges each subtable pass to `max_ops`, so the second subtable never runs once a DontAdvance loop has spent the budget). HarfRust 0.16.0’s changelog says it bounds “AAT processing”, but the second subtable still runs. Remains a divergence in 0.16 and main.
5. **`kerx` Backwards on pair formats.** aat-positioning.md:46, `backwards.ttf  AVTo`. `ot` (15.0.0 and 15.1.0): `[A=0+600|V=1+600|T=2+600|o=3+500]` (the subtable is skipped). 0.15: kerned, `[A=0+560|V=1@-40,0+560|T=2+550|o=3@-50,0+450]`. Fixed in 0.16 (“Handle … `kerx` processing direction”, CHANGELOG 0.16.0).
6. **`kerx` format 4 with Backwards, attaching to a later glyph.** aat-positioning.md:216, `1bfb8aab…ttf  xzbb`. `ot`: `[m=0@925,600+150|…]`. 0.15: `[m=0+150|…]`, not attached. Fixed in 0.16.
7. **Arabic `kerx` format 4.** aat-positioning.md:224, `a8b4a746…ttf  \u0643\u064F\u0644\u064F\u0651`. `ot` 15.1.0: first damma `@112,-32`; 15.0.0 and 0.16: `@112,122` (the 14.3.0 regression `NEWS` 15.1.0 fixes, HarfBuzz #6537); 0.15: all three marks misplaced (`uni064F=2+0|uni0651=2@-3,235+0|…|uni064F=0@-476,-164+0`). 0.15’s output matches neither HarfBuzz release, so it counts as real here; 0.16 brings it to lag; main matches 15.1.0.

### Malformed fonts

The backend hands HarfRust the face’s raw tables (`hb_face_reference_table`, `src/rust/shape.rs:66`), not sanitized ones, and read-fonts checks each read as it happens. HarfBuzz’s sanitizer, since 12.3, drops a whole table that fails, so HarfBuzz applies nothing from it, and HarfRust applies whatever it can still read. All of these are the same in 0.15, 0.16 and main.

8. fonts-as-bytes.md:311, `outside.ttf  aex` (a coverage offset far past the end of GSUB). `ot`: `[a=0+500|e=1+500|x=2+500]`; HarfRust: `[a=0+500|e=1+500|f=2+500]`: lookup 1 still applies.
9. fonts-as-bytes.md:338, `null-coverage-f1.ttf  aex` (a null coverage offset, whose population charge exhausts HarfBuzz’s sanitizer budget). `ot`: `[a=0+500|e=1+500|x=2+500]`; HarfRust: `[a.alt1=0+500|e.init=1+500|x=2+500]`: the other lookups apply.
10. from-features-to-lookups.md:271, `varliga-minor1.ttf  I  --variations=wght=400`. `ot`: `[I=0+260]`; HarfRust: `[H=0+600]`.
11. from-features-to-lookups.md:272, the same at `wght=800`. `ot`: `[I=0+390]`; HarfRust: `[V=0+504]`. (FeatureVariations minorVersion 1 whose bytes after the records don’t make a valid LookupVariationRecord array: HarfBuzz fails the whole GSUB; HarfRust keeps it, and the ordinary feature variations apply.)
12. trust-nothing-the-sanitizer.md:201, `bad-gsub.ttf  ab`. `ot`: `[a=0+500|b=1+500]`; HarfRust: `[a.alt=0+500|b=1+500]`: `calt` still applies; only the broken ligature is lost (`fi` is the same in both).
13. trust-nothing-the-sanitizer.md:326, `bad-gpos.ttf  ba`. `ot`: `[b=0+500|a=1+500]`; HarfRust: `[b=0+400|a=1+500]`: kerning survives.
14. trust-nothing-the-sanitizer.md:329, `bad-gpos.ttf  a\u0301`. `ot`: `acutecomb=0@-250,562`; HarfRust: `acutecomb=0+0`. Both lose the mark attachment here, but differently: HarfBuzz falls back to its fallback mark positioning (GPOS gone), HarfRust has a GPOS whose mark-to-base subtable can’t be read, so the mark stays where it is (inferred).
15. trust-nothing-the-sanitizer.md:332, `bad-gpos.ttf  b\u0301`. Same as 14.

### An unsorted PairSet

16. subsetting.md:340, `kern-map.ttf  ACAGAOAQATAVAWAY`, a subset whose `--gid-map` leaves the A pair set unsorted. `ot`: A–Q kerned (`A=6+460`), the one pair its binary search reaches; HarfRust: no pair kerned. Both binary-search an array the spec requires to be sorted; they reach different entries (inferred). The font is invalid, so neither is wrong.

## HarfRust’s own metrics (hr-shape only)

`hr-shape` doesn’t use HarfBuzz’s font funcs, so these eight are HarfRust’s built-in metrics, not its shaping. The backend matches `ot` on all of them.

* **Variable advances keep their fraction.** deltas.md:76 (`[I=0+34521]` against `34500`), varying-outlines.md:131 (`39633` against `39600`), where-metrics-come-from.md:325 (`385403|680322|491128` against `385000|680000|491000`). HarfBuzz rounds HVAR deltas to whole font units before scaling (the book, where-metrics-come-from.md:319); HarfRust doesn’t.
* **Extents of variable glyphs**, off by one unit: instancing.md:55, :57; variable-components.md:394, :395.
* **A glyph past the end of `hmtx`’s side bearings.** where-metrics-come-from.md:101, `metrics-short.ttf  012`: HarfRust gives `two` the shared advance, 550, as the spec says; HarfBuzz gives it 0 (the book describes this at where-metrics-come-from.md:95).

## Possible upstream reports

For HarfRust: items 1 (noncontextual ranges) and 3 (control-point actions) looked like bugs, each with a one-line font case in this book; both are fixed in HarfRust 0.16.1. Item 2 is a question of which base the spec means. Item 4 is a port not yet complete. For HarfBuzz: the backend’s not passing the invisible and not-found glyphs; 15.2.0 passes the not-found glyph. None has been filed.
