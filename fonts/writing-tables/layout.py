"""Prints where the objects of a GSUB table lie, for the chapter "Writing
tables": the LookupList, the Lookup tables, any Extension subtables, the
SingleSubst subtables and their Coverage tables, and the longest offset of
each width.

usage: python3 layout.py FONT.ttf ...

It reads the bytes with Python's struct module, not with HarfBuzz, and
knows only the lookup types these fonts use (1, and 7 wrapping 1).
"""
import struct
import sys

from fontTools.ttLib import TTFont


def layout(path):
    data = TTFont(path).reader["GSUB"]
    u16 = lambda at: struct.unpack_from(">H", data, at)[0]
    u32 = lambda at: struct.unpack_from(">L", data, at)[0]

    objects = {}   # start: (kind, size)
    offsets = []   # (width, distance, from kind, to kind, lookup index)

    lookup_list = u16(8)
    count = u16(lookup_list)
    objects[lookup_list] = ("LookupList", 2 + 2 * count)
    promoted = []
    for i in range(count):
        lookup = lookup_list + u16(lookup_list + 2 + 2 * i)
        offsets.append((16, lookup - lookup_list, "LookupList", "Lookup", i))
        kind, n = u16(lookup), u16(lookup + 4)
        objects[lookup] = ("Lookup", 6 + 2 * n)
        for s in range(n):
            sub = lookup + u16(lookup + 6 + 2 * s)
            if kind == 7:
                promoted.append(i)
                objects[sub] = ("Extension", 8)
                offsets.append((16, sub - lookup, "Lookup", "Extension", i))
                inner = sub + u32(sub + 4)
                offsets.append((32, inner - sub, "Extension", "SingleSubst", i))
                parent, sub = "Extension", inner
            else:
                offsets.append((16, sub - lookup, "Lookup", "SingleSubst", i))
            fmt = u16(sub)
            objects[sub] = ("SingleSubst", 6 if fmt == 1 else 6 + 2 * u16(sub + 4))
            cov = sub + u16(sub + 2)
            offsets.append((16, cov - sub, "SingleSubst", "Coverage", i))
            cfmt, cn = u16(cov), u16(cov + 2)
            objects[cov] = ("Coverage", 4 + (2 if cfmt == 1 else 6) * cn)

    print(f"{path}: GSUB, {len(data):,} bytes, {count} lookups")
    print(f"  {'kind':<12} {'count':>5}   {'first starts':>12}   {'last ends':>9}")
    for kind in ("LookupList", "Lookup", "Extension", "SingleSubst", "Coverage"):
        starts = sorted(at for at, (k, _) in objects.items() if k == kind)
        if not starts:
            continue
        end = max(at + objects[at][1] for at in starts)
        print(f"  {kind:<12} {len(starts):>5}   {starts[0]:>12,}   {end:>9,}")
    for width in (16, 32):
        mine = [o for o in offsets if o[0] == width]
        if mine:
            w, dist, a, b, i = max(mine, key=lambda o: o[1])
            print(f"  longest {width}-bit offset: {dist:,} ({a} to {b}, lookup {i};"
                  f" {len(mine)} offsets of this width)")
    if promoted:
        print(f"  Extension lookups: {len(promoted)} of {count}: "
              + " ".join(str(i) for i in promoted))


for p in sys.argv[1:]:
    layout(p)
