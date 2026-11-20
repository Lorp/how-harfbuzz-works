# The command-line tools

HarfBuzz comes with a handful of small programs, in its `util/` folder. `hb-shape` shapes a piece of text with a font and prints the glyphs and positions that come back. `hb-info` says what is in a font. `hb-subset` cuts a font down. `hb-vector`, `hb-raster`, and `hb-view` draw shaped text. They are thin: each parses its options, makes the same HarfBuzz objects an application would, calls the library, and prints what it gets. That makes them the quickest way to ask HarfBuzz a question about a font, and the answer comes from the library itself.

Every shaping result in this book is `hb-shape` output. This chapter explains its options, then the other tools, then puts them to work on a few questions about fonts. The tools come with a package manager’s HarfBuzz: Homebrew’s `harfbuzz`, for example, or Debian’s `libharfbuzz-bin`. Check the version first, with `hb-shape --version`: this book describes HarfBuzz 15, and a packaged HarfBuzz can be much older. [Building HarfBuzz](building-harfbuzz.html) shows how to build HarfBuzz {{hb}} yourself, including the build with detailed traces. [Reading this book](notation.html) explains how the book shows their output.

As everywhere in the book, the results and pictures below were made by running the tools of HarfBuzz {{hb}} when the page was built. Commands shown in plain code blocks are hand-written.

> For type designers: this chapter is for getting familiar with the tools, one switch at a time. For using them on a font of your own, to find out why a rule doesn’t work or to check that the font keeps working from one build to the next, see [Testing and debugging fonts with HarfBuzz](testing-and-debugging-fonts-with-harfbuzz.html), which puts these tools to work and links back here for each switch.

## The tools

