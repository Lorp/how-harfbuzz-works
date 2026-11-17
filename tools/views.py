"""The different views of one GSUB lookup, all made from a compiled font.

Nothing here is written by hand: each view is read from the font (or from
the HarfBuzz source), so the views can't disagree with each other or with
what HarfBuzz is shown doing.

  spec_view(font_path, lookup_index)   the abstract, spec-like view
  ttx_view(font_path, lookup_index)    fontTools' TTX dump of the lookup
  hex_view(font_path, lookup_index)    the lookup's bytes, annotated
  fea_view(fea_path, block_name)       a feature or lookup block, from its source
  cpp_view(hb_src, struct_name)        HarfBuzz's struct for a subtable
"""
import os
import re
import struct
import subprocess
from fontTools.ttLib import TTFont

FLAG_NAMES = [
    (0x0001, "RightToLeft"), (0x0002, "IgnoreBaseGlyphs"),
    (0x0004, "IgnoreLigatures"), (0x0008, "IgnoreMarks"),
    (0x0010, "UseMarkFilteringSet"),
]
TYPE_NAMES = {
    1: "Single", 2: "Multiple", 3: "Alternate", 4: "Ligature",
    5: "Context", 6: "Chained context", 7: "Extension",
    8: "Reverse chained single",
}


def flags_text(flag, mark_set=None):
    names = [n for bit, n in FLAG_NAMES if flag & bit]
    if flag & 0xFF00:
        names.append(f"MarkAttachmentType {flag >> 8}")
    if mark_set is not None and flag & 0x0010:
        names[-1] += f" {mark_set}"
    return ", ".join(names) or "none"


def glyphs(names):
    return "[" + " ".join(names) + "]"


def spec_view(font_path, lookup_index):
    font = TTFont(font_path)
    order = font.getGlyphOrder()
    lookup = font["GSUB"].table.LookupList.Lookup[lookup_index]
    t = lookup.LookupType
    out = [f"Lookup {lookup_index}: {TYPE_NAMES[t]} substitution (type {t})",
           f"  lookupFlag: {flags_text(lookup.LookupFlag, getattr(lookup, 'MarkFilteringSet', None))}"]
    for n, st in enumerate(lookup.SubTable):
        if t == 7:
            st = st.ExtSubTable
        fmt = getattr(st, "Format", 1)
        name = {1: "SingleSubst", 2: "MultipleSubst", 3: "AlternateSubst",
                4: "LigatureSubst", 5: "ContextSubst", 6: "ChainContextSubst",
                8: "ReverseChainSingleSubst"}[st.LookupType if t == 7 else t]
        out.append(f"  subtable {n}: {name}Format{fmt}")
        if t == 1:
            cov = sorted(st.mapping, key=order.index)
            out.append(f"    coverage: {glyphs(cov)}")
            if fmt == 1:
                deltas = {order.index(st.mapping[g]) - order.index(g) for g in cov}
                (d,) = deltas
                out.append(f"    deltaGlyphID: {d:+d}")
                out.append("    (so: " + ", ".join(f"{g} → {st.mapping[g]}" for g in cov) + ")")
            else:
                out.append("    substitute: " + glyphs(st.mapping[g] for g in cov))
        elif t == 2:
            cov = sorted(st.mapping, key=order.index)
            out.append(f"    coverage: {glyphs(cov)}")
            out.append("    sequence:")
            for g in cov:
                out.append(f"      {g} → {' '.join(st.mapping[g]) or '(nothing)'}")
        elif t == 3:
            cov = sorted(st.alternates, key=order.index)
            out.append(f"    coverage: {glyphs(cov)}")
            out.append("    alternateSet:")
            for g in cov:
                out.append(f"      {g} → {glyphs(st.alternates[g])}")
        elif t == 4:
            cov = sorted(st.ligatures, key=order.index)
            out.append(f"    coverage: {glyphs(cov)}")
            out.append("    ligatureSet:")
            for g in cov:
                out.append(f"      ({g})")
                for i, lig in enumerate(st.ligatures[g], 1):
                    out.append(f"        {i}. {glyphs(lig.Component)} → {lig.LigGlyph}")
        elif t == 6 and fmt == 3:
            covs = lambda cs: " ".join(glyphs(c.glyphs) for c in cs) or "(none)"
            out.append(f"    backtrack: {covs(st.BacktrackCoverage)}")
            out.append(f"    input:     {covs(st.InputCoverage)}")
            out.append(f"    lookahead: {covs(st.LookAheadCoverage)}")
            for r in st.SubstLookupRecord:
                out.append(f"    lookupRecord: input[{r.SequenceIndex}] → lookup {r.LookupListIndex}")
        else:
            raise NotImplementedError(f"spec view of {name}Format{fmt}")
    return "\n".join(out)


def ttx_view(font_path, lookup_index):
    dump = subprocess.run(["ttx", "-q", "-o", "-", "-t", "GSUB", font_path],
                          check=True, capture_output=True, text=True).stdout
    m = re.search(rf'( *)<Lookup index="{lookup_index}">.*?</Lookup>\n', dump, re.S)
    indent = len(m.group(1))
    return "\n".join(line[indent:] for line in m.group(0).rstrip().split("\n"))


class Reader:
    """Reads fields from the GSUB bytes, noting where each one is."""
    def __init__(self, data):
        self.data, self.fields = data, []

    def u16(self, at, label):
        v = struct.unpack_from(">H", self.data, at)[0]
        self.fields.append((at, 2, label, v))
        return v

    def i16(self, at, label):
        v = struct.unpack_from(">h", self.data, at)[0]
        self.fields.append((at, 2, label, v))
        return v


