#!/bin/sh
# Builds this chapter's test fonts: two source fonts made with fontTools
# (build-fonts.py), and their subsets, made with hb-subset from the
# HarfBuzz build in .cache/harfbuzz, and a smaller subset of one subset. Then writes layout.dump.txt, where the
# objects lie in each GSUB (made by layout.py, not by HarfBuzz).
# Only shape and info blocks use the fonts, so no views are written.
#
# If HB_SUBSET_DEBUG names an hb-subset built with
# -DHB_DEBUG_SUBSET=1 -DHB_DEBUG_SUBSET_REPACK=1, its messages about GSUB
# and the repacker's for each subset are written to FONT-subset.repack-log.txt
# as well. (The committed logs were made that way; see the chapter.)
set -e
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
HB_SUBSET=${HB_SUBSET:-../../.cache/harfbuzz/build/util/hb-subset}
SOURCE_DATE_EPOCH=0 $PYTHON build-fonts.py
for f in forty sixty; do
  $HB_SUBSET --unicodes-file=unicodes.txt --no-layout-closure \
    --layout-features='*' --glyph-names -o $f-subset.ttf $f.ttf
  if [ -n "$HB_SUBSET_DEBUG" ]; then
    $HB_SUBSET_DEBUG --unicodes-file=unicodes.txt --no-layout-closure \
      --layout-features='*' --glyph-names -o /dev/null $f.ttf 2>&1 \
      | grep -E 'SUBSET_REPACK|OT::GSUB' | sed -E 's/^SUBSET(_REPACK)? *├╴: //' > $f-subset.repack-log.txt
  fi
done
# A much smaller subset of sixty-subset.ttf: its first 64 characters.
$HB_SUBSET --unicodes=4E01-4E40 --no-layout-closure --layout-features='*' \
  --glyph-names -o sixty-small.ttf sixty-subset.ttf
$PYTHON layout.py sixty.ttf forty-subset.ttf sixty-subset.ttf sixty-small.ttf > layout.dump.txt
