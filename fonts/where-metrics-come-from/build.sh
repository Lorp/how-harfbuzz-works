#!/bin/sh
# Builds this chapter's test fonts.
set -e
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
SOURCE_DATE_EPOCH=0 $PYTHON build-metrics-fonts.py .
