#!/usr/bin/env python3
"""Run glyph-sequence tests against simple OpenType GSUB feature definitions.

This is intentionally a small simulator for the Adobe FEA syntax used by this
project's FontLab VFJ sources. It supports glyph classes, single substitutions,
and contextual single substitutions with one marked input glyph. Separate VFJ
checks verify mark attachment from the source anchors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

if __package__:
    from .regenerate_accented import build_elements_by_id, extreme_point, layer_points
else:
    from regenerate_accented import build_elements_by_id, extreme_point, layer_points


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_FEATURE_FILE = REPO_ROOT / "sources" / "features.txt"
DEFAULT_TEST_FILE = REPO_ROOT / "sources" / "feature_tests.json"


TOKEN_RE = re.compile(
    r"""
    "(?:\\.|[^"\\])*"      # quoted strings, usually in featureNames
    |\#[^\n]*               # comments
    |@[A-Za-z_][A-Za-z0-9_.-]*
    |[A-Za-z_][A-Za-z0-9_.-]*
    |[{}\[\];=']
    """,
    re.VERBOSE,
)


ASCII_GLYPHS = {
    " ": "space",
    "!": "exclam",
    '"': "quotedbl",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "quotesingle",
    "(": "parenleft",
    ")": "parenright",
    "*": "asterisk",
    "+": "plus",
    ",": "comma",
    "-": "hyphen",
    ".": "period",
    "/": "slash",
    ":": "colon",
    ";": "semicolon",
    "<": "less",
    "=": "equal",
    ">": "greater",
    "?": "question",
    "@": "at",
    "[": "bracketleft",
    "\\": "backslash",
    "]": "bracketright",
    "^": "asciicircum",
    "_": "underscore",
    "`": "grave",
    "{": "braceleft",
    "|": "bar",
    "}": "braceright",
    "~": "asciitilde",
}
ASCII_GLYPHS.update({chr(code): chr(code) for code in range(ord("a"), ord("z") + 1)})
ASCII_GLYPHS.update({chr(code): chr(code) for code in range(ord("A"), ord("Z") + 1)})
ASCII_GLYPHS.update(
    {
        "0": "zero",
        "1": "one",
        "2": "two",
        "3": "three",
        "4": "four",
        "5": "five",
        "6": "six",
        "7": "seven",
        "8": "eight",
        "9": "nine",
    }
)


@dataclass(frozen=True)
class LexToken:
    text: str
    line: int


@dataclass(frozen=True)
class SubstitutionRule:
    feature: str
    pattern: tuple[str, ...]
    replacement: str
    marked_index: Optional[int]
    line: int


@dataclass
class FeatureProgram:
    classes: dict[str, frozenset[str]]
    features: dict[str, list[SubstitutionRule]]

    def atom_matches(self, atom: str, glyph: str) -> bool:
        if atom.startswith("@"):
            class_name = atom[1:]
            members = self.classes.get(class_name)
            if members is None:
                raise ValueError(f"undefined glyph class {atom}")
            return glyph in members
        return glyph == atom

    def rule_matches(self, rule: SubstitutionRule, glyphs: list[str], start: int) -> bool:
        if start + len(rule.pattern) > len(glyphs):
            return False
        return all(
            self.atom_matches(atom, glyphs[start + offset])
            for offset, atom in enumerate(rule.pattern)
        )

    def apply_rule(self, rule: SubstitutionRule, glyphs: list[str]) -> list[str]:
        if rule.marked_index is None:
            atom = rule.pattern[0]
            return [
                rule.replacement if self.atom_matches(atom, glyph) else glyph
                for glyph in glyphs
            ]

        output = list(glyphs)
        max_start = len(output) - len(rule.pattern)
        for start in range(max_start + 1):
            if self.rule_matches(rule, output, start):
                output[start + rule.marked_index] = rule.replacement
        return output

    def apply(self, feature_tags: Iterable[str], glyphs: list[str]) -> list[str]:
        output = list(glyphs)
        for feature_tag in feature_tags:
            rules = self.features.get(feature_tag)
            if rules is None:
                known = ", ".join(self.features) or "<none>"
                raise ValueError(f"unknown feature {feature_tag!r}; known features: {known}")
            for rule in rules:
                output = self.apply_rule(rule, output)
        return output


def tokenize(text: str) -> list[LexToken]:
    tokens: list[LexToken] = []
    for match in TOKEN_RE.finditer(text):
        token = match.group(0)
        if token.startswith("#"):
            continue
        tokens.append(LexToken(token, text.count("\n", 0, match.start()) + 1))
    return tokens


def expect(tokens: list[LexToken], index: int, text: str) -> int:
    if index >= len(tokens) or tokens[index].text != text:
        line = tokens[index].line if index < len(tokens) else "EOF"
        found = tokens[index].text if index < len(tokens) else "EOF"
        raise ValueError(f"line {line}: expected {text!r}, found {found!r}")
    return index + 1


def parse_classes(tokens: list[LexToken]) -> dict[str, list[str]]:
    classes: dict[str, list[str]] = {}
    index = 0
    while index < len(tokens):
        if (
            tokens[index].text.startswith("@")
            and index + 2 < len(tokens)
            and tokens[index + 1].text == "="
            and tokens[index + 2].text == "["
        ):
            class_name = tokens[index].text[1:]
            index += 3
            members: list[str] = []
            while index < len(tokens) and tokens[index].text != "]":
                members.append(tokens[index].text)
                index += 1
            index = expect(tokens, index, "]")
            index = expect(tokens, index, ";")
            classes[class_name] = members
            continue
        index += 1
    return classes


def expand_classes(raw_classes: dict[str, list[str]]) -> dict[str, frozenset[str]]:
    expanded: dict[str, frozenset[str]] = {}
    visiting: set[str] = set()

    def expand(class_name: str) -> frozenset[str]:
        if class_name in expanded:
            return expanded[class_name]
        if class_name in visiting:
            raise ValueError(f"recursive glyph class @{class_name}")
        if class_name not in raw_classes:
            raise ValueError(f"undefined glyph class @{class_name}")

        visiting.add(class_name)
        members: set[str] = set()
        for member in raw_classes[class_name]:
            if member.startswith("@"):
                members.update(expand(member[1:]))
            else:
                members.add(member)
        visiting.remove(class_name)

        expanded[class_name] = frozenset(members)
        return expanded[class_name]

    for class_name in raw_classes:
        expand(class_name)
    return expanded


def skip_braced_block(tokens: list[LexToken], index: int) -> int:
    index = expect(tokens, index, "{")
    depth = 1
    while index < len(tokens) and depth:
        if tokens[index].text == "{":
            depth += 1
        elif tokens[index].text == "}":
            depth -= 1
        index += 1
    if depth:
        raise ValueError("unterminated braced block")
    if index < len(tokens) and tokens[index].text == ";":
        index += 1
    return index


def parse_substitution(
    feature_tag: str, statement: list[LexToken]
) -> Optional[SubstitutionRule]:
    if not statement:
        return None
    try:
        by_index = next(
            index for index, token in enumerate(statement) if token.text == "by"
        )
    except StopIteration:
        return None

    pattern: list[str] = []
    marked_indexes: list[int] = []
    index = 0
    while index < by_index:
        token = statement[index]
        if token.text == "'":
            raise ValueError(f"line {token.line}: stray mark quote")
        marked = index + 1 < by_index and statement[index + 1].text == "'"
        pattern.append(token.text)
        if marked:
            marked_indexes.append(len(pattern) - 1)
            index += 2
        else:
            index += 1

    replacement_tokens = statement[by_index + 1 :]
    if len(replacement_tokens) != 1:
        line = statement[0].line
        raise ValueError(
            f"line {line}: only one replacement glyph is supported in a sub rule"
        )
    replacement = replacement_tokens[0].text
    if replacement.startswith("@"):
        line = replacement_tokens[0].line
        raise ValueError(f"line {line}: replacement classes are not supported")
    if not pattern:
        line = statement[0].line
        raise ValueError(f"line {line}: empty substitution pattern")
    if len(marked_indexes) > 1:
        line = statement[0].line
        raise ValueError(f"line {line}: only one marked glyph is supported")
    if not marked_indexes and len(pattern) != 1:
        line = statement[0].line
        raise ValueError(
            f"line {line}: ligature or multiple-input substitutions are not supported"
        )

    return SubstitutionRule(
        feature=feature_tag,
        pattern=tuple(pattern),
        replacement=replacement,
        marked_index=marked_indexes[0] if marked_indexes else None,
        line=statement[0].line,
    )


def parse_feature_body(
    feature_tag: str, body: list[LexToken]
) -> list[SubstitutionRule]:
    rules: list[SubstitutionRule] = []
    index = 0
    while index < len(body):
        if (
            body[index].text in {"featureNames", "lookup", "table"}
            and index + 1 < len(body)
            and body[index + 1].text == "{"
        ):
            index = skip_braced_block(body, index + 1)
            continue

        if body[index].text != "sub":
            index += 1
            continue

        statement_start = index + 1
        index = statement_start
        while index < len(body) and body[index].text != ";":
            index += 1
        if index >= len(body):
            line = body[statement_start - 1].line
            raise ValueError(f"line {line}: unterminated sub statement")

        rule = parse_substitution(feature_tag, body[statement_start:index])
        if rule is not None:
            rules.append(rule)
        index += 1

    return rules


def parse_features(tokens: list[LexToken]) -> dict[str, list[SubstitutionRule]]:
    features: dict[str, list[SubstitutionRule]] = {}
    index = 0
    while index < len(tokens):
        if (
            tokens[index].text == "feature"
            and index + 2 < len(tokens)
            and tokens[index + 2].text == "{"
        ):
            feature_tag = tokens[index + 1].text
            index += 3
            depth = 1
            body: list[LexToken] = []
            while index < len(tokens) and depth:
                token = tokens[index]
                if token.text == "{":
                    depth += 1
                    body.append(token)
                elif token.text == "}":
                    depth -= 1
                    if depth:
                        body.append(token)
                else:
                    body.append(token)
                index += 1
            if depth:
                raise ValueError(f"feature {feature_tag}: unterminated feature block")
            features[feature_tag] = parse_feature_body(feature_tag, body)
            if index < len(tokens) and tokens[index].text == feature_tag:
                index += 1
            if index < len(tokens) and tokens[index].text == ";":
                index += 1
            continue
        index += 1
    return features


def feature_text_from_path(path: Path) -> str:
    if path.suffix.lower() not in {".vfj", ".vff"}:
        return path.read_text(encoding="utf-8")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error}") from error

    font = data.get("font")
    if not isinstance(font, dict):
        raise ValueError(f"{path}: expected top-level 'font' object")

    entries = font.get("openTypeFeatures")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected font.openTypeFeatures list")

    parts: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("feature"), str):
            parts.append(entry["feature"])
    return "\n".join(parts)


def parse_program(path: Path) -> FeatureProgram:
    tokens = tokenize(feature_text_from_path(path))
    return FeatureProgram(
        classes=expand_classes(parse_classes(tokens)),
        features=parse_features(tokens),
    )


def glyphs_from_text(text: str) -> list[str]:
    glyphs: list[str] = []
    for char in text:
        glyph_name = ASCII_GLYPHS.get(char)
        if glyph_name is None:
            raise ValueError(f"no built-in glyph-name mapping for character {char!r}")
        glyphs.append(glyph_name)
    return glyphs


def glyph_list(value: Any, field_name: str) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    if isinstance(value, str):
        return value.split()
    raise ValueError(f"{field_name} must be a string or list of glyph-name strings")


def test_glyphs(test: dict[str, Any], input_field: str) -> list[str]:
    if input_field == "inputText":
        return glyphs_from_text(test[input_field])
    return glyph_list(test[input_field], input_field)


def expected_glyphs(test: dict[str, Any]) -> list[str]:
    if "expected" in test:
        return glyph_list(test["expected"], "expected")
    if "expectedGlyphs" in test:
        return glyph_list(test["expectedGlyphs"], "expectedGlyphs")
    if "expectedText" in test:
        return glyphs_from_text(test["expectedText"])
    raise ValueError("test is missing expected, expectedGlyphs, or expectedText")


def test_features(test: dict[str, Any], default_features: list[str]) -> list[str]:
    raw_features = test.get("features", test.get("feature"))
    if raw_features is None:
        return default_features
    if isinstance(raw_features, str):
        return [raw_features]
    if isinstance(raw_features, list) and all(
        isinstance(item, str) for item in raw_features
    ):
        return list(raw_features)
    raise ValueError("features must be a string or list of strings")


def load_tests(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error}") from error

    tests = data.get("tests") if isinstance(data, dict) else data
    if not isinstance(tests, list):
        raise ValueError(f"{path}: expected a list or an object with a tests list")
    if not all(isinstance(test, dict) for test in tests):
        raise ValueError(f"{path}: every test must be an object")
    return tests


def format_glyphs(glyphs: list[str]) -> str:
    return " ".join(glyphs)


def anchor_point(layer: dict[str, Any], name: str) -> tuple[float, float]:
    for item in layer.get("anchors", []):
        if item["name"] == name:
            x, y = item["point"].split()
            return float(x), float(y)
    raise ValueError(f"missing {name} anchor")


def check_combining_marks(path: Path, case: dict[str, Any]) -> None:
    font = json.loads(path.read_text(encoding="utf-8"))["font"]
    elements = build_elements_by_id(font)
    glyphs = {glyph["name"]: glyph for glyph in font["glyphs"]}
    layers = {
        (glyph["name"], layer["name"]): layer
        for glyph in glyphs.values() for layer in glyph["layers"]
    }
    for master in font["masters"]:
        name = master["fontMaster"]["name"]
        for anchor, marks in case["anchors"].items():
            for spacing, (spacing_code, mark_code) in marks.items():
                mark = spacing + "comb"
                try:
                    for glyph, code, width in ((spacing, spacing_code, 1200), (mark, mark_code, 0)):
                        if glyphs[glyph].get("unicode", "").upper() != code:
                            raise ValueError(f"{glyph} must encode U+{code}")
                        if layers[glyph, name]["advanceWidth"] != width:
                            raise ValueError(f"{glyph} must advance {width} units")
                    layer = layers[mark, name]
                    mx, my = anchor_point(layer, "_" + anchor)
                    points = layer_points(layer, elements)
                    xmin, xmax = min(p.x for p in points), max(p.x for p in points)
                    ymin, ymax = min(p.y for p in points), max(p.y for p in points)
                    if anchor == "top":
                        _, stack_y = anchor_point(layer, "top")
                        if not (my < ymin and stack_y >= ymax - 1):
                            raise ValueError("mark or stacking anchor lacks clearance")
                    elif not (ymin < my <= ymax):
                        raise ValueError("attachment anchor must meet the top of the below mark")
                    for base in case["bases"]:
                        base_layer = layers[base, name]
                        bx, by = anchor_point(base_layer, anchor)
                        center = (xmin + xmax) / 2 + bx - mx
                        if not 0 <= center <= base_layer["advanceWidth"]:
                            raise ValueError(f"mark center falls outside {base}'s cell")
                        base_ys = [p.y for p in layer_points(base_layer, elements)]
                        dy = by - my
                        if anchor == "top" and ymin + dy <= max(base_ys):
                            raise ValueError(f"mark overlaps {base}")
                        if anchor != "top" and not ymin + dy < min(base_ys) <= ymax + dy:
                            raise ValueError(f"mark must meet the lower edge of {base}")
                except (KeyError, ValueError) as error:
                    raise ValueError(f"{path.name}, {name}, {mark}: {error}") from error


def check_mark_attachment(path: Path, case: dict[str, Any]) -> None:
    font = json.loads(path.read_text(encoding="utf-8"))["font"]
    elements = build_elements_by_id(font)
    layers = {
        (layer["name"], glyph["name"]): layer
        for glyph in font["glyphs"] for layer in glyph["layers"]
    }

    for master in font["masters"]:
        name = master["fontMaster"]["name"]
        glyph = case["mark"]
        try:
            mark = layers[name, glyph]
            mx, my = anchor_point(mark, "_" + case["anchor"])
            if "markAnchorY" in case and my != case["markAnchorY"]:
                raise ValueError(f"expected mark anchor Y {case['markAnchorY']}, got {my:g}")
            if mark["advanceWidth"] != 0:
                raise ValueError("mark must have zero advance")
            mark_points = layer_points(mark, elements)
            xs = [point.x for point in mark_points]
            xmin, xmax = min(xs), max(xs)
            for glyph, rise in case["expectedYOffsets"].items():
                base = layers[name, glyph]
                bx, by = anchor_point(base, case["anchor"])
                if by - my != rise:
                    raise ValueError(f"expected mark rise {rise}, got {by - my:g}")
                left, right = bx - mx + xmin, bx - mx + xmax
                if base["advanceWidth"] != case["baseAdvance"]:
                    raise ValueError(f"expected base advance {case['baseAdvance']}")
                if not (0 <= left < right <= base["advanceWidth"]):
                    raise ValueError(f"mark ink spans {left:g}..{right:g} outside the base cell")
                tolerance = case.get("crownXTolerance", {}).get(glyph)
                if tolerance is not None:
                    crown = extreme_point(layer_points(base, elements), "top")
                    if abs(bx - crown.x) > tolerance:
                        raise ValueError(f"anchor X {bx:g} is too far from the crown at {crown.x:g}")
                composed = case.get("precomposed", {}).get(glyph)
                if composed:
                    outline = {(p.x, p.y) for p in layer_points(layers[name, composed], elements)}
                    if any((p.x + bx - mx, p.y + by - my) not in outline for p in mark_points):
                        raise ValueError(f"attached mark and {composed} accent outlines differ")
        except (KeyError, ValueError) as error:
            raise ValueError(f"{path.name}, {name}, {glyph}: {error}") from error


def run_tests(
    program: FeatureProgram, tests: list[dict[str, Any]], default_features: list[str],
    test_dir: Path = DEFAULT_TEST_FILE.parent,
) -> int:
    failures = 0
    for test_number, test in enumerate(tests, start=1):
        name = str(test.get("name", f"test {test_number}"))
        input_field = "inputText" if "inputText" in test else "input"
        try:
            if "markAttachment" in test or "combiningMarks" in test:
                if "markAttachment" in test:
                    case, check = test["markAttachment"], check_mark_attachment
                else:
                    case, check = test["combiningMarks"], check_combining_marks
                for filename in case["fonts"]:
                    check(test_dir / filename, case)
                print(f"PASS {name}")
                continue
            if input_field not in test:
                raise ValueError("missing input or inputText")
            features = test_features(test, default_features)
            input_glyphs = test_glyphs(test, input_field)
            actual = program.apply(features, input_glyphs)
            expected = expected_glyphs(test)
        except (OSError, KeyError, ValueError) as error:
            print(f"FAIL {name}: {error}", file=sys.stderr)
            failures += 1
            continue

        if actual == expected:
            print(f"PASS {name}")
            continue

        print(f"FAIL {name}", file=sys.stderr)
        print(f"  features: {', '.join(features)}", file=sys.stderr)
        print(f"  input:    {format_glyphs(input_glyphs)}", file=sys.stderr)
        print(f"  expected: {format_glyphs(expected)}", file=sys.stderr)
        print(f"  actual:   {format_glyphs(actual)}", file=sys.stderr)
        failures += 1

    passed = len(tests) - failures
    print(f"{passed}/{len(tests)} tests passed")
    return 1 if failures else 0


def parse_feature_list(value: Optional[str], fallback: Iterable[str]) -> list[str]:
    if value is None:
        return list(fallback)
    return [feature.strip() for feature in value.split(",") if feature.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test glyph substitutions in simple OpenType feature definitions."
    )
    parser.add_argument(
        "feature_file",
        nargs="?",
        type=Path,
        default=DEFAULT_FEATURE_FILE,
        help=f"Path to a .fea/.vfj/.vff file. Default: {DEFAULT_FEATURE_FILE}",
    )
    parser.add_argument(
        "test_file",
        nargs="?",
        type=Path,
        default=DEFAULT_TEST_FILE,
        help=f"JSON feature tests. Default: {DEFAULT_TEST_FILE}",
    )
    parser.add_argument(
        "--features",
        help="Comma-separated default feature list for tests without a feature field.",
    )
    parser.add_argument(
        "--list-features",
        action="store_true",
        help="List parsed feature tags and exit.",
    )
    parser.add_argument(
        "--dump",
        metavar="GLYPH",
        nargs="+",
        help="Apply features to a glyph-name sequence and print the result.",
    )
    parser.add_argument(
        "--dump-text",
        help="Apply features to ASCII text mapped through built-in glyph names.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        program = parse_program(args.feature_file)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    if args.list_features:
        for feature_tag, rules in program.features.items():
            print(f"{feature_tag}: {len(rules)} substitution rules")
        return 0

    default_features = parse_feature_list(args.features, program.features)

    if args.dump is not None or args.dump_text is not None:
        if args.dump is not None and args.dump_text is not None:
            print("use either --dump or --dump-text, not both", file=sys.stderr)
            return 1
        try:
            input_glyphs = (
                args.dump if args.dump is not None else glyphs_from_text(args.dump_text)
            )
            print(format_glyphs(program.apply(default_features, list(input_glyphs))))
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        return 0

    try:
        tests = load_tests(args.test_file)
        return run_tests(program, tests, default_features, args.test_file.parent)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
