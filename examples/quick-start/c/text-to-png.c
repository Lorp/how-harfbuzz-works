/* Shape a line of text and draw it as a PNG.
 * usage: text-to-png FONT TEXT PIXELS > out.png */
#include <stdio.h>
#include <stdlib.h>
#include <hb.h>
#include <hb-raster.h>

int main (int argc, char **argv)
{
  if (argc != 4) { fprintf (stderr, "usage: %s FONT TEXT PIXELS\n", argv[0]); return 1; }

  hb_blob_t *blob = hb_blob_create_from_file_or_fail (argv[1]);
  if (!blob) { fprintf (stderr, "can't read %s\n", argv[1]); return 1; }
  hb_face_t *face = hb_face_create (blob, 0);
  hb_font_t *font = hb_font_create (face);

  /* The size: one pixel is 64 units, so positions keep fractions of a pixel. */
  int size = atoi (argv[3]) * 64;
  hb_font_set_scale (font, size, size);

  hb_buffer_t *buf = hb_buffer_create ();
  hb_buffer_add_utf8 (buf, argv[2], -1, 0, -1);
  hb_buffer_guess_segment_properties (buf);
  hb_shape (font, buf, NULL, 0);

  unsigned count;
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &count);
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, &count);

  /* The image: as wide as the line, and as tall as the font's ascender
   * and descender, in whole pixels. */
  int width = 0;
  for (unsigned i = 0; i < count; i++) width += pos[i].x_advance;
  hb_font_extents_t line;
  hb_font_get_h_extents (font, &line);
  int bottom = (line.descender - 63) / 64, top = (line.ascender + 63) / 64;
  hb_raster_extents_t extents = {0, bottom, (width + 63) / 64, top - bottom, 0};

  /* Paint each glyph at its pen position, in black. */
  hb_raster_paint_t *paint = hb_raster_paint_create_or_fail ();
  hb_raster_paint_set_scale_factor (paint, 64, 64);   /* 64 units to the pixel */
  hb_raster_paint_set_extents (paint, &extents);
  hb_raster_paint_set_foreground (paint, HB_COLOR (0, 0, 0, 255));
  float x = 0, y = 0;
  for (unsigned i = 0; i < count; i++)
  {
    hb_raster_paint_set_transform (paint, 1, 0, 0, 1,
                                   x + pos[i].x_offset, y + pos[i].y_offset);
    hb_raster_paint_glyph (paint, font, info[i].codepoint);
    x += pos[i].x_advance;
    y += pos[i].y_advance;
  }

  /* Write the PNG. */
  hb_raster_image_t *image = hb_raster_paint_render (paint);
  hb_blob_t *png = hb_raster_image_serialize_to_png_or_fail (image);
  if (!png)
  {
    fprintf (stderr, "nothing to write\n");
    return 1;
  }
  unsigned length;
  const char *data = hb_blob_get_data (png, &length);
  fwrite (data, 1, length, stdout);

  hb_blob_destroy (png);
  hb_raster_image_destroy (image);
  hb_raster_paint_destroy (paint);
  hb_buffer_destroy (buf);
  hb_font_destroy (font);
  hb_face_destroy (face);
  hb_blob_destroy (blob);
  return 0;
}
