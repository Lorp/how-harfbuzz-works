# Buffers

Everything HarfBuzz shapes passes through one object, the `hb_buffer_t`. An application fills it with characters, sets a few properties, hands it to `hb_shape`, and reads glyphs and positions back out of the same object. In between, the buffer is HarfBuzz’s working memory. Every step of the pipeline reads and rewrites the same arrays, and keeps notes about each glyph in private fields that change meaning several times during a single call.

[Why shaping exists](why-shaping-exists.html) introduced the two structs a buffer returns, `hb_glyph_info_t` and `hb_glyph_position_t`, along with segment properties, clusters, and three of the cluster levels. This chapter is about the machinery underneath: how the buffer makes a separate output array only when it has to, how eight bytes of scratch space in each glyph are lent to one stage after another, how clusters are merged and what each of the four cluster levels changes, what the glyph flags and buffer flags do, and how a buffer can be watched and checked while it is shaped.

The examples use one small test font, `buffers.ttf`, built from `fonts/buffers/buffers.fea`. It has an *fi* ligature whose lookup passes over marks, a multiple substitution that turns *x* into *f i*, a combining acute with a mark attachment, a dotted circle, beh in its four Arabic forms with tatweel, and the Devanagari conjunct K.SSA. Every shaping result and trace on this page was produced by running HarfBuzz {{hb}} on it when the page was built.

## What a buffer holds

`struct hb_buffer_t` is defined in `hb-buffer.hh:70`. Its fields fall into groups:

| Group | Fields | What they are for |
|---|---|---|
| Settings | `unicode`, `flags`, `cluster_level`, `replacement`, `invisible`, `not_found`, `not_found_variation_selector` | chosen by the application, kept across shaping calls |
| Contents | `content_type`, `props`, `info`, `pos`, `out_info`, `len`, `idx`, `out_len`, `allocated` | the glyphs and the cursor over them |
| State | `successful`, `have_output`, `have_positions` | whether anything has failed, and which arrays mean something |
| Context | `context[2][5]`, `context_len[2]` | up to five code points either side of the run |
| Per call | `allocated_var_bits`, `serial`, `random_state`, `scratch_flags`, `max_len`, `max_ops`, `digest` | working state for one shaping call |
| Messaging | `message_func`, `changed_func`, `message_depth`, and their data | the tracing hooks |

Of the settings, `replacement` (U+FFFD by default) is what invalid UTF-8, UTF-16, or UTF-32 decodes to, `not_found` is the glyph for a character the font lacks (`.notdef` by default), and `invisible` is the glyph that hidden default ignorables become (the font’s space by default). `hb_buffer_clear_contents` (`clear`, `hb-buffer.cc:301`) forgets the text, the segment properties, and the context, and keeps the settings. `hb_buffer_reset` (`:286`) also restores the default settings. Neither removes a message callback. The `scratch_flags` are hints that one stage leaves for later ones, such as “there are default ignorables” or “GPOS attached something”, so that a later stage can skip a loop over the buffer when its flag is clear (`hb-buffer.hh:46`).

## Content types

A buffer’s **content type** is `INVALID` (empty), `UNICODE` (characters), or `GLYPHS` (glyph IDs), and it says what the `codepoint` field of every `hb_glyph_info_t` means. The transitions look after themselves, as the comment on `hb_buffer_set_content_type` explains, so a loop of “clear, add text, shape” never sets the type by hand: adding text to an empty buffer makes it `UNICODE`, and a successful `hb_shape_plan_execute` makes it `GLYPHS`.

Inside the `ot` shaper, the switch happens partway through, in `hb_ot_map_glyphs_fast` (`hb-ot-shape.cc:844`), just before GSUB. A trace shows it, because `hb-shape` prints each state differently: characters in angle brackets, glyphs in square brackets, and glyphs with advances once positions exist.

```trace
font: buffers.ttf
text: x
options: --language=en
from: start decompose
to: start table GPOS
```

The buffer is Unicode during normalization, glyphs without positions during GSUB (where `ccmp` turns the *x* into *f i*), and glyphs with positions from GPOS on. The missing positions during GSUB are not just a matter of printing: during GSUB, the positions array holds something else.

## Adding text

The `hb_buffer_add_utf8`, `_utf16`, `_utf32`, `_latin1`, and `_codepoints` functions all go through one template, `hb_buffer_add_utf` (`hb-buffer.cc:1868`). Each takes the caller’s whole string, with an `item_offset` and `item_length` saying which part of it is the run, and sets each character’s cluster to its offset in the string, in the string’s own code units:

```shape
buffers.ttf  \u00E9fi  --language=en
buffers.ttf  \u00E9fi  --language=en  --utf8-clusters
```

In UTF-8, *é* takes two bytes, so with `--utf8-clusters` the ligature’s cluster is 2. An application can also call `hb_buffer_add` with any cluster value it likes: HarfBuzz never interprets a cluster except to compare it with others.

