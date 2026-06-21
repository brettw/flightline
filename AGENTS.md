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

`scripts/generate_features.py` has three main parts:

- `HEADER` is a literal block containing the FontLab-style preamble, glyph
  classes, and no `feature` blocks.
- `HARDCODED_FEATURES` is a literal block containing `ss01` and `ss02`.
- `generate_calt()` appends a generated `feature calt` block.

All glyph class definitions, including generated classes such as
`@lcAnnotated` and `@ucAnnotated`, must be emitted before any `feature` block.

The generated `calt` block has pair right-side uppercase rules first, lowercase
pair-operator rules second, single-punctuation rules third, and bracket-pair
rules last. Keep that order: uppercase-right pair rules must run before
lowercase pair rules, and pair rules need to see both base glyph names before a
single-punctuation rule rewrites either side.

Pair-operator rules come from `OPERATOR_COMBINATIONS`. Each two-character
operator gets eight lowercase contextual substitutions covering immediate and
space-separated contexts on either side of the operator. Compact arrow-like
operators use `COMPACT_LC_OUTPUTS`; for example, `->` generates
`hyphen.lc.rightfull` plus `greater.lc.leftfull`.

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
The annotated follow rules make adjacent glyphs with known `.lc` or `.uc`
variants inherit that same state. These follow rules are generated for
`MAX_ANNOTATED_FOLLOW_LENGTH` rounds so a run like `a+~*c` can propagate from
`plus.lc` through the following punctuation. Keep the annotated follow rules
below the explicit sequence, pair, and single-punctuation rules so those
position-specific outputs take precedence.

Pair right-side uppercase rules convert base operator pairs to their
uppercase/full-height outputs when the pair is followed by `@fullLeft` or
`space @fullLeft`. Compact outputs come from `COMPACT_UC_OUTPUTS`; non-compact
outputs use `UPPERCASE_OUTPUTS` where a `.uc` glyph exists and otherwise keep
the base glyph name, such as `less`.

The single-punctuation rules come from `PUNCTUATION_GLYPHS`. Each punctuation
glyph gets eight contextual substitutions:

- `.uc` rules for `@fullRight glyph'`, `@fullRight space glyph'`,
  `glyph' @fullLeft`, and `glyph' space @fullLeft`.
- `.lc` rules for `@littleRight glyph'`, `@littleRight space glyph'`,
  `glyph' @littleLeft`, and `glyph' space @littleLeft`.

The generator list intentionally includes `"equals"` as a readable name, but
`GLYPH_ALIASES` maps it to the actual glyph name `equal`. Use `equal` in tests
and generated feature output.

Bracket-pair rules come from `BRACKET_PAIRS` and are generated for content
lengths 1 through `MAX_BRACKET_CONTENT_LENGTH`. They lowercase matching
parentheses, brackets, and braces when the enclosed run starts with
`@littleLeft` and ends with `@littleRight`, with optional `@letters` between.

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
that is enough to verify the generated `ss01`, `ss02`, and simple `calt` source
rules.

Useful tester commands:

```bash
python3 scripts/test_features.py --list-features
python3 scripts/test_features.py --features calt --dump-text 'A + b'
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
