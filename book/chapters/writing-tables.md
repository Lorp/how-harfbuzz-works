# Writing tables

Every chapter so far has been about reading fonts. HarfBuzz also writes them. The subsetter writes a smaller copy of each table it keeps, the instancer writes tables with their variations pinned, the [face builder](blobs-faces-and-lazy-tables.html) writes a whole font file from a set of tables, and the Arabic shaper writes GSUB lookups of its own when a font has none ([Joining scripts](joining-scripts.html)). All of them write through one object, `hb_serialize_context_t`, the **serializer**.

Writing has two problems that reading doesn’t. A table is a tree of subtables joined by offsets, and an offset can’t be written until both ends have a place in the file. And most offsets are 16 bits, so every child must end up within 65,535 bytes of where its offset counts from. The serializer solves the first: a table’s code writes objects and the links between them, and the serializer lays them out, sharing identical objects, and fills the offsets in at the end. When an offset doesn’t fit, the **repacker** (`hb-repacker.hh` and `src/graph/`) looks for another layout, and changes the graph if it has to.

The examples use two test fonts made with fontTools, `forty.ttf` and `sixty.ttf`, and their subsets, made by `hb-subset` {{hb}} when the fonts were built. The `hb-info` listing and the shaping results were produced by running HarfBuzz on them when the page was built. The other listings were not: each says what made it.

## The head and the tail

A serializer is made over a buffer that someone else owns: `hb_serialize_context_t (buf, size)`. It keeps four pointers into it: `start` and `end`, the buffer’s bounds, and `head` and `tail`, the two ends of the free space between them. Writing at `head` is what the simplest code does. `allocate_size<Type> (size)` (`hb-serialize.hh:666`) hands out the next `size` bytes, zeroed, and moves `head` on. There is no growing: if the bytes aren’t there, it returns `nullptr` and records an error.

A table writer rarely calls `allocate_size` itself. The idiom, all through HarfBuzz’s table code, is to take a pointer to where the struct will start and then extend it:

```c++
auto *out = c->start_embed (*this);
if (unlikely (!c->extend_min (out))) return_trace (false);
out->format = format;
```

