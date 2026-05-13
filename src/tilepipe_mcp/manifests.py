"""Unity wall-kit manifest helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UNITY_IMPORT_RECOMMENDATIONS = {
    "pixels_per_unit": 64,
    "texture_type": "Sprite",
    "sprite_mode": "Multiple for sheets, Single for split subtiles",
    "filter_mode": "Point",
    "compression": "Uncompressed",
    "mipmaps": False,
    "alpha_is_transparency": True,
}


def build_unity_manifest(
    *,
    job_name: str,
    source_tile: dict[str, Any],
    render_result: dict[str, Any],
    output_dir: Path,
    unity_project_root: Path | None,
) -> dict[str, Any]:
    metadata = render_result.get("metadata", {})
    generated_masks = metadata.get("generated_masks", [])
    missing_masks = metadata.get("missing_rule_masks", [])
    outputs = render_result.get("outputs", {})
    return {
        "schema": "tilepipe2.unity_wallkit_manifest.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "job_name": job_name,
        "unity_project_root": str(unity_project_root) if unity_project_root else None,
        "source": source_tile,
        "outputs": outputs,
        "output_dir": str(output_dir),
        "tile_size": metadata.get("output_tile_size"),
        "template_size": metadata.get("template_size"),
        "rendered_size": metadata.get("rendered_size"),
        "generated_masks": generated_masks,
        "missing_masks": missing_masks,
        "mask_count": len(generated_masks),
        "unity_import_recommendations": UNITY_IMPORT_RECOMMENDATIONS,
        "warnings": render_result.get("warnings", []),
        "errors": render_result.get("errors", []),
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def validate_unity_wallkit_output(manifest: dict[str, Any]) -> dict[str, Any]:
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

    if manifest.get("missing_masks"):
        warnings.append("One or more generated template masks have no direct ruleset match.")

    tile_size = manifest.get("tile_size") or {}
    if tile_size and (tile_size.get("x") != 64 or tile_size.get("y") != 64):
        warnings.append("Output tile size is not 64x64; confirm this is intentional for Unity.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "mask_count": manifest.get("mask_count", 0),
        "output_count": len(subtiles) + (1 if texture else 0),
    }

