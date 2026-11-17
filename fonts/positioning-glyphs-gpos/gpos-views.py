"""Writes the views of every GPOS lookup in some fonts, read from the fonts.

usage: python3 gpos-views.py FONT.ttf ...

tools/font-views.py writes FONT.views.json for GSUB lookups only. This
script writes the same file in the same format for this chapter's fonts,
but with their GPOS lookups in it instead, so that `views` blocks can show
them: the spec-like view and the TTX view. (No bytes view: the GSUB one
decodes only ligature lookups.) The fonts' GSUB lookups are left out; no
block in the chapter shows them.

Like font-views.py, nothing here is written by hand: each view is read
from the compiled font.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "font_views", os.path.join(HERE, "..", "..", "tools", "font-views.py"))
font_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font_views)
flags_text, glyphs = font_views.flags_text, font_views.glyphs

TYPE_NAMES = {
    1: "Single adjustment", 2: "Pair adjustment", 3: "Cursive attachment",
    4: "Mark-to-base attachment", 5: "Mark-to-ligature attachment",
    6: "Mark-to-mark attachment", 7: "Context", 8: "Chained context",
    9: "Extension",
}
SUBTABLE_NAMES = {1: "SinglePos", 2: "PairPos", 3: "CursivePos", 4: "MarkBasePos",
                  5: "MarkLigPos", 6: "MarkMarkPos", 7: "ContextPos", 8: "ChainContextPos"}
# ValueFormat bits, with HarfBuzz's names for them (ValueFormat.hh)
VALUE_FIELDS = [(0x01, "XPlacement", "xPlacement"), (0x02, "YPlacement", "yPlacement"),
                (0x04, "XAdvance", "xAdvance"), (0x08, "YAdvance", "yAdvance"),
                (0x10, "XPlaDevice", "xPlaDevice"), (0x20, "YPlaDevice", "yPlaDevice"),
                (0x40, "XAdvDevice", "xAdvDevice"), (0x80, "YAdvDevice", "yAdvDevice")]


def format_text(fmt):
    return " ".join(hb for bit, _, hb in VALUE_FIELDS if fmt & bit) or "none"


def device_text(dev):
    if dev is None:
        return "NULL"
    if dev.DeltaFormat == 0x8000:
        return f"VariationIndex {dev.StartSize}:{dev.EndSize}"
    return f"Device {dev.StartSize}–{dev.EndSize} ppem {dev.DeltaValue}"


def value_text(fmt, v):
    if not fmt:
        return "(none)"
    parts = []
    for bit, tt, hb in VALUE_FIELDS:
        if fmt & bit:
            val = getattr(v, tt, None) if v is not None else None
            parts.append(f"{hb} {device_text(val) if bit >= 0x10 else (val or 0)}")
    return "<" + ", ".join(parts) + ">"


def anchor_text(a):
    if a is None:
        return "NULL"
    s = f"({a.XCoordinate}, {a.YCoordinate})"
    if a.Format == 2:
        s += f" point {a.AnchorPoint}"
    if a.Format == 3:
        s += f" x: {device_text(a.XDeviceTable)}, y: {device_text(a.YDeviceTable)}"
    return s


def coverage_list(cov, order):
    return sorted(cov.glyphs, key=order.index)


def classes_text(classdef, order, indent):
    by_class = {}
    for g, k in classdef.classDefs.items():
        by_class.setdefault(k, []).append(g)
    return [f"{indent}{k} = {glyphs(sorted(gs, key=order.index))}"
            for k, gs in sorted(by_class.items()) if k]


def spec_view(font, lookup_index):
    order = font.getGlyphOrder()
    lookup = font["GPOS"].table.LookupList.Lookup[lookup_index]
    t = lookup.LookupType
    out = [f"Lookup {lookup_index}: {TYPE_NAMES[t]} (type {t})",
           f"  lookupFlag: {flags_text(lookup.LookupFlag, getattr(lookup, 'MarkFilteringSet', None))}"]
    for n, st in enumerate(lookup.SubTable):
        if t == 9:
            st = st.ExtSubTable
        lt = st.LookupType if t == 9 else t
        fmt = st.Format
        out.append(f"  subtable {n}: {SUBTABLE_NAMES[lt]}Format{fmt}")
        if lt == 1:
            cov = coverage_list(st.Coverage, order)
            out.append(f"    coverage: {glyphs(cov)}")
            out.append(f"    valueFormat: {format_text(st.ValueFormat)}")
            if fmt == 1:
                out.append(f"    value: {value_text(st.ValueFormat, st.Value)}")
            else:
                for g, v in zip(cov, st.Value):
                    out.append(f"      {g}: {value_text(st.ValueFormat, v)}")
        elif lt == 2 and fmt == 1:
            cov = coverage_list(st.Coverage, order)
            out.append(f"    coverage: {glyphs(cov)}")
            out.append(f"    valueFormat[0]: {format_text(st.ValueFormat1)}")
            out.append(f"    valueFormat[1]: {format_text(st.ValueFormat2)}")
            out.append("    pairSet:")
            for g, ps in zip(st.Coverage.glyphs, st.PairSet):
                out.append(f"      ({g})")
                for r in ps.PairValueRecord:
                    v2 = f" {value_text(st.ValueFormat2, r.Value2)}" if st.ValueFormat2 else ""
                    out.append(f"        {r.SecondGlyph}: {value_text(st.ValueFormat1, r.Value1)}{v2}")
        elif lt == 2 and fmt == 2:
            out.append(f"    coverage: {glyphs(coverage_list(st.Coverage, order))}")
            out.append(f"    valueFormat1: {format_text(st.ValueFormat1)}")
            out.append(f"    valueFormat2: {format_text(st.ValueFormat2)}")
            out.append("    classDef1 (class 0: the rest of the coverage):")
            out += classes_text(st.ClassDef1, order, "      ")
            out.append("    classDef2 (class 0: every other glyph):")
            out += classes_text(st.ClassDef2, order, "      ")
            out.append(f"    values ({st.Class1Count} × {st.Class2Count}):")
            for i, row in enumerate(st.Class1Record):
                for j, rec in enumerate(row.Class2Record):
                    v2 = f" {value_text(st.ValueFormat2, rec.Value2)}" if st.ValueFormat2 else ""
                    out.append(f"      {i} × {j}: {value_text(st.ValueFormat1, rec.Value1)}{v2}")
        elif lt == 3:
            out.append(f"    coverage: {glyphs(coverage_list(st.Coverage, order))}")
            out.append("    entryExitRecord:")
            for g, r in zip(st.Coverage.glyphs, st.EntryExitRecord):
                out.append(f"      {g}: entry {anchor_text(r.EntryAnchor)}, exit {anchor_text(r.ExitAnchor)}")
        elif lt in (4, 5, 6):
            if lt == 6:
                marks, bases = st.Mark1Coverage, st.Mark2Coverage
                mark_array, base_records = st.Mark1Array, st.Mark2Array.Mark2Record
                names = ("mark1Coverage", "mark2Coverage", "mark1Array", "mark2Array")
            elif lt == 5:
                marks, bases = st.MarkCoverage, st.LigatureCoverage
                mark_array, base_records = st.MarkArray, st.LigatureArray.LigatureAttach
                names = ("markCoverage", "ligatureCoverage", "markArray", "ligatureArray")
            else:
                marks, bases = st.MarkCoverage, st.BaseCoverage
                mark_array, base_records = st.MarkArray, st.BaseArray.BaseRecord
                names = ("markCoverage", "baseCoverage", "markArray", "baseArray")
            out.append(f"    {names[0]}: {glyphs(coverage_list(marks, order))}")
            out.append(f"    {names[1]}: {glyphs(coverage_list(bases, order))}")
            out.append(f"    classCount: {st.ClassCount}")
            out.append(f"    {names[2]}:")
            for g, r in zip(marks.glyphs, mark_array.MarkRecord):
                out.append(f"      {g}: class {r.Class}, anchor {anchor_text(r.MarkAnchor)}")
            out.append(f"    {names[3]}:")
            for g, r in zip(bases.glyphs, base_records):
                if lt == 5:
                    out.append(f"      {g}:")
                    for c, comp in enumerate(r.ComponentRecord, 1):
                        anchors = ", ".join(anchor_text(a) for a in comp.LigatureAnchor)
                        out.append(f"        component {c}: [{anchors}]")
                else:
                    anchors = r.Mark2Anchor if lt == 6 else r.BaseAnchor
                    out.append(f"      {g}: [{', '.join(anchor_text(a) for a in anchors)}]")
        else:
            raise NotImplementedError(f"spec view of {SUBTABLE_NAMES[lt]}Format{fmt}")
    return "\n".join(out)


def ttx_dump(font_path):
    return subprocess.run([sys.executable, "-m", "fontTools.ttx", "-q", "-o", "-", "-t", "GPOS", font_path],
                          check=True, capture_output=True, text=True).stdout


def write_views(font_path):
    font = TTFont(font_path)
    dump = ttx_dump(font_path)
    lookups = {}
    for idx in range(len(font["GPOS"].table.LookupList.Lookup)):
        views = {"ttx": font_views.ttx_view(dump, idx)}
        try:
            views["spec"] = spec_view(font, idx)
        except NotImplementedError:
            pass
        lookups[str(idx)] = views
    with open(font_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    out = os.path.splitext(font_path)[0] + ".views.json"
    with open(out, "w") as f:
        json.dump({"font": os.path.basename(font_path), "sha256": digest,
                   "lookups": lookups, "tables": {}}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        write_views(path)
