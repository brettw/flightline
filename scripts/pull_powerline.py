#!/usr/bin/env python3
"""Copy Powerline glyphs into the Flightline VFJ sources."""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
POWERLINE_PATH = REPO_ROOT / "sources" / "vfj" / "NerdfontsPL-Regular.vfj"
FLIGHTLINE_DIR = REPO_ROOT / "sources" / "vfj"
POWERLINE_ROW_BOTTOM = -500
POWERLINE_ROW_TOP = 2067
POWERLINE_VERTICAL_EXCLUDE_CODEPOINTS = {0xE0A1, 0xE0A2, 0xE0A3}


@dataclass(frozen=True)
class GlyphCopySpec:
    source_name: str
    dest_name: str
    codepoint: str | None


@dataclass(frozen=True)
class VerticalBounds:
    bottom: float
    top: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy all Powerline glyphs from sources/vfj/NerdfontsPL-Regular.vfj "
            "into both Flightline VFJ source files. If a source glyph has a "
            ".stypo variant, that outline is copied under the base glyph name."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be copied without writing the Flightline VFJ files.",
    )
    return parser.parse_args()


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_data(path: Path) -> dict[str, Any]:
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

    return data


def write_data(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as font_file:
        json.dump(data, font_file, indent=2, separators=(",", ":"))
        font_file.write("\n")


def font_glyphs(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [glyph for glyph in data["font"]["glyphs"] if isinstance(glyph, dict)]


def glyph_name(glyph: dict[str, Any]) -> str | None:
    name = glyph.get("name")
    return name if isinstance(name, str) and name else None


def glyph_unicode(glyph: dict[str, Any]) -> str | None:
    value = glyph.get("unicode")
    return value.lower() if isinstance(value, str) and value else None


def glyph_codepoint_value(spec: GlyphCopySpec) -> int | None:
    if spec.codepoint is None:
        return None

    try:
        return int(spec.codepoint, 16)
    except ValueError:
        return None


def glyphs_by_name(glyphs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: glyph
        for glyph in glyphs
        if (name := glyph_name(glyph)) is not None
    }


def powerline_copy_specs(glyphs: list[dict[str, Any]]) -> list[GlyphCopySpec]:
    by_name = glyphs_by_name(glyphs)
    specs: list[GlyphCopySpec] = []
    seen_dest_names: set[str] = set()

    for glyph in glyphs:
        name = glyph_name(glyph)
        if name is None or name.endswith(".stypo"):
            continue

        stypo_name = f"{name}.stypo"
        source_name = stypo_name if stypo_name in by_name else name
        codepoint = glyph_unicode(glyph)

        if name in seen_dest_names:
            raise SystemExit(
                f"{relative_path(POWERLINE_PATH)}: duplicate destination glyph {name!r}"
            )
        seen_dest_names.add(name)
        specs.append(GlyphCopySpec(source_name, name, codepoint))

    if not specs:
        raise SystemExit(f"{relative_path(POWERLINE_PATH)}: no glyphs to copy")

    return specs


def flightline_paths() -> list[Path]:
    paths = [
        FLIGHTLINE_DIR / "FlightlineCode-Regular.vfj",
        FLIGHTLINE_DIR / "FlightlineCode-Italic.vfj",
    ]
    missing = [path for path in paths if not path.exists()]
    if missing:
        examples = ", ".join(relative_path(path) for path in missing)
        raise SystemExit(f"missing Flightline VFJ source file(s): {examples}")
    return paths


def master_names(font: dict[str, Any]) -> list[str]:
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


def target_layer_names(font: dict[str, Any]) -> list[str]:
    masters = master_names(font)
    master_set = set(masters)

    for glyph in font.get("glyphs", []):
        if not isinstance(glyph, dict):
            continue
        layers = glyph.get("layers")
        if not isinstance(layers, list):
            continue

        names = [
            layer["name"]
            for layer in layers
            if isinstance(layer, dict)
            and isinstance(layer.get("name"), str)
            and layer["name"] in master_set
        ]
        if set(names) == master_set:
            return names

    return masters


def source_layer(source_glyph: dict[str, Any], source_name: str) -> dict[str, Any]:
    layers = source_glyph.get("layers")
    if not isinstance(layers, list):
        raise SystemExit(f"{source_name}: source glyph has no layers list")

    layer_dicts = [layer for layer in layers if isinstance(layer, dict)]
    for layer in layer_dicts:
        if layer.get("name") == "Regular":
            return layer
    if layer_dicts:
        return layer_dicts[0]

    raise SystemExit(f"{source_name}: source glyph has no usable layers")


def rewrite_component_references(value: Any, source_to_dest: dict[str, str]) -> None:
    if isinstance(value, list):
        for item in value:
            rewrite_component_references(item, source_to_dest)
        return

    if not isinstance(value, dict):
        return

    component = value.get("component")
    if isinstance(component, dict):
        glyph_name_value = component.get("glyphName")
        if isinstance(glyph_name_value, str):
            component["glyphName"] = source_to_dest.get(
                glyph_name_value, glyph_name_value.removesuffix(".stypo")
            )

    for item in value.values():
        rewrite_component_references(item, source_to_dest)


def numeric_tokens(node: str) -> list[float]:
    values: list[float] = []
    for token in node.split():
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def layer_vertical_bounds(layer: dict[str, Any]) -> VerticalBounds | None:
    y_values: list[float] = []

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
            return

        if not isinstance(value, dict):
            return

        nodes = value.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, str):
                    values = numeric_tokens(node)
                    y_values.extend(values[1::2])

        for item in value.values():
            collect(item)

    collect(layer.get("elements", []))

    if not y_values:
        return None

    return VerticalBounds(min(y_values), max(y_values))


def transformed_y(value: float, source_bounds: VerticalBounds) -> int:
    source_height = source_bounds.top - source_bounds.bottom
    target_height = POWERLINE_ROW_TOP - POWERLINE_ROW_BOTTOM
    return round(
        POWERLINE_ROW_BOTTOM
        + (value - source_bounds.bottom) * target_height / source_height
    )


def transform_node_string(
    node: str, source_bounds: VerticalBounds
) -> tuple[str, bool]:
    transformed_tokens: list[str] = []
    numeric_index = 0
    modified = False

    for token in node.split():
        try:
            value = float(token)
        except ValueError:
            transformed_tokens.append(token)
            continue

        if numeric_index % 2 == 1:
            transformed_value = transformed_y(value, source_bounds)
            transformed_tokens.append(str(transformed_value))
            modified = modified or transformed_value != value
        else:
            transformed_tokens.append(token)
        numeric_index += 1

    return " ".join(transformed_tokens), modified


def transform_layer_nodes(value: Any, source_bounds: VerticalBounds) -> bool:
    modified = False

    if isinstance(value, list):
        for item in value:
            modified = transform_layer_nodes(item, source_bounds) or modified
        return modified

    if not isinstance(value, dict):
        return False

    nodes = value.get("nodes")
    if isinstance(nodes, list):
        transformed_nodes: list[Any] = []
        for node in nodes:
            if isinstance(node, str):
                transformed_node, node_modified = transform_node_string(
                    node, source_bounds
                )
                transformed_nodes.append(transformed_node)
                modified = node_modified or modified
            else:
                transformed_nodes.append(node)
        value["nodes"] = transformed_nodes

    for key, item in value.items():
        if key == "nodes":
            continue
        modified = transform_layer_nodes(item, source_bounds) or modified

    return modified


def normalize_powerline_vertical_bounds(
    glyph: dict[str, Any], spec: GlyphCopySpec
) -> bool:
    codepoint = glyph_codepoint_value(spec)
    if codepoint is None or codepoint in POWERLINE_VERTICAL_EXCLUDE_CODEPOINTS:
        return False

    layers = glyph.get("layers")
    if not isinstance(layers, list):
        return False

    modified = False
    for layer in layers:
        if not isinstance(layer, dict):
            continue

        bounds = layer_vertical_bounds(layer)
        if bounds is None:
            continue
        if bounds.bottom == bounds.top:
            continue
        if bounds.bottom == POWERLINE_ROW_BOTTOM and bounds.top == POWERLINE_ROW_TOP:
            continue

        modified = transform_layer_nodes(layer.get("elements", []), bounds) or modified

    return modified


def cloned_glyph(
    source_glyph: dict[str, Any],
    spec: GlyphCopySpec,
    layer_names: list[str],
    active_layer_name: str | None,
    source_to_dest: dict[str, str],
) -> dict[str, Any]:
    template_layer = source_layer(source_glyph, spec.source_name)
    glyph: dict[str, Any] = {"name": spec.dest_name}
    if spec.codepoint is not None:
        glyph["unicode"] = spec.codepoint

    for key, value in source_glyph.items():
        if key in {"name", "unicode", "layers"}:
            continue
        glyph[key] = copy.deepcopy(value)

    layers: list[dict[str, Any]] = []
    for layer_name in layer_names:
        layer = copy.deepcopy(template_layer)
        layer["name"] = layer_name
        if active_layer_name == layer_name:
            layer["active"] = True
        else:
            layer.pop("active", None)
        rewrite_component_references(layer, source_to_dest)
        layers.append(layer)

    glyph["layers"] = layers
    return glyph


def replace_or_append_glyph(glyphs: list[Any], glyph: dict[str, Any]) -> str:
    glyph_name_value = glyph.get("name")
    glyph_unicode_value = glyph.get("unicode")

    matching_indexes = [
        index
        for index, existing in enumerate(glyphs)
        if isinstance(existing, dict)
        and (
            existing.get("name") == glyph_name_value
            or (
                glyph_unicode_value is not None
                and isinstance(existing.get("unicode"), str)
                and existing["unicode"].lower() == glyph_unicode_value
            )
        )
    ]

    if not matching_indexes:
        glyphs.append(glyph)
        return "added"

    glyphs[matching_indexes[0]] = glyph
    for index in reversed(matching_indexes[1:]):
        del glyphs[index]
    return "replaced"


def copy_to_flightline_file(
    path: Path,
    specs: list[GlyphCopySpec],
    source_glyphs: dict[str, dict[str, Any]],
    source_to_dest: dict[str, str],
    dry_run: bool,
) -> tuple[int, int, int]:
    data = load_data(path)
    font = data["font"]
    glyphs = font["glyphs"]

    layer_names = target_layer_names(font)
    active_layer_name = font.get("currentMaster")
    if not isinstance(active_layer_name, str):
        active_layer_name = None

    added = 0
    replaced = 0
    transformed = 0
    for spec in specs:
        source_glyph = source_glyphs[spec.source_name]
        glyph = cloned_glyph(
            source_glyph, spec, layer_names, active_layer_name, source_to_dest
        )
        if normalize_powerline_vertical_bounds(glyph, spec):
            transformed += 1
        result = replace_or_append_glyph(glyphs, glyph)
        if result == "added":
            added += 1
        else:
            replaced += 1

    font["glyphsCount"] = len(glyphs)
    if not dry_run:
        write_data(path, data)

    return added, replaced, transformed


def main() -> int:
    args = parse_args()
    powerline_data = load_data(POWERLINE_PATH)
    powerline_glyphs = font_glyphs(powerline_data)
    source_glyphs = glyphs_by_name(powerline_glyphs)
    specs = powerline_copy_specs(powerline_glyphs)

    missing = [spec.source_name for spec in specs if spec.source_name not in source_glyphs]
    if missing:
        examples = ", ".join(missing[:10])
        suffix = f", and {len(missing) - 10} more" if len(missing) > 10 else ""
        raise SystemExit(
            f"{relative_path(POWERLINE_PATH)}: missing source glyphs: {examples}{suffix}"
        )

    source_to_dest = {spec.source_name: spec.dest_name for spec in specs}
    mode = "would add" if args.dry_run else "added"
    replace_mode = "would replace" if args.dry_run else "replaced"
    transform_mode = "would transform" if args.dry_run else "transformed"

    for path in flightline_paths():
        added, replaced, transformed = copy_to_flightline_file(
            path, specs, source_glyphs, source_to_dest, args.dry_run
        )
        print(
            f"{relative_path(path)}: {mode} {added}, {replace_mode} {replaced}, "
            f"{transform_mode} {transformed}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
