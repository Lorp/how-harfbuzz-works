#!/bin/sh
# Builds this chapter's test font, depend.ttf, from gsub/ligatures.ttf
# (see build-font.py). The chapter's graph and closures are not live
# blocks: run.sh makes them (graph.txt, closures.txt) with depend-graph.cc,
# which needs HarfBuzz compiled with HB_EXPERIMENTAL_API.
set -e
cd "$(dirname "$0")"
${PYTHON:-python3} build-font.py
