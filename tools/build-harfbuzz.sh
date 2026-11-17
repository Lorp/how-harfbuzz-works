#!/bin/sh
# Fetches and builds the HarfBuzz version this book describes, twice:
#   build/      as released: hb-shape, hb-vector (outlines as SVG, for the
#               `draw` blocks) and hb-info (for the `info` blocks)
#   build-msg/  with HB_BUFFER_MESSAGE_MORE: hb-shape only, for the detailed traces
# into .cache/harfbuzz/ (or $HB_BUILD).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(node -p "require('$ROOT/book/book.json').harfbuzz")
[ -n "$VERSION" ] || { echo "can't read the HarfBuzz version from book/book.json" >&2; exit 1; }
DIR=${HB_BUILD:-$ROOT/.cache/harfbuzz}
if [ ! -d "$DIR" ]; then
  git clone --depth 1 --branch "$VERSION" https://github.com/harfbuzz/harfbuzz.git "$DIR"
fi
cd "$DIR"
OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=disabled -Dicu=disabled"
[ -d build ] || meson setup build $OPTS
ninja -C build util/hb-shape util/hb-vector util/hb-info util/hb-subset
[ -d build-msg ] || CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1 meson setup build-msg $OPTS
ninja -C build-msg util/hb-shape
