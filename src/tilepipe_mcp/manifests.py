"""Unity candidate manifest helpers."""

from __future__ import annotations

import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


WALL_REQUIRED_MASKS = [
    0,
    1,
    4,
    5,
    7,
    16,
    17,
    20,
    21,
    23,
    28,
    29,
    31,
    64,
    65,
    68,
    69,
    71,
    80,
    81,
    84,
    85,
    87,
    92,
    93,
    95,
    112,
    113,
    116,
    117,
    119,
    124,
    125,
    127,
    193,
    197,
    199,
    209,
    213,
    215,
    221,
    223,
    241,
    245,
    247,
    253,
    255,
]

UNITY_IMPORT_RECOMMENDATIONS = {
    "pixels_per_unit": 64,
    "texture_type": "Sprite",
    "sprite_mode": "Multiple for sheets, Single for split subtiles",
    "filter_mode": "Point",
    "compression": "Uncompressed",
    "mipmaps": False,
    "alpha_is_transparency": True,
}

MASK_NORTH = 1
MASK_EAST = 4
MASK_SOUTH = 16
MASK_WEST = 64

SUBTILE_MASK_PATTERN = re.compile(r"_mask_(\d+)_")


def read_png_size(path: str | Path) -> dict[str, int]:
    png_path = Path(path)
    with png_path.open("rb") as file:
        header = file.read(24)
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Not a PNG file: {png_path}")
    width, height = struct.unpack(">II", header[16:24])
    return {"x": width, "y": height}


def build_candidate_manifest(
    *,
    job_name: str,
    candidate_type: str,
    source_tile: dict[str, Any],
    render_result: dict[str, Any],
    output_dir: Path,
    unity_project_root: Path | None,
    source_art: str | None = None,
    expected_masks: list[int] | None = None,
) -> dict[str, Any]:
    metadata = render_result.get("metadata", {})
    generated_masks = metadata.get("generated_masks", [])
    missing_masks = metadata.get("missing_rule_masks", [])
    outputs = render_result.get("outputs", {})
    return {
        "schema": "tilepipe2.unity_candidate_manifest.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "job_name": job_name,
        "candidate_type": candidate_type,
        "unity_project_root": str(unity_project_root) if unity_project_root else None,
        "source": {**source_tile, "source_art": source_art},
        "outputs": outputs,
        "output_dir": str(output_dir),
        "tile_size": metadata.get("output_tile_size"),
        "input_tile_size": metadata.get("input_tile_size"),
        "template_size": metadata.get("template_size"),
        "rendered_size": metadata.get("rendered_size"),
        "generated_masks": generated_masks,
        "expected_masks": expected_masks or [],
        "missing_masks": missing_masks,
        "mask_count": len(generated_masks),
        "unity_import_recommendations": UNITY_IMPORT_RECOMMENDATIONS,
        "warnings": render_result.get("warnings", []),
        "errors": render_result.get("errors", []),
    }


def build_unity_manifest(
    *,
    job_name: str,
    source_tile: dict[str, Any],
    render_result: dict[str, Any],
    output_dir: Path,
    unity_project_root: Path | None,
) -> dict[str, Any]:
    manifest = build_candidate_manifest(
        job_name=job_name,
        candidate_type="wallkit",
        source_tile=source_tile,
        render_result=render_result,
        output_dir=output_dir,
        unity_project_root=unity_project_root,
    )
    manifest["schema"] = "tilepipe2.unity_wallkit_manifest.v1"
    return manifest


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def validate_candidate_output(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    outputs = manifest.get("outputs", {})

    texture = outputs.get("texture")
    if texture and not Path(texture).is_file():
        errors.append(f"Texture output does not exist: {texture}")

    subtiles = outputs.get("subtiles", [])
    for subtile in subtiles:
        if not Path(subtile).is_file():
            errors.append(f"Subtile output does not exist: {subtile}")

    for output_key in ["texture"]:
        output_path = outputs.get(output_key)
        if output_path and Path(output_path).is_file():
            try:
                actual_size = read_png_size(output_path)
            except ValueError as error:
                errors.append(str(error))
                continue
            expected_size = manifest.get("rendered_size")
            if expected_size and actual_size != expected_size:
                errors.append(
                    f"{output_key} dimensions {actual_size} do not match manifest {expected_size}."
                )

    if manifest.get("missing_masks"):
        warnings.append("One or more generated template masks have no direct ruleset match.")

    expected_masks = set(manifest.get("expected_masks") or [])
    generated_masks = set(manifest.get("generated_masks") or [])
    missing_expected_masks = sorted(expected_masks - generated_masks)
    if missing_expected_masks:
        errors.append(f"Expected masks were not generated: {missing_expected_masks}")

    import_recommendations = manifest.get("unity_import_recommendations") or {}
    if import_recommendations and import_recommendations.get("pixels_per_unit") != 64:
        errors.append("Unity import recommendation must specify 64 pixels per unit.")

    tile_size = manifest.get("tile_size") or {}
    candidate_type = manifest.get("candidate_type", "wallkit")
    if candidate_type == "wallkit":
        valid_wall_size = tile_size in [{"x": 64, "y": 64}, {"x": 64, "y": 96}]
        if tile_size and not valid_wall_size:
            warnings.append("Wall output tile size is not 64x64 or 64x96.")
    elif tile_size and (tile_size.get("x") != 64 or tile_size.get("y") != 64):
        warnings.append("Floor output tile size is not 64x64.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "mask_count": manifest.get("mask_count", 0),
        "output_count": len(subtiles) + (1 if texture else 0),
    }


def validate_unity_wallkit_output(manifest: dict[str, Any]) -> dict[str, Any]:
    return validate_candidate_output(manifest)


def validate_wallkit_edge_seams(
    subtile_paths: list[str | Path],
    *,
    max_average_delta: float = 0.0,
    max_pixel_delta: int = 0,
) -> dict[str, Any]:
    tiles = _load_first_variant_by_mask(subtile_paths)
    errors: list[str] = []
    warnings: list[str] = []
    comparisons = 0

    for mask, image in tiles.items():
        if mask & MASK_EAST:
            comparisons += 1
            _compare_edges(
                errors,
                mask,
                "east",
                image,
                _matching_tile(tiles, MASK_WEST),
                "west",
                max_average_delta,
                max_pixel_delta,
            )
        if mask & MASK_WEST:
            comparisons += 1
            _compare_edges(
                errors,
                mask,
                "west",
                image,
                _matching_tile(tiles, MASK_EAST),
                "east",
                max_average_delta,
                max_pixel_delta,
            )
        if mask & MASK_NORTH:
            comparisons += 1
            _compare_edges(
                errors,
                mask,
                "north",
                image,
                _matching_tile(tiles, MASK_SOUTH),
                "south",
                max_average_delta,
                max_pixel_delta,
            )
        if mask & MASK_SOUTH:
            comparisons += 1
            _compare_edges(
                errors,
                mask,
                "south",
                image,
                _matching_tile(tiles, MASK_NORTH),
                "north",
                max_average_delta,
                max_pixel_delta,
            )

    if not tiles:
        errors.append("No subtile PNGs were available for seam validation.")
    if comparisons == 0 and tiles:
        warnings.append("No connected mask edges were available for seam validation.")

    for image in tiles.values():
        image.close()

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "tile_count": len(tiles),
        "comparison_count": comparisons,
        "max_average_delta": max_average_delta,
        "max_pixel_delta": max_pixel_delta,
    }


