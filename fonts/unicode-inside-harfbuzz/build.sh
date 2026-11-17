#!/bin/sh
# Builds this chapter's test font from its feature file.
# (No views blocks are used, so no FONT.views.json is written.)
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} build-font.py unicode.fea unicode.ttf
