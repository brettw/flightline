#!/usr/bin/env python3
"""Print a visual demo of Flightline's box drawing glyph coverage."""

from __future__ import annotations

import argparse
import unicodedata
from dataclasses import dataclass
from pathlib import Path


BOX_DRAWING_START = 0x2500
BOX_DRAWING_END = 0x257F
GLYPH_LIST_PATH = Path(__file__).resolve().with_name("glyphs_from_cascadia.txt")


@dataclass(frozen=True)
class BoxStyle:
    upper_left: str
    horizontal: str
    upper_right: str
    vertical: str
    tee_left: str
    cross: str
    tee_right: str
    lower_left: str
    tee_up: str
    lower_right: str


LIGHT_BOX = BoxStyle("┌", "─", "┐", "│", "├", "┼", "┤", "└", "┴", "┘")
HEAVY_BOX = BoxStyle("┏", "━", "┓", "┃", "┣", "╋", "┫", "┗", "┻", "┛")
DOUBLE_BOX = BoxStyle("╔", "═", "╗", "║", "╠", "╬", "╣", "╚", "╩", "╝")
ROUNDED_BOX = BoxStyle("╭", "─", "╮", "│", "├", "┼", "┤", "╰", "┴", "╯")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print sample single, double, heavy, dashed, mixed, rounded, diagonal, "
            "and partial box drawing characters used by Flightline."
        )
    )
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Only print the compact U+2500-U+257F catalog.",
    )
    parser.add_argument(
        "--no-catalog",
        action="store_true",
        help="Skip the compact U+2500-U+257F catalog.",
    )
    parser.add_argument(
        "--names",
        action="store_true",
        help="Also print the Flightline glyph-name mapping for every box drawing codepoint.",
    )
    return parser.parse_args()


def load_box_drawing_names() -> dict[int, str]:
    names: dict[int, str] = {}

    try:
        lines = GLYPH_LIST_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names

    for line in lines:
        parts = line.split()
        if len(parts) != 2 or not parts[0].startswith("U+"):
            continue

        try:
            codepoint = int(parts[0][2:], 16)
        except ValueError:
            continue

        if BOX_DRAWING_START <= codepoint <= BOX_DRAWING_END:
            names[codepoint] = parts[1].removesuffix(".stypo")

    return names


def section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def box(style: BoxStyle, title: str, width: int = 18) -> list[str]:
    label = title[:width].center(width)
    return [
        f"{style.upper_left}{style.horizontal * width}{style.upper_right}",
        f"{style.vertical}{label}{style.vertical}",
        f"{style.tee_left}{style.horizontal * (width // 2)}"
        f"{style.cross}{style.horizontal * (width - width // 2 - 1)}{style.tee_right}",
        f"{style.vertical}{'left'.center(width // 2)}"
        f"{style.vertical}{'right'.center(width - width // 2 - 1)}{style.vertical}",
        f"{style.lower_left}{style.horizontal * (width // 2)}"
        f"{style.tee_up}{style.horizontal * (width - width // 2 - 1)}{style.lower_right}",
    ]


def print_columns(rows: list[tuple[str, str]], label_width: int = 27) -> None:
    for label, value in rows:
        print(f"{label:<{label_width}} {value}")


