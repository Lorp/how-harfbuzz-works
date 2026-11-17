#!/bin/sh
# Builds this chapter's test font from a font another chapter builds
# (fonts/variations/var.ttf), then writes its lookup views. See build-fonts.py.
set -e
cd "$(dirname "$0")"
T=../../tools
${PYTHON:-python3} build-fonts.py
${PYTHON:-python3} $T/font-views.py featvar.ttf
