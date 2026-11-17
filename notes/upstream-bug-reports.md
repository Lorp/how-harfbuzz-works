# Draft bug reports for HarfBuzz

Sixty-five possible bugs found while writing the book, drafted for the HarfBuzz issue tracker. None has been filed. Each was reproduced on HarfBuzz 15.1.0 (commit `3df40d9b`), built by `tools/build-harfbuzz.sh` (meson, with FreeType, ICU and cairo off), on macOS. Repros use `test/subset/data/fonts/Roboto-Regular.ttf` from HarfBuzz’s own repository where they can, so they need nothing from this book.

---

## 1. A null or unknown-format Coverage in SingleSubst/SinglePos format 1 makes the sanitizer reject the whole GSUB/GPOS

**Summary.** `Coverage::get_population ()` returns `NOT_COVERED` (`0xFFFFFFFF`) for a format it doesn’t know (`src/OT/Layout/Common/Coverage.hh:138`), and so for the Null Coverage, whose format is 0. `SingleSubstFormat1_3::sanitize` passes half the population to `check_ops` (`src/OT/Layout/GSUB/SingleSubstFormat1.hh:125`), and so does `SinglePosFormat1::sanitize` (`src/OT/Layout/GPOS/SinglePosFormat1.hh:39`). With a null coverage offset, or a coverage of unknown format, that charges about 2 billion ops, `max_ops` runs out, and the whole table fails to sanitize.

Elsewhere a null offset, or an unknown format, makes that one subtable inert: the same change to a SingleSubst *format 2* subtable loses only that lookup. Since 12.3.0 a failed sanitize drops the whole table, so here one inert subtable takes every other lookup in GSUB (or GPOS) with it.

**Repro.** This script (fontTools) builds `good.ttf`, whose `liga` has two lookups, a format 2 SingleSubst (`a c` → `b a`) and a format 1 SingleSubst (`x` → `y`), and `null-coverage-f1.ttf`, the same font with the format 1 subtable’s `coverageOffset` set to 0:

```python
import struct
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

names = [".notdef", "a", "b", "c", "x", "y"]
fb = FontBuilder(1000, isTTF=True)
fb.setupGlyphOrder(names)
fb.setupCharacterMap({ord(n): n for n in "abcxy"})
pen = TTGlyphPen(None)
fb.setupGlyf({n: pen.glyph() for n in names})
fb.setupHorizontalMetrics({n: (500, 0) for n in names})
fb.setupHorizontalHeader(ascent=800, descent=-200)
fb.setupNameTable({"familyName": "NullCov", "styleName": "Regular"})
fb.setupOS2(); fb.setupPost()
addOpenTypeFeaturesFromString(fb.font, """
lookup L0 { sub [a c] by [b a]; } L0;
lookup L1 { sub x by y; } L1;
feature liga { lookup L0; lookup L1; } liga;
""")
fb.save("good.ttf")

data = bytearray(open("good.ttf", "rb").read())
g = TTFont("good.ttf").reader.tables["GSUB"].offset
u16 = lambda o: struct.unpack_from(">H", data, o)[0]
lookup_list = g + u16(g + 8)
lookup1 = lookup_list + u16(lookup_list + 4)
sub = lookup1 + u16(lookup1 + 6)
assert u16(sub) == 1                      # SingleSubst format 1
struct.pack_into(">H", data, sub + 2, 0)  # coverageOffset = 0
open("null-coverage-f1.ttf", "wb").write(data)
```

```
$ hb-shape good.ttf acx
[b=0+500|a=1+500|y=2+500]
$ hb-shape null-coverage-f1.ttf acx
[a=0+500|c=1+500|x=2+500]
```

**Expected.** Lookup 1 does nothing (its coverage is empty) and lookup 0 still applies: `[b=0+500|a=1+500|x=2+500]`.

**Actual.** Neither lookup applies: GSUB was rejected.

**Possible fix.** Have `Coverage::get_population ()` return 0 in its `default` case, which is what an empty or unknown coverage contains. The only other caller, `single_subst_closure` (`SingleSubstFormat1.hh:61`), uses the value as a size hint (`if (pop >= mask) return;`) and would just go on to intersect an empty coverage.

Real fonts are unlikely to have null coverage offsets, so the impact is small. But a coverage format from a future OpenType version would have the same effect, which seems contrary to the sanitizer’s policy of letting unknown formats pass.

---

## 2. The “start/end table GPOS” trace messages print GSUB’s chosen script

**Summary.** `hb_ot_map_t::position` (`src/hb-ot-layout.cc:2149`) formats its trace messages with `chosen_script[0]`, the script chosen for GSUB. GPOS’s is `chosen_script[1]` (`hb-ot-map.cc:80` fills them per table index). The code looks copied from `hb_ot_map_t::substitute` just above it.

**Repro.** Any font whose GSUB and GPOS choose different scripts. The plainest case is a font with no GSUB, where GSUB’s chosen script is empty. Roboto with its GSUB removed (`del font['GSUB']` in fontTools) shows it: the trace says GPOS has no script tag either, though GPOS chose `latn` and kerned:

```
$ hb-shape --trace Roboto-noGSUB.ttf AV | grep 'table G\|kern'
trace: start table GSUB script tag ''   buffer: [gid37=0|gid58=1]
trace: end table GSUB script tag ''     buffer: [gid37=0|gid58=1]
trace: start table GPOS script tag ''   buffer: [gid37=0+1336|gid58=1+1303]
trace: start lookup 1 feature 'kern'    buffer: [gid37=0+1336|gid58=1+1303]
trace: end lookup 1 feature 'kern'      buffer: [gid37=0+1249|gid58=1+1303]
trace: end table GPOS script tag ''     buffer: [gid37=0+1249|gid58=1+1303]
```

**Expected.** The GPOS lines name GPOS’s chosen script.

**Possible fix.** `hb_tag_to_string (chosen_script[1], tag);` in `hb_ot_map_t::position`. Only the debug messages are affected.

---

## 3. A synthetic font reports extents `<0,-1,-1,1>` for an empty glyph

**Summary.** With any synthetic setting (bold, grade or slant), `hb_font_t::get_glyph_extents` measures the glyph by painting or drawing it (`src/hb-font.hh:586`–`630`). For a glyph with no outline, such as space, nothing is drawn, so the `hb_extents_t` stays in its initial, *void* state: `xmin = 0, ymin = 0, xmax = -1, ymax = -1` (`src/hb-geometry.hh:121`–`124`). `draw_glyph_or_fail` still succeeds, and `hb_extents_t::to_glyph_extents` (`hb-geometry.hh:100`) converts the void box as if it were real, giving x_bearing 0, y_bearing −1, width −1 and height 1.

**Repro.**

```
$ hb-shape test/subset/data/fonts/Roboto-Regular.ttf "a b" --show-extents
[gid69=0+1114<109,1102,893,-1122>|gid4=1+507<0,0,0,0>|gid70=2+1149<140,1536,916,-1556>]
$ hb-shape test/subset/data/fonts/Roboto-Regular.ttf "a b" --show-extents --font-bold=0.02
[gid69=0+1155<109,1143,934,-1163>|gid4=1+548<0,-1,-1,1>|gid70=2+1190<140,1577,957,-1597>]
$ hb-shape test/subset/data/fonts/Roboto-Regular.ttf "a b" --show-extents --font-slant=0.2
[gid69=0+1114<141,1102,1002,-1122>|gid4=1+507<0,-1,-1,1>|gid70=2+1149<140,1536,1077,-1556>]
```

**Expected.** `<0,0,0,0>` for the space, as without synthetic settings.

**Actual.** `<0,-1,-1,1>`: a box with negative width and positive height, one unit below the origin.

**Possible fix.** Return zero extents for a void box in `to_glyph_extents`:

```c++
if (unlikely (is_void ()))
  return hb_glyph_extents_t {0, 0, 0, 0};
```

