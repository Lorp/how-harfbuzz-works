/* depend-graph: prints a font's glyph dependency graph, or a closure
 * computed from it beside the subsetter's, using HarfBuzz's experimental
 * hb_subset_depend_* API. Written for the book, not part of HarfBuzz.
 *
 * usage: depend-graph FONT
 *        depend-graph FONT --closure TEXT [--no-context]
 *
 * The first form prints every glyph that has edges, in the format of
 * HarfBuzz's own util/hb-subset-depend (which our build doesn't make):
 *
 *   SOURCE (name):
 *     TABLE [FEATURE] -> DEPENDENT  [lig[N]]  [flags: C/N]  [(context)]
 *
 * The second maps TEXT to glyphs through cmap, follows the graph from them
 * (GSUB edges of the subsetter's default features, to a fixed point,
 * ligatures only once all their components are present, contexts only
 * when satisfied unless --no-context; then the other tables' edges), and
 * prints that set beside the glyphs hb_subset_plan_create_or_fail() keeps.
 *
 * Build: see run.sh. The API is compiled only with HB_EXPERIMENTAL_API, so
 * this is linked with HarfBuzz's amalgamated source built that way.
 */

#include <hb.h>
#include <hb-subset.h>

#include <stdio.h>
#include <string.h>
#include <string>

static hb_font_t *font;

static std::string
name (hb_codepoint_t gid)
{
  char buf[128];
  if (hb_font_get_glyph_name (font, gid, buf, sizeof (buf))) return buf;
  return std::to_string (gid);
}

static std::string
tag (hb_tag_t t)
{
  char buf[5] = {0};
  hb_tag_to_string (t, buf);
  std::string s (buf);
  while (!s.empty () && s.back () == ' ') s.pop_back ();
  return s;
}

/* "(a & (b|c))": direct glyphs, and sets of which any one will do. */
static std::string
context_str (hb_subset_depend_t *depend, hb_codepoint_t index)
{
  hb_set_t *set = hb_set_create (), *sub = hb_set_create ();
  hb_subset_depend_lookup_set (depend, index, set);
  std::string s = "(";
  hb_codepoint_t e = HB_SET_VALUE_INVALID;
  bool first = true;
  while (hb_set_next (set, &e))
  {
    if (!first) s += " & ";
    first = false;
    if (e < 0x80000000u) { s += name (e); continue; }
    hb_subset_depend_lookup_set (depend, e & 0x7FFFFFFFu, sub);
    s += "(";
    hb_codepoint_t g = HB_SET_VALUE_INVALID;
    bool f2 = true;
    while (hb_set_next (sub, &g)) { if (!f2) s += "|"; f2 = false; s += name (g); }
    s += ")";
  }
  hb_set_destroy (set); hb_set_destroy (sub);
  return s + ")";
}

