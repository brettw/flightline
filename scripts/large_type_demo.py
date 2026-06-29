#!/usr/bin/env python3
"""Print a visual demo of Flightline's Unicode large type glyph coverage."""

from __future__ import annotations

import argparse


DEFAULT_PER_LINE = 8
DEMO_HEADING = "Unicode large type pieces"
DEMO_TITLE = "Flightline Code"
ASCII_UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ASCII_LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
ASCII_DIGITS = "0123456789"
ASCII_PUNCTUATION = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
DEMO_SECTIONS = (
    ("Uppercase ASCII Letters", ASCII_UPPERCASE),
    ("Lowercase ASCII Letters", ASCII_LOWERCASE),
    ("ASCII Numbers", ASCII_DIGITS),
    ("ASCII Punctuation", ASCII_PUNCTUATION),
)

# Extracted from the required Basic Latin FIGcharacters in PHM's Large Type font.
LARGE_TYPE_GLYPHS: dict[str, tuple[str, str, str]] = {
    ' ': ('\xa0\xa0', '\xa0\xa0', '\xa0\xa0'),
    '!': ('\xa0\U0001ce1c\xa0', '\xa0\U0001ce29\xa0', '\xa0\U0001ce4a\xa0'),
    '"': ('\U0001ce1c\U0001ce1c', '\xa0\xa0', '\xa0\xa0'),
    '#': ('\xa0\xa0', '\U0001ce3a\U0001ce3a', '\U0001ce3a\U0001ce3a'),
    '$': ('\U0001ce1a\U0001ce3a\U0001ce24', '\U0001ce3e\U0001ce3a\U0001ce24', '\U0001ce3e\U0001ce3a\U0001ce43'),
    '%': ('O\xa0\U0001ce47', '\U0001ce2c\U0001ce34\U0001ce3b', '\U0001ce50\xa0O'),
    '&': ('\U0001ce1a\U0001ce24\xa0', '\U0001ce2e\U0001ce20\U0001ce25', '\U0001ce3e\U0001ce40\U0001ce25'),
    "'": ('\U0001ce1c', '\xa0', '\xa0'),
    '(': ('\xa0\U0001ce1a\U0001ce25', '\xa0\U0001ce29\xa0', '\xa0\U0001ce3e\U0001ce25'),
    ')': ('\U0001ce1e\U0001ce24\xa0', '\xa0\U0001ce29\xa0', '\U0001ce1e\U0001ce43\xa0'),
    '*': ('\xa0\xa0\xa0', '\U0001ce2a\U0001ce32\U0001ce38', '\xa0\xa0\xa0'),
    '+': ('\xa0\U0001ce23\xa0', '\U0001ce1e\U0001ce3a\U0001ce25', '\xa0\U0001ce2d\xa0'),
    ',': ('\xa0\xa0\xa0', '\xa0\xa0\xa0', '\xa0\U0001ce43\xa0'),
    '-': ('\xa0\xa0\xa0', '\U0001ce1e\U0001ce1f\U0001ce25', '\xa0\xa0\xa0'),
    '.': ('\xa0\xa0\xa0', '\xa0\xa0\xa0', '\xa0\u2598\xa0'),
    '/': ('\xa0\xa0\U0001ce1c', '\U0001ce2c\U0001ce34\U0001ce3b', '\U0001ce3c\xa0\xa0'),
    '0': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce29\U0001ce4b\U0001ce29', '\U0001ce3e\U0001ce1f\U0001ce43'),
    '1': ('\U0001ce2c\U0001ce26\xa0', '\xa0\U0001ce29\xa0', '\U0001ce1e\U0001ce40\U0001ce25'),
    '2': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce1a\U0001ce1f\U0001ce43', '\U0001ce3d\U0001ce1f\U0001ce25'),
    '3': ('\U0001ce1a\U0001ce1f\U0001ce24', '\xa0\U0001ce1f\U0001ce37', '\U0001ce3e\U0001ce1f\U0001ce43'),
    '4': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce3d\U0001ce1f\U0001ce3a', '\xa0\xa0\U0001ce3c'),
    '5': ('\U0001ce1b\U0001ce1f\U0001ce25', '\U0001ce3d\U0001ce1f\U0001ce24', '\U0001ce1e\U0001ce1f\U0001ce43'),
    '6': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce28\U0001ce1f\U0001ce24', '\U0001ce3e\U0001ce1f\U0001ce43'),
    '7': ('\U0001ce1e\U0001ce1f\U0001ce27', '\xa0\U0001ce35\U0001ce3b', '\xa0\U0001ce3c\xa0'),
    '8': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce2e\U0001ce1f\U0001ce37', '\U0001ce3e\U0001ce1f\U0001ce43'),
    '9': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce3e\U0001ce1f\U0001ce36', '\U0001ce3e\U0001ce1f\U0001ce43'),
    ':': ('\xa0\xa0\xa0', '\xa0\U0001fbe4\xa0', '\xa0\U0001fbe4\xa0'),
    ';': ('\xa0\xa0\xa0', '\xa0\U0001ce50\xa0', '\xa0\U0001ce43\xa0'),
    '<': ('\xa0\xa0\U0001ce2c\xa0', '\xa0\U0001ce32\U0001ce38\xa0', '\xa0\xa0\U0001ce2b\xa0'),
    '=': ('\xa0\u2581\u2581\u2581\xa0', '\xa0\u2581\u2581\u2581\xa0', '\xa0\xa0\xa0\xa0\xa0'),
    '>': ('\xa0\U0001ce22\xa0\xa0', '\xa0\U0001ce2a\U0001ce32\xa0', '\xa0\U0001ce3b\xa0\xa0'),
    '?': ('\U0001ce1a\U0001ce1f\U0001ce24', '\xa0\U0001ce1a\U0001ce43', '\xa0\U0001ce4a\xa0'),
    '@': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce1a\U0001ce27\U0001ce29', '\U0001ce3e\U0001ce40\U0001ce43'),
    'A': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce28\U0001ce1f\U0001ce36', '\U0001ce3c\xa0\U0001ce3c'),
    'B': ('\U0001ce1b\U0001ce1f\U0001ce24', '\U0001ce28\U0001ce1f\U0001ce37', '\U0001ce3d\U0001ce1f\U0001ce43'),
    'C': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce29\xa0\xa0', '\U0001ce3e\U0001ce1f\U0001ce43'),
    'D': ('\U0001ce1b\U0001ce1f\U0001ce24', '\U0001ce29\xa0\U0001ce29', '\U0001ce3d\U0001ce1f\U0001ce43'),
    'E': ('\U0001ce1b\U0001ce1f\U0001ce25', '\U0001ce28\U0001ce1f\xa0', '\U0001ce3d\U0001ce1f\U0001ce25'),
    'F': ('\U0001ce1b\U0001ce1f\U0001ce25', '\U0001ce28\U0001ce1f\xa0', '\U0001ce3c\xa0\xa0'),
    'G': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce29\xa0\U0001ce27', '\U0001ce3e\U0001ce1f\U0001ce44'),
    'H': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce28\U0001ce1f\U0001ce36', '\U0001ce3c\xa0\U0001ce3c'),
    'I': ('\U0001ce1e\U0001ce20\U0001ce25', '\xa0\U0001ce29\xa0', '\U0001ce1e\U0001ce40\U0001ce25'),
    'J': ('\xa0\xa0\U0001ce1c', '\xa0\xa0\U0001ce29', '\U0001ce3e\U0001ce1f\U0001ce43'),
    'K': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce28\U0001ce2f\U0001ce38', '\U0001ce3c\xa0\U0001ce3c'),
    'L': ('\U0001ce1c\xa0\xa0', '\U0001ce29\xa0\xa0', '\U0001ce3d\U0001ce1f\U0001ce25'),
    'M': ('\U0001ce1d\U0001ce21\U0001ce26', '\U0001ce29\U0001ce30\U0001ce29', '\U0001ce3c\xa0\U0001ce3c'),
    'N': ('\U0001ce1d\U0001ce22\U0001ce1c', '\U0001ce29\U0001ce2b\U0001ce39', '\U0001ce3c\xa0\U0001ce3c'),
    'O': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce29\xa0\U0001ce29', '\U0001ce3e\U0001ce1f\U0001ce43'),
    'P': ('\U0001ce1b\U0001ce1f\U0001ce24', '\U0001ce28\U0001ce1f\U0001ce43', '\U0001ce3c\xa0\xa0'),
    'Q': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce29\xa0\U0001ce29', '\U0001ce3e\U0001ce1f\U0001ce45'),
    'R': ('\U0001ce1b\U0001ce1f\U0001ce24', '\U0001ce28\U0001ce1f\U0001ce37', '\U0001ce3c\xa0\U0001ce3c'),
    'S': ('\U0001ce1a\U0001ce1f\U0001ce24', '\U0001ce3e\U0001ce1f\U0001ce24', '\U0001ce3e\U0001ce1f\U0001ce43'),
    'T': ('\U0001ce1e\U0001ce20\U0001ce25', '\xa0\U0001ce29\xa0', '\xa0\U0001ce3c\xa0'),
    'U': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce29\xa0\U0001ce29', '\U0001ce3e\U0001ce1f\U0001ce43'),
    'V': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce29\xa0\U0001ce29', '\U0001ce2b\U0001ce41\U0001ce3b'),
    'W': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce29\U0001ce31\U0001ce29', '\U0001ce3f\U0001ce42\U0001ce46'),
    'X': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce2a\U0001ce32\U0001ce38', '\U0001ce3c\xa0\U0001ce3c'),
    'Y': ('\U0001ce1c\xa0\U0001ce1c', '\U0001ce2b\U0001ce33\U0001ce3b', '\xa0\U0001ce3c\xa0'),
    'Z': ('\U0001ce1e\U0001ce1f\U0001ce27', '\U0001ce2c\U0001ce34\U0001ce3b', '\U0001ce3d\U0001ce1f\U0001ce25'),
    '[': ('\xa0\U0001ce1b\U0001ce25', '\xa0\U0001ce29\xa0', '\xa0\U0001ce3d\U0001ce25'),
    '\\': ('\U0001ce1c\xa0\xa0', '\U0001ce2b\U0001ce32\U0001ce22', '\xa0\xa0\U0001ce3c'),
    ']': ('\U0001ce1e\U0001ce27\xa0', '\xa0\U0001ce29\xa0', '\U0001ce1e\U0001ce44\xa0'),
    '^': ('\xa0\U0001ce31\xa0', '\xa0\U0001ce42\xa0', '\xa0\xa0\xa0'),
    '_': ('\xa0\xa0\xa0', '\xa0\xa0\xa0', '\U0001ce1e\U0001ce1f\U0001ce25'),
    '`': ('\xa0\U0001ce22\xa0', '\xa0\U0001ce2b\xa0', '\xa0\xa0\xa0'),
    'a': ('\xa0\xa0', '\U0001ce1e\U0001ce24', '\U0001ce3e\U0001ce44'),
    'b': ('\U0001ce1c\xa0', '\U0001ce28\U0001ce24', '\U0001ce3d\U0001ce43'),
    'c': ('\xa0\xa0', '\U0001ce1a\U0001ce25', '\U0001ce3e\U0001ce25'),
    'd': ('\xa0\U0001ce1c', '\U0001ce1a\U0001ce36', '\U0001ce3e\U0001ce44'),
    'e': ('\xa0\xa0', '\U0001ce1a\U0001ce24', '\U0001ce3e\U0001ce25'),
    'f': ('\U0001ce1a\U0001ce25', '\U0001ce3a\U0001ce25', '\U0001ce3c\xa0'),
    'g': ('\xa0\xa0', '\U0001ce1a\U0001ce27', '\U0001ce3e\U0001ce36'),
    'h': ('\U0001ce1c\xa0', '\U0001ce28\U0001ce24', '\U0001ce3c\U0001ce3c'),
    'i': ('\U0001ce23', '\U0001ce1c', '\U0001ce3c'),
    'j': ('\xa0\U0001ce23', '\xa0\U0001ce1c', '\U0001ce1e\U0001ce43'),
    'k': ('\U0001ce1c\xa0', '\U0001ce28\U0001ce37', '\U0001ce3c\U0001ce3c'),
    'l': ('\U0001ce1c\xa0', '\U0001ce29\xa0', '\U0001ce3e\U0001ce25'),
    'm': ('\xa0\xa0\xa0', '\U0001ce1b\U0001ce20\U0001ce24', '\U0001ce3c\U0001ce3c\U0001ce3c'),
    'n': ('\xa0\xa0', '\U0001ce1b\U0001ce24', '\U0001ce3c\U0001ce3c'),
    'o': ('\xa0\xa0', '\U0001ce1a\U0001ce24', '\U0001ce3e\U0001ce43'),
    'p': ('\xa0\xa0', '\U0001ce1b\U0001ce24', '\U0001ce28\U0001ce43'),
    'q': ('\xa0\xa0', '\U0001ce1a\U0001ce27', '\U0001ce3e\U0001ce36'),
    'r': ('\xa0\xa0', '\U0001ce1b\U0001ce25', '\U0001ce3c\xa0'),
    's': ('\xa0\xa0', '\U0001ce1a\U0001ce25', '\U0001ce1e\U0001ce43'),
    't': ('\U0001ce23\xa0', '\U0001ce3a\U0001ce25', '\U0001ce3e\U0001ce25'),
    'u': ('\xa0\xa0', '\U0001ce1c\U0001ce1c', '\U0001ce3e\U0001ce44'),
    'v': ('\xa0\xa0', '\U0001ce1c\U0001ce1c', '\U0001ce3e\U0001ce43'),
    'w': ('\xa0\xa0', '\U0001ce1c\U0001ce1c', '\U0001ce3f\U0001ce46'),
    'x': ('\xa0\xa0', '\U0001ce2e\U0001ce37', '\U0001ce3c\U0001ce3c'),
    'y': ('\xa0\xa0', '\U0001ce1c\U0001ce1c', '\U0001ce3e\U0001ce36'),
    'z': ('\xa0\xa0', '\U0001ce1e\U0001ce27', '\U0001ce3d\U0001ce25'),
    '{': ('\xa0\U0001ce1a\U0001ce25', '\xa0\U0001ce37\xa0', '\xa0\U0001ce3e\U0001ce25'),
    '|': ('\xa0\U0001ce48\xa0', '\xa0\U0001ce29\xa0', '\xa0\U0001ce4c\xa0'),
    '}': ('\U0001ce1e\U0001ce24\xa0', '\xa0\U0001ce2e\xa0', '\U0001ce1e\U0001ce43\xa0'),
    '~': ('\xa0\xa0\xa0', '\U0001ce1a\U0001ce1f\U0001ce43', '\xa0\xa0\xa0'),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print supported ASCII characters rendered with Flightline's "
            "Unicode large type pieces."
        )
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Optional custom supported ASCII text to render instead of the full demo.",
    )
    parser.add_argument(
        "--per-line",
        type=int,
        default=DEFAULT_PER_LINE,
        help="Number of input characters per rendered block.",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Only print rendered large type rows.",
    )
    args = parser.parse_args()

    if args.per_line < 1:
        parser.error("--per-line must be at least 1")

    return args


