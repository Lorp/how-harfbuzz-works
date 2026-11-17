#!/bin/sh
# Compiles depend-graph.cc and writes the outputs the chapter quotes.
#
# The hb_subset_depend_* API exists only when HarfBuzz is compiled with
# HB_EXPERIMENTAL_API (meson -Dexperimental_api=true), which the book's
# build in .cache/harfbuzz/build doesn't use: its libraries have the depend
# code but not the public functions, and the internal symbols the depend
# code needs are hidden. So this compiles HarfBuzz's own amalgamated source
# (src/harfbuzz-subset.cc, which holds all of libharfbuzz and
# libharfbuzz-subset, from the same checkout) with that macro into a private
# build directory, and links the program with it. Nothing in
# .cache/harfbuzz/build is touched. The compile takes about a minute.
#
# usage: sh run.sh   (OUT=dir to keep the build; default a temporary one)
set -e
cd "$(dirname "$0")"
SRC=${HB_BUILD:-../../.cache/harfbuzz}/src
OUT=${OUT:-$(mktemp -d)}
CXX=${CXX:-c++}
FLAGS="-std=c++17 -O1 -DHB_EXPERIMENTAL_API -I$SRC"
[ -f "$OUT/harfbuzz-subset.o" ] || $CXX $FLAGS -c "$SRC/harfbuzz-subset.cc" -o "$OUT/harfbuzz-subset.o"
$CXX $FLAGS depend-graph.cc "$OUT/harfbuzz-subset.o" -o "$OUT/depend-graph"
P=$OUT/depend-graph
$P depend.ttf > graph.txt
{
  for t in 'xe' ' e' 'á'; do
    echo "text \"$t\":"; $P depend.ttf --closure "$t"
  done
  echo "text \"xe\", contexts ignored:"; $P depend.ttf --closure 'xe' --no-context
} > closures.txt
