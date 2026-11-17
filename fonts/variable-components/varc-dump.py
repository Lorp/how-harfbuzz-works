"""Decodes VARC from one of HarfBuzz's test fonts, for the chapter
"Variable components".

usage: python3 varc-dump.py FONT bytes GLYPH            a glyph's component records, byte by byte
       python3 varc-dump.py FONT walk GLYPH AXIS=V,...  how each component is placed, at a position
       python3 varc-dump.py FONT store OUTER:INNER      one item of the multiple item variation store

GLYPH is a glyph ID. Positions are user coordinates, normalized through
fvar (the test fonts have no avar) and rounded to 2.14, as HarfBuzz does.

This is not HarfBuzz. The component records are read byte by byte with
Python's struct module, in the order VarComponent::decompile_record
(src/OT/Var/VARC/VARC.cc) reads them, and with the field names it uses.
The variation store's regions and items are read by fontTools (4.68: older
versions can't read VARC). The walk repeats the arithmetic of
VarComponent::get_path_at and VARC::get_path_at; the chapter checks its
results against hb-vector's drawings.
"""
import math
import sys
sys.dont_write_bytecode = True
import struct
import sys

from fontTools.ttLib import TTFont

FLAGS = ["RESET_UNSPECIFIED_AXES", "HAVE_AXES", "AXIS_VALUES_HAVE_VARIATION",
         "TRANSFORM_HAS_VARIATION", "HAVE_TRANSLATE_X", "HAVE_TRANSLATE_Y",
         "HAVE_ROTATION", "HAVE_CONDITION", "HAVE_SCALE_X", "HAVE_SCALE_Y",
         "HAVE_TCENTER_X", "HAVE_TCENTER_Y", "GID_IS_24BIT", "HAVE_SKEW_X",
         "HAVE_SKEW_Y"]
BIT = {name: 1 << i for i, name in enumerate(FLAGS)}

# The transform fields, in the order they are stored, with the number of
# fraction bits of each (VARC_PROCESS_TRANSFORM_COMPONENTS).
TRANSFORM = [("translateX", 0, "HAVE_TRANSLATE_X"), ("translateY", 0, "HAVE_TRANSLATE_Y"),
             ("rotation", 12, "HAVE_ROTATION"), ("scaleX", 10, "HAVE_SCALE_X"),
             ("scaleY", 10, "HAVE_SCALE_Y"), ("skewX", 12, "HAVE_SKEW_X"),
             ("skewY", 12, "HAVE_SKEW_Y"), ("tCenterX", 0, "HAVE_TCENTER_X"),
             ("tCenterY", 0, "HAVE_TCENTER_Y")]


def varint(data, at):
    """An HBUINT32VAR: the first byte's leading 1 bits say how many follow."""
    b0 = data[at]
    if b0 < 0x80:
        return b0, 1
    if b0 < 0xC0:
        return ((b0 & 0x3F) << 8) | data[at + 1], 2
    if b0 < 0xE0:
        return ((b0 & 0x1F) << 16) | (data[at + 1] << 8) | data[at + 2], 3
    if b0 < 0xF0:
        return ((b0 & 0x0F) << 24) | (data[at + 1] << 16) | (data[at + 2] << 8) | data[at + 3], 4
    return struct.unpack_from(">I", data, at + 1)[0], 5


def tuple_values(data, at, count):
    """TupleValues: runs of zeros, bytes, words or longs, each with a control
    byte. Returns the values and a row for each run."""
    values, rows = [], []
    while len(values) < count:
        control = data[at]
        n = (control & 0x3F) + 1
        kind = control & 0xC0
        size, fmt, what = {0x80: (0, None, "zeros"), 0x00: (1, ">b", "bytes"),
                           0x40: (2, ">h", "words"), 0xC0: (4, ">i", "longs")}[kind]
        run = [0] * n if not size else [struct.unpack_from(fmt, data, at + 1 + i * size)[0] for i in range(n)]
        rows.append((at, 1, f"run of {n} {what}"))
        if size:
            rows.append((at + 1, n * size, ", ".join(str(v) for v in run)))
        values += run
        at += 1 + n * size
    return values, rows, at


def cff2_index(data, at):
    """A CFF2Index: a 32-bit count, an offset size, count + 1 offsets
    (counted from 1), then the data."""
    count = struct.unpack_from(">I", data, at)[0]
    if not count:
        return []
    off_size = data[at + 4]
    offs = [int.from_bytes(data[at + 5 + i * off_size:at + 5 + (i + 1) * off_size], "big")
            for i in range(count + 1)]
    base = at + 5 + (count + 1) * off_size - 1
    return [(base + offs[i], offs[i + 1] - offs[i]) for i in range(count)]


