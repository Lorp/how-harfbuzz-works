# Bibliography

## Specifications

* Microsoft, *OpenType specification*, version 1.9.1: <https://learn.microsoft.com/en-us/typography/opentype/spec/>
* ISO/IEC 14496-22, *Open Font Format*. The 5th edition adds the “beyond 64k” formats and extended collection headers.
* Microsoft, *Developing OpenType fonts* for particular scripts (Arabic, Devanagari and the rest), and the *Universal Shaping Engine* introduction: <https://learn.microsoft.com/en-us/typography/script-development/standard>
* Microsoft, *Creating and supporting OpenType fonts for the Universal Shaping Engine*: <https://learn.microsoft.com/en-us/typography/script-development/use>, with its data files in Microsoft’s font-tools repository
* Microsoft, *Developing OpenType Fonts for Khmer Script* and *Creating and Supporting OpenType Fonts for Myanmar Script*: <https://learn.microsoft.com/en-us/typography/script-development/khmer>, <https://learn.microsoft.com/en-us/typography/script-development/myanmar>
* Apple, *TrueType Reference Manual*, including the AAT tables (`morx`, `kerx`, `ankr`, `trak`, `feat`, `ltag`) and the TrueType rasterizer’s phantom points: <https://developer.apple.com/fonts/TrueType-Reference-Manual/>
* Microsoft, OpenType *kern* table: <https://learn.microsoft.com/en-us/typography/opentype/spec/kern>, and Apple, *TrueType Reference Manual*, the `kern` table
* Adobe, *The Type 2 Charstring Format*, Technical Note #5177
* Apple, *Inside Macintosh: More Macintosh Toolbox*, the “Resource Manager” chapter, for dfont files.
* The Unicode Consortium, *The Unicode Standard*, with UAX #9 (bidirectional text) and UAX #29 (text segmentation): <https://www.unicode.org/versions/latest/>
* The Unicode Consortium, UTR #53, *Unicode Arabic Mark Rendering*: <https://www.unicode.org/reports/tr53/>
* The Unicode Consortium, UAX #50 (vertical text layout): <https://www.unicode.org/reports/tr50/>
* The Unicode Consortium, UAX #44 (the Unicode Character Database), UAX #15 (normalization forms: NFC, NFD, starters and blocking) and UTS #51 (emoji): <https://www.unicode.org/reports/>
* Microsoft, OpenType *Script tags* and *Language system tags* registries: <https://learn.microsoft.com/en-us/typography/opentype/spec/scripttags>, <https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags>
* IANA, *Language Subtag Registry*: <https://www.iana.org/assignments/language-subtag-registry>
* W3C, *Compositing and Blending Level 1*, which COLR version 1’s composite modes follow: <https://www.w3.org/TR/compositing-1/>
* fontTools, `Lib/fontTools/ttLib/tables/otBase.py`: the `USE_HARFBUZZ_REPACKER` option, which writes GSUB and GPOS through HarfBuzz’s repacker by way of uharfbuzz: <https://github.com/fonttools/fonttools/blob/4.38.0/Lib/fontTools/ttLib/tables/otBase.py>
* HarfBuzz, `docs/serializer.md` and `docs/repacker.md`: <https://github.com/harfbuzz/harfbuzz/tree/15.1.0/docs>
* Behdad Esfahbod, “HarfBuzz Study: Introducing HarfRust”, 10 June 2025: <https://docs.google.com/document/d/1aH_waagdEM5UhslQxCeFEb82ECBhPlZjy5_MwLNLBYo/preview>
* HarfRust: <https://github.com/harfbuzz/harfrust>; rustybuzz: <https://github.com/harfbuzz/rustybuzz>; Fontations: <https://github.com/googlefonts/fontations>
* D. Röttsches, R. Sheeter, C. Brokaw, “Memory safety for web fonts”, Chrome for Developers, 19 March 2025: <https://developer.chrome.com/blog/memory-safety-fonts>
* The users’ sources read for chapter 42: Chromium (<https://chromium.googlesource.com/chromium/src/>), Skia (<https://github.com/google/skia>), Firefox (<https://github.com/mozilla-firefox/firefox>), Android (<https://android.googlesource.com/>), Pango (<https://github.com/GNOME/pango>), LibreOffice (<https://github.com/LibreOffice/core>), Qt (<https://github.com/qt/qtbase>), OpenJDK and JEP 258 (<https://github.com/openjdk/jdk>, <https://openjdk.org/jeps/258>), Godot (<https://github.com/godotengine/godot>); harfbuzzjs (<https://github.com/harfbuzz/harfbuzzjs>) and uharfbuzz (<https://github.com/harfbuzz/uharfbuzz>)
* fontTools, `varLib.instancer` and its `solver.py`, which HarfBuzz’s instancer ports, and `varLib/iup.py`: <https://github.com/fonttools/fonttools/tree/main/Lib/fontTools/varLib/instancer>
* HarfBuzz, `AVAR2-INSTANCING.md`: <https://github.com/harfbuzz/harfbuzz/blob/15.1.0/AVAR2-INSTANCING.md>
* Unicode, UAX #14, *Unicode Line Breaking Algorithm*: <https://www.unicode.org/reports/tr14/>
* Microsoft, OpenType specification, the MATH, BASE, STAT, `name`, `meta` and OS/2 chapters, and the baseline tag registry: <https://learn.microsoft.com/en-us/typography/opentype/spec/>
* W3C, *CSS Inline Layout Module Level 3*, baseline synthesis: <https://www.w3.org/TR/css-inline-3/>
* Chromium, `open_type_math_support.cc`, and Firefox, `gfxMathTable.cpp`: users of HarfBuzz’s MATH API
* HarfBuzz issue #4653, the Cambria Math constants: <https://github.com/harfbuzz/harfbuzz/issues/4653>
* Adobe, Annotated OpenType Specification tests (AOTS): <https://github.com/adobe-type-tools/aots>
* LLVM, libFuzzer: <https://llvm.org/docs/LibFuzzer.html>; Google, OSS-Fuzz: <https://github.com/google/oss-fuzz>
* HarfBuzz issue #2283, composition and decomposition in the subsetter’s character closure: <https://github.com/harfbuzz/harfbuzz/issues/2283>
* Unicode Character Database, the files HarfBuzz’s generators read (UnicodeData, Scripts, ArabicShaping, Blocks, DerivedCoreProperties, IndicSyllabicCategory, IndicPositionalCategory): <https://unicode.org/Public/UCD/latest/ucd/>; and in XML: <https://unicode.org/Public/UCD/latest/ucdxml/>
* Unicode emoji data, `emoji-data.txt` and `emoji-test.txt`: <https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt>, <https://www.unicode.org/Public/emoji/latest/emoji-test.txt>
* Ragel 6.10, the state-machine compiler HarfBuzz’s syllable machines are built with: <https://www.colm.net/files/ragel/ragel-6.10.tar.gz>
* Unicode, *text-rendering-tests*, the shared shaping tests that HarfBuzz’s `TestAATMort.ttf` and `MORX-*` fonts come from: <https://github.com/unicode-org/text-rendering-tests>
* Adobe, *OpenType Feature File Specification*: <https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html>

## HarfBuzz

* HarfBuzz source code, version {{hb}}: <https://github.com/harfbuzz/harfbuzz/tree/{{hb}}>. Its `NEWS` file is the project’s own history, release by release.
* HarfBuzz, *User manual*: <https://harfbuzz.github.io/>
* Behdad Esfahbod, *HarfBust*, a puzzle font that shapes differently in each engine, 2025: <https://behdad.github.io/harfbust/>
* Behdad Esfahbod, on how Core Text, DirectWrite and HarfBuzz handle invalid offsets, HarfBuzz issue #5535, 25 November 2025: <https://github.com/harfbuzz/harfbuzz/issues/5535#issuecomment-3573738217>
* HarfBuzz, `docs/wasm-shaper.md`, the WebAssembly shaper, with examples at <https://github.com/harfbuzz/harfbuzz-wasm-examples>
* HarfRust: <https://github.com/harfbuzz/harfrust>
* packTab, the table packer used for HarfBuzz’s Unicode data: <https://github.com/harfbuzz/packtab>
* Theppitak Karoonboonyanan, *Thai shaping*, cited in HarfBuzz’s Thai shaper: <https://linux.thai.net/~thep/th-otf/shaping.html>
* SBL Hebrew Font User Manual, cited in `hb-unicode.hh` for the order of Hebrew points
* Nathan Willis, *OpenType shaping documents*, the shaping models script by script: <https://github.com/n8willis/opentype-shaping-documents>

## Other software

* fontTools: <https://github.com/fonttools/fonttools>
* FreeType: <https://freetype.org/>
* Fontations (the read-fonts and skrifa crates): <https://github.com/googlefonts/fontations>
* Ragel, the state-machine compiler HarfBuzz’s syllable grammars are written for: <https://www.colm.net/open-source/ragel/>
* Eric Lengyel, the Slug algorithm for rendering glyphs on the GPU: <https://github.com/EricLengyel/Slug>
* SIL, Graphite: <https://graphite.sil.org/>
* WebAssembly Micro Runtime, which the `wasm` backend runs modules with: <https://github.com/bytecodealliance/wasm-micro-runtime>

## Books

* Yannis Haralambous, *Fonts & Encodings*, O’Reilly, 2007.