static void
print_graph (hb_subset_depend_t *depend, unsigned num_glyphs)
{
  hb_set_t *seen = hb_set_create (), *lig = hb_set_create ();
  bool any = false;
  for (unsigned gid = 0; gid < num_glyphs; gid++)
  {
    unsigned total = hb_subset_depend_lookup_glyph (depend, gid, 0, nullptr, nullptr);
    if (!total) continue;
    printf ("%s%u (%s):\n", any ? "\n" : "", gid, name (gid).c_str ());
    any = true;
    for (unsigned i = 0; i < total; i++)
    {
      hb_subset_depend_entry_t e;
      unsigned count = 1;
      hb_subset_depend_lookup_glyph (depend, gid, i, &count, &e);
      std::string line = "  " + tag (e.table_tag);
      if (e.table_tag == HB_OT_TAG_GSUB) line += " " + tag (e.layout_tag);
      line += " -> " + name (e.dependent);
      if (e.ligature_set_index != HB_CODEPOINT_INVALID)
        line += "  lig[" + std::to_string (e.ligature_set_index) + "]";
      if (e.flags)
      {
        line += "  flags: ";
        if (e.flags & HB_SUBSET_DEPEND_EDGE_FLAG_FROM_CONTEXT_POSITION) line += "C";
        if (e.flags & HB_SUBSET_DEPEND_EDGE_FLAG_FROM_NESTED_CONTEXT) line += "N";
      }
      if (e.context_set_index != HB_CODEPOINT_INVALID)
        line += "  " + context_str (depend, e.context_set_index);
      printf ("%s\n", line.c_str ());
      if (e.ligature_set_index != HB_CODEPOINT_INVALID &&
          !hb_set_has (seen, e.ligature_set_index))
      {
        hb_set_add (seen, e.ligature_set_index);
        hb_subset_depend_lookup_set (depend, e.ligature_set_index, lig);
        printf ("    lig[%u]:", e.ligature_set_index);
        hb_codepoint_t g = HB_SET_VALUE_INVALID;
        while (hb_set_next (lig, &g)) printf (" %s", name (g).c_str ());
        printf ("\n");
      }
    }
  }
  hb_set_destroy (seen); hb_set_destroy (lig);
}

static bool
context_ok (hb_subset_depend_t *depend, hb_codepoint_t index, const hb_set_t *glyphs)
{
  hb_set_t *set = hb_set_create (), *sub = hb_set_create ();
  hb_subset_depend_lookup_set (depend, index, set);
  bool ok = true;
  hb_codepoint_t e = HB_SET_VALUE_INVALID;
  while (ok && hb_set_next (set, &e))
    if (e < 0x80000000u)
      ok = hb_set_has (glyphs, e);           /* this glyph must be present */
    else
    {
      hb_subset_depend_lookup_set (depend, e & 0x7FFFFFFFu, sub);
      ok = hb_set_intersects (sub, glyphs);  /* any one of these */
    }
  hb_set_destroy (set); hb_set_destroy (sub);
  return ok;
}

/* One pass over the edges of the glyphs in `glyphs` from the tables in
 * `tables`; returns whether anything was added. */
static bool
follow (hb_subset_depend_t *depend, hb_set_t *glyphs, const hb_set_t *tables,
        const hb_set_t *features, bool use_context)
{
  hb_set_t *add = hb_set_create (), *lig = hb_set_create ();
  hb_codepoint_t gid = HB_SET_VALUE_INVALID;
  while (hb_set_next (glyphs, &gid))
  {
    unsigned total = hb_subset_depend_lookup_glyph (depend, gid, 0, nullptr, nullptr);
    for (unsigned i = 0; i < total; i++)
    {
      hb_subset_depend_entry_t e;
      unsigned count = 1;
      hb_subset_depend_lookup_glyph (depend, gid, i, &count, &e);
      if (!hb_set_has (tables, e.table_tag)) continue;
      if (e.table_tag == HB_OT_TAG_GSUB && !hb_set_has (features, e.layout_tag)) continue;
      if (use_context && e.context_set_index != HB_CODEPOINT_INVALID &&
          !context_ok (depend, e.context_set_index, glyphs)) continue;
      if (e.ligature_set_index != HB_CODEPOINT_INVALID)
      {
        hb_subset_depend_lookup_set (depend, e.ligature_set_index, lig);
        if (!hb_set_is_subset (lig, glyphs)) continue;
      }
      hb_set_add (add, e.dependent);
    }
  }
  unsigned before = hb_set_get_population (glyphs);
  hb_set_union (glyphs, add);
  bool grew = hb_set_get_population (glyphs) > before;
  hb_set_destroy (add); hb_set_destroy (lig);
  return grew;
}

static void
print_set (const char *label, const hb_set_t *s)
{
  printf ("%s", label);
  hb_codepoint_t g = HB_SET_VALUE_INVALID;
  while (hb_set_next (s, &g)) printf (" %s", name (g).c_str ());
  printf ("\n");
}

