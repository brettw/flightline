# Agent Notes

## OpenType Feature Workflow

This repo keeps the generated OpenType feature text in `sources/features.txt`.
Do not hand-edit that file for normal feature changes. Edit
`scripts/generate_features.py`, then regenerate:

```bash
python3 scripts/generate_features.py
```

The generator resolves paths relative to its own location and writes
`../sources/features.txt`, so it works from any current working directory.

`scripts/generate_features.py` has four main parts:

- `HEADER` is a literal block containing the FontLab-style preamble, glyph
  classes, and no `feature` blocks.
- `HARDCODED_FEATURES` is a literal block containing `ss01` and `ss02`.
- `generate_height_feature()` appends `ss03`, named "Contextual Punctuation
  Heights". This optional stylistic set contains all contextual height rules.
- `generate_calt()` appends `calt`, containing only horizontal shaping for
  `->`, `<-`, and `=>`. It shapes arrows without requiring surrounding letters
  and preserves each component's height.

Emit `ss03` before `calt` so the compiled lookup order chooses heights before
shaping arrows. `calt` accepts base, `.lc`, and available `.uc` inputs; its
`COMPACT_LC_OUTPUTS` and `COMPACT_UC_OUTPUTS` select the corresponding
`.leftfull`/`.rightfull` forms. The base and `.uc` forms have the same height.
`ss03` must also work independently when `calt` is disabled, adjusting heights
without compacting arrows.

All glyph class definitions, including generated classes such as
`@lcAnnotated` and `@ucAnnotated`, must be emitted before any `feature` block.

The generated `ss03` block has sequence and pair right-side uppercase rules
first, lowercase sequence and pair-operator rules second, single-punctuation
rules third, and annotated follow rules last. Keep that order: uppercase-right
pair rules must run before lowercase pair rules, and pair rules need to see
both base glyph names before a single-punctuation rule rewrites either side.

Pair-operator rules come from `OPERATOR_COMBINATIONS`. Each two-character
operator gets eight lowercase contextual substitutions covering immediate and
space-separated contexts on either side of the operator. These height rules
use ordinary `.lc`/`.uc` outputs, including for arrow-like operators. For
example, `ss03` maps `a->c` to `a hyphen.lc greater.lc c`, and the later `calt`
rules compact the arrow to `hyphen.lc.rightfull` plus `greater.lc.leftfull`.

Long equality operators come from `LONG_OPERATOR_COMBINATIONS`; currently this
is `===`, `!==`, and the four-character `!===` form. These use the same
lowercase and right-side uppercase contexts as two-character operators.
`exclam` remains unchanged because the font source does not define `exclam.lc`
or `exclam.uc`.

Repeated `equal` and `hyphen` runs come from `REPEATED_SEQUENCE_GLYPHS` and are
generated longest-first for lengths 2 through `MAX_REPEATED_SEQUENCE_LENGTH`.
These explicit rules seed the first glyph in runs such as `==`, `====`, `---`,
and `----` with the `.lc` or `.uc` form chosen by the surrounding context. Keep
repeated run rules longest-first and before the annotated follow rules so a
shorter tail match cannot steal precedence from the full run.

`@lcAnnotated` and `@ucAnnotated` are generated classes containing the glyphs
that have already been rewritten to lowercase or uppercase/full-height forms.
The classes exclude compact arrow forms, which are produced later by `calt`.
The annotated follow rules make adjacent glyphs with known `.lc` or `.uc`
variants inherit that same state. These follow rules are generated for
`MAX_ANNOTATED_FOLLOW_LENGTH` rounds so a run like `a+~*c` can propagate from
`plus.lc` through the following punctuation. Keep the annotated follow rules
below the explicit sequence, pair, and single-punctuation rules so those
position-specific outputs take precedence.

Pair right-side uppercase rules convert base operator pairs to their
uppercase/full-height outputs when the pair is followed by `@fullLeft` or
`space @fullLeft`. Outputs use `UPPERCASE_OUTPUTS` where a `.uc` glyph exists
and otherwise keep the base glyph name, such as `less`.

The single-punctuation rules come from `PUNCTUATION_GLYPHS`. Each punctuation
glyph gets eight contextual substitutions:

- `.uc` rules for `@fullRight glyph'`, `@fullRight space glyph'`,
  `glyph' @fullLeft`, and `glyph' space @fullLeft`.
- `.lc` rules for `@littleRight glyph'`, `@littleRight space glyph'`,
  `glyph' @littleLeft`, and `glyph' space @littleLeft`.

The generator list intentionally includes `"equals"` as a readable name, but
`GLYPH_ALIASES` maps it to the actual glyph name `equal`. Use `equal` in tests
and generated feature output.

Bracket-pair and bracket-follow rules are currently disabled. Their helpers
remain in the generator for possible use in `ss03`; keep them disabled unless
explicitly changing bracket behavior. `ss01` still provides unconditional
lowercase brackets.

## Feature Tests

Run the default feature tests with:

```bash
python3 scripts/test_features.py
```

With no arguments, the tester reads:

- `sources/features.txt`
- `sources/feature_tests.json`

Regenerate `sources/features.txt` before testing if the generator changed or
the generated file is missing.

The tester is a small simulator for the Adobe FEA subset used here. It supports
glyph classes, single substitutions, and contextual single substitutions with
one marked glyph. It is not a HarfBuzz or compiled-font test. For this project,
that is enough to verify the generated `ss01`, `ss02`, `ss03`, and simple `calt`
source rules. For combined height and arrow tests, select `["ss03", "calt"]`:
the simulator applies features in the requested order, so this must match the
generated lookup order. It does not model application feature defaults.

Useful tester commands:

```bash
python3 scripts/test_features.py --list-features
python3 scripts/test_features.py --features calt --dump-text 'A + b'
python3 scripts/test_features.py --features ss03,calt --dump-text 'a->c A + b'
python3 scripts/test_features.py sources/features.txt sources/feature_tests.json
```

When changing feature behavior, update `sources/feature_tests.json` in the same
change. `inputText` uses the built-in ASCII-to-glyph-name mapping in
`scripts/test_features.py`, where `=` maps to `equal`, `-` maps to `hyphen`,
`+` maps to `plus`, `~` maps to `asciitilde`, and `*` maps to `asterisk`.

If you need to byte-compile the scripts in this sandboxed environment, redirect
Python's cache outside `~/Library`:

```bash
PYTHONPYCACHEPREFIX=/tmp/code612-pycache python3 -m py_compile scripts/generate_features.py scripts/test_features.py
```

## Combining grave in FontLab

Both VFJs store an `_top` anchor on `gravecomb` (U+0300) and `top` anchors on
Latin bases. Place `top` on the letter's design height (typically cap height
or x-height), with optical adjustments for individual shapes. The gap above
the letter comes from the clearance between `_top` and the accent outline.
FontLab builds the variable GPOS `mark` feature from these
per-master anchors. In **File > Export Profiles**, use **Open profile file**
to import `sources/vfj/Flightline-Variable-TT.fl_profile` once. Select
**Flightline Variable TT** when exporting either VFJ. This profile enables
generation from anchors under **Features and Kerning > OpenType mark
attachment**. FontLab 8.4's built-in Variable TT profile defaults to **Never**.

To preview in FontLab, paste `Q̀x M̀x Z̀x  q̀x m̀x z̀x` into the Glyph
window's text bar and enable **Apply mark attachment**. Each grave should
clear its own letter, and the following `x` should start in the next cell.
The feature tests also check anchor placement and advances in both sources.
