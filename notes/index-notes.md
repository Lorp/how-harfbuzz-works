# Index notes

Decisions about the book’s indexes, kept by hand. `tools/index-terms.mjs` gathers candidate terms from the chapters into `index-terms.md`; this file says what to do with them. Page numbers, or links, come later.

There are two indexes:

* the **general index**: concepts, and OpenType table and feature tags (`GSUB`, `hmtx`, `liga`), which type designers look up as words;
* the **code index**: HarfBuzz’s own names: API functions, types and macros, internal structs, and source files.

A concept with a code name gets an entry in each, pointing at each other: “cluster level” in the general index, `hb_buffer_cluster_level_t` in the code index.

## How the indexes are built

`tools/build-site.mjs` builds both indexes (`book/end/index.md`, `book/end/code-index.md`) from the chapters and appendices, using `tools/index-lib.mjs`:

* Terms are the bold definitions and the code spans that name tags, API, types and files; this file adds variant forms, other names and “see also”s.
* Every paragraph, heading, list item or table cell that mentions a term is a place it can cite. Each entry cites one place per section: the chapter named for it, its definition (in bold) and headings that name it first, then the sections that mention it most; twelve at most, six for a term found in most chapters. “Where to read the source” and “In short” sections are skipped.
* A two- or three-word concept is also filed inverted (“components, variable”), as are other names given here.
* On screen a place is a link labelled chapter.section; `tools/build-pdf.mjs` prints the book once without the indexes to find each place’s page, then prints it with the page numbers.

To drop a bold run that isn’t a term, add it under “Not index terms”; to merge forms or add cross-references, add it under “Main entries and synonyms”.

## Not index terms

Bold runs that label a list item or table cell rather than define a term. `tools/index-terms.mjs` leaves these out. One per line, exactly as bolded.

* Harf
* Buzz
* Left
* Overrides replace some categories
* Two positions are overridden
* Unicode’s positional category becomes a position
* Unicode’s syllabic category becomes HarfBuzz’s category
* User features with a range
* carry on, check once
* After positioning
* At the very end
* In GSUB and GPOS matching
* BOT and EOT
* The default-ignorable flags
* Safe to break is safe
* Safe to concat is safe
* Graphemes
* Monotone
* match: YES
* match: MAYBE
* match: NO
* Bytes
* HarfBuzz C++
* spec-like
* TTX
* feature file
* Caret slope
* Contour points
* Extents
* default
* nil
* no
* zero
* Version 2
* 16.16
* 2.14
* HarfBuzz
* Core Text
* DirectWrite
* CoreText
* in font units

## Main entries and synonyms

One entry, the other forms pointing at it.

