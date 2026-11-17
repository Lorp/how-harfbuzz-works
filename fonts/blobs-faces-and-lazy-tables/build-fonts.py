"""Build the test fonts for the chapter on blobs, faces and lazy tables.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every font here is made from fonts that other chapters already build, so
that nothing new has to be designed:

  pair.ttc         a TrueType Collection of two faces: gsub/ligatures.ttf
                   (face 0) and gsub/ccmp-first.ttf (face 1). fontTools
                   stores each table that is identical in both faces once,
                   so the two table directories point at the same bytes for
                   every table except GSUB and head.
  instances.ttf    variations/var.ttf with three named instances added to
                   its fvar table: Thin (wght 100), Bold (wght 700) and
                   Black (wght 900).
  broken-gsub.ttf  gsub/ligatures.ttf with one offset in its GSUB header
                   (the LookupList offset) pointing past the end of the
                   table. Every other byte is unchanged.
"""
import struct

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection
from fontTools.ttLib.tables._f_v_a_r import NamedInstance


def build_pair():
    ttc = TTCollection()
    ttc.fonts = [TTFont("../gsub/ligatures.ttf"), TTFont("../gsub/ccmp-first.ttf")]
    ttc.save("pair.ttc", shareTables=True)


def build_instances():
    font = TTFont("../variations/var.ttf")
    name = font["name"]
    for label, wght in (("Thin", 100), ("Bold", 700), ("Black", 900)):
        inst = NamedInstance()
        inst.subfamilyNameID = name.addMultilingualName({"en": label}, mac=False)
        inst.coordinates = {"wght": wght, "wdth": 100}
        font["fvar"].instances.append(inst)
    font.save("instances.ttf")


def build_broken_gsub():
    data = bytearray(open("../gsub/ligatures.ttf", "rb").read())
    num_tables = struct.unpack(">H", data[4:6])[0]
    for i in range(num_tables):
        rec = 12 + 16 * i
        tag, _, offset, length = struct.unpack(">4sLLL", data[rec:rec + 16])
        if tag == b"GSUB":
            # GSUB header: majorVersion, minorVersion, scriptList,
            # featureList, lookupList (all 16-bit). Point lookupList
            # far outside the table.
            struct.pack_into(">H", data, offset + 8, 0xFFF0)
            break
    else:
        raise SystemExit("no GSUB in ligatures.ttf")
    open("broken-gsub.ttf", "wb").write(bytes(data))


build_pair()
build_instances()
build_broken_gsub()
