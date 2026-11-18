# Building HarfBuzz

Most people get HarfBuzz already built: inside their operating system or their browser, or from a package manager. Building it yourself is for when you want to work on it, or at least to watch it work: to run the command-line tools on your own fonts, to see the traces this book shows, to run the test suites, and to change something and see what happens.

To program with HarfBuzz, you don’t necessarily have to build it either. Three ready-made routes skip the build:

* **JavaScript.** [harfbuzzjs](https://github.com/harfbuzz/harfbuzzjs), from the HarfBuzz project, is HarfBuzz compiled to WebAssembly, for Node and browsers, installed with `npm install harfbuzzjs`. Version 1.6.4 contains HarfBuzz 15.0.0. It has the shaper and the glyph outlines, but not hb-vector, hb-raster or the tools.
* **Python.** [uharfbuzz](https://github.com/harfbuzz/uharfbuzz), also from the HarfBuzz project, comes ready-built for the common platforms with `pip install uharfbuzz`. Version 0.57.0 contains HarfBuzz 15.0.0.
* **Rust.** The [HarfRust](https://crates.io/crates/harfrust) crate needs no C at all, but it isn’t HarfBuzz: it is a port of HarfBuzz’s shaping to Rust, which matches HarfBuzz {{hb}} closely but not exactly ([HarfRust](harfrust.html)).

[Quick start](quick-start.html) uses harfbuzzjs and HarfRust. A package manager’s HarfBuzz is another way in, but check its version first, with `pkg-config --modversion harfbuzz`. This book describes HarfBuzz 15, and a packaged HarfBuzz can be much older: Linux distributions such as Debian and Ubuntu keep the version they shipped with for the life of a release, and Homebrew keeps the version you installed until you upgrade. An older HarfBuzz may not do what this book describes, and before 13.0.0 it has no hb-vector or hb-raster.

This chapter follows a developer setting up such a build, in order: the source, a first build, a development build, a second build for detailed traces, and the daily work in the tree. It ends with a short tour of builds for shipping. Options are named where they are needed; [Compile-time configuration](compile-time-configuration.html), Appendix B, lists them all.

Builds can’t run when the book is built, so the commands here are plain listings, and the little output shown was produced by hand, with HarfBuzz {{hb}} on a Mac.

## Getting the source

HarfBuzz lives on GitHub. Cloning one release, as this book does, takes a few seconds:

```
git clone --depth 1 --branch 15.1.0 https://github.com/harfbuzz/harfbuzz.git
cd harfbuzz
```

Without `--depth 1 --branch`, the clone has the whole history, which is what you want if you will be making commits. The tree’s top level is small:

| Directory | What’s in it |
|---|---|
| `src/` | the library: about 470 files, mostly `hb-*.cc`, `hb-*.hh` and the public `hb-*.h` headers, with the OpenType table code in `src/OT/`, the subsetter’s graph code in `src/graph/` and the Rust integrations in `src/rust/` |
| `util/` | the command-line tools: `hb-shape`, `hb-view`, `hb-info`, `hb-subset`, `hb-raster`, `hb-vector`, `hb-gpu` |
| `test/` | the test suites: `api`, `shape`, `subset`, `vector`, `threads` and `fuzzing` |
| `perf/` | benchmarks, and the fonts they use |
| `docs/` | the hand-written user manual and the files that build the API reference |
| `subprojects/` | Meson “wrap” files, which describe how to fetch a dependency that isn’t installed |
| `.ci/`, `.github/` | the scripts and workflows of HarfBuzz’s continuous integration |

Beside them are `BUILD.md`, `CONFIG.md` (small builds), `TESTING.md`, `README.mingw.md`, `README.python.md`, and `NEWS`, the release notes.

A good part of `src/` was written by programs. The Unicode property tables, the character categories that the script shapers use, the table that maps language tags to OpenType’s, and the state machines that find syllables in Indic and other scripts are all generated, and the generated files are committed. A build never downloads Unicode data or runs those generators; a maintainer runs them by hand when Unicode or a registry changes, as [Regenerating the Unicode and shaping tables](regenerating-the-unicode-and-shaping-tables.html) describes. A few generated files are different: the single-file sources `harfbuzz.cc`, `harfbuzz-subset.cc` and `harfbuzz-world.cc`, and, if Ragel is installed, the state machines’ C are remade by every build and copied back into `src/` when they change ([below](#rebuilding-after-changing-generated-code)).

## Meson and Ninja

HarfBuzz is built with Meson. **Meson** is a build system: it reads a description of the project, written in its own small language in files called `meson.build`, looks at the machine (the compilers, which libraries are installed and where), and writes out the exact commands that will build everything. It doesn’t run those commands itself. It hands them to **Ninja**, a small, fast build tool whose only job is to run build steps in the right order, as many at once as the machine allows, and on the next run to repeat only the steps whose inputs have changed.

Neither comes with macOS or with most Linux systems, but both are easy to get. HarfBuzz needs Meson 0.60.0 or later (`meson.build:2`), a C++ compiler, and `pkg-config`, which Meson uses to find libraries:

* **macOS**, with [Homebrew](https://brew.sh): `brew install meson pkg-config`. Homebrew installs Ninja with Meson. The compiler comes with Apple’s command-line tools, `xcode-select --install`.
* **Debian and Ubuntu**: `sudo apt install meson ninja-build pkg-config g++`. Debian calls its Ninja package `ninja-build`.
* **Fedora**: `sudo dnf install meson ninja-build pkgconfig gcc-c++`.
* **Anywhere with Python**: `pip install meson ninja`. Meson is written in Python, and the `ninja` package is Ninja ready-built. Where the system’s Python refuses to install packages, as recent Debian and Homebrew do, make a virtual environment for them (`python3 -m venv ~/hb-tools`, then `~/hb-tools/bin/pip install meson ninja`) and put its `bin` folder on your `PATH`. This book’s own build gets them that way.

`BUILD.md` adds the libraries the optional parts need, such as FreeType, GLib and cairo, for each platform.

The two meet in a **build directory**. Meson never writes into the source tree’s own directories (apart from the generated files above, which HarfBuzz copies back on purpose): everything it makes goes in a directory you name, by convention `build/`. You can have as many build directories as you like, each configured differently, side by side in one tree. This chapter will end up with three.

There are two steps:

```
meson setup build
ninja -C build
```

`meson setup` configures the build directory once: it runs the checks, records the choices, and writes `build/build.ninja`. `ninja -C build` (“change to `build`, then run”) builds, and is what you run after every edit; `meson compile -C build` does the same through Meson. If a `meson.build` file changes, Ninja reruns Meson before building.

Choices are made with **build options**, given to `meson setup` as `-Dname=value`. Some belong to Meson and work in any project, such as `buildtype` or `b_sanitize`. The rest belong to HarfBuzz and are declared in `meson_options.txt`. Most of HarfBuzz’s are **feature options**, with three values: `enabled` (build it, and fail if a dependency is missing), `disabled`, or `auto` (build it if the dependencies are found). An existing build directory is changed with `meson configure build -Dname=value`, or with `meson setup --reconfigure build` and the options; `meson configure build` alone lists every option with its current value.

## A first build

The first `meson setup` is the one that looks around. HarfBuzz needs nothing but a C++ compiler; everything else is optional, and with `auto`, used if found. Meson asks `pkg-config` for each library (`meson.build:115`–`:167`): FreeType, GLib and GObject, ICU, cairo, Chafa, libpng and zlib. What it finds decides what gets built: GLib is the one that matters most to a developer, since without it there are no command-line tools (`util/meson.build:44`) and no API tests (`test/api/meson.build:2`). `BUILD.md` lists the packages to install on Linux distributions and with Homebrew.

What Meson doesn’t do by default is fetch what it doesn’t find. A wrap file in `subprojects/` can build a missing dependency from source, but HarfBuzz sets `wrap_mode=nofallback` (`meson.build:8`), so that only happens when asked for with `--wrap-mode=default`, as `BUILD.md` suggests for Windows. Ragel, the tool that compiles the syllable machines, is looked for too (`src/meson.build:455`). Without it the build uses the committed C, and Meson warns, correctly, that “You have to install ragel if you are going to develop HarfBuzz itself” (`:463`). You need it only if you change a `.rl` grammar.

At the end, `meson setup` prints a summary (`meson.build:466`). It is worth reading every time, because a missing dependency doesn’t stop an `auto` build; it just leaves something out. Here is part of it, from `meson setup build` in a fresh tree on a Mac with Homebrew’s FreeType, GLib, cairo and libpng installed (hand-run):

```
  Unicode callbacks (you want at least one)
    Builtin                   : YES
    Glib                      : YES
    ICU                       : NO

  Font callbacks (the more the merrier)
    Builtin                   : YES
    FreeType                  : YES
    Fontations                : NO

  Additional libraries
    Subset                    : YES
    Raster                    : YES
    Vector                    : YES
    GPU                       : YES
```

ICU is missing even though Homebrew has it, because Homebrew keeps ICU out of `pkg-config`’s default path; HarfBuzz’s own macOS workflow runs `brew link --force icu4c` first (`.github/workflows/macos.yml`). Most of the other headings name the backends that [hb_shape and its backends](hb_shape-and-its-backends.html) describes; all are off by default.

`ninja -C build` then runs 467 build steps. On the ten-core laptop this chapter was written on, that took a minute.

### What a build makes

Everything lands in `build/`, laid out like the source tree. The libraries are in `build/src/`:

| Library | Built when | What it is |
|---|---|---|
| `libharfbuzz` | always | shaping, and the font, draw and paint APIs |
| `libharfbuzz-subset` | `subset` is not disabled (default enabled) | subsetting and instancing fonts |
| `libharfbuzz-raster` | `raster` (default enabled) | glyphs to pixels: [hb-raster](hb-raster.html) |
| `libharfbuzz-vector` | `vector` (default enabled) | glyphs to SVG and PDF: [hb-vector](hb-vector.html) |
| `libharfbuzz-gpu` | `gpu` (default enabled) | glyphs encoded for a shader: [hb-gpu](hb-gpu.html) |
| `libharfbuzz-icu` | ICU is found, and `icu_builtin` is off | ICU’s Unicode functions |
| `libharfbuzz-cairo` | cairo is found | drawing with cairo; `hb-view` uses it |
| `libharfbuzz-gobject` | GObject is found | GObject types, for bindings to other languages |

FreeType and GLib don’t get libraries of their own: their glue, hb-ft and hb-glib, goes into `libharfbuzz` itself ([Integrations](integrations.html) covers what each layer offers). Each library comes with a **`.pc` file**, the small text file that `pkg-config` reads to tell another project’s build which compiler and linker flags it needs (`pkg-config --cflags --libs harfbuzz`). The ones to be installed are in `build/meson-private/`. Meson also writes `build/meson-uninstalled/harfbuzz-uninstalled.pc` and its siblings, which point into the build directory, so another project can build against a HarfBuzz that was never installed: put that directory on `PKG_CONFIG_PATH`.

The build also writes **`hb-features.h`** (`src/meson.build:614`), an installed header that defines `HB_HAS_FREETYPE`, `HB_HAS_RASTER` and so on for each optional part this build has, so that an application can test for them with `#ifdef`. Two entries are never set by Meson: `HB_HAS_GRAPHITE`, because the option sets `HAVE_GRAPHITE2`, and `HB_HAS_GPU`, though hb-gpu is built (`src/meson.build:587`; [Compile-time configuration](compile-time-configuration.html#the-meson-options)).

> Since {{hb}}: fixed on HarfBuzz main by [`2b873b8`](https://github.com/harfbuzz/harfbuzz/commit/2b873b805800dcad37827f90a5c28ccb6ccc4ba8) and [`506cc94`](https://github.com/harfbuzz/harfbuzz/commit/506cc943b3c2ad82c5398361afdaf6e9eaad6b0f) (17 November 2026), so main’s `hb-features.h` defines `HB_HAS_GPU` when hb-gpu is built, and `HB_HAS_GRAPHITE` when graphite2 is.

The tools are in `build/util/`: `hb-shape`, `hb-view` (with cairo), `hb-info`, `hb-subset`, `hb-raster`, `hb-vector`, and `hb-ft-raster` when FreeType is found, plus `hb-gpu` when GLFW and GLEW are (`util/meson.build:225`). `hb-ft-raster`, which renders with FreeType for comparison, is built but not installed. The test programs are under `build/test/` and `build/src/`.

`ninja -C build install` copies the libraries, headers, `.pc` files and tools under the prefix, `/usr/local` unless `meson setup` was given `--prefix`. A developer usually doesn’t install at all, and runs everything from the build directory, [below](#working-in-the-tree).

## A build for development

The first build is already close to a development build. Meson’s own default build type is `debug`; HarfBuzz changes it to `debugoptimized` (`meson.build:9`), which compiles with optimization and debugging information (for GCC and Clang, `-O2 -g`), and keeps assertions on: `b_ndebug=if-release` (`:10`) removes them only in a `release` build. So it runs the tests quickly, has symbols for a debugger, and checks HarfBuzz’s assumptions. What a developer changes is mostly this:

**Debugging.** In an optimized build, a debugger shows variables as “optimized out” and steps through code in a surprising order. To step through HarfBuzz line by line, set up a second directory with `--buildtype=debug` (no optimization). It is slower: keep `debugoptimized` for everyday work and the tests. `meson test -C build --gdb testname` runs one test under GDB (`TESTING.md`).

**Sanitizers.** `-Db_sanitize=address,undefined` compiles in AddressSanitizer, which stops the program at the first read or write outside an allocation, and UndefinedBehaviorSanitizer, which reports overflowing arithmetic, misaligned reads and the like. HarfBuzz reads untrusted bytes all day ([Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html) is about how), and these are how a mistake in that reading is caught before a fuzzer or a user finds it. HarfBuzz’s CI runs the whole test suite this way, and separately with `thread` and `memory` (`.github/workflows/sanitizers.yml:28`). A sanitized build is slower and larger, so it is another build directory, not a replacement for the first. Some tests then run past their time limits: the CI gives `meson test` the option `-t 10` (`:81`), which multiplies every limit by ten. On a Mac, add `-Dintrospection=disabled` too. When this chapter was written, with Meson 1.12.1 and Homebrew’s gobject-introspection 1.84.0, the introspection scanner tried to link with `-lasan`, a library Apple’s toolchain doesn’t have, and the build stopped there.

**Experimental API.** `-Dexperimental_api=true` defines `HB_EXPERIMENTAL_API` (`meson.build:264`), which adds the functions not yet promised to stay the same, such as `hb_shape_justify` and the `hb_subset_depend_*` functions of [hb-depend](hb-depend.html), and builds the tool and tests that use them (`util/meson.build:192`, `test/subset/meson.build:105`). HarfBuzz’s CI turns it on in its sanitizer builds. [The other switches](compile-time-configuration.html#the-other-switches) lists what it adds.

**Making missing dependencies fatal.** `-Dauto_features=enabled`, a Meson option, turns every `auto` into `enabled`, so that a missing library stops `meson setup` instead of quietly removing a feature. HarfBuzz’s Linux and macOS CI builds start this way.

**An editor that understands the code.** Every Ninja build directory has a `compile_commands.json`, the exact compiler command for each source file. Editors and language servers such as clangd read it to resolve includes and macros: point the editor at `build/compile_commands.json`, or link it into the top of the tree. Choose the build whose options you want the editor to see, since it decides, for instance, whether code under `#ifdef HAVE_FREETYPE` is live.

**ccache.** Switching branches recompiles most of the library. ccache keeps the object file for each exact command and input, and hands it back instead of compiling again. Meson uses it with no configuration: when the compiler isn’t named in `CC` or `CXX` (or a cross or native file), Meson looks for `sccache` and then `ccache` on the `PATH` and puts it in front of the compiler (Meson 1.12.1, `mesonbuild/envconfig.py:467`, `compilers/detect.py:141`). Installing it is the whole job.

A development setup might then be:

```
meson setup build -Dexperimental_api=true -Dauto_features=enabled
meson setup build-asan -Db_sanitize=address,undefined -Dexperimental_api=true -Dintrospection=disabled
```

with `build/` for everyday work and the editor, and `build-asan/` for running the tests before a change is committed.

## A second build for traces

`hb-shape --trace` prints a line for each step of shaping, and the buffer after it: each feature’s lookups starting and ending, normalization, the script shaper’s passes. Those messages come from the library itself, through a callback any application can install ([Testing HarfBuzz](testing-harfbuzz.html#buffer-messages)). A released build sends the coarse ones. The **detailed messages**, from inside lookups (“replacing glyph at 1 (single substitution)”, “ligating glyphs at 0,1,2”, “start recursing to lookup 2 at 1”), cost time even when nobody listens, so since 12.0.0 they are compiled only when `HB_BUFFER_MESSAGE_MORE` is defined to 1 (`hb-debug.hh:452`). That needs a build of its own.

Defines like this aren’t build options. They are given as compiler flags, either through the environment when the directory is first set up, or with Meson’s `cpp_args`:

```
CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1 meson setup build-msg
meson setup build-msg -Dcpp_args=-DHB_BUFFER_MESSAGE_MORE=1
```

Meson reads `CXXFLAGS` only at that first setup, and stores it with the directory: after the first command, `meson introspect build-msg --buildoptions` reports `cpp_args` as `['-DHB_BUFFER_MESSAGE_MORE=1']`. Here is the `liga` lookup of the [GSUB](gsub.html) chapter’s test font on “ffi”, from `hb-shape --trace --language=en ligatures.ttf ffi`, first from `build/` and then from `build-msg/` (hand-run, trimmed to the one lookup):

```
trace: start lookup 0 feature 'liga'	buffer: [f=0|f=1|i=2]
trace: end lookup 0 feature 'liga'	buffer: [f_f_i=0]
```

```
trace: start lookup 0 feature 'liga'	buffer: [f=0|f=1|i=2]
trace: ligating glyphs at 0,1,2	buffer: [f=0|f=1|i=2]
trace: ligated glyph at 0	buffer: [f_f_i=0]
trace: end lookup 0 feature 'liga'	buffer: [f_f_i=0]
```

The `HB_DEBUG_*` macros work the same way: `-DHB_DEBUG_SANITIZE=100`, say, makes the library print every sanitize call to standard error, a hundred levels deep, and `-DHB_DEBUG_SUBSET=100`, as in `TESTING.md`, does the same for subsetting. [Testing HarfBuzz](testing-harfbuzz.html#debug-output) shows what they print, and [Compile-time configuration](compile-time-configuration.html#the-other-switches) lists them all. Such a build is for watching, not for timing, and its output would drown a test log, which is why it is kept apart from the first.

This book’s own `tools/build-harfbuzz.sh`, which builds the HarfBuzz behind every live example, is a worked example. It clones {{hb}} into `.cache/harfbuzz/` and sets up three build directories side by side, each built only as far as the book needs (trimmed):

```sh
OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=disabled -Dicu=disabled"
[ -d build ] || meson setup build $OPTS
ninja -C build util/hb-shape util/hb-vector util/hb-info util/hb-subset util/hb-raster
[ -d build-msg ] || CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1 meson setup build-msg $OPTS
ninja -C build-msg util/hb-shape
FT_OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=enabled -Dicu=disabled"
[ -d build-ft ] || meson setup build-ft $FT_OPTS
ninja -C build-ft util/hb-raster util/hb-shape util/hb-ft-raster
```

* **`build/`** has the tests, the documentation, cairo, FreeType and ICU off: the book runs no tests and needs no `hb-view`, and without FreeType and ICU its results can’t depend on the versions a machine has. Every shaping result, drawing and `info` block in the book comes from here.
* **`build-msg/`** is the same with `HB_BUFFER_MESSAGE_MORE`, and builds only `hb-shape`, since only the traces use it.
* **`build-ft/`** has FreeType on, so `hb-shape` and `hb-raster` can be asked for FreeType’s font functions with `--font-funcs=ft`, and builds `hb-ft-raster`. It is there for the few examples that compare HarfBuzz’s outlines and metrics with FreeType’s hinted ones, as [hb-raster](hb-raster.html#hinting-with-freetype) does.

Two things about the script are worth copying. The `[ -d build ] ||` guards set a directory up only once, so running the script again just brings each build up to date. And naming targets (`ninja -C build util/hb-shape`) builds only those programs and what they need, which on a trace build is a fraction of the whole.

## Working in the tree

### Running the tools

The tools run straight from the build directory: Meson links them so that they find the libraries next to them, with nothing installed and no library path to set.

```
build/util/hb-shape font.ttf 'office'
build-msg/util/hb-shape --trace font.ttf 'office'
```

Type the path every time: an `hb-shape` from a package manager is probably on the `PATH` too, and it is a different HarfBuzz. [The command-line tools](command-line-tools.html) is about what the tools do.

### Running the tests

`meson test -C build` runs the test suites, after first rebuilding whatever is out of date. Each test belongs to one or more **suites**, and `--suite` picks them. These are the ones that matter for everyday work, as `AGENTS.md` in HarfBuzz’s tree advises: `shape` after a change to shaping, `subset` after a change to the subsetter, `api` after a change to the public API, and the whole set before committing. The `shape` suite runs thousands of recorded shaping results through `hb-shape`, which is why the tools must be built for it (`test/meson.build:4`). [Testing HarfBuzz](testing-harfbuzz.html) describes the suites and their formats.

Here is the `shape` suite on the first build (hand-run, `meson test -C build --suite shape`):

```
1/3 shape+aots - harfbuzz:aots                                 OK              0.12s   541 subtests passed
2/3 shape+text-rendering-tests - harfbuzz:text-rendering-tests OK              0.15s   874 subtests passed
3/3 shape+in-house - harfbuzz:in-house                         OK              1.10s   6374 subtests passed

Ok:                3
Fail:              0
```

The full suite, 277 tests in this build, took under a minute. `--list` shows the tests without running them, `--print-errorlogs` prints a failing test’s output, and Meson keeps the whole log in `build/meson-logs/testlog.txt`.

### Rebuilding after changing generated code

Ninja tracks which headers each file includes. So when a generated table such as `hb-ucd-table.hh` or `hb-ot-shaper-use-table.hh` is regenerated, by the makefile of [Regenerating the Unicode and shaping tables](regenerating-the-unicode-and-shaping-tables.html#running-the-data-generators), the next `ninja -C build` recompiles exactly the files that include it. Nothing needs to be cleaned or reconfigured.

The Ragel grammars are different, because they are part of the build. With Ragel 6.10 installed, Meson compiles each `.rl` file to its header in every build, and copies the header into `src/` when it differs from the committed one (`src/meson.build:466`). Without Ragel, editing a `.rl` file changes nothing, silently: install it, or set `-Dragel_subproject=true` to have Meson build it from its wrap file. Either way, commit the regenerated header together with the grammar. The single-file sources are regenerated the same way, so adding a source file to `src/meson.build` updates `harfbuzz.cc` in the tree too; the files that turn up changed after a build belong in the commit.

## Builds to ship

A build to ship makes the opposite choices: release optimization, the platform’s dependencies, and nothing unused. What follows is a map; Appendix B has the details.

### Optional dependencies and backends

| Option | What it turns on |
|---|---|
| `freetype` | hb-ft: FreeType’s font functions, and making a HarfBuzz font from an `FT_Face`. Needed for hinted text, since HarfBuzz doesn’t hint: [hb-raster](hb-raster.html#hinting-with-freetype) |
| `glib` | GLib’s Unicode functions; needed for the tools and the API tests |
| `icu`, `icu_builtin` | ICU’s Unicode functions, in `libharfbuzz-icu` or in `libharfbuzz` itself |
| `cairo` | `libharfbuzz-cairo`, and `hb-view` |
| `png`, `zlib` | PNG output in hb-raster; compressed SVG glyphs and PDF output |
| `gobject`, `introspection` | `libharfbuzz-gobject`, and the introspection data that lets Python and other languages call HarfBuzz |
| `fontations` | font functions from Google’s Rust fontations crates; needs a Rust compiler |
| `graphite2`, `harfrust`, `kbts`, `wasm` | other shaping backends ([hb_shape and its backends](hb_shape-and-its-backends.html#the-backends)) |
| `coretext`, `directwrite`, `gdi` | the platform shapers and font functions, for comparison |
| `subset`, `raster`, `vector`, `gpu` | the libraries of the same names; disable what you don’t ship |
| `utilities`, `tests`, `docs` | the tools, the tests and the gtk-doc reference |

A build to ship also sets `--buildtype=release` and the `--prefix`, and, for a HarfBuzz linked into one application, perhaps `--default-library=static`. `CONFIG.md` recommends link-time optimization (`-Db_lto=true`) and, where size matters, optimizing for size (`--buildtype=minsize`), which it says Chrome does too. [The Meson options](compile-time-configuration.html#the-meson-options) has the defaults and the macros each option sets.

### Single-file builds

HarfBuzz can also be built with no build system at all. `src/harfbuzz.cc`, available since 2.6.0, is one line per source file of the main library, `#include "hb-buffer.cc"` and so on, so `c++ -c src/harfbuzz.cc` compiles all of `libharfbuzz` in one go (`BUILD.md:50`). `harfbuzz-subset.cc` does the same for the subsetter. Since 11.4.2 even `hb-shape` can be built against it, as `BUILD.md:57` shows:

```
c++ -O2 src/harfbuzz.cc util/hb-shape.cc -o hb-shape -I src -DHB_NO_FEATURES_H `pkg-config --cflags --libs glib-2.0`
```

Run by hand in a fresh tree on the same Mac, that command made a working `hb-shape` in under twenty seconds, on one core. `-DHB_NO_FEATURES_H` stops the tool from including `hb-features.h` (`util/options.hh:50`), which only a Meson build generates. Optional parts are switched on with the same `HAVE_*` macros Meson would write into `config.h`: `harfbuzz.cc` includes `hb-ft.cc` and the platform backends, and each of those compiles to nothing unless, for example, `HAVE_FREETYPE` is defined.

`harfbuzz-world.cc`, new in 14.0.0, goes further: every library in one file, each part chosen by an `HB_HAS_*` macro. It is generated from `src/harfbuzz-world.cc.in` by `src/gen-harfbuzz-world.py`, which replaces each placeholder in the template with the `#include` lines for one group of sources. The result begins like this (`harfbuzz-world.cc.in:1`, trimmed):

```c++
#ifdef HB_FEATURES_H
#include HB_FEATURES_H
#endif

#ifdef HB_HAS_FREETYPE
#define HAVE_FREETYPE 1
#endif
...
/* Core library. */
#include "OT/Var/VARC/VARC.cc"
#include "hb-aat-layout.cc"
...
#ifdef HB_HAS_RASTER
#include "hb-raster-draw.cc"
...
#endif
```

So a project writes its own small header defining the `HB_HAS_*` macros it wants, and compiles with `-DHB_FEATURES_H='"my-features.h"'`; `NEWS` for 14.0.0 calls this a “custom `hb-features.h`”. By hand, `c++ -O2 -c src/harfbuzz-world.cc -I src -DHB_FEATURES_H='"my-features.h"'`, with a header defining `HB_HAS_SUBSET`, `HB_HAS_RASTER` and `HB_HAS_VECTOR`, made one object file with all four libraries in forty seconds. The header can’t be the `hb-features.h` that Meson writes, nor a copy of it, because `HB_FEATURES_H` is also that header’s include guard (`hb-features.h.in:25`): with the macro already defined, its whole body is skipped. Checked with the preprocessor: naming Meson’s header leaves `HB_HAS_RASTER` undefined. The library macros can also come from a `config.h`, compiled with `-DHAVE_CONFIG_H`, because the core sources, which come first, include it before the template tests for the other libraries. That is what HarfBuzz’s own web build of the hb-gpu demo does (`util/gpu/web/build.sh:13`, `config.h:5`).

### Smaller builds

For an embedded system, or a download where every kilobyte counts, almost every part of the library can be compiled out with an `HB_NO_*` macro, and three ready-made sets cover the common cases. `HB_MINI` keeps a capable OpenType shaper and drops AAT and the legacy-font paths; `HB_LEAN` drops most of what isn’t shaping; `HB_TINY` is both, and makes the library single-threaded. They are passed as compiler flags, as `CONFIG.md` shows:

```
meson setup build -Dcpp_args=-DHB_MINI -Dc_args=-DHB_MINI
```

A tier can be partly undone with an override header. [The tiers](compile-time-configuration.html#the-tiers) says exactly what each removes, and [How the macros are processed](compile-time-configuration.html#how-the-macros-are-processed) how the override headers work.

### CMake

`CMakeLists.txt` is still there, but its first act is a warning: “The main build system for HarfBuzz is Meson. CMake build support is community-maintained and is not actively supported by HarfBuzz developers” (`CMakeLists.txt:4`). It reads its version from `meson.build` (`:170`) and its library sources from `harfbuzz.cc` (`:181`), so it keeps up without being edited. It builds the libraries (`:59`–`:62`) and, with `HB_BUILD_UTILS`, some of the tools, but not `hb-raster` or `hb-vector` (`:1008`–`:1074`), and no tests. Its options are named differently (`HB_HAVE_FREETYPE`, `:35`) and off by default, except CoreText on Apple platforms (`:45`), which Meson leaves off. Meson also installs a `harfbuzz-config.cmake` in `cmakepackagedir` (`src/meson.build:1240`), so a CMake project can find a HarfBuzz built with Meson.

### WebAssembly, Windows and Python

**WebAssembly.** There is no Meson setup for building HarfBuzz to WebAssembly; the single-file sources are the way. `util/gpu/web/build.sh` compiles `harfbuzz-world.cc` and the hb-gpu demo with Emscripten’s `em++ -Oz -flto` in one command, configured by a `config.h` that defines `HB_TINY` and `HB_HAS_GPU` and an override header that brings back drawing, painting, color, metrics and variations. The [harfbuzz-world.cc](https://harfbuzz-world.cc/) playground, which `README.md` calls “a worked example of the world.cc single-file build”, is built the same way. (The `wasm` option is something else: a shaping backend that runs WebAssembly code stored in a font.)

**Windows, from Linux or macOS.** `README.mingw.md` is a step-by-step guide to cross-compiling with MinGW and running the tools and tests under Wine, which is how HarfBuzz’s developers test the Uniscribe and DirectWrite backends without Windows. Its easiest path is `.ci/build-win.sh 64`, which also makes HarfBuzz’s Windows binaries; with real Windows DLLs copied into Wine, `hb-shape --shaper=uniscribe` compares HarfBuzz with Microsoft’s engine. On Windows itself, Meson works with MSVC or with GCC or Clang on the `PATH` (`BUILD.md:40`).

**Python.** `README.python.md` describes calling HarfBuzz from Python through GObject introspection: with GObject and gobject-introspection found, the build makes `HarfBuzz-0.0.typelib`, and PyGObject’s `from gi.repository import HarfBuzz` loads it (`src/sample.py` is an example). It warns that “The Python API will change”. `README.md` also points to [uharfbuzz](https://github.com/harfbuzz/uharfbuzz), separate Python bindings that don’t need any of this.

## Where to read the source

| File | What’s there |
|---|---|
| `BUILD.md`, `TESTING.md`, `CONFIG.md` | upstream’s own notes on building, testing and small builds |
| `meson.build` | the project defaults, the dependency checks, the `HAVE_*` macros, the summary |
| `meson_options.txt` | HarfBuzz’s build options |
| `src/meson.build` | the libraries, Ragel, `hb-features.h`, the single-file sources, the source checks |
| `util/meson.build`, `test/meson.build` | which tools and tests are built, and on what they depend |
| `src/harfbuzz-world.cc.in`, `src/gen-harfbuzz-world.py`, `src/gen-harfbuzzcc.py` | the single-file builds |
| `CMakeLists.txt` | the community CMake build |
| `README.mingw.md`, `.ci/build-win.sh`, `.ci/win64-cross-file.txt` | building for Windows |
| `util/gpu/web/build.sh`, `util/gpu/web/config.h` | a single-file WebAssembly build |
| `.github/workflows/` | how HarfBuzz’s own CI configures its builds, sanitizers included |
| `tools/build-harfbuzz.sh` (this book) | three build directories for the book’s examples |

## In short

* HarfBuzz builds with Meson, which configures a build directory (`meson setup build`), and Ninja, which builds in it (`ninja -C build`). Each build directory is configured once, and a tree can have several.
* Only a C++ compiler is required. Optional parts are built when their libraries are found; read the summary at the end of `meson setup`. Without GLib there are no tools and no API tests.
* The default build type is `debugoptimized`, with assertions on. A development setup adds `experimental_api`, a sanitized build directory (`-Db_sanitize=address,undefined`), `compile_commands.json` for the editor, and ccache, which Meson finds by itself.
* The detailed buffer messages and the `HB_DEBUG_*` output are compiled in with macros, so they need a build directory of their own, as `tools/build-harfbuzz.sh` sets up with `build-msg/`.
* Run the tools from `build/util/`, and the tests with `meson test -C build`, by suite. Generated tables are committed; Ragel is needed only to change a grammar.
* To ship: choose the backends and dependencies, release or size optimization, and if needed the single-file sources (`harfbuzz.cc`, `harfbuzz-world.cc` with a custom features header) and the `HB_MINI`, `HB_LEAN` and `HB_TINY` tiers. CMake is community-maintained.
