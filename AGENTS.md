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

`scripts/generate_features.py` has two main parts:

- `HEADER` is a literal block containing the FontLab-style preamble, glyph
  classes, `ss01`, and `ss02`.
- `generate_calt()` appends a generated `feature calt` block.

The generated `calt` block has pair-operator rules first, followed by
single-punctuation rules. Keep that order: pair rules need to see both base
glyph names before a single-punctuation rule rewrites either side.

Pair-operator rules come from `OPERATOR_COMBINATIONS`. Each two-character
operator gets eight lowercase contextual substitutions covering immediate and
space-separated contexts on either side of the operator. Compact arrow-like
operators use `COMPACT_LC_OUTPUTS`; for example, `->` generates
`hyphen.lc.rightfull` plus `greater.lc.leftfull`.

The single-punctuation rules come from `PUNCTUATION_GLYPHS`. Each punctuation
glyph gets eight contextual substitutions:

- `.uc` rules for `@fullRight glyph'`, `@fullRight space glyph'`,
  `glyph' @fullLeft`, and `glyph' space @fullLeft`.
- `.lc` rules for `@littleRight glyph'`, `@littleRight space glyph'`,
  `glyph' @littleLeft`, and `glyph' space @littleLeft`.

The generator list intentionally includes `"equals"` as a readable name, but
`GLYPH_ALIASES` maps it to the actual glyph name `equal`. Use `equal` in tests
and generated feature output.


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
