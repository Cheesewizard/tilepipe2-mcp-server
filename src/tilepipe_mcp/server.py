"""FastMCP server for TilePipe2 Unity wall-kit workflows."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, ValidationError
from pydantic import BaseModel, Field

from .config import TilePipeConfig
from .godot import TilePipeCommandError, TilePipeGodotClient
from .manifests import (
    WALL_REQUIRED_MASKS,
    build_candidate_manifest,
    build_unity_manifest,
    validate_candidate_output,
    validate_unity_wallkit_output,
    write_manifest,
)

app = FastMCP("tilepipe2-mcp")

F = TypeVar("F", bound=Callable[..., object])
tool: Callable[[str], Callable[[F], F]] = cast(Any, app.tool)

CFG: TilePipeConfig | None = None
CLIENT: TilePipeGodotClient | None = None


class TileRequest(BaseModel):
    project_dir: str = Field(description="TilePipe2 project directory containing .tptile files.")
    tile_file: str = Field(description="Tile file name relative to project_dir.")


class UnityWallKitJob(BaseModel):
    job_name: str = Field(description="Short filesystem-safe job name.")
    project_dir: str = Field(description="TilePipe2 project directory.")
    tile_file: str = Field(description="Tile file name relative to project_dir.")
    output_dir: str | None = Field(
        default=None,
        description="Output directory. Defaults to TILEPIPE_WORKSPACE/unity-wallkits/<job_name>.",
    )
    export_subtiles: bool = True


def _vector(x: int, y: int) -> dict[str, int]:
    return {"x": x, "y": y}


def _init_config(config: TilePipeConfig | None = None) -> None:
    global CFG, CLIENT
    CFG = config or TilePipeConfig.from_env()
    CLIENT = TilePipeGodotClient(CFG)


def _require_config() -> TilePipeConfig:
    if CFG is None:
        _init_config()
    if CFG is None:
        raise ToolError("TilePipe MCP config was not initialized.")
    return CFG


def _require_client() -> TilePipeGodotClient:
    if CLIENT is None:
        _init_config()
    if CLIENT is None:
        raise ToolError("TilePipe MCP client was not initialized.")
    return CLIENT


def _run(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _require_client().run(command, payload)
    except TilePipeCommandError as error:
        raise ToolError(json.dumps(error.result or {"errors": [str(error)]}, indent=2)) from error
    except ValueError as error:
        raise ValidationError(str(error)) from error


def _sanitize_job_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    if not sanitized:
        raise ValidationError("job_name must contain at least one filesystem-safe character.")
    return sanitized


def _tile_payload(tile: TileRequest) -> dict[str, Any]:
    return {"project_dir": str(Path(tile.project_dir).expanduser().resolve()), "tile_file": tile.tile_file}


def _default_candidate_dir(candidate_type: str, job_name: str) -> Path:
    return _require_config().workspace / "unity-candidates" / candidate_type / job_name


def _normalize_project_dir(project_dir: str | Path) -> str:
    return str(Path(project_dir).expanduser().resolve())


@tool("tilepipe_health")
def tilepipe_health() -> dict[str, Any]:
    """Report configuration and dependency status."""
    config = _require_config()
    godot_ok = config.godot_bin is not None and config.godot_bin.is_file()
    tilepipe_ok = (config.tilepipe2_repo / "project.godot").is_file()
    headless_ok = (config.tilepipe2_repo / "src" / "headless" / "TilePipeHeadless.gd").is_file()
    return {
        "ok": godot_ok and tilepipe_ok and headless_ok,
        "godot_bin": str(config.godot_bin) if config.godot_bin else None,
        "godot_ok": godot_ok,
        "tilepipe2_repo": str(config.tilepipe2_repo),
        "tilepipe_ok": tilepipe_ok,
        "headless_ok": headless_ok,
        "workspace": str(config.workspace),
        "unity_project_root": str(config.unity_project_root) if config.unity_project_root else None,
    }


@tool("tilepipe_list_projects")
def tilepipe_list_projects() -> dict[str, Any]:
    """List candidate TilePipe2 projects under the configured workspace and repo examples."""
    config = _require_config()
    candidates: list[str] = []
    for root in [config.workspace, config.tilepipe2_repo / "examples"]:
        if not root.exists():
            continue
        if any(root.glob("*.tptile")):
            candidates.append(str(root))
        for child in root.iterdir():
            if child.is_dir() and any(child.glob("*.tptile")):
                candidates.append(str(child))
    return {"ok": True, "projects": sorted(set(candidates))}


@tool("tilepipe_inspect_project")
def tilepipe_inspect_project(project_dir: str) -> dict[str, Any]:
    """Inspect a TilePipe2 project folder."""
    return _run("inspect_project", {"project_dir": str(Path(project_dir).expanduser().resolve())})


@tool("tilepipe_list_rulesets")
def tilepipe_list_rulesets(project_dir: str) -> dict[str, Any]:
    """List TilePipe2 rulesets in a project."""
    return _run("list_rulesets", {"project_dir": _normalize_project_dir(project_dir)})


@tool("tilepipe_list_templates")
def tilepipe_list_templates(project_dir: str) -> dict[str, Any]:
    """List TilePipe2 templates in a project."""
    return _run("list_templates", {"project_dir": _normalize_project_dir(project_dir)})


@tool("tilepipe_create_project_from_art")
def tilepipe_create_project_from_art(
    project_dir: str,
    tile_file: str,
    source_png: str,
    ruleset_path: str,
    template_path: str,
    input_tile_size: int = 64,
    output_tile_width: int = 64,
    output_tile_height: int = 64,
) -> dict[str, Any]:
    """Create a TilePipe2 project and .tptile from source art, ruleset, and template."""
    config = _require_config()
    resolved_project = config.ensure_output_dir(project_dir)
    return _run(
        "create_project_from_art",
        {
            "project_dir": str(resolved_project),
            "tile_file": tile_file,
            "source_png": str(config.resolve_read_path(source_png)),
            "ruleset_path": str(config.resolve_read_path(ruleset_path)),
            "template_path": str(config.resolve_read_path(template_path)),
            "input_tile_size": _vector(input_tile_size, input_tile_size),
            "output_tile_size": _vector(output_tile_width, output_tile_height),
            "output_resize": output_tile_width != input_tile_size
            or output_tile_height != input_tile_size,
        },
    )


@tool("tilepipe_create_tile")
def tilepipe_create_tile(
    project_dir: str,
    tile_file: str,
    source_png: str,
    ruleset_path: str,
    template_path: str,
    input_tile_size: int = 64,
    output_tile_width: int = 64,
    output_tile_height: int = 64,
) -> dict[str, Any]:
    """Create a .tptile in an existing or new TilePipe2 project."""
    return tilepipe_create_project_from_art(
        project_dir,
        tile_file,
        source_png,
        ruleset_path,
        template_path,
        input_tile_size,
        output_tile_width,
        output_tile_height,
    )


@tool("tilepipe_validate_ruleset")
def tilepipe_validate_ruleset(ruleset_path: str) -> dict[str, Any]:
    """Validate and summarize a TilePipe2 ruleset JSON file."""
    path = _require_config().resolve_read_path(ruleset_path)
    return _run("validate_ruleset", {"ruleset_path": str(path)})


@tool("tilepipe_validate_template")
def tilepipe_validate_template(template_path: str) -> dict[str, Any]:
    """Validate and summarize a TilePipe2 template PNG."""
    path = _require_config().resolve_read_path(template_path)
    return _run("validate_template", {"template_path": str(path)})


@tool("tilepipe_validate_tile")
def tilepipe_validate_tile(project_dir: str, tile_file: str) -> dict[str, Any]:
    """Validate a TilePipe2 .tptile file and emit metadata."""
    return _run("validate_tile", _tile_payload(TileRequest(project_dir=project_dir, tile_file=tile_file)))


@tool("tilepipe_render_tile")
def tilepipe_render_tile(project_dir: str, tile_file: str, output_path: str) -> dict[str, Any]:
    """Render a TilePipe2 tile to a single PNG."""
    config = _require_config()
    resolved_output = config.ensure_parent_dir(output_path)
    payload = _tile_payload(TileRequest(project_dir=project_dir, tile_file=tile_file))
    payload["output_path"] = str(resolved_output)
    return _run("render_tile", payload)


@tool("tilepipe_export_texture")
def tilepipe_export_texture(project_dir: str, tile_file: str, output_path: str) -> dict[str, Any]:
    """Export a TilePipe2 tile texture to PNG."""
    return tilepipe_render_tile(project_dir, tile_file, output_path)


@tool("tilepipe_export_subtiles")
def tilepipe_export_subtiles(project_dir: str, tile_file: str, output_dir: str) -> dict[str, Any]:
    """Export each generated subtile to an individual PNG."""
    config = _require_config()
    resolved_dir = config.ensure_output_dir(output_dir)
    payload = _tile_payload(TileRequest(project_dir=project_dir, tile_file=tile_file))
    payload["output_dir"] = str(resolved_dir)
    return _run("export_subtiles", payload)


@tool("tilepipe_export_mask_set")
def tilepipe_export_mask_set(
    project_dir: str,
    tile_file: str,
    output_dir: str,
    masks: list[int] | None = None,
    frame_index: int | None = None,
) -> dict[str, Any]:
    """Export generated subtiles, optionally filtered to specific masks and frame."""
    config = _require_config()
    resolved_dir = config.ensure_output_dir(output_dir)
    payload = _tile_payload(TileRequest(project_dir=project_dir, tile_file=tile_file))
    payload["output_dir"] = str(resolved_dir)
    if masks is not None:
        payload["masks"] = masks
    if frame_index is not None:
        payload["frame_index"] = frame_index
    return _run("export_mask_set", payload)


@tool("tilepipe_create_unity_wallkit_job")
def tilepipe_create_unity_wallkit_job(
    job_name: str,
    project_dir: str,
    tile_file: str,
    output_dir: str | None = None,
    export_subtiles: bool = True,
) -> dict[str, Any]:
    """Create a normalized Unity wall-kit generation job description."""
    config = _require_config()
    safe_name = _sanitize_job_name(job_name)
    resolved_output = (
        config.ensure_output_dir(output_dir)
        if output_dir
        else config.ensure_output_dir(config.workspace / "unity-wallkits" / safe_name)
    )
    job = UnityWallKitJob(
        job_name=safe_name,
        project_dir=str(Path(project_dir).expanduser().resolve()),
        tile_file=tile_file,
        output_dir=str(resolved_output),
        export_subtiles=export_subtiles,
    )
    return {"ok": True, "job": job.model_dump()}


@tool("tilepipe_generate_unity_wallkit")
def tilepipe_generate_unity_wallkit(
    job_name: str,
    project_dir: str,
    tile_file: str,
    output_dir: str | None = None,
    export_subtiles: bool = True,
) -> dict[str, Any]:
    """Generate Unity-ready wall-kit outputs and a validation manifest."""
    config = _require_config()
    job_result = tilepipe_create_unity_wallkit_job(
        job_name,
        project_dir,
        tile_file,
        output_dir,
        export_subtiles,
    )
    job = job_result["job"]
    job_output_dir = Path(job["output_dir"])
    texture_path = job_output_dir / f"{job['job_name']}.png"
    render_result = tilepipe_render_tile(job["project_dir"], job["tile_file"], str(texture_path))

    if export_subtiles:
        subtiles_dir = job_output_dir / "subtiles"
        subtile_result = tilepipe_export_subtiles(job["project_dir"], job["tile_file"], str(subtiles_dir))
        render_result.setdefault("outputs", {})["subtiles"] = subtile_result.get("outputs", {}).get(
            "subtiles", []
        )

    manifest = build_unity_manifest(
        job_name=job["job_name"],
        source_tile={"project_dir": job["project_dir"], "tile_file": job["tile_file"]},
        render_result=render_result,
        output_dir=job_output_dir,
        unity_project_root=config.unity_project_root,
    )
    manifest_path = write_manifest(job_output_dir / "tilepipe_wallkit_manifest.json", manifest)
    validation = validate_unity_wallkit_output(manifest)
    return {
        "ok": validation["ok"],
        "job": job,
        "outputs": render_result.get("outputs", {}),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "validation": validation,
    }


def _generate_candidate(
    *,
    candidate_type: str,
    job_name: str,
    project_dir: str,
    tile_file: str,
    output_dir: str | None,
    export_subtiles: bool,
    expected_masks: list[int] | None,
) -> dict[str, Any]:
    config = _require_config()
    safe_name = _sanitize_job_name(job_name)
    job_output_dir = (
        config.ensure_output_dir(output_dir)
        if output_dir
        else config.ensure_output_dir(_default_candidate_dir(candidate_type, safe_name))
    )
    texture_path = job_output_dir / f"{safe_name}.png"
    render_result = tilepipe_render_tile(project_dir, tile_file, str(texture_path))

    if export_subtiles:
        subtiles_dir = job_output_dir / "subtiles"
        subtile_result = tilepipe_export_mask_set(
            project_dir,
            tile_file,
            str(subtiles_dir),
            expected_masks,
        )
        render_result.setdefault("outputs", {})["subtiles"] = subtile_result.get("outputs", {}).get(
            "subtiles", []
        )

    manifest = build_candidate_manifest(
        job_name=safe_name,
        candidate_type=candidate_type,
        source_tile={"project_dir": _normalize_project_dir(project_dir), "tile_file": tile_file},
        render_result=render_result,
        output_dir=job_output_dir,
        unity_project_root=config.unity_project_root,
        expected_masks=expected_masks,
    )
    manifest_path = write_manifest(job_output_dir / "tilepipe_candidate_manifest.json", manifest)
    validation = validate_candidate_output(manifest)
    return {
        "ok": validation["ok"],
        "candidate_type": candidate_type,
        "outputs": render_result.get("outputs", {}),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "validation": validation,
    }


@tool("tilepipe_generate_wallkit_candidate")
def tilepipe_generate_wallkit_candidate(
    job_name: str,
    project_dir: str,
    tile_file: str,
    output_dir: str | None = None,
    export_subtiles: bool = True,
) -> dict[str, Any]:
    """Generate a staged Unity wall-kit candidate with required wall mask validation."""
    return _generate_candidate(
        candidate_type="wallkit",
        job_name=job_name,
        project_dir=project_dir,
        tile_file=tile_file,
        output_dir=output_dir,
        export_subtiles=export_subtiles,
        expected_masks=WALL_REQUIRED_MASKS,
    )


@tool("tilepipe_generate_floor_candidate")
def tilepipe_generate_floor_candidate(
    job_name: str,
    project_dir: str,
    tile_file: str,
    output_dir: str | None = None,
    export_subtiles: bool = True,
) -> dict[str, Any]:
    """Generate a staged Unity floor autotile candidate."""
    return _generate_candidate(
        candidate_type="floor",
        job_name=job_name,
        project_dir=project_dir,
        tile_file=tile_file,
        output_dir=output_dir,
        export_subtiles=export_subtiles,
        expected_masks=None,
    )


@tool("tilepipe_validate_candidate_complete")
def tilepipe_validate_candidate_complete(manifest_path: str) -> dict[str, Any]:
    """Validate a TilePipe2 Unity candidate manifest and referenced files."""
    manifest_file = _require_config().resolve_read_path(manifest_path)
    if not manifest_file.is_file():
        raise ValidationError(f"Manifest file does not exist: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    return validate_candidate_output(manifest)


@tool("tilepipe_prepare_unity_promotion")
def tilepipe_prepare_unity_promotion(
    manifest_path: str,
    target_asset_folder: str,
    target_wall_set_config: str | None = None,
    target_rule_tile: str | None = None,
) -> dict[str, Any]:
    """Prepare explicit Unity MCP promotion instructions without mutating Unity assets."""
    config = _require_config()
    if config.unity_project_root is None:
        raise ValidationError("UNITY_PROJECT_ROOT is not configured.")
    manifest_file = config.resolve_read_path(manifest_path)
    if not manifest_file.is_file():
        raise ValidationError(f"Manifest file does not exist: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    validation = validate_candidate_output(manifest)
    if not validation["ok"]:
        raise ValidationError(f"Candidate is not complete: {validation['errors']}")

    return {
        "ok": True,
        "manifest_path": str(manifest_file),
        "target_asset_folder": target_asset_folder,
        "target_wall_set_config": target_wall_set_config,
        "target_rule_tile": target_rule_tile,
        "unity_menu": "WorldGen/TilePipe2/Validate Selected Promotion Manifest",
        "requires_explicit_target": True,
        "instructions": [
            "Use Unity MCP to import the manifest outputs into target_asset_folder.",
            "Apply 64 PPU, Point filter, uncompressed sprites, alpha transparency, no mipmaps.",
            "Only update target_wall_set_config or target_rule_tile if the user explicitly selected it.",
        ],
        "validation": validation,
    }


@tool("tilepipe_promote_with_unity_mcp")
def tilepipe_promote_with_unity_mcp(
    manifest_path: str,
    target_asset_folder: str,
    explicit_target: str,
) -> dict[str, Any]:
    """Return a Unity MCP promotion request that requires an explicit selected target."""
    if not explicit_target.strip():
        raise ValidationError("explicit_target is required before Unity promotion can run.")
    prepared = tilepipe_prepare_unity_promotion(
        manifest_path=manifest_path,
        target_asset_folder=target_asset_folder,
        target_wall_set_config=explicit_target,
    )
    prepared["message"] = (
        "Unity MCP must execute the project editor utility against this explicit target; "
        "the Python MCP server does not edit Unity asset YAML."
    )
    return prepared


@tool("tilepipe_validate_unity_wallkit_output")
def tilepipe_validate_unity_wallkit_output(manifest_path: str) -> dict[str, Any]:
    """Validate a generated Unity wall-kit manifest and referenced outputs."""
    manifest_file = _require_config().resolve_read_path(manifest_path)
    if not manifest_file.is_file():
        raise ValidationError(f"Manifest file does not exist: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    return validate_unity_wallkit_output(manifest)


@tool("tilepipe_write_validation_manifest")
def tilepipe_write_validation_manifest(manifest_path: str, manifest_json: dict[str, Any]) -> dict[str, Any]:
    """Write a wall-kit validation manifest to an allowed output path."""
    path = _require_config().ensure_parent_dir(manifest_path)
    write_manifest(path, manifest_json)
    return {"ok": True, "manifest_path": str(path)}


@tool("tilepipe_refresh_unity_assets")
def tilepipe_refresh_unity_assets(asset_path: str | None = None) -> dict[str, Any]:
    """Report the Unity refresh action expected after generation.

    The standalone MCP does not directly own Unity Editor state. When Unity MCP is connected,
    the calling agent should use it to refresh/import the returned asset path.
    """
    config = _require_config()
    if config.unity_project_root is None:
        raise ValidationError("UNITY_PROJECT_ROOT is not configured.")
    return {
        "ok": True,
        "unity_project_root": str(config.unity_project_root),
        "asset_path": asset_path,
        "message": "Use Unity MCP to refresh/import this path when a Unity editor session is connected.",
    }


def main() -> None:
    _init_config()
    app.run()


if __name__ == "__main__":
    main()
