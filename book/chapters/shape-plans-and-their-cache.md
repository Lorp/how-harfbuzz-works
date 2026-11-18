# Shape plans and their cache

Before HarfBuzz can shape a run of text, it has to decide a great deal about it: which script shaper handles it, which of the font’s scripts and language systems to use, which features are on, which lookups those features use and in what order, and which bits of each glyph’s mask belong to which feature. None of that depends on the text itself. It depends on the face, the run’s segment properties, the features the application asked for and, for a variable font, where in the design space the font is. So HarfBuzz works it out once, keeps the result as a **shape plan**, and reuses the plan for every run that would come to the same answers.

This chapter is about the plan as an object and about its cache: what a plan holds, what the cache compares to decide that two runs can share one, and what it deliberately leaves out. The two things it leaves out that matter most are the variation coordinates and the ranges of features. How the features become lookups is the subject of the [next chapter](from-features-to-lookups.html), and how the script shaper is chosen is the one after that, [Choosing a script shaper](choosing-a-script-shaper.html).

The examples use one small test font, `featvar.ttf`, built by `fonts/shape-plans-and-their-cache/build-fonts.py` from the variable font that [Design space](design-space.html) introduced. Its only feature is `rvrn`, and its FeatureVariations table swaps `I` for another glyph in two ranges of weight. The GSUB test font, `gsub/ligatures.ttf`, appears too. Every result and trace on this page was produced by running HarfBuzz {{hb}} when the page was built.

## What a plan is

The struct is short (`hb-shape-plan.hh:71`):

```c++
struct hb_shape_plan_t
{
  hb_object_header_t header;
  hb_face_t *face_unsafe; /* We don't carry a reference to face. */
  hb_shape_plan_key_t key;
#ifndef HB_NO_OT_SHAPE
  hb_ot_shape_plan_t ot;
#endif
#ifdef HAVE_HARFRUST
  hb_atomic_t<void *> harfrust_data;
#endif
};
```

A plan belongs to a face, not to a font. Every font made from the face can use it, whatever its size, its font functions or its synthetic emboldening. The plan points at its face but doesn’t hold a reference to it, as the comment says. The face holds the plans in its cache, and a reference each way would keep both alive for ever (inferred).

