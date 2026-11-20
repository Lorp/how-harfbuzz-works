# Integrations: FreeType, cairo, ICU, and the platforms

HarfBuzz’s core needs nothing but a C++ compiler. It reads fonts itself, carries its own Unicode tables, and returns glyph IDs and positions as plain numbers. But the programs that call it already have a font library, a graphics library, a Unicode library, or an operating system’s text stack, and they want HarfBuzz to work with the objects those already hold: an `FT_Face`, a `cairo_t`, a `CTFont`, a `UScriptCode`. The **integration layers** are the small files that make the connection, each with its own header: `hb-ft.h`, `hb-cairo.h`, `hb-icu.h`, `hb-glib.h`, `hb-coretext.h`, `hb-directwrite.h`, `hb-uniscribe.h`, `hb-gdi.h`, `hb-graphite2.h`, and `hb-gobject.h`.

None of them changes how text is shaped. What they offer falls into four kinds: a face made from another library’s font object, so HarfBuzz reads tables through it; font funcs that ask that library for metrics and outlines, in place of [hb-ot](fonts-and-font-functions.html#hb-ot-the-default-funcs); Unicode funcs from another library’s character database; and conversions between HarfBuzz’s types and the other library’s. A few also carry a shaping backend, which [hb_shape and its backends](hb_shape-and-its-backends.html) covers. This chapter takes the layers one at a time: what each adds, and when an application would want it.

Most of the layers aren’t in the HarfBuzz this book is built with. Their output on this page was produced by hand, from a build of HarfBuzz {{hb}} on macOS with FreeType, cairo, ICU, GLib, GObject, Core Text, and Graphite turned on, and each example says so.

## Which layer is where

Each layer is turned on by a Meson option ([Building HarfBuzz](building-harfbuzz.html#optional-dependencies-and-backends)). Some are compiled into `libharfbuzz` itself; others are libraries of their own, so that a program that doesn’t use them doesn’t link their dependencies (`README.md:30`):

| Header | Option (default) | Library | What it adds |
|---|---|---|---|
| `hb-ft.h` | `freetype` (auto) | `libharfbuzz` | faces and fonts from an `FT_Face`; FreeType font funcs; a face loader |
| `hb-glib.h` | `glib` (auto) | `libharfbuzz` | GLib’s Unicode funcs; script conversions; blobs from `GBytes` |
| `hb-icu.h` | `icu` (auto) | `libharfbuzz-icu`, or `libharfbuzz` with `icu_builtin` | ICU’s Unicode funcs; script conversions |
| `hb-cairo.h` | `cairo` (auto) | `libharfbuzz-cairo` | cairo font faces that draw through HarfBuzz; cairo glyphs from a buffer |
| `hb-coretext.h` | `coretext` (off) | `libharfbuzz` | faces from a `CGFont`, fonts from a `CTFont`; Core Text font funcs and shaper |
| `hb-directwrite.h` | `directwrite` (off) | `libharfbuzz` | faces and fonts from an `IDWriteFontFace`; DirectWrite font funcs and shaper |
| `hb-gdi.h`, `hb-uniscribe.h` | `gdi` (off) | `libharfbuzz` | a face from an `HFONT`; the Uniscribe shaper |
| `hb-graphite2.h` | `graphite2` (off) | `libharfbuzz` | the Graphite shaper; the `gr_face` behind a face |
| `hb-gobject.h` | `gobject` (auto) | `libharfbuzz-gobject` | GObject types, for introspection |

“Auto” means the layer is built if Meson finds the library (`meson_options.txt:2` and on). The platform options are off by default, and they are also limited to their platforms: `gdi` and `directwrite` are checked only when the host is Windows, `coretext` only on Darwin (`meson.build:304` to `:354`).

A program can test what its HarfBuzz was built with. `hb-features.h`, installed with the headers, defines `HB_HAS_FREETYPE`, `HB_HAS_CAIRO`, `HB_HAS_ICU`, and the rest for the layers that were built (`src/meson.build:588`), from the `HAVE_` names the build sets: `HB_HAS_GRAPHITE` from `HAVE_GRAPHITE` (`meson.build:253`). In the hand-built HarfBuzz described above, `hb-shape --list-shapers` lists `graphite2`, and `hb-features.h` says `#define HB_HAS_GRAPHITE 1`. Before {{hb}} the build set `HAVE_GRAPHITE2` instead, so `HB_HAS_GRAPHITE` was never defined.

## FreeType: hb-ft

FreeType is the oldest partner. For years an application on Linux or Android opened a font with FreeType, made a HarfBuzz font from the same `FT_Face`, shaped with HarfBuzz, and rasterized with FreeType, and `hb-ft` exists to make that one step. [Fonts and font functions](fonts-and-font-functions.html#the-other-funcs) describes the FreeType font funcs themselves: how they set FreeType’s size, the lock they take, and the kerning and contour-point callbacks only they provide. This section is about the API around them.

### Faces

`hb_ft_face_create (ft_face, destroy)` makes a face that reads the font’s data through FreeType. If FreeType holds the whole font in memory, as it does for a face opened with `FT_New_Memory_Face`, the face is made over that memory directly; otherwise each table is fetched with `FT_Load_Sfnt_Table` as it is asked for (`hb-ft.cc:1341`, `:1363`). Either way, the face is an ordinary one, and a font made from it gets hb-ot’s funcs unless told otherwise (`hb-ft.cc:1318`).

There are three versions, which differ only in who keeps the `FT_Face` alive. The header is unusually direct about which to choose (`hb-ft.h:81`):

* `hb_ft_face_create_referenced` calls `FT_Reference_Face`, and `FT_Done_Face` when the face is destroyed. “This is the most convenient version to use. Use it unless you have very good reasons not to.”
* `hb_ft_face_create` does no reference counting. The caller must keep the `FT_Face` until the face is gone, and `destroy` is called with the `FT_Face` when it is.
* `hb_ft_face_create_cached` stores the face in the `FT_Face`’s `generic` field, so that asking again for the same `FT_Face` returns the same face. If something else was already using that field, its finalizer is run and the field is taken over (`hb-ft.cc:1440`).

Since 10.1.0 and 11.0.0, `hb_ft_face_create_from_file_or_fail` and `hb_ft_face_create_from_blob_or_fail` let FreeType open the file itself, with a FreeType library HarfBuzz keeps for the purpose. Their documentation gives the reason to: “This can be useful, for example, to load WOFF and WOFF2 font data” (`hb-ft.cc:1780`), which HarfBuzz’s own loader can’t unpack. They are also the `ft` [face loader](blobs-faces-and-lazy-tables.html#face-loaders), so `hb-shape --face-loader=ft` uses them.

### Fonts

`hb_ft_font_create (ft_face, destroy)` and `hb_ft_font_create_referenced (ft_face)` make the face and the font together, and install FreeType’s funcs on the font (`hb-ft.cc:1496`). The same advice applies: use the referenced one. `hb_ft_font_set_funcs` does the opposite job. It takes a font made from any face, such as one from `hb_face_create`, opens a private `FT_Face` on the face’s blob, and installs FreeType’s funcs on that (`hb-ft.cc:1931`). That private face is HarfBuzz’s own, and nothing outside can reach it except through `hb_ft_font_get_ft_face`.

When the font is made from an `FT_Face`, the `FT_Face` must already have a size, because hb-ft reads it unconditionally (`hb-ft.h:102`). The font’s scale is copied from it, and its units are FreeType’s: 26.6 fixed point, 64 units to the pixel. `hb_ft_font_changed` computes the scale from the face’s size metrics (`hb-ft.cc:1523`), and since FreeType’s `x_scale` converts font units to 64ths of a pixel, the result is the pixel size times 64. Every advance and offset HarfBuzz returns for that font is then in 64ths of a pixel, as FreeType’s own numbers are. Variation coordinates are copied too, as normalized coordinates (`hb-ft.cc:1550`).

Here is that in use. This is hand-written to show the calls, with no error checking:

```c
FT_Face ft_face;
FT_New_Face (ft_library, "Roboto-Regular.ttf", 0, &ft_face);
FT_Set_Pixel_Sizes (ft_face, 0, 11);          /* 11 pixels per em */

hb_font_t *font = hb_ft_font_create_referenced (ft_face);
/* hb_font_get_scale now gives 704: 11 × 64 */
hb_ft_font_set_load_flags (font, FT_LOAD_DEFAULT);   /* hinted */

hb_shape (font, buffer, NULL, 0);
/* x_advance values are in 64ths of a pixel */

hb_font_destroy (font);        /* drops HarfBuzz's reference */
FT_Done_Face (ft_face);        /* drops ours */
```

The **load flags** are what hb-ft passes to every `FT_Load_Glyph` and `FT_Get_Advance` call. They start as `FT_LOAD_DEFAULT | FT_LOAD_NO_HINTING` (`hb-ft.cc:131`), so a FreeType font is unhinted until `hb_ft_font_set_load_flags` says otherwise. Hinting is the main reason to use hb-ft at all, and [hb-raster](hb-raster.html#hinting-with-freetype) shows what it changes, in pixels and in advances.

### Keeping the two in step

A font made with hb-ft has its size in two places: the `hb_font_t`’s scale and coordinates, and the `FT_Face`’s size and design coordinates. There are two functions for keeping them together, one for each direction.

**From FreeType to HarfBuzz.** After the application changes the `FT_Face`, with `FT_Set_Char_Size` or `FT_Set_Var_Design_Coordinates`, it must call `hb_ft_font_changed`, which reads the scale and coordinates back. Nothing calls it automatically. Until it’s called, the `hb_font_t` still has its old scale, and hb-ft’s advance cache still has the old advances, while FreeType measures any glyph it hasn’t cached at the new size. Here is a hand-run program built against the FreeType-enabled HarfBuzz described above, with Roboto, load flags `FT_LOAD_DEFAULT`, and advances in 64ths of a pixel. It shapes `HH` at 11 pixels, then sets the `FT_Face` to 22 pixels and shapes `HO`, then calls `hb_ft_font_changed` and shapes `HO` again:

```
11 px                        H=512 H=512
FT at 22 px, not told        H=512 O=960
after hb_ft_font_changed     H=1024 O=960
```

In the middle line, the `H` comes from the cache, at 11 pixels, and the `O` from FreeType, at 22: one run, two sizes.

**From HarfBuzz to FreeType.** The other direction is now automatic. Every hb-ft callback compares the font’s serial number with the one it last saw, and if the font has changed, it sets FreeType’s size and coordinates from it before answering (`_hb_ft_hb_font_check_changed`, `hb-ft.cc:257`, called at `:531` and in every callback after it). `hb_ft_hb_font_changed`, added in 4.4.0 to do this by hand, says that “as of version 11.0.0, calling this function is not necessary” (`hb-ft.cc:1579`), though the documentation of `hb_ft_font_set_funcs` still tells the reader to call it (`:1922`; [HHW-81](bugs-this-book-found.html#hhw-81)). The change is made to the `FT_Face` itself, so when it is the application’s own face, the application sees it: in the program above, setting the font’s scale back to 704 with `hb_font_set_scale` put the `FT_Face` back to 11 pixels per em.

> Since {{hb}}: fixed on HarfBuzz main by [#6817](https://github.com/harfbuzz/harfbuzz/pull/6817) (20 November 2026), so main’s documentation of `hb_ft_font_set_funcs` no longer asks for `hb_ft_hb_font_changed`.

hb-ft turns the scale into a FreeType size in a simple way: it passes the scale to `FT_Set_Char_Size` as a character size in 26.6 points at FreeType’s default 72 dpi (`hb-ft.cc:192`). A font scaled in 64ths of a pixel gets the right FreeType size; one scaled in font units or whole pixels is set to a meaningless one, which matters only when hinting is on. A negative scale becomes a FreeType transform. If FreeType can’t set the size and the font has bitmap strikes, as color emoji fonts often do, hb-ft picks the largest strike and scales it with a transform instead (`:204`).

### Locking

The header warns that FreeType “is not thread-safe. Hence, these functions are not either” (`hb-ft.h:40`). What hb-ft does about it is to give each font a mutex and hold it during every FreeType call. An application that uses the same `FT_Face` itself, from another thread, can take the same lock: `hb_ft_font_lock_face` returns the `FT_Face` with the lock held, and blocks HarfBuzz’s calls until `hb_ft_font_unlock_face` (`hb-ft.cc:388`).

### When to use it, and when not

Use hb-ft when shaping must agree with FreeType’s numbers: when text is rasterized hinted by FreeType, and its advances must be the hinted ones, or when the font is one HarfBuzz can’t read but FreeType can, such as WOFF, or a Type 1 font whose kerning only FreeType knows ([Fonts and font functions](fonts-and-font-functions.html#the-other-funcs)). The `FT_Face` an application already has is also a convenient source of a face, through `hb_ft_face_create_referenced`, even when its funcs aren’t wanted.

Otherwise, hb-ot is usually right. It is the default for every new font ([Choosing funcs](fonts-and-font-functions.html#choosing-funcs)), it reads every table HarfBuzz’s shaper reads, its outlines and metrics vary with the font, and it takes no lock. hb-ft with hinting off gives the same advances, at the cost of a lock and a second copy of the font’s state. In the hand-built HarfBuzz, `hb-shape --font-funcs=ft` and `--font-funcs=ot` give identical output for Roboto at its default scale.

## cairo: hb-cairo

cairo is a 2D graphics library, used by GTK among others. `hb-cairo`, added in 7.0.0 as “a separate harfbuzz-cairo library” (`NEWS`), connects it to HarfBuzz in both directions: it lets cairo draw glyphs with HarfBuzz’s outlines and paint, and it converts a shaped buffer into the glyph array cairo draws.

### Font faces

`hb_cairo_font_face_create_for_font (font)` makes a cairo font face from a HarfBuzz font. It is a cairo *user font*: cairo calls back into HarfBuzz to draw each glyph, which hb-cairo does with `hb_font_draw_glyph_or_fail` and the draw funcs of [Drawing outlines](drawing-outlines.html), or, for color glyphs, `hb_font_paint_glyph` with paint funcs that turn the [paint graph](color.html) into cairo operations (`hb-cairo.cc:639`, `:664`). The HarfBuzz font is made immutable. Its variations and synthetic slant and bold show in the result, but its scale doesn’t: cairo’s font matrix sets the size (`hb-cairo.cc:732`).

`hb_cairo_font_face_create_for_face (face)` makes a font face from a face instead, and a new HarfBuzz font is made for each cairo scaled font. Its variations come from the cairo font options, and its scale is the cairo font matrix times the **scale factor** set with `hb_cairo_font_face_set_scale_factor`, or the units per em if none was set (`hb-cairo.cc:546`). `hb_cairo_font_face_set_font_init_func` installs a callback to adjust each new font before it is used.

Because it is drawn by HarfBuzz, such a font face works on any cairo surface, in color, but unhinted, as the user manual notes (`docs/usermanual-integration.xml:349`). It also supports cairo’s simple text API. Given `cairo_show_text`, it shapes the string with `hb_shape` after `hb_buffer_guess_segment_properties`, with no features and no control over language or direction (`hb-cairo.cc:604`). That is fine for a label; for real text, shape with HarfBuzz and pass cairo the glyphs.

### Glyphs from a buffer

`hb_cairo_glyphs_from_buffer` does that conversion. It takes the shaped buffer, a scale factor for each axis, an origin, and optionally the UTF-8 text, and fills an array of `cairo_glyph_t` with absolute positions: each glyph’s offset added to the sum of the advances before it, divided by the scale factor, with y flipped, since cairo’s y grows downward (`hb-cairo.cc:1043`). The array has one more entry than there are glyphs, holding the total advance. With the text, it also fills cairo’s cluster array, for `cairo_show_text_glyphs`, which lets PDF output keep the text searchable. cairo’s clusters must be monotonic, so if the buffer’s aren’t, everything becomes one cluster (`hb-cairo.cc:1026`).

The scale factor is whatever relates the HarfBuzz font’s scale to cairo’s font size. Shaping `Ham` with the 11-pixel FreeType font above, whose units are 64ths of a pixel, and passing 64 for both, gives glyphs at x = 0, 8, and 15, and an extra entry at 26: whole pixels, since the advances were hinted (hand-run). The doc comment has the descriptions of the two scale-factor parameters swapped: “@x_scale_factor: scale factor to divide #hb_position_t Y values by” (`hb-cairo.cc:936`; [HHW-81](bugs-this-book-found.html#hhw-81)).

> Since {{hb}}: fixed on HarfBuzz main by [#6817](https://github.com/harfbuzz/harfbuzz/pull/6817) (20 November 2026), so main’s doc comment describes each scale factor with its own axis.

### How hb-view uses it

`hb-view`, the drawing tool of [The command-line tools](command-line-tools.html#drawing-hb-vector-hb-raster-and-hb-view), is hb-cairo’s main user in HarfBuzz’s own tree. It makes its cairo font face with `hb_cairo_font_face_create_for_font`, with the scale factor set to `1 << subpixel_bits`, the same factor by which it multiplied the font size when it set the HarfBuzz font’s scale (`util/helper-cairo.hh:102`, `util/font-options.hh:101`). It turns each shaped line into cairo glyphs with `hb_cairo_glyphs_from_buffer` and the same factor (`helper-cairo.hh:587`), and draws them with `cairo_show_glyphs` or `cairo_show_text_glyphs`. Only when cairo is older than 1.17.5, or the `HB_DRAW` environment variable is 0, does it draw through cairo’s FreeType font face instead, because older cairo had bugs in color fonts and user fonts (`helper-cairo.hh:73`).

## Unicode from ICU or GLib: hb-icu and hb-glib

HarfBuzz asks Unicode six questions, through an `hb_unicode_funcs_t`, and answers them by default from its own tables ([Unicode inside HarfBuzz](unicode-inside-harfbuzz.html#three-implementations)). `hb_icu_get_unicode_funcs` and `hb_glib_get_unicode_funcs` return funcs that ask ICU or GLib instead. Each is a single static object, and an application uses it by setting it on each buffer with `hb_buffer_set_unicode_funcs`.

On the same machine, the three agree on ordinary questions. Asked for the general category and combining class of U+0301 COMBINING ACUTE ACCENT and the script of U+0627 ARABIC LETTER ALEF, HarfBuzz’s tables, Homebrew’s ICU, and Homebrew’s GLib all answered 12 (nonspacing mark), 230, and `Arab` (hand-run). Where they can differ is newly encoded characters: HarfBuzz’s tables follow its own release, the others follow whatever version of ICU or GLib is installed.

So the reasons to switch are about agreement and size, not quality. An application whose text stack is built on ICU, for segmentation, line breaking, and bidi, may want HarfBuzz to see characters exactly as ICU does. And one that ships ICU or GLib anyway can save the 40 to 60 KB of HarfBuzz’s tables. `CONFIG.md:65` describes that: build with ICU built in (`icu_builtin`), or with GLib, and define `HB_NO_UCD`. Then `hb_unicode_funcs_get_default` returns GLib’s funcs if GLib is there, and ICU’s otherwise (`hb-unicode.cc:154`). Without `HB_NO_UCD`, HarfBuzz’s own tables stay the default, whatever else is built.

Both headers also convert script codes, because a text stack that uses ICU or GLib hands HarfBuzz its runs labeled with that library’s script enum. `hb_icu_script_to_script` and `hb_icu_script_from_script` convert between `UScriptCode` and `hb_script_t` through the four-letter ISO 15924 names (`hb-icu.cc:84`). `hb_glib_script_to_script` and `hb_glib_script_from_script` do the same for `GUnicodeScript`, using GLib’s own ISO 15924 conversion (`hb-glib.cc:66`). hb-glib has one more function, `hb_glib_blob_create`, which wraps a `GBytes` in a blob and keeps a reference to it (`hb-glib.cc:211`); it is mostly useful to bindings, as the next section but one shows.

## The platforms: Core Text, DirectWrite, GDI, and Uniscribe

The platform layers do two jobs. One is to run the operating system’s own shaper in place of HarfBuzz’s, which is for comparison and testing, and is in [hb_shape and its backends](hb_shape-and-its-backends.html#the-platform-backends-coretext-directwrite-uniscribe). The other is to let an application that already has the platform’s font objects shape with HarfBuzz’s own `ot` shaper. That is the part covered here.

### Core Text

On Apple platforms, `hb_coretext_face_create (cg_font)` makes a face from a `CGFont`, which fetches each table with `CGFontCopyTableForTag` (`hb-coretext.cc:57`, `:436`). `hb_coretext_font_create (ct_font)` makes a font from a `CTFont`: it takes the `CGFont` behind it for the face, sets the font’s `ptem` to the `CTFont`’s size, copies its variation settings, and keeps the `CTFont` for the Core Text shaper and funcs to use (`hb-coretext.cc:584`). The font funcs it gets are hb-ot’s. The documentation calls Core Text’s funcs “rarely needed” (`:576`); `hb_coretext_font_set_funcs`, since 10.1.0, installs them.

This is how an application with a `CTFont` from the system’s font matching shapes it with HarfBuzz, for example to get OpenType features applied as HarfBuzz applies them, or the same results on every platform. Two details follow from the code. Since `ptem` is in points but the scale is still the units per em, the application sets the scale it wants itself. And the kept `CTFont` lasts only until the font changes: `hb_font_t::changed` throws away all shaper data (`hb-font.hh:1183`), so after `hb_font_set_scale`, `hb_coretext_font_get_ct_font` returns a new `CTFont` that HarfBuzz made from the `CGFont` at `ptem` (`hb-coretext-shape.cc:68`) (inferred from the code). `hb_coretext_face_create_from_file_or_fail` and `_from_blob_or_fail` are the `coretext` face loader; since 15.2.0 they can open any face of a collection as well as a named instance. When the face index isn’t 0, or the file holds more than one face or named instance, HarfBuzz opens the face itself, reads its PostScript name (name ID 6), and takes the Core Text descriptor with that name (`hb-coretext.cc:478`, `:200`). A font with no PostScript name then fails to load: in the hand-built HarfBuzz, the `coretext` loader refuses every face index of the variable test font of [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html), `instances.ttf`, which has none, though 15.1.0 opened it ([HHW-84](bugs-this-book-found.html#hhw-84)).

### DirectWrite

On Windows, `hb_directwrite_face_create` makes a face from an `IDWriteFontFace`, fetching tables through it (`hb-directwrite.cc:267`), and `hb_directwrite_font_create`, since 11.0.0, makes a font from one, copying its variation axis values when it has any (`:395`). `hb_directwrite_font_set_funcs` installs DirectWrite’s funcs, and `hb_directwrite_face_get_dw_font_face` and `hb_directwrite_font_get_dw_font_face` give the `IDWriteFontFace` back. `hb_directwrite_font_get_dw_font`, from 10.3.0, was deprecated in 11.0.0 and now returns `NULL` (`:465`).

### GDI and Uniscribe

`hb_gdi_face_create (hfont)`, since 2.6.0, makes a face from a GDI `HFONT`, for the many Windows programs that still select fonts through GDI. Each table is read with `GetFontData` on a device context the font is selected into, and copied into a new blob (`hb-gdi.cc:42`). The face doesn’t own the `HFONT` (`:82`), so the application must keep it until the face is gone.

`hb-uniscribe.h` has only two functions, `hb_uniscribe_font_get_logfontw` and `hb_uniscribe_font_get_hfont`, which return the `LOGFONTW` and `HFONT` that the Uniscribe shaper made for a font, or `NULL` if it hasn’t made one (`hb-uniscribe.cc:560`, `:577`). They are for code that runs the Uniscribe shaper and then wants to call other Uniscribe or GDI functions on the same font. The user manual says that `hb_shape` itself is the replacement for Uniscribe’s `ScriptShape` and `ScriptPlace` (`docs/usermanual-integration.xml:388`).

## Graphite: hb-graphite2

`hb-graphite2.h` belongs to the Graphite shaping backend, which [hb_shape and its backends](hb_shape-and-its-backends.html#graphite2) describes. Its public API is the tag `HB_GRAPHITE2_TAG_SILF` and `hb_graphite2_face_get_gr_face`, which returns the `gr_face` that the backend made for a face, for an application that wants to ask Graphite about the font’s features itself (`hb-graphite2.cc:170`). `hb_graphite2_font_get_gr_font` has returned `NULL` since 1.4.2. There is nothing to call to turn Graphite on: a HarfBuzz built with it uses it for any font with a `Silf` table.

## GObject and introspection: hb-gobject

`libharfbuzz-gobject` registers HarfBuzz’s types with GObject’s type system. Each object type (buffer, blob, face, font, font funcs, set, map, shape plan, Unicode funcs, draw funcs, paint funcs) becomes a boxed type whose copy is `hb_*_reference` and whose free is `hb_*_destroy`. Each plain struct, such as `hb_feature_t` or `hb_glyph_position_t`, becomes a boxed type that is copied by value. Every enum gets a GType generated from the headers (`hb-gobject-structs.cc:57`, `hb-gobject-enums.h.tmpl`). Its documentation says that this is “solely a linkage” and that “client programs should never need to access the GObject-integration mechanics” (`hb-gobject-structs.cc:41`).

What it is for is GObject introspection. With `introspection` on, the build runs `g-ir-scanner` over the headers and sources of `libharfbuzz` and `libharfbuzz-gobject`, and makes `HarfBuzz-0.0.gir` and `HarfBuzz-0.0.typelib` (`src/meson.build:1329`). The annotations in HarfBuzz’s doc comments, such as `(transfer full)` and `(nullable)`, tell the scanner who owns what, and `(skip)` leaves a function out of bindings. Because hb-ft and hb-glib are compiled into `libharfbuzz`, they are in the typelib; the separate libraries `libharfbuzz-subset`, `-cairo`, `-icu`, `-raster`, and `-vector` aren’t. In the hand-built HarfBuzz the `.gir` file has 567 functions, 16 of them `hb_ft_*`, 4 `hb_glib_*`, and none `hb_subset_*`.

Any language with a GObject introspection binding can then load the typelib at run time. The GObject introspection project lists them, among them PyGObject for Python and GJS for JavaScript ([users](https://gi.readthedocs.io/en/latest/users.html)). HarfBuzz’s `README.python.md` explains the Python route, and `src/sample.py` uses it: `from gi.repository import HarfBuzz`, then `hb.glib_blob_create (GLib.Bytes.new (fontdata))`, `hb.face_create`, `hb.font_create`, and so on, the C API with the `hb_` prefix moved into the namespace. This is where hb-glib’s `GBytes` function earns its place, since a `GBytes` is how introspection passes bytes. The README also warns: “The Python API will change.”

## Other language bindings

Most programs that call HarfBuzz from another language use a binding written for that language instead. Those the HarfBuzz project hosts itself, harfbuzzjs (WebAssembly, for JavaScript) and uharfbuzz (Cython, for Python), are described in [The family](family.html#other-relatives), along with harfbuzz_rs for Rust. Two more are widely used:

* **harfbuzz-sys** and **harfbuzz**, from the Servo project, are “Rust bindings to the HarfBuzz text shaping engine” ([rust-harfbuzz](https://github.com/servo/rust-harfbuzz)). The repository has HarfBuzz as a Git submodule, built with the `bundled` feature. Its `harfbuzz-sys/Cargo.toml` has features named `coretext`, `directwrite`, and `freetype`, all on by default, which expose this chapter’s integration layers to Rust.
* **HarfBuzzSharp**, in the SkiaSharp repository, “provides .NET bindings for the HarfBuzz OpenType text shaping engine”, and pairs with SkiaSharp for rendering through `SkiaSharp.HarfBuzz` ([its README](https://github.com/mono/SkiaSharp/blob/main/binding/HarfBuzzSharp/PACKAGE-README.md)). The repository has a native-assets package for each platform it supports, from Android to WebAssembly (`binding/HarfBuzzSharp.NativeAssets.*`).

Bindings like these wrap the core C API directly, so what they offer of the integration layers is whatever their authors chose to wrap.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-ft.h`, `src/hb-ft.cc` | FreeType faces, fonts, funcs, load flags, `hb_ft_font_changed`, the lock, the face loader |
| `src/hb-cairo.h`, `src/hb-cairo.cc`, `src/hb-cairo-utils.cc` | cairo user font faces, `hb_cairo_glyphs_from_buffer`, the cairo draw and paint funcs |
| `src/hb-icu.cc`, `src/hb-glib.cc` | ICU and GLib Unicode funcs and script conversions; `hb_glib_blob_create` |
| `src/hb-coretext.cc`, `src/hb-coretext-font.cc` | faces from `CGFont`, fonts from `CTFont`, Core Text funcs |
| `src/hb-directwrite.cc`, `src/hb-directwrite-font.cc` | faces and fonts from `IDWriteFontFace`, DirectWrite funcs |
| `src/hb-gdi.cc`, `src/hb-uniscribe.cc` | faces from `HFONT`; the Uniscribe accessors (the rest is the shaper) |
| `src/hb-graphite2.cc` | the Graphite backend and `hb_graphite2_face_get_gr_face` |
| `src/hb-gobject-structs.cc`, `src/hb-gobject-enums.*.tmpl` | the GObject types |
| `src/meson.build`, `meson.build` | which layer goes into which library; the introspection data; `hb-features.h` |
| `util/helper-cairo.hh` | how `hb-view` uses hb-cairo |
| `docs/usermanual-integration.xml` | the user manual’s chapter on integration |

## In short

* The integration layers connect HarfBuzz to other libraries’ objects: faces from their fonts, font funcs from their metrics, Unicode funcs from their databases, and conversions. None changes how text is shaped.
* hb-ft makes faces and fonts from an `FT_Face`; use the `_referenced` versions. Its scale is FreeType’s 26.6, its load flags start unhinted, and after changing the `FT_Face` call `hb_ft_font_changed`. Changes to the `hb_font_t` reach FreeType by themselves.
* Use hb-ft for FreeType’s hinted metrics or for fonts only FreeType can read; otherwise hb-ot, the default, is usually right.
* hb-cairo makes cairo font faces that draw and paint through HarfBuzz, and turns a shaped buffer into cairo glyphs and clusters; `hb-view` is built on it.
* hb-icu and hb-glib supply Unicode funcs and script conversions, for agreement with an ICU or GLib text stack, or with `HB_NO_UCD`, a smaller library.
* The platform layers wrap a `CGFont`, `CTFont`, `IDWriteFontFace`, or `HFONT` so that HarfBuzz’s own shaper can use it; their shapers are for comparison.
* hb-gobject and introspection make HarfBuzz callable from PyGObject, GJS, and other introspection bindings; most programs use a language’s own binding instead.
