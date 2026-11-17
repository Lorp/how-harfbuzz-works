#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py), then writes the
# lookup views of the font whose stch lookup the chapter shows.
set -e
cd "$(dirname "$0")"
T=../../tools
${PYTHON:-python3} build-fonts.py
${PYTHON:-python3} $T/font-views.py stch.ttf
