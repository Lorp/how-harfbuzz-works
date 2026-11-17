#!/bin/sh
# Builds this chapter's fonts. One source font, var-rvrn.ttf, is made by
# build-instancing-fonts.py (it needs a fontTools recent enough for avar 2
# designspaces, as tools/build-var-test-fonts.py does). Every other font here
# is an instance, cut by HarfBuzz's own hb-subset from that font or from the
# shared fonts in fonts/variations, since the book's blocks can't run
# hb-subset. Each keeps every character (--unicodes='*') and its glyph names.
#
# Then it writes the views (FONT.views.json) of the fonts the chapter shows
# tables from, and a summary of the feature variations (featvars-summary.txt).
#
# Needs hb-subset: HB_SUBSET, or the one tools/build-harfbuzz.sh builds.
set -e
cd "$(dirname "$0")"
HB_SUBSET=${HB_SUBSET:-../../.cache/harfbuzz/build/util/hb-subset}
V=../variations
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-instancing-fonts.py .

inst() { # inst SOURCE OUT VARIATIONS [OPTIONS...]
  src=$1; out=$2; vars=$3; shift 3
  "$HB_SUBSET" "$src" --unicodes='*' --glyph-names --variations="$vars" -o "$out" "$@"
}

inst $V/var.ttf       var-wght700.ttf          wght=700
inst $V/var.ttf       var-static700.ttf        wght=700,wdth=drop
inst $V/var.ttf       var-wght400-800.ttf      wght=400:800
inst $V/var.ttf       var-wght400-800-iup.ttf  wght=400:800 --optimize
inst $V/var-avar.ttf  var-avar-wght400-800.ttf wght=400:800
inst $V/var-avar2.ttf var-avar2-wght700.ttf    wght=700
inst var-rvrn.ttf     var-rvrn-wght700.ttf     wght=700
inst var-rvrn.ttf     var-rvrn-500-700-900.ttf wght=500:700:900

${PYTHON:-python3} ../../tools/font-views.py var-wght700.ttf var-wght400-800.ttf \
  var-wght400-800-iup.ttf var-avar-wght400-800.ttf var-avar2-wght700.ttf
${PYTHON:-python3} featvars-summary.py var-rvrn.ttf var-rvrn-wght700.ttf \
  var-rvrn-500-700-900.ttf > featvars-summary.txt
