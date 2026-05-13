"""Unity candidate manifest helpers."""

from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
