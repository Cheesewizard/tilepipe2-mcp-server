from pathlib import Path

from tilepipe_mcp.manifests import (
    build_unity_manifest,
    validate_unity_wallkit_output,
    write_manifest,
)


def test_manifest_round_trip(tmp_path: Path):
    texture = tmp_path / "wallkit.png"
    texture.write_bytes(b"png")
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

