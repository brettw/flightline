#!/usr/bin/env python3
"""Print Unicode characters from hex codepoint arguments."""

from __future__ import annotations

import argparse
import sys


if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


DESCRIPTION = (
    "Print a string made from one or more Unicode codepoints written as "
    "hexadecimal numbers."
)

EPILOG = """examples:
  scripts/unicode.py 2588
  scripts/unicode.py 2588 1fb01
  scripts/unicode.py 250c 2500 2510
"""


def character_from_hex(hex_text: str) -> str:
    try:
        codepoint = int(hex_text, 16)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid hex codepoint: {hex_text}")

    try:
        return chr(codepoint)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid Unicode codepoint: {hex_text}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "codepoints",
        metavar="HEX",
        nargs="*",
        type=character_from_hex,
        help="Unicode codepoint as hexadecimal, for example 2588 or 1fb01.",
    )

    args = parser.parse_args(argv)
    if not args.codepoints:
        parser.print_help()
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.codepoints:
        print("".join(args.codepoints))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
