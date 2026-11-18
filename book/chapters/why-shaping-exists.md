# Why shaping exists

Text is stored as characters, and it is drawn as glyphs. If every character had exactly one glyph, drawing text would be a table lookup: find each character in the font’s `cmap`, draw the glyph it names, move along by the glyph’s width, repeat. For a large part of the world’s writing that model fails at once, and even in English it fails as soon as a font has an *fi* ligature. Shaping is the work that replaces that table lookup.

This chapter sets up the words the rest of the book uses for the two sides of that work, and for what connects them: characters and code points, glyphs and glyph IDs, clusters, runs, advances and offsets, script, direction, language and features. Then it shows, one by one, the ways in which characters and glyphs fail to line up. It ends with where the rules for shaping live, and with the history of the engines that run them, from Uniscribe and Apple’s ATSUI to the program this book is about.

The examples come from one small test font, `shaping.ttf`, built from `fonts/why-shaping-exists/shaping.fea`. It has a few Latin glyphs (with an *fi* ligature and a combining acute), the Arabic letters beh, lam and alef in their joining forms, and the Devanagari consonants KA and SSA with the vowel sign I and a conjunct. Its glyphs are boxes: what matters is their names, their widths, the `cmap` and the layout tables. Every shaping result on this page was produced by running HarfBuzz {{hb}} on that font when the page was built.

## Characters and code points