The text outside the item is kept. Up to five code points before it become the **pre-context**, and up to five after it the **post-context** (`CONTEXT_LENGTH`, `hb-buffer.hh:109`), stored “ordered outward”, so `context[0][0]` is the character just before the run. The pre-context is only taken while the buffer is empty, so that a caller can supply it in one call and the text in another (the comment cites Mozilla bug 801410). Context is never shaped and never output. It is there for rules that look across the edge of the run, and Arabic joining is the plainest case:

```shape
buffers.ttf  ب
buffers.ttf  ب  --text-before=ب
buffers.ttf  ب  --text-after=ب
buffers.ttf  ب  --text-before=ب  --text-after=ب
```

The Arabic joining state machine starts from the pre-context and ends with the post-context (`arabic_joining`, `hb-ot-shaper-arabic.cc:301`), so one beh takes the form it would have inside the longer word.

> For programmers: when a paragraph is split into runs, pass the whole paragraph to `hb_buffer_add_utf8` with the run’s offset and length. The context comes for free, and the clusters are offsets into the paragraph.

Segment properties, and guessing them, are covered in [Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told). One thing belongs here: the `ot` shaper changes `props.direction` itself. A run whose direction isn’t its script’s natural one is reversed into native order at the start (`hb_ensure_native_direction`, `hb-ot-shape.cc:591`), and the requested direction, saved as `target_direction`, is put back as the last step of shaping (`:1200`).

## The buffer’s three arrays

A buffer has two arrays of 20-byte records, `info` and `pos`, which grow together in `enlarge` (`hb-buffer.cc:159`). Two static assertions in `hb-buffer.hh:38` insist that the two structs are exactly the same size, and the reason is a third array, `out_info`, which has no memory of its own.

Many steps read the glyphs in order and write a new sequence that may be longer or shorter: normalization, GSUB lookups, dotted-circle insertion, and several script shapers. For these the buffer has an output mode. `clear_output` (`:401`) starts it, setting `have_output` and pointing `out_info` at the same memory as `info`. The step reads the input at `idx` and appends to the output at `out_len`. `next_glyph` copies the current glyph to the output, but while the two arrays are the same and `out_len` equals `idx`, the glyph is already where it belongs, so nothing is copied (`hb-buffer.hh:354`):

```c++
bool next_glyph ()
{
  if (have_output)
  {
    if (out_info != info || out_len != idx)
    {
      if (unlikely (!ensure (out_len + 1))) return false;
      out_info[out_len] = info[idx];
    }
    out_len++;
  }
  idx++;
  return true;
}
```

As long as the output never gets ahead of the input, everything happens in place. A single substitution writes one glyph for one, and a ligature one for several, so neither ever gets ahead. Only a step that writes more glyphs than it has read needs memory of its own, and that is handled in `make_room_for` (`hb-buffer.cc:207`):

```c++
if (out_info == info &&
    out_len + num_out > idx + num_in)
{
  out_info = (hb_glyph_info_t *) pos;
  hb_memcpy (out_info, info, out_len * sizeof (out_info[0]));
}
```

The output moves into the positions array, which is the same size and, during substitution, holds nothing. At the end of the step, `sync` (`:424`) copies the rest of the input across and, if the arrays were separate, swaps them: the output becomes `info`, and the old `info` memory becomes `pos`. Here is an *x* between an *a* and an *e* going through the `ccmp` lookup (an illustration, not HarfBuzz output):

```
start          info = out_info   [ a  x  e ]      idx 0  out_len 0
copy a         in place          [ a  x  e ]      idx 1  out_len 1
x → f i        would overtake:   out_info moves into pos's memory
               out_info          [ a  f  i ]      idx 2  out_len 3
copy e         out_info          [ a  f  i  e ]   idx 3  out_len 4
sync           info ← out_info, pos ← old info, len 4
```

That is why there are no positions during GSUB. `clear_positions` (`:412`) ends output mode, sets `have_positions`, and zeroes the array, and GPOS then works in place: its lookups never use output mode (`always_inplace`, `hb-ot-layout.cc:1965`), and neither do reverse chained substitutions. Other backends borrow the same memory: `get_scratch_buffer` (`hb-buffer.cc:255`) hands the positions array to the Core Text, DirectWrite, Uniscribe, and Graphite backends as scratch space.

Contextual lookups need one more operation. A nested lookup may have to run at a position the main loop has passed, so `move_to` (`:477`) moves the boundary between output and input either way, copying glyphs across, and if the output has outgrown the input, `shift_forward` (`:225`) first makes room. Both are charged to the buffer’s operation budget. And messages to a tracing callback are only sent when output and input agree: `message_impl` asserts that the buffer is in sync (`hb-buffer.cc:2441`), so a callback never sees a half-finished lookup.

## Eight bytes of scratch space

Each `hb_glyph_info_t` has two private fields, `var1` and `var2`, unions that can be read as one 32-bit number, two 16-bit numbers, or four bytes. Together they are eight bytes per glyph for HarfBuzz’s notes. No stage needs all eight for the whole of shaping, so the bytes are lent out and taken back as shaping goes along, like registers in a processor. Each use is a macro that names a field, in `hb-ot-layout.hh:154`:

