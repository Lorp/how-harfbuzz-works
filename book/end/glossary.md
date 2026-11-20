# Glossary

**Accelerator.** An object HarfBuzz builds once per face from a table, holding whatever makes the table quick to read: a chosen `cmap` subtable, per-lookup digests, a glyph count.

**Advance.** How far the pen moves after a glyph: along *x* in horizontal text, along *y* in vertical text.

**Analytic coverage.** Working out how much of each pixel an outline covers exactly, from its edges, rather than by sampling points.

**Anchor.** A point on a glyph where another glyph attaches: a mark onto a base, or one cursive glyph onto the next.

**ankr.** Apple’s anchor point table, which `kerx` format 4 uses to attach one glyph to another by named points.

**Attachment chain.** HarfBuzz’s record, on each attached glyph, of the glyph it hangs from (`attach_chain`, `attach_type`), resolved into offsets after all GPOS lookups have run.

**Backend.** A complete shaping engine that `hb_shape` can hand a run to: `ot`, HarfBuzz’s own, or `graphite2`, `wasm`, `harfrust`, a platform engine, or `fallback`. Not the same as a script shaper.

**Base consonant.** The consonant an Indic syllable is built around, which HarfBuzz finds by asking the font’s own `blwf`, `pstf`, `pref`, and `vatu` lookups which consonants they would change.

**Bidi closure.** Adding the mirrored partners of requested characters, such as ( for ), so right-to-left text still works in a subset.

**Blob.** A run of bytes with a reference count and a function that frees them. Every table HarfBuzz reads is a blob, usually a sub-blob of the font file’s.

**Blocked.** Of a mark during composition: separated from the starter by a mark of the same or a higher combining class, so it can’t compose with it.

**Broken cluster.** A syllable that doesn’t follow its script’s grammar, such as a vowel sign with no consonant. HarfBuzz gives it a dotted circle.

**cfar.** “Conjunct form after Ro”: the Khmer feature applied to the glyphs after a COENG + RO that has been moved before the base.

**Chain.** In `morx`, a sequence of subtables run in order, each enabled or disabled by flags that the requested features set.

**Charstring.** A small program in a CFF or CFF2 font that draws one glyph’s outline. HarfBuzz runs it, ignoring the hints.

**Chillu.** In Malayalam, a consonant written in its final, vowelless form, which HarfBuzz treats like a half form.

**Chosen script.** The script tag HarfBuzz settles on in GSUB or GPOS: the first of the run’s tags the font has, or a fallback. GSUB’s choice helps pick the script shaper.

**ClipBox.** In COLR version 1, a box that bounds a glyph’s paint, giving its extents and limiting gradients that would otherwise fill everything.

**Cluster.** A number on each glyph naming the text it came from, normally the index of its first character. Glyphs from the same text share a cluster.

**Cluster level.** A buffer setting that decides how eagerly HarfBuzz merges clusters, and whether it keeps them in order.

**Code point.** The number Unicode gives a character, written in hexadecimal after “U+”, from U+0000 to U+10FFFF.

**COENG.** The Khmer sign, U+17D2, that makes the next consonant a subscript: Khmer’s counterpart of the virama.

**Color line.** The list of color stops along a COLR gradient, with an extend mode saying what happens beyond its ends.

**Content type.** Whether a buffer holds characters (Unicode), glyph IDs (glyphs), or nothing yet.

**Context (of a run).** Text just before and after a run, given to HarfBuzz so that rules looking across the run’s edges still work. It is not shaped.

**Context set.** In hb-depend, the glyphs a contextual lookup’s rule needs around it before an edge applies.

**Continuation.** A character that belongs with the one before it in a grapheme, such as a mark. HarfBuzz keeps a bit for it in each glyph’s Unicode properties.

**Coverage table.** A list of glyphs that a subtable applies to. A glyph’s place in the list (its coverage index) picks its data in the subtable.

**Cross-stream kerning.** Kerning that moves glyphs across the line rather than along it: up and down in horizontal text.

**Cursive attachment.** GPOS joining one glyph’s exit anchor to the next glyph’s entry anchor, so that connected letters line up across the line.

**Data generators.** The Python scripts in HarfBuzz’s `src/` that turn Unicode and registry data into the C tables committed to the repository, run by hand when the data changes.

**Default ignorable.** A character meant to be invisible unless a font does something with it: a joiner, a soft hyphen, a variation selector. HarfBuzz keeps its own list, and hides them at the end of shaping.

