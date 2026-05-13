#!/usr/bin/env python3
"""Summarize glyph advance widths in a VFF/VFJ JSON font source."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional, Union


AUXILIARY_LAYER_NAMES = {"mask", "img"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print glyph names grouped by advance width in a .vff/.vfj font file."
    )
    parser.add_argument("font_file", type=Path, help="Path to a .vff or .vfj font file")
    parser.add_argument(
        "--layer",
        help="Layer name to audit. Defaults to the active/non-auxiliary glyph layer.",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort widths from narrowest to widest. Default is widest to narrowest.",
    )
    return parser.parse_args()


def load_font(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as font_file:
            data = json.load(font_file)
    except OSError as error:
        raise SystemExit(f"{path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: invalid JSON: {error}") from error

    font = data.get("font")
    if not isinstance(font, dict):
        raise SystemExit(f"{path}: expected top-level 'font' object")
    return font


Width = Union[int, float]


def layer_width(glyph: dict[str, Any], requested_layer: Optional[str]) -> Optional[Width]:
    layers = glyph.get("layers", [])
    if not isinstance(layers, list):
        return None

    width_layers = [
        layer
        for layer in layers
        if isinstance(layer, dict) and isinstance(layer.get("advanceWidth"), (int, float))
    ]

    if requested_layer:
        for layer in width_layers:
            if layer.get("name") == requested_layer:
                return layer["advanceWidth"]
        return None

    for layer in width_layers:
        if layer.get("active") and layer.get("name") not in AUXILIARY_LAYER_NAMES:
            return layer["advanceWidth"]

    for layer in width_layers:
        if layer.get("name") not in AUXILIARY_LAYER_NAMES:
            return layer["advanceWidth"]

    if width_layers:
        return width_layers[0]["advanceWidth"]

    return None


def format_width(width: Width) -> str:
    if isinstance(width, float) and width.is_integer():
        return str(int(width))
    return str(width)


def main() -> int:
    args = parse_args()
    font = load_font(args.font_file)
    glyphs = font.get("glyphs", [])
    if not isinstance(glyphs, list):
        print(f"{args.font_file}: expected font.glyphs list", file=sys.stderr)
        return 1

    names_by_width: dict[Width, list[str]] = defaultdict(list)
    missing_widths: list[str] = []

    for glyph in glyphs:
        if not isinstance(glyph, dict):
            continue

        name = glyph.get("name")
        if not isinstance(name, str):
            continue

        width = layer_width(glyph, args.layer)
        if width is None:
            missing_widths.append(name)
            continue

        names_by_width[width].append(name)

    for width in sorted(names_by_width, reverse=not args.ascending):
        print(f"{format_width(width)}: {' '.join(names_by_width[width])}")

    if missing_widths:
        layer = f" on layer {args.layer!r}" if args.layer else ""
        print(
            f"warning: skipped {len(missing_widths)} glyphs without advanceWidth{layer}: "
            f"{' '.join(missing_widths)}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
