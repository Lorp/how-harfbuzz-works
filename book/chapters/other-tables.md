# Other tables

Shaping reads `cmap`, GSUB, GPOS, GDEF and the metrics tables. A font has others that matter to the software around the shaper: how to build a fraction or stretch a parenthesis, where the hanging baseline is, what weight the font is, what it is called in German, which languages it was made for. HarfBuzz reads five of these for applications: `MATH`, `BASE`, `STAT`, `name` and `meta`. None of them changes what `hb_shape` returns. Each has a small API that answers questions about the font, and leaves the layout to the caller.

This chapter is about those APIs: what each offers, how it reads its table, and what it does when the table is missing or says less than asked.

The examples use eight small fonts built with fontTools by `fonts/other-tables/build-fonts.py`, and one variable font from `fonts/variations/`. Their glyphs are boxes. Most of the output on this page comes from `hb-info`, run on those fonts with HarfBuzz {{hb}} when the page was built. `hb-info` has no options for `MATH` or for `BASE`’s min and max extents, so the values quoted for those come from `fonts/other-tables/query.c`, a short C program run against the same build when the chapter was written, not when the page is built.

## MATH

The `MATH` table holds what a formula typesetter needs from a font: 56 constants (how far to raise a superscript, how thick to draw a fraction bar), per-glyph corrections, and larger versions of glyphs that grow, such as parentheses, radicals and integrals. HarfBuzz doesn’t typeset formulas. The section comment in `hb-ot-math.cc` says so: “HarfBuzz itself does not implement a math layout solution. The functions and types provided can be used by client programs to access the font data necessary for typesetting OpenType Math layout.” The API came from Frédéric Wang of Igalia, whose name is on the file, and appeared in 1.3.3.

Two browsers use it for MathML: Chromium’s `third_party/blink/renderer/platform/fonts/opentype/open_type_math_support.cc` and Firefox’s `gfx/thebes/gfxMathTable.cpp` both call `hb_ot_math_get_constant`, `hb_ot_math_get_glyph_italics_correction`, `hb_ot_math_get_glyph_variants` and `hb_ot_math_get_glyph_assembly`. The layout itself is theirs.

The functions follow the table’s three parts:

| Part of the table | Function | Returns |
|---|---|---|
| `MathConstants` | `hb_ot_math_get_constant` | one constant, scaled, or a percentage |
| `MathGlyphInfo` | `hb_ot_math_get_glyph_italics_correction` | a glyph’s italics correction, or 0 |
| | `hb_ot_math_get_glyph_top_accent_attachment` | where an accent centres over a glyph, or half its advance |
| | `hb_ot_math_is_glyph_extended_shape` | whether the glyph is in the extended-shape coverage |
| | `hb_ot_math_get_glyph_kerning`, `hb_ot_math_get_glyph_kernings` | the cut-in at one corner of a glyph, at a height or as the whole list |
| `MathVariants` | `hb_ot_math_get_glyph_variants` | larger versions of a glyph in one direction |
| | `hb_ot_math_get_glyph_assembly` | parts to build a glyph of any size from |
| | `hb_ot_math_get_min_connector_overlap` | how much those parts must overlap |

`hb_ot_math_has_data` tests for the table: its version is non-zero. The sanitizer accepts major version 1 only (`hb-ot-math-table.hh:1258`).

### Constants

Every constant is read through one switch, `MathConstants::get_value`. Most are `MathValueRecord`s, a value with an optional Device table (a delta for the variation coordinates or the ppem), scaled by the font’s y scale; four horizontal ones, the radical kerns, the skewed fraction gap and `spaceAfterScript`, take the x scale. The two script scale-downs and `radicalDegreeBottomRaisePercent` are percentages, returned as they are. The two minimum heights are plain integers, scaled with no Device table.