**Detailed messages.** The extra buffer messages, one per lookup and stage, that HarfBuzz emits only when built with `HB_BUFFER_MESSAGE_MORE`.

**Device table.** A table of small corrections attached to a GPOS value or anchor: per pixel size, for hinting, or, as a VariationIndex table, per position in a variable font’s design space.

**dfont.** A classic Mac OS resource fork stored as a plain file, holding one or more OpenType fonts as `sfnt` resources.

**Dispatch context.** The job HarfBuzz passes down a table’s structure: sanitizing, applying, closure, subsetting. Each struct with formats dispatches to the right one, and the context says what to do there.

**DontAdvance.** An AAT state-machine flag that makes the machine look at the same glyph again, bounded in HarfBuzz by the operation budget.

**Dot reph.** The Malayalam reph, written as a dot (log repha), which HarfBuzz places after the base without an `rphf` lookup.

**Dotted circle.** U+25CC, which HarfBuzz inserts as a base for a mark that has none, so that the mark has something to sit on. It does so in four places: at the start of text, for broken syllables, for stray Hangul tone marks, and for the vowel constraints.

**Draw functions.** The callbacks a client gives HarfBuzz to receive an outline: move to, line to, quadratic and cubic curves to, and close path (`hb_draw_funcs_t`).

**Empty blob, empty face.** Static, immutable objects of length zero. A missing or broken table is the empty blob, which reads as the table’s Null object.

**Empty plan.** The shape plan returned when none can be made. Running it does nothing and returns false.

**Extension promotion.** The repacker’s rescue for a lookup out of reach of a 16-bit offset: wrapping its subtables in Extension subtables, whose 32-bit offsets reach anywhere.

**Eyelash RA.** In Devanagari, the form of RA before a virama that a ZWJ asks for, written as a small hook rather than a reph.

**Face.** One font in a font file, without a size. It hands out tables by tag and keeps lazily loaded accelerators for them, and can be shared between threads.

**Face index.** The number that picks a face in a collection (its low 16 bits) and, optionally, a named instance (its high 16 bits, minus one).

**Fallbacks.** What HarfBuzz does itself when a font lacks a table: positioning marks from glyph extents, giving missing spaces a width, and kerning through the font functions.

**feat.** Apple’s table of feature names, for user interfaces. HarfBuzz uses it to decide which requested features a `morx` font supports.

**Feature table substitution.** The part of a FeatureVariations record that swaps a feature’s whole table for another in some region of the design space.

**Feature type and selector.** AAT’s way of naming a feature setting, by two numbers rather than a tag. HarfBuzz maps OpenType tags onto them.

**Final reordering.** The Indic shaper’s second pass, after the basic features: it moves the reph and pre-base vowel signs to their final places, now that conjuncts and half forms are known.

**Fixpoint.** The point where repeating a step changes nothing further. HarfBuzz’s subset closure runs a fixed number of stages instead of iterating to one.

**Font.** A face at a particular scale, with variation coordinates and synthetic settings, and the font functions that answer questions about its glyphs.

**Font extents.** The ascender, descender, and line gap of a font as a whole.

**Font functions.** The table of callbacks a font uses to answer questions about glyphs: which glyph a character maps to, advances, origins, extents, outlines. HarfBuzz’s own are hb-ot.

**Font segmentation.** Splitting a font into pieces that can be loaded separately, as incremental font transfer does; it needs to know which glyphs depend on which.

**Foreground color.** The color of the surrounding text, which a color glyph asks for with palette entry 0xFFFF.

**Fuzzer.** A program that feeds a library endless mutated inputs, looking for crashes, hangs, and runaway memory. HarfBuzz’s run continuously on OSS-Fuzz.

**Global bit.** Bit 31 of each glyph’s mask, shared by every feature that is on for the whole run with value 1.

**Global feature.** A feature applied to the whole run. Global features with value 1 share one mask bit; a feature over a range needs bits of its own.

**Glyph assembly.** In MATH, a recipe for building a very large glyph, such as a tall bracket, from pieces and extenders.

**Glyph closure.** The set of glyphs a font can reach from given characters, through cmap, layout, composites, COLR, MATH, and VARC. The subsetter computes it in a fixed order of stages.

**Glyph dependency graph.** A graph of which glyphs a font can turn into or pull in, each edge labeled with the table that causes it: GSUB lookups, composites, COLR, MATH, VARC. HarfBuzz builds it with hb-depend.

**Glyph extents.** The box around a glyph’s ink, relative to its origin.

