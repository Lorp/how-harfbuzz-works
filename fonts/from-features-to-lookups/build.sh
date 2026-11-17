#!/bin/sh
# Builds this chapter's test fonts (see build-fonts.py; varliga*.ttf are made
# from fonts/variations/var.ttf), then writes their lookup views.
set -e
cd "$(dirname "$0")"
T=../../tools
${PYTHON:-python3} build-fonts.py
${PYTHON:-python3} $T/font-views.py *.ttf
