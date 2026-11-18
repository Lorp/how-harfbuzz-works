/* Prints the blobs that hb-gpu encodes, for the chapter "hb-gpu".
 *
 * usage: dump-gpu-blob FONT GLYPH [draw|paint]   one glyph's texels
 *        dump-gpu-blob FONT all [draw|paint]     every glyph's size
 *
 * GLYPH is a glyph name. "draw" (the default) encodes with hb_gpu_draw_t,
 * "paint" with hb_gpu_paint_t. Each texel is printed as its four signed
 * 16-bit components.
 *
 * The book's build doesn't run it. To build it against the book's HarfBuzz:
 *
 *   H=.cache/harfbuzz
 *   cc -o dump-gpu-blob fonts/hb-gpu/dump-gpu-blob.c -I$H/src -I$H/build/src \
 *      -L$H/build/src -lharfbuzz -lharfbuzz-gpu -Wl,-rpath,$PWD/$H/build/src
 */
#include <hb.h>
#include <hb-gpu.h>
#include <stdio.h>
#include <string.h>

static hb_blob_t *
encode (hb_font_t *font, hb_codepoint_t gid, int paint, hb_glyph_extents_t *ext)
{
  hb_blob_t *blob;
  if (paint)
  {
    hb_gpu_paint_t *p = hb_gpu_paint_create_or_fail ();
    hb_gpu_paint_glyph (p, font, gid);
    blob = hb_gpu_paint_encode (p, ext);
    hb_gpu_paint_destroy (p);
  }
  else
  {
    hb_gpu_draw_t *d = hb_gpu_draw_create_or_fail ();
    hb_gpu_draw_glyph (d, font, gid);
    blob = hb_gpu_draw_encode (d, ext);
    hb_gpu_draw_destroy (d);
  }
  return blob;
}

int
main (int argc, char **argv)
{
  if (argc < 3)
  {
    fprintf (stderr, "usage: %s FONT GLYPH|all [draw|paint]\n", argv[0]);
    return 1;
  }
  hb_blob_t *file = hb_blob_create_from_file_or_fail (argv[1]);
  if (!file)
  {
    fprintf (stderr, "can't read %s\n", argv[1]);
    return 1;
  }
  hb_face_t *face = hb_face_create (file, 0);
  hb_font_t *font = hb_font_create (face);
  int paint = argc > 3 && !strcmp (argv[3], "paint");
  int all = !strcmp (argv[2], "all");

  unsigned first = 0, count = hb_face_get_glyph_count (face);
  if (!all)
  {
    hb_codepoint_t gid;
    if (!hb_font_get_glyph_from_name (font, argv[2], -1, &gid))
    {
      fprintf (stderr, "no glyph named %s\n", argv[2]);
      return 1;
    }
    first = gid;
    count = gid + 1;
  }

  for (unsigned gid = first; gid < count; gid++)
  {
    char name[64];
    hb_font_get_glyph_name (font, gid, name, sizeof name);
    hb_glyph_extents_t ext;
    hb_blob_t *blob = encode (font, gid, paint, &ext);
    if (!blob)
    {
      printf ("%-10s NULL\n", name);
      continue;
    }
    unsigned len;
    const int16_t *t = (const int16_t *) hb_blob_get_data (blob, &len);
    if (all)
      printf ("%-10s %6u bytes %5u texels\n", name, len, len / 8);
    else
    {
      printf ("%s: %u bytes, %u texels\n", name, len, len / 8);
      for (unsigned i = 0; i < len / 8; i++)
	printf ("%3u: %6d %6d %6d %6d\n", i, t[4 * i], t[4 * i + 1], t[4 * i + 2], t[4 * i + 3]);
    }
    hb_blob_destroy (blob);
  }

  hb_font_destroy (font);
  hb_face_destroy (face);
  hb_blob_destroy (file);
  return 0;
}
