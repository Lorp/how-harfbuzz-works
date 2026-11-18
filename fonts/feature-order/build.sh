#!/bin/sh
# Builds the appendix's test fonts: see build-fonts.py.
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} build-fonts.py
