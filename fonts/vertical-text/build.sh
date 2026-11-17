#!/bin/sh
# Builds this chapter's test fonts from vertical.fea (see build-fonts.py),
# then writes the views of their GSUB lookups (FONT.views.json).
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PY build-fonts.py
$PY ../../tools/font-views.py vertical.ttf novert.ttf vert-kana.ttf vrt2.ttf
