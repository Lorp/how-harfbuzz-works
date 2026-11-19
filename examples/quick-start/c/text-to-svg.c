/* Shape a line of text and draw it as SVG.
 * usage: text-to-svg FONT TEXT > out.svg */
#include <stdio.h>
#include <hb.h>
#include <hb-vector.h>

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
  hb_font_t *font = hb_font_create (face);

  /* Shape: characters in, positioned glyphs out. */
  hb_buffer_t *buf = hb_buffer_create ();
  hb_buffer_add_utf8 (buf, argv[2], -1, 0, -1);
  hb_buffer_guess_segment_properties (buf);   /* script, language, direction */
  hb_shape (font, buf, NULL, 0);

  unsigned count;
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &count);
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, &count);

  /* Draw each glyph at its pen position. */
  hb_vector_draw_t *draw = hb_vector_draw_create_or_fail (HB_VECTOR_FORMAT_SVG);
  float x = 0, y = 0;
  for (unsigned i = 0; i < count; i++)
  {
    hb_vector_draw_set_transform (draw, 1, 0, 0, 1,
                                  x + pos[i].x_offset, y + pos[i].y_offset);
    hb_vector_draw_glyph (draw, font, info[i].codepoint,
                          HB_VECTOR_EXTENTS_MODE_EXPAND);  /* grow the viewBox */
    x += pos[i].x_advance;
    y += pos[i].y_advance;
  }

  /* Write the SVG. */
  hb_blob_t *svg = hb_vector_draw_render (draw);
  unsigned length;
  const char *data = hb_blob_get_data (svg, &length);
  fwrite (data, 1, length, stdout);

  hb_blob_destroy (svg);
  hb_vector_draw_destroy (draw);
  hb_buffer_destroy (buf);
  hb_font_destroy (font);
  hb_face_destroy (face);
  hb_blob_destroy (blob);
  return 0;
}
