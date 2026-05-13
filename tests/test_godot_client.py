import json
import subprocess
from pathlib import Path

import pytest

from tilepipe_mcp.config import TilePipeConfig
from tilepipe_mcp.godot import TilePipeCommandError, TilePipeGodotClient


def make_config(tmp_path: Path) -> TilePipeConfig:
    godot = tmp_path / "godot.exe"
    godot.write_text("fake", encoding="utf-8")
    repo = tmp_path / "TilePipe2"
    (repo / "src" / "headless").mkdir(parents=True)
    (repo / "project.godot").write_text("", encoding="utf-8")
    (repo / "src" / "headless" / "TilePipeHeadless.gd").write_text("", encoding="utf-8")
    return TilePipeConfig(
        godot_bin=godot,
        tilepipe2_repo=repo,
        workspace=tmp_path / "workspace",
        unity_project_root=None,
    )


def test_client_writes_request_and_reads_response(monkeypatch, tmp_path: Path):
    config = make_config(tmp_path)
    client = TilePipeGodotClient(config)

    def fake_run(args, cwd, capture_output, text, timeout, check):
        response_path = Path(args[args.index("--response") + 1])
        response_path.write_text(
            json.dumps({"ok": True, "command": "inspect_project", "outputs": {}, "metadata": {}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = client.run("inspect_project", {"project_dir": "project"})

    assert result["ok"] is True
    request_files = list((config.workspace / "jobs").glob("*/request.json"))
    assert request_files
    request = json.loads(request_files[0].read_text(encoding="utf-8"))
    assert request["command"] == "inspect_project"


def test_client_raises_structured_error(monkeypatch, tmp_path: Path):
    config = make_config(tmp_path)
    client = TilePipeGodotClient(config)

    def fake_run(args, cwd, capture_output, text, timeout, check):
        response_path = Path(args[args.index("--response") + 1])
        response_path.write_text(
            json.dumps({"ok": False, "command": "validate_tile", "errors": ["bad tile"]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(TilePipeCommandError) as error:
        client.run("validate_tile", {"project_dir": "project"})

    assert error.value.result["errors"] == ["bad tile"]

