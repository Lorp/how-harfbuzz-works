#!/bin/sh
# Builds this chapter's test fonts, and writes bytes.dump.txt, the bytes
# that the chapter shows (made by dump.py, not by HarfBuzz).
set -e
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PYTHON build-fonts.py
$PYTHON dump.py bytes.ttf > bytes.dump.txt