def section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def glyph_for(character: str) -> tuple[str, str, str]:
    try:
        return LARGE_TYPE_GLYPHS[character]
    except KeyError as error:
        raise ValueError(f"unsupported character: {character!r}") from error


def render_text(text: str) -> list[str]:
    rows = ["", "", ""]

    for index, character in enumerate(text):
        glyph = glyph_for(character)
        separator = "" if index == 0 else " "
        for row_index, glyph_row in enumerate(glyph):
            rows[row_index] += separator + glyph_row

    return rows


def chunks(text: str, chunk_size: int) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def print_large_text(text: str, per_line: int, include_labels: bool) -> None:
    for chunk in chunks(text, per_line):
        if include_labels:
            print(chunk)

        for row in render_text(chunk):
            print(row)
        print()


def print_demo(per_line: int, include_labels: bool) -> None:
    if include_labels:
        print(DEMO_HEADING)

    for row in render_text(DEMO_TITLE):
        print(row)
    print()

    for title, text in DEMO_SECTIONS:
        if include_labels:
            section(title)
        print_large_text(text, per_line, include_labels)


def main() -> int:
    args = parse_args()
    include_labels = not args.no_labels
    text = " ".join(args.text)

    try:
        if text:
            print_large_text(text, args.per_line, include_labels)
        else:
            print_demo(args.per_line, include_labels)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
