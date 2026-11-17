#!/bin/sh
# Builds this chapter's test fonts. No views blocks use them, so no
# FONT.views.json is written.
set -e
cd "$(dirname "$0")"
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-fonts.py .
