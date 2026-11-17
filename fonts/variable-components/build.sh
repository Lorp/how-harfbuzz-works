#!/bin/sh
# Decodes VARC from HarfBuzz's own test fonts for the chapter (varc-dump.py:
# not HarfBuzz), and writes varc-6868-no-reset.ttf, a copy of
# varc-6868.ttf with RESET_UNSPECIFIED_AXES cleared (no-reset.py).
#
# Needs fontTools 4.68 or later, which can read VARC: PYTHON defaults to
# the one in .cache/venv. The test fonts come from the HarfBuzz source tree
# the book is built against (HB_BUILD, as in tools/build-site.mjs).
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-../../.cache/venv/bin/python}
FONTS=${HB_BUILD:-../../.cache/harfbuzz}/test/api/fonts
AC00=$FONTS/varc-ac00-ac01.ttf
U6868=$FONTS/varc-6868.ttf
$PY varc-dump.py $AC00 walk 1 wght=598.4 > ac00-walk.txt
$PY varc-dump.py $AC00 bytes 3 > ac00-bytes.txt
$PY varc-dump.py $AC00 store 0:0 > ac00-store.txt
$PY varc-dump.py $U6868 store 0:4 > 6868-store-mu.txt
$PY varc-dump.py $U6868 store 3:7 > 6868-store-stem.txt
$PY varc-dump.py $U6868 bytes 7 > 6868-bytes-mu.txt
$PY varc-dump.py $U6868 walk 1 wght=400 > 6868-walk-400.txt
$PY varc-dump.py $U6868 walk 1 wght=700 > 6868-walk-700.txt
$PY no-reset.py $U6868 varc-6868-no-reset.ttf 2 5 7
$PY lsb.py ${HB_BUILD:-../../.cache/harfbuzz}/test/api/fonts/varc-static-gvar.ttf varc-static-gvar-lsb.ttf 100