def validate_wallkit_manifest_edge_seams(
    manifest: dict[str, Any],
    *,
    max_average_delta: float = 0.0,
    max_pixel_delta: int = 0,
) -> dict[str, Any]:
    outputs = manifest.get("outputs") or {}
    subtiles = outputs.get("subtiles") or []
    return validate_wallkit_edge_seams(
        subtiles,
        max_average_delta=max_average_delta,
        max_pixel_delta=max_pixel_delta,
    )


def _load_first_variant_by_mask(subtile_paths: list[str | Path]) -> dict[int, Image.Image]:
    tiles: dict[int, Image.Image] = {}
    for path_value in subtile_paths:
        path = Path(path_value)
        match = SUBTILE_MASK_PATTERN.search(path.name)
        if match is None or int(match.group(1)) in tiles or not path.is_file():
            continue
        image = Image.open(path).convert("RGBA")
        tiles[int(match.group(1))] = image
    return tiles


def _matching_tile(tiles: dict[int, Image.Image], required_edge: int) -> tuple[int, Image.Image] | None:
    for mask, image in tiles.items():
        if mask & required_edge:
            return mask, image
    return None


def _compare_edges(
    errors: list[str],
    left_mask: int,
    left_edge: str,
    left_image: Image.Image,
    right: tuple[int, Image.Image] | None,
    right_edge: str,
    max_average_delta: float,
    max_pixel_delta: int,
) -> None:
    if right is None:
        errors.append(f"Mask {left_mask} has {left_edge} connection but no matching {right_edge} tile exists.")
        return

    right_mask, right_image = right
    left_pixels = _edge_pixels(left_image, left_edge)
    right_pixels = _edge_pixels(right_image, right_edge)
    if len(left_pixels) != len(right_pixels):
        errors.append(
            f"Mask {left_mask} {left_edge} edge length does not match mask {right_mask} {right_edge} edge."
        )
        return

    total_delta = 0
    worst_delta = 0
    channel_count = len(left_pixels) * 4
    for index, pixel in enumerate(left_pixels):
        other = right_pixels[index]
        for channel in range(4):
            delta = abs(pixel[channel] - other[channel])
            total_delta += delta
            worst_delta = max(worst_delta, delta)

    average_delta = total_delta / channel_count
    if average_delta > max_average_delta or worst_delta > max_pixel_delta:
        errors.append(
            "Mask "
            f"{left_mask} {left_edge} edge does not match mask {right_mask} {right_edge} edge "
            f"(average delta {average_delta:.2f}, max delta {worst_delta})."
        )


def _edge_pixels(image: Image.Image, edge: str) -> list[tuple[int, int, int, int]]:
    width, height = image.size
    if edge == "north":
        return [image.getpixel((x, 0)) for x in range(width)]
    if edge == "south":
        return [image.getpixel((x, height - 1)) for x in range(width)]
    if edge == "west":
        return [image.getpixel((0, y)) for y in range(height)]
    if edge == "east":
        return [image.getpixel((width - 1, y)) for y in range(height)]
    raise ValueError(f"Unknown edge: {edge}")
