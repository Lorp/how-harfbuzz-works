# For applications

HarfBuzz turns one run of text into one row of positioned glyphs, on a line of no particular length. Everything else an application does with text happens on either side of that call: splitting a paragraph into runs before it, and afterward putting a cursor between letters, finding the character under a click, breaking the row into lines, justifying them, and keeping all of it up to date while someone types. The user manual is blunt about where the line is drawn: “HarfBuzz won’t help you with line breaking, hyphenation, or justification” (`docs/usermanual-what-is-harfbuzz.xml:402`).

What HarfBuzz does give back for that work is in each `hb_glyph_info_t`: the cluster, which ties glyphs to the text, and three glyph flags, which say where the result can be cut and joined without shaping again. [Buffers](buffers.html) explains how both are made inside the library. This chapter is about using them: what they promise, how a line breaker uses them, where the promise has gaps, and what the application has to do itself.

The examples use one small test font, `apps.ttf`, built from `fonts/for-applications/apps.fea`. It has *fi*, *ff* and *ffi* ligatures, two kerning pairs (hyphen with *T*, and *T* with *o*), and beh in its four Arabic forms with tatweel. A few examples borrow fonts from other chapters. Every shaping result on this page was produced by running HarfBuzz {{hb}} when the page was built.

## Mapping glyphs back to text

A cluster value is whatever the application put in when it added the text: with the `hb_buffer_add_utf*` functions, each character’s offset in the caller’s string, in that string’s code units. Shaping merges clusters but never invents a value, so after shaping every glyph’s cluster is the offset of the first character it came from, and the characters a cluster covers run from its value up to the next cluster value along the text:

```shape
apps.ttf  office  --language=en
apps.ttf  ببب  --language=ar
```

In *office* the ligature has cluster 1 and the *c* after it 4, so the ligature covers characters 1, 2 and 3. In right-to-left text the glyphs come out in visual order, so the clusters fall along the buffer instead of rising: the first glyph is the last beh. An application that goes from text to glyphs (to color a range, or to find where a selection starts) looks for the cluster that contains the character; one that goes from glyphs to text (to find what was clicked) takes the glyph’s cluster and the next one.

Cursor positions come from the same arithmetic. A boundary between two clusters is a place a cursor can go, and its position is the sum of the advances before it. Inside a cluster of several characters, HarfBuzz gives no position. For a ligature, the font may: GDEF can hold **ligature carets**, and `hb_ot_layout_get_ligature_carets` (`hb-ot-layout.cc:397`) returns them, one fewer than the ligature has components. The test font gives *ffi* carets at 300 and 600. The documentation warns that the positions are “unshaped”, so kerning applied to the ligature has to be added by the caller, and the function reads only GDEF, not the AAT `lcar` table. A font without carets leaves the application to divide the ligature itself, for example into equal parts (a common choice, not something HarfBuzz does).

