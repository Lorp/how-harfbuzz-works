#!/bin/sh
# Builds this chapter's test fonts. See build-fonts.py.
# (No views blocks are used, so no FONT.views.json is written.)
set -e
cd "$(dirname "$0")"
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-fonts.py
