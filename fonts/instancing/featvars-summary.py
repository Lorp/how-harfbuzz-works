"""Print each font's GSUB features and feature variations, briefly.

usage: python3 featvars-summary.py FONT.ttf ...

No HarfBuzz tool prints FeatureVariations, so build.sh writes this summary,
read by fontTools, for the chapter to quote.
"""
import sys

from fontTools.ttLib import TTFont


def lookups(feature):
    idx = feature.LookupListIndex
    return "lookup " + ", ".join(map(str, idx)) if idx else "no lookups"


def summary(path):
    font = TTFont(path)
    gsub = font["GSUB"].table
    axes = [a.axisTag for a in font["fvar"].axes] if "fvar" in font else []
    out = [path]
    for rec in gsub.FeatureList.FeatureRecord:
        out.append(f"  {rec.FeatureTag}: {lookups(rec.Feature)}")
    fv = getattr(gsub, "FeatureVariations", None)
    for i, rec in enumerate(fv.FeatureVariationRecord if fv else []):
        conds = rec.ConditionSet.ConditionTable if rec.ConditionSet else []
        when = ", ".join(f"{axes[c.AxisIndex]} {c.FilterRangeMinValue:g} to {c.FilterRangeMaxValue:g}"
                         for c in conds) or "always"
        for sub in rec.FeatureTableSubstitution.SubstitutionRecord:
            tag = gsub.FeatureList.FeatureRecord[sub.FeatureIndex].FeatureTag
            out.append(f"  record {i}, when {when}: {tag} -> {lookups(sub.Feature)}")
    return "\n".join(out)


print("\n".join(summary(p) for p in sys.argv[1:]))
