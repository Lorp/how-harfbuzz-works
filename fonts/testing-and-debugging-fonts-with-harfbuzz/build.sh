#!/bin/sh
# Builds this chapter's test fonts with the program Testing HarfBuzz shows,
# examples/test-font/make-test-font.py. Needs Python 3 with fontTools.
#   broken.ttf     a font whose rules don't fire where its maker expects
#   release-1.ttf  release 1 of a font under test
#   release-2.ttf  release 2: adds a calt lookup that makes o.alt, and loses
#                  the T o kerning
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} ../../examples/test-font/make-test-font.py broken.fea broken.ttf "Th fit" f_i T_h
for n in 1 2; do
  ${PYTHON:-python3} ../../examples/test-font/make-test-font.py release-$n.fea release-$n.ttf "To fit" f_i o.alt
done
