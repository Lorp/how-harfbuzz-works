#!/bin/sh
# Subsets for “The command-line tools”, cut from the font of “Why shaping
# exists” by HarfBuzz's own hb-subset, which the book's blocks can't run.
# Both keep their glyph names (--glyph-names), so that hb-info and hb-shape
# can show them.
#
# Needs hb-subset: HB_SUBSET, or the one tools/build-harfbuzz.sh builds.
set -e
cd "$(dirname "$0")"
HB_SUBSET=${HB_SUBSET:-../../.cache/harfbuzz/build/util/hb-subset}
SRC=../why-shaping-exists/shaping.ttf

"$HB_SUBSET" "$SRC" --text=fi --glyph-names -o fi.ttf
"$HB_SUBSET" "$SRC" --text=fi --glyph-names --layout-features-=liga -o fi-noliga.ttf
