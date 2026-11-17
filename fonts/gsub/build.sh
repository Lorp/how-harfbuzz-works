#!/bin/sh
# Builds this chapter's test fonts from their feature files.
set -e
cd "$(dirname "$0")"
B=../../tools/build-test-font.py
python3 $B ligatures.fea ligatures.ttf
python3 $B ccmp-first.fea ccmp-first.ttf
python3 $B ligatures.fea shortest-first.ttf --shortest-first
