#!/bin/sh
# Fetches and builds the HarfBuzz version this book describes, twice:
#   build/      as released
#   build-msg/  with HB_BUFFER_MESSAGE_MORE, for the detailed traces
# into .cache/harfbuzz/ (or $HB_BUILD).
set -e
VERSION=$(python3 -c "import json;print(json.load(open('$(dirname "$0")/../book/book.json'))['harfbuzz'])")
DIR=${HB_BUILD:-$(dirname "$0")/../.cache/harfbuzz}
if [ ! -d "$DIR" ]; then
  git clone --depth 1 --branch "$VERSION" https://github.com/harfbuzz/harfbuzz.git "$DIR"
fi
cd "$DIR"
OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=disabled -Dicu=disabled"
[ -d build ] || meson setup build $OPTS
ninja -C build util/hb-shape
[ -d build-msg ] || CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1 meson setup build-msg $OPTS
ninja -C build-msg util/hb-shape
