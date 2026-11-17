# Fonts as bytes

A font file is a few kilobytes or megabytes of numbers. Most programs that read a binary format parse it: they walk through the bytes once and build objects in memory. HarfBuzz doesn’t. It keeps the font’s bytes as they are, and describes their layout with C++ structs. To read a table, it points the right struct at the right byte and reads the fields where they sit. Nothing is copied, nothing is allocated, and a table that is never used is never touched.

The [GSUB chapter](gsub.html) previewed this in two paragraphs. This chapter is the full account: how HarfBuzz finds a table in a file, the types every table is built from, how a struct says how big it is, what HarfBuzz reads when an offset is zero or an index is out of range, and how one description of a table serves every job HarfBuzz does with it. What makes it *safe* to read untrusted bytes this way is the sanitizer, the subject of the [next chapter](trust-nothing-the-sanitizer.html). Here we take its work for granted.

The examples use a small test font, built from `fonts/fonts-as-bytes/bytes.fea`, and copies of it with one field changed by hand. Every shaping result and `hb-info` listing on this page was produced by running HarfBuzz {{hb}} on those fonts when the page was built. The byte dumps were not: a short Python script made them.

## A font file, from the top

An OpenType font is an **sfnt**: a short header, a directory of tables, and the tables. Each directory entry, a **table record**, gives a table’s four-letter tag, a checksum, and where the table is and how long. Here are the first bytes of the test font, `bytes.ttf`, with only the first record shown in full. They were printed by `fonts/fonts-as-bytes/dump.py`, which reads the file with Python’s `struct` module, not with HarfBuzz, using the field names of HarfBuzz’s structs:

```
── OpenTypeOffsetTable (at 0x0000 in the file)
0000  00 01 00 00  sfnt_version (0x00010000: TrueType outlines)
0004  00 0b        tables.len = 11 (numTables)
0006  00 80        tables.searchRange = 128
0008  00 03        tables.entrySelector = 3
000a  00 30        tables.rangeShift = 48
000c  47 53 55 42  tables[0].tag = 'GSUB'
0010  20 e8 25 e8  tables[0].checkSum
0014  00 00 04 e0  tables[0].offset = 1248
0018  00 00 00 68  tables[0].length = 104
001c  4f 53 2f 32  tables[1].tag = 'OS/2'
002c  63 6d 61 70  tables[2].tag = 'cmap'
003c  67 6c 79 66  tables[3].tag = 'glyf'
004c  68 65 61 64  tables[4].tag = 'head'
005c  68 68 65 61  tables[5].tag = 'hhea'
006c  68 6d 74 78  tables[6].tag = 'hmtx'
007c  6c 6f 63 61  tables[7].tag = 'loca'
008c  6d 61 78 70  tables[8].tag = 'maxp'
009c  6e 61 6d 65  tables[9].tag = 'name'
00ac  70 6f 73 74  tables[10].tag = 'post'
```

And here is the struct HarfBuzz lays over them, from `hb-open-file.hh:80` (trimmed to its fields):

```c++
typedef struct OpenTypeOffsetTable
{
  /* … */
  protected:
  Tag		sfnt_version;	/* '\0\001\0\00' if TrueType / 'OTTO' if CFF */
  BinSearchArrayOf<TableRecord>
		tables;
  public:
  DEFINE_SIZE_ARRAY (12, tables);
} OpenTypeFontFace;
```

`TableRecord` is `Tag tag`, `CheckSum checkSum`, `Offset32 offset` and `HBUINT32 length`, 16 bytes (`hb-open-file.hh:54`). `BinSearchArrayOf` is an array whose count is followed by `searchRange`, `entrySelector` and `rangeShift`, values precomputed for a binary search. HarfBuzz never reads them. The header type, `BinSearchHeader`, converts itself to a number by returning only its `len` (`hb-open-type.hh:1111`), so the generic sorted array uses the whole 8-byte header as its count.

HarfBuzz can list the directory itself:

```info
bytes.ttf  --list-tables
```

### Finding a table

When something asks a face for a table, `_hb_face_for_data_reference_table` (`hb-face.cc:185`) finds the face in the file, finds the record by its tag, and returns a **sub-blob**: a view of just those bytes, sharing the file’s memory. Blobs are the subject of [blobs, faces and lazy tables](blobs-faces-and-lazy-tables.html).

The search makes one concession to real fonts (`hb-open-file.hh:100`). The specification says records are sorted by tag, but some fonts’ aren’t, and other software reads them anyway. So HarfBuzz searches a directory of fewer than 16 tables from the start, and uses binary search, which needs sorting, only for 16 or more.

> For type designers: a font with 16 or more tables must have its directory sorted by tag, as the specification says, or HarfBuzz may not find some of its tables. Sorting is by the tag’s bytes, so uppercase tags such as `GSUB` and `OS/2` come before lowercase ones such as `cmap`, as in the listing above. Font compilers do this for you.

If the tag isn’t there, the search gives the index `0xFFFF`, and the array returns its **Null** record for it, whose offset and length are zero. A sub-blob of length zero is the empty blob. So a missing table is an empty blob, not an error, and whatever reads it gets the table’s Null object (below). A record that runs past the end of the file is cut short there (`hb-blob.cc:175`).

### Collections and resource forks

