#!/bin/sh
# Builds this chapter's test fonts from their feature files, then writes
# each font's lookup views (FONT.views.json) for the site build.
set -e
cd "$(dirname "$0")"
T=../../tools
${PYTHON:-python3} $T/build-test-font.py ligatures.fea ligatures.ttf
${PYTHON:-python3} $T/build-test-font.py ccmp-first.fea ccmp-first.ttf
${PYTHON:-python3} $T/build-test-font.py ligatures.fea shortest-first.ttf --shortest-first
${PYTHON:-python3} $T/build-test-font.py constructs.fea constructs.ttf
${PYTHON:-python3} $T/font-views.py *.ttf
