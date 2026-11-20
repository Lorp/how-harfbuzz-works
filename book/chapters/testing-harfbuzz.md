# Testing HarfBuzz

HarfBuzz is checked in three ways. A run can be watched from inside: the buffer reports each step as it happens, a debug build prints the work of the table code, and a flag makes the library reshape its own output and compare. The repository holds test suites that compare results with recorded ones: shaping results in `test/shape`, the C API in `test/api`, subset fonts in `test/subset`, and a few more. And fuzzers feed it malformed fonts without end, looking for crashes rather than wrong answers.

This chapter describes each, from the code and from the files in `test/`. The book’s build of HarfBuzz {{hb}} has the tests turned off (`-Dtests=disabled` in `tools/build-harfbuzz.sh`), so nothing from the suites runs here, except one test line that the build can run because it needs only `hb-shape` and a font. Traces and verification do run live.

The last part shows how to test HarfBuzz with a small font of your own, then the possible bugs found while this book’s examples were being built that way, and what they suggest about where bugs are left to find.

## Looking inside a run

### Buffer messages

[Buffers](buffers.html#messages) describes the mechanism. `hb_buffer_set_message_func` (`hb-buffer.cc:2396`) installs a callback that HarfBuzz calls with a short message, formatted into 100 bytes (`:2445`), before and after each step it is willing to report. Returning false skips the step about to start. Since 13.0.0 a callback may change glyph IDs too, if it then calls `hb_buffer_changed`.

`hb-ot-layout.cc` sends “start table GSUB” and “start table GPOS” (`:2139`, `:2151`), “start lookup” and “end lookup” around each lookup (`:2096`, `:2119`), and “skipped lookup … because no glyph matches” when the buffer’s digest rules a lookup out. Normalization, the AAT tables, legacy `kern`, and the script shapers send their own, and the verifier sends its failures the same way.

`hb-shape --trace` installs a callback that prints each message and then the whole buffer, serialized just as the final output is, on standard error (`util/shape-output.hh:136`):

```
trace: start lookup 3 feature 'calt'	buffer: [space=0|e=1|e=2]
```

The **detailed messages** come from inside lookups: which glyph a single substitution is about to replace, which glyphs a ligature is about to join, and each recursion from a contextual lookup into a nested one. They cost time even when nobody is listening, so 12.0.0 turned them off; `NEWS` says that tools that need them “should define `HB_BUFFER_MESSAGE_MORE` to 1 when building HarfBuzz”. The macro defaults to `HB_DEBUG+0` (`hb-debug.hh:452`), and every such message is guarded by it, as here in the code that recurses from a contextual rule (`hb-ot-layout-gsubgpos.hh:2770`, trimmed):

```c++
if (HB_BUFFER_MESSAGE_MORE && c->buffer->messaging ())
{
  if (buffer->have_output)
    c->buffer->sync_so_far ();
  c->buffer->message (c->font,
                      "start recursing to lookup %u at %u",
                      (unsigned) lookupRecord[i].lookupListIndex,
                      buffer->idx);
}
```

When the macro is 0, the compiler removes the whole block. This is why `tools/build-harfbuzz.sh` builds HarfBuzz more than once: `build/` as released, and `build-msg/` with `-DHB_BUFFER_MESSAGE_MORE=1`, which only the traces in this book use ([Building HarfBuzz](building-harfbuzz.html#a-second-build-for-traces)); a third, `build-ft/`, adds FreeType. Here is the `calt` lookup of [GSUB](gsub.html)’s test font on a space and two `e`s, with every line included:

```trace
font: gsub/ligatures.ttf
text: \u0020ee
options: --language=en
from: start table GSUB
to: end table GSUB
skipped: yes
```

A released build prints the “start”, “end”, and “skipped” lines. The four “recursing” lines and the four “replacing” and “replaced” lines come only from `build-msg/`. They show what a contextual lookup does at each position, which the lines around a lookup can’t: here the rule matched twice, at glyphs 1 and 2, and each time it ran lookup 2 on one glyph.

### Debug output

Below the messages is a second mechanism, for HarfBuzz’s own developers. `hb-debug.hh` defines a family of compile-time macros, `HB_DEBUG_APPLY`, `HB_DEBUG_SANITIZE`, `HB_DEBUG_SUBSET`, `HB_DEBUG_PAINT`, `HB_DEBUG_SHAPE_PLAN`, and a dozen more, each defaulting to `HB_DEBUG+0`, so that `-DHB_DEBUG=…` turns them all on. A released library prints nothing.

Each value is a depth. Code that wants tracing opens a trace object at the top of a function, and `return_trace` closes it (`hb-debug.hh:308`). With `HB_DEBUG_SANITIZE` set, every `sanitize ()` method in the library starts like this (`hb-debug.hh:384`, trimmed):

```c++
#define TRACE_SANITIZE(this) \
	hb_auto_trace_t<HB_DEBUG_SANITIZE, bool> trace \
	(&c->debug_depth, c->get_name (), this, HB_FUNC, " ")
```

`hb_auto_trace_t` prints the function’s name and the object’s address on standard error when it is entered, indented by the nesting depth, and the value and source line when it returns; only calls nested less deeply than the macro’s value are printed (`_hb_debug`, `:45`). So `-DHB_DEBUG_SANITIZE=4` prints the top four levels of the sanitizer’s descent through a table, and a large value prints all of it. With the macro at 0 the trace object is an empty struct, `hb_no_trace_t`, which the compiler removes (HarfBuzz pull request #605). [Compile-time configuration](compile-time-configuration.html) lists these macros with the rest.

### Verification

The third tool is in the library itself, since 3.4.0. With `HB_BUFFER_FLAG_VERIFY` set on the buffer, `hb_shape_full` copies the text before shaping (`hb-shape.cc:137`) and afterward checks the result against it: that clusters are monotone, and that cutting the text where the result says it is safe to break, or safe to concatenate, and shaping the pieces gives the same glyphs (`hb-buffer-verify.cc:380`). A failure goes to the message callback if there is one, and otherwise to standard error, and `hb_shape_full` returns false. `hb-shape --verify` sets the flag. [For applications](for-applications.html) explains what the checks mean for line breaking, and [Buffers](buffers.html#verification) how they are made.

Verification is the one check that needs no expected answer: it compares HarfBuzz with itself. That is why the test runner, the threading test, and the shaping fuzzer below all turn it on. It is also its limit. A result that is wrong in the same way whether the text is shaped whole or in pieces passes.

## The shaping tests

`test/shape` holds the suite that matters most for this book. Its tests are text files, each line a shaping run and its expected result, kept in three sets under `test/shape/data/`:

| Set | Files | Test lines | Where it comes from |
|---|---|---|---|
| `in-house` | 90 | 5,277 | HarfBuzz’s own, one file per subject (`arabic-stch.tests`, `indic-init.tests`, `vertical.tests` …) |
| `aots` | 128 | 276 | Adobe’s Annotated OpenType Specification tests, one per lookup type and format |
| `text-rendering-tests` | 94 | 753 | the Unicode Consortium’s text-rendering-tests repository |

(Test lines count every line that isn’t blank, a comment, or a directive.) There is no Microsoft suite in the tree at {{hb}}. What comes from Microsoft is data: `src/ms-use/` holds the USE category overrides and the vowel-constraint list that the generators read ([Regenerating the Unicode and shaping tables](regenerating-the-unicode-and-shaping-tables.html)). Microsoft’s own shapers appear only as backends: `uniscribe.tests` and `directwrite.tests` compare them with the `ot` shaper, on Windows.

### The format of a test

A line has four fields separated by semicolons: the font, the `hb-shape` options, the text as code points, and the expected output. Here is the first line of `in-house/tests/arabic-stch.tests`, a Syriac word with an abbreviation mark, which the `stch` feature stretches across the word ([Joining scripts](joining-scripts.html)):

```
../fonts/d9b8bc10985f24796826c29f7ccba3d0ae11ec02.ttf;--no-glyph-names;U+0718,U+070F,U+0718,U+0718,U+002E;[1=4+168|3=3+502|3=2+502|4=1@-1004,0+0|5=1@-876,0+0|5=1@-799,0+0|5=1@-722,0+0|5=1@-645,0+0|4=1@-566,0+0|5=1@-438,0+0|5=1@-361,0+0|5=1@-284,0+0|5=1@-207,0+0|4=1@-128,0+0|3=0+502]
```

The font path is relative to the test file. In-house fonts are named by the SHA-1 of their contents, because `record-test.sh` makes them: given an `hb-shape` command, it subsets the font to the characters of the test with fontTools’ `pyftsubset`, checks that the subset gives the same result as the original (or, for fonts without glyph names, the same picture through `hb-view`), and saves it under its hash (`test/shape/README.md`). The expected output is what `hb-shape` printed when the test was recorded. A `*` in its place means “any result”: the test only checks that shaping finishes.

Three other kinds of line can appear. A line beginning `#` and a space is a comment; `#` followed directly by a test is a test turned off. A line beginning `@` is a directive that applies to the rest of the file: `@shapers=ot,uniscribe`, `@font-funcs=ot,ft`, or with a minus, `@font-funcs-=ft`, to leave some out. And a font given as an absolute path, with a hash after an `@`, is a system font: `macos.tests` tests Apple’s fonts by path, and a test is skipped if the font is missing or its hash differs (`run-tests.py:204`).

The book’s build can run that line, because the test font is in HarfBuzz’s source tree. These are the options the runner adds to it, described next:

```shape
hb:test/shape/data/in-house/fonts/d9b8bc10985f24796826c29f7ccba3d0ae11ec02.ttf  ܘ܏ܘܘ.  --no-glyph-names  --verify  --unsafe-to-concat  --safe-to-insert-tatweel
hb:test/shape/data/in-house/fonts/d9b8bc10985f24796826c29f7ccba3d0ae11ec02.ttf  ܘ܏ܘܘ.
```

The first row is the expected output exactly, and verification passed. The second gives the same run with glyph names: three `syrcAbbrDot` glyphs, at −1004, −566, and −128, with four `syrcAbbrLine` tiles between each pair, all in cluster 1, the mark’s, laid back over the letters.

### How a test is run

`run-tests.py` is given the path of `hb-shape` and a list of test files, and prints its results in TAP, the format Meson’s test runner reads (`test/shape/meson.build` registers one test per set). It starts one `hb-shape --batch` and writes each test to it as a line of arguments joined by semicolons, reading one line of output back (`run-tests.py:25`), restarting it if a test crashes it. The environment is `LC_ALL=C`, so that the language never comes from the locale.

For each line, the runner builds the command from the font, `--unicodes`, and the line’s options, and adds `--verify --unsafe-to-concat --safe-to-insert-tatweel` unless the expected output is `*` (`:284`). So every test of the suite is also a verification test, with the unsafe-to-concat and tatweel flags computed and checked too.

Then it runs the line once for each backend it should test. Before reading any test it asks `hb-shape` for its `--list-shapers`, `--list-face-loaders`, and `--list-font-funcs`. Shapers and face loaders default to `ot` only, unless the environment variables `HB_SHAPER_LIST` and `HB_FACE_LOADER` name more (`:146`), but font functions default to every kind the build has: `ot`, and also `ft`, `fontations`, `coretext`, and `directwrite` where they were built in (`hb-font.cc:2608`). A line runs with `--font-funcs=ot`, again with `--font-funcs=ft`, and so on, and every run must give the expected output, so the suite also checks that the font functions agree on advances, origins, and glyph names. A directive or an option narrows the list, and a backend the build lacks is counted as skipped, not failed. The book’s build has only `ot`.

A last detail: if the output names glyphs as `gid…` because the font has no names, and it differs from what was expected, the runner converts both to bare glyph IDs with `--glyphs --no-glyph-names` and compares those, so that glyph names coming from one backend and not another don’t fail the test (issue #5169, `:323`).

### Where the other sets come from

The AOTS set is generated. `aots/update.py` clones Adobe’s `aots` repository, builds its test fonts, compiles `hb-aots-tester.cpp` against HarfBuzz, and runs it, which writes the `.tests` files. Its lines turn on a feature called `test` and print without clusters or names:

```
../fonts/gpos1_1_simple_f1.otf;--features="test" --single-par --no-clusters --no-glyph-names --ned;U+0011,U+0012,U+0013,U+0014,U+0015;[17|18@1300,0|19@3000,0|20@4300,0|21@6000,0]
```

The text-rendering-tests set is imported by its own `update.py` from the Unicode Consortium’s repository (`text-rendering-tests/README`). Its files begin with `@font-funcs=ot,ft`, and a `DISABLED` file lists the few it doesn’t run: one for a non-Unicode `cmap`, five for rounding differences.

### Other golden-file tests

`test/vector` does for `hb-vector` what `test/shape` does for `hb-shape`: lines of font, options, code points, and an expected SVG file, compared by its own `run-tests.py`. And `src/` holds 38 unit tests (`src/test-*.cc`) of internal pieces with no public API: the repacker, the serializer, the instancer’s solver, geometry, and others.

## The API tests

`test/api` tests the public C API, one file per subject: `test-buffer.c`, `test-font.c`, `test-ot-layout.c`, `test-subset-glyf.c`, and about seventy more. They use GLib’s test framework, so they are built only when GLib is found (`test/api/meson.build:1`), and the files for FreeType, Graphite, CoreText, DirectWrite, and cairo only when those are. `hb-test.h` wraps the framework so that a test is registered by its function’s name: `hb_test_add (test_buffer_properties)` becomes the test path `/buffer/properties`.

The tests are ordinary assertions: create an object, call the API, `g_assert_true` on what comes back. Their fonts are in `test/api/fonts`, some made by Python scripts beside them, such as `generate-cff2-nested-delta-font.py`, which build edge cases no font editor would produce. `results-paint/` holds the expected output of the paint API.

## The subsetting tests

`test/subset` checks the subsetter by its output files. Each of its 104 test files (`data/tests/*.tests`) lists fonts, profiles, and subsets:

```
FONTS:
Roboto-Regular.abc.ttf
NanumMyeongjo-Regular-subset.ttf

PROFILES:
default.txt
drop-hints.txt
retain-gids.txt

SUBSETS:
a
abc
*
```

That is part of `basics.tests`, shortened. Each profile in `data/profiles/` is a file of `hb-subset` options, and each subset is a set of characters (`*` is all). Every combination is a test, and its expected result is a whole font in `data/expected/<test name>/`, named after the font, profile, and code points: `NanumMyeongjo-Regular-subset.default.61,62,63.ttf`.

`run-tests.py` subsets with `hb-subset` and compares the output with the expected font byte for byte (`test/subset/run-tests.py:115`). If they differ, it dumps both with fontTools and prints the difference of the TTX, so that a failure says which table changed; and if `ots-sanitize` (the OpenType Sanitizer) is installed, it checks every output with that too.

The expected fonts are not just whatever HarfBuzz once produced. `generate-expected-outputs.py` makes them by running both subsetters, HarfBuzz’s and fontTools’ (with `--no-harfbuzz-repacker`, “so we aren’t comparing to ourself”), and stops if their TTX dumps differ (`:90`), unless a test is marked `no_fonttools`. So an expected subset is one that two independent implementations agree on. [Subsetting](subsetting.html) and [Instancing](instancing.html) describe what is being checked; the repacker has tests of its own here too (`repack_tests/`, `run-repack-tests.py`).

## Threads and benchmarks

`test/threads` has two programs in Meson’s `slow` suite. `hb-shape-threads.cc` shares one `hb_font_t` among several threads (three by default) that wait on a condition variable, then all start shaping the same texts at once, each with its own buffer and with `HB_BUFFER_FLAG_VERIFY` set, once for each kind of font functions. `hb-subset-threads.cc` does the same for subsetting. Neither compares results between threads. They give a thread checker something to find: HarfBuzz’s continuous integration builds with ThreadSanitizer, as well as AddressSanitizer with UndefinedBehaviorSanitizer and MemorySanitizer (`.github/workflows/sanitizers.yml`).

`perf/` holds benchmarks written with Google Benchmark, built only with `-Dbenchmark=enabled`: `benchmark-shape`, `benchmark-font`, `benchmark-subset`, `benchmark-set`, `benchmark-map`, `benchmark-ot`, and `benchmark-gpu`. They run on fonts in `perf/fonts/` (Roboto, Amiri, Noto Nastaliq Urdu, Gulzar, Noto Sans Duployan) and `test/subset/data/fonts/`, with texts in `perf/texts/`: *The Little Prince* in English and Persian, and word lists in English, Persian, and Hindi. The README calls `benchmark-font` the most useful.

## Fuzzing

A **fuzzer** runs a program over and over on inputs mutated from a corpus of examples, and watches for the program crashing, hanging, or using too much memory; mutations that reach new code are kept and mutated further. `test/fuzzing` has fuzzers for shaping, subsetting, the repacker, and the three renderers (raster, vector, GPU), and, when HarfBuzz is built with `-Dexperimental_api=true`, for hb-depend (`test/fuzzing/meson.build`). Each defines the one function libFuzzer calls, `LLVMFuzzerTestOneInput`, which takes a byte string and treats it as a font, perhaps with options at its end. The shaping fuzzer, trimmed (`hb-shape-fuzzer.cc:7`):

```c++
extern "C" int LLVMFuzzerTestOneInput (const uint8_t *data, size_t size)
{
  alloc_state = _fuzzing_alloc_state (data, size);

  _fuzzing_shape_input_t input;
  if (_fuzzing_prepare_shape_input (data, size, 12, 12, &input)
      == HB_FUZZING_SHAPE_INPUT_MALFORMED)
    return 0;

  {
    hb_buffer_t *buffer = hb_buffer_create ();
    hb_buffer_set_flags (buffer, HB_BUFFER_FLAG_VERIFY);
    hb_buffer_add_utf8 (buffer, "ABCDEXYZ123@_%&)*$!", -1, 0, -1);
    hb_buffer_guess_segment_properties (buffer);
    hb_shape (input.font, buffer, nullptr, 0);
    hb_buffer_destroy (buffer);
  }

  /* ... then shape 16 code points taken from the input,
     after running test_font () over the font's other APIs ... */
}
```

The input is the font, at a scale of 12. Its last 64 bytes are read again as 16 code points to shape, and its last byte as a number of variation coordinates, taken from the bytes before it (`hb-shape-input.hh:243`). A newer, extended form ends with the magic `HBSUBFZ2` and a list of operations (add text, set an axis), so that a fuzzer can reach variations and text on purpose. `test_font ()` comes from `test/api/test-ot-face.c`: it calls many of the face and font APIs on the font, so the shaping fuzzer covers those too.

**The corpus.** `test/fuzzing/fonts/` holds 532 fonts, and `graphs/` ten inputs for the repacker. Most are named like `clusterfuzz-testcase-minimized-hb-subset-fuzzer-6461128124465152`: inputs that once made a fuzzer fail, minimized, and kept after the fix, under the names ClusterFuzz gave them. When HarfBuzz is built normally, with tests, the fuzzers aren’t linked with libFuzzer but with `main.cc`, which reads each file named on its command line and passes it to `LLVMFuzzerTestOneInput` once, printing TAP (`test/fuzzing/main.cc`). Meson runs them over the corpus, 64 files a test, as the `fuzzing` suite. So every crash ever found becomes a regression test that runs on every build. [Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html) is the code most of those crashes hardened.

**Continuous fuzzing.** `NEWS` for 1.0.5, in 2015, reports memory access bugs “discovered using libFuzzer”, and “we now have continuous fuzzing set up, to avoid issues like these creeping in again.” The repository’s own part of that is `.github/workflows/cifuzz.yml`: on every pull request, OSS-Fuzz’s CIFuzz action builds the fuzzers of the OSS-Fuzz project `harfbuzz` and runs them for 600 seconds, failing the pull request if they find a crash.

**Failing allocations.** Code that handles running out of memory rarely runs. When the fuzzers are built for libFuzzer (`-Dfuzzer_ldflags=…`), HarfBuzz is compiled with `HB_CUSTOM_MALLOC` and `src/failing-alloc.c` (`src/meson.build:659`), whose `hb_malloc_impl`, `hb_calloc_impl`, and `hb_realloc_impl` return null about one time in sixteen:

```c
void* hb_malloc_impl (size_t size)
{
  return (fastrand () % 16) ? malloc (size) : NULL;
}
```

`fastrand` is a linear congruential generator seeded with `alloc_state`, which each fuzzer sets from its input: the input’s size, or 0 (never fail) when the input’s last byte is below 0x80 (`hb-fuzzer.hh:28`). So half the inputs run with a working allocator, and the other half fail allocations at points that are random but the same every time the input is run, which is what makes a crash reproducible. [Reading HarfBuzz’s C++](reading-harfbuzz-cpp.html) has the “carry on, check once” style this forces on the code.

**What fuzzing can’t find.** A fuzzer needs a failure it can detect, and wrong output isn’t one. The shaping fuzzer sets `HB_BUFFER_FLAG_VERIFY`, but `hb_shape` returns nothing, and a failed check only prints a message (`hb-buffer-verify.cc:49`), so a verification failure doesn’t stop a fuzzing run (inferred from the code: nothing in the fuzzer reads the message). The exception is `hb-depend-closure-parity`, which runs on valid fonts, computes a glyph closure from hb-depend’s graph and from the subsetter, and fails if they differ ([hb-depend](hb-depend.html)). It is a correctness check that a machine can run without being told the answer, and so the only one of its kind here.

## Testing with a font of your own

Many of HarfBuzz’s own shaping tests use small fonts, each made for one question, with the output it should give ([The shaping tests](#the-shaping-tests)). The same method works for anyone who wants to know what HarfBuzz does with a rule: build a font that has that rule and little else, and shape some text with it. This book’s examples were all made that way, and so were the bugs it found, in the next section. It is also how to cut a misbehaving font down to the lookups in question.

Shaping never looks at outlines, so the glyphs can be plain boxes. What matters is their names, the `cmap`, the advances, and the layout tables. This program builds such a font from a feature file ([Reading feature files](reading-feature-files.html) explains enough of the language to read one) with fontTools, given the characters it needs and any glyphs the rules make that no character maps to:

```example
program: test-font/make-test-font.py
args: question.fea  question.ttf  fiT  f_i  f_i.short
show: source
```

The font below was built by this program, from a feature file that asks a question: does `calt` see the ligature `liga` made?

```
feature liga {
  sub f i by f_i;
} liga;

feature calt {
  sub f_i' T by f_i.short;
} calt;
```

```shape
question.ttf  fi  --language=en
question.ttf  fiT  --language=en
```

It does: `liga`’s lookup comes first in the LookupList, and under the default shaper the two run in one stage, in that order ([Feature order](feature-order.html)). The trace shows each step:

```trace
font: question.ttf
text: fiT
options: --language=en
from: start lookup 0
to: end lookup 1
```

Some things this book learned to do in its own test fonts:

* **Ask one question per font.** Two fonts that differ in one thing, such as the order of two feature blocks, answer a question better than one font with everything in it.
* **Number lookups on purpose.** A lookup’s place in the LookupList decides when it runs within a stage, and feaLib numbers lookups in the order it meets them. The fonts behind [Feature order](feature-order.html) number theirs in opposite orders, to find where stages end.
* **Pass `--language`** in every `hb-shape` command whose result could depend on it. Otherwise `hb-shape` takes the language from the locale.
* **Use `--trace`**, which needs a HarfBuzz built with detailed traces ([Building HarfBuzz](building-harfbuzz.html)), and `--verify`, `--show-flags`, and `--show-extents` ([The command-line tools](command-line-tools.html)).

## The bugs this book found

Writing this book meant building small fonts that exercise one thing each, shaping text with them, and checking every result against the code and the specifications. Some results didn’t match. Those are drafted as bug reports in [`notes/upstream-bug-reports.md`](https://github.com/Lorp/how-harfbuzz-works/blob/main/notes/upstream-bug-reports.md), in the book’s repository, eighty-three so far, each reproduced on HarfBuzz {{hb}} (commit `3df40d9b`), most with a font or a command that needs nothing from this book.

**None is yet on HarfBuzz’s issue tracker.** The first sixty-five went to HarfBuzz’s author directly, and many are already fixed (see the last column below), but they are still drafts, written by the book’s authors. Some are certainly bugs, some are matters of policy that HarfBuzz’s developers may well decide the other way, and a few were found by reading code and have no example yet.

The tables below give each draft’s number in that file, a one-line summary, the chapter that describes the behavior, and how it was checked:

* **Live.** The chapter shows the behavior in a block, built from HarfBuzz {{hb}} when the page is built.
* **Run.** Reproduced with HarfBuzz’s tools or a small program, but not shown live.
* **Read.** Found by reading the code.

The last column records what has happened upstream. Drafts 1–65 were shown to HarfBuzz’s author, Behdad Esfahbod, on 17 November 2026, and he fixed many of them on the `main` branch the same day. Drafts 1–82 were checked against `main` at commit `454f9c4` (17 November) on 18 November 2026, and draft 83 against `94715f6` (19 November) on 20 November, by rerunning its example or, for those found by reading, reading the code again. The column gives the commit that fixed a draft, with its pull request; “partly fixed” where some of a draft’s items are fixed; “changed” where the behavior is different but the problem remains; and “in progress” where a pull request that addresses it is open but not merged. An empty cell means the draft still describes `main`. Related issues come from a keyword search of HarfBuzz’s issues and pull requests, which isn’t exhaustive.

<!-- Generated by hand from notes/upstream-bug-reports.md. To add a draft: give it a
     row in the group that fits, with its number, a summary, the chapter that shows it
     and how it was checked; update the counts in the paragraph after the tables.
     The numbers are permanent, as HarfBuzz cites them: never renumber or reuse one. -->

### Shaping results

Wrong glyphs or positions from `hb_shape`, in fonts and text that are valid.

<div class="bugs">

| # | Summary | Chapter | Checked | Upstream |
|---|---|---|---|---|
| 5 | Two glyph-flag functions treat cluster level 3 as monotone | [Buffers](buffers.html) | Read | Fixed: commit [`7f0fe35`](https://github.com/harfbuzz/harfbuzz/commit/7f0fe35618c08a7089af610b7546fa1cba484c29) (pull request #6706) |
| 8 | A ranged request then a global one for the same feature clears the global bit, turning off every global feature in the range | [From features to lookups](from-features-to-lookups.html) | Live | Fixed: commit [`5d9dfde`](https://github.com/harfbuzz/harfbuzz/commit/5d9dfde259979dd91439903d09e708d16a41bbf7) (pull request #6704) |
| 10 | In the Indic shapers’ normalization mode, text without marks is decomposed but never recomposed | [Normalization](normalization.html) | Live | Fixed: commit [`bc7dff9`](https://github.com/harfbuzz/harfbuzz/commit/bc7dff9a51e900d25d35ee1a903ab496caf0feae) (pull request #6705) |
| 11 | A variation-selector cluster ignores the not-found glyph | [Normalization](normalization.html) | Live | Fixed: commit [`97d8794`](https://github.com/harfbuzz/harfbuzz/commit/97d879446fe4de6f09ece771ef645127947f7795) (pull request #6699) |
| 12 | A mark skips a base whose `mark` bit is off and attaches to an earlier one | [GPOS: positioning glyphs](gpos.html) | Live | In progress: pull request #6736, not merged |
| 15 | A cross-stream `kern` value of 0x8000 isn’t treated as a reset | [Legacy kern](legacy-kern.html) | Live | In progress: pull request #6732, not merged |
| 16 | Fallback mark positioning ignores the base’s x offset | [Fallbacks](fallbacks.html) | Live | Fixed: commit [`641971d`](https://github.com/harfbuzz/harfbuzz/commit/641971dd14283a97f5e7cf8a7f12ac6337db74f7) (pull request #6701) |
| 17 | Fallback positioning centers LEFT and RIGHT marks, contrary to its comment | [Fallbacks](fallbacks.html) | Live | In progress: pull request #6742, not merged. It rewrites the comment and keeps the centering |
| 18 | Vertical `kern` subtables can never apply | [Legacy kern](legacy-kern.html) | Live | In progress: pull request #6734, not merged |
| 19 | The Hangul shaper’s dotted circle copies the tone mark’s properties | [Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html) | Live | Fixed: commit [`2831a8a`](https://github.com/harfbuzz/harfbuzz/commit/2831a8a45c77c180373987312958d31b3575a72c) (pull request #6711) |
| 20 | Two dotted circles before a Hangul tone mark at the start of text | [Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html) | Live | Fixed: commit [`59fa8f0`](https://github.com/harfbuzz/harfbuzz/commit/59fa8f0c28df047b6786a60febf2c8b53a694e05) (pull request #6712) |
| 21 | Hebrew: a `mark` feature under `DFLT` stops composition, but GPOS isn’t applied | [Hebrew, Thai, Lao, and Hangul](hebrew-thai-lao-and-hangul.html) | Live | In progress: pull request #6738, not merged |
| 22 | Indic `init` ignores pre-context | [The Indic model](indic-model.html) | Live | Fixed: commit [`5795f86`](https://github.com/harfbuzz/harfbuzz/commit/5795f8699503de6c64206cb939eaae9086b279f1) (pull request #6713) |
| 24 | `stch` tiles are shifted when they fit the word exactly | [Joining scripts](joining-scripts.html) | Live | In progress: pull request #6733, not merged |
| 29 | Khmer moves a second COENG + RO in front of the first | [Khmer and Myanmar](khmer-and-myanmar.html) | Live | In progress: pull request #6735, not merged |
| 30 | USE: a mark after a space attaches to the space | [The Universal Shaping Engine](universal-shaping-engine.html) | Live | |
| 31 | USE: a space doesn’t end a word for topographical forms | [The Universal Shaping Engine](universal-shaping-engine.html) | Live | |
| 32 | USE: ZWNJ after a virama doesn’t stop a half form | [The Universal Shaping Engine](universal-shaping-engine.html) | Live | |
| 33 | Indic: a broken cluster starting with RA + virama loses its reph | [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html) | Live | |
| 34 | A ZWJ defeats the vowel constraints | [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html) | Live | |
| 35 | The vowel-constraint dotted circle copies the next character’s properties | [Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html) | Live | Fixed: commit [`74fc8c8`](https://github.com/harfbuzz/harfbuzz/commit/74fc8c86c594ec594904fde28b548f5fc6ef2384) (pull request #6710) |
| 38 | With GSUB, GPOS, and `kerx`, `kerx` never applies and marks stop being zeroed | [AAT positioning](aat-positioning.html) | Live | |
| 39 | `trak` vertical tracking is added with the wrong sign | [AAT positioning](aat-positioning.html) | Live | Fixed: commit [`45c7759`](https://github.com/harfbuzz/harfbuzz/commit/45c7759a025ace1fd7ca632114ec7111808d5fc5) (pull request #6700), with [`1e2cf5d`](https://github.com/harfbuzz/harfbuzz/commit/1e2cf5dafa790d809dec0ef05850b1dd3703d1b5) (#6716) for the Core Text font functions |
| 40 | `kerx` format 4 control-point attachment does nothing with the `ot` font functions | [AAT positioning](aat-positioning.html) | Live | |
| 58 | Cross-stream kerning in legacy `kern` and `kerx` raises every later glyph but marks only the pair unsafe to break | [For applications](for-applications.html) | Live | |
| 59 | Hangul at cluster level 1 leaves a trailing jamo in its own cluster, unflagged | [For applications](for-applications.html) | Live | Fixed: commit [`8e6c16e`](https://github.com/harfbuzz/harfbuzz/commit/8e6c16eefc3dc7480326faa81de903b388fff151) (pull request #6709) |

</div>

### Limits and budgets

Places where a limit meant to stop malicious fonts changes the result for valid ones. [Limits](limits.html) lists every limit.

<div class="bugs">

| # | Summary | Chapter | Checked | Upstream |
|---|---|---|---|---|
| 1 | A null or unknown-format Coverage in a format 1 single lookup charges about 2 billion operations to the sanitizer, which then drops the whole GSUB or GPOS | [Fonts as bytes](fonts-as-bytes.html) | Live | Fixed: commit [`6426ee4`](https://github.com/harfbuzz/harfbuzz/commit/6426ee4ca8a218ecf7e8b8dd92997f6d435ff03f) (pull request #6696) |
| 9 | Mask bit 30 is never handed out, so 26 bits are free for features, not 27 | [From features to lookups](from-features-to-lookups.html) | Live | Fixed: commit [`ec94764`](https://github.com/harfbuzz/harfbuzz/commit/ec9476415057f3437019eed9b773984438d1d802) (pull request #6697) |
| 13 | Cursive chains that run against the buffer’s direction break after 64 links | [GPOS: positioning glyphs](gpos.html) | Live | |
| 23 | Syllables longer than 64 glyphs are reordered in pieces | [The Indic model](indic-model.html) | Run | Changed, not fixed: commit [`fd57025`](https://github.com/harfbuzz/harfbuzz/commit/fd57025171ff9ba3c77525d02f558a780cb0f32c) (pull request #6558) keeps the pieces the same in every pass and makes the whole syllable one cluster, but this draft’s example is still reordered wrongly at the cut |
| 28 | A CFF charstring with no `endchar` runs to 200,000 operations and uses up the drawing budget for later glyphs | [Drawing outlines](drawing-outlines.html) | Run | In progress: pull request #6737, not merged |
| 43 | The subsetter’s GSUB closure stops after 14 passes, losing glyphs from long nested chains that shaping reaches | [Subsetting](subsetting.html) | Live | Changed, not fixed: commit [`0209ec2`](https://github.com/harfbuzz/harfbuzz/commit/0209ec2865b55e892897966e95dfb8915a1309e9) (pull request #6725, for draft 44) allows 18 passes, so the example’s chain of 20 now stops at `s18`. Related, not the same: [issue #5993](https://github.com/harfbuzz/harfbuzz/issues/5993), closed: the limit is kept because glyphs reached only by applying a lookup again and again aren’t reachable by shaping. The glyphs in this draft are reached by one shaping run |
| 44 | `HB_CLOSURE_MAX_STAGES` is 12, though its comment requires more than the Indic shaper’s 14 pauses | [Subsetting](subsetting.html) | Read | Fixed: commit [`0209ec2`](https://github.com/harfbuzz/harfbuzz/commit/0209ec2865b55e892897966e95dfb8915a1309e9) (pull request #6725) |
| 47 | The sanitizer’s operation budget rejects a whole valid GSUB whose few single substitutions cover many glyphs by range | [Limits](limits.html) | Run | |
| 48 | The subsetter’s 256× buffer cap makes a valid subset fail when a tiny table legitimately grows | [Writing tables](writing-tables.html) | Run | |
| 54 | Texts of 524,289 to 1,048,575 characters go almost unshaped: the operation budget starts negative | [Limits](limits.html) | Run | Changed, not fixed: on `main` the budget still starts negative, and from 524,300 characters not even the first ligature forms |

</div>

### Extents, drawing, and subset fonts

<div class="bugs">

| # | Summary | Chapter | Checked | Upstream |
|---|---|---|---|---|
| 3 | With synthetic bold, grade, or slant, an empty glyph’s extents are `<0,-1,-1,1>` | [Fonts and font functions](fonts-and-font-functions.html) | Run | Fixed: commit [`46ab0d0`](https://github.com/harfbuzz/harfbuzz/commit/46ab0d095f021f98ad20c4480814ebdcc2a3d690) (pull request #6685) |
| 4 | Scaled glyph extents are rounded inwards vertically, so the box doesn’t cover the ink | [Where metrics come from](where-metrics-come-from.html) | Live | Fixed: commit [`f5e925c`](https://github.com/harfbuzz/harfbuzz/commit/f5e925cd256fd856f30298b89fe98772be5f6bf9) (pull request #6707) |
| 25 | CBDT format 19 images are never painted | [Color](color.html) | Read | |
| 27 | Point matching in nested composites counts from the wrong start | [Drawing outlines](drawing-outlines.html) | Live | |
| 36 | `hb-vector`’s PDF output drops PNG alpha | [hb-vector](hb-vector.html#color-glyphs-in-pdf) | Run | |
| 45 | MATH variants and italics corrections are lost for glyphs that only GSUB produces | [Subsetting](subsetting.html) | Live | In progress: pull request #6745, not merged |
| 50 | A reordering custom glyph map breaks PairPos and ClassDef in the subset | [Subsetting](subsetting.html) | Live | |
| 51 | Subsetting a symbol font drops its only, (3,0), `cmap` subtable | [Subsetting](subsetting.html) | Live | |
| 52 | The keep-`.notdef`-outline flag is ignored for CFF | [Subsetting](subsetting.html) | Live | |
| 61 | Small instancing differences from fontTools: an `avar` map one unit off after limiting, a misleading VARC refusal, an unreachable `MVAR` region | [Instancing](instancing.html) | Live | |
| 66 | `hb_color_lerp` reverses a color’s bytes, so every PDF sweep, and SVG sweeps that cross 0°, have the wrong colors | [hb-vector](hb-vector.html#color-glyphs-in-pdf) | Run | |
| 67 | `hb-vector`’s PDF sweeps leave a square hole at their center, from 16-bit mesh coordinates | [hb-vector](hb-vector.html#color-glyphs-in-pdf) | Run | |
| 68 | `hb-vector`’s PDF output ignores custom palette colors | [hb-vector](hb-vector.html#color-glyphs-in-pdf) | Run | |
| 69 | `hb-vector`’s PDF compositing isn’t isolated, so SCREEN and DIFFERENCE blend with the white page | [hb-vector](hb-vector.html#color-glyphs-in-pdf) | Run | |
| 70 | hb-gpu drops a fill whose only clip is a rectangle, though its comment says rectangles are just ignored | [hb-gpu](hb-gpu.html#what-isnt-supported) | Run | |
| 75 | `hb-vector --show-extents` and `hb-raster --show-extents` draw each box after the first at twice its pen position | [The command-line tools](command-line-tools.html#a-bug-in-show-extents) | Run | |

</div>

### API and format consistency

The same thing done differently in two places, or defined differently in two documents.

<div class="bugs">

| # | Summary | Chapter | Checked | Upstream |
|---|---|---|---|---|
| 6 | Three slips in `hb-shape-plan.cc`: a loop index, a null check after the dereference, a missing null-face guard | [Shape plans and their cache](shape-plans-and-their-cache.html) | Read | Fixed: commits [`caf12a8`](https://github.com/harfbuzz/harfbuzz/commit/caf12a809a78332fb320bc1375eca31ab838a0f6) (pull request #6693) and [`93d26d8`](https://github.com/harfbuzz/harfbuzz/commit/93d26d851047e13459eac70197f00298bfdd34ad) (#6698) |
| 7 | FeatureVariations minor version 1 means one thing to HarfBuzz and another to the ISO draft, and a font following the draft loses its GSUB | [From features to lookups](from-features-to-lookups.html) | Live | |
| 14 | With `HB_NO_HINTING`, y Device tables fall through into the variation branch, unlike x | [GPOS: positioning glyphs](gpos.html) | Read | Fixed: commit [`489157f`](https://github.com/harfbuzz/harfbuzz/commit/489157f826ff7c32493d6d0a05b7e608605c27f8) (pull request #6694) |
| 26 | The bitmap tables are tried in one order for images and extents, the other for painting | [Color](color.html) | Read | Fixed: commit [`7e97cd8`](https://github.com/harfbuzz/harfbuzz/commit/7e97cd8a182651f2ca3d2311f0910ca0ce64e927) (pull request #6723) |
| 37 | Smaller `hb-vector` and `hb-gpu` differences: PDF gradients that only pad, palette functions with other types than their twins, stale comments | [hb-vector](hb-vector.html#color-glyphs-in-pdf), [hb-gpu](hb-gpu.html) | Read | Partly fixed: commit [`24fe9f0`](https://github.com/harfbuzz/harfbuzz/commit/24fe9f0e258bfe008beea1a79c2efb3bae81b2bb) (pull request #6691) corrects the stale comments and documentation, and [`aa3cd40`](https://github.com/harfbuzz/harfbuzz/commit/aa3cd40bcff9f4180f61da69a728411397bacad8) (#6730) documents that PDF gradients only pad; the API differences remain |
| 41 | Of two requests for one feature, AAT keeps the first and OpenType the last | [AAT inside HarfBuzz](aat-inside-harfbuzz.html) | Live | Fixed: commit [`f346ea1`](https://github.com/harfbuzz/harfbuzz/commit/f346ea17a9cedce7ba98f45782aa27faa597a0e3) (pull request #6714) |
| 55 | `HB_LEAN` removes drawing and painting in every Meson build | [Compile-time configuration](compile-time-configuration.html) | Run | Fixed: commit [`c90000d`](https://github.com/harfbuzz/harfbuzz/commit/c90000dd8ee5a593bc60e65930d3aed501aca5bf) (pull request #6724) |
| 56 | `hb-features.h` never defines `HB_HAS_GPU` or `HB_HAS_GRAPHITE` | [Compile-time configuration](compile-time-configuration.html) | Run | Fixed: commits [`2b873b8`](https://github.com/harfbuzz/harfbuzz/commit/2b873b805800dcad37827f90a5c28ccb6ccc4ba8) (pull request #6721) and [`506cc94`](https://github.com/harfbuzz/harfbuzz/commit/506cc943b3c2ad82c5398361afdaf6e9eaad6b0f) (#6722) |
| 62 | `hb_style_get_value` returns OS/2 optical sizes in twentieths of a point | [Other tables](other-tables.html) | Live | Fixed: commit [`b14a94e`](https://github.com/harfbuzz/harfbuzz/commit/b14a94e52fed2ebb39744a4596ec2c840beffef3) (pull request #6695) |
| 63 | BASE min/max: missing values read as 0, and MinMax without BaseValues hides `DFLT` | [Other tables](other-tables.html) | Run | |
| 64 | `STAT::get_value` takes the first axis value, and STAT suppresses synthetic slant | [Other tables](other-tables.html) | Live | The synthetic slant is in progress: pull request #6743, not merged |
| 72 | `HB_FEATURES_H` is both `harfbuzz-world.cc`’s header name and `hb-features.h`’s include guard, so Meson’s header can’t be named | [Building HarfBuzz](building-harfbuzz.html#single-file-builds) | Run | |
| 77 | Smaller things in the build: Graphite in the single-file build, the `libs` target without hb-gpu, `meson build` without `setup`, an undefined `HAVE_ISATTY` | [Building HarfBuzz](building-harfbuzz.html#single-file-builds) | Run | The Graphite item is fixed by commit [`506cc94`](https://github.com/harfbuzz/harfbuzz/commit/506cc943b3c2ad82c5398361afdaf6e9eaad6b0f) (pull request #6722) |
| 79 | `hb_directwrite_font_set_funcs` takes a reference to the DirectWrite font face that nothing releases, where the Core Text version takes none | [Integrations](integrations.html#directwrite) | Read | |
| 80 | `_hb_gdi_reference_table` returns before its `ReleaseDC` guard when `SelectObject` fails, leaking the screen DC | [Integrations](integrations.html#gdi-and-uniscribe) | Read | |
| 82 | USE: the generator’s list of generic bases (U+2015, U+2022, U+25FB to U+25FE) never applies, and they come out `O` | [The Universal Shaping Engine](universal-shaping-engine.html#the-categories) | Run | |

</div>

### Documentation and messages

<div class="bugs">

| # | Summary | Chapter | Checked | Upstream |
|---|---|---|---|---|
| 2 | The “start table GPOS” trace message prints GSUB’s chosen script | [Choosing a script shaper](choosing-a-script-shaper.html) | Live | Fixed: commit [`24795ef`](https://github.com/harfbuzz/harfbuzz/commit/24795efd37271e6fac4e1e44316ccf690b63e31f) (pull request #6686) |
| 42 | hb-depend: errors in its header and design notes, a declared function that doesn’t exist, a wrong build option in the fuzzing README | [hb-depend](hb-depend.html) | Run | Partly fixed: commits [`88bb79a`](https://github.com/harfbuzz/harfbuzz/commit/88bb79a408620943fb475857777c2eceabb76ffb) (pull request #6703) and [`202b3e2`](https://github.com/harfbuzz/harfbuzz/commit/202b3e2c282a36f710834e61f460d8f48e6a10b9) (#6692) correct the documentation; removing the unused declaration and fields is in progress (pull request #6744); the parity test’s order remains |
| 46 | `hb_set_invert` is documented as “Since: 3.0.0”, but `NEWS` has it before 1.6.1 | [Reading HarfBuzz’s C++](reading-harfbuzz-cpp.html) | Read | Fixed: commit [`72e4cf3`](https://github.com/harfbuzz/harfbuzz/commit/72e4cf3a3479c08a5ae6d34255eb7be51c320379) (pull request #6690) |
| 49 | `docs/serializer.md` and `docs/repacker.md` are out of date | [Writing tables](writing-tables.html) | Read | Fixed: commit [`4d41c69`](https://github.com/harfbuzz/harfbuzz/commit/4d41c69d42fa9e73885a93a6396acbb582c9dee8) (pull request #6702) |
| 53 | Small faults in the data generators, none affecting the tables | [Regenerating the tables](regenerating-the-unicode-and-shaping-tables.html) | Read | Partly fixed: commits [`ebfcf19`](https://github.com/harfbuzz/harfbuzz/commit/ebfcf19c720f3328754ecdde620eb45c2fa8088c) (pull request #6688), [`c66b1a5`](https://github.com/harfbuzz/harfbuzz/commit/c66b1a505795d701b27c67702809814ee250d6cd) (#6689), and [`b873113`](https://github.com/harfbuzz/harfbuzz/commit/b873113f410f0fa0b215f225aec5d76eb55c22e3) (#6715); most of the rest is in progress (pull requests #6739 and #6740) |
| 57 | Configuration macros and limits defined but unused, or used but undocumented | [Compile-time configuration](compile-time-configuration.html) | Read | Partly fixed: commits [`9172214`](https://github.com/harfbuzz/harfbuzz/commit/91722141bb48a8414284cb3b4001b0c98cce9a19) (pull request #6728) and [`9e6b1a9`](https://github.com/harfbuzz/harfbuzz/commit/9e6b1a989857e1e2809186d045bb33416120c834) (#6727) remove the unused macros and correct `CONFIG.md`’s `HB_MINI`; the other items remain |
| 60 | `hb-shape --text-before` echoes its value to stderr | [For applications](for-applications.html) | Run | Fixed: commit [`55ecd75`](https://github.com/harfbuzz/harfbuzz/commit/55ecd750d40e20207cb56aadbaf597bbd084246f) (pull request #6687) |
| 65 | Smaller things in `name`, BASE, and MATH: `hb-info --list-names`, a sign error, a quadratic risk, a missed script tag | [Other tables](other-tables.html) | Live | Partly fixed: commit [`eaf004a`](https://github.com/harfbuzz/harfbuzz/commit/eaf004a2c5a745f790e60df5e7177db765a84b7b) (pull request #6708) fixes the sign error; `hb-info --list-names` is in progress (pull request #6741) |
| 71 | hb-gpu’s stem darkening is documented, and used by its viewer, with pixels per font unit for its ppem | [hb-gpu](hb-gpu.html#small-sizes) | Read | |
| 73 | `hb-shape -v` turns on `--ned` as well as `--verbose` | [The command-line tools](command-line-tools.html#reading-the-output) | Live | |
| 74 | `--features` and `--variations` split at spaces, so the CSS forms their help offers don’t work | [The command-line tools](command-line-tools.html#features) | Run | |
| 76 | Smaller things in the renderers: hb-raster’s HSL luminosity weights, stale hb-vector and hb-gpu documentation | [hb-raster](hb-raster.html#groups-and-the-composite-modes), [hb-gpu](hb-gpu.html) | Run | |
| 78 | Smaller things in the command-line tools: `--font-size` help, an unused `refuse_tty`, `hb-fc-list -V` | [The command-line tools](command-line-tools.html#the-tools-that-arent-installed) | Run | |
| 81 | Smaller things in the integration documentation: `hb_ft_font_set_funcs` and `hb_ft_hb_font_changed`, swapped cairo scale factors, missing `Since:` lines, `NEWS` for 11.0.0, the user manual’s integration chapter | [Integrations](integrations.html) | Read | |
| 83 | The user manual’s Configuration options describe ten of the thirty-three Meson options | [Compile-time configuration](compile-time-configuration.html#the-meson-options) | Read | |

</div>

Of the eighty-three, forty-three are shown live in the book, twenty-four were run outside it, and sixteen were found by reading. On `main`, twenty-seven are fixed and six partly fixed, three behave differently but aren’t fixed, and ten have a pull request open; the other thirty-seven still apply. The live blocks are built from {{hb}}, so they still show the bugs that `main` has fixed.

## Where the bugs are

None of the eighty-three is a crash, a hang, or a read out of bounds, though the book’s fonts include broken ones on purpose. That part of HarfBuzz is well defended: a decade of continuous fuzzing has turned every such failure into a test, and the sanitizer and the budgets stop the rest. What is left is output that is wrong but well formed, and, in two Windows integrations read but not run, a reference that is never released (79, 80). No fuzzer can see it, because nothing tells a fuzzer what the right answer is, and [verification](#verification) can’t either if the answer is consistently wrong. Only a test with an expected answer catches it, and only on the paths the tests take.

The drafts show where those paths stop.

**Combinations.** Most of the shaping results need two things at once that are each tested alone: a ranged feature and a global request for the same tag (8), a tone mark at the start of text where two dotted-circle paths both apply (20), a font with GSUB, GPOS *and* `kerx` (38), a Hebrew `mark` feature under `DFLT` rather than `hebr` (21), vertical text with a `kern` table (18), a kerned base with a fallback-positioned mark (16). The in-house tests are recorded one subject to a file, so a combination is tested once someone has met it (inferred from how `record-test.sh` works). A small font built with exactly the two features finds it directly.

**Paths the tests miss.** In-house `arabic-stch.tests` passes, with verification, on every font-functions backend, yet `stch` is wrong for a word that its tiles fit exactly (24), because the test’s words always take the other branch. Cluster level 3 arrived in 11.0.0, and two functions written before it were never taught about it (5). CBDT format 19 is never painted (25), and nested point-matched composites attach to the wrong point (27): rare formats, rare structures.

**Copies that drifted apart.** Something done in several places gets fixed or extended in one of them. The GPOS trace message copies the GSUB code above it and kept its index (2). `get_y_delta` lost the guard that `get_x_delta` has (14). Four paths insert dotted circles, and they give the circle three different sets of Unicode properties (19, 35). The AAT and OpenType maps merge repeated features in opposite orders (41), and the bitmap tables are tried in different orders by different callers (26). Comparing the copies finds these; testing one copy doesn’t.

**Limits that real text reaches.** Fuzzing pushes for limits, and the limits are needed. But a limit set to stop a hostile font is sometimes within reach of a legitimate one: 64 links of cursive attachment in Nastaliq (13), a 64-glyph syllable (23), a closure cut at 14 passes (43, 44), 26 mask bits (9). Each degrades quietly, by design: the output is merely wrong. The worst cases are 1 and 47, where the sanitizer’s budget costs a valid font every substitution it has, and 54, where a text of over half a million characters is left almost unshaped.

**Comments and documentation.** A comment says LEFT and RIGHT marks aren’t positioned, and they are (17); another states a rule its own constant breaks (44); hb-depend’s notes describe an earlier design (42); a `Since:` line is wrong (46).

The pattern suggests where to look next. Most of these drafts came from fonts small enough to have one feature, one lookup, or one table of interest, and every one of those fonts could become a test line in `test/shape/data/in-house/` as it stands. `record-test.sh` would subset it, hash it, and print the line.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-buffer.cc` | `hb_buffer_set_message_func`, `message_impl`, `hb_buffer_changed` |
| `src/hb-debug.hh` | `HB_DEBUG_*`, `hb_auto_trace_t`, the `TRACE_*` macros, `HB_BUFFER_MESSAGE_MORE` |
| `src/hb-buffer-verify.cc` | `HB_BUFFER_FLAG_VERIFY`’s three checks and how they report |
| `src/hb-shape.cc` | `hb_shape_full`, which keeps the text and calls the verifier |
| `util/shape-output.hh` | `hb-shape --trace` |
| `test/shape/run-tests.py`, `test/shape/record-test.sh` | running and recording shaping tests |
| `test/shape/data/{in-house,aots,text-rendering-tests}/` | the three sets of `.tests` files and their fonts |
| `test/api/hb-test.h`, `test/api/test-*.c` | the GLib-based API tests |
| `test/subset/run-tests.py`, `test/subset/generate-expected-outputs.py` | subset tests, and expected fonts checked against fontTools |
| `test/threads/`, `perf/` | the threading tests and the benchmarks |
| `test/fuzzing/`, `src/failing-alloc.c` | the fuzzers, their corpus, the TAP runner, the failing allocator |
| `.github/workflows/cifuzz.yml`, `sanitizers.yml` | fuzzing on pull requests; the sanitizer builds |

## In short

* Buffer messages report each step of a run and can skip it; the detailed messages from inside lookups need a build with `HB_BUFFER_MESSAGE_MORE`, which is why this book builds HarfBuzz separately for its traces.
* `HB_DEBUG_*` are compile-time switches for HarfBuzz’s developers, each a depth to which the work of the table code is printed.
* `HB_BUFFER_FLAG_VERIFY` makes HarfBuzz reshape its result in pieces and compare. It needs no expected answer, so it runs everywhere, but a consistently wrong result passes.
* `test/shape` holds about 6,300 test lines in three sets. Each runs with verification, once for every kind of font functions the build has, through one `hb-shape --batch` process.
* `test/api` checks the C API with GLib’s framework; `test/subset` compares subset fonts byte for byte with expected fonts that fontTools agrees with.
* The fuzzers look for crashes, hangs, and runaway memory, with allocations that fail at random. Every failure they find is kept and rerun as a test on every build.
* A font of boxes with a rule or two, built from a feature file, is the quickest way to find out what HarfBuzz does with a rule.
* The book’s eighty-three draft bug reports, none yet on HarfBuzz’s issue tracker, are nearly all wrong-but-valid output: combinations no test has, branches the tests miss, copies that drifted apart, limits real text can reach, and comments that no longer match the code. Checked against `main` on 18 November 2026, twenty-seven were fixed, six partly, and ten had pull requests open.