The first four bytes of the file say what the rest is. `OpenTypeFontFile` (`hb-open-file.hh:485`) is a union of the possible layouts, chosen by those bytes:

| First four bytes | What the file is | Faces |
|---|---|---|
| `00 01 00 00` | OpenType with TrueType outlines | 1 |
| `OTTO` | OpenType with CFF or CFF2 outlines | 1 |
| `true`, `typ1` | old Apple TrueType and Type 1 sfnts | 1 |
| `ttcf` | a TrueType Collection | one for each directory |
| `00 00 01 00` | a Mac resource fork (a “dfont”) | one for each `sfnt` resource |
| anything else | not a font HarfBuzz knows | 0 |

A **TrueType Collection** holds several fonts that can share tables. Its header (`TTCHeaderVersion1`, `hb-open-file.hh:219`) is a list of 32-bit offsets, from the start of the file, to table directories like the one above, and two directories can point to the same table. fontTools made the test file `collection.ttc` from `bytes.ttf` and an altered copy of it:

```info
collection.ttc  --show-face-count
```

The **face index** chooses the face. HarfBuzz uses its low 16 bits for this (`hb-face.cc:170`); the upper bits ask `hb_font_create` for a named instance. [Blobs, faces and lazy tables](blobs-faces-and-lazy-tables.html#collections-and-the-face-index) shapes with both. A collection header with minor version 1 or more is an *extended* TTC, from the 5th edition of the ISO Open Font Format: a second list of directories follows the first, and HarfBuzz uses that one.

A **resource fork** is how classic Mac OS stored fonts, and a “dfont” is a resource fork in a plain file. It doesn’t begin with a tag at all, but with the offset of its resource data, which is usually 256, and HarfBuzz takes those four bytes as the dfont’s “tag”. `ResourceForkHeader` and the structs after it (`hb-open-file.hh:323`–`479`) walk the resource map to the `sfnt` resources, each a complete OpenType font. The face index counts those, and since a face’s table offsets count from the start of its resource, the face lookup returns a base offset to add.

A file whose first bytes match none of these has no faces. `hb_face_create` still returns a face, with no tables; `hb_face_create_or_fail` returns null (`hb-face.cc:290`).

## Numbers

Everything in an OpenType table is built from a few kinds of number, all stored big-endian (most significant byte first), and with no padding: a 32-bit number can start at any byte. HarfBuzz’s types for them are all one template, `NumType<BE, Type, Size>` (`hb-open-type.hh:57`):

| HarfBuzz type | OpenType type | Size |
|---|---|---|
| `HBUINT8`, `HBINT8` | `uint8`, `int8` | 1 |
| `HBUINT16`, `HBINT16` | `uint16`, `int16` | 2 |
| `HBUINT24` | `uint24` | 3 |
| `HBUINT32`, `HBINT32` | `uint32`, `int32` | 4 |
| `HBUINT64`, `HBINT64` | (none) | 8 |
| `FWORD`, `UFWORD` | `FWORD`, `UFWORD` | 2 |
| `F2DOT14`, `F16DOT16` | `F2DOT14`, `Fixed` | 2, 4 |
| `Tag` | `Tag` | 4 |
| `HBGlyphID16`, `HBGlyphID24` | glyph IDs, 16- and 24-bit | 2, 3 |
| `Offset16`, `Offset24`, `Offset32` | `Offset16`, `Offset24`, `Offset32` | 2, 3, 4 |

The number inside a `NumType` is a plain array of bytes (`HBInt`, `hb-algs.hh:138`), so the struct has an alignment of 1 and can sit at any address, which is what laying structs over a file needs. Reading one converts it: `HBUINT16` has an `operator unsigned ()` that puts the two bytes together the right way round. In an optimized build, on a compiler with byte-swapping built-ins, that is one load and one byte swap (`HB_FAST_NUM_ACCESS`); otherwise it is shifts and adds. Older HarfBuzz code called the byte-array type `BEInt`; in {{hb}} it is `HBInt`, with a flag for byte order.

There is an unsigned 24-bit type but no signed one. A comment at `hb-open-type.hh:123` explains why: the conversion relies on the compiler to extend the sign, and C++ has no 24-bit type to extend it from.

A few types add behaviour to a plain number. `Tag` converts to a `const char *` pointing at its own four bytes, which are *not* followed by a NUL, so the code prints tags with `"%.4s"`. `Index` (a 16-bit index into a list of scripts, features or languages) and `VarIdx` (a 32-bit index into an item variation store) each have a value that means “none”, `0xFFFF` and `0xFFFFFFFF`, which matters for Null objects below. The fixed-point types (`HBFixed`, `hb-open-type.hh:247`) refuse to convert to an integer, so an `F2DOT14` can’t be used as one by accident.

None of these structs can be made on its own. The array types declare `HB_DELETE_CREATE_COPY_ASSIGN` (`hb-meta.hh:221`), which deletes their default constructor and copying, and so does any struct that holds one. There is no way to make a Coverage table except by pointing at bytes that hold one.

## How big is a struct?

An OpenType table is full of arrays whose length is in the font, not in the code. C++ has no way to write that, so HarfBuzz declares each such array with one element:

```c++
  LenType	len;
  Type		arrayZ[HB_VAR_ARRAY];   /* HB_VAR_ARRAY is 1 */
```

Fields like this have names ending in `Z` (`arrayZ`, `bytesZ`), a reminder that C++ doesn’t know their length. It also means `sizeof` gives the wrong answer for nearly every table struct, so each struct says how big it is with one of the `DEFINE_SIZE_*` macros from `hb-machinery.hh:111`–`141`. Each declares some constants and, through a `static_assert`, makes the compiler check that the struct as declared matches the size the specification gives:

| Macro | For | Declares | Checks at compile time |
|---|---|---|---|
| `DEFINE_SIZE_STATIC (n)` | a fixed-size record | `static_size`, `min_size`, `null_size` = n, and `get_size ()` | `sizeof (*this) == n` |
| `DEFINE_SIZE_MIN (n)` | a struct whose size depends on its content | `min_size`, `null_size` = n | `sizeof (*this) >= n` |
| `DEFINE_SIZE_ARRAY (n, array)` | a header of n bytes, then an array | `min_size`, `null_size` = n | `sizeof (*this) == n + sizeof (array[0])`, and that the element type has a static size |
| `DEFINE_SIZE_UNION (n, member)` | a union of formats | `min_size`, `null_size` = n | that `u.member` is n bytes |
| `DEFINE_SIZE_UNBOUNDED (n)` | a struct with no meaningful empty form | `min_size` only | `sizeof (*this) >= n` |

So `TableRecord` says `DEFINE_SIZE_STATIC (16)`, and if someone added a field to it, the build would fail. `OpenTypeOffsetTable` says `DEFINE_SIZE_ARRAY (12, tables)`: four bytes of version, eight of `BinSearchHeader`, then the records. A Coverage table says `DEFINE_SIZE_UNION (2, format.v)`: all that every format of it has in common is its first two bytes.

The three constants have three jobs:

* **`min_size`** is how many bytes must be there before any field is read. The sanitizer checks that many first (`check_struct`), and a table blob shorter than its table’s `min_size` reads as that table’s Null object (`hb-array.hh:301`).
* **`static_size`** is the size of a record that is always the same size. Arrays need it, to find element *i* at `i * static_size` bytes on, so a variable-size type can’t be the element of a plain array: `DEFINE_SIZE_ARRAY` doesn’t compile.
* **`null_size`** is how many bytes of the Null pool the type’s Null object uses. A type with a `min_size` but no `null_size`, as `DEFINE_SIZE_UNBOUNDED` makes, is saying it can’t be Null (`hb-null.hh:60`–`64`).

### Walking past variable-size fields

Some tables put a field *after* a variable-length array. A lookup is `lookupType`, `lookupFlag`, an array of subtable offsets, and then, if the flag says so, a mark-filtering-set index. No struct field can be declared there, so `Lookup` reads it with `StructAfter` (`hb-ot-layout-common.hh:1315`):

```c++
const HBUINT16 &markFilteringSet = StructAfter<const HBUINT16> (subTable);
```

`StructAfter<T> (x)` is `StructAtOffset<T> (&x, x.get_size ())`: the `T` that starts where `x` ends. `StructAtOffset<T> (p, n)` is the most basic tool of all, a cast of “the bytes *n* on from *p*” to a `T` (`hb-machinery.hh:45`–`84`).

Fields added in later versions are declared anyway, and read only after a version check. A version 1.0 GSUB header is ten bytes, and 1.1 adds an offset to FeatureVariations. `GSUBGPOS` declares every field, says `DEFINE_SIZE_MIN (10)`, and reads `featureVars` only if the version is 1.1 or more (`hb-ot-layout-gsubgpos.hh:6485`): in a 1.0 table those bytes are whatever comes next.

## Offsets that know their targets

An OpenType table is a tree: a header points at lists, which point at records, which point at subtables. Each pointer is an **offset**, a number of bytes counted from the start of some other structure. In HarfBuzz, an offset is a number that also knows the type of what it points to:

```c++
template <typename Type, typename OffsetType, typename BaseType=void, bool has_null=true>
struct OffsetTo : Offset<OffsetType, has_null>
{
  /* … */
  const Type& operator () (const void *base) const
  {
    if (unlikely (this->is_null ())) return *_hb_has_null<Type, has_null>::get_null ();
    return StructAtOffset<const Type> (base, *this);
  }
  /* … */
  friend const Type& operator + (const Base &base, const OffsetTo &offset) { return offset ((const void *) base); }
  /* … */
};
```

That is `hb-open-type.hh:410`–`446`, much trimmed. `Offset16To<Coverage>` is the same with a 16-bit offset. The `operator +` lets the code write what the specification says. Here are two lines of `SingleSubstFormat1_3::apply` (`OT/Layout/GSUB/SingleSubstFormat1.hh:206`):

```c++
unsigned int index = (this+coverage).get_coverage (glyph_id);
if (index == NOT_COVERED) return_trace (false);
```

`this` is the subtable, `coverage` is its offset field, and `this+coverage` is the Coverage table, as a `const Coverage &`. The type comes from the offset’s declaration; no cast is written.

The code always names the base, because OpenType counts offsets from different places, and only the code holding the offset knows which. A coverage offset counts from the start of its subtable, an offset in a ScriptList from the start of the ScriptList, a Device-table offset in a GPOS value record from the start of the *subtable* that holds the record, and a TTC’s directory offsets from the start of the file. HarfBuzz has types for some of these patterns:

* `List16OfOffsetTo<Type, OffsetType>` (`hb-open-type.hh:857`) is an array of offsets counted from the start of the array itself, which is what the LookupList is. Its `operator []` follows the offset, so `lookupList[i]` is the *i*th Lookup, not the *i*th number.
* `RecordListOf<Type>` (`hb-ot-layout-common.hh:955`) is the same for an array of tag-and-offset records, such as the ScriptList and FeatureList.
* The `BaseType` parameter can name a type that the base must be. GPOS uses a dummy type, `ValueBase` (`OT/Layout/GPOS/ValueFormat.hh:12`), for Device-table offsets, so that only a pointer that has been declared to be a value record’s base can be added to one, and passing `this` by mistake doesn’t compile.

### Zero means nothing, except when it doesn’t

An offset of zero would point at the base itself, which is never what a font means. So OpenType uses zero for “there is no table here”, and `OffsetTo` follows it. A zero offset doesn’t give a pointer to the base. It gives the target type’s **Null object**: a read-only, empty instance of the type, which every method can be called on. The code that follows the offset doesn’t check for zero. It just uses what it gets.

Not every offset may be null. In a resource fork, for example, an offset of zero is a real offset to the first resource. For those, HarfBuzz has `NNOffsetTo`, `NNOffset16To` and the rest (“non-null”, `hb-open-type.hh:545`), where `has_null` is false and zero means zero.

A nullable offset to a type that can’t be Null doesn’t compile. A `static_assert` in `OffsetTo` (`hb-open-type.hh:416`) refuses one to any type with a `min_size` but no `null_size`, such as `UnsizedArrayOf`, whose length the struct can’t know. Its Null object would have no safe size, so an offset that might produce one isn’t allowed.

## Arrays

There are several kinds of array, because OpenType stores lengths in several ways:

| HarfBuzz type | How the length is stored | Used for, for example |
|---|---|---|
| `ArrayOf<Type, LenType>`, `Array16Of`, `Array24Of`, `Array32Of` | a count, then the elements | most arrays |
| `SortedArrayOf`, `SortedArray16Of` and so on | the same, sorted, with `bsearch` and `bfind` | Coverage format 1 glyphs, range records |
| `BinSearchArrayOf` | a count and the three search fields | the table directory, `kerx` format 0 pairs |
| `HeadlessArrayOf`, `HeadlessArray16Of` | a count that includes a first element that isn’t stored | a ligature’s components |
| `ArrayOfM1` | the count minus one | Mac resource maps |
| `UnsizedArrayOf` | not stored: the caller supplies it | arrays sized by a field elsewhere, such as `hmtx` |
| `SortedUnsizedArrayOf` | the same, sorted | |
| `VarSizedBinSearchArrayOf` | a header giving the size and number of elements | AAT lookup tables |
| `List16OfOffsetTo`, `Array16OfOffset16To` and so on | a count, then offsets to the elements | the LookupList, a lookup’s subtables |

They share one rule: indexing past the end doesn’t read past the end. `ArrayOf::operator []` checks the index against `len` and returns `Null (Type)` if it is too big (`hb-open-type.hh:719`), and so do the other sized arrays. `UnsizedArrayOf` doesn’t know its length, so it can’t check, and its users have to; reading `arrayZ` directly skips the check too.

`HeadlessArrayOf`, the GSUB chapter’s ligature `component`, is indexed from 1. `VarSizedBinSearchArrayOf` (`hb-open-type.hh:1168`) is for AAT lookups, where the element size is in the font, and a last element of `0xFFFF`s is a terminator that isn’t counted.

### A Coverage table, byte by byte

The test font’s first lookup is a single substitution that turns `a` into `a.alt1` and `e` into `e.init`. Since the two glyphs move by different amounts, feaLib stored it as format 2, a list of output glyphs. Here are its bytes, made by the same script as before; offsets are counted from the start of GSUB:

```
── SingleSubstFormat2 (lookup 0's subtable, at 0x0048 in GSUB)
0048  00 02        format = 2
004a  00 18        coverage = 0x0018   → Coverage at 0x0060
004c  00 02        substitute.len = 2
004e  00 0d        substitute[0] = glyph 13
0050  00 10        substitute[1] = glyph 16

── CoverageFormat1 (at 0x0060 in GSUB)
0060  00 01        coverageFormat = 1
0062  00 02        glyphArray.len = 2
0064  00 02        glyphArray[0] = glyph 2
0066  00 03        glyphArray[1] = glyph 3
```

The structs for these are, with their methods left out:

```c++
template <typename Types>
struct SingleSubstFormat2_4
{
  HBUINT16      format;
  typename Types::template LOffsetTo<Coverage>
                coverage;
  typename Types::template ArrayOf<typename Types::HBGlyphID>
                substitute;
  DEFINE_SIZE_ARRAY (2 + Types::LOffset::static_size + Types::HBUINT::static_size, substitute);
};

template <typename Types>
struct CoverageFormat1_3
{
  HBUINT16      coverageFormat;
  typename Types::template SortedArrayOf<typename Types::HBGlyphID>
                glyphArray;
  DEFINE_SIZE_ARRAY (2 + Types::HBUINT::static_size, glyphArray);
};
```

With `SmallTypes` (explained at the end of this chapter), `LOffsetTo<Coverage>` is a 16-bit offset, `ArrayOf` has a 16-bit count, and a glyph ID is 16 bits, so the struct fields line up with the bytes one for one. Now follow `e`, glyph 3, through the lookup:

1. The subtable is at 0x48. `this+coverage` adds the offset, 0x18, to the subtable’s address and gets the `Coverage` at 0x60.
2. `Coverage::get_coverage` reads the first two bytes, `00 01`, and switches to format 1 (`OT/Layout/Common/Coverage.hh:87`).
3. `CoverageFormat1_3::get_coverage` calls `glyphArray.bfind (3)`, a binary search of the sorted array. It finds glyph 3 at index 1. That index, the **coverage index**, is what Coverage tables are for: it says which entry of the subtable’s own arrays belongs to this glyph.
4. Back in the subtable, `substitute[1]` checks 1 against `substitute.len`, 2, and reads `00 10`: glyph 16, `e.init`.

At no point did HarfBuzz make a list of the covered glyphs, or allocate anything. Every step was arithmetic on the address of the font’s bytes. (The set digests of the GSUB chapter are a cache in front of this code, not a replacement for it.)

Format 2 stores ranges instead: `RangeRecord`s of a first glyph, a last glyph and the coverage index of the first. `CoverageFormat2_4::get_coverage` binary-searches them for the range that holds the glyph. If there is none, `bsearch` returns the Null `RangeRecord`, and the code goes on to check `range.first <= range.last` (`OT/Layout/Common/CoverageFormat2.hh:61`). That works only because the Null `RangeRecord` isn’t all zeros, which is the next subject.

## Null objects

The Null pool is 640 bytes of zeros, `_hb_NullPool` (`hb-null.hh:40`, defined in `hb-static.cc:51`). `Null (T)` returns those bytes as a `const T &` (`hb-null.hh:110`–`124`):

```c++
template <typename Type>
struct Null {
  static Type const & get_null ()
  {
    static_assert (hb_null_size (Type) <= HB_NULL_POOL_SIZE, "Increase HB_NULL_POOL_SIZE.");
    return *reinterpret_cast<Type const *> (_hb_NullPool);
  }
};
```

Types share the one pool: the Null `GSUB`, the Null `Coverage` and the Null `Lookup` are at the same address. The `static_assert` makes sure the pool is big enough for every type ever used as Null.

### Why zeros are an empty table

In OpenType, zero bytes nearly always read as nothing. Every count is zero, so every array is empty. Every offset is zero, so following one gives another Null object. Every format and version field is zero, and most tables have no format 0 or version 0, so their switches take the `default` case. As long as each method’s `default` case does the empty thing, a Null table behaves like a table with nothing in it. A Null `Coverage` has format 0, for which `get_coverage` returns `NOT_COVERED` (`OT/Layout/Common/Coverage.hh:96`). A Null GSUB has version 0, so `has_data ()` is false, and it has no scripts, features or lookups. A Null `Lookup` has no subtables.

So a font with no GSUB, a GSUB with no lookups, and a lookup whose coverage offset is zero all go down the same code. The shaping code doesn’t check whether the font has a GSUB, and HarfBuzz’s table code has hardly an `if (table)` in it.

Here it is happening. `bytes.ttf` has two lookups in its `liga` feature: lookup 0 is the format 2 substitution above, and lookup 1 turns `x` into `f`. `null-coverage.ttf` is a copy with lookup 0’s coverage offset, at 0x4a, changed to zero. `unknown-format.ttf` is a copy with the Coverage table’s format changed from 1 to 9, a format that doesn’t exist:

```shape
bytes.ttf  aex
null-coverage.ttf  aex
unknown-format.ttf  aex
```

In both copies, lookup 0 now covers nothing, and lookup 1 still works. The null offset gave the Null Coverage. The unknown format went to the `default` cases. A table format from the future, which the code doesn’t know, is meant to be handled the same way: the sanitizer passes unknown formats (`Coverage.hh:76`), and every reader of them returns nothing.

Compare a third copy, `outside.ttf`, whose coverage offset is changed to 0xFFF0, far past the end of the 104-byte GSUB:

```shape
outside.ttf  aex
```

Now neither lookup applies, because HarfBuzz has thrown away the whole GSUB table. An offset that points outside its table can’t be made safe by a Null object, because the code would follow it into memory that isn’t the font’s. The sanitizer finds such offsets when the table is loaded, and since HarfBuzz 12.3 it rejects the whole table when it finds one. Why it does that, and not something gentler, is the subject of the [next chapter](trust-nothing-the-sanitizer.html).

### When a zero would mean something

The “zero is nothing” rule has exceptions, where a field’s zero value means something real. For those types, HarfBuzz defines a Null object with other bytes, using `DECLARE_NULL_NAMESPACE_BYTES` in the type’s header and `DEFINE_NULL_NAMESPACE_BYTES` in `hb-static.cc:54`–`61`, which specializes `Null<T>` to point at those bytes instead of the pool. In {{hb}} there are eight:

| Type | Null bytes | Why zeros would be wrong |
|---|---|---|
| `OT::Index` | `FF FF` | Index 0 is a real feature, script or language. `0xFFFF` is `NOT_FOUND_INDEX`. |
| `OT::VarIdx` | `FF FF FF FF` | Index 0 is a real delta set. `0xFFFFFFFF` is “no variation”. |
| `OT::LangSys` | `00 00 FF FF 00 00` | Its second field is the required feature index; zero would make feature 0 required for every script with no default language system. |
| `OT::RangeRecord` | `01 00 …` | A zero range is glyph 0 to glyph 0: the Null record would cover `.notdef`. With a first byte of 1, it runs from glyph 256 to glyph 0, which is nothing. |
| `OT::ClipRecord` (COLR) | `01 00 …` | The same, for a range of glyphs given a clip box. |
| `OT::CmapSubtableLongGroup` | start 1, end 0, glyph 0 | A zero group would map U+0000 to glyph 0. |
| `AAT::SettingName` | `FF FF FF FF` | A real setting and name ID would otherwise be 0. |
| `AAT::Lookup` | `FF FF …` | Format 0 has a value for *every* glyph, so a zero Null lookup would cover every glyph and read past the end of the pool. Format `0xFFFF` covers nothing. |

The `RangeRecord`’s Null is nine bytes, enough for the 24-bit kind, and is declared by hand (`OT/Layout/Common/RangeRecord.hh:88`), because the macro can’t yet handle a type two namespaces deep.

### Where the rule breaks

“Every default case does the empty thing” is a convention, not something the compiler checks. {{hb}} has at least one place where it doesn’t hold. `Coverage::get_population` counts a Coverage table’s glyphs, and for an unknown format, including the Null Coverage’s format 0, its `default` case returns `NOT_COVERED` (`Coverage.hh:138`), which is `0xFFFFFFFF`, not 0. `SingleSubstFormat1_3::sanitize` charges the sanitizer’s work budget half the population of its coverage (`OT/Layout/GSUB/SingleSubstFormat1.hh:125`), so that a tiny table can’t make it do a lot of work. With a null coverage offset, that charge is about two billion, the budget runs out, and the whole table is rejected. `null-coverage-f1.ttf` is `bytes.ttf` with lookup 1, a format 1 single substitution, given a null coverage offset:

```shape
null-coverage-f1.ttf  aex
```

Made to lookup 0, a format 2 subtable, the change switched off one lookup. Made to lookup 1, a format 1 subtable, it switches off all of GSUB. Real fonts don’t have null coverage offsets, so this is unlikely to matter, but it shows what holds the Null pattern together: every method of every type, in its `default` case.

### Crap: Null’s writable twin

`Null (T)` is `const`. Code with a *writable* struct, such as the subsetter, sometimes follows an offset or an index that isn’t there, and needs something writable back. It gets `Crap (T)` (`hb-null.hh:174`–`188`): a second 640-byte pool, into which the Null object’s bytes are copied each time. The name is spelt out in a comment, “Common Region for Access Protection”: writing there only stops a bug from doing damage elsewhere. Nothing correct relies on what is in it, which is why threads can share it without a lock. `CrapOrNull (T)` picks whichever fits the constness, and `hb_nonnull_ptr_t<T>` (`hb-null.hh:205`) is a pointer that reads as `Null (T)` when it is null; `hb_blob_ptr_t`, which holds a loaded table, keeps its blob in one.

## Dispatch contexts

HarfBuzz does many things with a GSUB table besides applying it. It checks it, works out which glyphs it can produce (closure, for the subsetter), collects the glyphs it mentions, asks whether a lookup would apply to a sequence, and copies what a subset font keeps. Each job walks the same tree: the LookupList, each Lookup, each subtable, through Extension subtables, into each format.

HarfBuzz writes the walk once and passes in the job. The job is a **context**, a struct whose `dispatch` method says what to do with each object it is handed, and every table struct with more than one format has a `dispatch` method that picks the format and hands it on. Here is `SingleSubst` (`OT/Layout/GSUB/SingleSubst.hh:27`–`41`):

```c++
template <typename context_t, typename ...Ts>
typename context_t::return_t dispatch (context_t *c, Ts&&... ds) const
{
  if (unlikely (!c->may_dispatch (this, &u.format.v))) return c->no_dispatch_return_value ();
  TRACE_DISPATCH (this, u.format.v);
  switch (u.format.v) {
  case 1: hb_barrier (); return_trace (c->dispatch (u.format1, std::forward<Ts> (ds)...));
  case 2: hb_barrier (); return_trace (c->dispatch (u.format2, std::forward<Ts> (ds)...));
#ifndef HB_NO_BEYOND_64K
  case 3: hb_barrier (); return_trace (c->dispatch (u.format3, std::forward<Ts> (ds)...));
  case 4: hb_barrier (); return_trace (c->dispatch (u.format4, std::forward<Ts> (ds)...));
#endif
  default:return_trace (c->default_return_value ());
  }
}
```

`u` is a union of the formats, each a struct that starts with the same two-byte format field, and `u.format.v` is that field. The `dispatch` doesn’t know what the context will do. It only knows how to find the right format. (`hb_barrier` keeps the compiler from reading ahead of the check on the format; it is the sanitizer’s business, and the next chapter’s.)

One level up, `SubstLookupSubTable::dispatch` (`OT/Layout/GSUB/SubstLookupSubTable.hh:49`) switches on the lookup type instead, which isn’t in the subtable but in the Lookup that holds it, so it is passed in. And `Lookup::dispatch` (`hb-ot-layout-common.hh:1338`) loops over the subtables:

```c++
for (unsigned int i = 0; i < count; i++) {
  typename context_t::return_t r = get_subtable<TSubTable> (i).dispatch (c, lookup_type, ds...);
  if (c->stop_sublookup_iteration (r))
    return_trace (r);
}
return_trace (c->default_return_value ());
```

`Lookup` is shared by GSUB and GPOS, so its array of subtable offsets is declared as plain `Offset16`s, with no target type. The caller says what they point to, `SubstLookupSubTable` or `PosLookupSubTable`, as the template argument `TSubTable`, and `get_subtable` casts the array to offsets of that type.

### The contexts

Every context derives from `hb_dispatch_context_t` (`hb-dispatch.hh:38`):

```c++
template <typename Context, typename Return=hb_empty_t, unsigned int MaxDebugDepth=0>
struct hb_dispatch_context_t
{
  /* … */
  template <typename T, typename F>
  bool may_dispatch (const T *obj HB_UNUSED, const F *format HB_UNUSED) { return true; }
  template <typename T, typename ...Ts>
  return_t dispatch (const T &obj, Ts&&... ds)
  { return obj.dispatch (thiz (), std::forward<Ts> (ds)...); }
  static return_t no_dispatch_return_value () { return Context::default_return_value (); }
  static bool stop_sublookup_iteration (const return_t r HB_UNUSED) { return false; }
  /* … */
};
```

This is the “curiously recurring template pattern”, as a comment in the file says: each context passes itself as `Context`, so the base calls the context’s own methods without virtual functions, and the compiler can inline the whole walk for each job. A context overrides what it needs: `dispatch` for what to do at a leaf, `return_t`, `default_return_value` for what an unknown format or an empty lookup gives, and `stop_sublookup_iteration` for whether one subtable’s result ends the loop over a lookup’s subtables.

The main contexts in {{hb}}:

| Context | At each subtable, it… | Returns | Stops when |
|---|---|---|---|
| `hb_sanitize_context_t` (`hb-sanitize.hh:123`) | checks it | `bool`, true by default | a check fails |
| `hb_ot_apply_context_t` (`hb-ot-layout-gsubgpos.hh:1127`) | applies it to the buffer | `bool`, false by default | a subtable applies |
| `hb_accelerate_subtables_context_t` (`:1419`) | records it, its `apply` function and its coverage digest | nothing | never |
| `hb_would_apply_context_t` (`:286`) | asks whether it would apply to a glyph sequence | `bool` | |
| `hb_closure_context_t`, `hb_closure_lookups_context_t` (`:68`, `:207`) | adds the glyphs it can produce, or the lookups it reaches | nothing | |
| `hb_collect_glyphs_context_t` (`:329`) | collects its input, context and output glyphs | nothing | |
| `hb_depend_context_t` (`:402`) | records glyph dependencies, for hb-depend | nothing | |
| `hb_subset_context_t` (`hb-subset.hh:40`) | writes its subset copy | `bool` | |

There are a dozen more: small questions about lookups in `hb-ot-layout-gsubgpos.hh` and `hb-ot-layout.cc`, subsetting helpers in `hb-ot-layout-common.hh`, the AAT apply context, and painting, closure and dependency contexts for COLRv1 paint graphs (`OT/Color/COLR/COLR.hh:65`). Writing a font is not among them. The serializer, `hb_serialize_context_t`, is not a dispatch context: tables have `serialize` methods that are called directly, and the subset context holds a serializer and walks the old table by dispatch, writing the new one as it goes.

### Choosing the method to call

The sanitizer walks *every* struct through `c->dispatch`, not only the leaves, so its `dispatch` has to call `sanitize` where a struct has one and the struct’s own `dispatch` where it doesn’t. It chooses at compile time (`hb-sanitize.hh:154`):

```c++
template <typename T, typename ...Ts> auto
_dispatch (const T &obj, hb_priority<1>, Ts&&... ds) HB_AUTO_RETURN
( obj.sanitize (this, std::forward<Ts> (ds)...) )
template <typename T, typename ...Ts> auto
_dispatch (const T &obj, hb_priority<0>, Ts&&... ds) HB_AUTO_RETURN
( obj.dispatch (this, std::forward<Ts> (ds)...) )
```

`hb_priority<1>` derives from `hb_priority<0>` (`hb-meta.hh:79`), so when both overloads compile, C++ prefers the first. When the struct has no `sanitize`, the first doesn’t compile and is quietly dropped, leaving the second. So `SingleSubst`, which has no `sanitize`, is sanitized through its `dispatch`, which picks the format, whose `sanitize` is called. The subset context does the same with `subset`, and the apply context uses the trick to prefer `apply (c, cache)` to `apply (c)`. The sanitizer also overrides `may_dispatch`, to check that the format field itself is inside the table before anything switches on it (`hb-sanitize.hh:136`).

### Dispatch once, not every glyph

Following the chain of `dispatch` calls through Lookup, Extension, lookup type and format for every glyph would be slow. So HarfBuzz walks it once per lookup, when the lookup’s accelerator is made (`hb-ot-layout-gsubgpos.hh:6197`). At each leaf, `hb_accelerate_subtables_context_t` stores the subtable’s address, a pointer to a function that calls that format’s `apply`, and a digest of its coverage (`:1562`). From then on, `accel.apply` in the GSUB chapter’s loop runs through that flat array, and the switches on lookup type and format aren’t run again while shaping.

> For programmers: a new operation over layout tables is a new context, derived from `hb_dispatch_context_t<YourContext, YourReturn>`, with a `default_return_value` and a `dispatch` that calls your method on each leaf. Every struct that already dispatches can then be walked by it; only the leaves need the new method.

## SmallTypes and MediumTypes

The structs above were templates on `Types`. That parameter is one of two structs in `hb-ot-dual.hh:38`–`73`, which bundle the widths of the basic fields:

| Member | `SmallTypes` | `MediumTypes` |
|---|---|---|
| `size` | 2 | 3 |
| `HBUINT` | `HBUINT16` | `HBUINT24` |
| `HBGlyphID` | `HBGlyphID16` | `HBGlyphID24` |
| `Offset`, `OffsetTo<T>` | 16-bit | 24-bit |
| `LOffset`, `LOffsetTo<T>` (“long”) | 16-bit | 32-bit |
| `ArrayOf<T>`, `SortedArrayOf<T>` | 16-bit count | 24-bit count |
| `large_int` | `uint32_t` | `uint64_t` |

`SmallTypes` is the OpenType everyone knows. `MediumTypes` is the “beyond 64k” extension in the 5th edition of the ISO Open Font Format, for fonts with more than 65,535 glyphs, supported by default since HarfBuzz 15.0. The same struct, with the same code, describes both. The `Coverage` union is:

```c++
union {
struct { HBUINT16 v; }        format;         /* Format identifier */
CoverageFormat1_3<SmallTypes> format1;
CoverageFormat2_4<SmallTypes> format2;
#ifndef HB_NO_BEYOND_64K
CoverageFormat1_3<MediumTypes>format3;
CoverageFormat2_4<MediumTypes>format4;
#endif
} u;
```

Coverage format 3 is format 1 with 24-bit glyph IDs and count, format 4 is format 2 likewise, and they are not separate code. The struct names say so: `CoverageFormat1_3` is “format 1, or 3”, and `LigatureSubstFormat1_2` “format 1, or 2”. The union turns the format number into a choice of types. A build with `HB_NO_BEYOND_64K` defined (or `HB_MINI`) leaves the wider formats out of every union, and they fall into the `default` cases like any unknown format.

Some beyond-64k tables are separate tables with uppercase tags, such as `GLYF` and `HMTX` beside `glyf` and `hmtx`. If the uppercase table has data, `hb_dual_accelerator_t` (`hb-ot-dual.hh:79`) loads the lowercase one from the empty face, so it is ignored entirely; [where metrics come from](where-metrics-come-from.html) has more.

## Where to read the source

| File | What’s there |
|---|---|
| `src/hb-open-type.hh` | the basic types: `NumType` and its typedefs, `Tag`, `Index`, `Offset`, `OffsetTo`, every kind of array |
| `src/hb-algs.hh` | `HBInt`, the bytes inside a `NumType`, and `HB_FAST_NUM_ACCESS` |
| `src/hb-machinery.hh` | `StructAtOffset`, `StructAfter`, the `DEFINE_SIZE_*` macros (and lazy loaders, for the [blobs and faces chapter](blobs-faces-and-lazy-tables.html)) |
| `src/hb-null.hh` | `Null`, `Crap`, `CrapOrNull`, the size traits, `DECLARE_NULL_NAMESPACE_BYTES`, `hb_nonnull_ptr_t` |
| `src/hb-static.cc` | the Null and Crap pools, and the non-zero Null bytes |
| `src/hb-open-file.hh` | the container: `OpenTypeFontFile`, `OpenTypeOffsetTable`, `TableRecord`, TTC headers, Mac resource forks |
| `src/hb-face.cc` | finding a face in a file and a table in a face |
| `src/hb-dispatch.hh` | `hb_dispatch_context_t` |
| `src/hb-ot-dual.hh` | `SmallTypes`, `MediumTypes`, and the dual accelerators for beyond-64k tables |
| `src/OT/Layout/Common/` | Coverage and `RangeRecord`, a small, complete example of the whole pattern |
| `src/OT/Layout/GSUB/SingleSubst*.hh` | a format union with `dispatch`, and its two format templates |

The test fonts and the scripts that make them are in `fonts/fonts-as-bytes/`: `build-fonts.py` builds `bytes.ttf` and the altered copies, and `dump.py` prints the bytes shown on this page.

## In short

* HarfBuzz doesn’t parse fonts. It describes their bytes with structs and reads fields in place, with no copying and no allocation.
* A face is found from the file’s first four bytes (sfnt, TTC or dfont) and a table from the directory; a missing table is an empty blob.
* Numbers are byte arrays that convert themselves from big-endian when read, so structs can sit at any address.
* `DEFINE_SIZE_*` gives each struct its real size and has the compiler check it against the declaration.
* `this+offset` follows an offset to a typed target. The code always names the base, because OpenType counts offsets from different places.
* A zero offset, an out-of-range index or a too-short table gives a Null object: zeros, or special bytes where zeros would mean something. A zeroed table is an empty one, so the code rarely checks for missing data.
* Format unions `dispatch` to their formats, and contexts say what to do there: one description of a table serves sanitizing, applying, closure, subsetting and the rest.
* `SmallTypes` and `MediumTypes` let one template describe both 16-bit OpenType and its 24-bit “beyond 64k” formats.
