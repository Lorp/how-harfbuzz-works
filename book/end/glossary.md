# Glossary

**Cluster.** A number on each glyph naming the text it came from, normally the index of its first character. Glyphs from the same text share a cluster.

**Coverage table.** A list of glyphs that a subtable applies to. A glyph's place in the list (its coverage index) picks its data in the subtable.

**Glyph properties.** HarfBuzz's record, on each glyph in the buffer, of its GDEF class and of how it got there (substituted, ligated, multiplied).

**Ligature ID and component.** Numbers HarfBuzz gives a ligature and the marks inside it, so each mark knows which part of the ligature it belongs to.

**Lookup.** One set of rules of one type, with flags saying which glyphs it ignores. Features are lists of lookups.

**Mask.** 32 bits on each glyph saying which features are on for it.

**Set digest.** A small, fast summary of a set of glyphs, which can say for certain that a glyph is *not* in the set.

**Stage.** A group of lookups run together, between pauses where a script shaper can work on the buffer.
