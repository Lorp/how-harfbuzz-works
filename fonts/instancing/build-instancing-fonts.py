"""Build the one source font of the Instancing chapter that fonts/variations
doesn't already have.

usage: python3 build-instancing-fonts.py OUT_DIR

  var-rvrn.ttf  the variations test font (tools/build-var-test-fonts.py),
                built the same way from the same masters, with one more
                glyph, I.serif: an I with slab serifs. An rvrn feature
                variation replaces I with I.serif from weight 600 up
                (normalized 0.4), the way a real font swaps a dollar sign's
                design at heavy weights.

Everything else in the chapter is cut from this font, or from the fonts in
fonts/variations, by HarfBuzz's hb-subset in build.sh.
"""
import importlib.util
import os
import sys
import tempfile

from fontTools import varLib
from fontTools.varLib.featureVars import addFeatureVariations

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "vartest", os.path.join(HERE, "..", "..", "tools", "build-var-test-fonts.py"))
vt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vt)

# One more glyph, after the others, with no character of its own.
vt.GLYPHS["I.serif"] = None
_draw = vt.draw


def draw(name, stem, width, lean):
    if name != "I.serif":
        return _draw(name, stem, width, lean)
    pen = vt.TTGlyphPen(None)
    serif = 60
    slab = round(stem * 0.5)
    left, right = vt.SB, vt.SB + 2 * serif + stem
    vt.rect(pen, left, 0, right, slab)                                  # foot
    vt.rect(pen, left + serif, slab, left + serif + stem, vt.CAP - slab)  # stem
    vt.rect(pen, left, vt.CAP - slab, right, vt.CAP)                    # head
    return pen.glyph(), right + vt.SB


vt.draw = draw


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        font = varLib.build(vt.designspace(tmp))[0]
        # rvrn is applied before every other feature, and HarfBuzz turns it
        # on by itself: the substitution needs nothing from the application.
        addFeatureVariations(font, [([{"wght": (0.4, 1.0)}], {"I": "I.serif"})],
                             featureTag="rvrn")
        path = os.path.join(out_dir, "var-rvrn.ttf")
        font.save(path)
        print(path)


if __name__ == "__main__":
    build(sys.argv[1])
