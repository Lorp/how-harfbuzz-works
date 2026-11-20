# Testing and debugging fonts with HarfBuzz

A font maker turns to a shaping engine with two kinds of question. The first comes while a font is being made: a rule has been written, and the text doesn’t come out as it should. The second comes once the font works: will it still work after the next change? This chapter answers both with HarfBuzz’s own tools: the first by narrowing a problem down to the step that causes it, the second with tests that every build of the font must pass.

HarfBuzz is the natural engine for both. Chrome, Firefox, Android, and most other software shape text with it, so for most of a font’s users, what HarfBuzz does with the font *is* what the font does. `hb-shape` gives the same answer those programs get for the same text and settings, and it can show each step it took to get there. And HarfBuzz’s own test suite has a format for expected results, and a runner for them, that work as well for a font maker’s tests as for HarfBuzz’s.

The chapter is for font makers and font engineers. Its examples use small test fonts built from feature files with the program in [Testing with a font of your own](testing-harfbuzz.html#testing-with-a-font-of-your-own), so their glyphs are boxes. The switches it uses are explained in [The command-line tools](command-line-tools.html), and how HarfBuzz tests itself is in [Testing HarfBuzz](testing-harfbuzz.html).

## When a font doesn’t work

The font in this section has two rules that don’t do what its maker meant. Its feature file:

```
languagesystem DFLT dflt;
languagesystem latn dflt;

feature liga {
  script DFLT;
  sub f i by f_i;
} liga;

feature dlig {
  sub T h by T_h;
} dlig;
```

Its maker reports that neither ligature ever forms. The steps below work for any such problem: reproduce it, find the step that goes wrong, decide whose problem it is, cut it down, and keep it as a test.

### Reproduce it with hb-shape

Start by getting `hb-shape` to give the wrong result. Use the text that goes wrong, and give it everything the application gives its shaper: the language (from the document, such as an HTML `lang` attribute, or from the user’s settings), the script and direction if the application sets them, and the features it turns on or off, such as CSS `font-feature-settings` ([Direction, script, and language](command-line-tools.html#direction-script-and-language), [Features](command-line-tools.html#features)). Leave one out and `hb-shape` may be answering a different question: a `locl` lookup that runs only for one language, or a feature the application turns off.

```shape
broken.ttf  fit  --language=en
broken.ttf  Th  --language=en
```

Both go wrong here, as reported. If `hb-shape` gets the right answer, the question moves to the application: what it passes to HarfBuzz, whether it has the build of the font it should (an installed copy, a cached web font), and whether it shapes with HarfBuzz at all.

### Find the step

`hb-info` says what the font offers for the text’s script and language ([Which features apply in this language?](command-line-tools.html#which-features-apply-in-this-language)):

```info
broken.ttf  --list-scripts
broken.ttf  --list-features --script=Latn
```

The font has two scripts, `DFLT` and `latn`, and under `latn` it has only `dlig`. Latin text gets the features of the font’s `latn` script, and falls back to `DFLT` only if the font has no `latn` ([Choosing a script shaper](choosing-a-script-shaper.html)), so the `liga` rule, written under `DFLT` alone, never runs. A trace shows the same from the other side: GSUB starts, under the script tag `latn`, and ends without running a lookup:

```trace
font: broken.ttf
text: fit
options: --language=en
from: start table GSUB
to: end table GSUB
```

Shaped as text whose script `DFLT` serves, the rule works, so the rule itself is right:

```shape
broken.ttf  fit  --language=en  --script=Zyyy
```

The fix is in the feature file: write the rule before any `script` statement, which registers it under every language system, as most feature files do ([Reading feature files](reading-feature-files.html)).

The *Th* ligature is a different case. `dlig` is registered under `latn`, but it is a discretionary feature, off unless asked for. HarfBuzz turns on a fixed set of features by default, and `dlig` isn’t one of them ([Which features are asked for](from-features-to-lookups.html#which-features-are-asked-for)). Asked for, it works:

```shape
broken.ttf  Th  --language=en  --features=dlig
```

So nothing is broken: the user has to turn the feature on (in CSS, `font-variant-ligatures: discretionary-ligatures`). If the ligature was meant to form always, it belongs in `liga` or `calt`, not `dlig`.

When the features are all there, the trace shows which lookup did the wrong thing, or which one never ran, and the recipe [Why didn’t this ligature form?](command-line-tools.html#why-didnt-this-ligature-form) works through one. Turning features off one at a time, with `--features=-calt` and so on, finds which feature is responsible when there are many.

### Decide whose problem it is

Most problems are in the font, but not all. When the font’s tables look right and the result is still wrong, try other engines: the same text in another HarfBuzz release, in the platform shapers where HarfBuzz is built with them, and in HarfRust ([Other shapers and other versions](#other-shapers-and-other-versions)). If every engine gives the same wrong result, the font is almost certainly the cause, however right the rule looks: read it again beside the trace. If HarfBuzz alone differs, look in this book’s chapter for the script, since many differences are deliberate, and in HarfBuzz’s issues, since many are known. If it is still unexplained, it may be a HarfBuzz bug, and the next step makes the report.

### Cut it down

A problem is easiest to understand, and to report, in a small font. `hb-subset` keeps what a text needs and drops the rest ([hb-subset](command-line-tools.html#hb-subset)):

```
$ hb-subset broken.ttf --text="fit" --glyph-names -o fit.ttf
```

`--glyph-names` keeps the glyph names, which a subset otherwise drops, so that the results still read `f_i`, not a glyph number. Check that the subset still goes wrong. Then, if there is a feature file, cut the layout down further: take out features, then lookups, then rules, checking each time, until only what goes wrong is left. If the outlines don’t matter, rebuild what is left with box glyphs. HarfBuzz’s own tests are made the same way, from a font subset to the text of the test ([The format of a test](testing-harfbuzz.html#the-format-of-a-test)), and a bug report with a font of a few glyphs, the `hb-shape` command, and the output expected is one its developers can turn straight into a test.

### Keep the case

Once the problem is fixed, keep the text that went wrong, with its options and the result it should give, as a test. Then the problem can’t come back unnoticed. The rest of the chapter is about such tests.

## Keeping a font working

Fonts are revised after they ship, and their layout tables with them. A new alternate is added, a class gains a glyph, a feature file is reordered, a glyph is renamed, a compiler is updated. Each change can alter how some text comes out, and nothing in the font says which. The way to find out is to keep a record of what the font did, and compare every new build with it.

The examples from here on use two releases of one test font. Release 1 has an *fi* ligature and kerns *T* with *o*:

```
feature liga {
  sub f i by f_i;
} liga;

feature kern {
  pos T o -80;
} kern;
```

Release 2 adds a contextual alternate, a different *o* after *T*, and nothing else:

```
feature calt {
  sub T o' by o.alt;
} calt;
```

It’s a common kind of change, and it has a common kind of mistake in it: the kerning wasn’t updated for the new glyph. Nothing warns about it. The font compiles, and each feature does what its rules say.

## Recording what the font does

A test is a text, the options to shape it with, and the result. The result isn’t written by hand: it is what HarfBuzz gives now, recorded once and checked by eye, and from then on it is what every later build must give. Here is what release 1 gives for four texts:

```shape
release-1.ttf  To  --language=en
release-1.ttf  fit  --language=en
release-1.ttf  fi  --language=en  --features=-liga
release-1.ttf  To fit  --language=en
```

Each is right: *T* and *o* are kerned by −80, and *fi* is one glyph, except where `liga` is turned off.

HarfBuzz keeps its own expected results in `.tests` files, one test to a line: the font, the `hb-shape` options, the text as code points, and the expected output, separated by semicolons ([The format of a test](testing-harfbuzz.html#the-format-of-a-test)). Nothing in the format is particular to HarfBuzz’s fonts, so a font maker’s tests can use it too, and HarfBuzz’s runner will run them. This program records a `.tests` file from a list of cases, by running `hb-shape` on each:

```example
program: font-tests/record-tests.py
args: release-1.ttf
show: source
```

Its cases file has one case to a line, the text and, after a tab, the options:

```
To	--language=en
fit	--language=en
fi	--language=en --features=-liga
To fit	--language=en
```

Run on release 1, saved as `myfont.ttf`, the program writes:

```
myfont.ttf;--language=en;U+0054,U+006F;[T=0+420|o=1+500]
myfont.ttf;--language=en;U+0066,U+0069,U+0074;[f_i=0+900|t=2+500]
myfont.ttf;--language=en --features=-liga;U+0066,U+0069;[f=0+500|i=1+500]
myfont.ttf;--language=en;U+0054,U+006F,U+0020,U+0066,U+0069,U+0074;[T=0+420|o=1+500|space=2+500|f_i=3+900|t=5+500]
```

The results are the ones above. The font is named without a folder, because the runner finds it beside the `.tests` file, so each build of the font is saved under the same name in the same place. Pass `--language` in every case: `hb-shape` otherwise takes the language from the locale, and the recording and the rerun could disagree. (The program sets `LC_ALL=C`, as HarfBuzz’s runner does, so they wouldn’t here, but a case recorded by hand might.)

Glyph names make the results readable, and a font built without them (a `post` table of version 3, as many shipping fonts have) is recorded with glyph IDs instead, as `gid` followed by the number. Either works, but a test with names is easier to check by eye and survives a change in glyph order. Record from a build with names if the build process can make one.

## Running the tests

HarfBuzz’s runner is `test/shape/run-tests.py`, in its source tree. It is one Python file with no dependencies beyond Python itself, so it can be copied out and used with any `hb-shape` ([Building HarfBuzz](building-harfbuzz.html) shows how to get one). It takes the path of `hb-shape`, then one or more `.tests` files:

```
$ python3 run-tests.py /path/to/hb-shape myfont.tests
```

Two things it does are worth having in a font’s tests. It runs every test with `--verify --unsafe-to-concat --safe-to-insert-tatweel` (`run-tests.py:284`), so a test also checks that the font gives the same result when the text is cut where a line could break; more on that [below](#results-that-change-at-a-line-break). And it runs every test once for each kind of font functions the `hb-shape` was built with (`:147`), so that a build with FreeType checks HarfBuzz’s metrics against FreeType’s too. An `@shapers=` or `@font-funcs=` line in the file narrows that ([How a test is run](testing-harfbuzz.html#how-a-test-is-run)).

Run on release 1, every test passes. Here is what it printed for release 2, saved as `myfont.ttf` in its place, run by hand with the book’s `hb-shape` (its path shortened to `hb-shape`, the first three lines left out, and the options the runner adds shown as `…`):

```
# Supported font-funcs: ['ot']
# Running tests in myfont.tests
not ok 1 - hb-shape myfont.ttf --unicodes U+0054,U+006F --language=en …
ok 2 - hb-shape myfont.ttf --unicodes U+0066,U+0069,U+0074 --language=en …
ok 3 - hb-shape myfont.ttf --unicodes U+0066,U+0069 --language=en --features=-liga …
not ok 4 - hb-shape myfont.ttf --unicodes U+0054,U+006F,U+0020,U+0066,U+0069,U+0074 --language=en …
# 2 tests passed; 2 failed; 0 skipped.
1..4
```

and, on standard error, for each failure:

```
   ---
   test_file: "myfont.tests"
   cmd: "hb-shape myfont.ttf --unicodes U+0054,U+006F --language=en …"
   actual:   "[T=0+500|o.alt=1+500]"
   expected: "[T=0+420|o=1+500]"
   ...
```

The output is TAP, the format Meson’s test runner reads. One thing to know before calling it from a build script: it exits with 0 whether or not tests fail. Nothing after the count is checked (`run-tests.py:357`, the last line), because Meson reads the `ok` and `not ok` lines itself. A script should look for `not ok`, or for the summary line, rather than the exit status.

If the font’s sources are kept in a repository with continuous integration, it is worth running the tests there, on every change, so that a failure is seen by whoever made the change, before the font is released. The step is the same as on a desktop: build the font, then run the tests and fail if any test failed:

```
$ python3 run-tests.py "$(command -v hb-shape)" myfont.tests > results.tap
$ ! grep -q '^not ok' results.tap
```

The second command fails when the file has a `not ok` line, and so fails the build. Two things make the results trustworthy. The `hb-shape` should be a known HarfBuzz release, pinned or built from source, since a CI machine’s packaged one may be years old ([Building HarfBuzz](building-harfbuzz.html)); and a change of release should be a change of its own, so that a difference it causes isn’t mistaken for one the font caused.

## Reading a failure

The runner says what changed. Shaped by both releases, the text that failed shows it plainly:

```shape
release-1.ttf  To  --language=en
release-2.ttf  To  --language=en
```

In release 2 the *o* is `o.alt`, as intended, and the *T* has lost its kerning: its advance is 500, not 420. Drawn, with every glyph a box, the two releases look like this:

```raster
zoom: 2
release-1.ttf  To fit  --font-size=48
release-2.ttf  To fit  --font-size=48
```

A trace finds the cause. It needs an `hb-shape` built with detailed messages ([Building HarfBuzz](building-harfbuzz.html)), and [Traces](command-line-tools.html#traces) explains what it prints. For release 2:

```trace
font: release-2.ttf
text: To
options: --language=en
from: start lookup 1 feature 'calt'
to: end lookup 0 feature 'kern'
```

`calt` replaces the *o* with `o.alt`, and then `kern` runs and changes nothing, because its pair is *T o*, and there is no longer an *o*. Substitution always comes before positioning, so GPOS only ever sees what GSUB has left. The recipe [Why didn’t this ligature form?](command-line-tools.html#why-didnt-this-ligature-form) works through the same reading for a substitution.

Then comes the decision only the font maker can make: is the change a mistake, or the new intended behavior? Here it is a mistake, and the fix is in the font, `pos T [o o.alt] -80;`. Had the change been intended, the fix would be in the tests: record the failing cases again, check the new results by eye, and commit them with the font, so that the record says when and why the font’s behavior changed. A suite whose expected results are regenerated without being read checks nothing.

## Results that change at a line break

Line breaking means shaping a text in pieces. An application shapes a paragraph once, picks the breaks, and reuses the glyphs on each side when the glyph flags say it can ([For applications](for-applications.html)). If a font’s result for a piece differs from the same glyphs in the whole, a line ends or begins with the wrong glyphs, and only where it happens to break.

`--verify` checks that, for one text at a time: it shapes the pieces between every break the flags allow, and compares them with the whole ([Verifying](command-line-tools.html#verifying)). The runner turns it on for every test, so a font’s tests check it for free. When verification fails, `hb-shape` prints the reason on standard error, and `error: Shaping failed.` in place of the result, so the test fails with that as its actual output. [For applications](for-applications.html#checking-the-flags) shows texts that fail.

A failure there isn’t always the font’s fault. The flags are set by HarfBuzz, from what the lookups did, and some of the failures in that chapter are HarfBuzz setting them wrongly. But it is always a break where the font’s text comes out differently in an application, so it is worth knowing about, and worth reporting to HarfBuzz if the font is doing nothing unusual. To test a text that should only be checked whole, record it with `*` as its expected result: the runner then counts it as passed without comparing anything, and runs it without `--verify` (`run-tests.py:298`).

## What to test

The tests only see what they shape. Some places to look, in roughly the order they catch problems:

* **Every rule in context, and just out of it.** A contextual rule needs a case where its context matches and one where it nearly does: *To* and *Tx*, a mark after a base and after a space. Release 2’s mistake is found by any case with *T o* in it.
* **Every script and language system the font registers.** A `locl` lookup only runs under its language, so a Turkish *i* needs `--language=tr` to be seen at all ([Choosing a script shaper](choosing-a-script-shaper.html)). Give every case its language.
* **Marks on every base they should attach to**, including a base reached through a ligature, and two marks stacked.
* **Broken text.** A mark with no base, or a syllable a script’s rules reject, gets a dotted circle from HarfBuzz ([Dotted circles and broken clusters](dotted-circles-and-broken-clusters.html)). A case for each says what users see when they type something unusual.
* **Text at the edges.** `--text-before` and `--text-after` give a case the context a line break or a style change would, without shaping it: the start of a word after a punctuation mark, an Arabic letter that joins to text in another run.
* **Variable fonts at every threshold.** Testing at the named instances isn’t enough when a substitution switches somewhere in between.

The last needs an example. This font, from [Shape plans and their cache](shape-plans-and-their-cache.html), substitutes `H` for `I` from weight 600 to 695, and `V` from 700:

```shape
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=400  --language=en  --ned
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=600  --language=en  --ned
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=695  --language=en  --ned
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=696  --language=en  --ned
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=700  --language=en  --ned
shape-plans-and-their-cache/featvar.ttf  I  --variations=wght=900  --language=en  --ned
```

Tests at 400 and 900 never see the `H`, nor the gap at 696, where the `I` comes back: the conditions say 0.59, and a user value of 696 normalizes to just above it. A feature file says where the switches are; the cases should sit on each side of each of them ([Design space](design-space.html) explains the normalization).

## Other shapers and other versions

A font’s users don’t all have the same HarfBuzz, and some don’t have HarfBuzz at all. The same tests can be run more widely.

* **Another HarfBuzz release.** HarfBuzz changes its output from time to time, to fix a bug or follow the specification, and `NEWS` records it. Running the suite with a new release before applications ship it shows whether the font is affected. A difference here is usually HarfBuzz’s change, not the font’s, and is a question for HarfBuzz, or for the font if it relied on the old behavior.
* **The platform shapers.** On macOS and Windows, HarfBuzz can be built with Core Text, DirectWrite, and Uniscribe as shapers ([hb_shape and its backends](hb_shape-and-its-backends.html)), and `hb-shape --shapers=coretext` shapes with the system’s engine but prints in HarfBuzz’s format. The runner tests only `ot` unless the environment variable `HB_SHAPER_LIST` names more (`run-tests.py:147`), or the file has an `@shapers=` line. Expect some differences: the engines differ where the specifications leave room, and HarfBuzz’s chapters on each script say where.
* **HarfRust.** HarfBuzz built with its `harfrust` backend shapes with HarfRust through the same `hb-shape` (`--shapers=harfrust`), and so runs the same tests ([The harfrust backend in HarfBuzz](harfrust.html#the-harfrust-backend-in-harfbuzz)).

The book’s build has only the `ot` and `fallback` shapers, so none of these runs here.

## Proofs

A test says which glyphs come out and where. It doesn’t say whether they look right: a wrong but consistent result passes forever once it is recorded. So the first recording of a case is checked by eye, and a proof is the easiest way to do that. `hb-view`, `hb-raster`, and `hb-vector` draw text as HarfBuzz shapes it, with the same options as `hb-shape` ([Drawing](command-line-tools.html#drawing-hb-vector-hb-raster-and-hb-view)), so a proof of the cases file shows exactly what the tests recorded. Release 2’s *To* above is easy to miss in a list of numbers and hard to miss in a picture.

## Font QA tools

Fontspector, the Rust successor to fontbakery, runs a font maker’s shaping tests as checks in its Google Fonts profile: `shaping/regression` compares the results with expected ones, and `shaping/forbidden` fails if a forbidden glyph, such as `.notdef` or a visible virama, appears (`profile-googlefonts/src/checks/shaping/` in [fontspector](https://github.com/fonttools/fontspector)). Its tests are JSON files, in the format Simon Cozens describes in [*Better Fonts Through Test-Driven Development*](https://simoncozens.github.io/tdd-for-otl/), which fontbakery’s checks of the same names read too. It shapes with HarfRust (its `Cargo.toml`), where fontbakery shapes through uharfbuzz, HarfBuzz’s Python binding, by way of vharfbuzz. HarfRust follows HarfBuzz closely, but not exactly ([HarfRust](harfrust.html)), so a result that matters is worth checking with HarfBuzz too.

Their other checks are outside this book: outlines, metadata, spacing, naming, and the rest of what makes a font fit to ship.

## Where to read the source

| File | What’s there |
|---|---|
| `test/shape/run-tests.py` | the runner: the backends it tries, the options it adds, its TAP output |
| `test/shape/README.md`, `test/shape/record-test.sh` | how HarfBuzz records its own tests, with a subset of the font |
| `util/batch.hh` | `--batch`, which the runner drives |
| `src/hb-buffer-verify.cc` | what `--verify` checks, and the messages it prints |
| `examples/font-tests/record-tests.py` (this book) | recording a `.tests` file from a list of cases |

## In short

* When a font doesn’t work, reproduce the problem with `hb-shape` and everything the application passes, find the step with `hb-info` and `--trace`, try other engines to see whose problem it is, and cut it down with `hb-subset` to a font small enough to report.
* Most “broken” rules are registered under a script or language the text doesn’t get, or in a feature that is off by default.
* Record what HarfBuzz does with the font now, check it by eye, and compare every later build with it. HarfBuzz’s `.tests` format holds the record, and its `run-tests.py` runs it with any `hb-shape`.
* The runner adds `--verify`, so every test also checks the font at line breaks, and it runs every test with each kind of font functions the build has. It exits with 0 even when tests fail: look for `not ok`.
* If the font has continuous integration, run the tests there on every change, with a pinned HarfBuzz release.
* A failure is read by shaping both builds and tracing the new one. Then decide: fix the font, or record the new result on purpose.
* Test every contextual rule in and just out of context, every language system, marks, broken text, text at the edges, and variable fonts on each side of every threshold.
* The same tests run with another HarfBuzz release, the platform shapers, and HarfRust. Fontspector and fontbakery run shaping tests of their own format, fontspector with HarfRust.