def print_demo(names: dict[int, str]) -> None:
    glyph_count = len(names)
    source_note = (
        f"{glyph_count} glyphs from {GLYPH_LIST_PATH.name}"
        if glyph_count
        else f"glyph names unavailable; expected {GLYPH_LIST_PATH.name}"
    )

    print("Flightline box drawing demo")
    print(f"Definition range: U+2500-U+257F ({source_note})")

    section("Line Weights And Dashes")
    print_columns(
        [
            ("Light single", "────────  │ │ │"),
            ("Heavy single", "━━━━━━━━  ┃ ┃ ┃"),
            ("Double", "════════  ║ ║ ║"),
            ("Light triple dash", "┄┄┄┄┄┄┄┄  ┆ ┆ ┆"),
            ("Heavy triple dash", "┅┅┅┅┅┅┅┅  ┇ ┇ ┇"),
            ("Light quadruple dash", "┈┈┈┈┈┈┈┈  ┊ ┊ ┊"),
            ("Heavy quadruple dash", "┉┉┉┉┉┉┉┉  ┋ ┋ ┋"),
            ("Light double dash", "╌╌╌╌╌╌╌╌  ╎ ╎ ╎"),
            ("Heavy double dash", "╍╍╍╍╍╍╍╍  ╏ ╏ ╏"),
        ]
    )

    section("Complete Boxes")
    for style, title in (
        (LIGHT_BOX, "single"),
        (HEAVY_BOX, "heavy"),
        (DOUBLE_BOX, "double"),
        (ROUNDED_BOX, "rounded"),
    ):
        for line in box(style, title):
            print(line)
        print()

    section("Single To Double Transitions")
    print("╔════╤════╗  top tee keeps the outer horizontal double")
    print("║    │    ║")
    print("╟────┼────╢  side tees bridge double vertical to single horizontal")
    print("║    │    ║")
    print("╚════╧════╝")
    print()
    print_columns(
        [
            ("Corners down/right", "╒ ╓ ╔"),
            ("Corners down/left", "╕ ╖ ╗"),
            ("Corners up/right", "╘ ╙ ╚"),
            ("Corners up/left", "╛ ╜ ╝"),
            ("Right tees", "╞ ╟ ╠"),
            ("Left tees", "╡ ╢ ╣"),
            ("Down tees", "╤ ╥ ╦"),
            ("Up tees", "╧ ╨ ╩"),
            ("Crosses", "╪ ╫ ╬"),
        ]
    )

    section("Light And Heavy Transitions")
    print_columns(
        [
            ("Corners down/right", "┌ ┍ ┎ ┏"),
            ("Corners down/left", "┐ ┑ ┒ ┓"),
            ("Corners up/right", "└ ┕ ┖ ┗"),
            ("Corners up/left", "┘ ┙ ┚ ┛"),
            ("Right tees", "├ ┝ ┞ ┟ ┠ ┡ ┢ ┣"),
            ("Left tees", "┤ ┥ ┦ ┧ ┨ ┩ ┪ ┫"),
            ("Down tees", "┬ ┭ ┮ ┯ ┰ ┱ ┲ ┳"),
            ("Up tees", "┴ ┵ ┶ ┷ ┸ ┹ ┺ ┻"),
            ("Crosses", "┼ ┽ ┾ ┿ ╀ ╁ ╂ ╃ ╄ ╅ ╆ ╇ ╈ ╉ ╊ ╋"),
        ]
    )
    print()
    print("┌────┬┰┬────┐")
    print("│    │┃│    │")
    print("├────┼╂┼────┤")
    print("┃    ┃┃┃    ┃")
    print("┗━━━━┻╋┻━━━━┛")

    section("Rounded, Diagonal, And Partial Lines")
    print_columns(
        [
            ("Rounded corners", "╭────────╮  ╰────────╯"),
            ("Diagonals", "╱ ╲ ╳"),
            ("Light partials", "╴ ╵ ╶ ╷"),
            ("Heavy partials", "╸ ╹ ╺ ╻"),
            ("Light/heavy partials", "╼ ╽ ╾ ╿"),
        ]
    )


def print_catalog(names: dict[int, str], include_names: bool) -> None:
    section("U+2500-U+257F Catalog")

    for start in range(BOX_DRAWING_START, BOX_DRAWING_END + 1, 16):
        chars = "".join(chr(codepoint) for codepoint in range(start, start + 16))
        print(f"U+{start:04X}  {chars}")

    missing = [
        codepoint
        for codepoint in range(BOX_DRAWING_START, BOX_DRAWING_END + 1)
        if codepoint not in names
    ]
    if missing:
        values = " ".join(f"U+{codepoint:04X}" for codepoint in missing)
        print(f"\nMissing from {GLYPH_LIST_PATH.name}: {values}")

    if include_names:
        section("Flightline Glyph Names")
        for codepoint in range(BOX_DRAWING_START, BOX_DRAWING_END + 1):
            character = chr(codepoint)
            glyph_name = names.get(codepoint, "(not listed)")
            unicode_name = unicodedata.name(character, "(unnamed)").title()
            print(f"U+{codepoint:04X}  {character}  {glyph_name:<42} {unicode_name}")


def main() -> int:
    args = parse_args()
    names = load_box_drawing_names()

    if not args.catalog_only:
        print_demo(names)

    if not args.no_catalog:
        print_catalog(names, args.names)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
