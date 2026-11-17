"""Builds modes.ttf, the Rendering chapter's test font.

It reuses the shapes, palette and helpers of the Colour chapter's builder
(fonts/colour/build-colour-fonts.py). Each letter is the same pair of
discs, a blue backdrop on the left and a red source on the right, joined
by a PaintComposite with one compositing mode:

    N  SRC_OVER     (the ordinary case, for comparison)
    I  SRC_IN       (only the part of the red disc over the blue one)
    O  DEST_OUT     (a blue crescent)
    X  XOR          (both discs, minus their overlap)
    P  PLUS         (the overlap is the sum of the two colours)
    S  SCREEN
    D  DIFFERENCE

Each letter also has the Colour chapter's fallback outline, a square with
one corner cut off.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "colour", os.path.join(HERE, "..", "colour", "build-colour-fonts.py"))
colour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colour)

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
    fb = colour.make_font(base, ["discL", "discR"], "Rendering Test Modes")
    font = fb.font
    paints = {g: colour.composite(m) for g, m in MODES.items()}
    clips = {g: (100, 0, 900, 800) for g in base}
    font["COLR"] = buildCOLR(paints, version=1, glyphMap=font.getReverseGlyphMap(),
                             clipBoxes=clips)
    font["CPAL"] = buildCPAL([colour.V1_PALETTE])
    font.save(out)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    modes(os.path.join(out, "modes.ttf"))


if __name__ == "__main__":
    main()
