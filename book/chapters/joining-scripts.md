# Joining scripts

In a joining script, a letter’s shape depends on whether it connects to its neighbors. [Why shaping exists](why-shaping-exists.html#one-character-many-shapes-joining-and-contextual-forms) showed beh taking four forms, and [The pipeline, step by step](the-pipeline-step-by-step.html#masks) showed where the decision is made: in the Arabic shaper’s `setup_masks` hook, before any glyph exists, a state machine reads each character’s joining type and sets one feature bit in its mask. This chapter takes that machine apart, then covers the rest of the Arabic shaper: its feature order, Syriac Alaph, mark reordering, `stch`, and shaping from presentation forms when a font has no Arabic `GSUB`.

Only Arabic and Syriac get the Arabic shaper ([Choosing a script shaper](choosing-a-script-shaper.html#arabic-and-syriac)). Mongolian, N’Ko and the other joining scripts go to the Universal Shaping Engine, which borrows the same state machine; the last section is about that.

The test fonts are built by `fonts/joining-scripts/build-fonts.py`: `joining.ttf` (from `joining.fea`) has Arabic, Syriac and Mongolian letters in their joining forms, `presentation.ttf` has no layout tables, only presentation-form glyphs, and `stch.ttf` has Syriac letters and an abbreviation mark. Every result was produced by HarfBuzz {{hb}} when the page was built.

## Joining types

Each character has a **joining type**, from Unicode’s `ArabicShaping.txt`: **dual-joining** (D) letters join on both sides, **right-joining** (R) letters only to the letter before them, **left-joining** (L) letters only to the letter after, **join-causing** (C) characters such as the tatweel and ZWJ make their neighbors join without having forms of their own, **non-joining** (U) characters join nothing, and **transparent** (T) characters, mostly marks, are passed over as though they weren’t there. “Right” and “left” are named for right-to-left text: an R letter joins the letter before it in logical order.

`gen-arabic-table.py` packs the file into a table with eight values (`hb-ot-shaper-arabic.cc:73`):

```c++
enum hb_arabic_joining_type_t {
  JOINING_TYPE_U            = 0,
  JOINING_TYPE_L            = 1,
  JOINING_TYPE_R            = 2,
  JOINING_TYPE_D            = 3,
  JOINING_TYPE_C            = JOINING_TYPE_D,
  JOINING_GROUP_ALAPH       = 4,
  JOINING_GROUP_DALATH_RISH = 5,
  NUM_STATE_MACHINE_COLS    = 6,

  JOINING_TYPE_T = 6,
  JOINING_TYPE_X = 7  /* means: use general-category to choose between U or T. */
};
```

Three things in it differ from the file. C is folded into D: for the machine, a join-causing character is a letter that joins both ways and has no forms. Two Syriac joining groups replace the joining type of their letters: Alaph, and Dalath and Rish, are R letters with special behavior, so the generator writes their group instead (`gen-arabic-table.py`, `print_joining_table`). And characters the file doesn’t list get X, which `get_joining_type` (`:89`) turns at run time into T for non-spacing and enclosing marks and format characters, and into U for everything else.

The table was made from `ArabicShaping-18.0.0.txt` and covers every script that file covers, which is how the same code serves the joining scripts under USE. The generator also reads `Blocks.txt`, but nothing it prints uses it (read from the code).

## The joining state machine

`arabic_joining` (`:302`) walks the buffer once, in logical order. Its state says what the last non-transparent character was and whether it is willing to join the next one. Each step looks up the current state and the current character’s column, and gets three things: an action for the *previous* character, an action for this one, and the next state. Here is the table, without its blank lines (`:140`):

```c++
/*   jt_U,          jt_L,          jt_R,          jt_D,          jg_ALAPH,      jg_DALATH_RISH */

/* State 0: prev was U, not willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {NONE,ISOL,1}, {NONE,ISOL,2}, {NONE,ISOL,1}, {NONE,ISOL,6}, },
/* State 1: prev was R or ISOL/ALAPH, not willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {NONE,ISOL,1}, {NONE,ISOL,2}, {NONE,FIN2,5}, {NONE,ISOL,6}, },
/* State 2: prev was D/L in ISOL form, willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {INIT,FINA,1}, {INIT,FINA,3}, {INIT,FINA,4}, {INIT,FINA,6}, },
/* State 3: prev was D in FINA form, willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {MEDI,FINA,1}, {MEDI,FINA,3}, {MEDI,FINA,4}, {MEDI,FINA,6}, },
/* State 4: prev was FINA ALAPH, not willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {MED2,ISOL,1}, {MED2,ISOL,2}, {MED2,FIN2,5}, {MED2,ISOL,6}, },
/* State 5: prev was FIN2/FIN3 ALAPH, not willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {ISOL,ISOL,1}, {ISOL,ISOL,2}, {ISOL,FIN2,5}, {ISOL,ISOL,6}, },
/* State 6: prev was DALATH/RISH, not willing to join. */
{ {NONE,NONE,0}, {NONE,ISOL,2}, {NONE,ISOL,1}, {NONE,ISOL,2}, {NONE,FIN3,5}, {NONE,ISOL,6}, }
```

Every joining letter starts out isolated, because nothing is known yet about the letter after it. The previous-letter action is how that is corrected. A D letter in state 0 is ISOL and moves to state 2, “willing to join”. If an R or D letter follows, the entry in state 2 says INIT for the previous letter and FINA for this one: the first letter is changed after the fact. A D letter after that moves to state 3, and the next joining letter turns it from FINA into MEDI. An R letter in states 2 or 3 is final and goes to state 1, where nothing joins it from the left. A U character goes back to state 0 and touches nothing. An L letter is always ISOL itself, since it can’t join backwards, and goes to state 2, so the letter after it can make it INIT. States 4 to 6 are for Alaph, in the next section.

```shape
joining.ttf  ببب  --language=ar
joining.ttf  بابب  --language=ar
joining.ttf  ببءب  --language=ar
joining.ttf  بـب  --language=ar
joining.ttf  ب\u064Eب  --language=ar
```

Read each result from the right. Alef, an R letter, ends the first word, so the beh after it starts again as initial. Hamza (U) breaks the chain: the beh before it is final, the one after isolated. The tatweel (C) joins its neighbors like a letter. The fatha (T) is skipped, so the behs on either side of it join.

The actions are stored in a byte of each glyph’s scratch space, `arabic_shaping_action()` ([Buffers](buffers.html#eight-bytes-of-scratch-space)). A transparent character gets NONE (`:326`), and is otherwise skipped: neither `prev` nor the state changes. Then `setup_masks_arabic_plan` (`:391`) ORs each glyph’s mask with `mask_array[action]`, the one-bit mask of the feature of the same number. `mask_array[NONE]` is zero, so marks and non-joining characters get no joining feature at all.

### The ends of the text

Before the first character, the machine reads the buffer’s pre-context, the text before the item ([Buffers](buffers.html#adding-text)). It skips transparent characters and lets the first other one set the starting state, with no actions, since that character isn’t in the buffer (`:308`). After the last character it does the same with the post-context, and here the previous-letter action is applied: a letter at the end of the buffer becomes initial or medial if the text after it joins. So a word split across two shaping calls gets the forms it would have had in one.

### Joiners

ZWJ is a C character and ZWNJ a U character, so they need no special case:

```shape
joining.ttf  ب\u200D  --language=ar
joining.ttf  \u200Dب  --language=ar
joining.ttf  ب\u200Cب  --language=ar
```

A beh before a ZWJ is initial and after one final; with a ZWNJ between them two behs stay isolated. That ZWJ also blocks Arabic *ligatures* is the flag `F_MANUAL_ZWJ` ([From features to lookups](from-features-to-lookups.html#the-flags)), not the machine.

The machine also sets glyph flags ([Buffers](buffers.html#glyph-flags)): `safe_to_insert_tatweel` wherever a previous-letter action joins two letters (`:335`), and unsafe-to-concat wherever a later character could still have changed an earlier one’s form (`:342`–`:348`, `:373`).

## Syriac and Alaph

Syriac has more forms than Arabic. Alaph, an R letter, has five: isolated, final when it joins the letter before it, and three more, each with a feature of its own: `fin2`, `fin3` and `med2`. In HarfBuzz’s table, an Alaph is:

* **final** (`fina`) after a letter that joins it, in states 2 and 3;
* **`fin2`** at the end of a word after a letter that doesn’t join it, in state 1 (after an R letter or an isolated Alaph) or state 5;
* **`fin3`** after Dalath or Rish, in state 6;
* **`med2`**, when it was final and another letter follows: state 4 changes the previous Alaph from FINA to MED2;
* **isolated** otherwise, and also when a `fin2` or `fin3` Alaph is followed by another letter: state 5 changes it back to ISOL.

```shape
joining.ttf  ܐ  --language=syr
joining.ttf  ܒܐ  --language=syr
joining.ttf  ܒܐܒ  --language=syr
joining.ttf  ܘܐ  --language=syr
joining.ttf  ܕܐ  --language=syr
joining.ttf  ܕܐܒ  --language=syr
joining.ttf  ܒܐܐ  --language=syr
```

Beth (D) joins the Alaph after it, which is final; with another beth after that, the Alaph is `med2` and the second beth is isolated, since Alaph never joins forwards. After waw, an ordinary R letter, it is `fin2`; after dalath, `fin3`; and that `fin3` turns back to isolated when beth follows. In the last line the second Alaph is `fin2`, after an Alaph, and the first is `med2`.

`FEATURE_IS_SYRIAC` (`:102`) recognizes the three by the digit at the end of their tags: they are the joining features with no fallback.

## The features, in order

`collect_features_arabic` (`:187`) asks for the shaper’s features, separated by pauses. In order:

| Stage | Features | Pause function at its end |
|---|---|---|
| | `stch` (with the common `rtla`, `rtlm`, `frac`, `numr`, `dnom`, `rand`, `Harf`) | `record_stch` |
| | `ccmp`, `locl` | |
| one each | `isol`, `fina`, `fin2`, `fin3`, `medi`, `med2`, `init` | |
| (empty) | | `deallocate_buffer_var` |
| | `rlig` | `arabic_fallback_shape`, for Arabic only |
| | `calt` | none if the font has `rclt` |
| | `liga`, `clig`, `mset`, then `Buzz` and the common and horizontal features | |

The joining features are added with `add_feature`, not `enable_feature`: none is on globally, and each glyph gets the bit of at most one. All but `stch` have `F_MANUAL_ZWJ`. `cswh` is no longer on, because Windows 8 and later don’t turn it on (`:244`); `mset` is.

Why so many stages? The comment at `:192` gives the reasons. The pause between the joining features and `rlig` is required: `rlig` must see the joining forms, because lam-alef is a ligature of an *initial or medial* lam and a *final* alef (the bug it cites is Mozilla’s 644184). The pauses between the joining features themselves “are not necessarily needed as only one of those features is applied to any character”; they make a difference only to contextual lookups, which see the forms of earlier features but not of later ones, and HarfBuzz follows the order of the specification, as giving “better experience if that’s what Uniscribe is doing”. [From features to lookups](from-features-to-lookups.html#harf-and-buzz-seen-through-the-arabic-shapers-stages) shows these stages running.

The pause between `rlig` and `calt` is for Arabic script only. Uniscribe was found to have it for Arabic, since without it the IranNastaliq font’s ALLAH ligature doesn’t form, and found not to have it for Mongolian (then shaped by this shaper). Syriac, the one other script here, therefore runs `rlig` and `calt` together. In `joining.ttf`, `calt` is lookup 0 and turns a ligature that `rlig`, lookup 8, makes into an alternate:

```shape
joining.ttf  لا  --language=ar
joining.ttf  ܠܐ  --language=syr
```

The Arabic lam-alef reaches `calt` and is changed. The Syriac lamadh-alaph is made in the same stage as `calt`, after `calt`’s lookup has run, and stays as it is.

The pause after `calt` (issue 1573) is left out if the font has an `rclt` feature (`:238`): `has_feature` asks the font, not the plan.

## Reordering marks

Unicode’s canonical ordering sorts a run of marks by combining class, and [Normalization](normalization.html) explains that HarfBuzz sorts by its own modified classes. For Arabic, this puts a hamza above, class 230, after a fatha or a shadda, whose classes are in the 27–35 range. But a hamza above is part of the letter: it should be drawn next to it, under any vowel. Unicode Technical Report #53, *Unicode Arabic Mark Rendering*, names such marks **modifier combining marks** and asks for them to be moved to the front of the run. `reorder_marks_arabic` (`:721`), the shaper’s `reorder_marks` hook, does that, straight after each run has been sorted.

Its list has fourteen marks (`:692`): hamza above and below, noon ghunna, small high and low seen, small high yeh and noon, and seven from the Arabic Extended-A block. For class 220, then for 230, it finds the first mark of that class in the run. If it and those right after it are on the list, it moves them to the front of the run, merges the clusters of everything it moved past, and renumbers them. Only marks at the head of their class are moved: a hamza above after a madda, both 230, stays behind the madda (read from the code).

```trace
font: joining.ttf
text: ب\u064E\u0654
options: --language=ar
from: start reorder
to: end compose
```

The renumbering is the subtle part. The modifier marks are given modified classes 25 or 26, values HarfBuzz otherwise uses for Hebrew points (`HB_MODIFIED_COMBINING_CLASS_CCC22` and `CCC26`), which are lower than every Arabic class, so the run still looks sorted. The normalizer’s CGJ handling needs that (issue 554). The fallback mark positioner maps 25 to below and 26 to above, as it does for the Hebrew points ([Fallbacks](fallbacks.html#recategorizing-marks)).

The comment admits the cost: a mark renumbered to 26 no longer blocks a later 230 mark from composing with the base. In “alef, hamza above, madda”, the hamza should keep the madda from composing with the alef. `joining.ttf` has a glyph for U+0622 ALEF WITH MADDA ABOVE but not for U+0623 ALEF WITH HAMZA ABOVE:

```trace
font: joining.ttf
text: ا\u0654\u0653
options: --language=ar
from: start compose
to: end compose
```

The alef and the madda compose across the hamza. Canonically, that text is not equivalent to U+0622 U+0654. HarfBuzz accepts this, in the comment at `:771`, as the price of keeping the CGJ logic right.

## Stretching: `stch`

The Syriac abbreviation mark, U+070F, is a line drawn over the letters of an abbreviation, as long as they are. A font draws it with the feature `stch`, which replaces the mark with a sequence of glyphs, some of fixed length and some to be repeated; the comment above HarfBuzz’s code points to Microsoft’s Syriac script development specification for an example. HarfBuzz implements it “in a generic way, such that the Arabic subtending marks can use it as well” (`:448`), so any font can use it under the Arabic shaper. `stch.ttf` breaks the mark into an end, a repeating bar and another end:

```views
font: stch.ttf
lookup: 0
fea: stch.fea stch
cpp: Sequence
```

**Recording.** `stch` is the first of the shaper’s features, and `record_stch` (`:456`) runs right after it. It looks for every glyph that a multiple substitution has *multiplied* (a property GSUB sets, [GSUB](gsub.html#glyph-properties)), and gives it an action that the joining machine never uses: STCH_FIXED if its component number is even and STCH_REPEATING if odd (`:475`). It is the same byte as the joining action (“We abuse the same byte for other things”, `:131`), which is free again by then, since the joining masks were set before GSUB. The comment warns that `rtlm`, `frac` and the other features in the same stage could also multiply a glyph, and assumes they don’t.

**Measuring.** Nothing more happens until the very end of shaping. `apply_stch` (`:482`), run from `postprocess_glyphs`, after GPOS and in visual order, finds each run of tiles and measures the “rest of the word”: the glyphs after it in logical order whose general category is a letter other than upper-, lower- or titlecase, a mark, a number, a symbol, private use or unassigned, or which are default ignorables (`HB_ARABIC_GENERAL_CATEGORY_IS_WORD`, `:45`). Spaces and punctuation end it. The tiles’ advances are read from the font and kept in the position’s scratch field, `stch_advance()` (`:39`). Then it works out how many extra copies of the repeating tiles fill the width left after the fixed ones (`:586`). If that leaves a gap, it adds one more copy and overlaps all the copies a little to take up the excess (`:589`).

**Cutting.** A second pass makes room, copies each repeating tile that many times, sets every tile’s advance to zero, and gives each an offset, so that the tiles lie over the word without taking any space. The range is marked unsafe to break.

```shape
stch.ttf  \u070Fܒ  --language=syr
stch.ttf  \u070Fܒܒܒ  --language=syr
stch.ttf  \u070Fܒܒܒ  --language=syr  --features=-stch
```

One beth is 500 units wide. The ends are 100 each and the bar 200, so 300 is left for bars: one bar is too short and two too long, so there are two, overlapping by 100, and the tiles run from −500 to 0, exactly over the beth. Three beths get seven bars, each overlapping the next by 16 units. Integer division leaves 4 units over, so the line starts at −1504 over a word 1500 wide. Without `stch` the mark is one zero-width glyph.

The fit is not always that close. When the bars fit with no gap, no extra copy is added and the variable `w_remaining` is not set to zero, so the tiles start at half the word’s width less the ends (`:625`), not at the word’s edge. With two beths, a 1000-unit word, the line runs from −600 to 400:

```shape
stch.ttf  \u070Fܒܒ  --language=syr
```

```draw
font: stch.ttf
text: \u070Fܒܒ \u070Fܒ
```

In the drawing, the word on the right has one beth, and its line fits it. The word on the left has two, and its line is moved 400 units right, across the space and into the other word. This looks like a bug: the exact fit is the one case where the result is worse than an approximate one. When the word is narrower than the two ends and a bar, the line is also off center, by half the width left after the ends.

Two limits keep a hostile font from making the buffer huge. A run of tiles is never repeated past 256 glyphs in all (`STCH_MAX_GLYPHS`, `:572`), and the arithmetic uses 64-bit integers and saturating additions; NEWS records fixes for overflows here in 13.1.0 and 13.1.1.

## Shaping without GSUB

Older Arabic fonts often map the **presentation forms**, Unicode’s compatibility characters for each joining form of each letter (U+FB50–U+FDFF, U+FE70–U+FEFF): they have a glyph for U+FE91 ARABIC LETTER BEH INITIAL FORM but no `init` feature. HarfBuzz shapes them by synthesizing the lookups they lack. This is why Arabic gets the Arabic shaper even when the font has no Arabic script tag ([Choosing a script shaper](choosing-a-script-shaper.html#arabic-and-syriac)).

```shape
presentation.ttf  ببب  --language=ar
presentation.ttf  بلا  --language=ar
presentation.ttf  لمب  --language=ar
presentation.ttf  لمب  --language=ar  --features=-rlig
presentation.ttf  ب\u0651\u064E  --language=ar
```

Each beh becomes the glyph the font maps to its presentation form. Lam and alef become U+FEFC, the final lam-alef. Lam and meem make U+FCCC, LAM WITH MEEM INITIAL FORM, because that ligature is in HarfBuzz’s tables too, and like every ligature here it is applied as `rlig`, so turning `rlig` off is the only way to stop it. A shadda and a fatha become one mark, U+FC60.

### When

Three conditions, all decided when the plan is made. The script must be Arabic: Syriac and the others have no fallback. Each of `isol`, `fina`, `medi`, `init` and `rlig` is added with `F_HAS_FALLBACK` (`:221`, `:231`), so it keeps a mask bit even if the font doesn’t have it, and the joining machine’s actions still reach the masks. And `data_create_arabic` (`:273`) turns fallback on only if *none* of `isol`, `fina`, `medi` and `init` was found in the font’s GSUB, for the chosen script and language. One is enough to turn it off:

```shape
presentation-init.ttf  ببب  --language=ar
presentation-init.ttf  بلا  --language=ar
```

`presentation-init.ttf` is `presentation.ttf` with a GSUB whose only feature is `init`. The initial beh comes from the font; nothing else is formed, and no lam-alef is made either. A font’s own `rlig` doesn’t count: if it has one, the synthesized ligatures run after it.

### How

The lookups can only be made with a font, which the plan doesn’t have, so they are made the first time the plan is used, by `arabic_fallback_shape` (`:417`), and kept in the plan ([Shape plans and their cache](shape-plans-and-their-cache.html)). `arabic_fallback_plan_init_unicode` (`hb-ot-shaper-arabic-fallback.hh:295`) makes up to seven, in the order of `arabic_fallback_features` (`:42`):

1. Four single substitutions, for `init`, `medi`, `fina` and `isol`. Each is made from a column of `shaping_table`, which gives the four presentation forms of each character from U+0621 to U+06D3. A pair is kept if the font has a glyph for both characters, the two glyphs differ, and both IDs are below 65536 (`:72`).
2. Three ligature substitutions, all for `rlig`: three-part ligatures, such as LAM WITH MEEM WITH HAH, then two-part ones, such as lam-alef, then mark ligatures, shadda with a vowel. The first two ignore marks; the mark ligatures, of course, don’t.

They are real GSUB lookups, written into a stack buffer by the serializer, copied, and given accelerators like any font’s; an empty one is dropped. `arabic_fallback_plan_shape` (`:367`) then applies them in order, each with its feature’s mask, in the pause after the font’s `rlig`. Since they don’t come from the font’s lookup list, a trace shows their substitutions with no “start lookup” around them:

```trace
font: presentation.ttf
text: بلا
options: --language=ar
from: start table GSUB
to: end table GSUB
```

The ligature tables are in presentation forms, not in letters: lam-alef is U+FEDF U+FE8E or U+FEE0 U+FE8E, because by then the single substitutions have run. `gen-arabic-table.py` builds them from the compatibility decompositions in `UnicodeData.txt`, so that `<initial> 0644 0645` for U+FCCC becomes initial lam then medial meem. It doesn’t take all of them, only those on its `LIGATURES` list (`gen-arabic-table.py:139`). It also adds three made-up entries for Private Use code points (`:156`), LELLAH, a lam-meem-jeem, and shadda with fathatan, for the legacy fonts below. The components of a ligature must each have a *nominal* glyph in the font, or the ligature is left out (`hb-ot-shaper-arabic-fallback.hh:164`); NEWS for 15.1.0 lists a fix to wrong ligatures “when a component is missing from the font”.

> For type designers: a modern Arabic font gets none of this, as long as it has any one of the four joining features for the script and language in use. A font with presentation forms in its `cmap` but only, say, `init` in GSUB gets no other forms and no lam-alef.

### Legacy encodings

If no lookup can be synthesized, because the font has no presentation forms either, HarfBuzz tries two older conventions.

The first is a font whose glyph IDs are Windows code page 1256 byte values. `arabic_fallback_plan_init_win1256` (`:251`) checks five: alef must be glyph 199, lam 225, alef maksura 236, yeh 237 and sukun 250. If they all are, HarfBuzz uses a hand-written set of five lookups compiled into the library, in `hb-ot-shaper-arabic-win1256.hh`. That file writes its OpenType bytes with C macros, and includes itself twice: once to measure each piece and once to emit it (“First we measure, then we cut.”). It was written for Firefox (NEWS for 0.9.34, Mozilla bug 1045139) and was built only on Windows until 14.4.0. `win1256.ttf` has 256 glyphs and maps the letters to those IDs:

```shape
win1256.ttf  ببلا  --language=ar  --no-glyph-names
win1256.ttf  با  --language=ar  --no-glyph-names
```

Both behs become glyph 4: these lookups give initial and medial beh the same glyph. Lam and alef become glyph 165, which the `medi` lookup then makes 170, the final lam-alef. The final alef is glyph 0, which in such fonts was presumably a real glyph, at the unused position of the NUL byte (inferred).

The second is fonts in the legacy Simplified and Traditional Arabic encodings, which use Private Use code points. This is handled in `cmap`, not the shaper (`hb-ot-cmap-table.hh:2219`). If the `cmap` is a symbol (3,0) subtable and the `OS/2` table is version 0 with an `fsSelection` high byte of 0xB2 or 0xB3 (the Windows 3.1 “font pages” of those encodings), a character not found as it is is looked up again through a map from Unicode to the encoding’s PUA codes, made by `gen-arabic-pua.py` from `ArabicPUASimplified.txt` and `ArabicPUATraditional.txt`. FreeType’s font funcs do the same (`hb-ft.cc:450`). Presentation forms are mapped too, so fallback shaping works as for any font. `pua.ttf` maps only PUA code points:

```shape
pua.ttf  بلا  --language=ar
```

The three made-up ligatures are found by looking their PUA code points up directly, since the encoding maps no Unicode character to them.

## Joining scripts under USE

`gen-arabic-joining-list.py` writes `has_arabic_joining`, from `ArabicShaping.txt` and `Scripts.txt`: the scripts with characters whose joining type is neither T nor U. They are Adlam, Arabic, Chorasmian, Hanifi Rohingya, Mandaic, Manichaean, Mongolian, N’Ko, Old Uyghur, Phags-pa, Psalter Pahlavi, Sogdian and Syriac. All but Arabic and Syriac are shaped by the Universal Shaping Engine (NEWS for 2.8.0 records the move). For these, `data_create_use` makes an Arabic plan of its own (`hb-ot-shaper-use.cc:156`), and `setup_masks_use` first calls `setup_masks_arabic_plan` with it (`:189`): the same state machine, with the same context and joiners.

```shape
joining.ttf  ᠠᠠᠠ  --language=mn
joining.ttf  ᠠ\u180Bᠠ  --language=mn
joining.ttf  ᠠ\u202Fᠠ  --language=mn
joining-DFLT.ttf  ᠠᠠᠠ  --language=mn
```

Mongolian A takes its three forms. Mongolian is the one script the machine knows: after joining, `mongolian_variation_selectors` (`hb-ot-shaper-arabic.cc:380`) copies each character’s action onto a free variation selector, U+180B to U+180D or U+180F, after it. A variation selector is transparent, so otherwise it would get no mask, and a lookup in `init` matching the letter and the selector together, as `joining.ttf` has for FVS1, would fail at the selector. The narrow no-break space Mongolian uses before suffixes is non-joining in HarfBuzz’s data, and so the letters on either side of it are isolated. The last line is the same lookups under `DFLT` only, which sends Mongolian to the default shaper ([Choosing a script shaper](choosing-a-script-shaper.html#from-tags-to-a-shaper)): there is no joining at all.

The same machine, but less around it. USE adds only `isol`, `init`, `medi` and `fina` (`:62`), in one stage after its reordering, so they run in LookupList order, with no pause between them and nothing for `fin2`, `fin3` or `med2`. It has no `stch`, no fallback from presentation forms (`do_fallback` needs Arabic script), and no pause between `rlig` and `calt`. Scripts not on the list get USE’s own topographical forms, from syllables rather than joining types (`setup_topographical_masks`, `:232`); that, and the rest of USE, is in [The Universal Shaping Engine](the-universal-shaping-engine.html).

## Configuration

`HB_NO_OT_SHAPER_ARABIC_FALLBACK` (implied by `HB_NO_OT_SHAPE_FALLBACK`) turns off shaping from presentation forms and the PUA `cmap` maps; `HB_NO_WIN1256` only the Windows-1256 tables.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-shaper-arabic.cc` | joining types, the state machine, the features and pauses, `stch`, mark reordering |
| `src/hb-ot-shaper-arabic-table.hh` | generated: joining types, `shaping_table` and the ligature tables |
| `src/gen-arabic-table.py` | its generator, from `ArabicShaping.txt`, `UnicodeData.txt` and `Blocks.txt` |
| `src/hb-ot-shaper-arabic-fallback.hh` | lookups synthesized from presentation forms, and the Windows-1256 detection |
| `src/hb-ot-shaper-arabic-win1256.hh` | the hand-written Windows-1256 lookups |
| `src/hb-ot-shaper-arabic-pua.hh`, `src/gen-arabic-pua.py` | maps from Unicode to the legacy PUA encodings |
| `src/hb-ot-cmap-table.hh` | where those maps are used, for symbol `cmap`s |
| `src/hb-ot-shaper-arabic-joining-list.hh`, `src/gen-arabic-joining-list.py` | `has_arabic_joining`, from `ArabicShaping.txt` and `Scripts.txt` |
| `src/hb-ot-shaper-use.cc` | USE’s use of the Arabic plan, and its own topographical forms |

## In short

* Joining types come from `ArabicShaping.txt`; C is treated as D, and Syriac Alaph and Dalath-Rish have columns of their own.
* A seven-state machine walks the text once, from pre-context to post-context, skipping transparent characters and correcting each letter’s form when it sees the next. Each action sets one feature’s mask bit.
* Syriac Alaph has `fin2`, `fin3` and `med2` forms. Each joining feature has its own stage, before `rlig`; for Arabic only, `calt` is a stage after `rlig`.
* Modifier combining marks such as hamza above are moved to the front of their mark run and renumbered 25 or 26, which can let a later mark compose across them.
* `stch` turns a mark into fixed and repeating tiles, which are repeated and laid over the following word after positioning. An exact fit misplaces them.
* Arabic in a font with none of `isol`, `fina`, `medi` and `init` is shaped with lookups synthesized from the presentation forms in its `cmap`, or built-in ones for Windows-1256 fonts.
* Mongolian, N’Ko and the other joining scripts are shaped by USE with the same state machine, but only the four basic forms, in one stage, and with no fallback or `stch`.
