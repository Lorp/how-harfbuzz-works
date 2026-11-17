"""Build the test fonts for “Joining scripts”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

  joining.ttf       joining.fea under DFLT, arab, syrc and mong: Arabic beh,
                    lam and alef, Syriac beth, lamadh, dalath, waw and
                    alaph (with fin2, fin3 and med2), Mongolian A with an
                    FVS1 variant, and calt and rlig lookups numbered so that
                    calt's comes first.
  joining-DFLT.ttf  the same lookups under DFLT alone.
  presentation.ttf  no GSUB, GPOS or GDEF: Arabic letters, and glyphs for
                    their presentation forms (U+FE8D... and U+FC60, U+FCCC,
                    U+FEFB, U+FEFC) in the cmap, named by code point.
  presentation-init.ttf
                    presentation.ttf with a GSUB whose only feature is init.
  win1256.ttf       no layout tables; 256 glyphs, with the Arabic letters
                    mapped to the glyph IDs of their Windows-1256 codes, as
                    in the legacy fonts HarfBuzz recognizes.
  pua.ttf           no layout tables; a symbol (3,0) cmap that maps only
                    Private Use code points of the legacy Traditional Arabic
                    encoding, and an OS/2 table of version 0 whose
                    fsSelection gives the Traditional Arabic font page.
  stch.ttf          stch.fea: Syriac letters and the abbreviation mark.

Glyphs are plain boxes, except the abbreviation mark's tiles in stch.ttf,
which are bars above the letters so that drawings show the stretch.
"""
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._c_m_a_p import cmap_format_4


def rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1))
    pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()


def box(width, mark=False):
    pen = TTGlyphPen(None)
    if mark:
        rect(pen, -250, 600, -150, 700)
    elif width:
        rect(pen, 50, 0, width - 50, 500)
    return pen.glyph()


def build(out, glyphs, fea=None, shapes=None, cmap=None):
    """glyphs: {name: (code point or None, advance)}; advance 0 is a mark.
    cmap: {code point: name}, if not the one glyphs gives."""
    shapes = shapes or {}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap(cmap if cmap is not None else
                         {cp: g for g, (cp, _) in glyphs.items() if cp})
    fb.setupGlyf({g: shapes[g] if g in shapes else
                  box(0 if g == "space" else w,
                      mark=(w == 0 and g not in ("space", ".notdef")))
                  for g, (_, w) in glyphs.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "HBBook Joining Test " + out[:-4], "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    if fea:
        addOpenTypeFeaturesFromString(fb.font, fea)
    return fb


JOINING = {
    ".notdef": (None, 500), "space": (0x20, 250),
    # Arabic
    "hamza": (0x621, 400), "alefMadda": (0x622, 300), "alef": (0x627, 300),
    "beh": (0x628, 600), "tatweel": (0x640, 200), "lam": (0x644, 500),
    "madda": (0x653, 0), "fatha": (0x64E, 0), "shadda": (0x651, 0),
    "hamzaabove": (0x654, 0),
    "beh.init": (None, 400), "beh.medi": (None, 400), "beh.fina": (None, 650),
    "lam.init": (None, 300), "lam.medi": (None, 300), "lam.fina": (None, 550),
    "alef.fina": (None, 350), "lam_alef": (None, 600), "lam_alef.fina": (None, 650),
    "lam_alef.calt": (None, 600),
    # Syriac
    "alaph": (0x710, 300), "beth": (0x712, 600), "dalath": (0x715, 450),
    "waw": (0x718, 450), "lamadh": (0x720, 450),
    "alaph.fina": (None, 350), "alaph.fin2": (None, 360), "alaph.fin3": (None, 370),
    "alaph.med2": (None, 380),
    "beth.init": (None, 450), "beth.medi": (None, 450), "beth.fina": (None, 650),
    "dalath.fina": (None, 500), "waw.fina": (None, 500),
    "lamadh.init": (None, 300), "lamadh.medi": (None, 300), "lamadh.fina": (None, 500),
    "lamadh_alaph": (None, 600), "lamadh_alaph.calt": (None, 600),
    # Mongolian
    "mongA": (0x1820, 500), "fvs1": (0x180B, 0), "mvs": (0x180E, 200),
    "nnbsp": (0x202F, 200),
    "mongA.init": (None, 450), "mongA.medi": (None, 400), "mongA.fina": (None, 550),
    "mongA.init.fvs1": (None, 460),
}

# Presentation forms, named by code point, each with the base letter.
PRESENTATION = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "alef": (0x627, 300), "beh": (0x628, 600), "lam": (0x644, 500), "meem": (0x645, 500),
    "fatha": (0x64E, 0), "shadda": (0x651, 0),
}
for cp, w in [(0xFE8D, 300), (0xFE8E, 350),                              # alef
              (0xFE8F, 600), (0xFE90, 650), (0xFE91, 400), (0xFE92, 400),  # beh
              (0xFEDD, 500), (0xFEDE, 550), (0xFEDF, 300), (0xFEE0, 300),  # lam
              (0xFEE1, 500), (0xFEE2, 550), (0xFEE3, 400), (0xFEE4, 400),  # meem
              (0xFEFB, 600), (0xFEFC, 650),                                # lam-alef
              (0xFCCC, 700), (0xFC60, 0)]:                                 # lam-meem, shadda-fatha
    PRESENTATION["uni%04X" % cp] = (cp, w)

# Windows-1256 positions of the letters HarfBuzz checks for, and a few more.
WIN1256 = {199: (0x627, "alef"), 200: (0x628, "beh"), 225: (0x644, "lam"),
           236: (0x649, "alefMaksura"), 237: (0x64A, "yeh"), 250: (0x652, "sukun")}

# Private Use code points of the legacy Traditional Arabic encoding
# (ArabicPUATraditional.txt in HarfBuzz's source).
PUA = {"alef": 0xF241, "alef.fina": 0xF242, "beh.init": 0xF249, "beh.medi": 0xF24A,
       "beh.fina": 0xF24B, "beh": 0xF24C, "lam.init": 0xF2BB, "lam.medi": 0xF2BC,
       "lam.fina": 0xF2BD, "lam": 0xF2BE, "lam_alef": 0xF2DC, "lam_alef.fina": 0xF2DD}

STCH = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "beth": (0x712, 500), "yudh": (0x71D, 250), "waw": (0x718, 500), "sam": (0x70F, 0),
    "sam.end": (None, 100), "sam.rep": (None, 200),
}


