from pathlib import Path

import pytest

from tilepipe_mcp.config import TilePipeConfig


def test_output_path_allows_workspace(tmp_path: Path):
    config = TilePipeConfig(
        workspace=tmp_path / "workspace",
        tilepipe2_repo=tmp_path / "TilePipe2",
        unity_project_root=tmp_path / "Zombie_Game",
    )

    output = config.resolve_output_path(config.workspace / "candidate" / "out.png")

    assert output == config.workspace / "candidate" / "out.png"


def test_output_path_allows_unity_root(tmp_path: Path):
    config = TilePipeConfig(
        workspace=tmp_path / "workspace",
        tilepipe2_repo=tmp_path / "TilePipe2",
        unity_project_root=tmp_path / "Zombie_Game",
    )

    output = config.resolve_output_path(config.unity_project_root / "Assets" / "out.png")

    assert output == config.unity_project_root / "Assets" / "out.png"


def test_output_path_rejects_escape(tmp_path: Path):
    config = TilePipeConfig(
        workspace=tmp_path / "workspace",
        tilepipe2_repo=tmp_path / "TilePipe2",
        unity_project_root=tmp_path / "Zombie_Game",
    )

    with pytest.raises(ValueError, match="Output path must stay"):
        config.resolve_output_path(tmp_path / "outside" / "out.png")


def test_validate_godot_requires_env_path(tmp_path: Path):
    config = TilePipeConfig(
        workspace=tmp_path / "workspace",
        tilepipe2_repo=tmp_path / "TilePipe2",
        unity_project_root=None,
    )

    with pytest.raises(ValueError, match="TILEPIPE_GODOT_BIN"):
        config.validate_godot()