```c++
#define unicode_props()  var2.u16[0]
#define glyph_props()    var1.u16[0] /* GDEF glyph properties */
#define lig_props()      var1.u8[2]  /* GSUB/GPOS ligature tracking */
#define syllable()       var1.u8[3]  /* GSUB/GPOS shaping boundaries */
```

so that `info.glyph_props()` reads as a field. The script shapers share two more bytes, `ot_shaper_var_u8_category()` and `ot_shaper_var_u8_auxiliary()` (`hb-ot-shaper.hh:38`), which each shaper renames: `indic_category()`, `arabic_shaping_action()`, and so on.

The lending is checked. The buffer keeps one bit per byte in `allocated_var_bits`, and `HB_BUFFER_ALLOCATE_VAR (buffer, glyph_props)` works out from the field’s offset and size which bytes it occupies (`hb-buffer.hh:724`) and claims them (`:151`):

```c++
void allocate_var (unsigned int start, unsigned int count)
{
  unsigned int end = start + count;
  assert (end <= 8);
  unsigned int bits = (1u<<end) - (1u<<start);
  assert (0 == (allocated_var_bits & bits));
  allocated_var_bits |= bits;
}
```

Claiming a byte twice fails an assertion, and so does releasing one that isn’t claimed (`HB_BUFFER_DEALLOCATE_VAR`). Code that only reads a field can check it is claimed with `HB_BUFFER_ASSERT_VAR`, as GSUB and GPOS do for `glyph_props` and `lig_props` (`hb-ot-layout.cc:273`, `OT/Layout/GPOS/GPOS.hh:166`). With assertions on, as when HarfBuzz is tested, two stages that use the same byte at once stop the program; with `NDEBUG` the checks cost nothing. `enter` and `leave`, around every shaping call, clear all eight bits.

### Who has which byte, and when

Bytes 0–3 are `var1` and 4–7 are `var2`. This table lists every allocation in the `ot` shaper in {{hb}}, from the `HB_BUFFER_ALLOCATE_VAR`, `HB_BUFFER_TRY_ALLOCATE_VAR`, and `HB_BUFFER_DEALLOCATE_VAR` calls, in the order the bytes are claimed:

| Field | Bytes | Claimed | Released |
|---|---|---|---|
| `unicode_props` | 4–5 | first thing in `hb_ot_shape_internal` (`hb-ot-shape.cc:1176`) | last thing, after the glyph flags are propagated (`:1198`) |
| `hangul_shaping_feature` | 7 | Hangul’s `preprocess_text` (`hb-ot-shaper-hangul.cc:148`) | Hangul’s `setup_masks` (`:429`) |
| `normalizer_glyph_index` | 0–3 | before normalization, in `hb_ot_substitute_default` (`hb-ot-shape.cc:888`) | once `hb_ot_map_glyphs_fast` has copied it into `codepoint` (`:900`) |
| `indic_category`, `khmer_category`, `myanmar_category`, `use_category` | 6 | the shaper’s `setup_masks` (`hb-ot-shaper-indic.cc:401`, `-khmer.cc:178`, `-myanmar.cc:142`, `-use.cc:201`) | the shaper’s reordering pause in GSUB (`hb-ot-shaper-indic.cc:1457`, `-khmer.cc:319`, `-myanmar.cc:340`, `-use.cc:467`) |
| `indic_position`, `myanmar_position` | 7 | the same (`hb-ot-shaper-indic.cc:402`, `-myanmar.cc:143`) | the same (`hb-ot-shaper-indic.cc:1458`, `-myanmar.cc:341`) |
| `arabic_shaping_action` | 7 | `setup_masks_arabic_plan` (`hb-ot-shaper-arabic.cc:395`) | a GSUB pause after the joining-form features (`:182`, added at `:225`) |
| `glyph_props`, `lig_props` | 0–2 | just before GSUB or `morx`, in `hb_ot_substitute_pre` (`hb-ot-shape.cc:940`) | after GPOS and the final reversal, in `hb_ot_position` (`:1105`) |
| `syllable` | 3 | a syllabic shaper’s first GSUB pause, which finds syllables (`hb-ot-shaper-indic.cc:418`, `-khmer.cc:194`, `-myanmar.cc:158`, `-use.cc:301`) | a pause at the end of GSUB, `hb_syllabic_clear_var` (`hb-ot-shaper-syllabic.cc:107`) |
| `syllable`, borrowed as a class cache | 3 | at the start of a lookup whose cache goes to a format 2 context subtable, if the byte is free (`hb-ot-layout-gsubgpos.hh:3079`) | at the end of that lookup (`:3091`) |

The design shows in the table. `normalizer_glyph_index` takes the whole of `var1`, but only while the text is normalized and masks are set up, and it is released just before `glyph_props` and `lig_props` claim three of the same bytes. The fourth, `syllable`, waits for an Indic, Khmer, Myanmar, or USE shaper to claim it in a GSUB pause, and is given back before GSUB ends. The shapers’ own bytes are claimed while masks are set up, when normalization still holds all of `var1`, so they have to live in `var2`.