**Glyph ID.** A glyph’s number in its font. Glyph 0 is `.notdef`.

**Glyph properties.** HarfBuzz’s record, on each glyph in the buffer, of its GDEF class and of how it got there (substituted, ligated, multiplied).

**Golden-file test.** A test that compares output with a stored expected file, as `test/subset` and `test/vector` do.

**Grade.** Synthetic bold that leaves advances alone, so text doesn’t reflow.

**HarfRust.** The HarfBuzz project’s Rust port of HarfBuzz shaping, reading fonts with Fontations’ `read-fonts`; HarfBuzz can call it as its `harfrust` shaper.

**hb-depend.** HarfBuzz’s experimental API for computing a font’s glyph dependency graph, part of the subset library.

**hb-gpu.** HarfBuzz’s library that encodes glyphs for drawing on the GPU, with the Slug method, and the shaders that draw them.

**HB_LEAN, HB_MINI, HB_TINY.** HarfBuzz’s configuration tiers: one macro each that turns off a group of features. `HB_TINY` sets both of the others, and more.

**hb-raster.** HarfBuzz’s library that turns drawn and painted glyphs into pixels: anti-aliased coverage masks for outlines, and color images for painted glyphs.

**hb-vector.** HarfBuzz’s library that writes drawn and painted glyphs as SVG or PDF. The book’s drawings are made with it.

**Hidden axes.** Design axes that no user sets: avar 2’s, which other axes drive, and VARC components’ own part parameters, set by the glyph that uses the part.

**Hidden (character).** A default ignorable that GSUB must not pass over, because it changes the shaping around it: the Mongolian free variation selectors, TAG characters, and a CGJ that kept marks apart.

**Implied on-curve point.** In a `glyf` outline, the point halfway between two consecutive off-curve points, which TrueType doesn’t store.

**Initial reordering.** The Indic shaper’s first pass over each syllable, before the basic features: it finds the base consonant, moves pre-base vowel signs and the reph, and sets each glyph’s feature masks by its position.

**Instance.** A font made from a variable font at a chosen position (a full instance, with no axes left) or over a narrower range (a partial instance).

**Invertible set.** An `hb_set_t` that can stand for everything except its members, so “all features but these” costs no more than “these”.

**Invisible glyph.** The glyph a hidden default ignorable becomes at the end of shaping: one the application sets, or else the font’s space, with no advance.

**Italics correction.** In MATH, the extra space to add after a slanted glyph before an upright one, so a superscript or the next symbol doesn’t collide with it.

**Jamo.** The letters a Korean syllable is built from: a leading consonant, a vowel, and an optional trailing consonant. Unicode encodes them separately and also as 11,172 precomposed syllables.

**Joining type.** A character’s Unicode property saying which sides it joins on: dual-joining, right-joining, left-joining, join-causing, non-joining, or transparent.

**Kern machine.** HarfBuzz’s loop that applies pair kerning from the `kern` and `kerx` tables and from fallback kerning (`hb_kern_machine_t`).

**kerx.** Apple’s extended kerning table, with 32-bit headers and formats for anchor attachment and class matrices, applied by HarfBuzz in place of GPOS when a font is shaped the AAT way.

**Kinzi.** In Myanmar, a NGA with ASAT and virama written above the next consonant; HarfBuzz moves it after the base, like a reph.

