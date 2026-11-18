#!/bin/sh
# Builds this chapter's test font with the program the chapter shows,
# examples/test-font/make-test-font.py. Needs Python 3 with fontTools.
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} ../../examples/test-font/make-test-font.py question.fea question.ttf fiT f_i f_i.short
