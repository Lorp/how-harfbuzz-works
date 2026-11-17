#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py), then writes the TTX
# of their MATH, BASE, STAT, name, ltag and meta tables (FONT.views.json) for
# the site build, with views.py: tools/font-views.py doesn't keep all of them.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PY build-fonts.py .
$PY views.py *.ttf