or check `is_void ()` in the two callers in `get_glyph_extents` (`hb-font.hh:617`, `:627`). The COLR caller (`OT/Color/COLR/COLR.hh:3168`) may want the same. `src/test-geometry.cc` would be the place for a test.

---

## 4. Scaled glyph extents are rounded inwards vertically

**Summary.** `hb_font_t::scale_glyph_extents` (`src/hb-font.hh:201`) takes the floor of `x1` and `y1` and the ceiling of `x2` and `y2`. Across, `x1` is the left edge and `x2` the right, so the box grows outwards. Up and down it’s the other way round: `y1` is `y_bearing`, the *top* edge, and `y2 = y1 + height` (height being negative) is the bottom. Taking the floor of the top moves it down, and the ceiling of the bottom moves it up, so the box shrinks vertically. NEWS for 14.2.1 says extents are now scaled “so the reported box always covers the glyph”. It does across, but not up and down.

**Repro.** Roboto’s `p` (2048 units per em) at a scale of 13:

```
$ hb-shape test/subset/data/fonts/Roboto-Regular.ttf p --show-extents
[gid84=0+1149<140,1102,914,-1518>]
$ hb-shape test/subset/data/fonts/Roboto-Regular.ttf p --show-extents --font-size=13
[gid84=0+7<0,6,7,-8>]
```

Scaled exactly, the ink runs from y = 6.995 (1102 × 13/2048) down to y = −2.641. Reported, it runs from 6 down to −2: almost a whole unit short at the top, and 0.64 short at the bottom. Across, 0.889 to 6.691 becomes 0 to 7, which does cover it.

**Expected.** y_bearing 7, height −10 (top 7, bottom −3).

**Possible fix.** Round each edge away from the box’s centre, whichever way the axes point. For example, round `hb_min (y1, y2)` down and `hb_max (y1, y2)` up, then put them back as top and bottom, and the same for x, which would also keep it right for negative scales. A sketch, not tested:

```c++
float xlo = floorf (hb_min (x1, x2)), xhi = ceilf (hb_max (x1, x2));
float ylo = floorf (hb_min (y1, y2)), yhi = ceilf (hb_max (y1, y2));
extents->x_bearing = hb_clamp_to<hb_position_t> (x1 <= x2 ? xlo : xhi);
extents->width     = hb_clamp_to<hb_position_t> (x1 <= x2 ? (double) xhi - xlo : (double) xlo - xhi);
extents->y_bearing = hb_clamp_to<hb_position_t> (y1 >= y2 ? yhi : ylo);
extents->height    = hb_clamp_to<hb_position_t> (y1 >= y2 ? (double) ylo - yhi : (double) yhi - ylo);
```

Expected outputs in `test/shape/` and `test/api/` that print scaled extents would change.

---

## 5. Glyph-flag ranges treat cluster level 3 (GRAPHEMES) as monotone

*Found by reading the code; not yet reproduced in shaping output.*

**Summary.** `_infos_set_glyph_flags` and `_infos_find_min_cluster` (`src/hb-buffer.hh:664` and `:694`) take a shortcut that is only valid when clusters are in order: they look at the first and last glyphs of a range rather than scanning it. They skip the shortcut with

```c++
if (cluster_level == HB_BUFFER_CLUSTER_LEVEL_CHARACTERS)
```

but level 3, `HB_BUFFER_CLUSTER_LEVEL_GRAPHEMES` (11.0.0), is not monotone either. Everywhere else the code tests `HB_BUFFER_CLUSTER_LEVEL_IS_MONOTONE` (`hb-buffer.hh:400`, `:423`, `hb-buffer-verify.cc:66`, and the CoreText and Graphite backends), and these two tests look as though they were missed when level 3 was added.

**Effect, as far as the code shows.** At level 3, after reordering puts clusters out of order, a range whose smallest cluster is neither its first nor its last glyph gets the wrong minimum from `_infos_find_min_cluster`, and `_infos_set_glyph_flags` then marks the wrong glyphs unsafe to break or unsafe to concat (it leaves out the glyphs it believes belong to the minimum cluster). The verifier doesn’t catch it, because it skips non-monotone levels.

**Possible fix.** Use the predicate in both places:

```c++
if (!HB_BUFFER_CLUSTER_LEVEL_IS_MONOTONE (cluster_level) || …)
```

**Before filing.** Try to construct a level-3 example whose flags differ from level 2’s in a way the scan would correct, for instance an Indic syllable whose reordering leaves its smallest cluster in the middle of a flagged range, and include it.

---

## 6. Small slips in `hb-shape-plan.cc`

*Found by reading the code. None changes shaping results today.* Three separate one-line issues, which could go in one report.

* **`features[0]` for `features[i]`.** `hb_shape_plan_key_t::init` copies the user features and, to “make start/end uniform to easier catch bugs”, sets every non-global `start` to 1 and `end` to 2. The loop indexes `features[0]` on every pass (`src/hb-shape-plan.cc:95`–`99`), so only the first feature is normalized. Nothing reads the copied ranges, so it’s harmless.
* **A null check after the dereference.** `hb_shape_plan_create2` tests `HB_DIRECTION_IS_VALID (props->direction)` (`:255`) before `if (unlikely (!props)) goto bail;` (`:260`), so the null check can never fire: a null `props` crashes first.
* **No null-face guard in the cached path.** `hb_shape_plan_create_cached2` reads `face->shape_plans` (`:553`) before anything checks `face`, so a null face crashes. `hb_shape_plan_create2` handles one by using the empty face.

**Possible fixes.** `features[i]` in the loop; move the `!props` test above the direction test; give `create_cached2` the same null-face handling as `create2`.

---

## 7. FeatureVariations minor version 1 means different things to HarfBuzz and to the ISO draft

*A question about the standard as much as a bug. Raise it as a discussion before filing as a bug.*

**Summary.** Since 14.6.0 HarfBuzz reads a FeatureVariations table of version 1.1 or later as having an array of `LookupVariationRecord`s after its `FeatureVariationRecord`s (`src/hb-ot-layout-common.hh:5957`), and its sanitizer requires that array to be there (`:6187`). The ISO/IEC 14496-22 working draft (WD9) defines minorVersion 1 differently: it allows Condition format 2, with nothing after the records.

A FeatureVariations table that fails to sanitize makes the whole GSUB (or GPOS) fail (`src/hb-ot-layout-gsubgpos.hh:6369`), and since 12.3.0 a failed table is dropped. So a font that follows the ISO draft’s minorVersion 1 loses every substitution, not only its variations.

**Repro.** Take a font with an ordinary FeatureVariations table (fontTools’ `addFeatureVariations` writes version 1.0) and set its minorVersion to 1, with nothing else changed. HarfBuzz then rejects the font’s GSUB: in the book’s test font, the `rvrn` substitutions stop at every weight.

**Expected.** Either that HarfBuzz and the ISO draft agree on what follows the records in a 1.1 table, or that HarfBuzz tells the two apart (for example by checking that the bytes after the records can be a lookup variation array) rather than dropping the table.

**Before raising it.** Check the current state of the ISO draft and of HarfBuzz’s “beyond 64k” / lookup-variations proposal, which may already have been reconciled, and quote the draft’s exact wording.

---

## 8. A ranged request followed by a global one for the same feature clears the global bit

**Summary.** When the same tag is requested twice, `hb_ot_map_builder_t::compile` merges the requests (`src/hb-ot-map.cc:238`), and a later global request makes the feature global. With value 1 it then shares the global bit (bit 31). But the earlier ranged request is still in the user features passed to the run, and `hb_ot_shape_setup_masks` (`src/hb-ot-shape.cc:760`) applies its range with the feature’s mask, which is now the global bit. The range clears bit 31 on those clusters, which turns off *every* global feature there, not just the one named.

