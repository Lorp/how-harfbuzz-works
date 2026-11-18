# Reading feature files

HarfBuzz never reads a feature file, but this book’s examples are written in them: the GSUB and GPOS chapters show feature-file source beside every compiled lookup, and most of the book’s test fonts get their layout tables, GSUB, GPOS and their GDEF glyph classes, from feature files. This appendix is enough to read that source, and to know what a rule becomes in the font HarfBuzz sees. To make a test font of your own and see what HarfBuzz does with a rule, see [Testing with a font of your own](testing-harfbuzz.html#testing-with-a-font-of-your-own). It isn’t a guide to writing feature files, but its last section says where to find one.

## The language

The feature file format is Adobe’s, defined for its font tools (AFDKO) in the [*OpenType Feature File Specification*](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html), now at document version 1.27. It is mainly for writing GSUB and GPOS rules. It can also give GDEF its glyph classes, and set values in BASE, `head`, `hhea`, `name`, `OS/2`, `vhea`, `vmtx` and STAT (its section 9), several of which HarfBuzz reads ([Where metrics come from](where-metrics-come-from.html), [Other tables](other-tables.html#base)). Font editors take feature code in the same language.

A rule says what a lookup should do, such as `sub f i by f_i;`. A compiler turns the rules into lookups, groups them into features, and registers the features under language systems. HarfBuzz never reads a feature file. It sees only the tables a compiler made.

## The compilers

* **makeotf**, Adobe’s compiler, part of AFDKO.
* **feaLib**, part of fontTools, used by fontmake. It built this book’s fonts, in fontTools 4.38.
* **fea-rs**, part of Google Fonts’ Rust compiler [fontc](https://github.com/googlefonts/fontc). Its README says it “should be able to compile most inputs”, and that “Obscure syntax may not be supported”. Its tests include feaLib’s own, “to ensure that we generate equivalent output to feaLib”.

The language leaves a compiler much to decide: how rules are split into lookups and subtables, which subtable formats to use, and how lookups are numbered. Two compilers need not make the same tables from the same file. What this book says about compiled lookups is what feaLib made, and [What a feature file compiles to](gsub.html#what-a-feature-file-compiles-to) shows the cases that surprise.

## The key

One row for each construct the book’s examples use. The middle column is what feaLib makes of it. It was checked by compiling one rule of each kind with feaLib and reading back the lookup types: it isn’t made when the book is built.

| You write | feaLib makes | Explained in |
|---|---|---|
| `languagesystem latn TRK;` | a language system, `TRK` under the script `latn`, that the features are registered under | [Choosing a script shaper](choosing-a-script-shaper.html#from-a-language-to-language-system-tags) |
| `feature liga { … } liga;` | a feature record for `liga`, listing the lookups made from the rules inside | [From features to lookups](from-features-to-lookups.html) |
| `lookup NAME { … } NAME;` | a named lookup, used by any feature that refers to it with `lookup NAME;` | [From features to lookups](from-features-to-lookups.html#collecting-the-lookups) |
| `@VOWELS = [a e i];` and `[a e i]` | nothing of its own: a glyph class is written out wherever it is used | |
| `sub a by a.alt1;` | Single substitution (GSUB type 1) | [GSUB](gsub.html#single-substitution) |
| `sub x by f i;` | Multiple substitution (GSUB type 2) | [GSUB](gsub.html#multiple-substitution) |
| `sub a from [a.alt1 a.alt2];` | Alternate substitution (GSUB type 3) | [GSUB](gsub.html#alternate-substitution) |
| `sub f i by f_i;` | Ligature substitution (GSUB type 4) | [GSUB](gsub.html#ligature-substitution) |
| `sub a' e by a.alt3;` | Chained context (GSUB type 6), and an unnamed single substitution it calls | [GSUB](gsub.html#an-inline-contextual-rule) |
| `ignore sub f' i;` | a chained-context rule that calls no lookup | [GSUB](gsub.html#an-ignore-rule) |
| `pos a 10;` or `pos a <40 100 0 0>;` | Single adjustment (GPOS type 1) | [GPOS](gpos.html#value-records) |
| `pos A V -80;` | Pair adjustment (GPOS type 2) | [GPOS](gpos.html#pair-adjustment) |
| `pos cursive x <anchor 0 0> <anchor 500 0>;` | Cursive attachment (GPOS type 3) | [GPOS](gpos.html#cursive-attachment) |
| `markClass acutecomb <anchor 250 500> @TOP;` | nothing of its own: the marks and their anchors, for the attachment rules that use the class | [GPOS](gpos.html#anchors) |
| `pos base a <anchor 250 500> mark @TOP;` | Mark to base (GPOS type 4) | [GPOS](gpos.html#mark-to-base) |
| `pos ligature f_i <anchor …> mark @TOP ligComponent <anchor …> mark @TOP;` | Mark to ligature (GPOS type 5), one anchor per component | [GPOS](gpos.html#mark-to-ligature) |
| `pos mark acutecomb <anchor 250 700> mark @TOP;` | Mark to mark (GPOS type 6) | [GPOS](gpos.html#mark-to-mark) |
| `pos T' 40 o n;` | Chained context (GPOS type 8), and an unnamed single adjustment it calls | [GPOS](gpos.html#context-chained-context-and-extension) |
| `lookupflag IgnoreMarks;` | the flags of the lookups made from the rules after it | [GSUB](gsub.html#which-glyphs-a-lookup-sees) |
| `script latn; language TRK exclude_dflt;` | which language systems the following rules’ lookups are registered under | [GSUB](gsub.html#rules-before-the-first-script), [Turkish i](choosing-a-script-shaper.html#turkish-i) |
| `language TRK required;` | the language system’s required feature | [From features to lookups](from-features-to-lookups.html#the-required-feature) |
| `table GDEF { GlyphClassDef … ; } GDEF;` | GDEF’s glyph classes: bases, ligatures, marks and components | [GSUB](gsub.html#which-glyphs-a-lookup-sees) |

Three things the key can’t show:

* **Where flags apply.** `lookupflag` sets the flags of the lookups made after it in the same block. A named lookup keeps the flags it was defined with: `lookupflag IgnoreMarks;` followed by `lookup NAME;` doesn’t change `NAME`.
* **When a new lookup starts.** Each feature block, each named lookup, and each change of rule type within a block starts a new lookup, and so do two kinds of attachment rule in one block, such as `pos base` then `pos ligature`. Rules of one type in a row share a lookup ([What a feature file compiles to](gsub.html#rules-of-different-types-in-one-block)).
* **The order lookups run in.** feaLib numbers lookups in the order it meets them, the unnamed ones included, and within a stage HarfBuzz runs them in that order, whatever features they belong to ([Feature order](feature-order.html)).

## Writing feature files

Much of a font’s layout isn’t written by hand. Font editors and build tools make many features themselves: `kern`, `mark` and `mkmk` from the kerning and the glyphs’ anchors, and often `ccmp`, `locl`, `liga` or the joining features from glyph names. Some show what they made as feature code; others build the lookups without it. Either way, HarfBuzz sees only the result. For what you do write by hand:

* Adobe’s [*OpenType Feature File Specification*](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html): the reference, for the exact syntax of every statement.
* Tal Leming’s [*OpenType Cookbook*](https://opentypecookbook.com/): “a designer friendly introduction to understanding and developing” OpenType features, teaching the language and its common techniques.
* Simon Cozens’ [*Fonts and Layout for Global Scripts*](https://simoncozens.github.io/fonts-and-layout/features.html): the lookup types worked through with examples from the world’s scripts, Arabic and Indic among them.
* Your font editor’s documentation: how it takes feature code, which compiler it uses, and which features it makes for you, and from what.

## In short

* A feature file is source for the layout tables, mainly GSUB and GPOS. HarfBuzz sees only what a compiler made of it.
* makeotf, feaLib and fea-rs compile the same language, but need not make the same tables. This book’s fonts are compiled by feaLib.
* Most rules compile to the lookup type they look like. Contextual rules make extra, unnamed lookups, and `ignore` rules make rules that call none.
