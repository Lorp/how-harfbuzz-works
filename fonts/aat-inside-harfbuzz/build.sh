#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py), then writes the
# TTX of latin.ttf's `morx` and `feat` tables (latin.views.json) for the
# chapter's `table` block, with morx-views.py: tools/font-views.py doesn't
# keep those tables. Needs fontTools with `morx` support (4.38 has it).
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PY build-fonts.py
$PY morx-views.py latin.ttf
