#!/usr/bin/env python3
"""Regenerate precomposed accented glyphs in a VFJ file using references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


# Update this table when adding or removing generated accented glyphs.
# Each row is (output glyph, base glyph, accent glyph, Unicode code point/comment).
ACCENTED_GLYPHS: tuple[tuple[str, str, str, str], ...] = (
    ("Agrave", "A", "gravecomb", "U+00C0 LATIN CAPITAL LETTER A WITH GRAVE"),
    ("Aacute", "A", "acute", "U+00C1 LATIN CAPITAL LETTER A WITH ACUTE"),
    ("Acircumflex", "A", "circumflex", "U+00C2 LATIN CAPITAL LETTER A WITH CIRCUMFLEX"),
    ("Atilde", "A", "tilde", "U+00C3 LATIN CAPITAL LETTER A WITH TILDE"),
    ("Adieresis", "A", "dieresis", "U+00C4 LATIN CAPITAL LETTER A WITH DIAERESIS"),
    ("Aring", "A", "ring", "U+00C5 LATIN CAPITAL LETTER A WITH RING ABOVE"),
    ("Egrave", "E", "gravecomb", "U+00C8 LATIN CAPITAL LETTER E WITH GRAVE"),
    ("Eacute", "E", "acute", "U+00C9 LATIN CAPITAL LETTER E WITH ACUTE"),
    ("Ecircumflex", "E", "circumflex", "U+00CA LATIN CAPITAL LETTER E WITH CIRCUMFLEX"),
    ("Edieresis", "E", "dieresis", "U+00CB LATIN CAPITAL LETTER E WITH DIAERESIS"),
    ("Igrave", "I", "gravecomb", "U+00CC LATIN CAPITAL LETTER I WITH GRAVE"),
    ("Iacute", "I", "acute", "U+00CD LATIN CAPITAL LETTER I WITH ACUTE"),
    ("Icircumflex", "I", "circumflex", "U+00CE LATIN CAPITAL LETTER I WITH CIRCUMFLEX"),
    ("Idieresis", "I", "dieresis", "U+00CF LATIN CAPITAL LETTER I WITH DIAERESIS"),
    ("egrave", "e", "gravecomb", "U+00E8 LATIN SMALL LETTER E WITH GRAVE"),
    ("eacute", "e", "acute", "U+00E9 LATIN SMALL LETTER E WITH ACUTE"),
    ("ecircumflex", "e", "circumflex", "U+00EA LATIN SMALL LETTER E WITH CIRCUMFLEX"),
    ("edieresis", "e", "dieresis", "U+00EB LATIN SMALL LETTER E WITH DIAERESIS"),
    ("agrave", "a", "gravecomb", "U+00E0 LATIN SMALL LETTER A WITH GRAVE"),
    ("aacute", "a", "acute", "U+00E1 LATIN SMALL LETTER A WITH ACUTE"),
    ("acircumflex", "a", "circumflex", "U+00E2 LATIN SMALL LETTER A WITH CIRCUMFLEX"),
    ("atilde", "a", "tilde", "U+00E3 LATIN SMALL LETTER A WITH TILDE"),
    ("adieresis", "a", "dieresis", "U+00E4 LATIN SMALL LETTER A WITH DIAERESIS"),
    ("aring", "a", "ring", "U+00E5 LATIN SMALL LETTER A WITH RING ABOVE"),
    ("igrave", "dotlessi", "gravecomb", "U+00EC LATIN SMALL LETTER I WITH GRAVE"),
    ("iacute", "dotlessi", "acute", "U+00ED LATIN SMALL LETTER I WITH ACUTE"),
    ("icircumflex", "dotlessi", "circumflex", "U+00EE LATIN SMALL LETTER I WITH CIRCUMFLEX"),
    ("idieresis", "dotlessi", "dieresis", "U+00EF LATIN SMALL LETTER I WITH DIAERESIS"),
)


AUXILIARY_LAYER_NAMES = {"img", "mask"}
BELOW_ACCENTS = {"cedilla", "ogonek"}
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
ELEMENT_ID_RE = re.compile(r"^elementdata(?:\.(\d+))?$")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a *_references.vfj with accented glyphs rebuilt from references."
    )
    parser.add_argument("font_file", type=Path, help="Path to a .vfj font file")
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


def write_data(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as font_file:
        json.dump(data, font_file, indent=2, separators=(",", ":"))
        font_file.write("\n")


def output_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}_references{path.suffix}")


def master_layer_names(font: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for master in font.get("masters", []):
        if not isinstance(master, dict):
            continue
        font_master = master.get("fontMaster")
        if isinstance(font_master, dict) and isinstance(font_master.get("name"), str):
            names.append(font_master["name"])
    if not names:
        raise SystemExit("font has no master layer names")
    return names


def glyphs_by_name(font: dict[str, Any]) -> dict[str, dict[str, Any]]:
    glyphs = font.get("glyphs", [])
    if not isinstance(glyphs, list):
        raise SystemExit("font.glyphs is not a list")
    return {glyph["name"]: glyph for glyph in glyphs if isinstance(glyph, dict) and isinstance(glyph.get("name"), str)}


def ensure_component_glyph_order(font: dict[str, Any]) -> None:
    glyphs = font.get("glyphs", [])
    if not isinstance(glyphs, list):
        return

    def index_by_name() -> dict[str, int]:
        return {
            glyph["name"]: index
            for index, glyph in enumerate(glyphs)
            if isinstance(glyph, dict) and isinstance(glyph.get("name"), str)
        }

    changed = True
    while changed:
        changed = False
        indices = index_by_name()
        for glyph_name, base_name, accent_name, _comment in ACCENTED_GLYPHS:
            target_index = indices.get(glyph_name)
            if target_index is None:
                continue

            for component_name in (base_name, accent_name):
                component_index = indices.get(component_name)
                if component_index is None or component_index < target_index:
                    continue

                component = glyphs.pop(component_index)
                glyphs.insert(target_index, component)
                changed = True
                break

            if changed:
                break


def layer_by_name(glyph: dict[str, Any], layer_name: str) -> Optional[dict[str, Any]]:
    layers = glyph.get("layers", [])
    if not isinstance(layers, list):
        return None
    for layer in layers:
        if isinstance(layer, dict) and layer.get("name") == layer_name:
            return layer
    return None


def layer_elements(layer: dict[str, Any]) -> list[dict[str, Any]]:
    elements = layer.get("elements", [])
    if not isinstance(elements, list):
        return []
    return [element for element in elements if isinstance(element, dict)]


def element_contours(element: dict[str, Any]) -> list[dict[str, Any]]:
    element_data = element.get("elementData")
    if not isinstance(element_data, dict):
        return []
    contours = element_data.get("contours", [])
    if not isinstance(contours, list):
        return []
    return [contour for contour in contours if isinstance(contour, dict)]


def parse_number(token: str) -> Optional[float]:
    return float(token) if NUMBER_RE.match(token) else None


def node_anchor_points(node: str) -> Iterable[Point]:
    tokens = node.split()
    numbers = [value for token in tokens if (value := parse_number(token)) is not None]
    pairs = [
        Point(numbers[index], numbers[index + 1])
        for index in range(0, len(numbers) - 1, 2)
    ]
    if not pairs:
        return []

    if "o" in tokens and len(pairs) == 1:
        return []

    return [pairs[-1]]


def node_points(node: str) -> Iterable[Point]:
    numbers = [value for token in node.split() if (value := parse_number(token)) is not None]
    for index in range(0, len(numbers) - 1, 2):
        yield Point(numbers[index], numbers[index + 1])


def contour_points(contour: dict[str, Any]) -> list[Point]:
    points: list[Point] = []
    nodes = contour.get("nodes", [])
    if not isinstance(nodes, list):
        return points
    for node in nodes:
        if isinstance(node, str):
            points.extend(node_anchor_points(node))
    return points


def transform_point(point: Point, transform: Optional[dict[str, Any]]) -> Point:
    if not isinstance(transform, dict):
        return point
    x_scale = transform.get("xScale", 1)
    y_scale = transform.get("yScale", 1)
    yx_scale = transform.get("yxScale", 0)
    x_offset = transform.get("xOffset", 0)
    y_offset = transform.get("yOffset", 0)
    if not isinstance(x_scale, (int, float)):
        x_scale = 1
    if not isinstance(y_scale, (int, float)):
        y_scale = 1
    if not isinstance(yx_scale, (int, float)):
        yx_scale = 0
    if not isinstance(x_offset, (int, float)):
        x_offset = 0
    if not isinstance(y_offset, (int, float)):
        y_offset = 0
    if abs(x_scale) > 10:
        x_scale /= 100
    if abs(y_scale) > 10:
        y_scale /= 100
    return Point(point.x * x_scale + x_offset, point.x * yx_scale + point.y * y_scale + y_offset)


def point_key(point: Point, mode: str) -> tuple[float, float]:
    if mode == "top":
        return (point.y, -point.x)
    if mode == "bottom":
        return (-point.y, -point.x)
    raise ValueError(mode)


def extreme_point(points: Iterable[Point], mode: str) -> Point:
    point_list = list(points)
    if not point_list:
        raise ValueError("no points")
    return max(point_list, key=lambda point: point_key(point, mode))


def collect_element_ids(font: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for glyph in glyphs_by_name(font).values():
        for layer in glyph.get("layers", []):
            if not isinstance(layer, dict):
                continue
            for element in layer_elements(layer):
                element_data = element.get("elementData")
                if isinstance(element_data, dict) and isinstance(element_data.get("id"), str):
                    ids.add(element_data["id"])
    return ids


def next_id_factory(font: dict[str, Any]):
    ids = collect_element_ids(font)
    max_number = -1
    for element_id in ids:
        match = ELEMENT_ID_RE.match(element_id)
        if match:
            max_number = max(max_number, int(match.group(1) or 0))

    def next_id() -> str:
        nonlocal max_number
        max_number += 1
        while True:
            element_id = "elementdata" if max_number == 0 else f"elementdata.{max_number}"
            if element_id not in ids:
                ids.add(element_id)
                return element_id
            max_number += 1

    return next_id


def ensure_element_id(element: dict[str, Any], next_id) -> str:
    element_data = element.get("elementData")
    if not isinstance(element_data, dict):
        raise ValueError("element is not outline data")
    if not isinstance(element_data.get("id"), str):
        element_data["id"] = next_id()
    return element_data["id"]


def prepare_referenceable_elements(
    font: dict[str, Any],
    glyph_by_name: dict[str, dict[str, Any]],
    layer_names: list[str],
) -> None:
    next_id = next_id_factory(font)
    needed = {base for _, base, _, _ in ACCENTED_GLYPHS} | {accent for _, _, accent, _ in ACCENTED_GLYPHS}
    for glyph_name in needed:
        glyph = glyph_by_name.get(glyph_name)
        if not glyph:
            continue
        for layer_name in layer_names:
            layer = layer_by_name(glyph, layer_name)
            if not layer:
                continue
            for element in layer_elements(layer):
                if isinstance(element.get("elementData"), dict):
                    ensure_element_id(element, next_id)


def referenced_points(
    element: dict[str, Any],
    elements_by_id: dict[str, dict[str, Any]],
    seen: Optional[set[str]] = None,
) -> list[Point]:
    seen = set() if seen is None else seen
    element_data = element.get("elementData")
    points: list[Point] = []
    if isinstance(element_data, str):
        if element_data in seen:
            return points
        target = elements_by_id.get(element_data)
        if not target:
            return points
        seen.add(element_data)
        points = referenced_points(target, elements_by_id, seen)
    elif isinstance(element_data, dict):
        for contour in element_contours(element):
            points.extend(contour_points(contour))
    return [transform_point(point, element.get("transform")) for point in points]


def build_elements_by_id(font: dict[str, Any]) -> dict[str, dict[str, Any]]:
    elements_by_id: dict[str, dict[str, Any]] = {}
    for glyph in glyphs_by_name(font).values():
        for layer in glyph.get("layers", []):
            if not isinstance(layer, dict):
                continue
            for element in layer_elements(layer):
                element_data = element.get("elementData")
                if isinstance(element_data, dict) and isinstance(element_data.get("id"), str):
                    elements_by_id[element_data["id"]] = element
    return elements_by_id


def layer_points(layer: dict[str, Any], elements_by_id: dict[str, dict[str, Any]]) -> list[Point]:
    points: list[Point] = []
    for element in layer_elements(layer):
        points.extend(referenced_points(element, elements_by_id))
    return points


def component_elements_for_layer(
    layer: dict[str, Any],
    base_name: str,
    next_id,
) -> list[dict[str, Any]]:
    component_elements: list[dict[str, Any]] = []
    for element in layer_elements(layer):
        element_data = element.get("elementData")
        if isinstance(element_data, dict):
            component_elements.append(element)
    if not component_elements:
        raise ValueError(f"{base_name}/{layer.get('name')}: no referenceable elements")
    for element in component_elements:
        ensure_element_id(element, next_id)
    return component_elements


def component_reference(element_id: str, dx: float, dy: float) -> dict[str, Any]:
    transform: dict[str, Any] = {}
    if dx:
        transform["xOffset"] = round(dx)
    if dy:
        transform["yOffset"] = round(dy)
    reference: dict[str, Any] = {"elementData": element_id}
    if transform:
        reference["transform"] = transform
    return reference


def regenerate_font(font: dict[str, Any]) -> list[str]:
    layer_names = master_layer_names(font)
    glyph_by_name = glyphs_by_name(font)
    prepare_referenceable_elements(font, glyph_by_name, layer_names)
    next_id = next_id_factory(font)
    elements_by_id = build_elements_by_id(font)
    messages: list[str] = []

    for glyph_name, base_name, accent_name, _comment in ACCENTED_GLYPHS:
        glyph = glyph_by_name.get(glyph_name)
        base_glyph = glyph_by_name.get(base_name)
        accent_glyph = glyph_by_name.get(accent_name)
        if not glyph or not base_glyph or not accent_glyph:
            messages.append(f"skip {glyph_name}: missing glyph/base/accent")
            continue

        for layer_name in layer_names:
            layer = layer_by_name(glyph, layer_name)
            base_layer = layer_by_name(base_glyph, layer_name)
            accent_layer = layer_by_name(accent_glyph, layer_name)
            if not layer or not base_layer or not accent_layer:
                messages.append(f"skip {glyph_name}/{layer_name}: missing layer")
                continue

            original_points = layer_points(layer, elements_by_id)
            if not original_points:
                messages.append(f"skip {glyph_name}/{layer_name}: no original points")
                continue

            accent_mode = "bottom" if accent_name in BELOW_ACCENTS else "top"
            base_mode = "top" if accent_name in BELOW_ACCENTS else "bottom"
            original_base_point = extreme_point(original_points, base_mode)
            original_accent_point = extreme_point(original_points, accent_mode)

            base_elements = component_elements_for_layer(base_layer, base_name, next_id)
            accent_elements = component_elements_for_layer(accent_layer, accent_name, next_id)
            elements_by_id = build_elements_by_id(font)

            base_points: list[Point] = []
            for element in base_elements:
                base_points.extend(referenced_points(element, elements_by_id))
            accent_points: list[Point] = []
            for element in accent_elements:
                accent_points.extend(referenced_points(element, elements_by_id))

            base_point = extreme_point(base_points, base_mode)
            accent_point = extreme_point(accent_points, accent_mode)
            base_dx = original_base_point.x - base_point.x
            base_dy = original_base_point.y - base_point.y
            accent_dx = original_accent_point.x - accent_point.x
            accent_dy = original_accent_point.y - accent_point.y

            new_elements: list[dict[str, Any]] = []
            for element in base_elements:
                element_id = ensure_element_id(element, next_id)
                new_elements.append(component_reference(element_id, base_dx, base_dy))
            for element in accent_elements:
                element_id = ensure_element_id(element, next_id)
                new_elements.append(component_reference(element_id, accent_dx, accent_dy))
            layer["elements"] = new_elements

    return messages


def main() -> int:
    args = parse_args()
    data = load_data(args.font_file)
    messages = regenerate_font(data["font"])
    ensure_component_glyph_order(data["font"])
    out_path = output_path(args.font_file)
    write_data(out_path, data)

    for message in messages:
        print(f"warning: {message}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
