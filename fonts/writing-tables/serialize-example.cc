/* The serializer example in the chapter "Writing tables": a root object A
 * with two 16-bit offsets, to B and to C, each of which has a 16-bit
 * offset to a one-byte object D. It is written with HarfBuzz's own
 * hb_serialize_context_t, into a 32-byte buffer, and prints where the
 * buffer's head and tail are after each step, then the bytes.
 *
 * hb-serialize.hh is internal to HarfBuzz, so this is built against the
 * source tree, not an installed library. From the repository's root:
 *
 *   H=.cache/harfbuzz
 *   c++ -std=c++11 -I$H/src \
 *       fonts/writing-tables/serialize-example.cc $H/src/harfbuzz.cc \
 *       -o serialize-example
 *   ./serialize-example > fonts/writing-tables/serialize-example.txt
 *
 * It isn't run when the book is built.
 */
#include "hb.hh"
#include "hb-serialize.hh"
#include "hb-open-type.hh"
#include <stdio.h>

using namespace OT;

struct Leaf  { HBUINT8 name; DEFINE_SIZE_STATIC (1); };
struct Child { HBUINT8 name; Offset16To<Leaf> leaf; DEFINE_SIZE_STATIC (3); };
struct Root  { HBUINT8 name; Offset16To<Child> child1, child2; DEFINE_SIZE_STATIC (5); };

static void show (hb_serialize_context_t &c, const char *what)
{
  printf ("%-22s head=%2d  tail=%2d\n", what,
	  (int) (c.head - c.start), (int) (c.tail - c.start));
}

int main ()
{
  char buf[32];
  hb_serialize_context_t c (buf, sizeof buf);

  Root *a = c.start_serialize<Root> ();
  c.extend_min (a);
  a->name = 'a';
  show (c, "A written");

  Child *b = c.push<Child> ();
  c.extend_min (b);
  b->name = 'b';
  show (c, "B written");

  Leaf *d = c.push<Leaf> ();
  c.extend_min (d);
  d->name = 'd';
  unsigned d_id = c.pop_pack ();
  show (c, "D packed");
  printf ("%22s object %u\n", "", d_id);

  c.add_link (b->leaf, d_id);
  unsigned b_id = c.pop_pack ();
  show (c, "B packed");
  printf ("%22s object %u\n", "", b_id);

  Child *cc = c.push<Child> ();
  c.extend_min (cc);
  cc->name = 'c';
  d = c.push<Leaf> ();
  c.extend_min (d);
  d->name = 'd';
  unsigned d2_id = c.pop_pack ();
  show (c, "second D packed");
  printf ("%22s object %u\n", "", d2_id);

  c.add_link (cc->leaf, d2_id);
  unsigned c_id = c.pop_pack ();
  show (c, "C packed");
  printf ("%22s object %u\n", "", c_id);

  c.add_link (a->child1, b_id);
  c.add_link (a->child2, c_id);
  c.end_serialize ();
  show (c, "end_serialize");

  hb_bytes_t out = c.copy_bytes ();
  printf ("%s, %u bytes:", c.in_error () ? "error" : "result", out.length);
  for (unsigned i = 0; i < out.length; i++)
    printf (" %02x", (unsigned char) out[i]);
  printf ("\n");
  hb_free ((void *) out.arrayZ);
  return 0;
}