def stch_shapes():
    end = TTGlyphPen(None); rect(end, 0, 600, 100, 760)
    rep = TTGlyphPen(None); rect(rep, 0, 600, 200, 660)
    return {"sam.end": end.glyph(), "sam.rep": rep.glyph(), "sam": box(0)}


def main():
    fea = open("joining.fea").read()
    systems = "\n".join(f"languagesystem {s} dflt;" for s in ["DFLT", "arab", "syrc", "mong"])
    build("joining.ttf", JOINING, fea.replace("LANGUAGESYSTEMS", systems)).save("joining.ttf")
    build("joining-DFLT.ttf", JOINING,
          fea.replace("LANGUAGESYSTEMS", "languagesystem DFLT dflt;")).save("joining-DFLT.ttf")

    build("presentation.ttf", PRESENTATION).save("presentation.ttf")
    build("presentation-init.ttf", PRESENTATION, """
languagesystem DFLT dflt;
languagesystem arab dflt;
feature init { sub beh by uniFE91; } init;
""").save("presentation-init.ttf")

    order = {i: ("g%03d" % i) for i in range(256)}
    order[0] = ".notdef"
    for gid, (_, name) in WIN1256.items():
        order[gid] = name
    glyphs = {order[i]: (None, 0 if order[i] == "sukun" else 500) for i in range(256)}
    build("win1256.ttf", glyphs,
          cmap={cp: order[gid] for gid, (cp, _) in WIN1256.items()}).save("win1256.ttf")

    glyphs = {".notdef": (None, 500)}
    glyphs.update({name: (None, 500) for name in PUA})
    fb = build("pua.ttf", glyphs, cmap={})
    sub = cmap_format_4(4)
    sub.platformID, sub.platEncID, sub.language = 3, 0, 0
    sub.cmap = {cp: name for name, cp in PUA.items()}
    fb.font["cmap"].tables = [sub]
    os2 = fb.font["OS/2"]
    os2.version = 0
    os2.fsSelection = 0xB300 | 0x40   # Traditional Arabic font page; REGULAR
    fb.save("pua.ttf")

    build("stch.ttf", STCH, open("stch.fea").read(), shapes=stch_shapes()).save("stch.ttf")


main()