| Tool | What it does | Library | Built |
|---|---|---|---|
| `hb-shape` | shapes text, prints glyphs and positions as text or JSON | `libharfbuzz` | always, installed |
| `hb-info` | lists a font’s names, tables, characters, glyphs, scripts, features, axes, palettes | `libharfbuzz` | always, installed |
| `hb-subset` | writes a smaller font: fewer characters, glyphs, tables, or axes | `libharfbuzz-subset` | option `subset`, installed |
| `hb-vector` | draws shaped text as SVG or PDF | `libharfbuzz-vector` | option `vector`, installed |
| `hb-raster` | draws shaped text as PNG, PPM, or terminal art | `libharfbuzz-raster` | option `raster`, installed |
| `hb-view` | draws shaped text through cairo ([hb-cairo](integrations.html#how-hb-view-uses-it)) | `libharfbuzz-cairo` | with cairo, installed |
| `hb-gpu` | an interactive window that draws text on the GPU | `libharfbuzz-gpu` | with GLEW and GLFW, installed |
| `hb-subset-depend` | prints a font’s glyph dependency graph | `libharfbuzz-subset` | option `experimental_api`, not installed |
| `hb-ft-raster` and the `*-all` programs | test and benchmark tools | various | not installed |

Except for `hb-gpu-encode-all`, they are built only where GLib is found (`util/meson.build:44`); its option parser is what gives them their common command line. The book’s build has neither cairo nor GLEW, so `hb-view` and `hb-gpu` are described here from their source, and nothing on this page comes from them.

Each tool answers `--help` with its common options, `--help-all` with all of them, and `--help-` followed by a group name (`--help-features`, say) with one group. `--version` prints the version, and says so if the library it is linked with is a different one (`util/options.hh:264`). With the environment variable `HB_UTIL_HELP_VERBOSE=1`, the help also lists the exit codes and environment variables (`options.hh:199`). The manual pages are made from that help, when the build finds `help2man` (`util/meson.build:36`).

## Options the tools share

The tools are put together from the same parts. Each group of options is a C++ struct in a header in `util/`, and a tool inherits the groups it needs. `hb-shape`, for example, is one line of `main` over a template: `main_font_text_t<shape_consumer_t<shape_output_t>, font_options_t, shape_text_options_t>` (`hb-shape.cc:41`). So an option means the same thing in every tool that has it, and an example worked out with `hb-shape` can be drawn with `hb-vector` by changing the program’s name.

| Group (`--help-…`) | Header | Options | Tools |
|---|---|---|---|
| `face` | `face-options.hh` | `--font-file`, `-y`/`--face-index`, `--face-loader` | all |
| `font`, `variations` | `font-options.hh` | `--font-size`, `--font-ppem`, `--font-ptem`, `--font-bold`, `--font-grade`, `--font-slant`, `--font-funcs`, `--ft-load-flags`, `--variations`, `--named-instance` | all but `hb-subset` and `hb-subset-depend` |
| `text`, `text-context` | `text-options.hh` | `--text`, `--text-file`, `-u`/`--unicodes`, `--single-par`, `--text-before`, `--text-after`, `--unicodes-before`, `--unicodes-after` | the shaping and drawing tools |
| `shape`, `features` | `shape-options.hh` | `--direction`, `--script`, `--language`, `--features`, `--shapers`, `--cluster-level`, `--verify`, and the buffer flags | the shaping and drawing tools |
| `output` | `output-options.hh` | `-o`/`--output-file`, `-O`/`--output-format` | `hb-shape`, `hb-subset`, `hb-vector`, `hb-raster`, `hb-view`, `hb-ft-raster` |
| `output-syntax` | `shape-format.hh` | `--no-glyph-names`, `--show-flags`, `--trace`, and the rest | `hb-shape` |
| `view` | `view-options.hh` | `--foreground`, `--background`, `--margin`, `--font-palette`, `--show-extents`, and others | `hb-view`, `hb-vector`, `hb-raster` |

“The shaping and drawing tools” are `hb-shape`, `hb-view`, `hb-vector`, `hb-raster`, `hb-ft-raster`, and `hb-gpu`. Every one of them shapes before it draws, with the same code (`shape-consumer.hh:65`), so the drawing tools take `--features`, `--language`, and the rest, and draw exactly the glyphs `hb-shape` would print.

A few habits are common to all of them:

* **The font and the text.** The first argument that isn’t an option is the font file and the second is the text (`main-font-text.hh:91`). `--font-file` and `--text` say the same thing as options. A font file named `-` is read from standard input (`face-options.hh:99`).
* **Text from a file, line by line.** With no text, the tools read standard input; `--text-file` reads a file (`text-options.hh:53`). Either way, and for `--text` too, each line is shaped on its own, unless `--single-par` makes the whole input one paragraph (`text-options.hh:314`).
* **Size.** The default `--font-size` is the font’s units per em for `hb-shape`, `hb-info`, and `hb-vector`, so their numbers are in font units, and 256 for `hb-raster` and `hb-view`, whose output is pixels (`hb-shape.cc:35`, `hb-raster.cc:34`).
* **Output.** `-o` names a file. Without `-O`, the format comes from the file’s extension (`output-options.hh:77`), so `hb-vector -o text.pdf` writes PDF.
* **Exit codes.** 0 for success, 1 if the options couldn’t be parsed, 2 if the font couldn’t be loaded, 3 if the operation failed, 4 if the font functions couldn’t be set (`options.hh:59`).
* **Environment.** `HB_SHAPER_LIST`, `HB_FONT_FUNCS`, and `HB_FACE_LOADER` change the library’s defaults, for these tools and for any other program ([hb_shape and its backends](hb_shape-and-its-backends.html), [Fonts and font functions](fonts-and-font-functions.html#choosing-funcs)).

## hb-shape

### Reading the output

`hb-shape` prints one line per line of input: the glyphs, in the order they are drawn, between square brackets. [Reading this book](notation.html#shaping-results) gives the format: `name=cluster@x,y+advance`. The cluster is the index of the character a glyph came from; characters and glyphs that belong together share one, as [Buffers](buffers.html#merging-clusters) explains. Switches take parts away or add them:

```shape
why-shaping-exists/shaping.ttf  fi\u00E1
why-shaping-exists/shaping.ttf  fi\u00E1  --no-glyph-names
why-shaping-exists/shaping.ttf  fi\u00E1  --no-clusters
why-shaping-exists/shaping.ttf  fi\u00E1  --no-positions
why-shaping-exists/shaping.ttf  fi\u00E1  --no-advances
why-shaping-exists/shaping.ttf  fi\u00E1  --ned
why-shaping-exists/shaping.ttf  fi\u00E1  --show-extents
```

`--no-glyph-names` gives glyph IDs; a font without names prints them as `gid59` anyway. `--no-advances` does more than leave out the advances: each `@x,y` becomes the glyph’s absolute position, the sum of the advances before it and its own offset (`hb-buffer-serialize.cc:290`). That is why the `aacute` is at `@900,0`. `--ned`, “no extra data”, is `--no-clusters` and `--no-advances` together (`shape-format.hh:95`). `--show-extents` adds each glyph’s ink box, `<x_bearing,y_bearing,width,height>`, from the font funcs; the height is negative because the box runs down from its top ([Where metrics come from](where-metrics-come-from.html)).

`--show-flags` adds the glyph flags, `#` and a hexadecimal number, to the glyphs that have any: 1 is unsafe to break, 2 unsafe to concatenate (only with `--unsafe-to-concat`), 4 safe to insert a tatweel (only with `--safe-to-insert-tatweel`). What they promise is in [Buffers](buffers.html#glyph-flags) and [For applications](for-applications.html#what-the-glyph-flags-promise):

```shape
why-shaping-exists/shaping.ttf  \u0628\u0628\u0628  --show-flags
why-shaping-exists/shaping.ttf  \u0628\u0628\u0628  --show-flags  --unsafe-to-concat
```

`--output-format=json` (or `-O json`) writes the same data as JSON, with short keys: `g`, `cl`, `dx`, `dy`, `ax`, `ay`, and `xb`, `yb`, `w`, `h` for extents and `fl` for flags:

```shape
why-shaping-exists/shaping.ttf  fi\u00E1  --output-format=json  --show-extents
```

Three switches put the input before each result: `--show-text` the text in parentheses, `--show-unicode` its code points, and `--show-line-num` the number of the input line. `--verbose` turns on all three. Its short form, `-v`, also turns on `--ned`, because in {{hb}} `--ned` was given the same letter (`shape-format.hh:187`, `:199`); the help lists `-v` only for `--verbose`:

```shape
why-shaping-exists/shaping.ttf  fi  --verbose
why-shaping-exists/shaping.ttf  fi  -v
```

### Text and code points

The text can be given as characters or as code points. `-u` (`--unicodes`) takes a list of hexadecimal numbers, and is generous about what separates them: commas, spaces, `U+`, `0x`, `\u`, `&#x`, and `;`, among others (`text-options.hh:150`). So `-u 628,644`, `-u "U+0628 U+0644"`, and `-u "&#x628;&#x644;"` give the same text. For text that is hard to type, or invisible, code points are safer than characters.

`--text-before` and `--text-after` give the text around the run, as an application gives the text around a run it has cut out of a paragraph. `--unicodes-before` and `--unicodes-after` do the same with code points. They are added to the buffer as **context**: characters HarfBuzz can look at but doesn’t shape (`shape-options.hh:117`). Context matters wherever shaping looks at Unicode properties of the neighbors, as Arabic joining does:

```shape
why-shaping-exists/shaping.ttf  \u0628
why-shaping-exists/shaping.ttf  \u0628  --unicodes-before=628
why-shaping-exists/shaping.ttf  \u0628  --unicodes-after=628
why-shaping-exists/shaping.ttf  \u0628  --unicodes-before=628  --unicodes-after=628
```

A lone beh is isolated; with a beh before it, it is final, and so on. The context is never in the buffer as glyphs, so GSUB rules can’t match it: the GSUB test font turns `e` into `e.init` after a space, but a space given as context doesn’t do it:

```shape
gsub/ligatures.ttf  \u0020e
gsub/ligatures.ttf  e  --unicodes-before=20
```

[For applications](for-applications.html#context-at-the-edges-of-a-run) says what this means for an application. One oddity: in {{hb}}, `--text-before` also prints its argument to standard error (`text-options.hh:225`), a debugging line left in.

### Direction, script, and language

A run has a direction, a script, and a language ([Why shaping exists](why-shaping-exists.html#runs-and-the-three-things-harfbuzz-must-be-told)). `hb-shape` guesses whatever isn’t given, with `hb_buffer_guess_segment_properties` (`shape-options.hh:64`): the script and direction from the text, the language from the locale, through the `LANG` and `LC_*` environment variables. The language changes results in fonts with language-specific rules, so a result that depends on it should say `--language` explicitly, or it will differ from one machine to the next:

```shape
why-shaping-exists/shaping.ttf  fi  --language=en
why-shaping-exists/shaping.ttf  fi  --language=tr
```

`--direction` takes `ltr`, `rtl`, `ttb`, or `btt`; `--script` an ISO 15924 code such as `Latn` or `Arab` ([Choosing a script shaper](choosing-a-script-shaper.html)); `--language` a BCP 47 tag such as `tr` or `ur-PK`.

### Features

`--features` takes a list of features separated by commas, each in the syntax of `hb_feature_from_string`, which the help prints in full:

| Setting | Means |
|---|---|
| `kern`, `+kern`, `kern=1` | on |
| `-kern`, `kern=0` | off |
| `aalt=2` | on, with value 2: the second alternate |
| `kern[3:5]` | on for characters 3 and 4 only |
| `kern[3]` | on for character 3 |
| `kern[5:]`, `kern[:5]` | on from character 5, or up to it |
| `aalt[3:5]=2` | value 2, for characters 3 and 4 |

The numbers in brackets count characters from 0 (bytes with `--utf8-clusters`), and the end is excluded, as in Python. A feature HarfBuzz turns on by default, such as `liga`, is already on everywhere, so turning it on for a range changes nothing. To keep a ligature in one place only, turn the feature off, then on again for the range:

```shape
why-shaping-exists/shaping.ttf  ffi  --language=en
why-shaping-exists/shaping.ttf  ffi  --language=en  --features=-liga
why-shaping-exists/shaping.ttf  ffi  --language=en  --features=-liga,liga[1:3]
gsub/ligatures.ttf  aa  --features=salt[1]=3
```

Which features are on by default, and how a list of features becomes a list of lookups, is [From features to lookups](from-features-to-lookups.html).

The help says that any value of CSS `font-feature-settings` is accepted too, and `hb_feature_from_string` does accept `"liga" 0`. But `hb-shape` splits its argument at spaces as well as commas before it parses anything (`shape-options.hh:352`), so on the command line the CSS form breaks in two, and its `0` is lost: use `liga=0`.

### Variations

`--variations` sets a variable font’s axes, as a list such as `wght=700,wdth=80`; an axis not mentioned stays at its default, and a value beyond an axis’s range is clamped to it. `--named-instance` picks one of the font’s named instances by its index, and `--variations` then applies on top of it (`font-options.hh:104`). [Design space](design-space.html) explains axes and instances; `hb-info --list-variations` lists them:

```shape
variations/var.ttf  IHV
variations/var.ttf  IHV  --variations=wght=900
variations/var.ttf  IHV  --variations=wght=900,wdth=50
variations/var.ttf  IHV  --named-instance=3
```

The same split at spaces applies: `wght 900`, in the CSS form the help mentions, sets nothing (`font-options.hh:192`).

### Size, and the font funcs

`--font-size` sets the font’s scale, the number that one em comes out as. With `--font-size=16`, positions are in pixels at 16 pixels per em; since positions are whole numbers, every advance is rounded to a whole pixel:

```shape
hb:test/subset/data/fonts/Roboto-Regular.ttf  Wave
hb:test/subset/data/fonts/Roboto-Regular.ttf  Wave  --font-size=16
hb:test/subset/data/fonts/Roboto-Regular.ttf  Wave  --font-size=1024
```

An application that wants fractions of a pixel scales the font by more, often 64 times, and `hb-raster`, `hb-vector`, and `hb-view` do that themselves: they multiply the size by 64 (`SUBPIXEL_BITS`, `hb-raster.cc:35`, `font-options.hh:99`). [Fonts and font functions](fonts-and-font-functions.html#three-kinds-of-size) explains scale, `--font-ppem` (pixels per em, which only Device tables, hinting, and bitmap strikes read), and `--font-ptem` (the point size, which AAT’s `trak` reads). `--font-bold`, `--font-grade`, and `--font-slant` make a font bold, heavier without wider advances, or slanted, synthetically ([Fonts and font functions](fonts-and-font-functions.html#synthetic-bold-and-slant)):

```shape
why-shaping-exists/shaping.ttf  fi  --font-bold=0.05
```

`--font-funcs` chooses where the metrics come from: `ot`, HarfBuzz’s own, by default, or `ft` for FreeType in a build that has it, and `--list-font-funcs` lists them. `--ft-load-flags` passes FreeType its load flags; the default, 2, is `FT_LOAD_NO_HINTING` (`font-options.hh:73`). FreeType reads the scale as a size in 64ths of a pixel, so to see hinted advances in `hb-shape`, multiply the size by 64; [hb-raster](hb-raster.html#hinting-with-freetype) shows the difference.

### Buffer and cluster options

Most of the remaining options set a property of the buffer, and are explained where the buffer is ([Buffers](buffers.html#buffer-flags)):

* `--cluster-level=0` to `3` chooses how much clusters merge. Level 0, the default, keeps a base and its marks together; level 1 doesn’t:

```shape
why-shaping-exists/shaping.ttf  e\u0301
why-shaping-exists/shaping.ttf  e\u0301  --cluster-level=1
```

* `--utf8-clusters` numbers clusters by byte in the UTF-8 text, as the library does, rather than by character, as `hb-shape` does unless told (`shape-options.hh:126`).
* `--bot` and `--eot` say that the text starts or ends a paragraph.
* `--preserve-default-ignorables` and `--remove-default-ignorables` decide what becomes of invisible characters such as ZWJ, which by default are hidden behind a zero-width space glyph; `--invisible-glyph=N` uses glyph `N` for them instead.
* `--not-found-glyph=N` uses glyph `N`, instead of `.notdef`, for a character the font doesn’t have.
* `--unsafe-to-concat` and `--safe-to-insert-tatweel` ask for the flags of those names.
* `--normalize-glyphs` sorts the glyphs within each cluster into a fixed order, so that two results can be compared.
* `--glyphs` takes, instead of text, glyphs in `hb-shape`’s own output format, and prints them without shaping, scaled to `--font-size` (`shape-options.hh:73`).
* `--shapers` lists the shaping backends to try, in order, and `--list-shapers` prints them ([hb_shape and its backends](hb_shape-and-its-backends.html)).

### Traces

`--trace` (`-V`) prints, on standard error, a line for every step of shaping: its name, a tab, and the buffer after it, in the same format as the result (`shape-output.hh:142`). So `--no-glyph-names` and the other switches apply to traces too. Here is the GSUB part of the trace for the `fi` above:

```trace
font: why-shaping-exists/shaping.ttf
text: fi
options: --language=en
from: start table GSUB
to: end table GSUB
```

`liga` has two lookups in this font, `ff` then `fi`, and the trace shows the second one making the ligature. The book’s traces come from a build with `HB_BUFFER_MESSAGE_MORE`, which adds the lines inside lookups, such as “ligating glyphs at 0,1”; an ordinary build prints only the starts and ends. [The pipeline, step by step](pipeline-step-by-step.html) reads a whole trace, and [Testing HarfBuzz](testing-harfbuzz.html#buffer-messages) explains the messages.

### Verifying

`--verify` makes HarfBuzz check its own result: it cuts the text wherever the glyph flags say a line could break, shapes the pieces, and compares (`shape-options.hh:54`, [Buffers](buffers.html#verification)). If the result passes, the output is unchanged. If it fails, HarfBuzz prints the reason and the text to standard error, `hb-shape` prints `error: Shaping failed.`, and exits with 3. [For applications](for-applications.html#checking-the-flags) shows fonts that fail, and [Testing and debugging fonts with HarfBuzz](testing-and-debugging-fonts-with-harfbuzz.html) why a font’s tests should run with it.

### Many runs

`--batch`, as the only argument, makes a tool read standard input for whole command lines, one per line, with the arguments separated by semicolons (`batch.hh:36`):

```
$ printf 'shaping.ttf;fi\nshaping.ttf;fi;--features=-liga\n' | hb-shape --batch
```

Each line runs as if it were a command of its own, and prints what it would. The font of the last line is kept loaded while the next line names the same file (`face-options.hh:109`), and one process serves every line. HarfBuzz’s own test runners drive `hb-shape` and `hb-subset` this way (`test/shape/run-tests.py:25`), and so can a font’s ([Testing and debugging fonts with HarfBuzz](testing-and-debugging-fonts-with-harfbuzz.html)). The drawing tools and `hb-subset` also print `success` or `failure` after each line. A line with a bad option or font still ends the whole batch (`options.hh:114`).

`-n` (`--num-iterations`) repeats the shaping, for timing, and an empty `--output-format=` skips writing the result at all (`shape-output.hh:56`), so that the time measured is HarfBuzz’s.

## hb-info

`hb-info` reads a font and says what is in it. With no query it prints a summary, here of Roboto, from HarfBuzz’s tests:

```info
hb:test/subset/data/fonts/Roboto-Regular.ttf
```

Its queries come in three kinds. `--show-…` prints one line of the summary (`--show-upem`, `--show-glyph-count`, and so on). `--get-…` fetches one thing by its tag or number: `--get-name=13`, `--get-metric=hasc`, `--get-style=wght`, `--get-baseline=romn`. `--get-table=GSUB` writes the table’s raw bytes to standard output (`hb-info.cc:617`), ready to pipe to another program. `--list-…` lists: names, tables (`-l`), characters (`--list-unicodes`), glyphs, scripts, features, variations, palettes, metrics, style values, baselines, and `meta` entries. `-a` (`--all`) prints everything. `-q` drops the headings, for scripts.

Because `hb-info` has the font options, its answers are for the font as configured: `--get-style=wght`, for example, answers for the instance `--variations` asks for:

```info
variations/var.ttf  -q --get-style=wght --variations=wght=650
```

`--list-features` alone lists every feature of GSUB and GPOS once. With `--script`, and optionally `--language`, it lists only those of that script and language, as HarfBuzz would choose them when shaping (`hb-info.cc:1047`); `--ot-script` and `--ot-language` give OpenType tags directly. [Other tables](other-tables.html) uses `hb-info`’s queries of `name`, `STAT`, `BASE`, and `meta`.

## hb-subset

`hb-subset` writes a font cut down to what some text, or some glyphs, needs. It must be told where to write: it refuses standard output unless asked for it with `-o -` (`output-options.hh:91`). A typical command keeps the characters of a string:

```
$ hb-subset Roboto-Regular.ttf --text="Hello" -o hello.ttf
```

The text can also come as the second argument, as for `hb-shape` (`hb-subset.cc:868`). What to keep is given by `--text`, `--unicodes` (hex, with ranges and `*` for all), `--gids`, and `--glyphs`, each with a `-file` form. Every set has a `+=` and a `-=` form that adds or takes away, so `--unicodes=* --unicodes-=41` keeps every character but `A`, and `--layout-features+=dlig` keeps one more feature than the default list. `--drop-tables`, `--name-IDs`, and `--layout-scripts` work the same way.

Among the flags, `--retain-gids` keeps glyph IDs unchanged, `--no-hinting` drops hinting, `--desubroutinize` flattens CFF, `--glyph-names` keeps the `post` table’s names (without it, a TrueType subset’s glyphs print as `gid0`, `gid1`), and `--no-layout-closure` drops the glyphs that only substitutions reach. `--variations` instances a variable font: `wght=700` pins an axis, `wght=300:700` limits it, `wght=drop` pins it at its default (`helper-subset.hh:37`). [Subsetting](subsetting.html) and [Instancing](instancing.html) explain what happens inside.

## Drawing: hb-vector, hb-raster, and hb-view

The three drawing tools shape the text, lay out its lines, and draw the glyphs. They share the view options (`view-options.hh:363`): `--foreground` and `--background` colors (`none` for a transparent background), `--margin`, `--line-space`, `--font-extents` to override ascent and descent, `--logical` and `--ink` to frame the picture by the line’s logical box or by the ink alone, `--font-palette` and `--custom-palette` for color fonts, `--rainbow` to color each glyph differently, and `--show-extents` to draw each glyph’s ink box and origin. `hb-vector` and `hb-raster` find out whether a font has color glyphs (COLR, or PNG bitmaps) and paint them in color; `--draw` forces plain outlines and `--paint` the color path (`raster-output.hh:79`, `vector-output.hh:225`).

`hb-vector` writes SVG, or PDF with `-O pdf` (`vector-output.hh:40`); `--precision` sets the number of decimals in its coordinates. Its default size is the font’s units per em, so an SVG is in font units. The commands in this section are run from the top of a HarfBuzz checkout, where these test fonts are. This one draws a word as SVG:

```command
$ hb-vector test/subset/data/fonts/Roboto-Variable.ttf Wave -o wave.svg
```

`--variations` chooses a weight in a variable font, as it does for `hb-shape`:

```command
$ hb-vector test/subset/data/fonts/Roboto-Variable.ttf Wave --variations=wght=900 -o wave-900.svg
```

and `-O pdf` writes PDF instead:

```command
$ hb-vector test/subset/data/fonts/Roboto-Variable.ttf Wave -O pdf -o wave.pdf
```

`hb-raster` writes PNG, PPM, or `ansi`, a picture in the characters and colors of a terminal (`raster-output.hh:41`). Its default size is 256 pixels per em. This command writes a PNG at 32 pixels to the em:

```command
zoom: 3
$ hb-raster test/subset/data/fonts/Roboto-Regular.ttf Wave --font-size=32 -o wave.png
```

Without `-o`, the picture goes to the terminal, as described below; `-O ansi` asks for it in characters, whatever the terminal:

```command
show: no
$ hb-raster test/subset/data/fonts/Roboto-Regular.ttf Wave --font-size=32 -O ansi
```

`--show-extents` should add each glyph’s ink box and origin to the picture, but in {{hb}} it puts most of them in the wrong place ([below](#a-bug-in-show-extents)).

`hb-view` came first: `hb-vector` and `hb-raster` arrived in 13.0.0 with their libraries, and “share many of the same options as `hb-view`” (`NEWS`). It draws through cairo, using `libharfbuzz-cairo`, and so writes whatever cairo can: PNG, SVG, PDF, PostScript, EPS, cairo script, and `ansi`, depending on how cairo was built (`helper-cairo.hh:374`). Its default size is 256. `hb-vector` and `hb-raster` do the same work with HarfBuzz’s own renderers and no cairo, and are described with their libraries, in [hb-vector](hb-vector.html) and [hb-raster](hb-raster.html). `hb-view` takes the format from the output file’s name:

```
$ hb-view test/subset/data/fonts/Roboto-Regular.ttf Wave -o wave.png
```

or from `-O`:

```
$ hb-view test/subset/data/fonts/Roboto-Regular.ttf Wave -O svg -o wave.svg
```

It is built only if both GLib and cairo are found (`util/meson.build:44`–`:45`, [Building HarfBuzz](building-harfbuzz.html#optional-dependencies-and-backends)); this book’s build leaves cairo out, so its pictures come from `hb-vector` and `hb-raster`.

Written to a terminal without `-O`, `hb-raster` and `hb-view` show the picture there. In iTerm2, WezTerm, and kitty, which can show images, they send a PNG in the terminal’s own protocol; elsewhere they print it as `ansi` (`helper-image-output.hh:76`), with the chafa library’s help if they were built with it.

### A bug in `--show-extents`

In {{hb}}, `hb-raster` and `hb-vector` draw the box of every glyph but the first in the wrong place. Here is the picture above with `--show-extents`:

```command
zoom: 3
$ hb-raster test/subset/data/fonts/Roboto-Regular.ttf Wave --font-size=32 --show-extents -o wave-extents.png
```

Only the *W*’s box is where it should be. The box around the *v* and the *e* is the *a*’s, at twice the *a*’s pen position, and the boxes of the *v* and the *e* are further on still, outside the picture. Each glyph’s overlay is drawn with its transform already set to the pen position, and then moved by the pen position again (`raster-output.hh:251`, `vector-output.hh:292`, `helper-extents-overlay.hh:66`). The first glyph’s pen position is 0, so its box alone is right. `hb-shape --show-extents` gives the correct numbers. This is draft 75 in [Bugs this book found](bugs-this-book-found.html#hhw-75).

## hb-gpu

`hb-gpu` opens a window and draws shaped text with the shaders of [hb-gpu](hb-gpu.html), through OpenGL, or Metal or Direct3D where those are offered (`gpu-output.hh:87`). It is a demonstration more than a tool: the text can be zoomed, rotated, and moved (`util/gpu/demo-view.cc`), and keys toggle a dark background, stem darkening, and a debug heat map. It takes the font and text options of `hb-shape`; with no text, it builds some from the scripts the font supports (`hb-gpu.cc:166`), and `--demo` uses a font and text built into it. `-o` renders one frame to a PPM file instead of opening a window.

## The tools that aren’t installed

The build makes a few more programs, for HarfBuzz’s own developers, and doesn’t install them (`util/meson.build:105`–`254`):

* `hb-subset-depend` prints the glyph dependency graph of [hb-depend](hb-depend.html): for each glyph, the glyphs it can produce or depend on through GSUB, composites, COLR, and MATH (`hb-subset-depend.cc:49`). `--gids` limits it to some glyphs, `--flagged` to the edges marked as approximate. It needs the experimental API (`util/meson.build:192`).
* `hb-ft-raster` draws like `hb-raster`, but with FreeType’s rasterizer, to compare the two pixel by pixel ([hb-raster](hb-raster.html#checking-against-freetype)). It writes PPM only, and has no view options.
* `hb-draw-all`, `hb-paint-all`, `hb-vector-svg-all`, `hb-raster-all`, and `hb-ft-raster-all` draw or paint every glyph of a font, as benchmarks; the two raster ones can also write each glyph as a PPM file. `hb-gpu-encode-all` encodes every glyph for hb-gpu and reports sizes and times.
* `hb-fc-list`, in `util/hb-fc-list.c`, lists the fontconfig fonts that can draw a piece of text. Nothing in the build compiles it.

## Recipes

Each of these answers one question about one font, once. To check that a font keeps giving the right answers, build after build, see [Testing and debugging fonts with HarfBuzz](testing-and-debugging-fonts-with-harfbuzz.html).

### What does this text look like in this font?

`hb-vector` and `hb-raster` draw it, one command each. The font here is Libre Baskerville, from Google Fonts under the SIL Open Font License, whose standard ligatures turn the *ffi* of “office” and the *ff* of “coffee” into one glyph each. First, download it:

```
$ curl -L -o LibreBaskerville.ttf "https://github.com/google/fonts/raw/main/ofl/librebaskerville/LibreBaskerville%5Bwght%5D.ttf"
```

`hb-shape` shows what the font does with the text. The thirteen characters become ten glyphs:

```command
font: quick-start/LibreBaskerville.ttf
$ hb-shape LibreBaskerville.ttf "office coffee"
```

`hb-vector` draws the result as SVG, in font units unless `--font-size` is given:

```command
font: quick-start/LibreBaskerville.ttf
$ hb-vector LibreBaskerville.ttf "office coffee" -o office.svg
```

and `hb-raster` as PNG, here at 32 pixels to the em:

```command
font: quick-start/LibreBaskerville.ttf
$ hb-raster LibreBaskerville.ttf "office coffee" --font-size=32 -o office.png
```

Features work as in `hb-shape`. The font’s discretionary ligatures are off unless asked for, with `--features=dlig`:

```command
font: quick-start/LibreBaskerville.ttf
$ hb-shape LibreBaskerville.ttf "act first" --features=dlig
```

The drawing tools take the same option:

```command
font: quick-start/LibreBaskerville.ttf
$ hb-vector LibreBaskerville.ttf "act first" --features=dlig -o act.svg
```

Both tools arrived in HarfBuzz 13.0.0, and this book describes 15: if your package manager’s HarfBuzz is older, build 15.1.0 ([Building HarfBuzz](building-harfbuzz.html)). `hb-raster` writes PNG only if HarfBuzz was built with libpng. The [next chapter](quick-start.html) shows how to write programs that do the same, in C, JavaScript, Python, and Rust.

### Does this font have these characters?

`hb-info --list-unicodes` lists the characters the font’s `cmap` maps, with the glyph each goes to:

```info
why-shaping-exists/shaping.ttf  --list-unicodes
```

That answers the question for the `cmap`, but not always for shaping. `é` (U+00E9) isn’t in the list, yet the font can draw it: HarfBuzz decomposes it into `e` and a combining acute, which are ([Normalization](normalization.html)). Shaping tells the whole story. A character the font can’t draw comes out as glyph 0, `.notdef`, and `--no-glyph-names` makes that easy to spot:

```shape
why-shaping-exists/shaping.ttf  \u00E9
why-shaping-exists/shaping.ttf  \u00E9b  --no-glyph-names
```

### Which features apply in this language?

`--list-scripts` shows which scripts and languages the font’s GSUB and GPOS know, and `--list-features` with `--script` and `--language` shows which features HarfBuzz will look at for that combination:

```info
why-shaping-exists/shaping.ttf  --list-scripts
why-shaping-exists/shaping.ttf  --list-features --script=Latn --language=tr
```

This font has a Turkish language system, `TRK`. `liga` is on its list, but it is a different `liga` from the default one, as the shaping of `fi` with `--language=tr` above showed: in Turkish it leaves out the `fi` ligature, which would hide the dot that tells `i` from `ı`.

### Why didn’t this ligature form?

The test font has a lam-alef ligature, made by `rlig` from `lam.init` and `alef.fina`. It forms on its own, but not after a beh:

```shape
why-shaping-exists/shaping.ttf  \u0644\u0627
why-shaping-exists/shaping.ttf  \u0628\u0644\u0627
```

A trace of the second, from the first joining lookup to `rlig`, shows why:

```trace
font: why-shaping-exists/shaping.ttf
text: \u0628\u0644\u0627
from: start lookup 4
to: end lookup 5
skipped: yes
```

After a beh, the lam is medial. `medi` runs and changes nothing, because the font has no medial lam, so when `rlig`’s turn comes the lam is still `lam`, not `lam.init`. HarfBuzz skips the lookup without trying it, since no glyph in the buffer is one it could start from (`hb-ot-layout.cc:2116`). A trace shows the buffer each lookup saw, which is usually enough; here it points at the font. The same steps work for any ligature: shape with and without the feature, check the features for the script and language with `hb-info`, then trace.

### What glyphs does a subset keep?

Subset the font, then list the glyphs. This page’s fonts were cut from the test font by `fonts/command-line-tools/build.sh`, with `--text=fi --glyph-names`, the second also with `--layout-features-=liga`:

```info
command-line-tools/fi.ttf  --list-glyphs
command-line-tools/fi-noliga.ttf  --list-glyphs
```

The first keeps `f_f` as well as `f_i`, though the text has only one `f`. The subsetter keeps every glyph that the features it keeps could make from the glyphs it already has, and it doesn’t ask whether the text could ever produce them ([Subsetting](subsetting.html#the-glyph-closure-stage-by-stage)). Without `liga`, neither ligature is kept, and the subset can no longer make `fi`:

```shape
command-line-tools/fi.ttf  fi
command-line-tools/fi-noliga.ttf  fi
```


## Where to read the source

| File | What’s there |
|---|---|
| `util/meson.build` | which tools are built, and when; which are installed |
| `util/options.hh` | the option parser, exit codes, `--version`, the verbose help |
| `util/batch.hh` | `--batch` |
| `util/main-font-text.hh` | the `main` shared by the shaping and drawing tools; the font and text arguments |
| `util/face-options.hh`, `util/font-options.hh` | the face, font, and variations options |
| `util/text-options.hh` | `--text`, `--unicodes`, reading lines, the context options |
| `util/shape-options.hh` | the shape options, `--features`, filling the buffer |
| `util/shape-consumer.hh` | shaping each line, for every tool that shapes |
| `util/shape-format.hh`, `util/shape-output.hh` | `hb-shape`’s output switches and `--trace` |
| `src/hb-buffer-serialize.cc` | the text and JSON formats themselves |
| `util/view-options.hh` | the drawing tools’ view options |
| `util/hb-info.cc`, `util/hb-subset.cc`, `util/helper-subset.hh` | `hb-info` and `hb-subset` |
| `util/vector-output.hh`, `util/raster-output.hh`, `util/view-cairo.hh` | `hb-vector`, `hb-raster`, `hb-view` |
| `util/gpu-output.hh`, `util/hb-gpu.cc`, `util/gpu/` | `hb-gpu` |

## In short

* The tools are thin layers over the library. Their options come from shared groups in `util/*.hh`, so an option works the same in every tool that has it, and the drawing tools shape exactly as `hb-shape` does.
* `hb-shape` prints `name=cluster@x,y+advance`. Switches remove parts (`--no-glyph-names`, `--no-clusters`, `--no-advances`, `--ned`) or add them (`--show-extents`, `--show-flags`), and `-O json` writes JSON.
* `--features` takes `tag`, `-tag`, `tag=N`, and ranges in brackets; `--variations` takes `tag=value`. Both split at spaces as well as commas.
* Pass `--language` whenever a result could depend on it. `--text-before` and `--text-after` give context for Unicode properties such as joining, but not for GSUB rules.
* `--trace` shows each step; `--verify` checks the glyph flags by reshaping; `--batch` runs many command lines in one process.
* `hb-info` answers questions about a font as configured, variations included. `hb-subset` writes subsets and instances, and needs `-o`.
* `hb-vector`, `hb-raster`, and `hb-view` draw shaped text as SVG or PDF, as pixels, and through cairo; `hb-gpu` draws it in a window on the GPU.