**Repro.** `gsub/ligatures.ttf` from the book’s test fonts, whose `calt` turns `e` into `e.init` after a space or an `e.init`:

```
$ hb-shape ligatures.ttf ' eee' --language=en
[space=0+250|e.init=1+500|e.init=2+500|e.init=3+500]
$ hb-shape ligatures.ttf ' eee' --language=en --features=-liga[2:3],liga
[space=0+250|e.init=1+500|e=2+500|e=3+500]
$ hb-shape ligatures.ttf ' eee' --language=en --features=liga,-liga[2:3]
[space=0+250|e.init=1+500|e.init=2+500|e.init=3+500]
```

**Expected.** `calt` unaffected: only `liga` is named.

**Actual.** `calt` stops at cluster 2 (and, since it looks back at its own output, cluster 3).

**Possible fix.** In `hb_ot_shape_setup_masks`, skip a ranged feature whose mask is the global mask, or have the merge record that a later global request superseded earlier ranged ones so `setup_masks` can ignore them.

---

## 9. Mask bit 30 is never handed out

**Summary.** `compile` gives a feature bits only if `next_bit + bits_needed >= global_bit_shift` is false (`src/hb-ot-map.cc:292`). With `global_bit_shift` 31, a one-bit feature starting at bit 30 fails the test, so the usable bits are 4–29: 26, not the 27 between the glyph flags and the global bit. Off by one.

**Repro.** A font with 27 features of one substitution each (`bits.ttf` in the book’s test fonts), all requested over a range so that each needs its own bit: the 27th by tag order is silently dropped.

**Possible fix.** `>` for `>=`. Low impact, but features dropped for lack of bits are dropped silently, so each bit counts.

---

## 10. In `COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT` mode, text without marks is decomposed but never recomposed

**Summary.** The Indic, Khmer, Myanmar and USE shapers normalize in `HB_OT_SHAPE_NORMALIZATION_MODE_COMPOSED_DIACRITICS_NO_SHORT_CIRCUIT`, documented as “Always fully decomposes and then recompose back” (`src/hb-ot-shape-normalize.hh:43`). Round 1 does fully decompose every character in this mode. But rounds 2 and 3 are skipped when `all_simple` is true, that is, when the input had no marks (`src/hb-ot-shape-normalize.cc:324`, `:356`, `:374`, `:422`). So whether a character is recomposed depends on whether *some other* character in the buffer is a mark.

**Repro.** A font with glyphs for U+0929 (NNNA), U+0928 + U+093C, U+093E, and for é and e + U+0301 (`norm.ttf` in the book’s test fonts):

```
$ hb-shape norm.ttf $'\u0929'
[na=0+600|nukta=0+0]
$ hb-shape norm.ttf $'\u0929\u093E'
[nnna=0+600|aaMatra=0+250]
$ hb-shape norm.ttf $'\u00E9' --script=deva
[e=0+500|acutecomb=0+0]
$ hb-shape norm.ttf $'\u00E9a\u0301' --script=deva
[eacute=0+500|aacute=1+500]
```

**Expected.** The same glyphs for NNNA, and for é, whatever else is in the buffer: recomposed, as the mode’s comment says.

**Possible fix.** In this mode, don’t let `all_simple` skip round 3 when round 1 decomposed anything (or track “decomposed something” separately from “had marks”).

---

## 11. The not-found glyph is ignored in variation-selector clusters

**Summary.** `handle_variation_selector_cluster` maps the base with `set_glyph` (`src/hb-ot-shape-normalize.cc:79`), which calls `get_nominal_glyph` without falling back to `buffer->not_found`. Everywhere else, a character the font lacks gets the not-found glyph set with `hb_buffer_set_not_found_glyph`; here it gets glyph 0.

**Repro.** With `norm.ttf`, which has an unencoded glyph 27 and no `x`:

```
$ hb-shape norm.ttf q --not-found-glyph=27
[missing=0+500]
$ hb-shape norm.ttf $'x\uFE00' --not-found-glyph=27
[.notdef=0+500|space=0+0]
```

**Expected.** `missing` for the `x` in the second run too.

**Possible fix.** Fall back to `buffer->not_found` in `set_glyph`’s callers in the variation-selector path, as `decompose_current_character` does.

---

## 12. Mark-to-base and mark-to-ligature pass over a base that lacks the lookup’s mask bit

**Summary.** When a mark-to-base or mark-to-ligature lookup looks back for the mark’s base, it treats a glyph without the lookup’s mask bit as if it were something to skip (`src/OT/Layout/GPOS/MarkBasePosFormat1.hh:113`–`127`, `MarkLigPosFormat1.hh:102`–`116`). So turning `mark` off on a base doesn’t stop marks attaching to it: it makes them attach to an *earlier* base instead.

**Repro.** `gpos.ttf` from the book’s test fonts: `a`, `e` and a combining acute with mark anchors on both bases.

```
$ hb-shape gpos.ttf $'ae\u0301' --cluster-level=1
[a=0+500|e=1+500|acutecomb=2@-250,500+0]
$ hb-shape gpos.ttf $'ae\u0301' --cluster-level=1 --features='mark[1:2]=0'
[a=0+500|e=1+500|acutecomb=2@-750,500+0]
```

**Expected.** With `mark` off on the `e`, the acute either attaches to nothing or is unaffected (the acute itself still has the bit). It shouldn’t move 750 units back onto the `a`.

**Possible fix.** In the base search, stop at (rather than skip) a non-mark glyph that lacks the mask bit, and decline to attach.

---

## 13. The nesting limit still breaks long cursive chains that run against the buffer’s direction

**Summary.** `propagate_attachment_offsets` resolves attachment chains with a depth limit of `HB_MAX_NESTING_LEVEL`, 64 (`src/OT/Layout/GPOS/GPOS.hh:93`). Issue #5514 changed the loop order (`:177`) so that chains in the buffer’s direction resolve in one pass, but chains that run against it still recurse, and past 64 links the offsets stop accumulating. That covers LTR text with the RightToLeft lookup flag, and RTL text without it, which is the usual case for Arabic cursive joining.

**Repro.** `gpos.ttf`, whose `ss03` gives `n` a cursive attachment that steps each glyph 100 units, against the direction:

```
$ hb-shape gpos.ttf nnnn…n (67 n) --features=-curs,ss03
```

The offsets step by 100 until glyph 65, where two consecutive glyphs have the same offset, and every glyph before it is 100 units off. The book’s writer saw the same with 70 Arabic behs in RTL.

**Expected.** Chains of any length resolve correctly, or a limit high enough that real text never reaches it. Long cursive chains do occur in Arabic, Nastaliq especially.

---

## 14. With `HB_NO_HINTING`, y Device tables fall through to the variation branch

*Found by reading the code; not testable in the book’s build.*

**Summary.** In `Device::get_y_delta` (`src/hb-ot-layout-common.hh:6430`), the labels `case 1: case 2: case 3:` sit outside `#ifndef HB_NO_HINTING`. In a build with `HB_NO_HINTING` but not `HB_NO_VAR`, a hinting Device table (formats 1–3) therefore falls through into `case 0x8000` and is read as a VariationIndex. `get_x_delta` (`:6410`) has the case labels inside the guard, as both should.

**Possible fix.** Move the case labels inside the `#ifndef HB_NO_HINTING` block, as in `get_x_delta`.

---

## 15. A cross-stream `kern` value of 0x8000 isn’t treated as a reset

**Summary.** The `kern` specification says “The value 0x8000 in the kerning data resets the cross-stream kerning back to 0.” Only the format 1 state machine checks for it (`src/hb-aat-layout-kerx-table.hh:360`). The kern machine, which runs formats 0, 2 and 3 (`src/hb-kern.hh`), takes 0x8000 as −32,768.

**Repro.** `cross.ttf` in the book’s test fonts: a cross-stream format 0 subtable with A V +100 and T o 0x8000.

