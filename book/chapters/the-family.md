# The family

The rest of this book has looked inside one program. This chapter looks around it: at the Rust port that the HarfBuzz project now maintains next to the C++ library, at a few smaller relatives, and at how some of the best-known programs that use HarfBuzz actually call it.

Everything here is about software other than HarfBuzz {{hb}}, so none of it can be checked against the code in `.cache/harfbuzz/` or shown live: the book’s build doesn’t include the `harfrust` backend, and it can’t run a browser. Each claim is taken from the other project’s own repository, documentation or announcement, linked where it is made, and read in November 2026. Repositories move on, so a version number given here is the one that was there when it was read.

## HarfRust

**HarfRust** is, in its [README](https://github.com/harfbuzz/harfrust)’s words, “a Rust port of HarfBuzz text shaping engine”. It is a library of its own, published as the `harfrust` crate, and also one of HarfBuzz’s optional backends ([hb_shape and its backends](hb_shape-and-its-backends.html) covers the backend).

### Where it came from

Behdad Esfahbod’s study [Introducing HarfRust](https://docs.google.com/document/d/1aH_waagdEM5UhslQxCeFEb82ECBhPlZjy5_MwLNLBYo/preview), dated 10 June 2025, gives the history. It lists earlier attempts at shaping in Rust: harfbuzz_rs, a safe Rust interface to the C++ library rather than a port; Allsorts, a separate implementation by YesLogic; swash; and RustyBuzz.

**rustybuzz** was a port of HarfBuzz to Rust by Yevhenii Reizner, built on his own font parser, ttf-parser, and “initially written to fulfill a need by resvg”, his SVG renderer. The study quotes him giving the project up in August 2023, and says Laurenz Stampfl then brought it from HarfBuzz 2.7.1 up to 10.1.0. Its [README](https://github.com/harfbuzz/rustybuzz) now begins: “This project is not developed further, unmaintained, and archived”, and recommends HarfRust instead.

Google Fonts wanted the same port to read fonts with its own Rust crates, [fontations](https://github.com/googlefonts/fontations), so that programs using its font reader **Skrifa** would not carry two implementations of font parsing (the HarfRust README says this, and points to [fontations issue 956](https://github.com/googlefonts/fontations/issues/956)). The study says that when no agreement was reached with rustybuzz’s author in 2024, Chad Brokaw started a fork, first called HarfRuzz, and that it was renamed HarfRust because the earlier name looked too much like HarfBuzz. Behdad Esfahbod started contributing in May 2025 and brought it up to date with HarfBuzz 11.2.1, and the fork dropped ttf-parser for fontations’ `read-fonts`. The study ends: “HarfRust is an official HarfBuzz project”, developed by Chad Brokaw of the Google Fonts team with Behdad Esfahbod’s contributions, then under contract with Google Fonts.

The name is a pun, as HarfBuzz’s is. The study explains *rāst* (راست) as Persian for “true”, “right” or “honest”: “Type–True”, a nod to TrueType, beside HarfBuzz’s “Type–Open”.

### Keeping up with HarfBuzz

The study is clear about which project leads: “Until further notice, all development will primarily happen in HarfBuzz, with the intention to quickly bring HarfRust up to date with each and every HarfBuzz release.” The [changelog](https://github.com/harfbuzz/harfrust/blob/main/CHANGELOG.md) shows that happening. Every release names the HarfBuzz release it matches:

| HarfRust | Released | Matches HarfBuzz |
|---|---|---|
| 0.1.0 | 10 June 2025 | 11.2.1 |
| 0.5.0 | 7 January 2026 | 12.3.0 |
| 0.13.3 | 25 August 2026 | 14.3.1 |
| 0.15.0 | 21 October 2026 | 15.0.0 |
| 0.16.0 | 11 November 2026 | 15.1.0 |

HarfBuzz 15.1.0 was released on 4 November 2026 (`NEWS`), so HarfRust caught up a week later. The two projects also share their generated data: HarfBuzz’s table generators have a `--rust` mode that writes HarfRust’s copy of the same tables ([The Universal Shaping Engine](the-universal-shaping-engine.html), [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html)).

The changelog also shows the differences being closed one by one. rustybuzz’s README lists things it never did: no `mort` table, and no Arabic fallback shaping, because building lookups on the fly needs “serialization code that is associated with subsetting”. HarfRust 0.13.3 added both: “Add support for shaping legacy AAT `mort` tables” and “Synthesize Arabic fallback GSUB lookups” ([Joining scripts](joining-scripts.html#shaping-without-gsub) describes what HarfBuzz does there). 0.15.0 added fonts with more than 65,535 glyphs.

### What it covers

The README divides HarfBuzz into six parts and says what became of each in HarfRust:

1. shaping, ported;
2. Unicode routines, ported;
3. font parsing, done by `read-fonts`;
4. subsetting, done by skera, the fontations subsetter;
5. HarfBuzz’s own containers and utilities, reimplemented in fontations where needed;
6. glue for system and third-party libraries, not ported.

So HarfRust has no FreeType, Core Text, DirectWrite, ICU or GLib integration, and no Graphite. It has no font size either: “Shaping is always using UnitsPerEm. You should scale the result manually.” A malformed font is an error, where HarfBuzz would shape anyway. And, the README says, “Experimental HarfBuzz features like most of the boring-expansion-spec are not supported yet.”

How close it is comes from [HARFBUZZ.md](https://github.com/harfbuzz/harfrust/blob/main/HARFBUZZ.md), which runs HarfBuzz’s own test suites through the backend with `HB_SHAPER_LIST=harfrust`. On 24 August 2026 that gave 800 of 800 AOTS tests, 437 of 437 text-rendering-tests and 5,012 of 5,021 in-house tests, the nine failures all Arabic fallback shaping, which 0.13.3 added the next day. On speed, the README says that “HarfRust is less than 25% slower than HarfBuzz on most common fonts”. A year earlier the study had it “over 3x slower than HarfBuzz for major workloads”, with a plan to port HarfBuzz’s caches. On safety: “There are no `unsafe` in this library and in most of its dependencies (excluding `bytemuck`).”

> For programmers: HARFBUZZ.md says HarfBuzz builds HarfRust from its git `main` branch. In 15.1.0 that line is commented out, and `src/rust/Cargo.toml` asks for the published crate, `harfrust = { version = "0.15.0" }`. That release matches HarfBuzz 15.0.0, not 15.1.0.

### A C API

Since 0.14.0, HarfRust also has a C library, [`harfrust_capi`](https://github.com/harfbuzz/harfrust/blob/main/harfrust_capi/README.md). It mirrors the shaping half of HarfBuzz’s API with an `hr_` prefix: “Every type, function, enumerator and constant is named and numbered to match its HarfBuzz counterpart, so C code can usually be ported by renaming `hb_` to `hr_`.” A header, `hr-hb.h`, maps HarfBuzz’s own names onto HarfRust’s, so that HarfBuzz shaping code can build against HarfRust unchanged. Later releases added drawing and painting backed by Skrifa, and subsetting backed by skera. The README lists what is left out, including custom Unicode funcs, buffer message callbacks and `hb_buffer_diff`, and one deliberate difference: “Allocation failure aborts” instead of being reported. Through this header, `HB_VERSION_STRING` gives the HarfBuzz release HarfRust matches, currently 15.1.0, though the README warns that this “does not imply that every API from that HarfBuzz release is available”.

## Other relatives

`fontations` is the font-funcs backend that reads fonts with fontations’ Rust crates ([Fonts and font functions](fonts-and-font-functions.html#the-other-funcs)). The crates are a project of their own at Google Fonts. Their [README](https://github.com/googlefonts/fontations) describes `read-fonts` as “intended to be a high performance parser, suitable for shaping”, one that “performs no allocation and no copying”, which is HarfBuzz’s own approach ([Fonts as bytes](fonts-as-bytes.html)), and says of Skrifa: “It’s primary purpose is to replace FreeType in Google applications.” The HarfBuzz README sends readers who need hinting to “FreeType or Skrifa”.

Several bindings live in the HarfBuzz organization on GitHub:

* **harfbuzzjs** offers “HarfBuzz shaping library for client/server side JavaScript projects” ([README](https://github.com/harfbuzz/harfbuzzjs)). It is HarfBuzz compiled to WebAssembly with Emscripten, published on npm, and its API keeps HarfBuzz’s objects: blob, face, font, buffer, `shape`.
* **uharfbuzz** is “Streamlined Cython bindings for the HarfBuzz shaping engine” for Python ([README](https://github.com/harfbuzz/uharfbuzz)). It normally builds its own copy of HarfBuzz, and with `USE_SYSTEM_LIBS=1` uses the system’s. The HarfBuzz README points Python users to it, and to GObject introspection (`README.python.md`). This book’s tools read fonts with fontTools and run `hb-shape` itself, not uharfbuzz.
* **harfbuzz_rs** is the Rust interface over the C++ library mentioned above. HarfRust uses it to benchmark against HarfBuzz (HARFBUZZ.md).

## How applications call HarfBuzz

HarfBuzz’s README lists users from Android and Chrome to car displays. What follows is eight of them, and only what their source shows: whether they keep their own copy of HarfBuzz (**vendoring**: copying its source into their tree and building it with their own code), which version that was, which font funcs they give it, which shapers they ask for, and which [cluster level](buffers.html#the-four-cluster-levels) they set.

| Project | Copy of HarfBuzz | Version read | Font funcs | Shapers asked for | Cluster level |
|---|---|---|---|---|---|
| Chromium (Blink) | vendored | 15.1.0 and 148 commits | callbacks into Skia | `ot`, or `harfrust` in tests | default |
| Skia (SkShaper) | through its DEPS | a commit, not a release | hb-ot, with a sub-font calling Skia | default | monotone characters |
| Firefox | vendored | 15.1.0 | its own, reading tables | default | monotone characters |
| Android (minikin) | vendored | 10.2.0 in AOSP | a sub-font calling Skia for advances | default | default |
| Pango | a dependency, or built from a wrap | at least 11.0.0 | | | |
| LibreOffice | bundled tarball, or system | 15.1.0 | hb-ot, with a sub-font for `cmap` | `graphite2`, `ot`, `fallback` | characters |
| Qt | bundled, or system | 15.1.0 | its own, calling the font engine | `graphite2`, `ot`, `fallback` | default |
| OpenJDK | vendored | 15.0.0 | its own, calling Java’s font code | default | monotone characters |
| Godot | vendored | 15.0.0 | hb-ft (FreeType) | default | default |

“Default” in the last column means the code read never sets a cluster level, so HarfBuzz’s level 0 applies. Blank cells are questions the source read for this chapter didn’t answer.

### Chrome and Skia

Chromium keeps HarfBuzz in `third_party/harfbuzz`. Its [README.chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/harfbuzz/README.chromium) gives the version as `15.1.0-148`, rolled on 16 November 2026: Chromium follows HarfBuzz’s main branch, not its releases. It lists files it doesn’t build, among them the Core Text, DirectWrite and Uniscribe backends, “as we rely on HarfBuzz’ built-in AAT shaping”.

The [BUILD.gn](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/harfbuzz/BUILD.gn) is a worked example of [compile-time configuration](compile-time-configuration.html). It uses ICU for Unicode data (`HB_NO_UCD`, with `HAVE_ICU`). It leaves out the `fallback` backend: “Fallback shaper not required, we only use the HarfBuzz internal OT shaper.” It drops drawing, painting, buffer messages and verification, and the experimental formats (`HB_NO_BEYOND_64K`, `HB_NO_CUBIC_GLYF`, and `HB_NO_VAR_COMPOSITES` with the comment “Don’t ship VARC yet”). It keeps the subsetter, because Skia’s PDF output needs it, but without layout or CFF subsetting unless Paint Previews are built. It defines `HAVE_FONTATIONS`, and in [harfbuzz.gni](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/harfbuzz/harfbuzz.gni) `enable_harfrust` is true, so Chromium builds HarfRust 0.15 into HarfBuzz as the `harfrust` backend.

Blink’s [harfbuzz_shaper.cc](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/platform/fonts/shaping/harfbuzz_shaper.cc) decides between the two engines on each call to `hb_shape_full` (trimmed):

```c++
const char* const harfrust_shaper_list[] = {"harfrust"};
const char* const ot_shaper_list[] = {"ot"};

inline const char* const* ShapingBackend() {
  return RuntimeEnabledFeatures::HarfRustShapingEnabled() ? harfrust_shaper_list
                                                          : ot_shaper_list;
}
```

The `HarfRustShaping` feature has the status `test` in [runtime_enabled_features.json5](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/platform/runtime_enabled_features.json5), which the file defines as “Enabled in ContentShell for testing, otherwise off.” So Chrome shapes with `ot`, and the Rust port runs in Blink’s test shell.

Blink’s font funcs, in [harfbuzz_face.cc](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/platform/fonts/shaping/harfbuzz_face.cc), answer the nominal and variation glyph, advance, vertical origin and extents callbacks from Skia, and it gets table data from the Skia typeface. On Apple platforms one exception is made: for a font with a `trak` table and no `sbix`, the horizontal advances are left to HarfBuzz. Since the `harfrust` backend asks the HarfBuzz font for these answers, the same callbacks serve either engine (inferred, from [hb_shape and its backends](hb_shape-and-its-backends.html)).

Below Blink, Skia’s own text layout module has a HarfBuzz shaper, [SkShaper_harfbuzz.cpp](https://github.com/google/skia/blob/main/modules/skshaper/src/SkShaper_harfbuzz.cpp). It builds a face from the typeface’s bytes, or through a table callback when it can’t, makes a font with hb-ot funcs and the typeface’s variation coordinates, and then puts a sub-font on top whose funcs ask Skia for nominal glyphs, advances and extents. Its comment is the [parents and sub-fonts](fonts-and-font-functions.html#parents-and-sub-fonts) model in one line: “Creating a sub font means that non-available functions are found from the parent.” It shapes at `HB_BUFFER_CLUSTER_LEVEL_MONOTONE_CHARACTERS`.

What Skia reads fonts with is changing. Chrome’s blog post [Memory safety for web fonts](https://developer.chrome.com/blog/memory-safety-fonts) (19 March 2025) describes a Skia font backend based on Skrifa, used for web fonts on Linux, Android and ChromeOS from Chrome 133. A note added in 2026 says it was enabled for system fonts on Linux and Android in Chrome 136, and that “In Chrome 145 we removed FreeType from Blink.”

### Firefox

Firefox keeps HarfBuzz in `gfx/harfbuzz`. Its [moz.yaml](https://github.com/mozilla-firefox/firefox/blob/main/gfx/harfbuzz/moz.yaml) gives the release, 15.1.0, tracks HarfBuzz by tag, and leaves out the Core Text, DirectWrite, `harfrust` and `kbts` backends and the paint, raster and vector code.

[gfxHarfBuzzShaper.cpp](https://github.com/mozilla-firefox/firefox/blob/main/gfx/thebes/gfxHarfBuzzShaper.cpp) gives HarfBuzz its own Unicode funcs (`mozilla_harfbuzz_glue_set_up_unicode_funcs`) and its own font funcs: nominal and variation glyphs, horizontal and vertical advances, vertical origin, extents, contour points, font extents, and `glyph_h_kerning`, for which it reads `kern` tables itself. That is the callback HarfBuzz’s [fallback kerning](fallbacks.html#kerning-through-the-font-funcs) asks. For a font with a `CFF ` table it does less: it makes a sub-font that supplies only the nominal glyph and font extents, and leaves the rest to the parent. It sets the scale in 16.16 fixed point from the font size, passes the variation settings, and shapes at the monotone-characters level.

### Android

Android’s copy is `external/harfbuzz_ng`. In AOSP’s public main branch its [METADATA](https://android.googlesource.com/platform/external/harfbuzz_ng/+/refs/heads/main/METADATA) gives version 10.2.0, last upgraded in January 2025, and its [README.android](https://android.googlesource.com/platform/external/harfbuzz_ng/+/refs/heads/main/README.android) notes that “Chromium updates Harfbuzz more frequently”.

The text layout library minikin calls it in [LayoutCore.cpp](https://android.googlesource.com/platform/frameworks/minikin/+/refs/heads/main/libs/minikin/LayoutCore.cpp). For each font it makes a sub-font, because “We override some functions which are not thread safe.” The funcs on it supply advances and origins from Skia, for a stated reason: “we can’t use HarfBuzz’s implemenation. It may return the wrong value if the font uses hinting aggressively.” Colour bitmap fonts (those with `CBDT`) get funcs that keep HarfBuzz’s own advances, “for performance reasons”.

### Pango and GNOME

Pango’s [NEWS](https://github.com/GNOME/pango/blob/main/NEWS) (read on the GitHub mirror) records the whole relationship. Version 1.13.0 “Moved the OpenType Layout code into a new project called HarfBuzz”. 1.31.0 ported Pango to HarfBuzz 0.9, used it as an external library, and removed Pango’s Arabic, Syriac, Hangul, Hebrew, Khmer, Tibetan, Thai and Indic shapers as “replaced by harfbuzz”. 1.44.0 said “Use harfbuzz for shaping on all platforms” and stopped using FreeType for font loading, which “drops support for type1 and bitmap fonts”. 1.44.4 switched to HarfBuzz for metrics too. Pango links HarfBuzz as an ordinary dependency: its [meson.build](https://github.com/GNOME/pango/blob/main/meson.build) asks for `harfbuzz >= 11.0.0`, and a Meson wrap file in `subprojects/` points at HarfBuzz 14.4.0 for building it from source.

### LibreOffice

LibreOffice’s [download.lst](https://github.com/LibreOffice/core/blob/master/download.lst) names `harfbuzz-15.1.0.tar.xz` among the third-party tarballs. In [LogicalFontInstance.cxx](https://github.com/LibreOffice/core/blob/master/vcl/source/font/LogicalFontInstance.cxx) it creates a font with hb-ot funcs, its scale set to the font’s units per em, and passes variations. When it slants a font artificially it tells HarfBuzz to do the same, “so that mark positioning is also transformed” ([synthetic slant](fonts-and-font-functions.html#slant)). On top it puts a sub-font that replaces only the nominal and variation glyph callbacks, so that a hyphen the font has no glyph for can use the minus sign’s glyph instead (bug tdf#171555).

[CommonSalLayout.cxx](https://github.com/LibreOffice/core/blob/master/vcl/source/gdi/CommonSalLayout.cxx) shapes each run with an explicit list, “in the order of preference”: `{ "graphite2", "ot", "fallback", nullptr }`. It sets the BOT and EOT flags at the ends of the text, asks for `HB_BUFFER_FLAG_PRODUCE_SAFE_TO_INSERT_TATWEEL`, which marks where a tatweel may be inserted ([Buffers](buffers.html#glyph-flags)), and uses the characters cluster level, not monotone characters.

### Qt

Qt bundles HarfBuzz in `src/3rdparty/harfbuzz-ng`. Its [qt_attribution.json](https://github.com/qt/qtbase/blob/dev/src/3rdparty/harfbuzz-ng/qt_attribution.json) gives version 15.1.0, and says HarfBuzz is “Optionally used in Qt GUI”, with `-system-harfbuzz` or `-qt-harfbuzz` choosing between the system library and the bundled copy. Its copyright list still includes “Nokia Corporation and/or its subsidiary(-ies)”, from the history in [chapter 1](why-shaping-exists.html#freetype-pango-and-qt-the-first-harfbuzz).

[qharfbuzzng.cpp](https://github.com/qt/qtbase/blob/dev/src/gui/text/qharfbuzzng.cpp) builds the face from a table callback into Qt’s font engine, and gives HarfBuzz Qt’s own Unicode funcs and font funcs, including `glyph_h_kerning` and `glyph_contour_point`. [qtextengine.cpp](https://github.com/qt/qtbase/blob/dev/src/gui/text/qtextengine.cpp) passes the same shaper list as LibreOffice, `graphite2`, `ot`, `fallback`, under the comment “whitelist cross-platforms shapers only”, and sets `HB_BUFFER_FLAG_PRESERVE_DEFAULT_IGNORABLES` for symbol fonts or when the application asks to show default ignorables.

### OpenJDK

Java took HarfBuzz in JDK 9. [JEP 258](https://openjdk.org/jeps/258) proposed to “Replace the existing ICU OpenType font-layout engine with HarfBuzz”, because ICU’s layout engine “is no longer actively developed and IBM, the project owner, intends to replace it with HarfBuzz in the ICU project”. It found “no viable open-source alternatives to HarfBuzz”. The JDK keeps its copy in `src/java.desktop/share/native/libharfbuzz`, at 15.0.0 according to its [legal notice](https://github.com/openjdk/jdk/blob/master/src/java.desktop/share/legal/harfbuzz.md).

Its glue, [hb-jdk-font.cc](https://github.com/openjdk/jdk/blob/master/src/java.desktop/share/native/libfontmanager/hb-jdk-font.cc), builds the face from a table callback and gives HarfBuzz a full set of font funcs that call back into Java’s font code, including kerning, contour points and glyph names. [HBShaper.c](https://github.com/openjdk/jdk/blob/master/src/java.desktop/share/native/libfontmanager/HBShaper.c) shapes at the monotone-characters level, with no shaper list.

### Godot

The Godot game engine vendors HarfBuzz in `thirdparty/harfbuzz`. Its [thirdparty/README.md](https://github.com/godotengine/godot/blob/master/thirdparty/README.md) gives version 15.0.0, and lists what it leaves out: among others `hb-harfrust.cc`, `rust/*`, `hb-wasm*` and `hb-gpu*`. Its advanced text server, [text_server_adv.cpp](https://github.com/godotengine/godot/blob/master/modules/text_server_adv/text_server_adv.cpp), is the only project here that uses HarfBuzz’s FreeType funcs, `hb_ft_font_create`, and asks HarfBuzz for synthetic bold when a font is emboldened. For its bitmap fonts it supplies font funcs of its own.

### What they have in common

Most of these programs let HarfBuzz read the layout tables but answer some of its questions about glyphs themselves, from the code that also renders them: Skia, Android and LibreOffice with a sub-font over hb-ot ([Fonts and font functions](fonts-and-font-functions.html#parents-and-sub-fonts)), Firefox, Qt and OpenJDK with whole sets of funcs. Android’s comment gives one reason, hinted advances; keeping shaping and drawing in agreement is the general one (inferred). The platform backends hardly appear: Chromium stopped building Core Text in favour of HarfBuzz’s own AAT code, Firefox leaves the Core Text and DirectWrite files out, and Qt and LibreOffice name only cross-platform shapers. And while Chromium builds HarfRust in and tests with it, Firefox and Godot leave `hb-harfrust.cc` out of their copies.

## Where to read the source

| Where | What’s there |
|---|---|
| `src/hb-harfrust.cc`, `src/rust/shape.rs`, `src/rust/Cargo.toml` | HarfBuzz’s side of the `harfrust` backend, and the HarfRust version it builds |
| `src/rust/font.rs` | the `fontations` font funcs |
| `NEWS`, `README.md`, `README.python.md` | HarfBuzz’s record of the HarfRust backend, its list of users, and its Python bindings |
| harfrust: `README.md`, `CHANGELOG.md`, `HARFBUZZ.md`, `harfrust_capi/README.md` | what HarfRust ports, which HarfBuzz each release matches, how it is tested against HarfBuzz, and its C API |
| Chromium: `third_party/harfbuzz/`, `third_party/blink/renderer/platform/fonts/shaping/` | Chromium’s copy and build of HarfBuzz, and Blink’s font funcs and shaper |
| Skia: `modules/skshaper/src/SkShaper_harfbuzz.cpp` | Skia’s HarfBuzz shaper |
| Firefox: `gfx/harfbuzz/moz.yaml`, `gfx/thebes/gfxHarfBuzzShaper.cpp` | Firefox’s copy and its shaper |
| Android: `external/harfbuzz_ng/`, `frameworks/minikin/libs/minikin/LayoutCore.cpp` | Android’s copy, and minikin’s calls |
| LibreOffice: `vcl/source/font/LogicalFontInstance.cxx`, `vcl/source/gdi/CommonSalLayout.cxx` | LibreOffice’s fonts and shaping |
| Qt: `src/gui/text/qharfbuzzng.cpp`, `src/gui/text/qtextengine.cpp` | Qt’s glue and shaping |
| OpenJDK: `src/java.desktop/share/native/libfontmanager/` | the JDK’s glue and shaping |

## In short

* HarfRust is the HarfBuzz project’s Rust port of shaping. It began as a fork of rustybuzz that reads fonts with fontations instead of ttf-parser, and is now developed with Google Fonts.
* HarfBuzz leads and HarfRust follows: each HarfRust release names the HarfBuzz release it matches, and 0.16.0 matches 15.1.0. HarfBuzz 15.1.0 itself builds HarfRust 0.15.
* HarfRust ports shaping and Unicode, and leaves font parsing, subsetting and drawing to the fontations crates. It has no font size, no platform integrations and no Graphite, and it now has a C API with HarfBuzz’s names.
* Most large users vendor HarfBuzz: Chromium follows its main branch, and Firefox, Qt and LibreOffice were on 15.1.0 when read. Pango takes it as an ordinary dependency.
* Most of them give HarfBuzz font funcs that answer from their own rendering code, often on a sub-font over hb-ot, and shape with `ot`. Chromium builds the `harfrust` backend but uses it only in tests.

HarfBuzz {{hb}} is one release of a program that changes every few weeks, and some of what this book describes will have changed by the time it is read. The book’s examples run when it is built, so building it again against a newer HarfBuzz will show what has changed.
