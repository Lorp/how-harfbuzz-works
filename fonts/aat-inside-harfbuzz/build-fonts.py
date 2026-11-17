"""Build the test fonts for “AAT inside HarfBuzz”.

usage: python3 build-fonts.py   (run from this folder; build.sh does)

Every glyph is a box, as in tools/build-test-font.py. The `morx` and `feat`
tables are written as fontTools TTX (XML) and compiled by fontTools, so the
state machines below are the font's own, and the views are read back from
the compiled fonts by morx-views.py.

Fonts written:
  latin.ttf         one `morx` chain of three subtables, and a `feat` table:
                    0  Ligature: f i -> f_i            flag 0x1, on by default
                    1  Contextual: a word-final e      flag 0x4, on by default
                       becomes e.fina (a substitution
                       of the marked glyph)
                    2  Noncontextual: a, e, e.fina     flag 0x2, off by default
                       -> small capitals
                    The chain's feature entries tie the flags to AAT
                    features: Ligatures (type 1), Contextual Alternatives
                    (type 36) and Lower Case (type 37).
  latin-nofeat.ttf  latin.ttf without its `feat` table
  latin-gsub.ttf    latin.ttf with a GSUB too, whose `ccmp` makes f l -> f_l
  deva.ttf          box glyphs for a few Devanagari characters, with no GSUB:
                    0  Ligature: ka virama ssa -> k_ssa
                    1  Insertion: a dotted circle before a vowel sign I
                       that has no consonant before it
                    2  Rearrangement: the vowel sign I moved before its
                       consonant or conjunct (verb 2, xD => Dx)
                    Every state of every subtable passes over a deleted
                    glyph (class 2), staying in the state it is in.
  deva-deleted.ttf  deva.ttf, but its Insertion and Rearrangement subtables
                    send a deleted glyph back to state 0, like a glyph of no
                    class
  loop.ttf          latin.ttf's glyphs, with a Contextual subtable whose
                    entries for `a` have SetMark and DontAdvance and stay in
                    state 0, a loop only the buffer's budget ends, then a
                    Noncontextual one: e -> e.sc
"""
import io
import os

from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.pens.ttGlyphPen import TTGlyphPen

DELETED, OOB = 2, 1   # reserved classes: 0 end of text, 1 out of bounds,
                      # 2 deleted glyph, 3 end of line


def box(width):
    pen = TTGlyphPen(None)
    if width:
        pen.moveTo((50, 0)); pen.lineTo((50, 500))
        pen.lineTo((width - 50, 500)); pen.lineTo((width - 50, 0))
        pen.closePath()
    return pen.glyph()


