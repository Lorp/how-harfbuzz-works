/* Shape a line of text and print the glyphs, as hb-shape does.
 * usage: text-to-glyphs FONT TEXT */
#include <stdio.h>
#include <hb.h>

int main (int argc, char **argv)
{
  if (argc != 3)
  {
    fprintf (stderr, "usage: %s FONT TEXT\n", argv[0]);
    return 1;
  }

  /* Load the font: file → blob → face → font. */
  hb_blob_t *blob = hb_blob_create_from_file_or_fail (argv[1]);
  if (!blob)
  {
    fprintf (stderr, "can't read %s\n", argv[1]);
    return 1;
  }
  hb_face_t *face = hb_face_create (blob, 0);
  if (!hb_face_get_glyph_count (face))   /* not a font: HarfBuzz gives an empty face */
  {
    fprintf (stderr, "%s isn't a font\n", argv[1]);
    return 1;
  }
  hb_font_t *font = hb_font_create (face);

  /* Shape: characters in, positioned glyphs out. */
  hb_buffer_t *buf = hb_buffer_create ();
  hb_buffer_add_utf8 (buf, argv[2], -1, 0, -1);
  hb_buffer_guess_segment_properties (buf);   /* script, language, direction */
  hb_shape (font, buf, NULL, 0);

  unsigned count;
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &count);
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, &count);

  /* Print each glyph: name=cluster, @offset if it has one, +advance. */
  printf ("[");
  for (unsigned i = 0; i < count; i++)
  {
    char name[64];
    hb_font_glyph_to_string (font, info[i].codepoint, name, sizeof name);
    printf ("%s%s=%u", i ? "|" : "", name, info[i].cluster);
    if (pos[i].x_offset || pos[i].y_offset)
      printf ("@%d,%d", pos[i].x_offset, pos[i].y_offset);
    printf ("+%d", pos[i].x_advance);
  }
  printf ("]\n");

  hb_buffer_destroy (buf);
  hb_font_destroy (font);
  hb_face_destroy (face);
  hb_blob_destroy (blob);
  return 0;
}
