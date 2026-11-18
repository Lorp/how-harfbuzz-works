#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py), then writes the
# views of their GPOS lookups (FONT.views.json) for the site build, with
# gpos-views.py: tools/font-views.py shows only GSUB lookups.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PY build-fonts.py
$PY gpos-views.py gpos.ttf class-first.ttf second-value.ttf var-kern.ttf context.ttf