* **cluster**: see also cluster level, merging clusters (“merges”)
* **feature** (“features”)
* **long metric** (“long metrics”): also `numberOfHMetrics`, `numberOfLongMetrics`
* **named instance** (“named instances”): also face index
* **normalized coordinates** (“normalized”): see also design space, user coordinates
* **Null object** (“Null”): see also empty blob, tagged Null, `Crap`
* **phantom points**: also top phantom point; see also `gvar`, HVAR
* **script shaper**: not the same as backend (“backend shaper”)
* **glyph extents** (“extents”, “glyph’s extents”): see also font extents
* **pixels per em** (“Pixels per em”): also ppem
* **point size** (“Point size”): also ptem
* **scale** (“Scale”)
* **modified combining class** (“modified combining classes”)
* **stage** (“stages”)
* **item variation store**: see also multiple item variation store, delta-set index map, varStore cache
* **map** (`hb_ot_map_t`): see also shape plan; **map builder** (`hb_ot_map_builder_t`)
* **global bit**: see also mask
* **pause**, pause function: see also stage
* **required feature**: also `requiredFeatureIndex`, `hb_ot_layout_language_get_required_feature`
* **Harf, Buzz**: under their own entry and under “features, private”
* **feature table substitution**: see also FeatureVariations
* **lookup variations**: also `LookupVariationRecord`, FeatureVariations 1.1
* **feature flags** (`hb_ot_map_feature_flags_t`); `F_GLOBAL_SEARCH`: see `vert`
* **mask bits, running out of**: see also Limits (appendix)
* **script tag**: see also language system tag, chosen script
* **chosen script**: code index `chosen_script`, `found_script`
* **private-use subtags** (`-x-hbsc`, `-x-hbot`, hbsc, hbot): code index `parse_private_use_subtag`
* **Zawgyi**: see also `Qaag`, `myanmar_zawgyi`
* **old Indic tags**, **new Indic tags** (HarfBuzz’s “old-spec”, “new-spec”): code index `is_old_spec`
* **dumber shaper**: see also AAT
* **script shaper**: see also `hb_ot_shaper_categorize`
* **the pipeline** (`hb_ot_shape_internal`)
* **continuation**: see also grapheme, `hb_form_clusters`
* **native order**: see also visual order, `hb_ensure_native_direction`
* **visual order**: see also `hb_buffer_reverse`
* **mirroring**: see also `rtlm`, Bidi_Mirroring_Glyph
* **zero-width marks**: see also `zero_width_marks`, early, late
* **default ignorables, hiding**: see also invisible glyph
* **normalization mode** (`normalization_preference`): see also short-circuit, shortest mode
* **`normalizer_glyph_index`**: see also `hb_ot_map_glyphs_fast`, cmap lookup
* **starter**, **blocked**: see each other; see also modified combining class
* **partial composition**: see also recomposition (“compose” in traces)
* **space fallback**: see also Fallbacks, `space_fallback_type`
* **not-found glyph**: also `.notdef`, `hb_buffer_set_not_found_glyph`
* **singleton decomposition**: see also canonical decomposition
* **kerning**: see pair adjustment; **class kerning** (PairPos format 2); **kerning exceptions** (PairPos format 1); see also legacy `kern`
* **value record** (ValueFormat); **Device table**: see also VariationIndex
* **anchor**: see also entry anchor, exit anchor; **cursive attachment**: see also RightToLeft flag
* **attachment, resolving** (`attach_chain`, `attach_type`, `propagate_attachment_offsets`)
* **mark-to-mark** (`mkmk`); **mark-to-base** (`last_base`)
* **top to bottom** (TTB, `HB_DIRECTION_TTB`); **bottom to top** (BTT, `HB_DIRECTION_BTT`)
* **`vert`**: see also `F_GLOBAL_SEARCH`, vertical presentation forms, `vertical_char_for`; **`vrt2`**: see also `vert`, `vrtr`; **`vkrn`**: see also `kern`, legacy kern
* **vertical presentation forms** (vertical forms): see also `hb_ot_rotate_chars`
* **sideways text**: see also upright, Vertical_Orientation
* **fallback mark positioning**: see also mark zeroing, GPOS mark attachment, glyph extents; **recategorizing**: see also combining class
* **space fallback**: see also EM SPACE, THIN SPACE, NARROW NO-BREAK SPACE, figure space
* **fallback kerning** (`glyph_h_kerning`): see also hb-ft, Type 1 fonts, legacy `kern`
* **`fallback` backend**: not the same as fallbacks
* **legacy kern** (`kern` table, TrueType kern); **Apple kern** (`kern` version 1.0); **kern machine** (`hb_kern_machine_t`)
* **cross-stream**: see also `kerx`, AAT positioning; `fallback_position`: see also Fallbacks; `dist`: see also issue #5607
* **presentation forms** (Hebrew, Arabic): see also Joining scripts, PUA
* **SARA AM**: see also NIKHAHIT, SARA AA, Lao SARA AM; **PUA fallback** (Thai): see also private use area
* **jamo**: see also conjoining jamo, L/V/T, `ljmo`/`vjmo`/`tjmo`; **precomposed syllables** (Hangul); **Old Hangul**: see also `KOH`, Middle Korean (`okm`)
* **tone marks** (Hangul): see also dotted circle; **meteg**: see also modified combining classes
* **virama** (halant); **matra** (vowel sign); **reph** (repha); **pref** (pre-base-reordering consonant)
* **base consonant**: see also `would_substitute`, probe; **syllable byte**: see also class cache; **scanner**: see Ragel; **broken cluster**: see also dotted circle
* **joining type** (Joining_Type; D, R, L, C, U, T): see also joining group
* **modifier combining marks**: see also UTR #53, `reorder_marks`; **`stch`**: see also Syriac abbreviation mark (U+070F), tiles
* **Alaph**: see also `fin2`, `fin3`, `med2`; **Windows-1256**: see also legacy Arabic fonts; **FVS**: see Mongolian free variation selectors
* **paint API** (`hb_paint_funcs_t`): see also draw API, font functions; **COLR v0** (colour layers); **COLR v1** (paint graph)
* **palette**: see CPAL; **foreground colour**: see also `is_foreground`, 0xFFFF; **ClipBox**, ClipList: see also glyph extents, boundedness
* **colour line**: see also extend mode, gradients; **strike**: see also ppem, sbix, CBDT; **decycler** (`hb_decycler_t`): see also cycles
* **draw funcs** (`hb_draw_funcs_t`); **point matching** (anchored components): see also anchor points; **implied on-curve point**: see also quadratic curve
* **cubic glyf**: see GLYF, boring expansion; **seac** (standard encoding accented character); **charstring**: see also CFF, CFF2, subroutines, blend, vsindex
* **work budget**: see also limits, `HB_BUDGET_GLYPH`
* **COENG**: see also virama, subscript; **kinzi**: see also reph; **`cfar`** (conjunct form after Ro); **split vowel sign**: see also two-part vowel sign, decomposition
* **Khmer, Myanmar consonant syllable**: see also consonant syllable (Indic); **non-Khmer, non-Myanmar cluster**: see also non-Indic cluster; **`mym2`**: see also Zawgyi
* **dot reph** (log repha): see also reph mode; **ya-phalaa**: see also ZWJ before a virama; **chillu**: see also half form (Malayalam)
* **pre-base-reordering consonant**: see also “pref didn’t form”; **`vatu`**: see also below-base form, probe; **eyelash RA**: see also ZWJ
* **USE** (Universal Shaping Engine): see also Indic model, `dev3`, Ragel; **standard cluster**: see also syllable (Indic), broken cluster
* **VARC** (variable composites, variable components): see also smart components, composite glyph; **hidden axes**: see also avar version 2, `AXIS_FLAG_HIDDEN`
* **`RESET_UNSPECIFIED_AXES`**: see also parent’s coordinates; **`HBUINT32VAR`** (variable-length integer); **`TupleValues`**: see also packed deltas (gvar)
* **dotted circle** (U+25CC): see also broken cluster, vowel constraints, BOT, `DO_NOT_INSERT_DOTTED_CIRCLE`; **broken cluster** (broken syllable)
* **vowel constraints** (invalid cluster, `Indic_Shaping_Invalid_Cluster`, vowel letter spoofing); **repha**: see reph
* **rasterizer**: see hb-raster; **analytic coverage**: see also flattening, nonzero winding rule; **Slug**: see hb-gpu, bands, cu2qu; **cu2qu**: see also quadratic curve
* **draw context**, **paint context**: see also draw funcs, paint funcs; **SVG id prefix** (`hb_vector_paint_set_svg_prefix`); **PDF output**: see hb-vector; **composite modes**: see also PaintComposite
* **`kerx`** (extended kerning table); **`ankr`** (anchor point table); **`trak`** (tracking table); **letter-spacing**: see tracking
* **marked glyph**: see also mark attachment, `kerx` format 4; **control point**: see also anchor format 2, `glyph_contour_point`; **ptem**: see also `trak`
* **selector** (AAT setting); **sub-feature flags**: see also default flags, feature entries; **DontAdvance**: see also `max_ops`
* **deleted glyph** (AAT): see also `_AAT_DELETED`, hidden glyphs; **Rearrangement**: see also reordering; **Insertion**: see also dotted circle
* **`mort`**: see also `morx`; **`feat`**, **`ltag`**; **state machine**: see also legacy `kern` format 1, `kerx`
* **glyph dependency graph** = hb-depend; see also glyph closure, subsetting; **depend context** (`hb_depend_context_t`): see also dispatch contexts
* **context set**: see also ligature set, chained context; **font segmentation**: see also incremental font transfer; **`HB_EXPERIMENTAL_API`**: see also experimental API
* **glyph closure**: see also closure (GSUB), hb-depend; **bidi closure**: see also mirroring; **fixpoint** = fixed point; **subset plan** = plan
* **retain-gids** (`HB_SUBSET_FLAGS_RETAIN_GIDS`); **preprocessing** (`hb_subset_preprocess`): see also subset accelerator; **pass-through tables** = no-subset tables
* **vector** = `hb_vector_t`; **array view**, **span** = `hb_array_t`; **hash map** = `hb_hashmap_t`, `hb_map_t`; **bit set** = `hb_bit_set_t`, see also `hb_set_t`; **page** (of a set): see also major
* **pipe**, **`|` operator** = iterators; **sink** (`hb_sink`); **predicate**, **projection**: see also `hb_filter`, `hb_map`; **`hb_set_t`**: see also set digest (distinct); **`HB_FUNCOBJ`** = function objects
* **detailed messages** = `HB_BUFFER_MESSAGE_MORE`; **fuzzer** = libFuzzer, see also OSS-Fuzz, ClusterFuzz, corpus; **verification**: see also `HB_BUFFER_FLAG_VERIFY`, `--verify`, safe to break; **test line**: see `.tests` file; **failing allocator** (`failing-alloc.c`): see also `HB_CUSTOM_MALLOC`; **golden-file test**: see also `test/vector`, `test/subset`
* **italics correction** = italic correction; **top accent attachment**: see MATH; **math kern** = cut-in; **glyph assembly**: see also glyph variants, extender; **min/max extents**: see also BASE, font extents; **name record**: see also `ltag`, `name`; **baseline tags** (`romn`, `hang`, `ideo`, `idtp`, `icfb`, `icft`, `math`); **`hb_style_get_value`**: see also STAT, OS/2, `post`, synthetic slant, `ptem`
* **instancing** = instantiation, partial instancing; see also subsetting, `rebase_tent`, IUP, avar 2, FeatureVariations; **full instance** = static instance; **gain** = constant delta; **renormalize**: see also normalized coordinates
* **ligature caret**: see also cluster, GDEF; **unsafe to break**, **unsafe to concat**: see also line breaking, `--verify`, reshaping; **context**: see also pre-context, `item_offset`; **itemization**: see also segment properties, font fallback; **justification**: see also tatweel, `hb_shape_justify`, `stch`; **hyphenation**: see also unsafe to concat
* **HarfRust**, **HarfRuzz**: see HarfRust; see also `harfrust` backend, rustybuzz; **Skrifa**, **read-fonts**: see also fontations; **vendoring** = bundled HarfBuzz; **harfbuzzjs** = hb.js; **uharfbuzz**; **Chromium**, **Blink**, **Skia**, **minikin** (see Android), **Pango**, **LibreOffice**, **Qt**, **OpenJDK** (JEP 258), **Godot**
* **configuration macros**, **compile-time options**: see `HB_NO_*`; **tiers**: see `HB_TINY`, `HB_LEAN`, `HB_MINI`; **-Os**, `__OPTIMIZE_SIZE__`: see `HB_OPTIMIZE_SIZE`; **config-override.h**: see override header; **debug output**: see `HB_DEBUG_*`, see also buffer messages; **thread safety**: see also `HB_NO_MT`; **hb-features.h**: see also `HB_HAS_*`
* **structural limit**: see also work budget, `max_ops`; **`max_ops`** (buffer) and **`max_ops`** (sanitizer): see each other; **`successful`**: see also limits; **limits**: see also sanitizer, DontAdvance, closure
* **data generators**: see also packTab, Ragel, `update-unicode-tables.make`; **UCD** = Unicode Character Database, see also `hb-ucd-table.hh`; **ms-use** = Microsoft USE data, see also USE, vowel constraints; **category overrides**: see also Indic categories, USE categories; **build helpers**: see also amalgamation
* **symbol cmap** ((3,0) subtable): see also `cmap`, legacy encodings; **custom glyph map** (`--gid-map`): see also glyph map, `RETAIN_GIDS`
* **serializer** = `hb_serialize_context_t`; **sharing** = deduplication, see also object index; **link**: see also virtual link, whence, bias
* **repacker** = overflow resolution, see also offset overflow, Extension; **object graph**: see also topological order, distance, priority, spaces; **Extension promotion**: see also Extension lookup; **subtable splitting**; **face builder**: see also serializer
* **topographical features** (`isol`, `init`, `medi`, `fina`) in USE: see also joining scripts; **`CGJ` category** (USE): see also ZWJ, variation selectors

## Conventions for writers

* Bold marks a term where it is defined, and nothing else.
* A bold label on a paragraph or list item ends with its full stop inside the bold (“**In the font.**”), so it can be told apart from a definition.
* Report, with each chapter, any synonyms or “see also” links its terms need here.
