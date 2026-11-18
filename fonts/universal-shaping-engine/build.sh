#!/bin/sh
# Builds this chapter's test fonts from their feature files. See build-fonts.py.
# (No views blocks are used, so no FONT.views.json is written.)
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} build-fonts.py
