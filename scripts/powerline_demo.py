#!/usr/bin/env python3
"""Print ANSI-colored Powerline prompt and status-line demos."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass


RESET = "\033[0m"
DEFAULT_WIDTH = 92

BRANCH = ""
LINE_NUMBER = ""
LOCKED = ""
RIGHT_SEPARATOR = ""
RIGHT_THIN_SEPARATOR = ""
LEFT_SEPARATOR = ""
LEFT_THIN_SEPARATOR = ""
RIGHT_ROUNDED = ""
LEFT_ROUNDED = ""
RIGHT_FLAME = ""
LEFT_FLAME = ""

ANSI_RE = re.compile(r"\033\[[0-9;]*m")
Color = tuple[int, int, int]

BLACK: Color = (24, 27, 36)
WHITE: Color = (244, 247, 250)
MUTED: Color = (178, 186, 197)
CHARCOAL: Color = (43, 48, 59)
SLATE: Color = (70, 80, 96)
BLUE: Color = (42, 97, 204)
CYAN: Color = (39, 159, 174)
GREEN: Color = (75, 154, 92)
YELLOW: Color = (211, 160, 67)
RED: Color = (194, 72, 76)
PURPLE: Color = (126, 87, 194)


@dataclass(frozen=True)
class Segment:
    text: str
    fg: Color
    bg: Color
    bold: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print typical Powerline prompt and status-line samples."
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help="Target width for the combined status-line sample.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Print Powerline glyphs without ANSI color escape sequences.",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Only print the demo lines.",
    )
    args = parser.parse_args()

    if args.width < 40:
        parser.error("--width must be at least 40")

    return args


def ansi(*, fg: Color | None = None, bg: Color | None = None, bold: bool = False) -> str:
    codes: list[str] = []
    if bold:
        codes.append("1")
    if fg is not None:
        codes.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")
    if bg is not None:
        codes.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")

    return f"\033[{';'.join(codes) if codes else '0'}m"


def paint(
    text: str,
    *,
    fg: Color | None = None,
    bg: Color | None = None,
    bold: bool = False,
    color: bool = True,
) -> str:
    if not color:
        return text
    return f"{ansi(fg=fg, bg=bg, bold=bold)}{text}{RESET}"


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def section(title: str, include_labels: bool) -> None:
    if not include_labels:
        return
    print()
    print(title)
    print("=" * len(title))


def render_left_segments(
    segments: list[Segment],
    *,
    final_separator: str = RIGHT_SEPARATOR,
    color: bool = True,
) -> str:
    pieces: list[str] = []

    for index, segment in enumerate(segments):
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        pieces.append(
            paint(
                f" {segment.text} ",
                fg=segment.fg,
                bg=segment.bg,
                bold=segment.bold,
                color=color,
            )
        )

        separator_bg = next_segment.bg if next_segment is not None else None
        pieces.append(
            paint(
                final_separator,
                fg=segment.bg,
                bg=separator_bg,
                color=color,
            )
        )

    return "".join(pieces)


def render_right_segments(
    segments: list[Segment],
    *,
    initial_separator: str = LEFT_SEPARATOR,
    color: bool = True,
) -> str:
    pieces: list[str] = []

    for index, segment in enumerate(segments):
        previous_segment = segments[index - 1] if index > 0 else None
        separator_bg = previous_segment.bg if previous_segment is not None else None
        pieces.append(
            paint(
                initial_separator,
                fg=segment.bg,
                bg=separator_bg,
                color=color,
            )
        )
        pieces.append(
            paint(
                f" {segment.text} ",
                fg=segment.fg,
                bg=segment.bg,
                bold=segment.bold,
                color=color,
            )
        )

    return "".join(pieces)


def fit_status_line(left: str, right: str, width: int) -> str:
    gap_width = max(1, width - visible_len(left) - visible_len(right))
    return f"{left}{' ' * gap_width}{right}"


def print_prompt_samples(color: bool) -> None:
    print(
        render_left_segments(
            [
                Segment("user@flightline", WHITE, BLUE, bold=True),
                Segment("~/prj/fonts/flightline", WHITE, CHARCOAL),
                Segment(f"{BRANCH} codex/powerline-demo", WHITE, GREEN),
                Segment("3 files changed", BLACK, YELLOW),
            ],
            color=color,
        )
    )
    print(
        render_left_segments(
            [
                Segment("python", WHITE, PURPLE, bold=True),
                Segment("3.12.4", WHITE, SLATE),
                Segment(f"{BRANCH} main", WHITE, CYAN),
                Segment("tests passed", WHITE, GREEN),
            ],
            final_separator=RIGHT_ROUNDED,
            color=color,
        )
    )
    print(
        render_left_segments(
            [
                Segment("flightline", WHITE, CHARCOAL, bold=True),
                Segment("build", WHITE, BLUE),
                Segment("exit 1", WHITE, RED, bold=True),
                Segment("fix needed", BLACK, YELLOW),
            ],
            final_separator=RIGHT_FLAME,
            color=color,
        )
    )


def print_status_bar_sample(width: int, color: bool) -> None:
    left = render_left_segments(
        [
            Segment("NORMAL", WHITE, GREEN, bold=True),
            Segment("sources/features.txt", WHITE, CHARCOAL),
            Segment(f"{BRANCH} main", WHITE, BLUE),
        ],
        color=color,
    )
    right = render_right_segments(
        [
            Segment("utf-8", WHITE, SLATE),
            Segment(f"{LINE_NUMBER} 128", WHITE, PURPLE),
            Segment("col 24", WHITE, CYAN),
            Segment("100%", BLACK, YELLOW, bold=True),
        ],
        color=color,
    )
    print(fit_status_line(left, right, width))


def print_thin_separator_sample(color: bool) -> None:
    print(
        paint(" git ", fg=WHITE, bg=CHARCOAL, color=color)
        + paint(RIGHT_THIN_SEPARATOR, fg=MUTED, bg=CHARCOAL, color=color)
        + paint(f" {BRANCH} main ", fg=WHITE, bg=CHARCOAL, color=color)
        + paint(RIGHT_THIN_SEPARATOR, fg=MUTED, bg=CHARCOAL, color=color)
        + paint(" +12 -4 ", fg=WHITE, bg=CHARCOAL, color=color)
    )
    print(
        paint(" " + LEFT_THIN_SEPARATOR + " ", fg=MUTED, color=color)
        + paint("readonly", fg=WHITE, bg=RED, bold=True, color=color)
        + paint(" " + LOCKED + " ", fg=WHITE, bg=RED, color=color)
        + paint(LEFT_THIN_SEPARATOR, fg=MUTED, bg=RED, color=color)
        + paint(" protected branch ", fg=WHITE, bg=RED, color=color)
    )


def print_separator_samples(color: bool) -> None:
    print(
        render_left_segments(
            [
                Segment("sharp", WHITE, BLUE),
                Segment("rounded", WHITE, PURPLE),
                Segment("flame", WHITE, RED),
            ],
            color=color,
        )
    )
    print(
        render_left_segments(
            [
                Segment("sharp", WHITE, BLUE),
                Segment("rounded", WHITE, PURPLE),
                Segment("flame", WHITE, RED),
            ],
            final_separator=RIGHT_ROUNDED,
            color=color,
        )
    )
    print(
        render_right_segments(
            [
                Segment("left sharp", WHITE, BLUE),
                Segment("left rounded", WHITE, PURPLE),
                Segment("left flame", WHITE, RED),
            ],
            color=color,
        )
    )
    print(
        render_right_segments(
            [
                Segment("left sharp", WHITE, BLUE),
                Segment("left rounded", WHITE, PURPLE),
                Segment("left flame", WHITE, RED),
            ],
            initial_separator=LEFT_ROUNDED,
            color=color,
        )
    )
    print(
        render_right_segments(
            [
                Segment("left sharp", WHITE, BLUE),
                Segment("left rounded", WHITE, PURPLE),
                Segment("left flame", WHITE, RED),
            ],
            initial_separator=LEFT_FLAME,
            color=color,
        )
    )


def print_demo(width: int, color: bool, include_labels: bool) -> None:
    if include_labels:
        print("Flightline Powerline demo")
        print("ANSI true-color prompt and status-line samples")

    section("Shell Prompts", include_labels)
    print_prompt_samples(color)

    section("Status Bar", include_labels)
    print_status_bar_sample(width, color)

    section("Thin Separators", include_labels)
    print_thin_separator_sample(color)

    section("Separator Shapes", include_labels)
    print_separator_samples(color)


def main() -> int:
    args = parse_args()
    print_demo(args.width, not args.no_color, not args.no_labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
