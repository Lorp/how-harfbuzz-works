#!/bin/sh
# Fetches and builds the HarfBuzz version this book describes, four times:
#   build/      as released: hb-shape, hb-vector (outlines as SVG, for the
#               `draw` blocks), hb-raster (PNG, for the `raster` blocks) and
#               hb-info (for the `info` blocks)
#   build-msg/  with HB_BUFFER_MESSAGE_MORE: hb-shape only, for the detailed traces
#   build-ft/   with FreeType: hb-raster, hb-shape and hb-ft-raster, for
#               examples that compare FreeType's (hinted) outlines and metrics
#   build-harfrust/  with the harfrust shaper (hb-shape --shapers=harfrust), for
#               comparing HarfRust with HarfBuzz. Cargo fetches the HarfRust
#               release src/rust/Cargo.toml names. Needs Rust nightly with
#               rust-src (rustup toolchain install nightly --component rust-src)
#               and bindgen (cargo install bindgen-cli); skipped without them
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
ninja -C build util/hb-shape util/hb-vector util/hb-info util/hb-subset util/hb-raster
[ -d build-msg ] || CXXFLAGS=-DHB_BUFFER_MESSAGE_MORE=1 meson setup build-msg $OPTS
ninja -C build-msg util/hb-shape
FT_OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=enabled -Dicu=disabled"
[ -d build-ft ] || meson setup build-ft $FT_OPTS
ninja -C build-ft util/hb-raster util/hb-shape util/hb-ft-raster
if command -v cargo >/dev/null && command -v bindgen >/dev/null &&
   cargo +nightly --version >/dev/null 2>&1; then
  HR_OPTS="-Dtests=disabled -Ddocs=disabled -Dcairo=disabled -Dfreetype=disabled -Dicu=disabled -Dharfrust=enabled"
  [ -d build-harfrust ] || RUSTUP_TOOLCHAIN=nightly meson setup build-harfrust $HR_OPTS
  RUSTUP_TOOLCHAIN=nightly ninja -C build-harfrust util/hb-shape
else
  echo "skipping build-harfrust/: it needs cargo, Rust nightly and bindgen" >&2
fi
