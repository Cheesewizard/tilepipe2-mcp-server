from pathlib import Path

from tilepipe_mcp.manifests import (
    WALL_REQUIRED_MASKS,
    build_unity_manifest,
    validate_candidate_output,
    validate_unity_wallkit_output,
    write_manifest,
)


def write_png_header(path: Path, width: int, height: int):
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def test_manifest_round_trip(tmp_path: Path):
    texture = tmp_path / "wallkit.png"
    write_png_header(texture, 192, 64)
    render_result = {
        "outputs": {"texture": str(texture)},
        "metadata": {
            "generated_masks": [0, 1, 4],
            "missing_rule_masks": [],
            "output_tile_size": {"x": 64, "y": 64},
            "template_size": {"x": 3, "y": 1},
            "rendered_size": {"x": 192, "y": 64},
        },
        "warnings": [],
        "errors": [],
    }

    manifest = build_unity_manifest(
        job_name="walls",
        source_tile={"project_dir": "project", "tile_file": "walls.tptile"},
        render_result=render_result,
        output_dir=tmp_path,
        unity_project_root=None,
    )
    path = write_manifest(tmp_path / "manifest.json", manifest)

    assert path.is_file()
    assert manifest["schema"] == "tilepipe2.unity_wallkit_manifest.v1"
    assert validate_unity_wallkit_output(manifest)["ok"] is True


def test_validate_manifest_reports_missing_output(tmp_path: Path):
    manifest = {
        "outputs": {"texture": str(tmp_path / "missing.png")},
        "missing_masks": [],
        "tile_size": {"x": 64, "y": 64},
    }

    result = validate_unity_wallkit_output(manifest)

    assert result["ok"] is False
    assert "Texture output does not exist" in result["errors"][0]


def test_validate_manifest_warns_nonstandard_tile_size():
    manifest = {
        "outputs": {},
        "missing_masks": [],
        "tile_size": {"x": 48, "y": 48},
    }

    result = validate_unity_wallkit_output(manifest)

    assert result["ok"] is True
    assert result["warnings"]


def test_validate_candidate_reports_missing_required_masks(tmp_path: Path):
    texture = tmp_path / "wallkit.png"
    write_png_header(texture, 64, 64)
    manifest = {
        "candidate_type": "wallkit",
        "outputs": {"texture": str(texture)},
        "missing_masks": [],
        "tile_size": {"x": 64, "y": 64},
        "rendered_size": {"x": 64, "y": 64},
        "generated_masks": [0],
        "expected_masks": WALL_REQUIRED_MASKS,
        "unity_import_recommendations": {"pixels_per_unit": 64},
    }

    result = validate_candidate_output(manifest)

    assert result["ok"] is False
    assert "Expected masks were not generated" in result["errors"][0]