```
$ hb-shape cross.ttf AVTo --language=en
[A=0+560|V=1@-40,100+560|T=2@0,100+550|o=3@-50,-32668+450]
```

**Expected.** The `o` back on the line (y offset 0).

---

## 16. Fallback mark positioning ignores the base’s x offset

**Summary.** The fallback positioner (`src/hb-ot-shape-fallback.cc`) builds the base’s box from its advance and ink and adds the base’s y offset, but not its x offset. After kerning that splits a value between two glyphs (the `kern` table, or fallback kerning), the second glyph has an x offset, and a mark on it is placed off-centre by that amount.

**Repro.** `kern-table.ttf` (no GPOS, a `kern` table with o o −50) against `fallback.ttf` (the same without `kern`):

```
$ hb-shape fallback.ttf $'o\u00F3' --language=en
[o=0+500|o=1+500|acutecomb=1@-25,12+0]
$ hb-shape kern-table.ttf $'o\u00F3' --language=en
[o=0+450|o=1@-50,0+450|acutecomb=1@25,12+0]
```

**Expected.** The acute centred over the kerned `o`, as it is over the unkerned one.

---

## 17. Fallback positioning centres LEFT and RIGHT marks, contrary to its comment

**Summary.** `position_mark` in `src/hb-ot-shape-fallback.cc` says “We don’t position LEFT and RIGHT marks” (`:228`), but the switch has no cases for `HB_UNICODE_COMBINING_CLASS_LEFT` (224) and `RIGHT` (226), so they fall into `default` and are centred on the base, and lose their advance like every placed mark.

**Repro.** U+1D16D MUSICAL SYMBOL COMBINING AUGMENTATION DOT (class 226) after `o`, in a font without GPOS:

```
$ hb-shape fallback.ttf $'o\U0001D16D' --language=en
[o=0+500|augdot=0@-350,0+0]
```

**Expected.** Either leave such marks where they are (as the comment says), or place them to the left or right of the base.

---

## 18. Vertical `kern` subtables can never apply

**Summary.** In vertical text the plan’s kerning mask is `vkrn`’s (`src/hb-ot-shape.cc:127`). `vkrn` isn’t on by default, and unlike `kern` it has no `F_HAS_FALLBACK`, so when GPOS lacks it the feature isn’t kept and its mask is 0. Subtables of the `kern` table marked for vertical text therefore never run, even with `--features=vkrn`.

**Repro.** A `kern` table with a vertical (non-horizontal) format 0 subtable, shaped with `--direction=ttb`, with and without `--features=vkrn`: no kerning either way.

**Possible fix.** Give `vkrn` `F_HAS_FALLBACK` when it is requested, or consult the vertical `kern` subtables under `vert`’s default kerning, whichever matches the intended policy.

---

## 19. The Hangul shaper’s dotted circle copies the tone mark’s properties

**Summary.** For a tone mark that doesn’t follow a syllable, `preprocess_text_hangul` inserts a dotted circle with `replace_glyphs` (`src/hb-ot-shaper-hangul.cc:245`), which copies the tone mark’s buffer entry, Unicode properties included. The circle is then a spacing mark (Mc, class 224), so after a base the fallback positioner zeroes its advance and places it over the base. The generic dotted circle gets U+25CC’s own properties (`src/hb-ot-shape.cc:567`).

**Repro.** `hangul.ttf` in the book’s test fonts (no GPOS):

```
$ hb-shape hangul.ttf $'\u1100\u302E'
[kiyeok=0+500|singledot=0@-350,0+0|dottedcircle=0@-500,0+0]
```

**Expected.** The dotted circle as a base with its own advance, carrying the tone mark.

---

## 20. Two dotted circles before a Hangul tone mark at the start of text

**Summary.** With `HB_BUFFER_FLAG_BOT`, the generic dotted circle is inserted before a leading mark (`src/hb-ot-shape.cc:567`). The Hangul shaper doesn’t recognise that circle as a syllable, so it inserts a second one.

**Repro.**

```
$ hb-shape hangul.ttf $'\u302E' --bot
[dottedcircle=0+500|singledot=0@-350,0+0|dottedcircle=0@-500,0+0]
```

**Expected.** One dotted circle.

---

## 21. Hebrew: `has_gpos_mark` and `gpos_tag` disagree about a `mark` feature under `DFLT`

**Summary.** The Hebrew shaper composes presentation forms only when the plan has no `mark` feature (`has_gpos_mark`, `src/hb-ot-shape.cc:196`; `hb-ot-shaper-hebrew.cc:81`). Its `gpos_tag` makes GPOS apply only when GPOS chose `hebr`. In a font whose `mark` feature is under `DFLT` only, `has_gpos_mark` is true, so presentation forms aren’t composed, but GPOS is ignored because of `gpos_tag`. The points fall to fallback positioning though the font has presentation-form glyphs that would serve better.

**Repro.** `hebrew-mark-DFLT.ttf` in the book’s test fonts: shin with dagesh and shin dot gives separate glyphs placed by the fallback positioner, where `hebrew-old.ttf` (no GPOS) gives U+FB2C’s glyph.

**Possible fix.** Compute `has_gpos_mark` from the GPOS the plan will actually apply (after the `gpos_tag` test).

---

## 22. Indic `init` ignores pre-context

**Summary.** The Indic shaper applies `init` to a pre-base matra at the start of a word, testing for a word start only inside the buffer (`src/hb-ot-shaper-indic.cc:1431`). With the previous consonant supplied as pre-context, the syllable still gets the word-initial form.

**Repro.** `full.ttf` in the book’s test fonts (an `init` lookup for the I matra):

```
$ hb-shape full.ttf $'\u0915\u093F'
[iMatra.init=0+250|ka=0+600]
$ hb-shape full.ttf $'\u0915\u093F' --text-before=$'\u0915'
[iMatra.init=0+250|ka=0+600]
$ hb-shape full.ttf $'\u0915\u0915\u093F'
[ka=0+600|iMatra=1+250|ka=1+600]
```

**Expected.** With a letter before it in the pre-context, the matra isn’t word-initial, as when the text is shaped whole.

---

## 23. Syllables longer than 64 glyphs are cut into pieces

*Seen by the book’s writer; not yet in the book.*

**Summary.** `foreach_syllable` caps a syllable at `HB_MAX_SYLLABLE_LENGTH`, 64 (`src/hb-limits.hh:62`). A longer syllable is processed in pieces, so reordering can go wrong at the cut: with 32 TA + virama pairs followed by KA + I, the matra lands mid-syllable and the 32nd TA keeps a visible virama. The cap also makes the `end - start > 127` branch in `hb-ot-shaper-indic.cc:810` unreachable.

**Before filing.** Reproduce with a real Devanagari font and confirm the cut is the cause; a limit is reasonable, but splitting silently mid-syllable might be worse than treating the whole run as broken.

---

## 24. `stch` tiles are shifted when they fit the word exactly

**Summary.** In `apply_stch` (`src/hb-ot-shaper-arabic.cc:625`), the first tile starts at `x_offset = w_remaining / 2`. `w_remaining` is set to zero only on the path that adds an extra, overlapping repeat (`:598`). When the repeating tiles fill the word exactly, or the word is narrower than the fixed tiles plus one repeat, the whole line is shifted by half of what remains.

**Repro.** `stch.ttf` in the book’s test fonts: U+070F SYRIAC ABBREVIATION MARK followed by two beths (a word 1,000 units wide).

```
$ hb-shape stch.ttf $'\u070F\u0712\u0712' --script=Syrc
[beth=2+500|beth=1+500|sam.end=0@-600,0+0|sam.rep=0@-500,0+0|sam.rep=0@-300,0+0|sam.rep=0@-100,0+0|sam.rep=0@100,0+0|sam.end=0@300,0+0]
```

