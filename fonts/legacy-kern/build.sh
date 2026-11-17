#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py), then writes the
# TTX of their `kern` tables (FONT.views.json) for the site build, with
# kern-views.py: tools/font-views.py doesn't keep `kern`.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PY build-fonts.py
$PY kern-views.py *.ttf
