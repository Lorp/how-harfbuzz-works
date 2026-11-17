#!/bin/sh
# Builds this chapter's source fonts (see build-subsetting-fonts.py), then cuts
# subsets from them with HarfBuzz's own hb-subset, which the book's blocks
# can't run. Every subset keeps its glyph names (--glyph-names), so that
# hb-info and hb-shape can show them.
#
# Needs hb-subset: HB_SUBSET, or the one tools/build-harfbuzz.sh builds.
set -e
cd "$(dirname "$0")"
HB_SUBSET=${HB_SUBSET:-../../.cache/harfbuzz/build/util/hb-subset}
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-subsetting-fonts.py .

sub() { # sub SOURCE OUT OPTIONS...
  src=$1; out=$2; shift 2
  "$HB_SUBSET" "$src" --glyph-names -o "$out" "$@"
}

sub demo.ttf if.ttf            --text=if
sub demo.ttf if-nohint.ttf     --text=if --no-hinting
sub demo.ttf fi-retain.ttf     --text=fi --retain-gids
sub demo.ttf star.ttf          --text=★
sub demo.ttf e-acute.ttf       --unicodes=65,301
sub demo.ttf aacute.ttf        --text=Á
sub demo.ttf paren.ttf         --text='('
sub demo.ttf paren-nobidi.ttf  --text='(' --no-bidi-closure
sub demo.ttf ct.ttf            --text=ct
sub demo.ttf ct-dlig.ttf       --text=ct --layout-features+=dlig
sub nested.ttf nested-a.ttf    --text=a
sub math.ttf math-integral.ttf --text=∫
sub math.ttf math-rtlm.ttf     --text=∫ --glyphs=integral.rtlm
sub kern.ttf kern-map.ttf      --text=ACGOQTVWY --gid-map=1:1,2:9,3:8,4:7,5:6,6:5,7:4,8:3,9:2
sub symbol.ttf symbol-a.ttf    --text=a
# A CFF font from another chapter, to compare its .notdef with glyf's.
sub ../drawing-outlines/cff.otf cff-o.otf --text=o

${PYTHON:-python3} ../../tools/font-views.py demo.ttf if.ttf star.ttf
${PYTHON:-python3} math-summary.py math.ttf math-integral.ttf math-rtlm.ttf > math-summary.txt