def coverage(data, at):
    fmt = struct.unpack_from(">H", data, at)[0]
    if fmt == 1:
        n = struct.unpack_from(">H", data, at + 2)[0]
        return list(struct.unpack_from(f">{n}H", data, at + 4))
    n = struct.unpack_from(">H", data, at + 2)[0]
    out = []
    for i in range(n):
        start, end, _ = struct.unpack_from(">HHH", data, at + 4 + 6 * i)
        out += range(start, end + 1)
    return out


class Varc:
    def __init__(self, path):
        self.font = TTFont(path)
        self.data = data = self.font.reader["VARC"]
        _, cov, _, _, axes, recs = struct.unpack_from(">IIIIII", data, 0)
        self.coverage = coverage(data, cov)
        self.axis_lists = cff2_index(data, axes)
        self.records = cff2_index(data, recs)
        self.store = self.font["VARC"].table.MultiVarStore
        self.axes = [a.axisTag for a in self.font["fvar"].axes] if "fvar" in self.font else []

    def axis_name(self, i):
        return self.axes[i] if i < len(self.axes) else f"axis {i}"

    def axis_indices(self, index):
        at, length = self.axis_lists[index]
        n = 0
        # Count the values first, as TupleValues::count_values does.
        p = at
        while p < at + length:
            c = self.data[p]
            k = (c & 0x3F) + 1
            n += k
            p += 1 + k * {0x80: 0, 0x00: 1, 0x40: 2, 0xC0: 4}[c & 0xC0]
        return tuple_values(self.data, at, n)[0]

    def decode(self, at, end):
        """One component record, as decompile_record reads it. Returns the
        fields and a row (offset, size, label) for each part of it."""
        d, rows, c = self.data, [], {"start": at}
        flags, n = varint(d, at)
        names = [f for f in FLAGS if flags & BIT[f]]
        rows.append((at, n, f"flags = {flags:#x}: " + ", ".join(names)))
        at += n
        if flags & BIT["GID_IS_24BIT"]:
            c["gid"] = int.from_bytes(d[at:at + 3], "big")
            rows.append((at, 3, f"gid = {c['gid']}")); at += 3
        else:
            c["gid"] = struct.unpack_from(">H", d, at)[0]
            rows.append((at, 2, f"gid = {c['gid']}")); at += 2
        c["flags"] = flags
        if flags & BIT["HAVE_CONDITION"]:
            c["condition"], n = varint(d, at)
            rows.append((at, n, f"conditionIndex = {c['condition']}")); at += n
        c["axes"], c["values"] = [], []
        if flags & BIT["HAVE_AXES"]:
            idx, n = varint(d, at)
            c["axes"] = self.axis_indices(idx)
            rows.append((at, n, f"axisIndicesIndex = {idx} → axes " +
                         ", ".join(self.axis_name(i) for i in c["axes"]))); at += n
            values, vrows, at = tuple_values(d, at, len(c["axes"]))
            c["values"] = values
            rows += [(o, s, "axisValues: " + label) for o, s, label in vrows]
        c["axis_var"] = c["transform_var"] = None
        if flags & BIT["AXIS_VALUES_HAVE_VARIATION"]:
            c["axis_var"], n = varint(d, at)
            rows.append((at, n, f"axisValuesVarIndex = {c['axis_var']}")); at += n
        if flags & BIT["TRANSFORM_HAS_VARIATION"]:
            c["transform_var"], n = varint(d, at)
            rows.append((at, n, f"transformVarIndex = {c['transform_var']}")); at += n
        c["transform"] = {}
        for name, shift, flag in TRANSFORM:
            if flags & BIT[flag]:
                v = struct.unpack_from(">h", d, at)[0]
                c["transform"][name] = v
                shown = f"{v}" if not shift else f"{v} = {v / (1 << shift):g}"
                rows.append((at, 2, f"{name} = {shown}")); at += 2
        c["size"] = at - c["start"]
        return c, rows

    def components(self, gid):
        if gid not in self.coverage:
            return None
        at, length = self.records[self.coverage.index(gid)]
        out, end = [], at + length
        while at < end:
            c, rows = self.decode(at, end)
            out.append((c, rows))
            at += c["size"]
        return out

    # The multiple item variation store.

    def region_scalar(self, region, coords):
        v = 1.0
        for ax in region.SparseVarRegionAxis:
            i = ax.AxisIndex
            coord = coords[i] if i < len(coords) else 0
            start, peak, end = (round(x * 16384) for x in (ax.StartCoord, ax.PeakCoord, ax.EndCoord))
            if peak == 0 or coord == peak:
                f = 1.0
            elif coord == 0:
                f = 0.0
            elif start > peak or peak > end or (start < 0 and end > 0):
                f = 1.0
            elif coord <= start or end <= coord:
                f = 0.0
            elif coord < peak:
                f = (coord - start) / (peak - start)
            else:
                f = (end - coord) / (end - peak)
            if f == 0:
                return 0.0
            v *= f
        return v

    def delta(self, index, coords, n):
        """The deltas for one item: n numbers. The item holds n numbers for
        each region, region by region (MultiVarData::get_delta)."""
        data = self.store.MultiVarData[index >> 16]
        item = data.Item[index & 0xFFFF]
        out, terms = [0.0] * n, []
        for r, region_index in enumerate(data.VarRegionIndex):
            s = self.region_scalar(self.store.SparseVarRegionList.Region[region_index], coords)
            row = item[r * n:(r + 1) * n]
            if s:
                for k in range(n):
                    out[k] += s * row[k]
            terms.append((region_index, s, row))
        return out, terms

    def region_text(self, region_index):
        region = self.store.SparseVarRegionList.Region[region_index]
        parts = [f"{self.axis_name(a.AxisIndex)} {a.StartCoord:g}…{a.PeakCoord:g}…{a.EndCoord:g}"
                 for a in region.SparseVarRegionAxis]
        return " × ".join(parts) or "everywhere"


