# Reading HarfBuzz’s C++

HarfBuzz has a C API, but it is written in C++, and in a dialect of its own. It doesn’t use the standard library’s containers. It has its own vector, set, and hash map, a small library of iterators that are chained together with `|`, and a set of macros and function objects that turn up on almost every page of the source. A programmer who knows C++ well can still stall on a line like `+ hb_iter (intersection) | hb_filter (glyphset, hb_second)`.

This appendix is the key to that dialect, so that chapters quoting the source can link here instead of explaining. Idioms that belong to one subject, such as the structs laid over a font’s bytes, are explained in that subject’s chapter, and [listed](#covered-elsewhere) at the end. Everything here lives in headers that `hb.hh` includes for every file (`hb.hh:578`).

## The rules the dialect follows

Three rules explain most of what is unusual.

**No STL containers.** HarfBuzz’s own `AGENTS.md` says so: “Do not introduce STL containers in library code.” The code still uses type traits, `std::forward`, `std::move`, and `std::initializer_list`, but not `std::vector`, `std::map`, and the rest.

**No exceptions.** The library is compiled with `-fno-exceptions` and `-fno-rtti` (in the top-level Meson build file). Nothing throws. Instead a container that fails to allocate remembers it, and `in_error ()` becomes true. Objects that own several containers, such as buffers, keep a flag called **`successful`** that goes false on the first failure and stays false.

**All memory through `hb_malloc`.** Every allocation goes through `hb_malloc`, `hb_calloc`, `hb_realloc`, and `hb_free`. They are the C library’s functions unless HarfBuzz is built with `HB_CUSTOM_MALLOC` and the four `hb_*_impl` functions are supplied (`hb.hh:553`). The fuzzers use exactly that: `failing-alloc.c` fails one allocation in sixteen at random, so the out-of-memory paths are run all the time. (The four are public API since 11.0.0, “Not of much use to clients”, says `hb-common.h`.)

Together these give the pattern that most container code follows: **carry on, check once**. Operations on a container that has failed do nothing and return quietly, so a long run of them needs only one check at the end. Here is the subsetter building the map from old glyph IDs to new ones, trimmed (`hb-subset-plan.cc:565`):

```c++
static bool
_create_glyph_map_gsub (const hb_set_t* glyph_set_gsub,
                        const hb_map_t* glyph_map,
                        hb_map_t* out,
                        hb_vector_t<hb_codepoint_t>* out_flat)
{
  if (unlikely (glyph_set_gsub->in_error ()))
    return false;
  ...
  if (unlikely (!out_flat->resize_dirty (flat_size)))
    return false;
  ...
  out->alloc (glyph_set_gsub->get_population ());
  for (auto gid : *glyph_set_gsub)
  {
    hb_codepoint_t new_gid = glyph_map->get (gid);
    out->set (gid, new_gid);
    out_flat->arrayZ[gid] = new_gid;
  }
  return !out->in_error ();
}
```

All three containers are here. The set is checked before it is used, the vector’s resize is checked because the loop writes to its memory directly, and the map’s many `set` calls are checked once, at the end.

## hb_vector_t

**`hb_vector_t<Type>`** is HarfBuzz’s growable array (`hb-vector.hh:44`), and **`hb_sorted_vector_t<Type>`** is the same with a flag set: `hb_vector_t<Type, true>` (`:794`). It has three fields, all public: `arrayZ`, the storage; `length`; and `allocated`, the capacity, which is signed: a negative value means an allocation failed (`:161`). It grows by half as much again plus eight (`:586`).

| Method | What it does |
|---|---|
| `push (v)` | appends; returns a pointer to the new element |
| `push_or_fail (v)` | the same, returning `false` on failure |
| `alloc (n)`, `alloc_exact (n)` | reserves room without changing `length` |
| `resize (n)`, `resize_exact (n)`, `resize_dirty (n)` | changes `length`; the dirty form leaves new elements uninitialized |
| `pop ()`, `shrink (n)`, `remove_ordered (i)`, `remove_unordered (i)`, `clear ()` | removes |
| `tail ()` | the last element |
| `as_array ()`, `iter ()` | an `hb_array_t` view, which is also an iterator |
| `qsort ()`, `lsearch (x)`, `lfind (x)` | sorting and linear search |
| `in_error ()`, `reset ()` | the error state, and the way out of it |

Three behaviors catch readers out.

**Indexing never crashes.** `v[i]` with `i` past the end returns `Crap (Type)`, a writable scratch object, or `Null (Type)` from a `const` vector (`hb-vector.hh:263`). No assertion fires. [Fonts as bytes](fonts-as-bytes.html#null-objects) explains both objects.

**A failed `push` still returns a pointer.** It points at `Crap`, so code can fill in the new element without checking. The shape-plan builder does just that (`hb-ot-map.cc:154`, trimmed):

```c++
hb_ot_map_t::lookup_map_t *lookup = m.lookups[table_index].push ();
lookup->mask = mask;
lookup->index = lookup_index;
lookup->auto_zwnj = auto_zwnj;
```

If the allocation failed, these writes land in the scratch object, and the vector is in error for a later check to see.

**`hb_sorted_vector_t` doesn’t sort itself.** All the flag does is enable `bsearch` and `bfind`, and make `as_array ()` return a sorted array. Keeping the elements in order is the caller’s job: either fill the vector and then call `qsort ()`, or insert each element where `bfind` says it belongs, as the set’s page map does (`hb-bit-set.hh:1188`). Sorting and searching use two different comparison functions, and a type that is both sorted and searched has both: a static `cmp (const void *, const void *)` for `qsort`, in the C library’s style, and a member `cmp (key)` for `bsearch`, which compares a key with this element. The plan’s feature map has both (`hb-ot-map.hh:62` and `:65`), and is searched by tag (`hb-ot-map.hh:125`).

> For programmers: `static constexpr bool realloc_move = true;` near the top of a struct (the containers all have it) says that the type can be moved by copying its bytes. A vector of such things grows with `realloc`, without calling move constructors (`hb-vector.hh:455`).

## hb_array_t and hb_sorted_array_t

**`hb_array_t<Type>`** is a view: a pointer and a length, owning nothing (`hb-array.hh:48`). `hb_array (ptr, len)` makes one, `as_array ()` gets one from a vector or a font table’s array, and `hb_bytes_t` is `hb_array_t<const char>` (`:527`). It is also a random-access iterator, which is how plain memory enters the pipes described below. Like the vector, it returns `Crap` or `Null` for an index past the end (`:86`).

`sub_array (start, count)` takes a slice, and clamps it to what is there (`:279`). Its second form takes `count` by pointer, and writes back how many elements the slice really has. That is the shape of HarfBuzz’s public functions that fill a caller’s array (a start offset, a pointer to the count, the array), and such a function is often little more than a `sub_array`. Here is `hb_ot_map_t::get_feature_tags` (`hb-ot-map.cc:410`, trimmed):

```c++
if (tag_count)
{
  auto sub_features = features.as_array ().sub_array (start_offset, tag_count);
  if (tags)
  {
    for (unsigned int i = 0; i < sub_features.length; i++)
      tags[i] = sub_features[i].tag;
  }
}
return features.length;
```

**`hb_sorted_array_t<Type>`** adds binary search (`:367`). `bsearch (key)` returns a pointer to the match, or `nullptr`. `bfind (key, &i)` returns whether it found the key, and stores its index; with `HB_NOT_FOUND_STORE_CLOSEST` it stores, on a miss, where the key would go, which is how the set below finds where to insert a page. Both search with the element’s `cmp (key)`. All of HarfBuzz’s binary searches come down to one function, `hb_bsearch_impl` (`hb-algs.hh:1423`: “This is our *only* bsearch implementation.”). Calling `qsort ()` on an `hb_array_t` sorts it in place and returns it as an `hb_sorted_array_t`.

The arrays in a font’s tables, `ArrayOf` and `SortedArrayOf`, are a different thing: structs laid over bytes, described in [Fonts as bytes](fonts-as-bytes.html#arrays). Their `as_array ()` turns them into these views.

## hb_set_t

**`hb_set_t`** is a set of 32-bit unsigned integers (`hb-set.hh:177`). It is the same type as the public `hb_set_t` that `hb_set_create` returns, which is why it carries an object header, but inside the library it is mostly made on the stack. Its values are glyph IDs more than anything else, but also code points, lookup and feature indices, name IDs, and table tags.

It is built in layers. `hb_set_t` wraps `hb_sparseset_t`, which wraps `hb_bit_set_invertible_t`, which wraps **`hb_bit_set_t`**, the real data structure (`hb-bit-set.hh:34`). That is a list of **pages**. A page (`hb_bit_page_t`, `hb-bit-page.hh:115`) is 512 bits, eight 64-bit words, holding 512 consecutive values, with a cached count of how many are set. The set keeps its pages in the order it made them, and beside them a `page_map`: a sorted vector of (major, index) pairs, where a value’s **major** is the value divided by 512 (`hb-bit-set.hh:80`). Finding a value’s page is a binary search of the page map, after a check of the page found last time (`page_for`, `:1172`).

This suits glyph IDs well. The glyphs a lookup or a subset touches tend to come in runs, so a few pages hold them: every glyph of a 1,000-glyph font fits in two. Once the page is found, membership is a shift and a mask, and union, intersection, and the rest work 64 bits at a time. Code points are much the same, since text in one script uses a few blocks.

Sets are everywhere because much of what HarfBuzz computes is a set of glyphs: the glyphs a lookup’s coverage holds, the glyphs a substitution can reach (the **closure**), the lookups a set of features uses. The subsetter is built on them. Of the 69 members of a subset plan, 30 are sets or maps (`hb-subset-plan-member-list.hh`). The shaping loop itself doesn’t use them: when it needs to ask “might this lookup touch this glyph?” fast, it uses the much smaller set digest, which is not a set (see [GSUB](gsub.html#three-filters-before-any-real-work)).

**The invertible set.** `hb_bit_set_invertible_t` adds one flag, `inverted` (`hb-bit-set-invertible.hh:35`). When it is set, the bits record what is *not* in the set: `add` clears a bit, and `get` returns the bit XOR the flag (`:116`, `:140`). A set can then mean “everything except these”, in no memory. The subsetter uses this for its defaults: a new subset input’s set of scripts is inverted, “Default to all scripts” (`hb-subset-input.cc:190`), and `hb_subset_input_keep_everything` clears and inverts each of its sets (`:394`). `hb_set_invert` was deprecated in 1.6.1, and undeprecated in 2.9.1 along with the new subsetting API (`NEWS`).

What to watch for:

* Iterating a set gives its values in increasing order, inverted or not. Its iterator is marked as sorted.
* `HB_SET_VALUE_INVALID`, which is `(hb_codepoint_t) -1`, can’t be a member: `add` ignores it (`hb-bit-set.hh:158`). The C-style `next (&v)` and `previous (&v)` use it as the start and end marker.
* The population of an inverted set is about four billion.
* A set is a **predicate** and a **sink** as well as a container: `set (g)` and `set.has (g)` test membership, and `set << g` adds (`hb-set.hh:118`, `:121`). That is what lets it appear in the pipes below as `hb_filter (glyphset)` or `hb_sink (c->output)`.

## hb_map_t and hb_hashmap_t

**`hb_hashmap_t<K, V>`** is a hash table with open addressing (`hb-map.hh:43`). The items live in one array whose size is a power of two. A search starts at the key’s hash modulo a prime just below that size, and steps on by 1, 2, 3 slots, and so on (`fetch_item`, `:390`). A deleted item stays behind, marked as no longer live, so that searches still pass over it. The table grows when two-thirds of its slots have been used.

**`hb_map_t`** is `hb_hashmap_t<hb_codepoint_t, hb_codepoint_t, true>` (`:605`), and, like the set, it is also the public type that `hb_map_create` returns. The subsetter’s glyph map, from old glyph IDs to new ones, is one; so are its maps of lookup and feature indices. Larger values use `hb_hashmap_t` directly: the subset plan maps each script’s index to a set of language systems with `hb_hashmap_t<unsigned, hb::unique_ptr<hb_set_t>>`.

| Method | What it does |
|---|---|
| `set (k, v)` | adds or replaces |
| `get (k)`, `m[k]`, `m (k)` | the value, or a default if there is none |
| `has (k)`, `has (k, &vp)` | whether the key is there, and a pointer to its value |
| `del (k)` | removes |
| `iter ()`, `keys ()`, `values ()` | iterators over pairs, keys, or values |

What to watch for:

* **A missing key returns a default, not an error.** For `hb_map_t` the default is `HB_MAP_VALUE_INVALID`, which is `-1`; for other maps it is `Null (V)`, a zero-filled value (`:129`). Where the default could be a real value, use `has (k, &vp)`.
* **`m[k]` doesn’t insert.** Unlike `std::map`, it is only another way of writing `get`.
* **Iteration is in hash order.** Code that writes a map out in a particular order sorts first.
* A map is a **projection** (`m (k)`, `:410`) and a predicate (`has`), so `hb_map (glyph_map)` and `hb_filter (map)` both work in pipes.

## Iterators and pipes

HarfBuzz’s iterators are not the standard library’s. An STL loop needs two iterators, a begin and an end. A HarfBuzz iterator is one small object that knows when it has run out: `*it` is the current item, `++it` moves on, and `bool (it)` says whether there is anything left. Many have `it.len ()` and `it[i]` as well. Iterators are values, cheap to copy, and copying one makes an independent cursor.

The base class is **`hb_iter_t`** (`hb-iter.hh:59`), which each iterator derives from, passing itself as the template argument. An iterator implements a few methods with double-underscore names (`__item__`, `__next__`, `__more__`, `__len__`…), and the base class turns them into operators. `hb_iter_with_fallback_t` fills in what an iterator leaves out, slowly if it must: without `__len__`, `len ()` counts by walking a copy (`:206`). Each iterator also says whether it is random-access, and whether it is sorted.

`hb_iter (x)` gets an iterator from anything: it calls `x.iter ()` on a container, and it makes an `hb_array_t` from a pointer and a length, or from a C array (`:156`). Every iterator also works in a range-based `for` loop.

### Pipes

The `|` operator is defined for any iterator on its left, and what it does is short: `lhs | rhs` is `rhs (lhs)` (`hb-iter.hh:369`). The functions written on the right return small objects that take an iterator and wrap it in another. So a pipe is a chain of iterators, each pulling from the one before. Nothing happens until something pulls at the end. Here is the whole of `get_feature_types` in the `feat` table (`hb-aat-layout-feat-table.hh:166`), which fills a caller’s array:

```c++
if (count && features)
{
  + namesZ.as_array (featureNameCount).sub_array (start_offset, count)
  | hb_map (&FeatureName::get_feature_type)
  | hb_sink (hb_array (features, *count))
  ;
}
return featureNameCount;
```

It takes a slice of the table’s array, maps each record to its type by calling a member function, and writes each result into the caller’s array. The `+` at the front is the iterator’s unary plus, which returns a copy of the iterator and nothing more (`hb-iter.hh:76`). It lets every line of the pipe begin with an operator, which seems to be all it is for at the head of a pipe (inferred). The lone `;` on the last line is the same habit: lines can be added and removed without touching their neighbors.

The vocabulary:

| Name | Kind | What it does |
|---|---|---|
| `hb_map (f)` | stage | each item becomes `f (item)` |
| `hb_map_retains_sorting (f)`, `hb_map_sorted (f)` | stage | the same, and promises that the order is kept, or that the result is sorted |
| `hb_filter (p, f)` | stage | keeps items for which `p (f (item))` is true; `f` defaults to the identity |
| `hb_zip (a, b)` | source or stage | pairs of items from two iterators, stopping at the shorter |
| `hb_enumerate (it)` | source or stage | pairs of (index, item) |
| `hb_range (end)`, `hb_range (start, end, step)` | source | numbers, as an iterator |
| `hb_iota (start, step)` | source | numbers without end |
| `hb_take (n)`, `hb_concat (a, b)` | stage, source | the first n items; one iterator after another |
| `hb_sink (s)` | end | writes each item with `s << item`, into a vector, set, map, or array |
| `hb_apply (f)` | end | calls `f (item)` for each item |
| `hb_reduce (f, init)` | end | folds the items into one value |
| `hb_all`, `hb_any`, `hb_none` | function | whether every, some, or no item matches |

`hb_pair_t` is the pair the zips make, with `.first` and `.second`; `hb_codepoint_pair_t` is a pair of `hb_codepoint_t`s. `hb_first` and `hb_second` take the halves of a pair, and `hb_identity` returns what it is given.

### Function objects

Each of those names is an object, not a function. `HB_FUNCOBJ (hb_second)` declares a `static const` object of an unnamed struct whose `operator ()` does the work (`hb-meta.hh:75`). An object, unlike a function template, can be passed as an argument without naming its types, which is how `hb_filter (glyphset, hb_second)` can pass `hb_second` along to be called later.

The pipe stages call what they are given through three helpers, which accept more than functions (`hb-algs.hh:689` and `:752`):

* `hb_has (p, v)` calls `p.has (v)` if `p` has one, and `p (v)` otherwise. So a set or a map can be a filter.
* `hb_get (f, v)` calls `f.get (v)` if there is one, then `f (v)`, then `f[v]`. So a map can be a mapping.
* `hb_invoke` calls lambdas, function objects, pointers to member functions (`&FeatureName::get_feature_type`), and pointers to data members alike.

Some function objects can also be given only their last argument, to make a function of the rest. `hb_add (this)` is “add `this` to whatever comes”, and `hb_zip (b)` on the right of a pipe zips what comes from the left with `b`. Here is the closure of an alternate substitution, finding the glyphs it can produce (`OT/Layout/GSUB/AlternateSubstFormat1.hh:66`):

```c++
+ hb_zip (this+coverage, alternateSet)
| hb_filter (c->parent_active_glyphs (), hb_first)
| hb_map (hb_second)
| hb_map (hb_add (this))
| hb_apply ([c] (const AlternateSet<Types> &_) { _.closure (c); })
;
```

A Coverage table iterates over its glyphs in coverage-index order, so zipping it with the subtable’s array of offsets pairs each glyph with its own entry, which is exactly what a coverage index is for. The filter keeps the pairs whose glyph is in the set of glyphs reached so far; `hb_second` takes the offset; `hb_add (this)` resolves it, as `this+offset` would; and `hb_apply` visits each alternate set.

### One pipe, read step by step

The subsetter’s code for SingleSubst format 1 (`OT/Layout/GSUB/SingleSubstFormat1.hh:11`) uses most of the pieces at once. Format 1 maps every covered glyph `g` to `g + d`, modulo 65536. Subsetting it means keeping the mappings whose glyphs both survive, and renumbering them:

```c++
const hb_set_t &glyphset = *c->plan->glyphset_gsub ();
const hb_map_t &glyph_map = *c->plan->glyph_map;

hb_set_t intersection;
coverage.intersect_set (glyphset, intersection);

auto it =
+ hb_iter (intersection)
| hb_map_retains_sorting ([d, mask] (hb_codepoint_t g) {
                            return hb_codepoint_pair_t (g,
                                                        (g + d) & mask); })
| hb_filter (glyphset, hb_second)
| hb_map_retains_sorting ([&] (hb_codepoint_pair_t p) -> hb_codepoint_pair_t
                          { return hb_pair (glyph_map[p.first], glyph_map[p.second]); })
;

bool ret = bool (it);
SingleSubst_serialize (c->serializer, it);
return ret;
```

1. `glyphset` is the set of glyphs the subset keeps, and `glyph_map` maps their old IDs to new ones. Both are references to the plan’s own containers: nothing is copied.
2. `intersection` is a set on the stack: the covered glyphs that survive.
3. `hb_iter (intersection)` walks it, in increasing order.
4. The first `hb_map_retains_sorting` turns each glyph into the pair (glyph, its substitute). The lambda captures `d` and `mask` by value. The name promises that the pairs stay in order, which they do, since their first halves are the glyphs in order.
5. `hb_filter (glyphset, hb_second)` drops a pair unless its *second* half, the substitute, is kept too. The set is the predicate, through `hb_has`, and `hb_second` is the projection that picks what it tests.
6. The second map renumbers both halves through `glyph_map`. It promises to keep the order again. That holds when the subsetter numbers the glyphs itself, since it numbers them in their old order (`hb-subset-plan.cc:668`), but not necessarily when a caller has supplied its own glyph mapping.
7. The semicolon ends the expression, and `it` holds the whole pipe. Nothing has been computed yet, except that a filter, when it is made, moves to its first match. So `bool (it)` asks whether any mapping survives at all.
8. `SingleSubst_serialize` pulls the pairs and writes the new subtable.

The other end shows what the promises are for. `SingleSubst::serialize` accepts only a sorted iterator of pairs (`OT/Layout/GSUB/SingleSubst.hh:43`, trimmed):

```c++
template<typename Iterator,
         hb_requires (hb_is_sorted_source_of (Iterator,
                                              const hb_codepoint_pair_t))>
bool serialize (hb_serialize_context_t *c,
                Iterator glyphs)
{
  ...
  auto get_delta = [=] (hb_codepoint_pair_t _)
                   { return (unsigned) (_.second - _.first) & mask; };
  delta = get_delta (*glyphs);
  if (!hb_all (++(+glyphs), delta, get_delta)) format += 1;
```

`hb_requires` (`hb-meta.hh:61`) removes the function from consideration unless its condition holds, so passing an unsorted iterator doesn’t compile. Then `+glyphs` copies the iterator, `++` moves the copy past the first pair, and `hb_all` checks that every later pair has the same delta as the first: if they all do, the subset can stay format 1, and if not it moves to the format that lists every substitute (2, or 4 beyond 64K). Here the predicate passed to `hb_all` is a plain value, `delta`, which matches by equality.

What to watch for:

* **A pipe runs each time it is walked.** `serialize` walks `glyphs` several times, and every walk calls every lambda again. That is cheap here, but a pipe that does real work in a stage is better sunk into a vector once.
* **“Sorted” is a promise, not a check.** As the comment in `hb-iter.hh:570` puts it: “Our ‘sorted’ comes with no guarantees. It’s just a contract, put in place to help you remember, and think about, whether an iterator you receive is expected to be sorted or not.” Where it matters most, the code checks anyway: Coverage’s serializer looks at the order itself, and doesn’t choose the format that needs sorted glyphs if it finds them out of order (`OT/Layout/Common/Coverage.hh:167`).
* **`len ()` may walk.** A filtered iterator doesn’t know its length without counting.
* **Lambdas that capture by reference tie the pipe to what they capture.** A pipe kept in `auto it` that holds a `[&]` lambda must not outlive the variables the lambda refers to.

A good pipe to read next is in [the Universal Shaping Engine](universal-shaping-engine.html#what-the-machine-doesnt-see), where `hb_enumerate` numbers the glyphs before the filters drop some, so that results can be written back to the right positions.

## Small idioms

**`likely (x)` and `unlikely (x)`** (`hb.hh:273`) tell the compiler which way a test usually goes, with `__builtin_expect`, when optimizing. They don’t change what the test means. When reading, `unlikely` marks an error path, and a function can usually be understood first by skipping every branch that starts with it.

**`HB_INTERNAL`** (`hb.hh:302`) gives a declaration hidden visibility, so it isn’t exported from the shared library. It marks functions and data that cross files inside HarfBuzz but are not API.

**`hb_min`, `hb_max`, and `hb_clamp`** (`hb-algs.hh:885`) are function objects, like the pipe stages. They take arguments of two different types on purpose, so that the compiler can warn when signed and unsigned integers are compared, as the comment above them explains. `hb_clamp (x, lo, hi)` is `hb_min (hb_max (x, lo), hi)`.

**`hb_memcpy`, `hb_memset`, and `hb_memcmp`** wrap the C functions and return at once for a length of zero, because the C functions mustn’t be given a null pointer even then (“It’s illegal to pass NULL to memset(), even if n is zero”, `hb-algs.hh:1271`). HarfBuzz’s `AGENTS.md` asks for them in place of the C functions. `hb_swap` swaps.

**`hb_codepoint_t`** is a `uint32_t` (`hb-common.h:123`). It holds a Unicode code point or a glyph ID, depending on where it is: in a buffer, the [content type](buffers.html#content-types) says which. **`HB_CODEPOINT_INVALID`** is `(hb_codepoint_t) -1` (`hb-common.h:132`), and `HB_SET_VALUE_INVALID` and `HB_MAP_VALUE_INVALID` are other names for it.

**`hb_tag_t`** is a `uint32_t` too, holding four characters, first character in the top byte. `HB_TAG ('l','i','g','a')` makes one (`hb-common.h:196`), and `HB_UNTAG` takes one apart. Tables have their own: `HB_OT_TAG_GSUB` and so on. Tags compare as integers, so sorting by tag sorts printable ASCII tags alphabetically.

**`FLAG (x)`** is `1u << x`, with a compile-time check that `x` is below 32 (`hb-algs.hh:86`). Sets of small enum values are written as masks of flags: `FLAG_UNSAFE (gen_cat) & (FLAG (…SPACING_MARK) | FLAG (…ENCLOSING_MARK) | FLAG (…NON_SPACING_MARK))` asks whether a general category is a mark (`hb-unicode.hh:406`). `FLAG_UNSAFE` skips the check, for values not known at compile time, and `HB_MARK_AS_FLAG_T` gives an enum the bitwise operators.

**`ARRAY_LENGTH (a)`** is the number of elements in a C array. **`HB_SCOPE_GUARD (stmt)`** runs `stmt` when the scope ends, however it ends: `HB_SCOPE_GUARD (fclose (fp));` (`hb-blob.cc:741`). **`hb::unique_ptr`** and **`hb::shared_ptr`** (`hb-cplusplus.hh`) hold a HarfBuzz object and destroy it, or release a reference, when they go out of scope.

**`_or_fail`** at the end of a name means the function says when it fails. In the API, `hb_blob_create` returns the empty blob when it can’t make one, but `hb_blob_create_or_fail` returns `NULL`; `hb_font_draw_glyph_or_fail` returns `false` when there is nothing to draw. [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html) covers the empty objects that the plain versions return. Inside the library, `push_or_fail` is the same idea.

`#ifndef HB_NO_…` blocks are compile-time switches. A build that defines `HB_NO_BEYOND_64K`, for instance, leaves out the wider subtable formats, and with them the code in `SingleSubst::serialize` that chooses them. The [Compile-time configuration](compile-time-configuration.html) appendix lists the switches. `HB_EXPERIMENTAL_API` guards API that isn’t stable yet.

**Templates.** `hb_enable_if (cond)` and `hb_requires (cond)` (`hb-meta.hh:59`) remove a template from overload resolution unless `cond` holds; since 15.2.0 they are written with `std::enable_if`, where 15.1.0 had a HarfBuzz copy of it. `HB_AUTO_RETURN (expr)` (`:68`) writes a function whose body and return type are both `expr`. `hb_priority` and `hb_prioritize` choose between overloads in order of preference; [Fonts as bytes](fonts-as-bytes.html#choosing-the-method-to-call) explains them.

### Covered elsewhere

| Idiom | Where |
|---|---|
| structs over bytes, `HBUINT16`, `OffsetTo`, `this+offset`, `ArrayOf`, `DEFINE_SIZE_*` | [Fonts as bytes](fonts-as-bytes.html) |
| `Null`, `Crap` | [Fonts as bytes](fonts-as-bytes.html#null-objects) |
| dispatch and contexts | [Fonts as bytes](fonts-as-bytes.html#dispatch-contexts) |
| `hb_barrier`, `TRACE_SANITIZE`, `return_trace`, the `HB_DEBUG_*` macros | [Trust nothing: the sanitizer](trust-nothing-the-sanitizer.html) |
| lazy loaders, `hb_atomic_t`, `hb_object_header_t`, reference counting | [Blobs, faces, and lazy tables](blobs-faces-and-lazy-tables.html) |
| the X-macro lists (`HB_FONT_FUNC_IMPLEMENT`, `HB_SHAPER_IMPLEMENT`) | [Fonts and font functions](fonts-and-font-functions.html#one-list-of-callbacks), [hb_shape and its backends](hb_shape-and-its-backends.html#the-shaper-list) |
| `HB_BUFFER_ALLOCATE_VAR` and the buffer’s scratch bytes | [Buffers](buffers.html#eight-bytes-of-scratch-space) |
| the set digest | [GSUB](gsub.html#three-filters-before-any-real-work) |

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb.hh` | `likely`, `HB_INTERNAL`, the allocator hooks, and the list of headers every file gets |
| `src/hb-vector.hh` | `hb_vector_t` and `hb_sorted_vector_t` |
| `src/hb-array.hh` | `hb_array_t`, `hb_sorted_array_t`, `hb_bytes_t` |
| `src/hb-set.hh`, `src/hb-bit-set-invertible.hh`, `src/hb-bit-set.hh`, `src/hb-bit-page.hh` | `hb_set_t`, layer by layer |
| `src/hb-map.hh` | `hb_hashmap_t` and `hb_map_t` |
| `src/hb-iter.hh` | the iterator base classes, the pipe operator, and the pipe stages |
| `src/hb-algs.hh` | the function objects (`hb_has`, `hb_get`, `hb_invoke`, `hb_min`, `hb_add`…), `hb_pair_t`, `FLAG`, `hb_memcpy`, `hb_bsearch_impl`, `HB_SCOPE_GUARD` |
| `src/hb-meta.hh` | `HB_FUNCOBJ`, `hb_enable_if`, `hb_requires`, `HB_AUTO_RETURN`, `hb_priority` |
| `src/hb-cplusplus.hh` | `hb::shared_ptr`, `hb::unique_ptr` |
| `src/hb-debug.hh` | `DEBUG_MSG`, the `TRACE_*` macros |
| `src/hb-null.hh`, `src/hb-machinery.hh` | `Null` and `Crap`; the lazy loaders |
| `src/failing-alloc.c` | the allocator the fuzzers use, which fails at random |

## In short

* No STL containers and no exceptions: containers record failure, `in_error ()` reports it, and code checks once, at the end.
* `hb_vector_t` returns `Crap` for a bad index and for a failed `push`. `hb_sorted_vector_t` is sorted only if the caller sorts it.
* `hb_array_t` is a view and an iterator; `sub_array` with a count pointer matches the shape of HarfBuzz’s array-filling API.
* `hb_set_t` is a bit set in 512-bit pages, made for runs of glyph IDs, and it can be inverted to mean “everything except”.
* `hb_map_t` returns `-1` for a missing key; iteration is in hash order.
* A pipe is a chain of lazy iterators: `a | f` is `f (a)`, and nothing runs until a sink, an `apply`, or a loop pulls. Sets and maps can stand in for functions.