`start_embed` is just `head`, cast to the struct’s type. `extend_min` (`:757`) allocates the struct’s fixed part, its `min_size`; `extend` and `extend_size` (`:740`–`766`) allocate a size the struct works out or the caller gives. The struct sits on the buffer’s bytes, so writing its fields, in the big-endian types of [Fonts as bytes](fonts-as-bytes.html#numbers), is writing the table. Arrays fill themselves from an iterator (`ArrayOf::serialize (c, items)`). `embed` copies an object’s bytes as they are, and `copy` (`:724`) calls the object’s own `copy` method if it has one.

This is all a table without offsets needs. The face builder’s font file is written this way (`hb-face-builder.cc:120`, `hb-open-file.hh:123`): the 12-byte header, the table directory, then each table’s bytes, 4-byte aligned, with each directory record’s offset worked out from where the table landed. That offset is set with `check_assign` (`:277`), which assigns a value and checks it survived the narrowing:

```c++
if (unlikely (!c->check_assign (rec.offset,
                                (unsigned) ((char *) start - (char *) this),
                                HB_SERIALIZE_ERROR_OFFSET_OVERFLOW)))
  return_trace (false);
```

## Objects and links

Most tables have offsets, and for those the serializer uses the other end of the buffer too. The bytes between `start` and `head` are a stack of objects being written; the bytes between `tail` and `end` are a stack of finished ones, growing down from the end.

An **object** is a contiguous run of bytes holding zero or more offsets. `push` starts one at `head`, on top of whatever object was being written before. When the object is complete, `pop_pack` (`hb-serialize.hh:370`) moves its bytes from the head side to the tail side, rewinds `head` to where the object began, and returns the object’s **object index**, its place in the stack of packed objects, counting from 1 (object 0 is the nil object, meaning “nothing”). `pop_discard` drops an object instead, as if it had never been started.

An offset to an object can only be written after the object is packed, since only then does it have an index. The parent doesn’t write a number into its offset field: it calls `add_link (field, objidx)` (`:533`), which records a **link** on the parent: where in the parent the field is, how wide it is (the size of the field’s type: 2, 3 or 4 bytes), whether it is signed, and which object it points to. The field itself stays zero. Only `end_serialize` (`:300`), once the root object is packed, works out every offset, in `resolve_links` (`:577`).

What an offset counts from varies between tables, as [Fonts as bytes](fonts-as-bytes.html#offsets-that-know-their-targets) explains, so a link also has a **whence**: what its offset is relative to.

| `whence` | Offset counts from | Used by |
|---|---|---|
| `Head` (the default) | the start of the parent object | nearly everything |
| `Tail` | the end of the parent object | the `name` table, whose string offsets count from the string storage after the records (`OT/name/name.hh:199`) |
| `Absolute` | the start of the buffer, which is the start of the table | CFF, whose offsets in DICTs count from the start of the CFF table (`hb-subset-cff-common.hh:307`) |

A link can also have a **bias**, subtracted from the offset, for a field whose base is not the start of the object being written but somewhere inside it. In GDEF, a CaretValue’s Device-table offset counts from the CaretValue, and when the CaretValue is part of a larger object, `to_bias` (`:568`) gives the distance between the two (`OT/Layout/GDEF/GDEF.hh:227`).

`hb-open-type.hh` wraps the push–write–pack–link sequence into methods on `OffsetTo` itself. Here is the one subsetting uses most, trimmed (`hb-open-type.hh:450`):

```c++
bool serialize_subset (hb_subset_context_t *c, const OffsetTo& src,
                       const Base *src_base, Ts&&... ds)
{
  *this = 0;
  if (src.is_null ())
    return false;

  auto *s = c->serializer;
  s->push ();
  bool ret = c->dispatch (src_base+src, std::forward<Ts> (ds)...);
  if (ret || !has_null)
    s->add_link (*this, s->pop_pack ());
  else
    s->pop_discard ();
  return ret;
}
```

Called on an offset field in the new table, it follows the same offset in the old one, has the subset context write the target’s subset as a new object, and links the field to it; if that subset is empty, the object is discarded and the offset stays null. `serialize_serialize` (`:473`) does the same around a struct’s `serialize` method, for building a table from data, and `serialize_copy` (`:493`) around `copy`. What each table’s `subset` method keeps is the subject of [Subsetting](subsetting.html); this chapter is about how it writes it.

### A small graph, packed

Here is the smallest graph that shows everything: a root A with two 16-bit offsets, to B and to C, which each have a 16-bit offset to a one-byte object D. The code that writes it, in `fonts/writing-tables/serialize-example.cc`, uses three structs of 5, 3 and 1 bytes and a 32-byte buffer. It writes A, then B; then D, which it packs; it links B to D and packs B; then C, and D again; then it links A’s two offsets and calls `end_serialize`. After each step it printed where `head` and `tail` were:

```
A written              head= 5  tail=32
B written              head= 8  tail=32
D packed               head= 8  tail=31
                       object 1
B packed               head= 5  tail=28
                       object 2
second D packed        head= 8  tail=28
                       object 1
C packed               head= 5  tail=25
                       object 3
end_serialize          head= 0  tail=20
result, 12 bytes: 61 00 08 00 05 63 00 06 62 00 03 64
```

(Output of `serialize-example.cc`, compiled against the HarfBuzz {{hb}} source; it isn’t run when the book is built.)

While B is being written, A is still open below it. Packing D moves its byte to the end of the buffer, and packing B moves B’s three bytes in front of it; each time `head` goes back, so the next object reuses the space. The second D is never stored: `pop_pack` finds an identical object already packed and returns its index, 1, so B and C share one D. Finally `end_serialize` packs A and resolves the four links. The 12 bytes, annotated by hand:

```
 at   bytes            object   offsets
  0   61 00 08 00 05   A        child1 = 8 → B,  child2 = 5 → C
  5   63 00 06         C        leaf = 6, so 5 + 6 = 11 → D
  8   62 00 03         B        leaf = 3, so 8 + 3 = 11 → D
 11   64               D
```

Packed objects pile up backwards from the end, so in the finished table every parent comes before its children, and of two siblings, the one written later comes first: C sits between A and B. Here nobody chose the layout. It fell out of the order the code wrote things in, and that matters for the rest of this chapter.

### Sharing

**Sharing**, or deduplication, is automatic: `pop_pack` returns the index of an identical object if one is already packed. Identical means the same bytes and the same links, to the same objects at the same positions (`hb-serialize.hh:124`). The serializer keeps a hash map from packed objects to their indices, `packed_map`, and hashes at most the first 128 bytes of an object, with its links (`:133`); a longer object that hashes the same is told apart by the full comparison. Because a link is to an object index, and children are packed before parents, equality propagates upwards: two LigatureSets whose Ligatures were shared are themselves identical, and are shared in turn.

`pop_pack (false)` packs without trying to share. The root is always packed that way, and so are objects not worth hashing, such as CFF’s CharStrings (`hb-subset-cff1.cc:906`), which `start_zerocopy` (`:646`) even lets the code write straight onto the tail side.

### Order on request

Sometimes the order the code writes things in isn’t enough, and a table needs a guarantee. A **virtual link**, added by `add_virtual_link` (`:487`), is a link with no offset field. It is never written to the font, and it doesn’t count when objects are compared for sharing (`:126`), but it tells the repacker that its target must come after its source, whatever else it moves.

LigatureSubst is the example (`OT/Layout/GSUB/LigatureSubstFormat1.hh:166`). Because of a bug in some versions of Windows 7, a comment says, its Coverage table must come after its LigatureSets and Ligatures. So `subset` packs the new Coverage table *first*, which puts it at the end, then writes the LigatureSets, and every LigatureSet and Ligature it keeps adds a virtual link to the Coverage table (`OT/Layout/GSUB/Ligature.hh:216`), so the repacker can’t move it in front of them.

## When writing fails

The serializer has no exceptions to throw. It keeps a set of error flags (`hb-serialize.hh:45`):

| Flag | Set when |
|---|---|
| `HB_SERIALIZE_ERROR_OTHER` | an allocation fails, or something else unrecoverable happens |
| `HB_SERIALIZE_ERROR_OFFSET_OVERFLOW` | an offset doesn’t fit its field |
| `HB_SERIALIZE_ERROR_OUT_OF_ROOM` | the buffer is full |
| `HB_SERIALIZE_ERROR_INT_OVERFLOW` | a value doesn’t fit its field (`check_assign`, used for counts, glyph IDs, coordinates) |
| `HB_SERIALIZE_ERROR_ARRAY_OVERFLOW` | an array has more items than its count field can hold |

`err` sets a flag and returns false. Once any flag is set, nearly every method does nothing: `allocate_size` returns `nullptr`, `add_link` and `resolve_links` return at once. Table code checks results where it must and otherwise carries on, and the caller looks at the flags at the end. After a pure overflow (`only_overflow()`, `:231`), though, `push`, `pop_pack` and `pop_discard` keep working, so every push is still matched by its pop.

`snapshot()` and `revert (snap)` (`:437`) roll the serializer back, errors and all. The cmap subsetter uses them when a format 4 subtable overflows, and writes the table again without one (`hb-ot-cmap-table.hh:1965`).

The subsetter starts each table in a buffer of a guessed size (`hb-subset-table.hh:73`): the source table’s size, scaled by the square root of the fraction of glyphs kept (or unscaled, for GSUB, GPOS, GDEF and `name`), plus 8 KB. When a table runs out of room, it doubles the buffer and starts the table again, up to 256 times the size of the source table (`:61`). That is usually generous, but not always. A font tried while making this chapter had a 72-byte GSUB, one SingleSubst format 1 over 20,000 glyphs; subset like the fonts below, it outgrew its first buffer of 8 KB, the next would have passed 256 × 72 = 18,432 bytes, and `hb-subset` failed.

The flag that leads to the rest of this chapter is `OFFSET_OVERFLOW`. `resolve_links` sets it when a link’s offset doesn’t fit, through `check_assign`. The subsetter sends a table to the repacker only when that flag is the only one set (`hb-subset-table.hh:172`, `:116`). An overflow found before the links are resolved, as in the font-file writer above, is beyond the repacker’s help: `end_serialize` turns it into `OTHER` (`hb-serialize.hh:313`).

## Offsets that don’t fit

A GSUB table points from its LookupList to each Lookup, from each Lookup to its subtables and from each subtable to its Coverage and other tables, nearly all with 16-bit offsets. Large fonts have GSUB and GPOS tables far bigger than 64 KB, and the [Extension](gsub.html#extension) lookup type exists only so that some offsets can be 32 bits. Whether a table fits is a matter of layout: the same objects in one order can have every offset under 65,536, and in another not.

The serializer’s layout is the order the table’s code wrote things in, reversed. A LookupList is written lookup by lookup, each with its whole subtree, so lookup 0 and everything under it are packed first and end up at the end of the table. The LookupList’s offset to lookup 0 then spans nearly the whole table. (That is read from the code; the last listing on this page shows it in a table small enough to keep the serializer’s layout.) So, by our reading, any GSUB much over 64 KB overflows in the serializer’s own order, whether or not a better order exists.

Here is a case. `forty.ttf` has 1,500 glyphs and 40 lookups, each mapping every glyph to one a fixed number of places further on, so each is a SingleSubst format 1: one glyph-ID difference and a one-range Coverage table. The subset keeps every character except those whose glyph number is a multiple of 5 or 7, without layout closure. With glyphs missing from between the others, one difference no longer works for most lookups, so they become SingleSubst format 2, listing every substitute, with Coverage tables that list glyphs. GSUB grows sixty-fold:

```info
forty.ttf  --list-tables
forty-subset.ttf  --list-tables
```

`hb-subset` printed this about it, when built with `HB_DEBUG_SUBSET` and `HB_DEBUG_SUBSET_REPACK`:

```
OT::GSUB initial estimated table size: 9824 bytes.
OT::GSUB ran out of room; reallocating to 20764 bytes.
OT::GSUB ran out of room; reallocating to 41544 bytes.
OT::GSUB ran out of room; reallocating to 83104 bytes.
OT::GSUB ran out of room; reallocating to 166224 bytes.
Repacking GSUB.
OT::GSUB final subset table size: 99758 bytes.
OT::GSUB::subset success
```

(`fonts/writing-tables/forty-subset.repack-log.txt`, made by `build.sh` with a debugging build of `hb-subset` {{hb}}; not run when the book is built.)

The buffer doubled four times; then the serializer’s layout overflowed and the repacker found one that doesn’t. Where it put things was printed by `fonts/writing-tables/layout.py`, a Python script that reads the GSUB bytes, not HarfBuzz:

```
forty-subset.ttf: GSUB, 99,758 bytes, 40 lookups
  kind         count   first starts   last ends
  LookupList       1             18         100
  Lookup          40            346         666
  SingleSubst     40            906      50,850
  Coverage        40         50,850      99,758
  longest 16-bit offset: 60,784 (SingleSubst to Coverage, lookup 27; 120 offsets of this width)
```

The repacked table is in layers: the LookupList, then all 40 Lookups, then all 40 subtables, then all 40 Coverage tables. Every offset fits, the longest with under 5,000 bytes to spare.

### The graph

`hb_resolve_overflows` (`hb-repacker.hh:480`) starts from what the serializer leaves behind: its stack of packed objects, with their bytes and links. `graph_t::create` (`graph/graph.hh:575`) turns them into an **object graph**: a vertex for each object, an edge for each link, real or virtual. The repacker needs only each object’s size and links, and looks inside objects only for GSUB and GPOS, below. A graph is refused if it has more than `HB_REPACKER_MAX_VERTICES` (800,000) objects, if some object can’t be reached from the root, or if it has a cycle (`graph/graph-result.hh` lists the errors).

### Sorting by distance

The layout is a **topological order** of the graph: an order in which every object comes after all the objects that point to it, so that every offset is positive. There are many, and `sort_shortest_distance` (`graph/graph.hh:740`) picks one by distance from the root.

First it gives each object a **distance**, with Dijkstra’s algorithm (`update_distances`, `:1865`). Following a link costs the size of the object it points to plus 2<sup>16</sup> for a 16-bit link, 2<sup>24</sup> for a 24-bit one and 2<sup>32</sup> for a 32-bit one (`:1911`). The power of two dominates, so distance mostly counts how many offsets deep an object is, and how wide those offsets are; size breaks the ties. Then it lays the objects out with Kahn’s algorithm, using a priority queue: an object becomes ready once every object that points to it has been placed, and of the ready objects, the nearest goes next. Objects at the same distance go in the order their parents’ links name them (`:787`).

That is the layering in `forty-subset.ttf`: every Lookup is one 16-bit offset from the LookupList, every subtable two, every Coverage table three.

`docs/repacker.md` says plain Kahn’s algorithm is tried first, being faster. In {{hb}} there is only the distance sort.

> Since {{hb}}: fixed on HarfBuzz main by [`4d41c69`](https://github.com/harfbuzz/harfbuzz/commit/4d41c69d42fa9e73885a93a6396acbb582c9dee8) (17 November 2026), so main’s `docs/repacker.md` describes only the distance sort.

### Round by round

After sorting, `will_overflow` (`graph/serialize.hh:93`) works out each object’s position from the sizes and checks every real link against its width and signedness, collecting the ones that overflow. If there are none, the repacker is done. If there are, `hb_resolve_graph_overflows` (`hb-repacker.hh:402`) changes the graph and sorts again, round after round. In each round, starting with the overflow furthest down the table, it tries:

* **Isolating a space.** If the overflowing link is inside a space (next section) that more than one 32-bit offset points into, it moves up to half of those entry points into a new space of their own, and the round is over (`_try_isolating_subgraphs`, `:191`).
* **Duplicating a shared child.** If the child has several parents, a copy is made for the parents whose links overflow, so the copy can be placed near them (`_resolve_shared_overflow`, `:246`). A child with an incoming virtual link isn’t duplicated (`graph/graph.hh:1494`), since the repacker can’t tell whether the original would be left with only virtual links.
* **Moving a leaf closer.** If the child points to nothing, the parent’s children get a higher **priority** (`raise_childrens_priority`, `graph/graph.hh:1594`). Priority lowers the distance the sort uses: by half the object’s size at priority 1, by its whole size at 2, and at 3, the maximum, the distance becomes zero, so the object is placed as soon as its parents are (`:473`–`499`).

If nothing can be done for any overflow, the loop stops. Otherwise it stops after `max_rounds` rounds without isolation (32 for the subsetter), or 500 rounds in all (`HB_REPACKER_MAX_ITERATIONS`, `hb-limits.hh:283`). Duplication undoes some of the serializer’s sharing, so the table grows, but it means the same to anything that reads it.

### 32-bit offsets and spaces

A 32-bit offset (or a 24-bit one, in the beyond-64k formats) can reach anywhere in the table. A part of the graph reached only through such offsets needn’t be near its parents, and is better kept together: if the distance sort interleaved two such parts, each one’s 16-bit offsets would have to jump over the other’s objects (`docs/repacker.md` has an example).

So before the rounds start, `assign_spaces` (`graph/graph.hh:939`) finds the objects that wide offsets point to, the roots of **spaces**. Roots whose subgraphs touch are put in the same space. Any object in a space that is also reachable from outside it, by a path with no wide offset, is duplicated, so that the space is entirely its own (`isolate_subgraph`, `:1011`). Each space then gets a number, 1 upwards, which multiplies the cost of the wide link into it, so the sort lays out all of space 0 first, then all of space 1, and so on. There can be at most `HB_REPACKER_MAX_SPACES` (8,000) spaces.

### GSUB and GPOS

Reordering and duplication can’t fix everything. When the part of a GSUB reached through 16-bit offsets is simply too big, no order and no copy helps. For GSUB and GPOS, the repacker has two more remedies, which change what the table *says*, not only where things are:

* **Splitting subtables.** A subtable that is too big for its own offsets to work, such as one whose Coverage table, packed last, is more than 64 KB from its start, is split into two or more subtables of the same type in the same lookup (`split_subtables_if_needed`, `graph/gsubgpos-graph.hh:135`). Only some types can be split: in GPOS, PairPos and MarkBasePos; in GSUB, LigatureSubst (`:383`–`394`). The split points are worked out from the sizes, as in `compute_split_points` for ligatures (`graph/ligature-graph.hh:128`), which keeps each piece’s data under 64 KB. `docs/repacker.md` still says only GPOS subtables can be split.
* **Promoting lookups to Extension.** A lookup is rewritten as an Extension lookup: each of its subtables gets an 8-byte Extension subtable in front of it, holding the lookup type and a 32-bit offset (`make_extension`, `graph/gsubgpos-graph.hh:99`). `_promote_extensions_if_needed` (`hb-repacker.hh:102`) decides which. It sorts the lookups by subtables per byte, most first, then keeps lookups as they are, in that order, while three totals stay under 64 KB: the LookupList and the Lookups; the Lookups and their subtables; and the subtables and everything below them. Once one doesn’t, it promotes every lookup still to come. A comment calls this “v1”, and describes a better algorithm, by connected components, that isn’t written yet.

Neither is tried at first. The first pass runs with `always_recalculate_extensions` false, so for GSUB and GPOS it only assigns spaces before the rounds. If that pass ends with overflows still there, the repacker runs again, on the graph as the first pass left it, with splitting and promotion on (`hb-repacker.hh:451`). `sixty.ttf` is `forty.ttf` with 60 lookups instead of 40, subset the same way:

```
OT::GSUB initial estimated table size: 10624 bytes.
  … four reallocations …
Repacking GSUB.
Applying GSUB/GPOS repacking specializations.
Assigning spaces to 32 bit subgraphs.
=== Overflow resolution round 0 ===
  overflow from   14 (   1 in,    1 out, space  0) =>   13 (   1 in,    1 out, space  0)
  … nine more, plus 54 more overflows; then priorities raised …
=== Overflow resolution round 1 ===
=== Overflow resolution round 2 ===
=== Overflow resolution round 3 ===
No resolution available :(
Failed to find a resolution. Re-running with extension promotion and table splitting enabled.
Repacking GSUB.
Applying GSUB/GPOS repacking specializations.
Splitting subtables if needed.
Promoting lookups to extensions if needed.
Promoting lookup type 1 (obj 56) to extension.
Promoting lookup type 1 (obj 68) to extension.
  … 30 more …
OT::GSUB final subset table size: 152548 bytes.
OT::GSUB::subset success
```

(`fonts/writing-tables/sixty-subset.repack-log.txt`, cut down by hand; made with the same debugging build, not when the book is built.)

Three rounds of raising priorities didn’t help, and in the fourth there was nothing left to try. The second pass promoted 32 lookups (numbered here as objects, not lookups), after which a sort was enough. `layout.py` found:

```
sixty.ttf: GSUB, 2,432 bytes, 60 lookups
  kind         count   first starts   last ends
  LookupList       1            870         992
  Lookup          60            992       2,416
  SingleSubst     60          1,000       2,422
  Coverage        60          1,006       2,432
  longest 16-bit offset: 1,538 (LookupList to Lookup, lookup 59; 180 offsets of this width)
sixty-subset.ttf: GSUB, 152,548 bytes, 60 lookups
  kind         count   first starts   last ends
  LookupList       1             18         140
  Lookup          60            506         986
  Extension       32          5,310       5,566
  SingleSubst     60          1,346     149,446
  Coverage        60          1,352     152,548
  longest 16-bit offset: 62,574 (Lookup to SingleSubst, lookup 21; 180 offsets of this width)
  longest 32-bit offset: 142,400 (Extension to SingleSubst, lookup 4; 32 offsets of this width)
  Extension lookups: 32 of 60: 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 22 24 27 29 39 41 44 48 49 54 55 59
```

(Printed by `layout.py`, not by HarfBuzz.)

fontTools wrote the source with each lookup, its subtable and its Coverage table side by side. In the subset, the 28 lookups left alone have their subtables and Coverage tables in the first 65 KB, each Coverage table right after its subtable (put there by the first pass’s raised priorities, by our reading). The 32 Extension subtables are near the front too, and the promoted lookups’ subtables fill the rest, reached by 32-bit offsets. Lookup 4 (`ss05`) is a promoted one, and works the same through its Extension subtable:

```shape
sixty.ttf  \u4E01\u4E02\u4E03  --features=ss05
sixty-subset.ttf  \u4E01\u4E02\u4E03  --features=ss05
```

The second glyph differs because the subset has no `g7` to substitute (7 is a multiple of 7), not because of the repacking.

The repacker never turns an Extension lookup back into an ordinary one, and the subsetter copies an Extension subtable as an Extension subtable (`hb-ot-layout-gsubgpos.hh:6109`). So a font keeps its Extension lookups through a subset, however small. `sixty-small.ttf` is `sixty-subset.ttf` cut down to its first 64 characters:

```
sixty-small.ttf: GSUB, 5,752 bytes, 60 lookups
  kind         count   first starts   last ends
  LookupList       1            870         992
  Lookup          60            992       5,688
  Extension       32          1,000       5,566
  SingleSubst     60          1,008       5,694
  Coverage        59          1,034       5,752
  longest 16-bit offset: 4,810 (LookupList to Lookup, lookup 0; 180 offsets of this width)
  longest 32-bit offset: 8 (Extension to SingleSubst, lookup 1; 32 offsets of this width)
  Extension lookups: 32 of 60: 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 22 24 27 29 39 41 44 48 49 54 55 59
```

(Printed by `layout.py`, not by HarfBuzz.)

Its 32 Extension lookups each point eight bytes ahead, to a subtable that is now tiny. Nothing overflowed, so this is the serializer’s own layout, and it shows the order described earlier: lookup 0, written first, is at the end, 4,810 bytes after the LookupList, and lookup 59 is at the front. It also shows sharing: 60 lookups, but 59 Coverage tables, because two of the subsets’ Coverage tables came out identical.

### Writing the result

When the graph has no overflows, `graph::serialize` (`graph/serialize.hh:234`) writes it with a new serializer: each object, in reverse of the sorted order, is pushed, copied, given its real links again and packed with sharing off, since the graph already says what is shared. If an offset still overflows, `hb_resolve_overflows` returns nothing, and `_hb_subset_repack` (`hb-subset-table.hh:114`) fails the table.

## For other writers: `hb_subset_serialize_or_fail`

The repacker is also public, in `hb-subset-serialize.h`, for programs that have built an object graph of their own and want HarfBuzz to lay it out:

```c
hb_blob_t *
hb_subset_serialize_or_fail (hb_tag_t                      table_tag,
                             hb_subset_serialize_object_t *hb_objects,
                             unsigned                      num_hb_objs);
```

Each `hb_subset_serialize_object_t` is an object as the serializer would have it: `head` and `tail` pointers to its bytes, and arrays of real and virtual links. A `hb_subset_serialize_link_t` has a `width` in bytes, a `position` in the object, and an `objidx`: the target’s place in `hb_objects`, plus 1, since the function puts the nil object in front (`hb-subset-serialize.cc:52`). Children come before parents, and the last object is the root. There is no `whence` or `bias`: every link is unsigned and counts from the start of its object (`hb-serialize.hh:152`).

It runs at most 20 rounds, with GSUB and GPOS splitting and promotion on from the start (`hb-subset-serialize.cc:56`); `HB_TAG_NONE` as the tag turns off what is specific to a table. It returns `NULL` on failure. It has been public since HarfBuzz 10.2.0; before that it was the experimental `hb_subset_repack_or_fail`, added in 4.1.0 (`NEWS`).

> For programmers: fontTools is one user. When a table it compiles overflows, fontTools 4.38 hands the objects to HarfBuzz’s repacker through uharfbuzz, if that is installed, and falls back to its own splitting and promotion if it fails (`fontTools/ttLib/tables/otBase.py`, option `USE_HARFBUZZ_REPACKER`). This chapter’s fonts were built with it off, so they don’t depend on uharfbuzz.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-serialize.hh` | `hb_serialize_context_t`: the buffer, objects and links, `pop_pack` and sharing, `resolve_links`, the error flags, snapshots |
| `src/hb-open-type.hh` | `serialize` methods for arrays, and `OffsetTo::serialize_subset`, `serialize_serialize`, `serialize_copy` |
| `src/hb-open-file.hh` | writing a font file’s header and directory, used by the face builder |
| `src/OT/Layout/GSUB/LigatureSubstFormat1.hh` | a `subset` method that writes objects in a chosen order and adds virtual links |
| `src/hb-subset-table.hh` | the subsetter’s buffer estimate and retries, and the call to the repacker |
| `src/hb-repacker.hh` | `hb_resolve_overflows`: the passes, the rounds, isolation, duplication, priorities, extension promotion |
| `src/graph/graph.hh` | `graph_t`: distances, the sort, spaces, duplication |
| `src/graph/serialize.hh` | checking for overflows, and writing the graph back out |
| `src/graph/gsubgpos-graph.hh`, `pairpos-graph.hh`, `markbasepos-graph.hh`, `ligature-graph.hh` | GSUB and GPOS as graphs: splitting subtables and making Extension lookups |
| `src/hb-subset-serialize.h`, `src/hb-subset-serialize.cc` | the public repacker |
| `src/hb-limits.hh` | `HB_REPACKER_MAX_ITERATIONS`, `HB_REPACKER_MAX_VERTICES`, `HB_REPACKER_MAX_SPACES` |
| `docs/serializer.md`, `docs/repacker.md` | the design notes; the repacker’s is partly out of date |

> Since {{hb}}: fixed on HarfBuzz main by [`4d41c69`](https://github.com/harfbuzz/harfbuzz/commit/4d41c69d42fa9e73885a93a6396acbb582c9dee8) (17 November 2026), which brings both design notes up to date (the table’s last row).

The fonts and scripts are in `fonts/writing-tables/`: `build-fonts.py` makes `forty.ttf` and `sixty.ttf`, `build.sh` subsets them and runs `layout.py`, and `serialize-example.cc` is the program behind the walk-through above.

## In short

* Everything in HarfBuzz that writes font data writes it through `hb_serialize_context_t`, into a fixed buffer: simple data at the head, finished objects stacked at the tail.
* `push` starts an object, `pop_pack` packs it and returns its index, and `add_link` records an offset to it, with a width, a `whence` and a bias; `end_serialize` fills the offsets in.
* `pop_pack` shares an object with an identical one already packed. The layout is the writing order reversed; virtual links ask the repacker to keep an order.
* Errors are flags, and once one is set writing stops quietly. The subsetter doubles the buffer when it runs out of room, up to 256 times the source table, and repacks when the only error is an offset overflow.
* The repacker sorts the object graph by distance from the root, then, round by round, isolates 32-bit spaces, duplicates shared children and raises priorities.
* For GSUB and GPOS, if that fails, it runs again, splitting PairPos, MarkBasePos and LigatureSubst subtables and promoting lookups to Extension.
* `hb_subset_serialize_or_fail` offers the repacker to other font compilers, such as fontTools.