A **character** is the smallest unit of text that Unicode encodes: a letter, a digit, a punctuation mark, an accent, a space, a joiner. Each has a number, its **code point**, written in hexadecimal after “U+”: U+0066 is *f* (102 in decimal), and U+0628 (1576) the Arabic letter beh. Code points run from U+0000 to U+10FFFF. A string is stored in one of three encodings, UTF-8, UTF-16 or UTF-32, which spell each code point as one or more bytes, 16-bit units or 32-bit units: in UTF-8, *f* is the single byte 66 and beh the two bytes D8 A8. Unicode’s [FAQ on the encodings](https://www.unicode.org/faq/utf_bom.html) explains them, and character lookup sites list each character’s bytes. HarfBuzz accepts all three (`hb_buffer_add_utf8`, `hb_buffer_add_utf16` and `hb_buffer_add_utf32` in `hb-buffer.cc`), as well as plain arrays of code points. Whichever it is given, it decodes the text into code points as soon as it arrives. Inside HarfBuzz, a code point is an `hb_codepoint_t`, a 32-bit integer.

In strings, characters are stored in **logical order**: the order in which they are read, and normally typed. That is true whichever way the script runs on the page. The first character of an Arabic word is its rightmost letter, and it comes first in the string.

Unicode encodes characters, not their appearance. There is one code point for beh, though it has four shapes, and one for *a*, whatever the font. Unicode does say a great deal about each character: its general category (letter, mark, number…), its script, whether it is a combining mark and how strongly it binds, how it joins its neighbors, and how it decomposes into other characters. Shaping needs all of that, and HarfBuzz carries its own tables of it, covered in [Unicode inside HarfBuzz](unicode-inside-harfbuzz.html).

Unicode does also contain characters that look like glyphs: the *fi* ligature U+FB01, and hundreds of Arabic “presentation forms”, one code point for each joining form of each letter. They exist for compatibility with older character sets. Text isn’t normally written with them, and a shaping engine never needs them to produce those shapes. (HarfBuzz’s Arabic shaper does use them for something: as a fallback, when a font has no `GSUB` but does map the presentation forms in its `cmap`. That is in [Joining scripts](joining-scripts.html).)

## Glyphs and glyph IDs

A **glyph** is a shape in a font. Fonts don’t name their glyphs by character, or by anything else that shaping uses: a glyph is known by its position in the font, its **glyph ID**, a number from 0 up to the number of glyphs in the font, less one. In OpenType that is a 16-bit number, so a font has at most 65,535 glyphs, unless it uses the “beyond 64k” extensions mentioned in the [GSUB chapter](gsub.html). Glyph 0 is always `.notdef`, the glyph drawn for a character the font doesn’t have.

Glyphs can also have names, such as `f_i` or `beh.init`. Names are for people: HarfBuzz doesn’t need them to shape, and a font can leave them out. `hb-shape` ([The command-line tools](command-line-tools.html#hb-shape)) prints them when the font has them, and prints glyph IDs if asked:

```shape
shaping.ttf  a
shaping.ttf  a  --no-glyph-names
shaping.ttf  fi  --no-glyph-names
shaping.ttf  ab
```

The *a* is glyph 2 in this font. The *fi* ligature is glyph 9. The font has no *b*, so the second character becomes glyph 0.

The font’s `cmap` table maps code points to glyph IDs. The glyph it gives for a character is that character’s **nominal glyph**, and a font function, `get_nominal_glyph`, asks for it (font functions are the subject of [Fonts and font functions](fonts-and-font-functions.html)). The nominal glyph is where shaping starts, not where it ends.

## What HarfBuzz hands back

A shaped buffer is two arrays of the same length, one entry per glyph. Here are the two structs, from `hb-buffer.h:62` and `hb-buffer.h:191`, with comments left out:

```c++
typedef struct hb_glyph_info_t {
  hb_codepoint_t codepoint;
  hb_mask_t      mask;      /* private */
  uint32_t       cluster;
  hb_var_int_t   var1;      /* private */
  hb_var_int_t   var2;      /* private */
} hb_glyph_info_t;

typedef struct hb_glyph_position_t {
  hb_position_t  x_advance;
  hb_position_t  y_advance;
  hb_position_t  x_offset;
  hb_position_t  y_offset;
  hb_var_int_t   var;       /* private */
} hb_glyph_position_t;
```

The same `hb_glyph_info_t` is used on the way in and on the way out. When text is added to a buffer, `codepoint` holds a Unicode code point. Partway through shaping, HarfBuzz overwrites it with the glyph ID (`hb_ot_map_glyphs_fast`, `hb-ot-shape.cc:844`), and the buffer’s content type changes from Unicode to glyphs. The name of the field stays the same. `cluster` is set when the text is added and is the subject of a section of its own below. The private fields are HarfBuzz’s scratch space during shaping. `mask` holds the bits that say which features are on for the glyph, as the [GSUB chapter](gsub.html#the-mask) explains.

The positions are in two parts. The **advance** is how far to move the pen after drawing the glyph: along *x* for horizontal text, along *y* for vertical text. The **offset** moves the glyph from where the pen is, without moving the pen. A glyph with an advance of zero and an offset is drawn somewhere other than the pen position, and doesn’t move the next glyph along. That is how marks are placed:

```shape
shaping.ttf  e\u0301
```

The *e* is 500 units wide. The acute has an advance of 0, and an offset of −250 across and 150 up. By the time it is drawn the pen has already moved past the *e*, so the offset brings it back to the *e*’s anchor at (250, 650), where the font says marks attach. The acute’s own anchor is at (0, 500), so it is moved by 250 − 500 = −250 across and 650 − 500 = 150 up. Positions are in the font’s units here, because `hb-shape` sets the font’s scale to its units per em unless told otherwise. In an application they are in whatever units the font object was given, as [Fonts and font functions](fonts-and-font-functions.html) explains.

> For programmers: the advances and offsets are relative, not absolute. To place glyph *n*, add up the advances of glyphs 0 to *n* − 1, then add glyph *n*’s offset. Nothing in the output gives a glyph’s absolute position directly.

## Runs, and the three things HarfBuzz must be told

As the [introduction](introduction.html) says, HarfBuzz shapes a **run**: text in one font, with one script, one direction and one language. Those three are the buffer’s **segment properties** (`hb-buffer.h:211`):

```c++
typedef struct hb_segment_properties_t {
  hb_direction_t  direction;
  hb_script_t     script;
  hb_language_t   language;
  /* two private fields left out */
} hb_segment_properties_t;
```

The **script** is the writing system: Latin, Arabic, Devanagari. HarfBuzz’s `hb_script_t` values are the four-letter ISO 15924 codes (`Latn`, `Arab`, `Deva`) packed into an integer. OpenType names scripts with tags of its own, which are not always the same: the newer Devanagari tag is `dev2`, for example, and HarfBuzz translates between the two in `hb-ot-tag.cc`. The script decides which **script shaper** HarfBuzz uses, the part of HarfBuzz that knows the script’s rules, and which part of the font’s tables apply.

The **direction** is left to right, right to left, top to bottom or bottom to top. It is the direction the glyphs go on the page, and HarfBuzz returns glyphs in that order: for a right-to-left run, the first glyph in the output is the rightmost, which comes from the *last* character.

The **language** is a BCP 47 tag, such as `en`, `tr` or `ur`, built from the codes in [IANA’s language subtag registry](https://www.iana.org/assignments/language-subtag-registry). HarfBuzz maps it to an OpenType language system tag, from [OpenType’s own list](https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags) (`tr` becomes `TRK`), and the font can then use different rules for it.

HarfBuzz can’t tell the language from the text: Turkish and English are written with the same letters. The application has to say, and it usually knows from the document. In HTML, the [`lang` attribute](https://html.spec.whatwg.org/multipage/dom.html#the-lang-and-xml:lang-attributes) says what language an element’s text is in, and everything inside the element inherits it, so `<html lang="tr">` covers a whole page and `<span lang="en">` one phrase in it. Word processors and layout programs keep a language with each run of text, which they need for spelling and hyphenation as well. Failing those, there are the user’s own language settings. CSS can also name the OpenType language system itself, with [`font-language-override`](https://www.w3.org/TR/css-fonts-4/#font-language-override-prop), for when the font’s tag isn’t the one the language would map to; HarfBuzz has its own way of doing the same ([Choosing a script shaper](choosing-a-script-shaper.html#naming-the-tags-directly)).

If an application doesn’t set them, `hb_buffer_guess_segment_properties` (`hb-buffer.cc:746`) fills them in: the script from the first character that has a real script (not Common or Inherited), the direction from the script, and the language from the process’s locale, which has nothing to do with the text: on a computer set up for Turkish, English text is shaped as Turkish. `hb-shape` calls it, which is why the examples on this page don’t have to say what script they are in. Guessing is no substitute for knowing. Here the same Arabic text is shaped first as Arabic and then as if it were Latin:

```shape
shaping.ttf  ببب
shaping.ttf  ببب  --script=latn
shaping.ttf  ببب  --script=latn  --direction=rtl
```

As Arabic, the three behs take their initial, medial and final forms, and come out right to left. Called Latin, they get the default shaper, which knows nothing about joining, and are drawn left to right as three isolated letters. Setting the direction puts them in the right order, but they still don’t join: that needs the Arabic shaper, and only the script chooses it.

The language works on a smaller scale. In Turkish, the dot on the *i* tells it apart from the dotless *ı*, and an *fi* ligature that swallows the dot would turn one letter into the other. So the test font, as many real fonts do, has no *fi* ligature for Turkish:

```shape
shaping.ttf  fi
shaping.ttf  fi  --language=tr
```

Finding the runs is not HarfBuzz’s job. An application splits a paragraph where the script changes, where the bidirectional algorithm says the direction changes, and where the font changes, because a style changes or because the font lacks a character and another has to be used. What HarfBuzz can be given is a little of the text on either side of a run, its **context**, so that rules looking across the edge of the run still work. The Arabic shaper uses it to decide whether the first and last letters of a run join their neighbors (`arabic_joining`, `hb-ot-shaper-arabic.cc:302`).

## Features

A font’s layout tables are organized into **features**, each named by a four-letter tag: `liga` for standard ligatures, `kern` for kerning, `init` for initial forms, `smcp` for small capitals. A feature is a list of lookups, the actual rules. The font decides what each feature does. The shaping engine decides which features to apply, to which glyphs, and in what order.

Some features are on by default for every script, like `liga`, `kern` and `mark`. Some are part of a script’s shaping and are applied by its shaper to particular glyphs only, like Arabic’s `init`, `medi` and `fina`. Others are off unless an application asks for them, like `smcp`, or the stylistic alternates the GSUB chapter showed. An application asks with an `hb_feature_t` (`hb-common.h:437`):

```c++
typedef struct hb_feature_t {
  hb_tag_t      tag;
  uint32_t      value;
  unsigned int  start;
  unsigned int  end;
} hb_feature_t;
```

The value is usually 1 (on) or 0 (off). `start` and `end` limit the feature to part of the buffer. `hb-shape` takes the same thing as a string:

```shape
shaping.ttf  fi
shaping.ttf  fi  --features=-liga
```

How a list of features turns into a list of lookups, and in what order those run, is the subject of [From features to lookups](from-features-to-lookups.html).

## Where one-to-one breaks

With those words in hand, here are the ways in which characters and glyphs fail to correspond. Each is shown in the test font.

### Many characters, one glyph: ligatures

The plainest case. Two characters, *f* and *i*, become one glyph:

```shape
shaping.ttf  fi
```

The ligature has cluster 0: it came from the text starting at character 0. Nothing in the output has cluster 1, because the *i* no longer has a glyph of its own. In Latin text this is a refinement, and the text reads the same with `liga` off. In other scripts some ligatures are compulsory. Arabic lam followed by alef must become the lam-alef ligature, and fonts put it in the `rlig` (“required ligatures”) feature:

```shape
shaping.ttf  لا
```

### One character, many shapes: joining and contextual forms

The shape of an Arabic letter depends on whether it joins the letter before it, the letter after it, both or neither. Beh joins on both sides, and has four forms:

```shape
shaping.ttf  ب
shaping.ttf  بب
shaping.ttf  ببب
```

Each character still has one glyph and one cluster, but which glyph depends on its neighbors. Read the clusters to see the right-to-left order: the first glyph printed has the highest cluster number, so it is the last letter of the word.

The font can’t work this out alone. Its `fina` lookup in this font says only “replace beh with beh.fina”, which would change every beh in the text. What makes it change only the last one is the Arabic shaper. Before any lookup runs, `arabic_joining` walks through the text with a state machine driven by each character’s Unicode joining type (dual-joining, right-joining, transparent, non-joining), and records for each letter which of the forms it takes. `setup_masks_arabic_plan` (`:391`) then sets that form’s feature bit in the letter’s mask. Each of the features then runs as its own stage, and touches only the glyphs whose masks have its bit (`collect_features_arabic`, `hb-ot-shaper-arabic.cc:186`). The trace shows each lookup changing one glyph:

```trace
font: shaping.ttf
text: ببب
from: start table GSUB
to: end table GSUB
```

The buffer is still in logical order during GSUB. HarfBuzz reverses it into visual order only near the end of shaping, which is why the trace and the result above run in opposite directions.

Arabic is the clearest case, but not the only one. Syriac, N’Ko, Mongolian and many other scripts join, and a Latin font can use contextual alternates (`calt`) for the same kind of effect, as the [GSUB chapter](gsub.html#an-input-buffer-and-an-output-buffer) showed.

### Order on the page, order in the text: reordering

In Devanagari, the vowel sign I (U+093F) is written *after* the consonant it follows in speech, and drawn *before* it:

```shape
shaping.ttf  कि
shaping.ttf  क्षि
```

In the first line, KA then I becomes the glyph for I then the glyph for KA. In the second, KA, virama and SSA form the conjunct K.SSA, and the I goes before the whole conjunct. Both glyphs in each line have cluster 0: once glyphs have been reordered, the only honest thing to say is that they all came from the whole syllable.

Again the font doesn’t do the moving. The Indic shaper finds the syllables, works out which consonant is the base, and moves the vowel sign before it, all before the font’s lookups run, then adjusts its position again after the basic features have formed conjuncts and half forms (`initial_reordering_consonant_syllable`, `hb-ot-shaper-indic.cc:463`, and `final_reordering_syllable_indic`, `:999`):

```trace
font: shaping.ttf
text: कि
from: start table GSUB
to: end table GSUB
```

The reordering appears in the trace as two steps of its own, “reordering indic initial” and “reordering indic final”, which run between stages of lookups (this font’s one Devanagari lookup, `akhn`, has nothing to do here, so the trace leaves it out). How the shaper decides what is a base, and how the font’s own lookups steer that, is in [The Indic model](the-indic-model.html). The shaper is chosen by the script tag the font has as well as by the text: a Devanagari font with only `DFLT` or `latn` scripts in its `GSUB` gets the default shaper and no reordering at all, as [Choosing a script shaper](choosing-a-script-shaper.html) explains.

### Glyphs placed on other glyphs: marks

A combining mark, such as U+0301 COMBINING ACUTE ACCENT, is a character of its own that belongs on the character before it. It gets a glyph of its own, and the font’s `GPOS` table says where that glyph goes, as shown above. A font may have the accented letter as a single glyph instead, and that brings in one more mismatch.

### One character, several glyphs, or the other way round: decomposition

Unicode has two ways of writing *é*: the single character U+00E9, or *e* followed by the combining acute. They are **canonically equivalent**: they mean the same thing, and text may contain either. The test font has a glyph for *á* but none for *é*. Here are both letters, written both ways:

```shape
shaping.ttf  \u00E9
shaping.ttf  e\u0301
shaping.ttf  \u00E1
shaping.ttf  a\u0301
```

Each pair comes out the same, whichever way the text was written, and what it comes out as is decided by the font. With no *é* glyph, HarfBuzz decomposes U+00E9 into *e* and the acute, and positions the acute with `GPOS`: one character has become two glyphs, both in cluster 0. With an *á* glyph, it composes *a* and the acute into U+00E1 and uses that glyph: two characters have become one. This is HarfBuzz’s **normalization**, done against the font’s `cmap` rather than for its own sake (`_hb_ot_shape_normalize`, `hb-ot-shape-normalize.cc:280`), and it is where the `cmap` lookup actually happens. It is covered in [Normalization](normalization.html).

A font can also turn one glyph into several itself, with a multiple substitution in `GSUB`. That and the other substitution types are in the [GSUB chapter](gsub.html#multiple-substitution).

> For type designers: a font doesn’t need precomposed glyphs for every accented letter, as long as its `GPOS` can position the marks on the base letters. HarfBuzz finds whichever form the font supports. But where the font does have a precomposed glyph, that is the one used, even for text typed as base and mark.

## Clusters

Every one of those mismatches leaves a question behind: which glyphs came from which characters? An application needs the answer to put a cursor between letters, to select text, to find which character was clicked, to color part of a word, or to copy text back out of a PDF. HarfBuzz’s answer is the **cluster**.

When text is added to a buffer, each character’s cluster is set to its position in the caller’s string, counted in the string’s own code units (bytes, for UTF-8). `hb-shape` counts characters instead, unless it is given `--utf8-clusters`. Whenever shaping combines or reorders glyphs, it **merges** their clusters: every glyph in the group is given the smallest cluster value among them (`merge_clusters_impl`, `hb-buffer.cc:569`). A cluster is therefore a group of characters and the glyphs made from them that can’t be split any further. The examples so far show each kind:

| Text | Glyphs | What happened |
|---|---|---|
| *f i* | `f_i=0` | two characters, one glyph |
| *é* (U+00E9) | `e=0`, `acutecomb=0` | one character, two glyphs |
| *a* + acute | `aacute=0` | two characters, one glyph, by composition |
| KA + I | `iMatra=0`, `ka=0` | two characters, two glyphs, in the other order |
| beh beh beh | `beh.fina=2`, `beh.medi=1`, `beh.init=0` | one glyph each, in right-to-left order |

The rule that ties them together is that a cluster holds the *whole* of what it is made of: within a cluster there is no saying which glyph came from which character. A cursor can go between clusters, and only an application that does its own work can go inside one, for example between the two letters of the *fi* ligature.

How eagerly HarfBuzz merges is set by the buffer’s **cluster level** (`hb_buffer_cluster_level_t`, `hb-buffer.h:461`). There are four. At the default, level 0, a mark is merged into the cluster of the base it follows before shaping begins (`hb_form_clusters`, `hb-ot-shape.cc:581`), and clusters are kept in order: they rise along the buffer in left-to-right text and fall in right-to-left text, with no going back. Level 1 keeps marks in clusters of their own, and still keeps the order. Level 2 does neither:

```shape
shaping.ttf  e\u0301
shaping.ttf  e\u0301  --cluster-level=1
shaping.ttf  कि  --cluster-level=1
shaping.ttf  कि  --cluster-level=2
```

At level 1 the acute has its own cluster, 1. The reordered vowel sign doesn’t: putting it first with cluster 1 would break the order, so its cluster is merged with the consonant’s. At level 2, nothing is merged just to keep the order, and the vowel sign keeps its cluster, 1, though it comes first. Level 3, which merges marks as level 0 does but doesn’t keep the order, is the newest: it arrived in 11.0.0. The header comment says level 0 is the default only for backward compatibility and recommends level 1 for new programs. The user manual adds where level 0 came from: it is how the Windows shaping engine behaves, and the old HarfBuzz copied it. All four levels are covered in [Buffers](buffers.html).

Merging is one of two things HarfBuzz records about the boundaries in its output. The other is whether a boundary is safe to break at: whether the text on each side could be shaped separately and give the same glyphs. Between joined Arabic letters it is not, since each one’s form depends on the next. HarfBuzz marks a glyph with `UNSAFE_TO_BREAK` when the run can’t safely be broken at the start of its cluster, and `hb-shape` shows the flag as `#1`:

```shape
shaping.ttf  ببب  --show-flags
```

What applications do with clusters and with these flags, for line breaking and for reshaping after an edit, is in [For applications](for-applications.html).

## Where the rules live

Everything above needed two kinds of knowledge. Some of it is about the font: which glyphs it has, which ligatures, where its anchors are. Some of it is about the script: which letters join, which vowel signs go before the consonant, what a syllable is, which features apply to which letters and in what order. The font’s designer knows the first kind. The second kind is the same for every font of the script.

There have been three answers to the question of where the second kind should live.

**In the engine.** OpenType keeps the font’s knowledge in the font and leaves the script’s knowledge to the shaping engine. A font says what `init` does to a beh. The engine decides which behs get `init`. Microsoft documents what its engine does for each script, in its specifications for developing OpenType fonts for Arabic, Devanagari and the rest, and font developers write their fonts to match. The cost is that every engine has to know every script, and has to know it the same way.

**In the font.** Apple’s layout tables, now called AAT, put everything in the font. The `morx` table holds state machines that walk along the glyphs and change, insert, ligate or rearrange them. A font for Devanagari carries its own reordering rules. The engine needs no knowledge of any script, but every font has to contain all of it.

**In the font, as a program.** SIL’s Graphite also puts the rules in the font, written in a language of its own and compiled into tables that the Graphite engine runs.

HarfBuzz implements all three. Its OpenType shaping has a script shaper for each family of scripts that needs one, which is what Part VI covers. Apple’s tables run inside the same pipeline, in place of `GSUB` and `GPOS`, when a font has them ([AAT inside HarfBuzz](aat-inside-harfbuzz.html)). Graphite runs through a separate backend that uses SIL’s own library, as [hb_shape and its backends](hb_shape-and-its-backends.html) explains.

## A short history

HarfBuzz comes out of a particular history, and it still shows in the code. What follows is only an outline, kept to what the HarfBuzz source and its documents bear out, or what is well known.

### Apple: GX, AAT and ATSUI

TrueType began at Apple. Apple’s QuickDraw GX added layout tables to it, in which the font carries its own rules as state machines: the `mort` table, later extended as `morx`, with `kern` and later `kerx` for positioning. When GX was retired, its font technology lived on as Apple Advanced Typography. On Mac OS the system API for laying out Unicode text with those fonts was ATSUI, Apple Type Services for Unicode Imaging, later replaced by Core Text. AAT fonts are still found mostly on Apple’s systems, as the HarfBuzz user manual notes.

### Microsoft and Adobe: OpenType and Uniscribe

Microsoft took the other road. Its TrueType Open, developed further with Adobe as OpenType, added the `GSUB`, `GPOS` and `GDEF` tables, which describe *what* a font can do but leave *when* to the engine. On Windows, that engine was Uniscribe, the system’s script processor, with a shaping engine for each family of complex scripts, and later DirectWrite.

Because the script knowledge lived in Uniscribe, Uniscribe’s behavior became, in practice, part of the specification. Fonts were made and tested on Windows, so they worked with what Uniscribe did, including where it differed from what the documents said. Any other engine that wanted those fonts to work had to find out what Uniscribe did, often by testing it. HarfBuzz’s source is full of the results. The Indic shaper corrects a sentence of Microsoft’s Devanagari specification with “Testing, with Windows 7 Uniscribe and Devanagari shows that the behavior is best described as…” (`hb-ot-shaper-indic.cc:1111`). The Khmer shaper applies its basic features without pauses because “testing suggests that Uniscribe does NOT pause between basic features” (`hb-ot-shaper-khmer.cc:110`). The Hangul shaper leaves `calt` off for jamo because Uniscribe does (`hb-ot-shaper-hangul.cc:69`). The [GSUB chapter](gsub.html#multiple-substitution) showed another: a multiple substitution may delete a glyph, though the specification says it can’t, because Uniscribe allows it.

Microsoft later added a single engine for many of the scripts its other engines didn’t cover, the Universal Shaping Engine, driven by Unicode character properties instead of rules written for each script. HarfBuzz implemented it in its 1.0.0 release, in July 2015, and its `NEWS` file for that release links to Microsoft’s announcement. It has its own chapter, [The Universal Shaping Engine](the-universal-shaping-engine.html).

### ICU’s LayoutEngine

IBM’s International Components for Unicode (ICU), the portable library of Unicode algorithms, had an OpenType layout engine of its own, the LayoutEngine. It offered shaping outside Windows and the Mac in a library anyone could use, and OpenJDK, among others, used it. ICU later deprecated it and pointed its users to HarfBuzz. HarfBuzz still connects to ICU in another way: `libharfbuzz-icu` lets it take Unicode properties from ICU instead of from its own tables.

### FreeType, Pango and Qt: the first HarfBuzz

The free software desktop needed shaping too. FreeType, the free font rasterizer, had code for reading OpenType layout tables, written by David Turner and Werner Lemberg. Their copyright, 1998 to 2004, is still at the top of `hb-buffer.cc` and `hb-ot-layout.cc`, and the user manual says that HarfBuzz “began its life as text-shaping code within the FreeType project”. Pango, GNOME’s text layout library, used that code for its OpenType support, with shaping modules of its own for each script. The Red Hat authors named in `hb-buffer.cc` are Owen Taylor and Behdad Esfahbod. Qt, the toolkit then developed by Trolltech and later Nokia, used the same code; two of its developers, Lars Knoll and Simon Hausmann, are in HarfBuzz’s `AUTHORS` file, and Nokia’s copyright is in `COPYING`.

The shared code was extracted into a project of its own, and Behdad Esfahbod named it HarfBuzz: in the README’s words, a “transliteration of the Persian calque for *OpenType*”, from *harf*, letter, and *bâz*, open. The README calls the second meaning, “insincerely talkative; glib”, “a nod to the GNOME project where HarfBuzz originates from”. HarfBuzz dates itself from 2006: the README lists talks called “Ten Years of HarfBuzz” in 2016 and “HarfBuzz at 20!” in 2026, and Behdad Esfahbod’s copyright on `hb-ot-layout.cc` starts in 2006. The 2006 date is the rewrite’s: he had put together a first library in 2005, “thanks to a code donation from Qt”, and “at the end of 2006 I started a rewrite of the entire codebase, codenamed harfbuzz-ng, which is what we simply call HarfBuzz today” ([“Introducing HarfRust”](https://docs.google.com/document/d/1aH_waagdEM5UhslQxCeFEb82ECBhPlZjy5_MwLNLBYo/preview), 2025).

### The rewrite

That first HarfBuzz is now called “old HarfBuzz”. Behdad Esfahbod then rewrote it as a new library, known during its development as harfbuzz-ng, “next generation”. The copyright lines show the work moving from Red Hat to Google, whose copyright starts in 2010. Its `NEWS` file calls 0.9.2, released on 10 August 2012, “the first major release of HarfBuzz”, and says HarfBuzz “should be in par, or better, than both Pango’s shapers and old HarfBuzz / Qt shapers”. The same release added an Indic shaper, a new Arabic shaper with fallback shaping, a Thai and Lao shaper, synthetic `GDEF` classes, fallback mark positioning, and backends that call Uniscribe and Core Text, “primarily for testing”: a way of comparing HarfBuzz with the engines it had to match.

Some things were kept for compatibility with what came before. The default cluster level, 0, is one of them. The README promises that the API and ABI are compatible back to the 0.9 series, and that if they ever have to break, “that would be called a new library”.

From there, HarfBuzz grew in both directions. Version 2.0.0, in October 2018, added shaping with Apple’s `morx`, `kerx` and `trak` tables, so the engine that started as an implementation of OpenType now runs Apple’s model too. Since then it has added variable fonts, subsetting, drawing and painting glyphs, and rasterizing them, which is why the README now calls it “a full font platform”. Its list of users includes Android, Chrome, Firefox, GNOME, KDE, Qt, LibreOffice, OpenJDK and Adobe’s applications, among many others, and in its own words, “HarfBuzz shapes the majority of text on modern screens”.

## What happens to a run

This chapter has looked at HarfBuzz from outside: text in, glyphs out, and the ways the two differ. The next two chapters are practical: [building HarfBuzz](building-harfbuzz.html) and [the command-line tools](command-line-tools.html) that come with it, which the rest of the book uses to show what HarfBuzz does. After them the book looks inside. It follows one run through the library: from the bytes of the font, which [Fonts as bytes](fonts-as-bytes.html) starts with, through the buffer and the shape plan, to the pipeline that maps characters to glyphs, substitutes and positions them, and hands them back with their clusters.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-buffer.h` | `hb_glyph_info_t`, `hb_glyph_position_t`, `hb_segment_properties_t`, the cluster levels and glyph flags |
| `src/hb-buffer.cc` | adding text (`hb_buffer_add_utf8` and the others), guessing segment properties, merging clusters |
| `src/hb-common.h` | `hb_feature_t`, `hb_script_t`, `hb_direction_t`, `hb_language_t` |
| `src/hb-ot-tag.cc` | translating scripts and languages into OpenType tags |
| `src/hb-ot-shape.cc` | `hb_ot_shape_internal`, the pipeline: forming clusters, mapping to glyphs, substituting, positioning |
| `src/hb-ot-shape-normalize.cc` | decomposition and composition against the font’s `cmap` |
| `src/hb-ot-shaper-arabic.cc` | the joining state machine and the order of the joining features |
| `src/hb-ot-shaper-indic.cc` | syllables and reordering |
| `NEWS`, `AUTHORS`, `COPYING`, `README.md` | the project’s own record of its history |
| `docs/usermanual-what-is-harfbuzz.xml` | the user manual’s account of what shaping is and what HarfBuzz doesn’t do |

## In short

* Text is characters in logical order. A font draws glyphs, known by glyph ID. The `cmap` gives each character a nominal glyph, and shaping starts there.
* HarfBuzz shapes a run with one script, one direction and one language, and returns, for each glyph, its ID, its cluster, an advance and an offset.
* Characters and glyphs fail to correspond because of ligatures, joining and contextual forms, reordering, marks, and decomposition and composition. Much of the knowledge needed is about the script, not the font, and in OpenType it lives in the engine.
* A cluster groups characters with the glyphs made from them. Merged clusters take the smallest value. The cluster level sets how much is merged.
* HarfBuzz grew out of FreeType’s OpenType code as shared by Pango and Qt, was rewritten as harfbuzz-ng, and had to match Uniscribe’s behavior to work with the fonts made for it. It now runs OpenType, AAT and Graphite.
