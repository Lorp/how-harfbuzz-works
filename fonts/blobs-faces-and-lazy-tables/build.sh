#!/bin/sh
# Builds this chapter's test fonts from fonts that other chapters build
# (fonts/gsub and fonts/variations). See build-fonts.py.
# Only shape and info blocks use them, so no views are written.
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} build-fonts.py