The tiles run from −600 to 400, extending 400 units past the word, where −1000 to 0 would cover it. With one or three beths the overlap path is taken and the fit is right. HarfBuzz’s own test (`test/shape/data/in-house/tests/arabic-stch.tests`) happens to go through the overlap path.

**Possible fix.** Zero `w_remaining` whenever the tiles fill the word, not only on the overlap path.

---

## 25. CBDT format 19 images are never painted

*Found by reading the code; not shown live.*

**Summary.** `CBDT::paint_glyph` needs the image’s pixel extents, but for format 19 (PNG with metrics in the CBLC index) they come from `IndexSubtable::get_extents`, which is a TODO that always returns false (`src/OT/Color/CBDT/CBDT.hh:334`). So a format 19 glyph can be fetched with `hb_ot_color_glyph_reference_png` but is never painted. Only index subtable formats 1 and 3 are read (`:345`).

---

## 26. The bitmap tables are tried in different orders for different purposes

**Summary.** `hb_ot_color_glyph_reference_png` tries `sbix` before CBDT (`src/hb-ot-color.cc:417`), and so do glyph extents, but painting tries CBDT first. For a glyph in both tables, a client can get one table’s image from one call and the other’s from another. Low impact (fonts rarely have both), but the order should be one.

---

## 27. Point matching in nested composites counts from the wrong start

*Shown in a drawing in the book; the expected position not yet worked out independently.*

**Summary.** When a `glyf` component is placed by point matching (`ARGS_ARE_XY_VALUES` clear), the anchor point number of the parent is counted from the start of the whole `all_points` array (`src/OT/glyf/Glyph.hh:539`–`551`), not from the start of the inner composite’s own points. At nesting depth above 0, the outer glyph’s earlier points are counted too, so the component is attached to the wrong point.

**Repro.** `outlines.ttf` in the book’s test fonts: `x` is a composite of `b` and `i`, with `i` placed by point matching inside a nested composite. HarfBuzz draws the dot of the `i` 250 units too high; fontTools places it correctly.

**Before filing.** Confirm the expected position against FreeType or fontTools’ pen output, and reduce the font to the smallest case.

---

## 28. A CFF charstring with no `endchar` runs to the operation limit

**Summary.** In CFF1, running off the end of a charstring isn’t treated as an error: `fetch_op` returns `OpCode_Invalid`, which only clears the arguments, and the interpreter loops until `HB_CFF_MAX_OPS` (200,000). The outline so far is emitted to the client, then `hb_font_draw_glyph_or_fail` returns false, and the glyph has no extents. Each such glyph uses 200,000 of the shared drawing budget, so a few of them stop later glyphs from being drawn at all.

**Repro.** A CFF font with 90 charstrings lacking `endchar` and one good glyph: `hb-vector` draws 84 paths and the good glyph vanishes (checked by the book’s writer with `hb-vector` and a small C client).

**Expected.** Running off the end ends the charstring (as an implied `endchar`, or as an error) at once.

---

## 29. Khmer moves a second COENG + RO in front of the first

**Summary.** In Khmer initial reordering (`src/hb-ot-shaper-khmer.cc:239`), the test `num_coengs <= 2` is checked before the counter is incremented, so a third COENG still passes; and `num_coengs = 2; /* Done. */` after moving a COENG + RO doesn’t stop the loop. So a second COENG + RO in the same syllable is also moved before the base, in front of the first. Microsoft’s Khmer specification says the move applies while the “subscript count is less than two”.

**Repro.** `khmer.ttf` in the book’s test fonts:

```
$ hb-shape khmer.ttf $'\u1780\u17D2\u179A\u17D2\u179A'
[ro.pref=0+300|ro.pref=0+300|ka=0+600]
```

**Expected.** Only the first COENG + RO moved. Low impact: the text is already invalid.

**Possible fix.** `break` after moving the COENG + RO, and test `num_coengs < 2`.

---

## 30. USE: a mark after a space attaches to the space

**Summary.** In the USE grammar, `symbol_cluster = (O | GB | SB) tail?` (`src/hb-ot-shaper-use-machine.rl`) lets a space (category `O`) take any marks after it. A vowel sign typed after a space is then reordered before the space, with no dotted circle. Microsoft’s specification lets an independent cluster of category `O` take only a variation selector.

**Repro.** `deva3.ttf` in the book’s test fonts (Devanagari under `dev3`), against `deva2.ttf` (`dev2`, the Indic shaper):

```
$ hb-shape deva3.ttf $'\u0915 \u093F'
[ka=0+600|iMatra=1+250|space=1+250]
$ hb-shape deva2.ttf $'\u0915 \u093F'
[ka=0+600|space=1+250|iMatra.init=1+250|dottedcircle=1+500]
```

---

## 31. USE: a space doesn’t end a word for topographical forms

**Summary.** HarfBuzz gives non-joining USE scripts its own topographical forms (`isol`/`init`/`medi`/`fina`), which Microsoft’s specification says aren’t implemented for them at all. A space is a symbol cluster, and symbol clusters join, so a syllable after a space isn’t word-initial and one before it isn’t final. ZWNJ doesn’t break the chain either; only a non-cluster such as WORD JOINER does.

**Repro.**

```
$ hb-shape deva3.ttf $'\u0915\u093F \u0915\u093F'
[iMatra.init=0+250|ka=0+600|space=2+250|iMatra=3+250|ka=3+600]
```

The second कि, after a space, doesn’t get `init`.

---

## 32. USE: ZWNJ after a virama doesn’t stop a half form

**Summary.** Under the Indic shaper, ZWNJ after a virama stops a half form (`F_MANUAL_ZWNJ` on the basic features). USE’s features lack `F_MANUAL_ZWNJ`, so the lookup passes over the ZWNJ and the half form is made.

**Repro.**

```
$ hb-shape deva3.ttf $'\u0915\u094D\u200C\u0930'
[ka.half=0+400|space=2+0|ra=3+500]
$ hb-shape deva2.ttf $'\u0915\u094D\u200C\u0930'
[ka=0+600|virama=0+0|space=2+0|ra=3+500]
```

**Expected.** As under `dev2`: a visible virama. (Also seen: RA + virama + ZWJ still makes a reph under USE, where the Indic shaper gives none.)

**Also noticed, not a bug report:** `hb-ot-shaper-use-table.hh` records `DerivedCoreProperties-17.0.0` while every other input is 18.0.0, apparently because `update-unicode-tables.make` leaves that file out of `SOURCES`.

---

## 33. Indic: a broken cluster starting with RA + virama loses its reph

**Summary.** When the Indic syllable machine finds a broken cluster, `hb_syllabic_insert_dotted_circles` (`src/hb-ot-shaper-syllabic.cc`) inserts the circle after any leading *repha character*, but the Indic shaper passes only the category `Repha`, which in the Indic table is just U+0D4E. So RA + virama + a vowel sign gets its circle *before* the RA: the reph never forms, and a visible virama follows the circle.

**Repro.** `circle.ttf` in the book’s test fonts (Devanagari with `rphf` and a dotted circle):

```
$ hb-shape circle.ttf $'\u0930\u094D\u093F'
[iMatra=0+250|dottedcircle=0+500|ra=0+500|virama=0+0]
$ hb-shape circle.ttf $'\u0930\u094D\u25CC\u093F'
[iMatra=0+250|dottedcircle=0+500|reph=0+0]
```

**Expected.** The circle after RA + virama, as when it is typed, so that a reph forms on it.

---

## 34. A ZWJ defeats the vowel constraints

