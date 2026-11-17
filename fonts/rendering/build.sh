#!/bin/sh
# Builds this chapter's test font, modes.ttf, with the Colour chapter's
# helpers (fonts/colour/build-colour-fonts.py). No views blocks use it, so
# no FONT.views.json is written.
set -e
cd "$(dirname "$0")"
SOURCE_DATE_EPOCH=0 ${PYTHON:-python3} build-fonts.py .