The cluster level decides how coarse all this is. At the default, level 0, a mark joins the cluster of its base before shaping starts, so a cursor can never land between them. At level 1, which the header recommends for new programs, marks keep clusters of their own where the order allows it. Levels 2 and 3 give finer clusters that can be out of order, which this chapter’s arithmetic doesn’t handle. All four are compared in [Buffers](buffers.html#the-four-cluster-levels). Whichever level is used, grapheme boundaries for cursor movement are the application’s business: HarfBuzz’s notion of a grapheme is only “similar to” Unicode’s, as the header puts it.

## What the glyph flags promise

| Flag | `hb-shape` | What its presence on a glyph means |
|---|---|---|
| `UNSAFE_TO_BREAK` | `#1` | cutting the text at the start of this glyph’s cluster and shaping the two sides separately might give a different result |
| `UNSAFE_TO_CONCAT` | `#2` | changing the text on one side of the start of this cluster might change the result on the other |
| `SAFE_TO_INSERT_TATWEEL` | `#4` | a U+0640 TATWEEL can be inserted before this cluster without disturbing the shaping |

The definitions are the header’s (`hb-buffer.h:76`–`153`), and they are worded with care. The unsafe flags are promises by their absence. A glyph *without* `UNSAFE_TO_BREAK` is a place where the run can be cut and the two halves are already what shaping them separately would give. A glyph *with* it is only a warning: the result might change, and often won’t. Every flag is about the boundary at the *start* of its glyph’s cluster, and after shaping every glyph of a cluster carries the same flags (`hb_propagate_flags`, `hb-ot-shape.cc:1109`), so any of them can be read. There is no flag for the end of the text, which matters below.

`UNSAFE_TO_CONCAT` is the weaker condition, and implies nothing on its own: “the absence of this flag will NOT by itself mean that it IS safe to concat text. Only two pieces of text both of which clear of this flag can be concatenated safely.” Unsafe to break always implies unsafe to concat, since `unsafe_to_break` sets both (`hb-buffer.hh:506`). Unsafe to concat costs more to work out, because it has to be recorded where a lookup *failed* to match, so it is only made when the buffer has `HB_BUFFER_FLAG_PRODUCE_UNSAFE_TO_CONCAT` (`:526`), and otherwise cleared at the end. Without that flag, a `#2` can’t be trusted either way. The tatweel flag likewise needs `HB_BUFFER_FLAG_PRODUCE_SAFE_TO_INSERT_TATWEEL`.

Here is a paragraph with both unsafe flags asked for:

```shape
apps.ttf  a fine non-Toxic office  --language=en  --show-flags
apps.ttf  a fine non-Toxic office  --language=en  --show-flags  --unsafe-to-concat
```

The kerning pairs leave the only marks. The hyphen is kerned against the *T* (its advance is 200, not 300), so the *T* is unsafe to break; the *T* is kerned against the *o*, so the *o* is too. The hyphen itself is clear, because a pair marks only its interior: breaking *before* the hyphen would not separate the pair. Every other boundary in the paragraph is safe. The ligatures leave nothing to see, since each is a single cluster with no boundary inside it.

Not every backend is this precise. The Core Text, DirectWrite, Uniscribe, Graphite, `kbts` and `wasm` backends mark the whole buffer unsafe to break ([hb_shape and its backends](hb_shape-and-its-backends.html)). The `ot` shaper’s AAT paths mark the whole buffer unsafe to concat: `morx` (`hb-aat-layout-morx-table.hh:1465`, shown in [AAT inside HarfBuzz](aat-inside-harfbuzz.html#clusters-and-safe-breaking)), `kerx` (`hb-aat-layout-kerx-table.hh:1058`), and the machine that applies the legacy `kern` table (`hb-kern.hh:54`):

```shape
aat-positioning/kerx.ttf  AVTo  --language=en  --show-flags  --unsafe-to-concat
```

Unsafe to break is still set pair by pair there, so line breaking keeps its shortcut; only the finer reshaping described next loses it.

## Breaking lines

HarfBuzz doesn’t find break opportunities. They come from the Unicode line-breaking algorithm, through ICU or another library, and hyphenation points from a dictionary. What the flags make cheap is measuring. The approach the header describes is to shape the whole paragraph once, find where the lines would break using the advances, and then cut the glyph row at those places. A cut where the glyph after it is clear of `UNSAFE_TO_BREAK` is final: both sides are exactly what shaping them separately would give.

In the paragraph above, a break before *office* is like that. The *o* at cluster 17 has no flags, and shaped on its own the second line is identical, apart from the clusters, which `hb-shape` counts from the start of its own text:

```shape
apps.ttf  office  --language=en  --show-flags
```

A break after the hyphen, before *Toxic*, falls on the *T*, which is unsafe to break. Shaped separately, the first line is wider, because its hyphen has no *T* to kern against:

```shape
apps.ttf  a fine non-  --language=en
apps.ttf  Toxic office  --language=en
```

The hyphen is 300 units wide, not 200, so the line is 4,350 units long rather than the 4,250 the paragraph’s glyphs add up to. A line breaker that summed the paragraph’s advances would have fitted the line 100 units too tightly. When the cut is flagged, the lines on both sides have to be shaped again. The simple way is to shape each such line whole, with the rest of the paragraph as context (below).

### Reshaping only near the break

Shaping a whole line again is more than is needed. The documentation of `UNSAFE_TO_CONCAT` (`hb-buffer.h:90`–`143`) gives a cheaper method, which works even for breaks that change the text, such as an added hyphen. For the end of the line:

1. From the break, go back to the first cluster start that is *not* unsafe to concat.
2. Shape the text from there to the end of the line.
3. If the first glyph of that result is also clear of unsafe to concat, splice it in place of the old glyphs. If not, go back to the next clear cluster start and try again.

The start of the next line is the same, forwards: go forward from the break to the first clear cluster start, shape the text from the break up to there, and check that the result is clear at its end. Here the method runs into the gap in the flags: there is no glyph for the end of a text, so nothing can say whether the end is clear. The header’s remedy is to shape a little more text than needed and look for the flag inside it.

In the paragraph, the break is before the *T* (cluster 11), which is unsafe to concat; the hyphen before it (cluster 10) is clear. So the end of the first line starts with the hyphen. But shaped alone, a hyphen at the end of a text is itself unsafe to concat, because the kerning lookup looked for a glyph after it and found none; with the *n* before it, the result starts clear:

```shape
apps.ttf  n-  --language=en  --show-flags  --unsafe-to-concat
apps.ttf  Tox  --language=en  --show-flags  --unsafe-to-concat
```

So the first line is the paragraph’s glyphs up to the second *n*, then *n* and the 300-unit hyphen from the new result. The second line starts at the *T*; going forward, the first clear cluster start is the *x* (cluster 13), so *To* is shaped again (here, *Tox*, to see past its end) and spliced in front of the rest of the paragraph’s glyphs. Only three short pieces of text were shaped twice.

### Breaks inside a cluster

A hyphenation point can fall where the paragraph has no glyph boundary at all. *Office* hyphenates as *of-fice*, between the two *f*s of the *ffi* ligature. No flag can help, since the break is inside cluster 1; the application has to shape both pieces, and the method above finds how much:

```shape
apps.ttf  of-  --language=en
apps.ttf  fice  --language=en
```

The ligature splits into an *f* on one line and an *fi* on the next. The flags exist to make this kind of change cheap, and the header names hyphenation as one of the cases unsafe to concat is for.

## Checking the flags

`HB_BUFFER_FLAG_VERIFY` (`hb-shape --verify`) makes `hb_shape_full` test its own flags by doing what a line breaker would: it cuts the text at every boundary not marked unsafe to break, shapes each piece, and compares the pieces joined with the whole; and, if unsafe-to-concat flags were asked for, it shapes alternate pieces as two texts and interleaves them (`hb-buffer-verify.cc:89`, `:200`). The details are in [Buffers](buffers.html#verification). For the paragraph above, both tests pass:

```shape
apps.ttf  a fine non-Toxic office  --language=en  --verify  --unsafe-to-concat
```

Two things about the test matter to an application. The pieces are cut from the text with `hb_buffer_append`, which since 2.9.1 copies the neighboring characters as pre- and post-context (`hb-buffer.cc:2139`–`2154`). So the promise that is checked is about pieces shaped *with* their context, and an application should supply it too. And all three checks are skipped at cluster levels 2 and 3 (`hb-buffer-verify.cc:65`), so flags made at those levels are never tested, and [one of the ways flags are set at level 3](buffers.html#the-four-cluster-levels) treats it as ordered when it isn’t.

`--verify` doesn’t fail for the examples in most chapters of this book, but it does for some, and each failure is a break the flags call safe that isn’t. Run over every `shape` example in the book, it fails on three kinds of text. The book’s build stops when `hb-shape` fails, so the failures are shown here by shaping the pieces by hand.

The USE shaper gives a Devanagari syllable `init` when it starts a word, and doesn’t count a space as the end of one ([The Universal Shaping Engine](the-universal-shaping-engine.html#topographical-forms)): the first vowel sign below is initial in the whole text, but not when the text is cut at the space, which carries no flag:

```shape
the-universal-shaping-engine/deva3.ttf  क\u093F क  --language=hi  --show-flags
the-universal-shaping-engine/deva3.ttf  क\u093F  --language=hi
```

Cross-stream kerning in a legacy `kern` table (or `kerx`) raises every glyph after a pair, but marks only the pair. Cut before the second *A*, which is unflagged, and the *A T* come down to the baseline:

```shape
legacy-kern/cross.ttf  AVAT  --language=en  --show-flags
legacy-kern/cross.ttf  AT  --language=en
```

And the Hangul shaper, at cluster level 1, splits a precomposed syllable into jamo to add a trailing consonant that follows it, and leaves the trailing consonant in its own cluster with no flag (`hb-ot-shaper-hangul.cc:385`), though apart the two are a syllable glyph and a separate jamo:

```shape
hebrew-thai-lao-and-hangul/hangul.ttf  가\u11EB  --language=ko  --cluster-level=1  --show-flags
hebrew-thai-lao-and-hangul/hangul.ttf  가  --language=ko  --cluster-level=1
```

Each of these looks like a HarfBuzz bug. For an application, they mean the flags are as good as the code that sets them, and `--verify` is how to find out for a given font and text.

## Context at the edges of a run

The run handed to HarfBuzz is rarely a whole paragraph, and the characters around it can matter. `hb_buffer_add_utf8` and its siblings take the whole string with an `item_offset` and `item_length`, and keep up to five characters on either side as pre- and post-context (`hb_buffer_add_utf`, `hb-buffer.cc:1868`). The pre-context is taken only while the buffer is empty and the offset is greater than 0 (`:1903`), so it can come from a separate first call with a length of 0, which is how `hb-shape --text-before` supplies it (`util/shape-options.hh:117`). `hb_buffer_clear_contents` forgets both. The clusters are offsets into the whole string, which keeps them meaningful to the application.

In {{hb}}, the context is read in only two places in the `ot` shaper: the Arabic joining machine, which starts from the pre-context and ends with the post-context (`hb-ot-shaper-arabic.cc:309`, `:358`), and the test for a dotted circle at the start of a paragraph (`hb-ot-shape.cc:558`). The `harfrust` backend passes it on. Lookups never see it. So context makes a run split inside an Arabic word join as though it were whole, but it can’t make a ligature, or a kerning pair, across the split:

```shape
apps.ttf  بب  --show-flags  --unsafe-to-concat
apps.ttf  بب  --show-flags  --unsafe-to-concat  --text-before=ب
apps.ttf  i  --language=en  --text-before=f
```

With a beh before it as context, the first beh of the run takes its medial form. The *i* after an *f* stays an *i*. An application that splits runs only to change color or underline, within one font, loses ligatures and kerning at every split. Splitting only where the font or the segment properties change, and coloring by cluster afterward, avoids it, with the caveat that a ligature’s cluster can’t be colored in part.

## Reshaping after an edit

Editing is the same problem as breaking, run the other way: the text either side of the change stays, and the question is how much of its shaping can be kept. With unsafe-to-concat flags, the old result says where the changed text could reach:

```shape
apps.ttf  of ice  --language=en  --show-flags  --unsafe-to-concat
apps.ttf  of  --language=en  --show-flags  --unsafe-to-concat
apps.ttf  offi  --language=en  --show-flags  --unsafe-to-concat
```

The *f* and the space are both unsafe to concat: the ligature lookup tried to match at the *f* and found a space where an *i* would have made a ligature. Deleting the space touches that region, so the application reshapes from the last clear cluster start before the change, the *o*, to the first clear one after it, the *i*. Shaped alone, *of* would end unsafe to concat, its *f* still looking for a partner, so the piece is extended to the next clear start, the *c*, and *offi* is shaped instead. It comes out as *o* and *ffi*, clear at both ends, and the *ce* of the old result is kept. Without the flag, the same edit would need the whole run reshaped, or a guess.

Reshaping is cheap in another way as well: the plan is cached, so shaping a few characters again costs the lookups and not the planning, as long as the features and segment properties are the same each time ([Shape plans and their cache](shape-plans-and-their-cache.html#for-applications)).

## Runs the application must find

HarfBuzz doesn’t itemize. Before it is called, the application splits each paragraph into runs of one script, one direction, one language and one font, with one set of features. The directions come from the Unicode bidirectional algorithm, the scripts from Unicode’s script property with the application’s own rules for characters such as spaces, digits and punctuation that belong to no one script, the languages from the document’s markup or settings ([Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told)), and the fonts from its own fallback, when the chosen font lacks a character.

`hb_buffer_guess_segment_properties` (`hb-buffer.cc:746`) is not an itemizer. It looks for the first character whose script isn’t Common, Inherited or Unknown, takes the direction from that script, and the language from the locale ([Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told)). Given mixed text, it calls the whole run by the first script it sees:

```shape
apps.ttf  a بب  --language=ar
apps.ttf  a بب  --language=ar  --script=arab  --direction=rtl
```

Guessed as Latin, the behs neither join nor run right to left. Called Arabic, they join, and the *a* is put in right-to-left order with them, which is just as wrong: the *a* belongs in a run of its own.

Font fallback works from the output. A character the font lacks comes out as glyph 0, `.notdef`, in its own cluster (or the buffer’s `not_found` glyph, if one is set), and the application can shape that cluster again with another font. HarfBuzz first tries the character’s decomposition, and keeps it whole when that doesn’t help, so the *é* here, whose acute the font lacks, is one `.notdef`:

```shape
apps.ttf  café  --language=en
```

An application can also ask before shaping, with `hb_font_get_nominal_glyph`. Whole clusters, not single characters, are what should move to another font, so that a mark stays with its base.

## Justification

HarfBuzz has no justifier. It measures the run and leaves the spacing of lines to the application. Two things in it are made for justification.

The tatweel flag marks where an Arabic word can be lengthened with U+0640 TATWEEL without changing how it joins. The Arabic joining machine sets it at every join (`hb-ot-shaper-arabic.cc:335`); the header is careful to say that it “does not determine the script-specific elongation places”, only where elongation won’t interrupt shaping. Choosing among the flagged places, by the rules of the script and the taste of the typography, is still the application’s job. A flagged cluster is always unsafe to break as well, and a cluster unsafe to break for another reason loses the flag (`hb-ot-shape.cc:1145`):

```shape
apps.ttf  ببب  --show-flags  --safe-to-insert-tatweel
apps.ttf  ب\u0640بب  --show-flags  --safe-to-insert-tatweel
```

Both the medial and final behs (clusters 1 and 2) are `#5`, unsafe to break and safe for a tatweel. With a tatweel inserted before the middle one, the forms are the same and the word is 300 units wider. The text has changed, so the word has to be shaped again, and its clusters move along by one; an application that wants clusters to keep pointing into its own text can add the tatweel with `hb_buffer_add` and the cluster of the character it was inserted before (inferred from how clusters work, not tried here).

The other is `hb_shape_justify` (`hb-shape.cc:255`, new in 7.1.0), which shapes a run again and again at different settings of a font’s `jstf` axis, or failing that `wdth`, until its advance falls between two targets. It is still experimental: it exists only in a build with `-Dexperimental_api=true`, and with it `hb-shape --justify-to`. This book’s build is not one. Syriac’s `stch`, which stretches a mark across a word, is a different thing: the font asks for it, and HarfBuzz does it while shaping ([Joining scripts](joining-scripts.html#stretching-stch)).

## Pitfalls

**Feature ranges are in cluster units.** `hb_feature_t`’s `start` and `end` are compared with cluster values, not glyph or character indices (`set_masks`, `hb-buffer.cc:539`). An application that adds text from a larger string has clusters in that string’s code units, counting from its start, and its ranges have to be in the same units. A range that cuts through a ligature changes which ligature forms, since every component needs the feature:

```shape
apps.ttf  office  --language=en  --features=-liga[3]
apps.ttf  office  --language=en  --features=-liga[2]
```

With *liga* off for the *i* only, *ff* still forms; off for the second *f*, neither does.

**Clusters merge more than expected.** At the monotone levels, anything that reorders merges everything it passes over: an Indic syllable whose vowel sign moves in front of a conjunct becomes one cluster, and a cursor can’t go inside it ([Buffers](buffers.html#the-four-cluster-levels)). A mark at level 0 is in its base’s cluster before shaping starts. An application that needs finer clusters has to choose a level that gives them and handle what comes with it.

**Glyph order is visual.** In right-to-left runs, the first glyph is the rightmost, and its cluster is the highest.

**Flags depend on the backend.** Everything except the `ot` shaper’s OpenType path marks either the whole run unsafe to break or the whole run unsafe to concat, as listed above.

**`BOT` and `EOT`.** Setting both on every run of a paragraph is safe, since HarfBuzz ignores `BOT` when there is pre-context ([Buffers](buffers.html#buffer-flags)).

**Failure is quiet.** `hb_shape` returns nothing, and `hb_shape_full` returns true even when the buffer ran out of memory or of its operation budget; `hb_buffer_allocation_successful` is the test ([hb_shape and its backends](hb_shape-and-its-backends.html#running-the-plan-and-failing)).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-buffer.h` | the glyph flags and their documentation, including the reshaping method; the buffer flags; the cluster levels |
| `src/hb-buffer.hh` | `unsafe_to_break`, `unsafe_to_concat`, `safe_to_insert_tatweel` and `_set_glyph_flags` |
| `src/hb-buffer.cc` | `hb_buffer_add_utf` and its context, `hb_buffer_append`, `guess_segment_properties`, `set_masks` |
| `src/hb-buffer-verify.cc` | the three checks behind `HB_BUFFER_FLAG_VERIFY` |
| `src/hb-ot-shape.cc` | `hb_propagate_flags` |
| `src/hb-ot-shaper-arabic.cc` | the joining machine: the only reader of context, and the tatweel flag |
| `src/hb-ot-layout.cc` | `hb_ot_layout_get_ligature_carets` |
| `src/hb-shape.cc` | `hb_shape_full`, and the experimental `hb_shape_justify` |
| `docs/usermanual-clusters.xml`, `docs/usermanual-what-is-harfbuzz.xml` | the manual on clusters, and on what HarfBuzz leaves to applications |

## In short

* A glyph’s cluster is the offset of the first character it came from; a cluster covers the characters up to the next cluster value. Cursors go between clusters, or inside a ligature at GDEF’s carets.
* No `UNSAFE_TO_BREAK` on a glyph means the run can be cut at the start of its cluster with nothing reshaped. No `UNSAFE_TO_CONCAT` on both pieces means they can be joined; it must be asked for with `HB_BUFFER_FLAG_PRODUCE_UNSAFE_TO_CONCAT`.
* A line breaker shapes the paragraph once, cuts where the flags allow, and reshapes only around flagged breaks, or as little as the unsafe-to-concat method needs. A break inside a cluster always needs reshaping.
* `--verify` checks the flags by reshaping. A few shapers and tables in {{hb}} set them too optimistically.
* Context, given through the `item_offset` of the add functions, reaches only Arabic joining and the dotted-circle test, never lookups.
* Itemization, font fallback, line breaking and justification are the application’s; HarfBuzz offers the tatweel flag, and an experimental justifier that uses variation axes.