In `math.ttf` the axis height is 250 and the script scale-down 70. At the default scale, 1,000 units per em, HarfBuzz returns 250 and 70; at a scale of 2,000, it returns 500 for the axis height and still 70 for the percentage (from `query.c`).

One font gets special treatment. HarfBuzz issue #4653 found that Cambria Math has the values of `displayOperatorMinHeight` and `delimitedSubFormulaMinHeight` the wrong way round, and that Microsoft’s implementation swaps them. `hb_ot_math_get_constant` does the same when `is_bad_cambria` recognises the font: a `MATH` table 25,722 bytes long with those two fields at 2,500 and 3,000 (`hb-ot-math-table.hh:1266`, comparing three known `cambria.ttc` files). 11.4.3 fixed the detection for fonts at other scales.

### Glyph info

An **italics correction** is the extra space a slanted glyph needs after it before an upright one, or where a superscript goes. `f` in `math.ttf` has one of 120 units. A glyph outside the coverage table gets 0.

The **top accent attachment** is the horizontal position over which an accent is centred. It is the one value in the table that HarfBuzz makes up when the font doesn’t give it: a glyph not in the coverage gets half its advance (`hb-ot-math-table.hh:331`). In `math.ttf`, `a` has 300 and `x`, not covered, gets 250, half of its 500.

A **math kern** is a cut-in at one corner of a glyph: how far a superscript or subscript may tuck under or over it, as a step function of height. Each corner has *n* heights and *n* + 1 kern values. `MathKern::get_value` (`:391`) chooses the value whose range contains the height asked for, by binary search, as `std::upper_bound` would: “the index chosen for kern value should be i such that correctionHeight[i-1] <= correction_height < correctionHeight[i]”. A height exactly on a boundary takes the value above it. The top-right corner of `f` has heights 300 and 600 and values −50, 0 and 40; at heights 0, 150, 300, 600 and 900 HarfBuzz returns −50, −50, 0, 40 and 40. The heights are compared after scaling. HarfBuzz 8.3.1’s `NEWS` says it changed this function “to match updated ‘MATH’ table spec”.

`hb_ot_math_get_glyph_kernings` (3.4.0) returns the whole step function as `hb_ot_math_kern_entry_t` pairs. There is one more value than height, so the last entry’s `max_correction_height` is `INT32_MAX`: for `f`, (300, −50), (600, 0), (2147483647, 40).

`hb_ot_math_is_glyph_extended_shape` is a coverage test. The specification uses it for glyphs whose extents are not a good guide to where scripts go, typically the larger variants; in `math.ttf`, `parenleft.size1` and `parenleft.size2`.

### Glyph variants and assemblies

A glyph that can grow has a `MathGlyphConstruction` in each direction it grows in: a list of larger variants, each with its size, and optionally a **glyph assembly**, a list of parts from which any larger size is built. `math.ttf` has a vertical construction for `parenleft`: variants of 900, 1,300 and 1,700 units (the first is the glyph itself), and an assembly of a bottom, an extender and a top, each 600 units with 200-unit connectors at the ends that join.

`get_glyph_construction` (`:1156`) chooses the vertical or horizontal coverage by `HB_DIRECTION_IS_VERTICAL`, and the sizes are scaled by that direction’s scale. Asked for the vertical variants of `parenleft`, HarfBuzz returns the three glyphs with 900, 1,300 and 1,700; asked for horizontal ones, none. The parts come back in the table’s order, “from left to right and bottom to top”, with their connector lengths, full advances and one flag, `HB_OT_MATH_GLYPH_PART_FLAG_EXTENDER`, which marks a part that may be repeated or left out. The assembly’s own italics correction comes back beside them. Choosing a variant, or working out how many extenders to use and how far to overlap them, at least `hb_ot_math_get_min_connector_overlap` (20 in `math.ttf`), is the client’s job.

All of these take a `start_offset` and an in/out count, as HarfBuzz’s list functions do, and return the total, so a client can ask for the count first and then fill an array.

