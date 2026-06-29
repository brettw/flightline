#!/usr/bin/env python3
"""Audit Cascadia symbol glyphs that are not present in Flightline sources."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASCADIA_PATH = REPO_ROOT / "sources" / "CascadiaCode-Regular.vfj"
FLIGHTLINE_DIR = REPO_ROOT / "sources" / "vfj"


@dataclass(frozen=True)
class CodepointRange:
    start: int
    end: int

    def contains(self, codepoint: int) -> bool:
        return self.start <= codepoint <= self.end


@dataclass(frozen=True)
class AuditBlock:
    label: str
    ranges: tuple[CodepointRange, ...]
    note: str = ""
    exclude: tuple[CodepointRange, ...] = ()

    def contains(self, codepoint: int) -> bool:
        return any(item.contains(codepoint) for item in self.ranges) and not any(
            item.contains(codepoint) for item in self.exclude
        )


@dataclass(frozen=True)
class GlyphRecord:
    codepoint: int
    preferred_name: str


AUDIT_BLOCKS: tuple[AuditBlock, ...] = (
    AuditBlock(
        "Line and box drawing",
        (
            CodepointRange(0x2500, 0x257F),
            CodepointRange(0x2580, 0x259F),
        ),
        "Box Drawing plus Block Elements.",
    ),
    AuditBlock("Geometric Shapes", (CodepointRange(0x25A0, 0x25FF),)),
    AuditBlock(
        "Miscellaneous Symbols and Arrows Geometric Shapes",
        (CodepointRange(0x2B12, 0x2B2F),),
        "Square, diamond, pentagon, hexagon, circle, lozenge, and ellipse shapes.",
    ),
    AuditBlock("Braille Patterns", (CodepointRange(0x2800, 0x28FF),)),
    AuditBlock("Symbols for Legacy Computing", (CodepointRange(0x1FB00, 0x1FBFF),)),
    AuditBlock(
        "Symbols for Legacy Computing Supplement",
        (CodepointRange(0x1CC00, 0x1CEBF),),
        (
            "Separated quadrant, octant, separated sextant, and sedecimant "
            "mosaic pieces. Excludes Large Type Pieces, which are listed separately."
        ),
        exclude=(CodepointRange(0x1CE1A, 0x1CE50),),
    ),
    AuditBlock(
        "Large Type Pieces",
        (CodepointRange(0x1CE1A, 0x1CE50),),
        "Cascadia's encoded largeType-* run.",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Cascadia symbol glyphs that are encoded in selected Unicode "
            "ranges and missing from the Flightline VFJ sources."
        )
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        required=True,
        help="Print the Cascadia symbol glyph audit.",
    )
    return parser.parse_args()


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_glyphs(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as font_file:
            data = json.load(font_file)
    except OSError as error:
        raise SystemExit(f"{relative_path(path)}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"{relative_path(path)}: invalid JSON: {error}") from error

    font = data.get("font")
    if not isinstance(font, dict):
        raise SystemExit(f"{relative_path(path)}: expected top-level 'font' object")

    glyphs = font.get("glyphs")
    if not isinstance(glyphs, list):
        raise SystemExit(f"{relative_path(path)}: expected font.glyphs list")

    return [glyph for glyph in glyphs if isinstance(glyph, dict)]


def parse_codepoint(glyph: dict[str, Any]) -> int | None:
    value = glyph.get("unicode")
    if not isinstance(value, str) or not value:
        return None

    try:
        return int(value, 16)
    except ValueError:
        return None


def glyph_name(glyph: dict[str, Any]) -> str | None:
    name = glyph.get("name")
    return name if isinstance(name, str) else None


def cascadia_records(glyphs: list[dict[str, Any]]) -> dict[int, GlyphRecord]:
    names = {name for glyph in glyphs if (name := glyph_name(glyph)) is not None}
    records: dict[int, GlyphRecord] = {}

    for glyph in glyphs:
        name = glyph_name(glyph)
        codepoint = parse_codepoint(glyph)
        if name is None or codepoint is None:
            continue

        stypo_name = f"{name}.stypo"
        preferred_name = stypo_name if stypo_name in names else name
        candidate = GlyphRecord(codepoint, preferred_name)
        existing = records.get(codepoint)

        if existing is None:
            records[codepoint] = candidate
            continue

        candidate_is_stypo = candidate.preferred_name.endswith(".stypo")
        existing_is_stypo = existing.preferred_name.endswith(".stypo")
        if candidate_is_stypo and not existing_is_stypo:
            records[codepoint] = candidate

    return records


def flightline_paths() -> list[Path]:
    def sort_key(path: Path) -> tuple[int, str]:
        if "Regular" in path.name:
            return (0, path.name)
        if "Italic" in path.name:
            return (1, path.name)
        return (2, path.name)

    paths = sorted(FLIGHTLINE_DIR.glob("Flightline*.vfj"), key=sort_key)
    if len(paths) != 2:
        raise SystemExit(
            f"{relative_path(FLIGHTLINE_DIR)}: expected exactly 2 Flightline*.vfj files, "
            f"found {len(paths)}"
        )
    return paths


def encoded_codepoints(path: Path) -> set[int]:
    codepoints: set[int] = set()
    for glyph in load_glyphs(path):
        codepoint = parse_codepoint(glyph)
        if codepoint is not None:
            codepoints.add(codepoint)
    return codepoints


def missing_paths(
    codepoint: int, flightline_codepoints: dict[Path, set[int]]
) -> tuple[Path, ...]:
    return tuple(
        path for path, codepoints in flightline_codepoints.items() if codepoint not in codepoints
    )


def records_for_block(
    block: AuditBlock,
    records_by_codepoint: dict[int, GlyphRecord],
    flightline_codepoints: dict[Path, set[int]],
) -> list[tuple[GlyphRecord, tuple[Path, ...]]]:
    records: list[tuple[GlyphRecord, tuple[Path, ...]]] = []
    for codepoint in sorted(records_by_codepoint):
        if not block.contains(codepoint):
            continue

        missing = missing_paths(codepoint, flightline_codepoints)
        if missing:
            records.append((records_by_codepoint[codepoint], missing))

    return records


def audit() -> int:
    cascadia_glyphs = load_glyphs(CASCADIA_PATH)
    records_by_codepoint = cascadia_records(cascadia_glyphs)
    paths = flightline_paths()
    flightline_codepoints = {path: encoded_codepoints(path) for path in paths}

    missing_records: dict[int, GlyphRecord] = {}
    for block in AUDIT_BLOCKS:
        for record, _missing in records_for_block(
            block, records_by_codepoint, flightline_codepoints
        ):
            missing_records[record.codepoint] = record

    for codepoint in sorted(missing_records):
        record = missing_records[codepoint]
        print(f"U+{record.codepoint:04X} {record.preferred_name}")

    return 0


def main() -> int:
    parse_args()
    return audit()


if __name__ == "__main__":
    raise SystemExit(main())
