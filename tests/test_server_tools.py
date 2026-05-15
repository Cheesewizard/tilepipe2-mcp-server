import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ValidationError

from tilepipe_mcp.config import TilePipeConfig
from tilepipe_mcp.server import (
    _init_config,
    _slice_rendered_subtiles,
    tilepipe_create_tile,
    tilepipe_prepare_unity_promotion,
)


def test_create_tile_sends_headless_create_command(monkeypatch, tmp_path: Path):
    godot = tmp_path / "godot.exe"
    godot.write_text("fake", encoding="utf-8")
    repo = tmp_path / "TilePipe2"
    (repo / "src" / "headless").mkdir(parents=True)
    (repo / "project.godot").write_text("", encoding="utf-8")
    (repo / "src" / "headless" / "TilePipeHeadless.gd").write_text("", encoding="utf-8")
    source = tmp_path / "source.png"
    ruleset = tmp_path / "ruleset.json"
    template = tmp_path / "template.png"
    source.write_bytes(b"png")
    ruleset.write_text("{}", encoding="utf-8")
    template.write_bytes(b"png")
    config = TilePipeConfig(
        godot_bin=godot,
        tilepipe2_repo=repo,
        workspace=tmp_path / "workspace",
        unity_project_root=None,
    )
    _init_config(config)
    calls = []

    def fake_run(command, payload):
        calls.append((command, payload))
        return {"ok": True, "outputs": {"tile_file": str(tmp_path / "tile.tptile")}}

    monkeypatch.setattr("tilepipe_mcp.server._run", fake_run)

    result = tilepipe_create_tile(
        str(config.workspace / "project"),
        "tile.tptile",
        str(source),
        str(ruleset),
        str(template),
    )

    assert result["ok"] is True
    assert calls[0][0] == "create_project_from_art"
    assert calls[0][1]["project_dir"] == str((config.workspace / "project").resolve())


def test_prepare_promotion_rejects_incomplete_candidate(tmp_path: Path):
    config = TilePipeConfig(
        tilepipe2_repo=tmp_path / "TilePipe2",
        workspace=tmp_path / "workspace",
        unity_project_root=tmp_path / "Zombie_Game",
    )
    _init_config(config)
    manifest_path = config.workspace / "candidate.json"
    manifest_path.write_text(
        json.dumps(
            {
                "outputs": {"texture": str(config.workspace / "missing.png")},
                "missing_masks": [],
                "tile_size": {"x": 64, "y": 64},
                "unity_import_recommendations": {"pixels_per_unit": 64},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        tilepipe_prepare_unity_promotion(
            str(manifest_path),
            "Assets/Game/Art/Sprites/Generated/TilePipe2",
        )


def test_slice_rendered_subtiles_uses_template_masks(tmp_path: Path):
    from PIL import Image

    texture = tmp_path / "render.png"
    template = tmp_path / "template.png"
    output_dir = tmp_path / "subtiles"

    Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(texture)
    template_image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    template_image.putpixel((16, 16), (0, 0, 0, 255))
    template_image.putpixel((28, 16), (0, 0, 0, 255))
    template_image.save(template)

    result = _slice_rendered_subtiles(
        render_result={
            "outputs": {"texture": str(texture)},
            "metadata": {
                "template_path": str(template),
                "output_tile_size": {"x": 64, "y": 64},
            },
        },
        output_dir=output_dir,
        tile_file="walls.tptile",
        masks=[4],
    )

    assert len(result) == 1
    assert Path(result[0]).name == "walls_frame_0_mask_4_variant_0.png"
