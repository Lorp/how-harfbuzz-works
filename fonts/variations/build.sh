#!/bin/sh
# Builds the variable test fonts shared by the chapters on variations, then
# writes each font's views (FONT.views.json) for the site build.
set -e
cd "$(dirname "$0")"
T=../../tools
SOURCE_DATE_EPOCH=0 python3 $T/build-var-test-fonts.py .
python3 $T/font-views.py *.ttf