def c_round(x):
    """C's round: halves away from zero (Python's round goes to even)."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def mul(a, b):
    """hb_transform_t::multiply: a then b, as cairo does."""
    axx, ayx, axy, ayy, ax0, ay0 = a
    bxx, byx, bxy, byy, bx0, by0 = b
    return (axx * bxx + axy * byx, ayx * bxx + ayy * byx,
            axx * bxy + axy * byy, ayx * bxy + ayy * byy,
            axx * bx0 + axy * by0 + ax0, ayx * bx0 + ayy * by0 + ay0)


def to_transform(t):
    """hb_transform_decomposed_t::to_transform (hb-geometry.hh)."""
    m = (1, 0, 0, 1, 0, 0)
    m = mul(m, (1, 0, 0, 1, t["translateX"] + t["tCenterX"], t["translateY"] + t["tCenterY"]))
    if t["rotation"]:
        c, s = math.cos(t["rotation"]), math.sin(t["rotation"])
        m = mul(m, (c, s, -s, c, 0, 0))
    m = mul(m, (t["scaleX"], 0, 0, t["scaleY"], 0, 0))
    if t["skewX"] or t["skewY"]:
        m = mul(m, (1, math.tan(t["skewY"]), math.tan(-t["skewX"]), 1, 0, 0))
    m = mul(m, (1, 0, 0, 1, -t["tCenterX"], -t["tCenterY"]))
    return m


def fmt_coords(v, coords):
    return ", ".join(f"{v.axis_name(i)} {c / 16384:.4g}" for i, c in enumerate(coords) if c) or "all 0"


def walk(v, gid, coords, font_coords, total, parent=None, depth=0, out=print):
    pad = "  " * depth
    comps = v.components(gid) if gid != parent else None
    if comps is None:
        xx, yx, xy, yy, x0, y0 = total
        out(f"{pad}leaf: glyph {gid}, drawn from glyf at: {fmt_coords(v, coords)}")
        out(f"{pad}      through the matrix ({xx:.4g}, {yx:.4g}, {xy:.4g}, {yy:.4g}) and offset ({x0:.4g}, {y0:.4g})")
        return
    out(f"{pad}glyph {gid}, at: {fmt_coords(v, coords)}")
    for k, (c, _) in enumerate(comps):
        flags = c["flags"]
        out(f"{pad}  component {k}: glyph {c['gid']}")
        if flags & BIT["HAVE_CONDITION"]:
            out(f"{pad}    condition {c['condition']} (not evaluated here)")
        values = [float(x) for x in c["values"]]
        if c["axis_var"] is not None:
            d, terms = v.delta(c["axis_var"], coords, len(values))
            for region_index, s, row in terms:
                if s and any(row):
                    out(f"{pad}    axis-value deltas, region {region_index} ({v.region_text(region_index)}), "
                        f"scalar {s:g}: {row}")
            values = [a + b for a, b in zip(values, d)]
        comp = list(font_coords if flags & BIT["RESET_UNSPECIFIED_AXES"] else coords)
        if c["axes"]:
            def shown(i, raw, val):
                if val == raw:
                    return f"{v.axis_name(i)} {raw}"
                sign = "+" if val > raw else "-"
                return f"{v.axis_name(i)} {raw} {sign} {abs(val - raw):g} = {val:g} → {c_round(val)}"
            out(f"{pad}    axis values (2.14): " + ", ".join(
                shown(i, raw, val) for i, raw, val in zip(c["axes"], c["values"], values)))
        for i, val in zip(c["axes"], values):
            while len(comp) <= i:
                comp.append(0)
            comp[i] = c_round(val)
        t = {name: 0.0 for name, _, _ in TRANSFORM}
        t["scaleX"] = t["scaleY"] = 1.0
        stored = [name for name, _, flag in TRANSFORM if flags & BIT[flag]]
        raw = {name: float(c["transform"][name]) for name in stored}
        if c["transform_var"] is not None:
            d, terms = v.delta(c["transform_var"], coords, len(stored))
            for region_index, s, row in terms:
                if s and any(row):
                    out(f"{pad}    transform deltas, region {region_index} ({v.region_text(region_index)}), "
                        f"scalar {s:g}: {row}")
            for name, dd in zip(stored, d):
                raw[name] += dd
        for name, shift, flag in TRANSFORM:
            if name in raw:
                t[name] = raw[name] / (1 << shift)
        if not flags & BIT["HAVE_SCALE_Y"]:
            t["scaleY"] = t["scaleX"]
        shown = {k: val for k, val in t.items() if k in raw or (k == "scaleY" and "scaleX" in raw)}
        if shown:
            out(f"{pad}    transform: " + ", ".join(
                f"{k} {val * 180:g}°" if k in ("rotation", "skewX", "skewY") else f"{k} {val:g}"
                for k, val in shown.items()))
        for k in ("rotation", "skewX", "skewY"):
            t[k] *= math.pi
        walk(v, c["gid"], comp, font_coords, mul(total, to_transform(t)), gid, depth + 2, out)


def normalize(v, spec):
    coords = [0] * len(v.axes)
    for part in filter(None, spec.split(",")):
        tag, val = part.split("=")
        val = float(val)
        for i, a in enumerate(v.font["fvar"].axes):
            if a.axisTag == tag:
                if val < a.defaultValue:
                    n = (val - a.defaultValue) / (a.defaultValue - a.minValue)
                elif val > a.defaultValue:
                    n = (val - a.defaultValue) / (a.maxValue - a.defaultValue)
                else:
                    n = 0
                coords[i] = c_round(max(-1, min(1, n)) * 16384)
    return coords


def main(path, what, arg, pos=""):
    v = Varc(path)
    if what == "bytes":
        gid = int(arg)
        for k, (c, rows) in enumerate(v.components(gid)):
            print(f"── glyph {gid}, component {k} (offsets from the start of VARC)")
            for at, size, label in rows:
                hexes = " ".join(f"{b:02x}" for b in v.data[at:at + size])
                print(f"{at:04x}  {hexes:<15} {label}")
    elif what == "walk":
        coords = normalize(v, pos)
        walk(v, int(arg), coords, coords, (1, 0, 0, 1, 0, 0))
    elif what == "store":
        outer, inner = (int(x) for x in arg.split(":"))
        data = v.store.MultiVarData[outer]
        item = data.Item[inner]
        n = len(item) // len(data.VarRegionIndex)
        print(f"── item {outer}:{inner} (VarIdx {outer << 16 | inner}): "
              f"{n} numbers for each of {len(data.VarRegionIndex)} regions")
        zeros = 0
        for r, region_index in enumerate(data.VarRegionIndex):
            row = item[r * n:(r + 1) * n]
            if not any(row):
                zeros += 1
                continue
            print(f"region {region_index} ({v.region_text(region_index)}): {row}")
        if zeros:
            print(f"(and {zeros} more region{'s' if zeros > 1 else ''}, all 0)")


if __name__ == "__main__":
    main(*sys.argv[1:])