The **key** is what the plan was made for, and what the cache compares. The rest is what was made. The `ot` part is the compiled result for the `ot` backend, and it is built for every plan, whichever backend the key names ([hb_shape and its backends](hb_shape-and-its-backends.html#ot) explains why that matters for Graphite). `harfrust_data` exists only in builds with the HarfRust backend, which keeps HarfRust’s own plan there. Other backends can attach data with `hb_shape_plan_set_user_data`, as `kbts` does (`hb-kbts.cc:107`).

### The `ot` part

`hb_ot_shape_plan_t` (`hb-ot-shape.hh:107`) is everything the `ot` pipeline needs to know before it sees any text:

| Field | What it holds | Explained in |
|---|---|---|
| `props` | the segment properties the plan was made for | [Buffers](buffers.html) |
| `shaper` | the script shaper: default, Arabic, Indic, USE and the rest | [Choosing a script shaper](choosing-a-script-shaper.html) |
| `map` | the chosen script and language tags; each feature’s mask bits and shift; the GSUB and GPOS lookups, in stages, with the mask and flags each runs with | [From features to lookups](from-features-to-lookups.html) |
| `aat_map` | the same for `morx`, when it is used instead of GSUB | [AAT inside HarfBuzz](aat-inside-harfbuzz.html) |
| `data` | the script shaper’s own plan data, if it has any | the chapters on scripts |
| `frac_mask`, `numr_mask`, `dnom_mask`, `rtlm_mask`, `kern_mask` | the masks of features the pipeline treats specially | [The pipeline, step by step](pipeline-step-by-step.html) |
| `apply_gpos`, `apply_kern`, `apply_morx`, `zero_marks`, `fallback_mark_positioning` and other flags | decisions about which tables and fallbacks to use | [Fallbacks](fallbacks.html), [Legacy kern](legacy-kern.html) |

Five script shapers keep `data`: Arabic, Hangul, Indic, Khmer and USE (their `data_create` functions). The Indic shaper, for instance, records there whether the font uses the old or the new Indic script tags, and prepares the tests it uses to ask whether `rphf`, `pref`, `blwf`, `pstf` and `vatu` would apply to a glyph (`hb-ot-shaper-indic.cc:315`), once per plan rather than once per run.

All of this is worked out from the face and the key alone, except for two things that need a font, which the plan doesn’t have. The Indic shaper looks up its script’s virama glyph the first time it needs it, and keeps it in the plan (`hb-ot-shaper-indic.cc:281`). And Arabic fallback shaping, for Arabic text in fonts whose GSUB lacks the joining features, synthesizes lookups from the font’s glyphs for the Arabic presentation forms. It waits until the plan is first run, builds them with whichever font that is, and keeps them in the plan’s data with a compare-and-swap. The comment there is frank: “This sucks. We need a font to build the fallback plan...” (`hb-ot-shaper-arabic.cc:434`). In both cases every later font on the same face gets what the first one found. For fonts that share a face, and so a `cmap`, that’s only wrong if one of them has font functions that map characters to glyphs differently (inferred). [Joining scripts](joining-scripts.html) covers fallback shaping itself.

## The key

The key is four things (`hb-shape-plan.hh:34`):

```c++
struct hb_shape_plan_key_t
{
  hb_segment_properties_t  props;

  const hb_feature_t      *user_features;
  unsigned int             num_user_features;

  hb_ot_shape_plan_key_t   ot;

  hb_shape_func_t         *shaper_func;
  const char              *shaper_name;
};
```

and two keys are equal when all four are (`hb-shape-plan.cc:177`):

```c++
return hb_segment_properties_equal (&this->props, &other->props) &&
       this->user_features_match (other) &&
       this->ot.equal (&other->ot) &&
       this->shaper_func == other->shaper_func;
```

`hb_shape_plan_key_t::init` (`hb-shape-plan.cc:75`) fills one in. It copies the segment properties and the features, works out the variation state, and then chooses the backend, as [hb_shape and its backends](hb_shape-and-its-backends.html#how-the-backend-is-chosen) describes. If no backend will take the face, `init` fails, and there is no key.

### Segment properties

The properties are compared field by field by `hb_segment_properties_equal` (`hb-buffer.cc:64`): direction, script, language, and two private fields that are always null. The language is an `hb_language_t`, which is a pointer to an interned string, so languages are compared as pointers. `hb_language_from_string` lowercases its input before interning it, so `en-US` and `en-us` are one language and share a plan. But `en`, `en-US` and `en-GB` are three languages, and get three plans, even though all three map to the same OpenType language tag, `ENG`. The key is compared before the tags are chosen, so it can’t know that.

Everything else about the buffer is left out: its text and context, its flags and its cluster level. They change what happens during shaping, not what the plan holds.

### User features

The features are compared by `user_features_match` (`hb-shape-plan.cc:159`), here whole:

```c++
if (this->num_user_features != other->num_user_features)
  return false;
for (unsigned int i = 0; i < num_user_features; i++)
{
  if (this->user_features[i].tag   != other->user_features[i].tag   ||
      this->user_features[i].value != other->user_features[i].value ||
      (this->user_features[i].start == HB_FEATURE_GLOBAL_START &&
       this->user_features[i].end   == HB_FEATURE_GLOBAL_END) !=
      (other->user_features[i].start == HB_FEATURE_GLOBAL_START &&
       other->user_features[i].end   == HB_FEATURE_GLOBAL_END))
    return false;
}
return true;
```

Three things count: the tag, the value, and whether the feature is **global**, meaning that its range is the whole of the text (`start` 0 and `end` `HB_FEATURE_GLOBAL_END`, which is `(unsigned) -1`). The range itself doesn’t count. Two runs that turn `liga` off over different clusters share one plan.

That is possible because ranges are never used while the plan is made. The planner only asks whether each feature is global (`hb-ot-shape.cc:392`). A global feature with value 1 can share the one global mask bit with every other such feature, while a feature that is on in some places and off in others needs bits of its own. The range is applied each time the plan is run, from the features passed to the run, in `hb_ot_shape_setup_masks` (`hb-ot-shape.cc:760`):

```c++
for (unsigned int i = 0; i < c->num_user_features; i++)
{
  const hb_feature_t *feature = &c->user_features[i];
  if (!(feature->start == HB_FEATURE_GLOBAL_START && feature->end == HB_FEATURE_GLOBAL_END)) {
    unsigned int shift;
    hb_mask_t mask = map->get_mask (feature->tag, &shift);
    buffer->set_masks (feature->value << shift, mask, feature->start, feature->end);
  }
}
```

So these two runs, with `liga` off over different clusters, share a plan, and come out differently all the same:

```shape
gsub/ligatures.ttf  fifi  --language=en  --features=-liga[0:2]
gsub/ligatures.ttf  fifi  --language=en  --features=-liga[2:4]
```

(That they share it can’t be seen from `hb-shape`, which shapes once and exits. A small C program, not part of the book’s build, which asks `hb_shape_plan_create_cached2` for both and compares the pointers, confirms it.) [Buffers](buffers.html#the-mask) shows how `set_masks` compares ranges with clusters.

The value counts even for a feature with a range, because it decides how many bits the feature gets: `hb_bit_storage (max_value)`, at most eight (`hb-ot-map.cc:290`). An alternate substitution reads its alternate’s number from those bits, as [GSUB: substituting glyphs](gsub.html#the-mask) shows. The comparison is exact, not by the number of bits, so `salt=2` and `salt=3` over the same cluster get separate plans, though each needs two bits:

```shape
gsub/ligatures.ttf  aaa  --language=en  --features=salt[1]=2
gsub/ligatures.ttf  aaa  --language=en  --features=salt[1]=3
gsub/ligatures.ttf  aaa  --language=en  --features=salt[1]=2,salt[2]=3
```

The features are compared in order, one by one. `kern,liga` and `liga,kern` are different keys, and so are `liga` and `liga,liga`, though each pair compiles to the same map. Order can matter. When a tag is listed twice, the planner merges the entries, and a later global entry replaces the value of an earlier one (`hb-ot-map.cc:249`), so sorting the list could change what it means.

Asking for a feature that is on anyway makes a new plan too: an empty list and `liga` are different keys, with identical results.

When `init` copies the features into a new plan, it means to “make start/end uniform to easier catch bugs”, setting every non-global `start` and `end` to 1 and 2. The loop it does this in writes `features[0]` each time round instead of `features[i]` (`hb-shape-plan.cc:95`), so only the first feature is changed. Nothing reads the copied ranges, so nothing goes wrong (inferred).

> Since {{hb}}: fixed on HarfBuzz main by [`caf12a8`](https://github.com/harfbuzz/harfbuzz/commit/caf12a809a78332fb320bc1375eca31ab838a0f6) (17 November 2026), so main writes `features[i]` and makes every copied range uniform.

### The variation state

The coordinates aren’t in the key. What is in it is their *outcome*: which of the font’s feature variations apply. `hb_shape_full` passes the font’s normalized coordinates only when some are non-zero (`hb-shape.cc:143`), and `init` hands them to `hb_ot_shape_plan_key_t` (`hb-ot-shape.hh:52`, trimmed):

```c++
struct hb_ot_shape_plan_key_t
{
  unsigned int variations_index[2];
  /* Sorted offsets of distinct true conditions within FeatureVariations.
   * Different outcomes may conservatively separate equivalent lookup sets. */
  hb_vector_t<unsigned> lookup_conditions[2];

  bool equal (const hb_ot_shape_plan_key_t *other)
  {
    return variations_index[0] == other->variations_index[0] &&
           variations_index[1] == other->variations_index[1] &&
           lookup_conditions[0] == other->lookup_conditions[0] &&
           lookup_conditions[1] == other->lookup_conditions[1];
  }
};
```

There are two of each, one for GSUB and one for GPOS. `variations_index` is the number of the FeatureVariations record that applies. `FeatureVariations::find_index` (`hb-ot-layout-common.hh:5969`) tests the records’ condition sets in order and stops at the first that matches, as the specification says it should. If none matches, or the table has no FeatureVariations, the index is `NOT_FOUND_INDEX`, `0xFFFFFFFF`. A build with `HB_NO_VAR` always gets that (`hb-ot-layout-gsubgpos.hh:6527`).

`featvar.ttf` has two records, made by fontTools’ `addFeatureVariations`. Record 0 applies from normalized weight 0.6 to 1 (user weights 700 to 900) and swaps `I` for `V`. Record 1 applies from 0.4 to 0.59 (600 to 695) and swaps `I` for `H`. Below 600 neither applies:

```shape
featvar.ttf  I  --language=en  --variations=wght=400
featvar.ttf  I  --language=en  --variations=wght=500
featvar.ttf  I  --language=en  --variations=wght=600
featvar.ttf  I  --language=en  --variations=wght=695
featvar.ttf  I  --language=en  --variations=wght=700
featvar.ttf  I  --language=en  --variations=wght=900
```

Those six positions make three keys: `NOT_FOUND_INDEX` for 400 and 500, 1 for 600 and 695, 0 for 700 and 900. So they make three plans, however many positions in between are shaped (the C program confirms this too). Each plan’s map holds the lookups its record chose, which a trace shows as the lookups that run:

```trace
font: featvar.ttf
text: I
options: --language=en --variations=wght=650
from: start table GSUB
to: end table GSUB
```

```trace
font: featvar.ttf
text: I
options: --language=en --variations=wght=800
from: start table GSUB
to: end table GSUB
```

At weight 650 the plan made for record 1 runs lookup 0. At 800 the plan for record 0 runs lookup 1. At 400 the plan has no lookups at all, since `rvrn` has none by default, and GSUB starts and ends with nothing in between:

```trace
font: featvar.ttf
text: I
options: --language=en --variations=wght=400
from: start table GSUB
to: end table GSUB
```

<span class="screen-only">Here the slider moves across all of them.</span><span class="print-only">Here are four of them, at weights 400, 600, 700 and 900.</span> Under each frame, the glyph name says which plan made it:

```draw
font: shape-plans-and-their-cache/featvar.ttf
text: I
slider: wght 100 900 25
start: 400
print: 400 600 700 900
```

#### Lookup variations

The second half of the key is newer. `NEWS` for 14.6.0 says “Support `FeatureVariations` 1.1 lookup variations”. HarfBuzz reads them from an array of `LookupVariationRecord`s that follows the ordinary records in a FeatureVariations table of version 1.1 or later (`hb-ot-layout-common.hh:5957`). With these, a feature’s lookups aren’t replaced wholesale. Each record gives one feature a list of lookup groups, each with a condition of its own, and the feature gets the groups whose conditions are true, plus its default lookups if a flag says so (`:5784`). Any number of conditions can be true at once, so one record index can’t describe the result.

So the key records which conditions are true. `collect_lookup_conditions` (`hb-ot-layout-common.hh:5994`) goes through every lookup variation record in the table, evaluates each distinct condition once, and keeps the offsets of the true ones, sorted, so that two positions with the same true conditions give equal lists. A group with no condition always applies, and isn’t recorded (`:5716`). The comment in the key admits what this costs: two positions whose true conditions differ get different plans, even if they would end up with the same lookups. And it is every condition in the table, not only those of the features this script and language use.

None of the book’s test fonts uses lookup variations: the fontTools that builds them, 4.38, can’t write them.

> For type designers: every distinct outcome of FeatureVariations is a separate plan, and a plan is the whole compiled map, not just the feature that varied. A font with one `rvrn` record can have two plans for each script, language and feature set: one inside the record and one outside it. A font that steps a substitution through twenty ranges of an axis has twenty-one, and an application that animates the axis builds each of them once, at the moment the position first crosses into its range. That’s fine for a handful of records. A font that needs many, perhaps generated by a tool that splits the design space into small boxes, makes many plans and makes every shaping call test more conditions, as the next section explains.

### The shaper

The last part of the key is the backend, compared by its function (`shaper_func`), not by the list of names that chose it. So `--shapers=ot` and the default list share plans, and a name the build doesn’t have, at the front of a list, changes nothing. [hb_shape and its backends](hb_shape-and-its-backends.html#asking-for-a-backend-by-name) has the details.

### What the key leaves out

| Left out | Why it can be | Where it is used instead |
|---|---|---|
| the font: size, scale, ppem, point size, synthetic bold and slant, font functions | the plan is per face | when the plan is run |
| the variation coordinates themselves | only the FeatureVariations outcome changes the plan | font functions, GDEF and GPOS deltas, when the plan is run |
| feature ranges | the plan needs only to know which features are global | `hb_ot_shape_setup_masks`, each run |
| the text, its context, buffer flags, cluster level | none of them changes which lookups apply | the pipeline |

## The cache

### Where it lives

The cache is two fields of the face (`hb-face.hh:67`):

```c++
struct plan_node_t
{
  hb_shape_plan_t *shape_plan;
  plan_node_t *next;
};
hb_atomic_t<plan_node_t *> shape_plans;
/* One-entry cache of the last plan looked up, so repeated shaping with the
 * same key hits without walking the list.  Nodes are never freed before the
 * face, so a cached pointer stays valid. */
hb_atomic_t<plan_node_t *> last_shape_plan;
```

`shape_plans` is a singly linked list, newest first. `last_shape_plan` points at whichever node was found or added most recently.

### Looking up, and adding

`hb_shape_plan_create_cached2` (`hb-shape-plan.cc:538`) is the whole cache. Trimmed of its debug messages:

```c++
retry:
  hb_face_t::plan_node_t *cached_plan_nodes = face->shape_plans;

  bool dont_cache = !hb_object_is_valid (face);

  if (likely (!dont_cache))
  {
    hb_shape_plan_key_t key;
    if (!key.init (false, face, props, user_features, num_user_features,
                   coords, num_coords, shaper_list))
      return hb_shape_plan_get_empty ();

    hb_face_t::plan_node_t *cached = face->last_shape_plan.get_acquire ();
    if (cached && cached->shape_plan->key.equal (&key))
      return hb_shape_plan_reference (cached->shape_plan);

    for (hb_face_t::plan_node_t *node = cached_plan_nodes; node; node = node->next)
      if (node->shape_plan->key.equal (&key))
      {
        face->last_shape_plan.set_release (node);
        return hb_shape_plan_reference (node->shape_plan);
      }
  }

  hb_shape_plan_t *shape_plan = hb_shape_plan_create2 (face, props,
                                                       user_features, num_user_features,
                                                       coords, num_coords,
                                                       shaper_list);
  if (unlikely (dont_cache))
    return shape_plan;

  hb_face_t::plan_node_t *node = (hb_face_t::plan_node_t *) hb_calloc (1, sizeof (hb_face_t::plan_node_t));
  if (unlikely (!node))
    return shape_plan;

  node->shape_plan = shape_plan;
  node->next = cached_plan_nodes;

  if (unlikely (!face->shape_plans.cmpexch (cached_plan_nodes, node)))
  {
    hb_shape_plan_destroy (shape_plan);
    hb_free (node);
    goto retry;
  }
  face->last_shape_plan.set_release (node);

  return hb_shape_plan_reference (shape_plan);
```

A key is built on every call, cached or not. With `copy` false, it points at the caller’s features instead of copying them, so a lookup allocates nothing for them. But it does evaluate FeatureVariations, for both tables, every time: `find_index` until a record matches, and for version 1.1 every distinct lookup condition. For a font without FeatureVariations that is next to nothing. For one with many records or conditions, it is work done on every shaping call, before the cache is even looked at. The backend is chosen again too, though after the first time that is only a test of a stored pointer.

The lookup itself is two steps. First the last plan, then the list from its head. Each comparison is `key.equal`, which compares properties first, and so fails fast for a different script or direction.

On a miss, the new plan is built, and then a node is put at the head of the list with one compare-and-swap: “if the head is still the one I started from, make it my node”. If another thread has added a plan since this one read the head, the swap fails, and the thread throws away the plan it built and starts again from `retry`. That second time round it walks the new list, and if the other thread’s plan was the one it wanted, it finds it there. So two threads that need the same plan at the same moment both build it, but only one copy ends up in the list. It is the same trade as the lazy table loaders’ in [Blobs, faces and lazy tables](blobs-faces-and-lazy-tables.html#loading-without-a-lock): occasional duplicate work, in exchange for no lock on the path every shaping call takes. A thread that loses the race to a *different* plan throws its own away too, and builds it again.

Only the head is ever written, and nodes are never removed, so a thread walking the list can never meet a node that is being changed or freed. That is why the walk needs no lock either.

### The last plan

`last_shape_plan` arrived in 15.1.0, whose `NEWS` lists “speed up shaping on faces with many shape plans”. Most programs shape run after run with the same key, and a repeat now costs one comparison instead of a walk of the list. It is one entry for the whole face, shared by every thread. Two threads shaping with different keys on one face, or one program alternating between two kinds of run, replace each other’s entry, and walk the list on most calls, which is what happened before 15.1.0 (inferred). Finding a plan in the list doesn’t move it to the front.

### Never pruned

Nothing removes a plan from the cache. The list is freed only in `hb_face_destroy` (`hb-face.cc:607`), which drops the face’s reference to each plan. There is no limit on its length, no eviction, and no API to empty it.

The plan an application gets back has its own reference, which it releases with `hb_shape_plan_destroy`, as `hb_shape_full` does at once. A plan the application keeps can outlive its face, but its `face_unsafe` then points at freed memory, so it shouldn’t be used (inferred).

### The empty plan

When a plan can’t be made, these functions return the **empty plan**, `hb_shape_plan_get_empty` (`hb-shape-plan.cc:306`): the shared Null object, all zeros, which `hb_object_is_valid` rejects. Running it returns false (`:425`) and leaves the buffer as it was. Its shaper name is null. It is what `hb_shape_plan_create2` returns for an invalid direction (`:255`), when no backend will take the face, and when it runs out of memory, and what `create_cached2` returns when no key can be made.

The cache has one more case. A face that isn’t a valid object, which means the empty face, `hb_face_get_empty`, is never cached (`dont_cache`), and every call goes straight to `hb_shape_plan_create2`. That doesn’t help much. The empty face’s per-shaper data loaders are inert, so no backend can make data for it, not even `ot`, and the key can’t be made. Shaping a font made from `hb_face_get_empty ()` fails: `hb_shape_full` returns false and the buffer stays Unicode. A face made from an empty blob is a valid face with no tables, and shapes every character to glyph 0. (Both were checked with a C program, since `hb-shape` can’t open the empty face.)

## Making plans directly

The public API has four functions that make plans:

| Function | Since | Coordinates | Cached |
|---|---|---|---|
| `hb_shape_plan_create` | 0.9.7 | none | no |
| `hb_shape_plan_create2` | 1.4.0 | yes | no |
| `hb_shape_plan_create_cached` | 0.9.7 | none | yes |
| `hb_shape_plan_create_cached2` | 1.4.0 | yes | yes |

The versions without coordinates pass none, so they make the plan for the default position. The uncached ones make a new plan on every call, with its own copy of the features, and put it nowhere: two calls with the same arguments give two plans. `hb_shape_plan_create2` (`hb-shape-plan.cc:240`) is the function that actually builds one, cached or not. It makes the face immutable (`:267`, see [Blobs, faces and lazy tables](blobs-faces-and-lazy-tables.html#immutability)), makes the key with a copy of the features, and calls `ot.init0` (`:280`), which runs the planner and compiles the map (`hb-ot-shape.cc:227`).

A plan is run with `hb_shape_plan_execute`, and it can be looked at: `hb_shape_plan_get_shaper` gives the backend’s name, `hb_ot_shape_plan_collect_lookups` the lookups in its map, and `hb_ot_shape_plan_get_feature_tags` (since 10.3.0) the features it turned on. `hb_ot_shape_glyphs_closure` uses the cache too, to find the lookups a text could use (`hb-ot-shape.cc:1310`).

> For programmers: `hb_shape_plan_execute` takes the features again, and they should be the ones the plan was made with. The global ones were compiled into the plan and are ignored when it runs, while the ranges and values of the others are read from the features passed to `execute`. A feature the plan wasn’t made with has no mask bits and does nothing. A value bigger than the plan allowed for loses its high bits. `execute` also asserts that the font’s face is the plan’s face and that the buffer’s properties are the plan’s (`hb-shape-plan.cc:428`). `hb_shape_full` gets all of this right by construction.

## What it means

### For applications

Plans are shared by every run that shapes the same face with the same direction, script and language object, the same list of features in the same order with the same values and the same global-ness, the same FeatureVariations outcome, and the same backend. In ordinary text that is a handful of plans per face: one per script and language in use, times the feature settings in use.

The cache grows when those multiply. Each distinct language tag is a distinct plan, so an application that passes BCP 47 tags with regions and variants through to HarfBuzz gets a plan per tag, not per language system. Each distinct feature list is a plan, so an application that builds its list in different orders for the same settings, or adds `liga` and `kern` explicitly in some places and not others, gets more plans than it needs. And each FeatureVariations outcome is a plan per everything else. Since plans live as long as the face, a long-lived face, such as one kept in a font cache for a whole session, keeps every plan it ever made (inferred).

Two things help. Building the feature list the same way each time, without reordering entries that share a tag, keeps the keys equal. For a one-off combination that won’t recur, `hb_shape_plan_create2` with `hb_shape_plan_execute` makes a plan that is freed when it is released, instead of one that stays in the cache.

Feature ranges cost nothing here: an editor that turns features on and off over spans gets one plan per set of tags and values, however the spans move.

### For type designers

What the cache sees of a font is its FeatureVariations. A plan is built the first time each record, or each set of true lookup conditions, is reached, and kept. A few records along an axis are cheap. Many records make many plans, each a full compile of every feature’s lookups, and make every shaping call evaluate the conditions before it can find its plan. Records whose substitutions are identical still count separately, since the key holds the index, not the substitutions.

Nothing else about a variable font reaches the plan: deltas, metrics and outlines are read from the font while the plan runs.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-shape-plan.hh` | `hb_shape_plan_key_t` and `hb_shape_plan_t` |
| `src/hb-shape-plan.cc` | the key (`init`, `user_features_match`, `equal`), the four create functions, the empty plan, `execute`, and the cache in `hb_shape_plan_create_cached2` |
| `src/hb-face.hh`, `src/hb-face.cc` | the cache’s two fields, and freeing it in `hb_face_destroy` |
| `src/hb-ot-shape.hh` | `hb_ot_shape_plan_key_t` and `hb_ot_shape_plan_t` |
| `src/hb-ot-shape.cc` | `hb_ot_shape_plan_t::init0`, the user features in the planner, and `hb_ot_shape_setup_masks` |
| `src/hb-ot-layout-common.hh` | `FeatureVariations::find_index`, `collect_lookup_conditions`, and the 1.1 records |
| `src/hb-ot-layout.cc` | `_hb_ot_layout_table_get_feature_variations_state`, which the key calls |
| `src/hb-buffer.cc` | `hb_segment_properties_equal` |

Building HarfBuzz with `HB_DEBUG_SHAPE_PLAN` defined prints a message from the cache on every lookup: “fulfilled from last-plan cache”, “fulfilled from cache” or “inserted into cache”. The book’s build doesn’t, so those messages can’t be shown here.

## In short

* A shape plan is made for a face, not a font, and holds everything that can be decided before the text is seen: the script shaper, the feature masks, and the lookups in stages.
* The key is the segment properties, the user features, the FeatureVariations outcome, and the backend.
* Features match on tag, value and whether they are global, in order. Their ranges aren’t in the key: they are applied as masks every time the plan runs.
* The coordinates aren’t in the key either: only the index of the FeatureVariations record that applies and, for version 1.1 lookup variations, which conditions are true.
* The cache is a list on the face, grown with a compare-and-swap and read without a lock, with a one-entry fast path for the last plan. Nothing is ever removed until the face is destroyed.
* The empty plan stands for every failure, and running it returns false. The empty face can’t be shaped at all.