**Summary.** The vowel constraints (`src/hb-ot-shaper-vowel-constraints.cc`, generated from Microsoft’s `IndicShapingInvalidCluster.txt`) match only adjacent code points. Putting a ZWJ between an independent vowel and a vowel sign avoids the dotted circle, which defeats the anti-spoofing purpose (issue #1019).

**Repro.**

```
$ hb-shape circle.ttf $'\u0905\u093E'
[a.deva=0+600|dottedcircle=0+500|aaMatra=0+250]
$ hb-shape circle.ttf $'\u0905\u200D\u093E'
[a.deva=0+600|space=0+0|aaMatra=0+250]
```

**Expected.** A circle in both, or a documented reason why ZWJ is allowed through.

---

## 35. The vowel-constraint dotted circle copies the next character’s properties

**Summary.** The circle is inserted with `output_glyph`, which copies `cur()` (`src/hb-buffer.hh:313`), so it takes the following vowel sign’s Unicode properties: general category Mn. In a font without GDEF, synthesized classes then make it a mark, and USE zeroes its advance and moves it back over the letter. Compare report 19 (the Hangul circle copying the tone mark). The circles from the other paths are inserted with U+25CC’s own properties (generic) or with zero properties (syllabic).

**Repro.** `bare.ttf` in the book’s test fonts (no GDEF or GPOS): Brahmi A + AA.

**Possible fix.** Give every inserted dotted circle U+25CC’s own Unicode properties, in one helper used by all four paths.

---

## 36. hb-vector’s PDF output drops PNG alpha

**Summary.** In `src/hb-vector-paint-pdf.cc:305`, `(void) has_alpha;`: RGBA and grey+alpha PNGs are embedded as `/DeviceRGB` or `/DeviceGray` images with `/Colors 4` or `2` and no `/SMask`. The alpha channel is read as colour, and the image renders as stripes.

**Repro.** A font with an RGBA PNG bitmap glyph (`images.ttf` in the book’s test fonts): `hb-vector images.ttf P -O pdf`, rendered with `pdftoppm`.

**Expected.** The alpha channel split into an `/SMask` image, as PDF requires.

---

## 37. Smaller hb-vector and hb-gpu inconsistencies

* PDF: linear and radial gradients with REPEAT or REFLECT extend modes only pad (`hb-vector-paint-pdf.cc:1099`, `:1200`), so they lose their repeats. Possibly a deliberate limitation; worth documenting if so.
* Stale comments and docs: `hb-vector-paint-pdf.cc:49` says sweeps are “approximated via solid fallback” (they are Coons-patch meshes); the `hb-gpu.cc` docs example calls `hb_gpu_draw_encode (draw)` without the `extents` argument added in 14.2.0; `README.md` says the vector library is “currently SVG”; the `HB_VECTOR_MAX_DOCUMENT_SIZE` comment in `hb-limits.hh` says “one glyph per context”.
* API: `hb_vector_paint_set_palette` takes `int` where the raster and GPU versions take `unsigned`, and `hb_vector_paint_set_custom_palette_color` returns `void` where theirs return `hb_bool_t`.

---

## 38. A font with GSUB, GPOS and `kerx` never applies `kerx`, and stops zeroing marks

**Summary.** When a font has GSUB and GPOS, and GPOS has no `kern` feature in the language system it chose, and the font also has `kerx`, the planner sets both `apply_gpos` and `apply_kerx` (`src/hb-ot-shape.cc:167`–`195`). `hb_ot_shape_plan_t::position` runs only GPOS, so `kerx` never kerns. And because the plan thinks `kerx` is in use, marks are no longer zeroed.

**Repro.** `mark-gpos.ttf` (GSUB, GPOS without `kern`) and `mark-gpos-kerx.ttf` (the same plus a `kerx` A V −40) in the book’s test fonts:

```
$ hb-shape mark-gpos.ttf $'a\u0301AV' --language=en
[.notdef=0+500|acutecomb=0+0|A=2+600|V=3+600]
$ hb-shape mark-gpos-kerx.ttf $'a\u0301AV' --language=en
[.notdef=0+500|acutecomb=0+200|A=2+600|V=3+600]
```

**Expected.** Either `kerx` applies after GPOS (A V −40) or the plan doesn’t claim it; and marks zeroed as before.

---

## 39. `trak` vertical tracking is added with the wrong sign

**Summary.** `trak` adds its vertical value to `y_advance` without negating it (`src/hb-aat-layout-trak-table.hh:242`). Vertical advances are negative in HarfBuzz, so positive tracking, which should loosen a column, tightens it. GPOS negates in the same situation.

**Repro.** `trak.ttf` in the book’s test fonts (vertical track 0 = +100 at 12 pt):

```
$ hb-shape trak.ttf AV --direction=ttb --font-ptem=12
[A=0@-300,-750+0,-900|V=1@-300,-750+0,-900]
```

Without `trak` the advance is −1000; with +100 tracking it should be −1100.

---

## 40. `kerx` format 4 control-point attachment does nothing with the default font functions

**Summary.** Format 4’s control-point actions (type 0) ask the font functions for contour points, which hb-ot doesn’t implement (`glyph_contour_point` is commented out in `hb-ot-font.cc`). Unlike GPOS anchor format 2, there is no fallback to coordinates, so nothing is attached. Also `HB_DIRECTION_LTR /*XXX*/` at `hb-aat-layout-kerx-table.hh:628`.

**Repro.** `points.ttf` in the book’s test fonts: the marked glyph stays unattached with the default `ot` funcs.

---

## 41. In AAT, the first of two requests for one feature wins

**Summary.** For `morx` fonts, the AAT map sorts requested features by type, selector pair and then sequence, and keeps the first (`src/hb-aat-map.cc:139`–`155`). The OpenType map lets the later request win (`hb-ot-map.cc:238`). So the same feature list does opposite things in the two kinds of font.

**Repro.** `latin.ttf` (a `morx` font with an f i ligature) against `ligatures.ttf` (GSUB), both from the book’s test fonts:

```
$ hb-shape latin.ttf fi --features=-liga,liga
[f=0+500|i=1+500]
$ hb-shape ligatures.ttf fi --features=-liga,liga
[f_i=0+900]
```

**Expected.** The later request wins in both, as `hb_shape`’s documentation of feature lists implies.

---

## 42. hb-depend: documentation errors and loose ends

* `src/hb-subset-depend.h:90` documents `layout_tag` as 0 for edges not from GSUB; it is `HB_CODEPOINT_INVALID` (0xFFFFFFFF), as a program built against the API shows.
* `docs/depend-implementation.md`: says an edge takes only the first feature using its lookup (the code makes one edge per feature, `hb-depend-data.hh:559`); names the header `hb-depend.h`; calls the utility “TODO” though `util/hb-subset-depend.cc` exists; shows `lookup_features[256]`; gives the closure of {f} under `f i → f_i` as {f, fi}, where `Ligature.hh:35` gives {f}.
* `hb_depend_data_builder_t::get_gsub_dependencies` is declared (`hb-depend-data.hh:650`) but never defined; the builder fields `unicodes` and `nominal_glyphs` are unused.
* `test/fuzzing/README.md:18` asks for `-Ddepend_api=true`; the option is `experimental_api`.
* The closure parity test (`hb-depend-closure-parity.cc:27`, `:326`) says it mirrors the subsetter’s order but runs GSUB before MATH; the subsetter runs MATH first (`hb-subset-plan.cc:467`). A GSUB output with math variants could make the two disagree (inferred, not tried).

---

## 43. The subsetter’s GSUB closure cuts long nested chains

**Summary.** `hb_ot_layout_lookups_substitute_closure` runs at most `HB_CLOSURE_MAX_STAGES` + 2 = 14 passes, and glyphs produced by nested lookups aren’t flushed until the next pass (`SubstLookup.hh:209`). A context rule that applies many lookups in a row at one position loses the glyphs after the fourteenth.

**Repro.** `nested.ttf` in the book’s test fonts (one context rule applying 20 single substitutions in turn, a → s1 → … → s20):

```
$ hb-subset nested.ttf --text=a -o nested-a.ttf
$ hb-shape nested.ttf a
[s20=0+500]
$ hb-shape nested-a.ttf a
[s14=0+500]
```

**Expected.** The subset shapes as the original does.

---

## 44. `HB_CLOSURE_MAX_STAGES` is smaller than its own comment requires

**Summary.** `hb-limits.hh:68` says the limit “must be larger than the number of times add_gsub_pause() is called in a collect_features call of any shaper”. It is 12; `collect_features_indic` makes 14 such calls (three named pauses plus one after each of the eleven basic features, `hb-ot-shaper-indic.cc:249`–`265`).

---

## 45. MATH data is lost for glyphs that only GSUB produces

**Summary.** The closure runs MATH before GSUB, and MathVariants is subset against `_glyphset_cmaped`, MathGlyphInfo against `_glyphset_mathed` (`hb-ot-math-table.hh:232`, `:1064`). Glyphs reached only through GSUB (`rtlm`, `ssty`, stylistic sets) keep their outlines but lose their size variants and italics corrections.

**Repro.** `math.ttf` in the book’s test fonts, subset with its `rtlm` forms; and HarfBuzz’s own `STIXTwoMath-Regular.ttf` with `ss08` kept: `uni222B.up` loses its variants and italics correction. Requesting the glyphs explicitly (`math-rtlm.ttf`) works around it.

---

## 46. `hb_set_invert`’s “Since” is wrong

**Summary.** `src/hb-set.cc:505` documents `hb_set_invert` as “Since: 3.0.0”. `NEWS` has it deprecated in 1.6.1 and undeprecated in 2.9.1, so it has existed since before 1.6.1. Documentation only.

---

## 47. The sanitizer drops a whole valid GSUB whose SingleSubst lookups cover many glyphs

**Summary.** `SingleSubstFormat1::sanitize` charges the operation budget half its Coverage population (`src/OT/Layout/GSUB/SingleSubstFormat1.hh:125`), and the budget is max(`HB_SANITIZE_MAX_OPS_MIN` 16384, `HB_SANITIZE_MAX_OPS_FACTOR` 64 × table length). Range-based Coverage makes such lookups tiny, so a small table with a few of them exceeds the budget, and the whole GSUB is rejected.

**Repro.** Two fonts of 20,001 glyphs, each lookup a SingleSubst format 1 over a range Coverage of about 20,000 glyphs. One lookup (72-byte GSUB): `hb-shape C1.ttf --unicodes=U+4E01 --features=ss01` gives `[g2=0+500]`. Three lookups (152-byte GSUB): `hb-shape C3.ttf --unicodes=U+4E01 --features=ss01` gives `[g1=0+500]`, and `ss02`, `ss03` likewise do nothing. `hb-subset` reports “sanitize failed on source table”.

**Expected.** A valid table accepted; a budget charge proportional to work the sanitizer actually does, or at least only the offending lookup dropped. Large CJK fonts with whole-repertoire stylistic sets could hit this.

---

## 48. The subsetter’s 256× buffer cap can make a valid subset fail

**Summary.** The subsetter retries a table with a doubled buffer up to 256 × the source table’s size (`src/hb-subset-table.hh:61`). A tiny source table whose subset legitimately grows larger (a SingleSubst format 1 over a range becoming format 2 once glyphs are dropped) hits the cap, and `hb-subset` fails with “Operation failed. Probably a bug.”

**Repro.** A 72-byte GSUB, one SingleSubst format 1 over 20,000 glyphs, subset with `--no-layout-closure` dropping glyphs whose IDs are multiples of 5 or 7 (checked by script in the chapter 36 work, not in the book).

---

## 49. `docs/serializer.md` and `docs/repacker.md` are out of date

* `docs/serializer.md`’s example pushes the root, `pop_pack`s it, then calls `end_serialize`, which returns early because nothing is current (`hb-serialize.hh:310`), so its links are never resolved.
* `docs/repacker.md` says plain Kahn sorting is tried first (there is only the shortest-distance sort, itself Kahn’s algorithm with a priority queue); that only GPOS subtables can be split (GSUB LigatureSubst can be, `graph/gsubgpos-graph.hh:383`); and that spaces add n × 2^32 to a link’s weight (the code multiplies it by space + 1, `graph/graph.hh:1911`).

---

## 50. A reordering custom glyph map breaks PairPos and ClassDef in the subset

**Summary.** The API allows any old→new glyph map, but several layout subsetters write records in old-glyph order and assume the new IDs keep it (`hb_map_retains_sorting`): PairPos format 1’s PairSet (`src/OT/Layout/GPOS/PairSet.hh:255`) comes out unsorted by second glyph, so its binary search fails; `ClassDef_remap_and_serialize` (`hb-ot-layout-common.hh:1500`) pushes unsorted pairs into an `hb_sorted_vector_t`, and the ClassDef loses glyphs. SingleSubst survives in HarfBuzz but writes Coverage indices out of order (fontTools warns “Coverage is not sorted by glyph ids”).

**Repro.** `kern.ttf` in the book’s test fonts (PairPos format 1, A against eight glyphs), subset with a reversing `--gid-map` into `kern-map.ttf`. Each pair `A C`, `A G`, … `A Y` kerns −10 to −80 in the original; in the subset only `A Q` still kerns.

**Expected.** Records sorted by new glyph ID, so the subset kerns as the original does.

---

## 51. Subsetting a symbol font drops its only `cmap` subtable

**Summary.** `cmap` subsetting keeps only (0,3), (0,4), (3,1), (3,10) and variation-selector subtables (`src/hb-ot-cmap-table.hh:2502`). A font whose only subtable is (3,0), as symbol fonts have, comes out with no `cmap`, though its glyphs are kept. fontTools drops (3,0) by default too but has `--symbol-cmap`; HarfBuzz has no option. Related, from the code only: a (3,1) subtable in a format other than 4 or 12 is skipped silently.

**Repro.** `symbol.ttf` (a (3,0)-only `cmap`) in the book’s test fonts, subset to `symbol-a.ttf`: `hb-info --list-tables` shows no `cmap`.

---

## 52. `HB_SUBSET_FLAGS_NOTDEF_OUTLINE` is ignored for CFF

**Summary.** Only the glyf and gvar subsetters read the flag (`Glyph.hh:265`), so a CFF font’s `.notdef` keeps its outline whether or not the flag is set. fontTools empties it in both.

**Repro.** `cff-o.otf` in the book’s test fonts, subset without `--notdef-outline`: `hb-shape --show-extents` shows `.notdef` with its original extents.

---

## 53. Small faults in the data generators

None affects the generated tables.

* `src/gen-hb-version.py:20`: the regex `(\d.\d.\d)` allows one digit per part, so since 10.0.0 the “already current” early exit never fires and the header is always rewritten.
* `src/gen-ragel-artifacts.py`: checks `len(sys.argv) < 4` but reads `sys.argv[4]`, so a missing argument gives an `IndexError` instead of the usage message.
* `src/update-unicode-tables.make:16`: `SOURCES` omits `DerivedCoreProperties.txt` and `emoji-test.txt`, so `clean-sources` leaves stale copies; possibly why the USE table header records DerivedCoreProperties 17.0.0 beside 18.0.0 for the rest (inferred).
* `src/gen-arabic-table.py`: reads `Blocks.txt` into a dictionary nothing uses; U+F2EE appears twice in `LIGATURES`.
* `src/gen-arabic-joining-list.py`: its usage string names `gen-arabic-joining-table.py`.
* `src/gen-emoji-table.py`: its header comment names only `emoji-data.txt`, not `emoji-test.txt`.
* `src/gen-indic-table.py`: the `Consonant_Killer: 'M'` entry, commented “U+17CD only”, decides nothing, since U+17CD is overridden to `Xgroup`.
* `gen-tag-table.py` and `gen-os2-unicode-ranges.py` cite `docs.microsoft.com` URLs, and the ISO 639 table cites `www-01.sil.org`.

---

## 54. Texts of 524,289 to 1,048,575 characters go almost unshaped: the operation budget starts negative

**Summary.** `hb_buffer_t::enter` computes the operation budget as `int limit = (int) hb_max (mul, (unsigned) HB_BUFFER_MAX_OPS_MIN)` with `mul = len × HB_BUFFER_MAX_OPS_FACTOR` (4096) unsigned (`src/hb-buffer.cc:345`). For lengths from 524,289 to 1,048,575 the cast gives a negative `max_ops`, so the budget is spent before shaping starts and most lookups don’t run. At exactly 524,288 it is `INT_MIN`, and the next decrement is signed overflow, undefined behaviour. From 1,048,576 the unsigned multiply overflows, the `if` is skipped, and the default budget applies again. Nothing reports it: `hb-shape` doesn’t check `hb_buffer_allocation_successful`.

**Repro.** `ligatures.ttf` in the book’s test fonts, with `fi` repeated:

```
 524,286 characters: 262,143 f_i ligatures
 524,290 characters: 1 ligature, then plain f and i
1,000,000 characters: 1 ligature
1,048,576 characters: 524,288 ligatures
```

**Expected.** The budget clamped to `INT_MAX` (or computed in a wider type), so long texts shape fully.

---

## 55. `HB_LEAN` removes drawing and painting in every Meson build

**Summary.** `hb-config.hh:85` keeps drawing and painting under `HB_LEAN` only if `HB_HAS_CAIRO`, `HB_HAS_RASTER`, `HB_HAS_VECTOR` or `HB_HAS_GPU` is defined. Those come only from `hb-features.h`, which no library source includes (only `harfbuzz-world.cc` does, when `HB_FEATURES_H` is set); Meson’s `config.h` has `HAVE_RASTER` and so on instead. Checked with the preprocessor against a build with raster and vector on: `-DHB_LEAN` still defines `HB_NO_DRAW`.

---

## 56. `hb-features.h` never defines `HB_HAS_GPU` or `HB_HAS_GRAPHITE`

**Summary.** `src/meson.build:587` maps `HAVE_GPU` and `HAVE_GRAPHITE` to `HB_HAS_*`, but Meson sets `HAVE_GRAPHITE2`, and the `gpu` option sets no `HAVE_` macro. The book’s build has `#undef HB_HAS_GPU` in `hb-features.h` though `libharfbuzz-gpu` was built. (The graphite half is from reading the Meson files.)

---

## 57. Unused and undocumented configuration and limits

* `HB_MINIMIZE_MEMORY_USAGE_VAL` (`hb-config.hh:205`), `HB_SVG_MAX_PATH_SEGMENTS` and `HB_SANITIZE_MAX_EDITS` are defined but never used.
* `CONFIG.md` describes `HB_MINI` as dropping AAT and legacy shaping, but it also sets `HB_NO_BEYOND_64K` and `HB_NO_CUBIC_GLYF`; it doesn’t mention `HB_CONFIG_OVERRIDE_LAST_H`, nor about 70 other `HB_NO_*` macros.
* A composite component dropped by the subsetter’s nesting or operation limit keeps its old glyph ID when written (`SubsetGlyph.hh:55`), so it may point at the wrong glyph in the subset (inferred).

---

## 58. Cross-stream kerning breaks the unsafe-to-break promise

**Summary.** In legacy `kern` and `kerx`, a cross-stream value raises every later glyph, but only the pair is marked unsafe to break. A line broken later in the run shapes differently.

**Repro.** `cross.ttf` in the book’s `legacy-kern` test fonts (and `aat-positioning/cross.ttf`, `cross-first.ttf` with `גבגב`):

```
$ hb-shape cross.ttf AVAT --verify
harfbuzz buffer verify error: unsafe-to-break test failed.
```

---

## 59. Hangul at cluster level 1 breaks the unsafe-to-break promise

**Summary.** `hb-ot-shaper-hangul.cc:385` calls `merge_out_grapheme_clusters`, which at levels other than 0 neither merges nor flags, so a trailing jamo keeps its own cluster, unflagged, though it shapes with the syllable before it.

**Repro.** `hangul-koh.ttf` in the book’s test fonts: `hb-shape hangul-koh.ttf $'\uAC00\u11EB' --cluster-level=1 --verify` fails the unsafe-to-break test.

---

## 60. `hb-shape --text-before` echoes its value to stderr

**Summary.** A leftover debugging line, `fprintf(stderr, "%s\n", opts->text_before);`, at `util/text-options.hh:224`.

---

## 61. Small instancing differences from fontTools

* After limiting an axis, `SegmentMaps::subset` maps the new range back through `avar` instead of using the quantized limit (its comment: “unmap_axis_range needs to be killed”), and the `avar` map can be one 2.14 unit off. In `var-avar.ttf` limited to wght 400–800, `I` at wght 570 has advance 370 where the original has 369 (fontTools matches the original).
* Pinning an axis that VARC uses is refused by design (`VARC-subset.hh:101`), but `hb-subset` reports “Operation failed. Probably a bug. File github issue.”
* With `avar` 2 and weight pinned, one unreachable region stays in `MVAR`.

---

## 62. `hb_style_get_value (opsz)` returns OS/2 optical sizes in twentieths of a point

**Summary.** OS/2 version 5’s `usLowerOpticalPointSize` and `usUpperOpticalPointSize` are in TWIPs (1/20 pt). `OS2V5Tail::get_optical_size` (`src/hb-ot-os2-table.hh:86`) returns them unconverted, and `hb_style_get_value` (`hb-style.cc:101`) averages them as points.

**Repro.** `style-size.ttf` in the book’s test fonts, with an optical range of 8–24 pt (160–480 TWIPs): `hb_style_get_value (font, HB_STYLE_TAG_OPTICAL_SIZE)` returns 320, not 16.

---

## 63. BASE min/max: missing values read as 0

**Summary.** For a script with language-system MinMax records but no `DefaultMinMax`, `get_min_max` returns true with ascender and descender 0 for every other language (`src/hb-ot-layout-base-table.hh:482`). A null Min or Max coord is also read as 0 rather than reported missing. And a script record with MinMax but no BaseValues hides `DFLT`’s baselines from that script.

**Repro.** `base.ttf` in the book’s test fonts, queried with the chapter’s `query.c`.

---

## 64. `STAT::get_value` takes the first axis value, and STAT suppresses synthetic slant

**Summary.** `STAT::get_value` returns the first axis value record for the axis, which need not be the font’s own (weight 300 in a bold font); format 4 records are never matched. Because STAT (or `fvar`) is consulted before `post`, a STAT `slnt` value also stops `hb_style_get_value` adding synthetic slant (`hb-style.cc:114` is reached only in the `post` fallback).

**Repro.** `style-stat.ttf` in the book’s test fonts.

---

## 65. Smaller things in `name`, BASE and MATH

* `hb-info --list-names` prints each entry in the command-line language, not the entry’s own, so the same string repeats.
* `minConnectorOverlap` (uint16) goes through `em_scale_dir (int16_t)` (`hb-font.hh:169`), so values ≥ 32768 come back negative (read from the code).
* For Unicode-platform name records, `name` calls `ltag::get_language`, which interns strings with `hb_language_from_string`: the quadratic risk `hb-aat-ltag-table.hh:77` says `morx` avoids (read from the code).
* `choose_base_tags` keeps the last script tag (`deva`), so a BASE keyed `dev2` is missed and `DFLT` used.

---

Note from chapter 41: `test/fuzzing/README.md:13` lists the fuzzers without the gpu fuzzer (add to draft 42 if filed). Upstream checks so far: draft 23 is addressed after 15.1.0 by commit `fd57025` (PR #6558), not yet retested; draft 43 is related to the closed issue #5993.