The last row is the neatest. A format 2 context lookup matches glyphs by class, and finding a glyph’s class in a ClassDef table is a search. Each lookup lets one subtable use a cache, the one that says it would save most (`hb-ot-layout-gsubgpos.hh:1585`). When that is a format 2 context subtable and no shaper holds `syllable`, it claims the byte with `HB_BUFFER_TRY_ALLOCATE_VAR`, which returns false rather than asserting, and sets it to 255, “not known”, on every glyph. Each glyph’s class is then stored there the first time it is looked up (`get_class_cached`, `:1856`), and a glyph that the lookup substitutes has its byte reset to 255 (`_set_glyph_class`, `:1345`). When a syllabic shaper holds the byte, the lookup runs without the cache. Since syllables are released before GPOS, GPOS context lookups in those scripts can use it.

The positions have a scratch field too, `hb_glyph_position_t.var`, outside the allocation bits. GPOS keeps attachments there, `attach_chain()` and `attach_type()` (`OT/Layout/GPOS/Common.hh:17`), and the Arabic shaper keeps `stch` advances (`hb-ot-shaper-arabic.cc:39`). Both run only after `clear_positions`, when the array really holds positions.

> For programmers: `mask`, `var1`, `var2`, and `var` are private, and after shaping they hold whatever the last stage to use them left. Read glyph flags with `hb_glyph_info_get_glyph_flags`. Other backends use the same fields differently: Core Text, DirectWrite, and Uniscribe keep glyph offsets in `var1` and `var2` while converting their results.