static void
closure (hb_face_t *face, hb_subset_depend_t *depend, const char *text, bool use_context)
{
  hb_subset_input_t *input = hb_subset_input_create_or_fail ();
  hb_set_t *unicodes = hb_subset_input_unicode_set (input);
  for (const char *p = text; *p; )
  {
    /* Decode one UTF-8 character. */
    unsigned char c = *p;
    unsigned len = c < 0x80 ? 1 : c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
    hb_codepoint_t u = len == 1 ? c : c & (0x3F >> (len - 1));
    for (unsigned k = 1; k < len && p[k]; k++) u = (u << 6) | (p[k] & 0x3F);
    hb_set_add (unicodes, u);
    p += len;
  }

  /* From the graph: .notdef and the cmap glyphs, then GSUB to a fixed point,
   * then MATH once, then COLR, VARC and composites to a fixed point. */
  hb_set_t *glyphs = hb_set_create ();
  hb_set_add (glyphs, 0);
  hb_codepoint_t u = HB_SET_VALUE_INVALID, g;
  while (hb_set_next (unicodes, &u))
    if (hb_font_get_nominal_glyph (font, u, &g)) hb_set_add (glyphs, g);
  const hb_set_t *features = hb_subset_input_set (input, HB_SUBSET_SETS_LAYOUT_FEATURE_TAG);
  hb_set_t *tables = hb_set_create ();
  hb_set_add (tables, HB_OT_TAG_GSUB);
  while (follow (depend, glyphs, tables, features, use_context)) ;
  hb_set_clear (tables);
  hb_set_add (tables, HB_OT_TAG_MATH);
  follow (depend, glyphs, tables, features, use_context);
  hb_set_clear (tables);
  for (hb_tag_t t : {HB_TAG ('C','O','L','R'), HB_TAG ('V','A','R','C'),
                     HB_TAG ('g','l','y','f'), HB_TAG ('G','L','Y','F'),
                     HB_TAG ('C','F','F',' ')})
    hb_set_add (tables, t);
  while (follow (depend, glyphs, tables, features, use_context)) ;
  print_set ("from the graph:", glyphs);

  /* The subsetter's own closure: the glyphs its plan keeps. */
  hb_subset_plan_t *plan = hb_subset_plan_create_or_fail (face, input);
  hb_set_t *kept = hb_set_create ();
  const hb_map_t *map = hb_subset_plan_old_to_new_glyph_mapping (plan);
  int idx = -1;
  hb_codepoint_t old_gid, new_gid;
  while (hb_map_next (map, &idx, &old_gid, &new_gid)) hb_set_add (kept, old_gid);
  print_set ("the subsetter:", kept);

  hb_subset_plan_destroy (plan);
  hb_set_destroy (kept); hb_set_destroy (tables); hb_set_destroy (glyphs);
  hb_subset_input_destroy (input);
}

int
main (int argc, char **argv)
{
  if (argc < 2) { fprintf (stderr, "usage: %s FONT [--closure TEXT [--no-context]]\n", argv[0]); return 1; }
  hb_blob_t *blob = hb_blob_create_from_file_or_fail (argv[1]);
  if (!blob) { fprintf (stderr, "can't read %s\n", argv[1]); return 1; }
  hb_face_t *face = hb_face_create (blob, 0);
  font = hb_font_create (face);

  hb_subset_depend_t *depend = hb_subset_depend_from_face_or_fail (face);
  if (!depend) { fprintf (stderr, "failed to build the dependency graph\n"); return 1; }

  if (argc >= 4 && !strcmp (argv[2], "--closure"))
    closure (face, depend, argv[3], !(argc >= 5 && !strcmp (argv[4], "--no-context")));
  else
    print_graph (depend, hb_face_get_glyph_count (face));

  hb_subset_depend_destroy (depend);
  hb_font_destroy (font);
  hb_face_destroy (face);
  hb_blob_destroy (blob);
  return 0;
}
