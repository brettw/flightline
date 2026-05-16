#!/usr/bin/env python3
"""Set nonzero glyph widths in a VFF/VFJ JSON font source."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional, Union


AUXILIARY_LAYER_NAMES = {"mask", "img"}
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

Number = Union[int, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set each nonzero glyph advance width to NEW_WIDTH, centering the "
            "glyph by adding/removing space from both sides."
        )
    )
    parser.add_argument("font_file", type=Path, help="Path to a .vff or .vfj font file")
    parser.add_argument("new_width", type=int, help="New nonzero glyph width")
    parser.add_argument(
        "--layer",
        help="Layer name to adjust. Defaults to the active/non-auxiliary glyph layer.",
    )
    return parser.parse_args()


def load_data(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as font_file:
            data = json.load(font_file)
    except OSError as error:
        raise SystemExit(f"{path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: invalid JSON: {error}") from error

    if not isinstance(data.get("font"), dict):
        raise SystemExit(f"{path}: expected top-level 'font' object")
    return data


def select_layer(glyph: dict[str, Any], requested_layer: Optional[str]) -> Optional[dict[str, Any]]:
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
                return layer
        return None

    for layer in width_layers:
        if layer.get("active") and layer.get("name") not in AUXILIARY_LAYER_NAMES:
            return layer

    for layer in width_layers:
        if layer.get("name") not in AUXILIARY_LAYER_NAMES:
            return layer

    return width_layers[0] if width_layers else None


def split_width_delta(old_width: Number, new_width: int) -> tuple[int, int]:
    delta = new_width - int(old_width)
    left = int(delta / 2)
    right = delta - left
    return left, right


def parse_number(token: str) -> Optional[Number]:
    if not NUMBER_RE.match(token):
        return None
    if "." in token:
        return float(token)
    return int(token)


def format_number(value: Number) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def shifted_node(node: str, shift: int) -> str:
    tokens = node.split()
    numeric_index = 0

    for index, token in enumerate(tokens):
        value = parse_number(token)
        if value is None:
            continue

        if numeric_index % 2 == 0:
            tokens[index] = format_number(value + shift)

        numeric_index += 1

    return " ".join(tokens)


def node_x_values(node: str, x_scale: Number, x_offset: Number) -> list[Number]:
    values: list[Number] = []
    numeric_index = 0

    for token in node.split():
        value = parse_number(token)
        if value is None:
            continue

        if numeric_index % 2 == 0:
            values.append(value * x_scale + x_offset)

        numeric_index += 1

    return values


def layer_elements(layer: dict[str, Any]) -> list[dict[str, Any]]:
    elements = layer.get("elements", [])
    if not isinstance(elements, list):
        return []
    return [element for element in elements if isinstance(element, dict)]


def element_contours(element: dict[str, Any]) -> list[dict[str, Any]]:
    element_data = element.get("elementData", {})
    if not isinstance(element_data, dict):
        return []

    contours = element_data.get("contours", [])
    if not isinstance(contours, list):
        return []

    return [contour for contour in contours if isinstance(contour, dict)]


def shift_layer_points(layer: dict[str, Any], shift: int) -> None:
    for element in layer_elements(layer):
        transform = element.get("transform")
        if isinstance(transform, dict):
            transform["xOffset"] = transform.get("xOffset", 0) + shift
            continue

        for contour in element_contours(element):
            nodes = contour.get("nodes", [])
            if not isinstance(nodes, list):
                continue

            contour["nodes"] = [
                shifted_node(node, shift) if isinstance(node, str) else node
                for node in nodes
            ]


def layer_x_values(layer: dict[str, Any]) -> list[Number]:
    values: list[Number] = []

    for element in layer_elements(layer):
        transform = element.get("transform")
        if isinstance(transform, dict):
            x_scale = transform.get("xScale", 1)
            x_offset = transform.get("xOffset", 0)
        else:
            x_scale = 1
            x_offset = 0

        if not isinstance(x_scale, (int, float)):
            x_scale = 1
        if not isinstance(x_offset, (int, float)):
            x_offset = 0

        for contour in element_contours(element):
            nodes = contour.get("nodes", [])
            if not isinstance(nodes, list):
                continue

            for node in nodes:
                if isinstance(node, str):
                    values.extend(node_x_values(node, x_scale, x_offset))

    return values


def audit_layer(layer: dict[str, Any], new_width: int) -> dict[str, Number]:
    x_values = layer_x_values(layer)
    if not x_values:
        return {}

    audit: dict[str, Number] = {}
    leftmost = min(x_values)
    rightmost = max(x_values)

    if leftmost < 0:
        audit["left"] = -leftmost
    if rightmost > new_width:
        audit["right"] = rightmost - new_width

    return audit


def write_data(path: Path, data: dict[str, Any]) -> None:
    try:
        with path.open("w", encoding="utf-8") as font_file:
            json.dump(data, font_file, indent=2, separators=(",", ":"))
            font_file.write("\n")
    except OSError as error:
        raise SystemExit(f"{path}: {error}") from error


def main() -> int:
    args = parse_args()
    if args.new_width < 0:
        print("new_width must be non-negative", file=sys.stderr)
        return 1

    data = load_data(args.font_file)
    glyphs = data["font"].get("glyphs", [])
    if not isinstance(glyphs, list):
        print(f"{args.font_file}: expected font.glyphs list", file=sys.stderr)
        return 1

    audit_entries: list[tuple[str, dict[str, Number]]] = []

    for glyph in glyphs:
        if not isinstance(glyph, dict):
            continue

        name = glyph.get("name")
        if not isinstance(name, str):
            continue

        layer = select_layer(glyph, args.layer)
        if layer is None:
            continue

        old_width = layer.get("advanceWidth")
        if not isinstance(old_width, (int, float)) or old_width == 0:
            continue

        left_adjustment, _right_adjustment = split_width_delta(old_width, args.new_width)
        shift_layer_points(layer, left_adjustment)
        layer["advanceWidth"] = args.new_width

        audit = audit_layer(layer, args.new_width)
        if audit:
            audit_entries.append((name, audit))

    write_data(args.font_file, data)

    for name, audit in audit_entries:
        parts = [f"{side}={format_number(distance)}" for side, distance in audit.items()]
        print(f"{name}: {' '.join(parts)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
