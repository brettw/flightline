#!/usr/bin/env python3
"""Audit Cascadia symbol glyphs that are not present in Flightline sources."""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
CASCADIA_PATH = REPO_ROOT / "sources" / "CascadiaCode-Regular.vfj"
FLIGHTLINE_DIR = REPO_ROOT / "sources" / "vfj"
COPY_LIST_PATH = Path(__file__).resolve().with_name("glyphs_from_cascadia.txt")


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


@dataclass(frozen=True)
class GlyphCopySpec:
    codepoint: int
    source_name: str
    dest_name: str


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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--audit",
        action="store_true",
        help="Print the Cascadia symbol glyph audit.",
    )
    mode.add_argument(
        "--copy",
        action="store_true",
        help=(
            "Copy glyphs listed in glyphs_from_cascadia.txt from Cascadia into "
            "both Flightline VFJ sources."
        ),
    )
    return parser.parse_args()


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_glyphs(path: Path) -> list[dict[str, Any]]:
    data = load_data(path)
    return font_glyphs(data, path)


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

    return data


def write_data(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as font_file:
        json.dump(data, font_file, indent=2, separators=(",", ":"))
        font_file.write("\n")


def font_glyphs(data: dict[str, Any], path: Path) -> list[dict[str, Any]]:
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


def parse_copy_specs(lines: Iterable[str], path: Path) -> list[GlyphCopySpec]:
    specs: list[GlyphCopySpec] = []
    dest_names: dict[str, int] = {}

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not parts[0].startswith("U+"):
            raise SystemExit(
                f"{relative_path(path)}:{line_number}: expected 'U+XXXX glyphName'"
            )

        try:
            codepoint = int(parts[0][2:], 16)
        except ValueError as error:
            raise SystemExit(
                f"{relative_path(path)}:{line_number}: invalid Unicode code point {parts[0]!r}"
            ) from error

        source_name = parts[1].strip()
        if not source_name:
            raise SystemExit(f"{relative_path(path)}:{line_number}: missing glyph name")

        dest_name = source_name.removesuffix(".stypo")
        if dest_name in dest_names:
            first_line = dest_names[dest_name]
            raise SystemExit(
                f"{relative_path(path)}:{line_number}: destination glyph {dest_name!r} "
                f"was already listed on line {first_line}"
            )
        dest_names[dest_name] = line_number
        specs.append(GlyphCopySpec(codepoint, source_name, dest_name))

    if not specs:
        raise SystemExit(f"{relative_path(path)}: no glyphs listed")

    return specs


def load_copy_specs(path: Path = COPY_LIST_PATH) -> list[GlyphCopySpec]:
    try:
        with path.open(encoding="utf-8") as glyph_file:
            return parse_copy_specs(glyph_file, path)
    except OSError as error:
        raise SystemExit(f"{relative_path(path)}: {error}") from error


def glyphs_by_name(glyphs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: glyph
        for glyph in glyphs
        if (name := glyph_name(glyph)) is not None
    }


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

    glyphs = font.get("glyphs", [])
    if isinstance(glyphs, list):
        for glyph in glyphs:
            if not isinstance(glyph, dict):
                continue
            layers = glyph.get("layers", [])
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
            if glyph_name_value in source_to_dest:
                component["glyphName"] = source_to_dest[glyph_name_value]
            else:
                component["glyphName"] = glyph_name_value.removesuffix(".stypo")

    for item in value.values():
        rewrite_component_references(item, source_to_dest)


def cloned_glyph(
    source_glyph: dict[str, Any],
    spec: GlyphCopySpec,
    layer_names: list[str],
    active_layer_name: str | None,
    source_to_dest: dict[str, str],
) -> dict[str, Any]:
    template_layer = source_layer(source_glyph, spec.source_name)
    glyph: dict[str, Any] = {
        "name": spec.dest_name,
        "unicode": f"{spec.codepoint:04x}",
    }

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
    glyph_name_value = glyph["name"]
    matching_indexes = [
        index
        for index, existing in enumerate(glyphs)
        if isinstance(existing, dict) and existing.get("name") == glyph_name_value
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
) -> tuple[int, int]:
    data = load_data(path)
    font = data["font"]
    glyphs = font.get("glyphs")
    if not isinstance(glyphs, list):
        raise SystemExit(f"{relative_path(path)}: expected font.glyphs list")

    layer_names = target_layer_names(font)
    active_layer_name = font.get("currentMaster")
    if not isinstance(active_layer_name, str):
        active_layer_name = None

    added = 0
    replaced = 0
    for spec in specs:
        source_glyph = source_glyphs[spec.source_name]
        glyph = cloned_glyph(
            source_glyph, spec, layer_names, active_layer_name, source_to_dest
        )
        result = replace_or_append_glyph(glyphs, glyph)
        if result == "added":
            added += 1
        else:
            replaced += 1

    font["glyphsCount"] = len(glyphs)
    write_data(path, data)
    return added, replaced


def copy_glyphs() -> int:
    specs = load_copy_specs()
    cascadia_glyphs = load_glyphs(CASCADIA_PATH)
    source_glyphs = glyphs_by_name(cascadia_glyphs)
    missing = [spec.source_name for spec in specs if spec.source_name not in source_glyphs]
    if missing:
        examples = ", ".join(missing[:10])
        suffix = f", and {len(missing) - 10} more" if len(missing) > 10 else ""
        raise SystemExit(
            f"{relative_path(CASCADIA_PATH)}: missing source glyphs: {examples}{suffix}"
        )

    source_to_dest = {spec.source_name: spec.dest_name for spec in specs}
    for path in flightline_paths():
        added, replaced = copy_to_flightline_file(
            path, specs, source_glyphs, source_to_dest
        )
        print(f"{relative_path(path)}: added {added}, replaced {replaced}")

    return 0


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
    args = parse_args()
    if args.audit:
        return audit()
    if args.copy:
        return copy_glyphs()
    raise SystemExit("choose --audit or --copy")


if __name__ == "__main__":
    raise SystemExit(main())