`MATH` matters to subsetting too: the glyph closure adds the variants and assembly parts of the glyphs kept, and what it misses is in [Where the fixed order misses](subsetting.html#where-the-fixed-order-misses).

## BASE

A line of text can mix scripts that sit on different baselines: Latin on the alphabetic baseline, Devanagari hanging from its headline, Chinese on the bottom of the ideographic em box. The `BASE` table says where each baseline is, for each script, so that an application can line them up. It can also give each script, and each language system, its own **min/max extents**: how far the glyphs reach above and below the baseline, in place of the font’s ascender and descender.

`hb_ot_layout_get_baseline` (2.6.0) reads one baseline, and `hb_ot_layout_get_baseline_with_fallback` (4.0.0) makes one up when the font doesn’t have it. Both take a baseline tag, a direction, and OpenType script and language tags; the versions ending in `2` (8.0.0) take an `hb_script_t` and an `hb_language_t` instead. `hb-info --list-baselines` prints every baseline both ways, with an asterisk on the ones that were made up. `base.ttf` has a horizontal axis, with the baselines `hang`, `ideo` and `romn` for the scripts `DFLT`, `dev2` and `hani`, and `latn` with extents but no baselines:

```table
font: base.ttf
table: BASE
```

### Looking a baseline up

The lookup is short (`hb-ot-layout-base-table.hh:605–683`). The direction chooses the axis, horizontal or vertical. The script tag is found in that axis’s script list by binary search; if it isn’t there, `DFLT` is used instead. The baseline tag is found in the axis’s tag list, and its index picks the coordinate from the script’s values. The language tag isn’t used at all: in the `BASE` table, language systems have min/max extents but no baselines of their own.

```info
base.ttf  --list-baselines
base.ttf  --list-baselines  --ot-script=dev2
base.ttf  --list-baselines  --script=Latn
```

With no script, the values are `DFLT`’s: `hang` 600, `ideo` −120, `romn` 0. With the tag `dev2`, the hanging baseline is 640. With `--script=Latn`, every value has an asterisk, though `DFLT` has three of them: `latn` is in the font, so the search finds it and doesn’t go on to `DFLT`, and `latn` has no baseline values. A script record with only extents hides `DFLT`’s baselines from that script.

There are three coordinate formats. Format 1 is a number. Format 3 adds a Device table, which in a variable font is a variation index into the table’s item variation store (`BASE` version 1.1). Format 2 names a glyph and a contour point whose position should be used instead, so that the baseline follows hinting; HarfBuzz reads only its number, and the code says `/* TODO */` (`:73`). Format 4 is format 2 with a 24-bit glyph ID, for fonts beyond 64K glyphs.

### Which script tag

The functions that take an `hb_script_t` turn it into tags with `choose_base_tags` (`hb-ot-layout.cc:2168`), and keep the *last* of them. For Devanagari, HarfBuzz’s tags are `dev3`, `dev2` and `deva`, in that order of preference, and the last is the oldest, `deva`. So a `BASE` table that lists its Devanagari values under `dev2` isn’t found from `HB_SCRIPT_DEVANAGARI`, and the `DFLT` values are used. `hb-info` chooses the same way:

```info
base.ttf  --get-baseline=hang  --script=Deva
base.ttf  --get-baseline=hang  --ot-script=dev2
```

The OpenType specification doesn’t say which of a script’s tags `BASE` should use; GSUB and GPOS have both, and a font may use either. A client that knows the font uses `dev2` can pass tags directly.

### Baselines a font doesn’t have

`hb_ot_layout_get_baseline_with_fallback` (`hb-ot-layout.cc:2423`) synthesizes a missing baseline, following the CSS Inline Layout specification’s “baseline synthesis” (the comment links to it). In horizontal text:

| Tag | What HarfBuzz does without it |
|---|---|
| `romn` | 0, with a comment “FIXME origin ?” |
| `math` | the middle of the minus sign’s ink (U+2212, or else the hyphen-minus); without either, half the x-height |
| `hang` | the top of a typical letter for one of 21 Indic and other hanging scripts (क for Devanagari, ক for Bengali, ཀ for Tibetan…); for any other script, or without that glyph, 60% of the em |
| `ideo` | the embox top (`idtp`) minus the em, if the font has `idtp`; otherwise the font’s descender |
| `idtp` | `ideo` plus the em, if the font has `ideo`; otherwise the font’s ascender |
| `icfb`, `icft` | the embox edges, each moved inwards by a tenth of the em box’s height |
| `Icfc`, `Idce` | halfway between the two face edges, or the two embox edges |

`Icfc` and `Idce` aren’t in OpenType’s registry of baseline tags: HarfBuzz gave them capital first letters, as its private tags have, so in practice they are always synthesized. `nobase.ttf` has the same glyphs as `base.ttf` and no `BASE` table:

```info
nobase.ttf  --list-baselines
nobase.ttf  --get-baseline=hang  --script=Deva
nobase.ttf  --list-baselines  --direction=ttb
```

Every value is made up. The `math` baseline is 260, the middle of the minus sign’s box, from 230 to 290. The hanging baseline is 600 for no script and 640, the top of क’s headline, for Devanagari. The ideographic em box is the font’s descender and ascender, −200 and 800, and the face is a tenth inside it. In `base.ttf` above, `ideo` came from the font, so `idtp` was `ideo` plus the em: 880. Vertical text, as in the third row, takes its em box from the vertical font extents, −500 and 500 for this font, which has no `vhea` ([Where metrics come from](where-metrics-come-from.html#font-extents)), its `math` baseline from half the x-height, and its hanging baseline from 60% of the em across the column. {{hb}}’s `NEWS` lists a fix to the fallback for “the hanging baseline for some scripts”.

`hb_ot_layout_get_horizontal_baseline_tag_for_script` (4.0.0) gives the baseline a script usually sits on: `hang` for the 21 hanging scripts, `icfb` for Han, Hangul, kana, Bopomofo, Tangut, Nushu, Khitan, Jurchen and Seal, and `romn` for the rest. Its list is the same as the fallback’s, and a comment in each says to keep them in step.

### Extents for a script

`hb_ot_layout_get_font_extents` and `hb_ot_layout_get_font_extents2` (8.0.0) read a script’s min/max extents: the language system’s if there is a record for it, else the script’s default (per-feature values are never asked for). Found, they become the ascender and descender, with a line gap of zero, and the function returns true. If not, it returns the font’s ordinary extents and false.

In `base.ttf`, Latin text gets 900 and −250, Vietnamese (`VIT `) 1,100 and −300, and Devanagari, with no extents in the table, the font’s 800 and −200 and false (from `query.c`). One case goes wrong. A script with language-system extents but no default extents, `DefaultMinMax` being optional, returns true with an ascender and descender of 0 for every other language: the missing table is read as the `Null` object, whose coordinates are 0 (`hb-ot-layout-base-table.hh:482`, checked with a copy of `base.ttf` without `latn`’s defaults). That looks like a HarfBuzz bug. A missing `MinCoord` or `MaxCoord` in a record that exists is read as 0 in the same way.

Nothing in shaping reads `BASE`; [Vertical text](vertical-text.html) covers what HarfBuzz leaves to applications in vertical layout.

## STAT and hb_style_get_value

`hb_style_get_value` (3.0.0) answers one question about a font: where does it sit on a style axis? It knows six tags:

| Tag | Constant | Meaning |
|---|---|---|
| `wght` | `HB_STYLE_TAG_WEIGHT` | weight, 1 to 1,000 |
| `wdth` | `HB_STYLE_TAG_WIDTH` | width, as a percentage of normal |
| `ital` | `HB_STYLE_TAG_ITALIC` | 0 for roman, 1 for italic |
| `slnt` | `HB_STYLE_TAG_SLANT_ANGLE` | slant, in degrees counter-clockwise, so negative for a right-leaning italic |
| `Slnt` | `HB_STYLE_TAG_SLANT_RATIO` | the same slant as a ratio, positive for a right-leaning italic |
| `opsz` | `HB_STYLE_TAG_OPTICAL_SIZE` | optical size, in points |

`Slnt`, with a capital, is HarfBuzz’s own: it is the slant angle turned into a ratio, `tan (−angle)`. The others are the registered axis tags. The answer comes from the first of these that has one (`hb-style.cc:72`):

1. A variation axis with that tag in `fvar`: the font’s design coordinate on it, or the axis default if no coordinates are set. For a variable font, as the code says, “fvar’s default_value is better than STAT records”.
2. For `opsz` only, the font’s point size, `ptem`, if it is set ([Three kinds of size](fonts-and-font-functions.html#three-kinds-of-size)).
3. The `STAT` table: the value of the first axis value record for that axis.
4. Older tables: OS/2’s `usWeightClass`, its `usWidthClass` turned into a percentage, its italic bit or `head`’s, and `post`’s italic angle. Without OS/2, `head`’s bold, condensed and expanded bits give 700 or 400, 75, 125 or 100. For `opsz`, the middle of OS/2’s optical size range (version 5), or the design size of GPOS’s `size` feature, or else 12.

`variations/var.ttf` has `wght` and `wdth` axes, so those come from the coordinates; the rest from its other tables:

```info
variations/var.ttf  --list-style  --variations=wght=650,wdth=80  --font-ptem=9  --font-slant=0.2
```

### Reading STAT

`STAT` names the positions in a family ([Design space](design-space.html)); `hb_style_get_value` uses it as a record of where a *static* font sits. `STAT::get_value` (`hb-ot-stat-table.hh:480`) finds the axis tag among the design axes, then returns the value of the first axis value table that refers to that axis. Formats 1 and 3 give their value, format 2 its nominal value. Format 4, which gives a combination of values on several axes, is never matched: “Makes more sense for variable fonts which are handled by fvar in hb-style” (`:371`).

Choosing the first is right for a font whose `STAT` lists only its own values. A `STAT` table can list more: a static font made as one of a family may describe the family’s whole weight range, with flags that mark which values are elidable, and nothing in the table marks the font’s own. `style-stat.ttf` has OS/2 weight 700 and a `STAT` with weight values 300, 400 and 700, in that order:

```table
font: style-stat.ttf
table: STAT
```

```info
style.ttf  --list-style
style-stat.ttf  --list-style
style-stat.ttf  --get-style=slnt  --font-slant=0.2
style.ttf  --get-style=slnt  --font-slant=0.2
```

`style.ttf` has no `STAT`, and reports what OS/2 and `post` say: weight 700, width 75 (width class 3), italic 1, slant −12. `style-stat.ttf` reports weight 300, the first value, though the font is bold. Its slant of 0, upright, comes from `STAT` too, and wins over `post`’s −12. It also wins over synthetic slant: only the `post` fallback adds the font’s synthetic slant to the angle (`hb-style.cc:114`), so `--font-slant=0.2` changes the answer for `style.ttf` and not for `style-stat.ttf`, nor (read from the code) for a variable font with a `slnt` axis. (Synthetic slant itself is in [Fonts and font functions](fonts-and-font-functions.html#slant).)

### Optical size from OS/2

The optical size fallback has a unit wrong. OS/2 version 5’s `usLowerOpticalPointSize` and `usUpperOpticalPointSize` are in TWIPs, twentieths of a point, as the OpenType specification says, but `OS2V5Tail::get_optical_size` (`hb-ot-os2-table.hh:86`) returns them as they are, and `hb_style_get_value` averages them as points. `style.ttf`’s range is 8 to 24 points, stored as 160 and 480:

```info
style.ttf  --get-style=opsz
style-size.ttf  --get-style=opsz
```

The answer is 320 points, not 16. That looks like a HarfBuzz bug. The `size` feature’s design size is in decipoints, and is divided by 10: `style-size.ttf`, which has OS/2 version 4 and a `size` feature of 100, reports 10.

`STAT` is read in shaping in one place: an AAT `trak` table is applied only to a font that also has `STAT` (`hb-ot-shape.cc:218`), Apple’s test for a modern font ([AAT positioning](aat-positioning.html)).

## name

The `name` table holds the font’s strings: family and style names, copyright, version, designer, and any string another table refers to by name ID, such as a `STAT` axis name, a named instance, a stylistic set’s label or a palette name. Each **name record** has a platform, an encoding, a language and a name ID, and points to its bytes in a pool. The API (2.1.0, `hb-ot-name.h`) has two parts. `hb_ot_name_list_names` returns the name IDs and languages the face has, as `hb_ot_name_entry_t`s. `hb_ot_name_get_utf8`, `hb_ot_name_get_utf16` and `hb_ot_name_get_utf32` return one name, in one language, converted to that encoding.

`names.ttf` has the family name, ID 1, for Windows in US English, UK English, German and Japanese, and for the Macintosh in English; a name 256 for the Macintosh only, with an é; and a name 257 on the Unicode platform, in two languages given by an `ltag` table:

```table
font: names.ttf
table: name
```

### Choosing one record

The accelerator (`OT/name/name.hh:477`) turns the records into a sorted list when the table is first used. For each record it works out a language, an `hb_language_t`, and a score for its platform and encoding (`:118`), in the same order of preference as `cmap`:

| Score | Platform, encoding | Read as |
|---|---|---|
| 0–2 | Windows UCS-4 (3, 10); Unicode full repertoire (0, 6) and UCS-4 (0, 4) | UTF-16BE |
| 3–7 | Windows BMP (3, 1); Unicode BMP and older (0, 3) to (0, 0) | UTF-16BE |
| 8 | Windows Symbol (3, 0) | UTF-16BE |
| 10 | Macintosh Roman (1, 0) | ASCII |
| — | anything else | dropped |

It sorts by name ID, language, score and position, and keeps the first record of each name ID and language, dropping unsupported encodings and records whose language it doesn’t know. So for each name and language there is one string, and the platform with the best encoding provides it. A Windows name hides a Macintosh one in the same language.

The language comes from the platform. A Windows record’s language ID is looked up in a table of 240 Windows language codes (`hb-ot-name-language-static.hh`), and a Macintosh record’s in a table of 117 of Apple’s. A Unicode-platform record’s language ID is an index into the font’s `ltag` table, Apple’s list of language tags, which is otherwise read for `morx` ([feat and ltag](aat-inside-harfbuzz.html#feat-and-ltag)). Without an `ltag` table, a Unicode-platform record has no language and is dropped. The name table’s own language tags, format 1’s `langTagRecord`s, aren’t read at all: the sanitizer accepts format 1, but “We only implement format 0 for now” (`:568`), and a language ID of 0x8000 or more isn’t in the Windows table.

```info
names.ttf  --get-name=257  --language=ga
names-noltag.ttf  --get-name=257  --language=ga
```

The Windows table maps codes to tags without regions, mostly: 0x0409, US English, and 0x0809, UK English, are both `en` (`:61`, `:186`), as are the other English variants, and so with French, German, Spanish and Portuguese. Chinese keeps its regions (`zh-cn`, `zh-tw`, `zh-hk`, `zh-sg`). Since one record is kept for each name and language, the UK English family name in `names.ttf` can’t be reached at all: it and the US one are both `en`, and the US one comes first. `hb_ot_name_list_names` lists ID 1 three times, for `de`, `en` and `ja` (from `query.c`).

### Matching a language

`get_index` (`:522`) looks for the name ID and the language asked for, first exactly, then by `hb_language_matches`: a request for a more specific tag finds a record in a less specific one, so `en-GB` finds `en` and `de-AT` finds `de`. A request for a less specific tag doesn’t find a more specific record: `zh` doesn’t find `zh-tw`. With no language, `HB_LANGUAGE_INVALID`, the functions ask for `en` (`hb-ot-name.cc:78`). With a language the font doesn’t have, they return nothing: there is no fallback to English, or to any name. `hb-info` adds one of its own, asking for `en` when the first request fails:

```info
names.ttf  --get-name=1  --language=de-AT
names.ttf  --get-name=1  --language=en-GB
names.ttf  --get-name=1  --language=fr
```

`hb-info --list-names` has a slip of its own. It lists every entry from `hb_ot_name_list_names`, but fetches each one’s string in the language given on the command line, not in the entry’s language, so a name in three languages is printed three times in one of them:

```info
names.ttf  --list-names  --language=de
```

### Encodings

The bytes are UTF-16BE for every supported platform but the Macintosh, and HarfBuzz converts them to the encoding asked for with its own UTF readers and writers (`hb_ot_name_convert_utf`, `:40`). A malformed sequence, such as an unpaired surrogate, becomes U+FFFD. Macintosh Roman is read as ASCII: “We treat all Mac Latin names as ASCII only.” A byte of 0x80 or more becomes U+FFFD (`hb-utf.hh:415`), so the é of name 256 is lost:

```info
names.ttf  --get-name=256
```

The other Macintosh encodings, such as Japanese, aren’t read at all.

The functions take the buffer size in, give the length written out, and return the name’s full length. The output is always NUL-terminated, and the NUL counts against the buffer: with room for 4 bytes, family name 1 comes back as “HBB” and a NUL, and the return value is 12, the length of “HBBook Names”. A truncated string never ends in the middle of a character.

## meta

The `meta` table, which came from Apple, is a list of tagged blobs of data. Two tags are defined by OpenType: `dlng`, the languages and scripts the font was designed for, and `slng`, those it supports, each a comma-separated list of tags in ASCII. HarfBuzz’s API (2.6.0) has two functions: `hb_ot_meta_get_entry_tags`, which lists the tags, and `hb_ot_meta_reference_entry`, which returns one entry’s data as a sub-blob of the table. The `hb_ot_meta_tag_t` enum names `dlng` and `slng`; Apple’s `appl` and `bild` are there commented out. Entries are found by linear search (`hb-ot-meta-table.hh:80`), and a missing one is an empty blob.

```info
names.ttf  --list-meta
names.ttf  --get-meta=slng
nobase.ttf  --get-meta=slng
```

HarfBuzz doesn’t parse the lists. `dlng` and `slng` are text for the client to split, and nothing in HarfBuzz uses them, not even to choose a language for shaping or for `name`.

## Other readers for applications

Two more functions read GPOS and GSUB for applications. `hb_ot_layout_get_size_params` reads the `size` feature: a design size in decipoints, a subfamily ID and name ID, and a range of sizes. `hb_ot_layout_feature_get_name_ids` reads a stylistic set’s UI label, or a character variant’s label, tooltip, sample text and parameter names; `hb-info --list-features` shows the labels. Like `STAT`, `fvar` and `CPAL`, these give name IDs, whose strings come from `hb_ot_name_get_utf8`. The other readers are in their own chapters: `hb_ot_color_*` in [Colour](colour.html), `hb_ot_var_*` in [Design space](design-space.html), and `hb_ot_metrics_get_position` in [Where metrics come from](where-metrics-come-from.html).

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ot-math.h`, `src/hb-ot-math.cc` | the MATH API, its constants and part flags, and the Cambria swap |
| `src/hb-ot-math-table.hh` | `MathConstants`, `MathGlyphInfo` with italics corrections, accent attachments and `MathKern`, `MathVariants` with constructions and assemblies, `is_bad_cambria` |
| `src/hb-ot-layout-base-table.hh` | `BASE`: the axes, script and language records, `MinMax`, and the coordinate formats |
| `src/hb-ot-layout.cc` | `hb_ot_layout_get_baseline` and its fallbacks (`:2362`–`2640`), `hb_ot_layout_get_font_extents`, `hb_ot_layout_get_horizontal_baseline_tag_for_script`, `hb_ot_layout_get_size_params`, `hb_ot_layout_feature_get_name_ids` |
| `src/hb-style.h`, `src/hb-style.cc` | `hb_style_get_value` and its order of sources |
| `src/hb-ot-stat-table.hh` | `STAT`: axis records, the four axis value formats, `STAT::get_value` |
| `src/hb-ot-os2-table.hh`, `src/hb-ot-head-table.hh`, `src/hb-ot-post-table.hh` | the older fields the style fallbacks read |
| `src/hb-ot-name.h`, `src/hb-ot-name.cc` | the name API |
| `src/OT/name/name.hh` | `name`: records, scores, the accelerator, language matching, UTF conversion |
| `src/hb-ot-name-language-static.hh` | the Windows and Macintosh language code tables |
| `src/hb-aat-ltag-table.hh` | `ltag` |
| `src/hb-ot-meta.h`, `src/hb-ot-meta.cc`, `src/hb-ot-meta-table.hh` | `meta` |
| `util/hb-info.cc` | the `--list-baselines`, `--list-style`, `--list-names` and `--list-meta` options |

Each API can be compiled out: `HB_NO_MATH`, `HB_NO_BASE`, `HB_NO_STYLE`, `HB_NO_NAME` and `HB_NO_META`. `HB_NO_NAME` sets `HB_NO_OT_NAME_LANGUAGE`, which leaves out the language tables, and `HB_NO_AAT` sets `HB_NO_OT_NAME_LANGUAGE_AAT`, which leaves out `ltag`’s use in `name`. `HB_LEAN` sets all of them except `HB_NO_BASE`, along with `HB_NO_LAYOUT_FEATURE_PARAMS`, which removes the feature name IDs and the `size` parameters (`hb-config.hh:55–80`). `HB_NO_STYLE` also turns off `trak`, whose test for `STAT` it removes.

## In short

* `MATH`, `BASE`, `STAT`, `name` and `meta` don’t affect shaping (apart from `STAT` as the test for `trak`). HarfBuzz reads them for applications.
* The MATH API returns constants, italics corrections, accent positions (half the advance when missing), math kerns as step functions of height, and size variants and assemblies by direction. It swaps two constants for Cambria Math.
* `BASE` baselines are per script, found by tag with `DFLT` as fallback; a script with a record but no values gets no baselines from `DFLT`. With an `hb_script_t`, HarfBuzz looks up the oldest tag, `deva` not `dev2`. Missing baselines are synthesized from the minus sign, a hanging letter, the font extents and the em. Min/max extents can be per language.
* `hb_style_get_value` takes the value from `fvar` coordinates, then `ptem` for `opsz`, then the first `STAT` value for the axis, then OS/2, `head` and `post`. The first `STAT` value may not be the font’s own, `STAT` hides synthetic slant, and OS/2’s optical sizes are read as points when they are TWIPs.
* `name` keeps one record per name ID and language, from the platform with the best encoding. Windows English variants are all `en`; Unicode-platform names need `ltag`; format 1 language tags aren’t read; Macintosh Roman is read as ASCII. Names come out as UTF-8, UTF-16 or UTF-32, in the language asked for or a less specific one, else not at all.
* `meta` entries come back as raw blobs; HarfBuzz doesn’t parse `dlng` or `slng`.