def base_font(glyphs, family):
    """glyphs: name -> (code point or None, advance width)."""
    order = list(glyphs)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp: g for g, (cp, _) in glyphs.items() if cp})
    fb.setupGlyf({g: box(0 if g == "space" else w) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalMetrics({g: (w, 50) for g, (_, w) in glyphs.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    return fb


# ---------------------------------------------------------------- morx XML

def transition_xml(kind, klass, t):
    """One transition. t: dict with 'to', 'flags' (list of names) and, by
    kind: 'verb'; 'mark', 'current' (lookup indices); 'actions' (glyph index
    deltas); 'marked_insert', 'current_insert' (glyph names)."""
    x = [f'<Transition onGlyphClass="{klass}">',
         f'<NewState value="{t.get("to", 0)}"/>']
    if t.get("flags"):
        x.append(f'<Flags value="{",".join(t["flags"])}"/>')
    if kind == "Rearrangement":
        x.append(f'<Verb value="{t.get("verb", 0)}"/>')
    elif kind == "Contextual":
        x.append(f'<MarkIndex value="{t.get("mark", 0xFFFF)}"/>')
        x.append(f'<CurrentIndex value="{t.get("current", 0xFFFF)}"/>')
    elif kind == "Ligature":
        x += [f'<Action GlyphIndexDelta="{d}"/>' for d in t.get("actions", [])]
    elif kind == "Insertion":
        x += [f'<MarkedInsertionAction glyph="{g}"/>' for g in t.get("marked_insert", [])]
        x += [f'<CurrentInsertionAction glyph="{g}"/>' for g in t.get("current_insert", [])]
    x.append("</Transition>")
    return "\n".join(x)


def state_table_xml(kind, classes, states, extra="", keep_deleted=True):
    """classes: glyph -> class (4 and up); states: list of dicts mapping a
    class to a transition (missing classes go to state 0, doing nothing).
    With keep_deleted, a deleted glyph (class 2) leaves every state as it
    is, unless a state says otherwise."""
    n = max(classes.values()) + 1
    x = ["<StateTable>"]
    x += [f'<GlyphClass glyph="{g}" value="{c}"/>' for g, c in classes.items()]
    for i, st in enumerate(states):
        if keep_deleted and DELETED not in st:
            st = {**st, DELETED: {"to": i}}
        x.append(f'<State index="{i}">')
        x += [transition_xml(kind, k, st.get(k, {})) for k in range(n)]
        x.append("</State>")
    x.append(extra)
    x.append("</StateTable>")
    return "\n".join(x)


def subtable_xml(i, kind, flags, body, direction="Any", order="LayoutOrder"):
    return (f'<MorphSubtable index="{i}">'
            f'<TextDirection value="{direction}"/>'
            f'<ProcessingOrder value="{order}"/>'
            f'<SubFeatureFlags value="0x{flags:08X}"/>'
            f'<{kind}Morph>{body}</{kind}Morph></MorphSubtable>')


def morx_xml(default_flags, features, subtables):
    """features: (type, setting, enable, disable) entries."""
    feats = "".join(
        f'<MorphFeature index="{i}"><FeatureType value="{t}"/>'
        f'<FeatureSetting value="{s}"/><EnableFlags value="0x{e:08X}"/>'
        f'<DisableFlags value="0x{d:08X}"/></MorphFeature>'
        for i, (t, s, e, d) in enumerate(features))
    return ('<ttFont><morx><Version value="2"/><Reserved value="0"/>'
            f'<MorphChain index="0"><DefaultFlags value="0x{default_flags:08X}"/>'
            f'{feats}{"".join(subtables)}</MorphChain></morx></ttFont>')


def feat_xml(features):
    """features: (type, name id, flags, [(setting, name id), ...])."""
    names = []
    for i, (t, nid, flags, settings) in enumerate(features):
        s = "".join(f'<Setting index="{j}"><SettingValue value="{v}"/>'
                    f'<SettingNameID value="{n}"/></Setting>'
                    for j, (v, n) in enumerate(settings))
        names.append(f'<FeatureName index="{i}"><FeatureType value="{t}"/>'
                     f'<Settings>{s}</Settings><FeatureFlags value="{flags}"/>'
                     f'<FeatureNameID value="{nid}"/></FeatureName>')
    return ('<ttFont><feat><Version value="0x00010000"/><FeatureNames>'
            '<Reserved1 value="0"/><Reserved2 value="0"/>'
            f'{"".join(names)}</FeatureNames></feat></ttFont>')


def import_xml(font, xml):
    font.importXML(io.BytesIO(xml.encode()))


ALL = 0xFFFFFFFF


# ---------------------------------------------------------------- latin

LATIN = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "a": (0x61, 500), "e": (0x65, 500), "f": (0x66, 500),
    "i": (0x69, 500), "l": (0x6C, 500),
    "a.sc": (None, 450), "e.sc": (None, 450), "e.fina": (None, 600),
    "f_i": (None, 900), "f_l": (None, 900),
}
LGID = {g: i for i, g in enumerate(LATIN)}


def latin_morx():
    # 0. Ligature: f i -> f_i. Each action pops one glyph and adds
    # component[glyph + delta] to the ligature index; both deltas land on
    # component 0 (value 0), so the index is 0: ligature[0], f_i.
    lig = state_table_xml("Ligature", {"f": 4, "i": 5}, [
        {4: {"to": 2, "flags": ["SetComponent"]}},          # 0 start of text
        {4: {"to": 2, "flags": ["SetComponent"]}},          # 1 start of line
        {4: {"to": 2, "flags": ["SetComponent"]},           # 2 after f
         5: {"to": 0, "flags": ["SetComponent"],
             "actions": [-LGID["i"], -LGID["f"]]}},
    ], '<LigComponents><LigComponent index="0" value="0"/></LigComponents>'
       '<Ligatures><Ligature glyph="f_i" index="0"/></Ligatures>')

    # 1. Contextual: mark each e; when the word ends (a glyph of no class,
    # such as the space, or the end of text) right after it, replace the
    # marked e by e.fina, through lookup 0.
    ctx = state_table_xml("Contextual", {"e": 4, "a": 5, "f": 5, "i": 5, "l": 5, "f_i": 5}, [
        {4: {"to": 2, "flags": ["SetMark"]}},
        {4: {"to": 2, "flags": ["SetMark"]}},
        {0: {"to": 0, "mark": 0},                           # 2 just after e
         OOB: {"to": 0, "mark": 0},
         4: {"to": 2, "flags": ["SetMark"]}},
    ], '<PerGlyphLookup index="0"><Lookup glyph="e" value="e.fina"/></PerGlyphLookup>')

    # 2. Noncontextual: small capitals.
    sc = ('<Substitution><Lookup glyph="a" value="a.sc"/><Lookup glyph="e" value="e.sc"/>'
          '<Lookup glyph="e.fina" value="e.sc"/></Substitution>')

    return morx_xml(0x1 | 0x4, [
        (1, 2, 0x1, ALL),            # Ligatures: Common Ligatures on
        (1, 3, 0x0, ALL & ~0x1),     #            Common Ligatures off
        (36, 0, 0x4, ALL),           # Contextual Alternatives on
        (36, 1, 0x0, ALL & ~0x4),    #                         off
        (37, 0, 0x0, ALL & ~0x2),    # Lower Case: Default
        (37, 1, 0x2, ALL),           #             Small Caps
    ], [subtable_xml(0, "Ligature", 0x1, lig),
        subtable_xml(1, "Contextual", 0x4, ctx),
        subtable_xml(2, "Noncontextual", 0x2, sc)])


LATIN_FEAT = feat_xml([
    (1, 256, 0, [(2, 257)]),                    # Ligatures: Common
    (36, 258, 0, [(0, 259)]),                   # Contextual Alternatives
    (37, 260, 0x8000, [(0, 261), (1, 262)]),    # Lower Case (exclusive)
])
LATIN_NAMES = {256: "Ligatures", 257: "Common Ligatures",
               258: "Contextual Alternates", 259: "Contextual Alternates",
               260: "Lower Case", 261: "Default Lower Case", 262: "Small Caps"}


def build_latin(out, feat=True, gsub=None):
    fb = base_font(LATIN, "HBBook AAT Latin")
    if feat:
        for nid, s in LATIN_NAMES.items():
            fb.font["name"].setName(s, nid, 3, 1, 0x409)
        import_xml(fb.font, LATIN_FEAT)
    import_xml(fb.font, latin_morx())
    if gsub:
        addOpenTypeFeatures(fb.font, gsub)
    fb.save(out)


# ---------------------------------------------------------------- loop

def build_loop(out):
    # In state 0, `a` marks itself and leads back to state 0 without
    # advancing: a machine that would never stop if nothing stopped it.
    # (Without SetMark, the entry would do nothing, and HarfBuzz would skip
    # the subtable: `a` couldn't start anything.)
    ctx = state_table_xml("Contextual", {"a": 4}, [
        {4: {"to": 0, "flags": ["SetMark", "DontAdvance"]}},
        {4: {"to": 0, "flags": ["SetMark", "DontAdvance"]}},
    ])
    # Then e -> e.sc, in a subtable after it.
    sc = '<Substitution><Lookup glyph="e" value="e.sc"/></Substitution>'
    fb = base_font(LATIN, "HBBook AAT Loop")
    import_xml(fb.font, morx_xml(0x1, [], [subtable_xml(0, "Contextual", 0x1, ctx),
                                           subtable_xml(1, "Noncontextual", 0x1, sc)]))
    fb.save(out)


# ---------------------------------------------------------------- deva

DEVA = {
    ".notdef": (None, 500), "space": (0x20, 250),
    "ka": (0x0915, 600), "ssa": (0x0937, 600), "virama": (0x094D, 300),
    "iMatra": (0x093F, 300), "dottedcircle": (0x25CC, 500),
    "k_ssa": (None, 800),
}
DGID = {g: i for i, g in enumerate(DEVA)}


def deva_morx(keep_deleted=True):
    # 0. Ligature: ka virama ssa -> k_ssa.
    lig = state_table_xml("Ligature", {"ka": 4, "virama": 5, "ssa": 6}, [
        {4: {"to": 2, "flags": ["SetComponent"]}},
        {4: {"to": 2, "flags": ["SetComponent"]}},
        {4: {"to": 2, "flags": ["SetComponent"]},           # 2 after ka
         5: {"to": 3, "flags": ["SetComponent"]}},
        {4: {"to": 2, "flags": ["SetComponent"]},           # 3 after ka virama
         6: {"to": 0, "flags": ["SetComponent"],
             "actions": [-DGID["ssa"], -DGID["virama"], -DGID["ka"]]}},
    ], '<LigComponents><LigComponent index="0" value="0"/></LigComponents>'
       '<Ligatures><Ligature glyph="k_ssa" index="0"/></Ligatures>')

    base = {"ka": 4, "ssa": 4, "k_ssa": 4, "dottedcircle": 4, "virama": 5, "iMatra": 6}

    # 1. Insertion: a vowel sign I with no consonant before it gets a
    # dotted circle inserted before it.
    no_base = {4: {"to": 2},
               6: {"to": 0, "flags": ["CurrentInsertBefore"],
                   "current_insert": ["dottedcircle"]}}
    ins = state_table_xml("Insertion", base, [
        no_base, no_base,
        {4: {"to": 2}, 5: {"to": 2}},                        # 2 after a consonant
    ], keep_deleted=keep_deleted)

    # 2. Rearrangement: mark the first consonant of a cluster, and when the
    # vowel sign I comes, mark it as the last glyph and apply verb 2,
    # xD => Dx, which moves it to the front.
    first = {4: {"to": 2, "flags": ["MarkFirst"]}}
    rea = state_table_xml("Rearrangement", base, [
        first, first,
        {4: {"to": 2, "flags": ["MarkFirst"]},               # 2 in a cluster
         5: {"to": 3},
         6: {"to": 0, "flags": ["MarkLast"], "verb": 2}},
        {4: {"to": 2}},                                       # 3 after a virama
    ], keep_deleted=keep_deleted)

    return morx_xml(0x7, [], [subtable_xml(0, "Ligature", 0x1, lig),
                              subtable_xml(1, "Insertion", 0x2, ins),
                              subtable_xml(2, "Rearrangement", 0x4, rea)])


def build_deva(out, keep_deleted=True):
    fb = base_font(DEVA, "HBBook AAT Devanagari")
    import_xml(fb.font, deva_morx(keep_deleted))
    fb.save(out)


if __name__ == "__main__":
    build_latin("latin.ttf")
    build_latin("latin-nofeat.ttf", feat=False)
    build_latin("latin-gsub.ttf", gsub="ccmp.fea")
    build_deva("deva.ttf")
    build_deva("deva-deleted.ttf", keep_deleted=False)
    build_loop("loop.ttf")
    for f in ("latin.ttf", "latin-nofeat.ttf", "latin-gsub.ttf", "deva.ttf", "deva-deleted.ttf", "loop.ttf"):
        print(os.path.abspath(f))
