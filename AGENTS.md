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

`scripts/generate_features.py` emits:

- `HEADER` is a literal block containing the FontLab-style preamble, glyph
  classes, and no `feature` blocks.
- `ABOVE_MARK_CLASS` and `CCMP_FEATURE` handle dotless i/j before combining
  accents above. The mark filtering set lets this rule see past marks below.
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

<a id="combining-grave-in-fontlab"></a>

## Combining accents in FontLab

Both VFJs have zero-width combining counterparts to the spacing accents.
The eleven above marks (grave, acute, circumflex, tilde, macron, breve, dot,
diaeresis, ring, double acute, caron) have two anchors: `_top` attaches to
the letter and `top` receives another mark. On a plain letter, place `top`
at its optical center at cap height, x-height, or ascender height as appropriate.
The gap comes from the distance between `_top` and the mark's ink. On an
accented letter, `top` belongs on the top of the accent.

Cedilla uses `_bottom` and `bottom`; ogonek uses `_ogonek` and `ogonek`.
Keep these distinct: the cedilla generally attaches under the center, while
the ogonek joins the lower-right stroke. On i and j, `ccmp` removes the
original dot for accents above and keeps it for accents below.

FontLab builds variable `mark` and `mkmk` lookups from the per-master anchors.
In FontLab 8.4, a glyph made entirely of element references can show anchors
in the editor but disappear from the exported attachment tables. Keep native
contours in combining marks. In accented letters, keep the accent as contours
and the reference to the base where available. The letter still receives
additional marks after Unicode shaping selects its precomposed glyph.

If **Flightline Variable TT** is missing from your FontLab export profiles,
use **File > Export Profiles > Open profile file** to import
`sources/vfj/Flightline-Variable-TT.fl_profile` and click **OK** to save it.
FontLab remembers the profile across restarts for your user account. For
each Regular or Italic export, make sure **Flightline Variable TT** is selected.
This profile enables
generation from anchors under **Features and Kerning > OpenType mark
attachment**. FontLab 8.4's built-in Variable TT profile defaults to **Never**.

To preview without relying on a precomposed character, enter glyph names such
as `/Q/macroncomb/x`, `/a/ogonekcomb/x`, or `/m/brevecomb/acutecomb/x` in the
Glyph window's text bar and enable **Apply mark attachment**. The first two
examples check the join to the letter; the third checks stacking. In each
case the following `x` should start in the next cell.

After exporting both TTFs, run `python3 scripts/test_exported_marks.py` with
fontTools installed to check that the exported fonts include every attachment
pair declared in the VFJs.

## TrueType hinting

The production variable fonts use unhinted outlines. Both VFJs set one `gasp`
range: all four flags (`0x000F`) through 65535 ppem. After FontLab exports,
`scripts/make_release.py` runs `scripts/prepare_variable_font.py` on both faces.
This removes glyph instructions and installs the [Google Fonts unhinted
settings](https://github.com/googlefonts/gftools/blob/main/Lib/gftools/fix.py#L172-L194):
the same all-size `gasp` range and a font-wide `prep` program for smart dropout
control including stubs.

For a manual build, export each face with **Flightline Variable TT**, then
run the finalizer on each exported file (requires fontTools), for example:

```bash
python3 scripts/prepare_variable_font.py path/to/Regular-export.ttf ttf/variable/FlightlineCode-Regular-VF.ttf
```

Keep the authored vertical visual hints in the VFJs for comparison builds.
The raw FontLab profile compiles them. Keep each glyph's instructions compatible
across its participating masters, including intermediate layers; FontLab 8 can
discard all glyph hints when it encounters incompatible programs.
