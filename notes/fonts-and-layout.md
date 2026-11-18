# Fonts and Layout for Global Scripts

Notes on Simon Cozens’s book, for anyone drafting this one. It was written between 2016 and 2021: begun in September 2016, mostly written in 2019–20, and last substantially changed in January 2021. Since then it has had only typo and link fixes. A copy is in `resources/fonts-and-layout/` (not committed), at commit `d3642ab`, 3 July 2025. It’s online at <https://simoncozens.github.io/fonts-and-layout/>.

## What it is

* It’s by Simon Cozens alone. The index page thanks Khaled Hosny, Georg Seifert, Michael Aars, Peter Constable and Rob McKaughan, and names Google Fonts, Jeremy Tribby and Lukas Prokop as sponsors.
* It’s written from the font maker’s side: OpenType taught through feature files, checked with `hb-shape`.
* Its finished chapters are history, concepts, Unicode, OpenType, the two features chapters, and localisation.
* `layout.md` stops partway through. `adv-features.md` has headings only. `harfbuzz.md`, `freetype.md`, `raqm.md`, `hint.md` and `web.md` are empty.
* The second half, about the programs that use fonts, was never written. That half is this book’s subject. The preface says so, and the bibliography lists the book.

## The licence

It’s under CC BY-SA 4.0. Cite it, link to it, and quote it briefly with credit. Don’t adapt or closely paraphrase its text: an adaptation would have to be under CC BY-SA too. The LICENSE also asks, as a courtesy, that any version in another format be typeset with care for the scripts.

## Where it differs from HarfBuzz {{hb}}

These were checked against the HarfBuzz source, at the version the book describes, in November 2026. Don’t carry them into this book. Where this book covers the topic, it should state HarfBuzz’s behavior plainly, since readers of Cozens may expect otherwise. Paths are in his repository, at the commit above.

### Feature order and lookups

* `features.md:256-262` says features apply in order, and lists HarfBuzz’s common features as ending “`mark`, `mkmk`, `liga`”. They end with `rlig` (`hb-ot-shape.cc`, `common_features[]`). `trak` is the AAT table, not an OpenType feature HarfBuzz adds. Within a stage, lookups run in LookupList order, not feature order.
* `features.md:264-266`: script fallback tries `DFLT` only. HarfBuzz tries `DFLT`, then `dflt`, then `latn` (`hb-ot-layout.cc`).
* `features.md:346`: glyphs in no GDEF class are “never ignored”. With no GDEF glyph classes, HarfBuzz guesses them from Unicode, so `IgnoreMarks` still works.
* `features.md:402` blames applications for ignoring `yAdvance` in horizontal text. HarfBuzz drops it itself (`OT/Layout/GPOS/ValueFormat.hh`).
* `features.md:428` calls `dev2` a language tag. It’s a script tag.
* `features.md:473`: with CFF outlines you need GPOS for kerning. That matches the specification, but HarfBuzz applies a `kern` table whatever the outline format.
* `features-2.md:82` says HarfBuzz has only recently implemented `rand`, and that no application requests it. HarfBuzz turns `rand` on by default, with a deterministic seed (`hb-ot-shape.cc`).
* `features-2.md:236`: an `ignore` rule “ends processing of the current lookup”. It compiles to a chain rule with no lookups. When it matches, HarfBuzz skips past the matched input, and the lookup carries on at later positions. His wording is ambiguous rather than wrong.
* `features-2.md:446` has the hamza attaching to the damma. It is the other way round: the damma attaches to the hamza, as base mark.

### Scripts

* `localisation.md:258-290`: the reph only moves after the base once it’s in a mark class. In HarfBuzz the reph moves whenever `rphf` formed it (`hb-ot-shaper-indic.cc`). This was tested with his own example font under hb-shape {{hb}}, and the result is the same with or without the `markClass`.
* `localisation.md:43`: `abvs` runs “near the start of the substitution phase”. In the Indic and USE shapers it is one of the last, presentation features, after reordering.
* `localisation.md:356`: in USE, `locl`, `ccmp`, `nukt` and `akhn` apply “in that order”. In HarfBuzz they’re one stage, so lookups run in LookupList order (`hb-ot-shaper-use.cc`).
* `localisation.md:399`: Tai Tham doesn’t fit USE. HarfBuzz USE now adds sakot groups for Tai Tham, although the specification’s grammar doesn’t.
* `localisation.md:130,139` has the typos `exclude_dft` and `exclude_dflt`.

### Layout and Unicode

* `layout.md:46`: text can be put in visual order before shaping. HarfBuzz needs each run in logical order. It reverses right-to-left runs and mirrors brackets itself.
* `unicode.md:36,46` says Unicode is “up to version 9.0”. HarfBuzz {{hb}} has Unicode 18.0.0 tables.
* `unicode.md:42` gives the click letter as U+013C. It is U+01C3 (U+013C is ļ).
* `unicode.md:107`: emoji “all live in the supplemental plane”. Many are in the BMP.
* `history.md:150`: HarfBuzz “recently gained support for AAT”. That was 2.0.0, in 2018.
* `history.md:152` says Microsoft and Adobe made TrueType Open together. TrueType Open was Microsoft’s and came first, as his own footnote concedes.
* `concepts.md:28` describes the platform situation as it was then: HarfBuzz on libre systems, DirectWrite on Windows.

### OpenType tables

* `opentype.md:142`: unitsPerEm “must be a power of two” for TrueType. The specification allows 16 to 16384, and only recommends a power of two for TrueType. HarfBuzz replaces an out-of-range value with 1000 (`hb-ot-head-table.hh`).
* `opentype.md:191,204` calls the fsSelection bit set bit 7. The value shown, `00000000 01000000`, is bit 6 (REGULAR).
* `opentype.md:226`: which metrics applications use. HarfBuzz uses typo metrics only with USE_TYPO_METRICS, and otherwise hhea, never the Win metrics. See `where-metrics-come-from.md`.
* `opentype.md:551`: variation deltas multiplied together. They are scaled and added.
* `opentype.md:32` (`easy_install`) and the `otspec180` links are stale.

## Checked and correct

* `features.md:296-300`: the lookup-versus-rule example.
* `features-2.md:377`: the root of a right-to-left cursive chain (`CursivePosFormat1.hh`).
* `features-2.md:521-542`: reading `hb-shape` offsets.
* `localisation.md`: a `pref` that substitutes a glyph by itself still triggers reordering (`_set_glyph_class` always sets SUBSTITUTED).

## What this book has taken up from it

Done in November 2026:

* The preface says how the two books relate, and the bibliography lists it.
* “See also” links to his font maker’s examples, from GSUB, GPOS, Normalization, Joining scripts, The Indic model and Choosing a script shaper.
* Where his readers may expect otherwise, the book now says plainly: `rand` is on by default (GSUB); a reph that `rphf` formed moves without a mark class (The Indic model); runs go to HarfBuzz in logical order (For applications); a `kern` table is applied in a CFF font too (Legacy kern).
* What feature-file constructs compile to: `ignore`, inline contextual rules, mixed blocks and rules before the first `script` (GSUB, “What a feature file compiles to”).
* A kerning triplet (GPOS, “Context, chained context and extension”).
* A Turkish i through `locl`, and why its lookup must come first (Choosing a script shaper, “Turkish i”).
* The order features run in, shaper by shaper (the appendix “Feature order”).

Not taken up: a guide to choosing which feature a rule belongs in (the appendix covers when each runs), and his advice on setting vertical metrics, which is opinion.
