#!/bin/sh
# Builds this chapter's test fonts, and the table views of colr0.ttf
# (CPAL, COLR) that the chapter's `table` blocks show.
set -e
cd "$(dirname "$0")"
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-color-fonts.py .
${PYTHON:-python3} ../../tools/font-views.py colr0.ttf
