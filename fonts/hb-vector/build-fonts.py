"""Builds modes.ttf, the hb-vector chapter’s test font.

It reuses the shapes, palette and helpers of the Color chapter's builder
(fonts/color/build-color-fonts.py). Each letter is the same pair of
discs, a blue backdrop on the left and a red source on the right, joined
by a PaintComposite with one compositing mode:

    N  SRC_OVER     (the ordinary case, for comparison)
    I  SRC_IN       (only the part of the red disc over the blue one)
    O  DEST_OUT     (a blue crescent)
    X  XOR          (both discs, minus their overlap)
    P  PLUS         (the overlap is the sum of the two colors)
    S  SCREEN
    D  DIFFERENCE

Each letter also has the Color chapter's fallback outline, a square with
one corner cut off.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "color", os.path.join(HERE, "..", "color", "build-color-fonts.py"))
color = importlib.util.module_from_spec(spec)
spec.loader.exec_module(color)

from fontTools.colorLib.builder import buildCOLR, buildCPAL  # noqa: E402

MODES = {
    "N": "src_over",
    "I": "src_in",
    "O": "dest_out",
    "X": "xor",
    "P": "plus",
    "S": "screen",
    "D": "difference",
}


def modes(out):
    base = list(MODES)
    fb = color.make_font(base, ["discL", "discR"], "hb-vector Test Modes")
    font = fb.font
    paints = {g: color.composite(m) for g, m in MODES.items()}
    clips = {g: (100, 0, 900, 800) for g in base}
    font["COLR"] = buildCOLR(paints, version=1, glyphMap=font.getReverseGlyphMap(),
                             clipBoxes=clips)
    font["CPAL"] = buildCPAL([color.V1_PALETTE])
    font.save(out)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    modes(os.path.join(out, "modes.ttf"))


if __name__ == "__main__":
    main()