def hex_view(font_path, lookup_index):
    """The bytes of one lookup and everything it points to, annotated.

    Offsets are shown relative to the start of the GSUB table. Only the
    lookup types this book shows in bytes are decoded.
    """
    font = TTFont(font_path)
    order = font.getGlyphOrder()
    data = font.reader["GSUB"]
    r = Reader(data)
    gname = lambda gid: order[gid] if gid < len(order) else f"#{gid}"

    lookup_list = struct.unpack_from(">H", data, 8)[0]
    lookup = lookup_list + struct.unpack_from(">H", data, lookup_list + 2 + 2 * lookup_index)[0]
    blocks = []  # (title, start) of each table, in the order met

    def coverage(at, title):
        blocks.append((title, at))
        fmt = r.u16(at, "format")
        if fmt == 1:
            n = r.u16(at + 2, "glyphCount")
            for i in range(n):
                g = struct.unpack_from(">H", data, at + 4 + 2 * i)[0]
                r.fields.append((at + 4 + 2 * i, 2, f"glyphArray[{i}] = {gname(g)}", g))
        else:
            n = r.u16(at + 2, "rangeCount")
            for i in range(n):
                p = at + 4 + 6 * i
                s, e = struct.unpack_from(">HH", data, p)
                r.fields.append((p, 2, f"rangeRecords[{i}].startGlyphID = {gname(s)}", s))
                r.fields.append((p + 2, 2, f"rangeRecords[{i}].endGlyphID = {gname(e)}", e))
                r.u16(p + 4, f"rangeRecords[{i}].startCoverageIndex")

    blocks.append((f"Lookup {lookup_index}", lookup))
    ltype = r.u16(lookup, "lookupType")
    flag = r.u16(lookup + 2, "lookupFlag")
    r.fields[-1] = r.fields[-1][:2] + (f"lookupFlag ({flags_text(flag)})", flag)
    nsub = r.u16(lookup + 4, "subTableCount")
    for s in range(nsub):
        off = r.u16(lookup + 6 + 2 * s, f"subtableOffsets[{s}] → subtable {s}")
        st = lookup + off
        if ltype != 4:
            raise NotImplementedError("hex view only decodes ligature lookups")
        blocks.append((f"subtable {s}: LigatureSubstFormat1", st))
        r.u16(st, "substFormat")
        cov = st + r.u16(st + 2, "coverageOffset → Coverage")
        nset = r.u16(st + 4, "ligatureSetCount")
        sets = [st + r.u16(st + 6 + 2 * i, f"ligatureSetOffsets[{i}] → LigatureSet {i}")
                for i in range(nset)]
        coverage(cov, "Coverage")
        for i, ls in enumerate(sets):
            blocks.append((f"LigatureSet {i}", ls))
            nlig = r.u16(ls, "ligatureCount")
            ligs = [ls + r.u16(ls + 2 + 2 * j, f"ligatureOffsets[{j}] → Ligature {i}.{j}")
                    for j in range(nlig)]
            for j, lg in enumerate(ligs):
                blocks.append((f"Ligature {i}.{j}", lg))
                g = struct.unpack_from(">H", data, lg)[0]
                r.fields.append((lg, 2, f"ligatureGlyph = {gname(g)}", g))
                nc = r.u16(lg + 2, "componentCount (including the first)")
                for k in range(nc - 1):
                    c = struct.unpack_from(">H", data, lg + 4 + 2 * k)[0]
                    r.fields.append((lg + 4 + 2 * k, 2, f"componentGlyphIDs[{k}] = {gname(c)}", c))

    # Print each table's fields, tables in the order they sit in the file.
    starts = sorted({b for _, b in blocks})
    titles = {}
    for title, at in blocks:
        titles.setdefault(at, title)
    out = []
    for at in starts:
        out.append(f"── {titles[at]} (at {at:#06x})")
        nxt = min([s for s in starts if s > at], default=len(data))
        for (p, size, label, _v) in sorted(f for f in r.fields if at <= f[0] < nxt):
            hexbytes = " ".join(f"{b:02x}" for b in data[p:p + size])
            out.append(f"{p:04x}  {hexbytes}   {label}")
    return "\n".join(out)


def fea_view(fea_path, name):
    src = open(fea_path).read()
    m = re.search(rf"^(feature|lookup) {re.escape(name)} \{{.*?^\}} {re.escape(name)};",
                  src, re.S | re.M)
    if not m:
        raise KeyError(f"no block {name} in {fea_path}")
    return m.group(0)


def cpp_view(hb_src, struct_name, tag):
    """A struct's fields, from the HarfBuzz source, with where it is."""
    for root, _, files in os.walk(hb_src):
        for f in files:
            if not f.endswith(".hh"):
                continue
            path = os.path.join(root, f)
            lines = open(path).read().split("\n")
            for i, line in enumerate(lines):
                if line.strip() == f"struct {struct_name}":
                    j = i
                    while "DEFINE_SIZE" not in lines[j]:
                        j += 1
                    start = i - 1 if lines[i - 1].startswith("template") else i
                    body = [l for l in lines[start:j + 1]]
                    rel = os.path.relpath(path, os.path.dirname(hb_src))
                    url = f"https://github.com/harfbuzz/harfbuzz/blob/{tag}/{rel}#L{start + 1}-L{j + 1}"
                    return "\n".join(body) + "\n  /* … */\n};", rel, start + 1, url
    raise KeyError(struct_name)


if __name__ == "__main__":
    import sys
    font, idx = sys.argv[1], int(sys.argv[2])
    print(spec_view(font, idx)); print()
    print(ttx_view(font, idx)); print()
    if TTFont(font)["GSUB"].table.LookupList.Lookup[idx].LookupType == 4:
        print(hex_view(font, idx))