What `unicode_props` holds is in [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html), and what `glyph_props` and `lig_props` hold is in the [GSUB chapter](gsub.html#glyph-properties).

## The mask

The other private field, `mask`, is divided up too:

| Bits | Use |
|---|---|
| 0–2 | the public glyph flags |
| 3 | unused |
| 4–29 | feature bits, handed out during planning (`hb-ot-map.cc:276`) |
| 30 | never handed out, because of an off-by-one test ([From features to lookups](from-features-to-lookups.html#running-out)) |
| 31 | the global bit, shared by every feature that is on for the whole run with value 1 |

How features get their bits is in [From features to lookups](from-features-to-lookups.html). Each glyph’s mask starts as the plan’s global mask (`hb-ot-shape.cc:486`). A feature the application asks for over a range is then applied with `set_masks` (`hb-buffer.cc:539`), and the range is compared with *cluster values*, not positions in the buffer:

```shape
buffers.ttf  fifi  --language=en
buffers.ttf  fifi  --language=en  --features=-liga[1]
buffers.ttf  fifi  --language=en  --features=-liga[3:]
```

Turning `liga` off for cluster 1, the first *i*, is enough to stop the first ligature, since every glyph a ligature uses needs the lookup’s bit. Because ranges are clusters, they are in whatever units the clusters are: characters here, bytes for an application that adds UTF-8.

## Merging clusters

Every step that combines or reorders glyphs merges their clusters, with `merge_clusters_impl` (`hb-buffer.cc:569`). Here it is, with operation counting left out:

```c++
unsigned int cluster = info[start].cluster;
for (unsigned int i = start + 1; i < end; i++)
  cluster = hb_min (cluster, info[i].cluster);

/* Extend end */
if (cluster != info[end - 1].cluster)
  while (end < len && info[end - 1].cluster == info[end].cluster)
    end++;

/* Extend start */
if (cluster != info[start].cluster)
  while (idx < start && info[start - 1].cluster == info[start].cluster)
    start--;

/* If we hit the start of buffer, continue in out-buffer. */
if (idx == start && info[start].cluster != cluster)
  for (i = out_len; i && out_info[i - 1].cluster == info[start].cluster; i--)
    set_cluster (out_info[i - 1], cluster);

for (unsigned int i = start; i < end; i++)
  set_cluster (info[i], cluster);
```

The merged cluster takes the smallest value, and the range always grows to whole clusters: if a cluster at either end carries on past the range, the rest of it is merged too, including any part already written to the output. Otherwise a merge could split a cluster in two. `merge_out_clusters_impl` (`:610`) is the mirror image, for a range of the output. `set_cluster` (`hb-buffer.hh:642`) also replaces the glyph flags of any glyph whose cluster it changes, with none unless it is given some.

Deleting a glyph has to merge too, or a character could vanish with no cluster to say where it went. `delete_glyph` (`hb-buffer.cc:652`) does nothing if a neighbor shares the glyph’s cluster. Otherwise it merges the cluster backward into the glyph before, if that glyph’s cluster is larger, or, at the start of the buffer, forward into the glyph after. `delete_glyphs_inplace` (`:694`) does the same once positions exist. Removing a ZWNJ shows both cases:

```shape
buffers.ttf  a\u200Ce  --remove-default-ignorables
buffers.ttf  \u200Cae  --remove-default-ignorables
```

In the first, cluster 1 just disappears, since merging it backward would make the *a*’s cluster larger. In the second, the ZWNJ is first, so it merges forward, and the *a* takes its cluster, 0.

### Four ways in

The pipeline never calls `merge_clusters_impl` directly. It calls one of four functions (`hb-buffer.hh:396`), and the cluster level decides whether each one merges:

| Function | Merges when the level is | Otherwise |
|---|---|---|
| `merge_clusters` | monotone (0 or 1) | marks the range unsafe to break |
| `merge_grapheme_clusters` | grapheme (0 or 3) | marks the range unsafe to break |
| `merge_out_clusters` | monotone (0 or 1) | nothing |
| `merge_out_grapheme_clusters` | grapheme (0 or 3) | nothing |

`merge_clusters` is the common one. A ligature calls it (`ligate_input`, `hb-ot-layout-gsubgpos.hh:2091`), as do `replace_glyphs`, `buffer->sort` (which normalization uses to put marks in order, `hb-buffer.cc:2239`), and the Indic, Khmer, USE, Arabic, and Hebrew shapers when they move or combine glyphs. Normalization calls `merge_out_clusters` when it composes two characters into one. Only one place calls `merge_grapheme_clusters`: `hb_form_clusters` (`hb-ot-shape.cc:581`), at the start of shaping, which groups each base character with the characters that continue it.

## The four cluster levels

The two properties those functions test make up the cluster levels’ names. **Graphemes**: before shaping, each base is merged with the characters that continue it. **Monotone**: whenever glyphs are combined or reordered, their clusters are merged, so cluster values only rise along the buffer (or only fall, in right-to-left output). The four levels are the four combinations (`hb-buffer.h:461`):

| Level | Name | Graphemes merged first | Clusters kept in order |
|---|---|---|---|
| 0 | `MONOTONE_GRAPHEMES` (the default) | yes | yes |
| 1 | `MONOTONE_CHARACTERS` | no | yes |
| 2 | `CHARACTERS` | no | no |
| 3 | `GRAPHEMES` | yes | no |

HarfBuzz’s code tests the properties with `HB_BUFFER_CLUSTER_LEVEL_IS_MONOTONE`, `_IS_GRAPHEMES`, and `_IS_CHARACTERS`, not by comparing numbers. Level 3 and the three macros arrived together in 11.0.0, according to `NEWS`. The header documents all four levels; the clusters chapter of the user manual (`docs/usermanual-clusters.xml`) still describes three.

What continues a base is decided by the “continuation” bit in `unicode_props`, which [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#continuations-just-enough-of-graphemes) lists in full: marks, and a few other characters, but not ZWNJ. HarfBuzz implements only “enough of Unicode Graphemes” for its own purposes. Hence the header’s description of level 3 as “similar to the Unicode Grapheme Cluster algorithm, but … not exactly the same”.

Three pieces of text show the differences. First, a ZWJ between two letters:

```shape
buffers.ttf  a\u200De  --cluster-level=0  --show-flags
buffers.ttf  a\u200De  --cluster-level=1  --show-flags
buffers.ttf  a\u200De  --cluster-level=2  --show-flags
buffers.ttf  a\u200De  --cluster-level=3  --show-flags
```

At the grapheme levels, 0 and 3, the ZWJ (by now a hidden space) is in the *a*’s cluster. At 1 and 2 it keeps cluster 1, and `merge_grapheme_clusters` marks it unsafe to break instead.

Second, *f i* with an acute between them, which the ligature lookup passes over:

```shape
buffers.ttf  f\u0301i  --language=en  --cluster-level=0
buffers.ttf  f\u0301i  --language=en  --cluster-level=1
buffers.ttf  f\u0301i  --language=en  --cluster-level=2
buffers.ttf  f\u0301i  --language=en  --cluster-level=3
```

At level 0 the *f* and the acute are one cluster from the start, and the ligature merges in the *i*. At level 1 the acute starts in cluster 1, but the ligature merges everything from its first component to its last, including the mark it passed over. At level 2 nothing merges: the acute keeps 1, and the *i*’s cluster 2 is simply gone. At level 3 the acute was merged with the *f* first, and the ligature doesn’t merge. At the non-monotone levels, a missing cluster number means that character has no glyph of its own, and an application has to work out where it went.

Third, reordering. With K.SSA and the vowel sign I, the vowel sign moves in front of the conjunct:

```shape
buffers.ttf  क\u094Dष\u093F  --cluster-level=0
buffers.ttf  क\u094Dष\u093F  --cluster-level=1
buffers.ttf  क\u094Dष\u093F  --cluster-level=2
buffers.ttf  क\u094Dष\u093F  --cluster-level=3
```

The characters are KA (0), virama (1), SSA (2), and I (3). At the monotone levels the Indic shaper’s reordering merges the whole syllable into cluster 0. At level 2 the vowel sign keeps cluster 3 and comes first. Level 3 is the new case: the virama was merged with KA and the vowel sign with SSA before shaping, since both are marks, and the reordering merged nothing more. The vowel sign comes first with cluster 2, the grapheme SSA + I, and the conjunct has 0. The clusters are out of order, but each is a whole grapheme, which is what level 3 is for: a program can tell which grapheme each glyph came from, without the merging that order requires, which at level 0 swallowed the whole syllable.

The level matters in a few other places. When `hb_ensure_native_direction` reverses a run it keeps each grapheme’s characters in order, and at level 1 also merges each grapheme’s clusters (`_hb_ot_layout_reverse_graphemes`, `hb-ot-layout.hh:401`). The verifier runs only at the monotone levels. And when glyph flags are set across a range, the smallest cluster is found by scanning the whole range only at level 2 (`hb-buffer.hh:664`, `:694`); otherwise only the first and last glyphs are looked at, which is right when clusters are in order. Level 3 is not in order, but in {{hb}} it doesn’t get the full scan.

> Since {{hb}}: fixed on HarfBuzz main by [`7f0fe35`](https://github.com/harfbuzz/harfbuzz/commit/7f0fe35618c08a7089af610b7546fa1cba484c29) (17 November 2026), so main scans the whole range at level 3 too.

> For programmers: the header recommends level 1 for new programs, and calls level 0 the default only for backward compatibility. Level 1 gives marks their own clusters where it can. A program that copes with clusters out of order can use level 2, or level 3 for clusters that are whole graphemes.

## Glyph flags

The three glyph flags live in the low bits of the mask (`hb-buffer.h:160`):

| Flag | Value | Added | Means |
|---|---|---|---|
| `UNSAFE_TO_BREAK` | 1 | 1.5.0 | breaking the text at the start of this cluster and shaping the two sides separately could change the result |
| `UNSAFE_TO_CONCAT` | 2 | 3.3.0 | changing the text on one side of the start of this cluster could change the result on the other |
| `SAFE_TO_INSERT_TATWEEL` | 4 | 5.1.0 | a tatweel can be inserted before this cluster without disturbing shaping |

The versions are from `NEWS`; the header gives 4.0.0 for `UNSAFE_TO_CONCAT`, the release that added the buffer flag that produces it. What applications do with them is in [For applications](for-applications.html). Here is how they are made.

All three are set over a range of glyphs by `_set_glyph_flags` (`hb-buffer.hh:488`), which ignores ranges longer than 255. `unsafe_to_break` sets both unsafe flags, so unsafe to break implies unsafe to concat, and it sets them only on the range’s *interior*: every glyph except those of the cluster with the smallest value, the cluster the range starts from (`_infos_set_glyph_flags`, `:649`). A context match, a kerning pair, an Arabic join, and an Indic syllable each mark their range this way, and so does every `merge_clusters` at a level where it doesn’t merge. (A ligature needs no flag of its own at the monotone levels: it merges its glyphs into one cluster, which leaves no boundary inside it to break at.)

Unsafe to concat is expensive, because it has to be recorded where matching *fails*: a ligature that nearly matched is just where different text would change the result. So `unsafe_to_concat` does nothing unless the buffer has `HB_BUFFER_FLAG_PRODUCE_UNSAFE_TO_CONCAT` (`:526`):

```shape
buffers.ttf  fa  --language=en  --show-flags
buffers.ttf  fa  --language=en  --show-flags  --unsafe-to-concat
buffers.ttf  af  --language=en  --show-flags  --unsafe-to-concat
buffers.ttf  ea  --language=en  --show-flags  --unsafe-to-concat
```

`hb-shape` prints flags as `#` and a hexadecimal value. In *fa* the ligature lookup looked at the *a* after the *f* and found no ligature, so both are marked: an *i* inserted between them would make one. In *af* the *f* is last, and an *i* after it would ligate. *ea* concerns no lookup, and stays clear.

The tatweel flag is set by the Arabic joining state machine wherever two letters join (`hb-ot-shaper-arabic.cc:335`), and without `HB_BUFFER_FLAG_PRODUCE_SAFE_TO_INSERT_TATWEEL` the same call marks the join unsafe to break instead (`hb-buffer.hh:512`):

```shape
buffers.ttf  ببب  --show-flags
buffers.ttf  ببب  --show-flags  --safe-to-insert-tatweel
buffers.ttf  بـب  --show-flags  --safe-to-insert-tatweel
```

The joins are unsafe to break either way, and with the flag asked for they also get 4. In the third line, with a tatweel typed between the behs, both sides of it are places where another could go.

At the end of shaping, `hb_propagate_flags` (`hb-ot-shape.cc:1109`) combines the flags of each cluster’s glyphs and gives the result to all of them, so any glyph of a cluster can be read. Unsafe to concat is cleared unless it was asked for, since otherwise it is only partly recorded. When tatweel flags were asked for, a cluster that is unsafe to break loses its tatweel flag, and a cluster that keeps one is then marked unsafe to break and unsafe to concat too: the comment says this interaction “couldn’t” be made earlier.

## Buffer flags

The buffer flags (`hb-buffer.h:396`) are the application’s instructions about the text:

| Flag | Value | What reads it in {{hb}} |
|---|---|---|
| `BOT` | 0x01 | `hb_insert_dotted_circle` (`hb-ot-shape.cc:552`), and the verifier |
| `EOT` | 0x02 | only the verifier |
| `PRESERVE_DEFAULT_IGNORABLES` | 0x04 | hiding default ignorables (`:817`) and zeroing their advances (`:772`) |
| `REMOVE_DEFAULT_IGNORABLES` | 0x08 | the same |
| `DO_NOT_INSERT_DOTTED_CIRCLE` | 0x10 | every kind of dotted-circle insertion |
| `VERIFY` | 0x20 | `hb_shape_full` (`hb-shape.cc:137`) |
| `PRODUCE_UNSAFE_TO_CONCAT` | 0x40 | `unsafe_to_concat` and flag propagation |
| `PRODUCE_SAFE_TO_INSERT_TATWEEL` | 0x80 | `safe_to_insert_tatweel` and flag propagation |

`NEWS` lists the first three as new in 0.9.7. The rest arrived in 1.8.0, 2.4.0, 3.4.0, 4.0.0, and 5.1.0, in table order.

**BOT and EOT** say the buffer begins or ends a paragraph. The `ot` shaper reads only `BOT`, for one purpose: a mark at the start of a paragraph has no base, and HarfBuzz gives it a dotted circle, if the font has one, but only when `BOT` is set and there is no pre-context:

```shape
buffers.ttf  \u0301
buffers.ttf  \u0301  --bot
buffers.ttf  \u0301  --bot  --text-before=e
```

Without `BOT` the mark might belong to a base before the buffer, so it is left alone. With `BOT`, the dotted circle takes the mark’s cluster and the mark attaches to it. With an *e* in the pre-context there is a base, and nothing is inserted. This is the rule `NEWS` announced in 0.9.34, “if there’s pre-context text in the buffer, HarfBuzz ignores the BOT flag”, so that an application can set `BOT` and `EOT` on every run of a paragraph and let the context decide. The dotted circles that syllabic shapers insert into broken syllables don’t depend on `BOT`: they are in [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html). `EOT` is read by nothing in the `ot` shaper. The verifier clears both on fragments from the middle of the text. `hb-shape` sets neither unless given `--bot` or `--eot`.

**The default-ignorable flags** decide what becomes of characters such as ZWJ, ZWNJ, and variation selectors once they have done their work. By default, after positioning, each is replaced with the `invisible` glyph or the space glyph, with no advance (`hb_ot_hide_default_ignorables`), or deleted if the font has no space. `PRESERVE` keeps the font’s own glyph, `.notdef` if there is none, and wins over `REMOVE`, which deletes them. [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#hidden-preserved-or-removed) shows all three.

Hiding comes after GSUB and GPOS, so lookups still see the characters, and pass over them, as the [GSUB chapter](gsub.html#joiners) describes. `DO_NOT_INSERT_DOTTED_CIRCLE` has no `hb-shape` option. `VERIFY` is described below.

## Limits

A font is a program of sorts, and the buffer is where HarfBuzz stops one that would run for ever or grow the text without end. `enter` (`hb-buffer.cc:326`), which runs around every shaping call including `hb_shape_plan_execute` (`hb-shape-plan.cc:433`), installs two limits: `max_len`, the most glyphs the buffer may grow to, 256 times its starting length and at least 65,536; and `max_ops`, an operation budget of 4,096 per glyph and at least 65,536. `leave` sets both back to very large defaults. The numbers are in `hb-limits.hh`, and all the limits are collected in the [Limits](limits.html) appendix.

The budget is charged by work that a font can make expensive: merging clusters, setting flags and masks, moving the output boundary, and each nested lookup a context lookup calls (`hb-ot-layout-gsubgpos.hh:1151`). When it runs out, or memory does, `successful` becomes false, the buffer stops growing, and the remaining steps do little or nothing. `hb_shape_full` still returns true, as [hb_shape and its backends](hb_shape-and-its-backends.html#running-the-plan-and-failing) explains: a program that needs to know calls `hb_buffer_allocation_successful`.

## Watching and checking a buffer

### Messages

`hb_buffer_set_message_func` installs a callback that HarfBuzz calls at each step, with a message such as `start lookup 3 feature 'calt'`. It is how [`hb-shape --trace`](command-line-tools.html#traces), and this book’s traces, work. If the callback returns false, HarfBuzz skips the step it was about to start: a whole GSUB or GPOS table, one lookup, normalization, a shaper’s preprocessing. Steps can be turned off one at a time to find which is responsible for a result.

Messages are formatted into 100 bytes (`hb-buffer.cc:2445`) and only sent when the buffer is in sync. While a callback runs, it may not install another (`:2396`), and `hb_buffer_get_glyph_positions` returns null rather than create positions that don’t exist yet. A callback that changes glyph IDs must call `hb_buffer_changed` (new in 13.0.0) to refresh the buffer’s digest. Since 12.0.0 the detailed messages from inside lookups need a build with `HB_BUFFER_MESSAGE_MORE` (`hb-debug.hh:452`). More is in [Testing HarfBuzz](testing-harfbuzz.html).

### Verification

With `HB_BUFFER_FLAG_VERIFY`, `hb_shape_full` keeps a copy of the text and checks the result against it (`hb-buffer-verify.cc:380`). All three checks are skipped at the non-monotone levels:

1. **Clusters are monotone.**
2. **Safe to break is safe**: the text is cut at every cluster boundary not marked unsafe to break, each piece is shaped alone, and the pieces together must equal the whole, apart from the flags.
3. **Safe to concat is safe**, if unsafe-to-concat flags were asked for: the text is cut at every boundary not marked unsafe to concat, the odd and the even pieces are shaped as two texts, and interleaving the results must give the whole again.

Failures go to the message callback, or to standard error, with the text, and a failed reshaping check replaces the buffer with the reconstruction so the difference can be seen. [`hb-shape --verify`](command-line-tools.html#verifying) arrived with unsafe to break in 1.5.0, `NEWS` for 1.5.1 says “All our tests pass with --verify now”, and since 3.4.0 the checks are in the library itself.

```shape
buffers.ttf  क\u094Dष\u093F  --verify
buffers.ttf  ببب  --verify  --unsafe-to-concat  --show-flags
```

Both pass, so the output is what it would be without `--verify`.

### Comparing and writing out

The verifier compares buffers with the public `hb_buffer_diff` (`hb-buffer.cc:2278`). It returns flags, not a yes or no: different content types, different lengths, and glyph by glyph, different glyph IDs, clusters, glyph flags, or positions, with an allowed error for positions. Given the dotted circle’s glyph ID, it also says whether the reference contains one, or `.notdef`, cases in which, the header says, a caller “may not care so much about other differences”.

`hb-shape` prints with `hb_buffer_serialize_glyphs` (`hb-buffer-serialize.cc`), in TEXT or JSON, with flags to leave out clusters, positions, or names, or add extents and glyph flags. `HB_BUFFER_SERIALIZE_FLAG_NO_ADVANCES` (`--no-advances`, part of `--ned`) prints each glyph’s absolute position instead of its advance:

```shape
buffers.ttf  ببب  --output-format=json  --show-flags
buffers.ttf  \u00E9fi  --language=en  --no-advances
```

`hb_buffer_serialize_unicode` writes the angle-bracket form the trace above began with, and the `hb_buffer_deserialize_*` functions read both formats back; {{hb}} adds `_glyphs2` and `_unicode2` versions that report how many bytes they read. Finally, `hb_buffer_normalize_glyphs` (`hb-buffer.cc:2226`) puts the glyphs inside each cluster into a fixed order, with the cluster’s advance on one glyph and offsets adjusted so nothing moves. As its documentation says, it has nothing to do with Unicode normalization: it makes results from shapers that order glyphs within a cluster differently comparable.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-buffer.h` | the public structs and enums: glyph info and positions, content types, buffer flags, glyph flags, cluster levels, serialization, diff, the message callback |
| `src/hb-buffer.hh` | `struct hb_buffer_t`, output mode, the four merge functions, setting glyph flags, the var allocation macros |
| `src/hb-buffer.cc` | adding text and context, `make_room_for`, `sync`, `move_to`, `merge_clusters_impl`, deleting glyphs, `enter` and `leave`, `hb_buffer_diff`, messages |
| `src/hb-buffer-verify.cc` | the three verification checks |
| `src/hb-buffer-serialize.cc` | the TEXT and JSON formats |
| `src/hb-ot-layout.hh`, `src/hb-ot-shaper.hh` | the named var fields and their allocation helpers |
| `src/hb-ot-shape.cc` | `hb_ot_shape_internal`: where vars are claimed and released, `hb_form_clusters`, dotted circles, hiding default ignorables, `hb_propagate_flags` |
| `src/hb-ot-layout-gsubgpos.hh` | `ligate_input`’s merge, and the class cache in the syllable byte |
| `src/hb-limits.hh` | `max_len` and `max_ops` |

## In short

* A buffer holds characters, then glyphs, in the same `info` array; its content type changes just before GSUB.
* Output is written in place until it would overtake the input, then moves into the positions array, which is why there are no positions until substitution is over.
* Clusters are the caller’s code-unit offsets. Up to five characters either side of the run are kept as context.
* `var1` and `var2` are eight bytes per glyph, lent to one stage after another and checked by `HB_BUFFER_ALLOCATE_VAR`.
* A merged cluster takes the smallest value and always covers whole clusters. Whether merging happens depends on two properties of the cluster level, merging graphemes first and keeping clusters in order; level 3, new in 11.0.0, does the first without the second.
* Unsafe to concat and safe to insert tatweel must be asked for with buffer flags. `BOT` only decides whether a leading mark gets a dotted circle, and `EOT` affects only verification.
* Message callbacks can watch and skip steps, and `VERIFY` checks clusters and flags by reshaping.
