#!/bin/sh
# Builds this chapter's test fonts: good.ttf from sanitizer.fea, and three
# copies of it with one offset broken in each (see build-fonts.py). Then
# writes the views (FONT.views.json) of the good font for the site build.
# The broken fonts get no views: fontTools can't read them, which is the point.
set -e
cd "$(dirname "$0")"
T=../../tools
PY=${PYTHON:-python3}
$PY build-fonts.py
$PY $T/font-views.py good.ttf