**Language.** What a run of text is written in, given to HarfBuzz as a BCP 47 tag such as `tr`, `ur`, or `zh-Hant`, built from the subtags in [IANA’s registry](https://www.iana.org/assignments/language-subtag-registry). HarfBuzz ignores case and reads `_` as `-` (`hb-common.cc:167`), and maps the tag to OpenType language system tags: `tr` becomes `'TRK '`.

**Language system tag.** OpenType’s name for a language under a script, such as `MAR` or `TRK`, with its own features. Like every OpenType tag it is four bytes: most language system tags are three letters padded with a space (`'TRK '`), and a few use all four (`'ZHTM'`, `'HYE0'`). The tags are [listed in the OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags).

**Lazy loader.** A one-pointer slot on a face that is filled the first time a table or accelerator is asked for, without a lock.

**Leaf.** In VARC, a component drawn from an ordinary outline, in `glyf`, CFF2, or CFF, rather than from more components.

**Legacy kern table.** `kern`, the kerning table that came before GPOS, in Microsoft’s and Apple’s incompatible versions. HarfBuzz applies it only where GPOS has no `kern` feature, and only under some shapers.

**Ligature caret.** A position inside a ligature where a text cursor can stand, from GDEF, so “ffi” can be edited letter by letter.

**Ligature ID and component.** Numbers HarfBuzz gives a ligature and the marks inside it, so each mark knows which part of the ligature it belongs to.

**Ligature set.** In hb-depend, the set of glyphs that must all be present for a ligature edge to apply.

**Limiting.** Narrowing an axis’s range when instancing, so the font keeps the axis but varies over less of it, renormalized to the new range.

**Long metric.** An advance and side bearing pair in `hmtx` or `vmtx`. Glyphs after the last one store only a side bearing and share its advance.

**Lookup.** One set of rules of one type, with flags saying which glyphs it ignores. Features are lists of lookups.

**Map.** The part of a shape plan that turns feature tags into the lookups that run: each with its mask and flags, in stages.

**Mask.** 32 bits on each glyph saying which features are on for it.

**Math kern.** In MATH, kerning for a glyph’s corners that varies with height, for placing superscripts and subscripts.

**Meson.** The build system HarfBuzz uses. A build is set up with `meson setup`, which reads `meson.build` and the options in `meson_options.txt`, and then run with Ninja ([Building HarfBuzz](building-harfbuzz.html#meson-and-ninja)).

**Min/max extents.** In BASE, the highest and lowest a script’s glyphs reach, for a given language, used to set line spacing.

**Modified combining class.** HarfBuzz’s version of Unicode’s combining class, used to sort marks into the order fonts expect for Hebrew, Arabic, Telugu, Thai, and Tibetan.

**Modifier combining mark.** One of the Arabic marks, such as hamza above, that Unicode’s Arabic mark rendering (UTR #53) moves to the front of a run of marks.

**morx.** Apple’s extended glyph metamorphosis table: chains of state-machine subtables that substitute, ligate, insert, and rearrange glyphs. HarfBuzz runs it in place of GSUB.

**Multiple item variation store.** The variation store VARC uses, whose items are lists of numbers that vary together (all of one component’s values), and whose regions name only the axes they use.

**Name record.** One entry in the `name` table: a string for a name ID in one platform, encoding, and language.

**Native order.** The order a script is read in. HarfBuzz reverses a run into it at the start of shaping if it was given in the other direction, so that lookups see text the way fonts are written for.

**Neutering.** What the sanitizer did before HarfBuzz 12.3: writing zero over a bad offset in the font’s bytes, so that the rest of the table could be kept.

**Ninja.** A small, fast build tool that runs the build steps Meson writes out (`ninja -C build`).

**Nominal glyph.** The glyph a font’s `cmap` gives for a character: where shaping starts.

**Normalization.** HarfBuzz’s decomposing, reordering, and recomposing of characters before shaping, done against the font: a character is decomposed only if the font has the pieces, and composed only if it has the result.

**Normalization mode.** How far a script shaper wants HarfBuzz to compose: never, or diacritics onto their bases, with or without first decomposing characters the font already has.

**Not-found glyph.** The glyph used for a character the font doesn’t have: `.notdef`, glyph 0, unless the application sets another.

**Null object.** A read-only, empty instance of a table type, usually all zeros. A zero offset, an out-of-range index, or a missing table reads as one.

**Object graph.** A table being written, seen as objects (subtables) joined by links (offsets). The serializer builds it; the repacker rearranges it.

**Offset.** A number of bytes, counted from some base structure, to another structure in the same table. In HarfBuzz an offset knows the type of its target.

**Old and new Indic tags.** The two generations of OpenType tag for the nine Indic scripts (`deva`, `dev2`), which expect some glyphs in different orders. `dev3` and the other `3` tags, which HarfBuzz and Core Text support but the OpenType registry doesn’t list, send text to the Universal Shaping Engine.

**Old Hangul.** Korean as written before the twentieth century, whose syllables have no precomposed characters and are drawn from jamo glyphs with `ljmo`, `vjmo`, and `tjmo`.

**Output buffer.** The second sequence a buffer writes to while a step reads the first. It shares memory with the input until it would overtake it, then moves into the positions array.

**Override header.** A header named by `HB_CONFIG_OVERRIDE_H` (or `HB_CONFIG_OVERRIDE_LAST_H`, read after the rest) that a build uses to define or undefine HarfBuzz’s configuration macros.

**packTab.** HarfBuzz’s packer for multi-level lookup tables, used by the generators to make the Unicode tables small.

**Paint graph.** How a COLR version 1 glyph is described: a tree of paints (fills, gradients, transforms, clips, composites, other glyphs) that HarfBuzz walks and hands to the client’s paint functions.

**Palette.** A list of colors in the CPAL table. A color glyph refers to entries by index, so one font can be shown in several palettes, chosen by the client.

**Pause.** The end of a stage, where a script shaper may run a function of its own before the next stage’s lookups.

**Phantom points.** Four points HarfBuzz adds to each TrueType glyph, at the ends of its horizontal and vertical advances, so that `gvar` deltas can vary the advances.

**Pinning.** Fixing an axis at one value when instancing, so the axis disappears and its deltas are applied.

**Pipe.** HarfBuzz’s way of chaining iterator steps with `|`, as in `+ glyphs | hb_filter (set) | hb_map (map) | hb_sink (out)`; each step is a function object applied to the iterator before it.

**Point matching.** Placing a `glyf` component by making one of its points coincide with one of the glyph’s earlier points, instead of by an offset.

**ppem.** Pixels per em: the size a font is drawn at on a pixel grid, as the length of its em measured in pixels.

**Presentation form.** A character that encodes a letter already shaped: an Arabic letter in one joining form, or a Hebrew letter with its points. HarfBuzz uses them only for old fonts without layout tables.

**ptem.** The font’s size in points. Read only by `trak`, CoreText, and the reported optical size.

**PUA fallback.** HarfBuzz’s shaping of Thai for old fonts without a `thai` script, by swapping marks and consonants for the private-use glyphs Windows and Mac fonts once drew them with.

**Ragel.** The state-machine compiler HarfBuzz uses for the grammars that find syllables in Indic, Khmer, Myanmar, and USE text.

**Recategorizing.** Replacing marks’ combining classes with the few positional classes fallback mark positioning understands, just before glyphs are mapped.

**Repacker.** The code that reorders, splits, and duplicates a table’s objects when its 16-bit offsets overflow, so the table can still be written.

**Reph.** The form of RA written above the syllable when RA and a virama begin it, moved by the Indic shaper to where the script puts it.

**Required feature.** A feature a language system names by index, whose lookups always run, whatever the application asks for.

**Run.** Text in one font, script, direction, and language: what HarfBuzz shapes in one call.

**rustybuzz.** An earlier Rust port of HarfBuzz shaping, built on ttf-parser, now archived; HarfRust started from it.

**Sanitizer.** The code that checks, once per table, that HarfBuzz can read the table without going outside it. It checks for safety, not validity.

**SARA AM.** The Thai vowel ำ, drawn as a small circle over the consonant and a SARA AA after it. HarfBuzz always splits it into NIKHAHIT and SARA AA.

**Scale.** The number of output units in one em. Everything HarfBuzz returns is in those units.

**Scratch fields (`var1`, `var2`).** Eight private bytes on each glyph, lent to one stage of shaping after another and checked by `HB_BUFFER_ALLOCATE_VAR`.

**Script shaper.** The part of HarfBuzz that knows one family of scripts’ rules: joining, reordering, which features apply to which glyphs.

**Script tag.** OpenType’s four-letter name for a script in a font’s ScriptList, such as `latn` or `dev2`; a few shorter ones are padded with spaces (`'nko '`, <code>'yi&nbsp;&nbsp;'</code>). One Unicode script can have several. The tags are [listed in the OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/scripttags).

**Segment properties.** A buffer’s direction, script, and language.

**Serializer.** HarfBuzz’s writer of font tables, `hb_serialize_context_t`: it builds each table as a graph of objects joined by links, shares identical objects, and resolves the offsets at the end.

**Set digest.** A small, fast summary of a set of glyphs, which can say for certain that a glyph is *not* in the set.

**sfnt.** The container format of TrueType and OpenType fonts: a header, a directory of tables, and the tables.

**Shape plan.** Everything HarfBuzz decides about a run before seeing its text: the script shaper, the feature masks, and the lookups in stages. Made per face, and cached on it.

**Shaper list.** The ordered list of backends a build has. The first that accepts a face shapes it. `HB_SHAPER_LIST` reorders it.

**Sharing.** The serializer writing one copy of an object that several others link to, found by hashing the objects as they are packed.

**Short-circuit.** In normalization, keeping a character the font has without looking at its decomposition.

**Sink.** The last step of a pipe, which stores each item somewhere: a set, a vector, or a serializer.

**Slug.** Eric Lengyel’s method of drawing glyphs directly from their quadratic curves on the GPU, which hb-gpu implements.

**Stage.** A group of lookups run together, between pauses where a script shaper can work on the buffer.

**Standard cluster.** USE’s name for an ordinary syllable: a base with its marks, medials, and finals, matched by its grammar.

**Starter.** In normalization, the last character with combining class zero: the one a following mark may compose with.

**stch.** A feature for Syriac’s abbreviation mark and similar lines, which HarfBuzz stretches to the width of the word by repeating tiles.

**Strike.** One size of bitmap in an sbix or CBDT table. HarfBuzz chooses the strike nearest the font’s ppem.

**Structural limit.** A fixed bound on the shape of the data, such as nesting depth or pattern length, as against a work budget, which bounds how much is done.

**Sub-blob.** A blob that points into another blob’s bytes and keeps it alive. Tables are sub-blobs of the file.

**Sub-font.** A font whose parent is another font. Questions its own font functions don’t answer go to the parent, rescaled.

**Subset plan.** What the subsetter computes before writing anything: which glyphs, characters, lookups, and features survive, and the map from old glyph IDs to new.

**Subsetter.** HarfBuzz’s library for cutting a font down to the characters, glyphs, and features a document needs, `hb_subset_or_fail`.

**Synthetic bold and slant.** Emboldening and shearing applied by the font object to whatever its font functions report, for families without a real bold or italic.

**Tagged Null.** A Null object’s address with its lowest bit set, stored in a lazy slot when building an accelerator failed, so that the failure isn’t retried.

**Tent.** A region of the design space along one axis: zero at its start and end, full at its peak. Deltas apply in proportion to how far into the tent a location is.

**Top accent attachment.** In MATH, the horizontal position over a glyph where an accent is centered; HarfBuzz returns half the advance when the font gives none.

**Top to bottom (TTB).** HarfBuzz’s direction for vertical text. A bottom-to-top run is turned into it at the start of shaping, and stays in it.

**trak.** Apple’s tracking table: letter-spacing that varies with point size, which HarfBuzz reads at the font’s ptem.

**TrueType Collection (TTC).** A file holding several fonts, each with its own table directory, which can share tables.

**Unicode funcs.** The table of callbacks a buffer uses to ask about characters: general category, combining class, mirroring, script, composition, and decomposition.

**Unicode properties.** Sixteen bits HarfBuzz keeps on each glyph for the whole of shaping: its general category, ignorable, hidden, and continuation bits, and a byte whose meaning depends on the category.

**Universal Shaping Engine (USE).** Microsoft’s shaping model for scripts that have no shaper of their own, driven by Unicode character properties: in effect the Indic model with most of its script-specific rules taken out.

**Unsafe to break.** A glyph flag saying the run can’t be cut at the start of this glyph’s cluster and shaped in two parts without changing the result.

**Unsafe to concat.** A glyph flag saying that changing the text on one side of this cluster’s start could change the result on the other. Recorded only when the buffer asks for it.

**Upright and sideways.** The two ways a run sits in a vertical line. HarfBuzz shapes vertical runs upright; text set sideways is shaped as horizontal text and rotated by the application.

**Value record.** In GPOS, up to eight numbers or Device-table offsets that move a glyph or change its advance. A ValueFormat says which are stored.

**VARC.** The variable composites table: glyphs built from components, each placed with a full transform and drawn at its own position in the design space.

**Variation selector.** A character that follows another to ask for a particular form of it, through the font’s `cmap` format 14.

**Vendoring.** Keeping a copy of a library’s source in a project’s own tree and building it with the project, as most of HarfBuzz’s users do.

**Vertical origin.** The point a glyph hangs from in vertical text, usually centered above it.

**Vertical presentation form.** A character such as U+FE35, a parenthesis drawn for vertical text. HarfBuzz substitutes these itself in vertical runs, but only when the font has no `vert` feature.

**Visual order.** The order glyphs are drawn in, left to right. HarfBuzz returns its output in visual order, reversing right-to-left runs as the last step of positioning.

**Vowel constraints.** Microsoft’s list of sequences, such as an independent vowel followed by a vowel sign, that would look like another letter. HarfBuzz breaks them with a dotted circle, against spoofing.

**Whence.** Where a serializer link’s offset is counted from: the start of the parent object (head), its end (tail), or the start of the table (absolute).

**Work budget.** The number of operations HarfBuzz will spend drawing or painting, 2²⁵ per glyph, so that no font can make it draw for ever.

**Zawgyi.** A font encoding for Burmese that uses the Myanmar code points in its own way. HarfBuzz shapes it, as the private script `Qaag`, with a shaper that does almost nothing.
