"""Build the test font for the chapter on shape plans and their cache.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

  featvar.ttf   variations/var.ttf with a GSUB table whose only feature is
                `rvrn`, and whose FeatureVariations table has two records,
                in normalized weight coordinates:

                  record 0: wght 0.6 to 1.0    (user 700 to 900): lookup 1, I -> V
                  record 1: wght 0.4 to 0.59   (user 600 to 695): lookup 0, I -> H

                Below user weight 600, no record applies and `rvrn` has no
                lookups, so I stays I. The swaps use glyphs the font already
                has: only their names matter, since they show which record
                HarfBuzz chose. fontTools' addFeatureVariations writes the
                lookups and the records, and chooses their order.
"""
from fontTools.ttLib import TTFont
from fontTools.varLib.featureVars import addFeatureVariations


def build_featvar():
    font = TTFont("../variations/var.ttf")
    addFeatureVariations(font, [
        ([{"wght": (0.4, 0.59)}], {"I": "H"}),
        ([{"wght": (0.6, 1.0)}], {"I": "V"}),
    ], featureTag="rvrn")
    font.save("featvar.ttf")


build_featvar()
