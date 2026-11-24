"""Build the test font for “Why shaping exists” with real outlines.

usage: python3 build-font.py FEATURES.fea OUT.ttf

The glyph names, cmap and layout tables are the book's own; the outlines and
advances are borrowed (tools/real_outlines.py) from Libre Baskerville for
Latin, Noto Naskh Arabic, and Noto Sans Devanagari, so the shaped output can
be drawn.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from real_outlines import Sources, build

SRC = Sources({
    "lat": "quick-start/LibreBaskerville.ttf",
    "ar": "sources/noto/NotoNaskhArabic-Regular.ttf",
    "dev": "sources/noto/NotoSansDevanagari-Regular.ttf",
})

# test glyph: (code point, source, [(source glyph, dx, dy)…], advance or None)
GLYPHS = {
    ".notdef": (None, "lat", [(".notdef", 0, 0)], None),
    "space": (0x20, "lat", [("space", 0, 0)], None),
    # Latin
    "a": (0x61, "lat", [("a", 0, 0)], None),
    "e": (0x65, "lat", [("e", 0, 0)], None),
    "f": (0x66, "lat", [("f", 0, 0)], None),
    "i": (0x69, "lat", [("i", 0, 0)], None),
    "aacute": (0xE1, "lat", [("aacute", 0, 0)], None),
    "acutecomb": (0x301, "lat", [("acutecomb", 0, 0)], None),
    "f_f": (None, "lat", [("f_f", 0, 0)], None),
    "f_i": (None, "lat", [("fi", 0, 0)], None),
    # Arabic. Noto Naskh draws beh as a dotless body (U+066E's glyphs) and a
    # separate dot, which its GPOS places; here each form is one glyph, the dot
    # where Noto puts it. Its lam-alef is two glyphs, joined here into one.
    "beh": (0x628, "ar", [("uni066E", 0, 0), ("dotbelowar", 308, -31)], None),
    "beh.init": (None, "ar", [("uni066E.init", 0, 0), ("dotbelowar", 70, -31)], None),
    "beh.medi": (None, "ar", [("uni066E.medi", 0, 0), ("dotbelowar", 90, -31)], None),
    "beh.fina": (None, "ar", [("uni066E.fina", 0, 0), ("dotbelowar", 338, -31)], None),
    "lam": (0x644, "ar", [("uni0644", 0, 0)], None),
    "lam.init": (None, "ar", [("uni0644.init", 0, 0)], None),
    "alef": (0x627, "ar", [("uni0627", 0, 0)], None),
    "alef.fina": (None, "ar", [("uni0627.fina", 0, 0)], None),
    "lam_alef": (None, "ar", [("uni0627.fina.rlig", 0, 0), ("uni0644.init.rlig", 300, 0)], 518),
    # Devanagari. Noto has vowel sign I in several widths, chosen by the
    # consonant after it; this font has one.
    "ka": (0x915, "dev", [("ka-deva", 0, 0)], None),
    "ssa": (0x937, "dev", [("ssa-deva", 0, 0)], None),
    "virama": (0x94D, "dev", [("halant-deva", 0, 0)], None),
    "iMatra": (0x93F, "dev", [("iMatra-deva.04", 0, 0)], None),
    "k_ssa": (None, "dev", [("k_ssa-deva", 0, 0)], None),
}

if __name__ == "__main__":
    build(SRC, GLYPHS, "HBBook Shaping Test", sys.argv[1], sys.argv[2])
