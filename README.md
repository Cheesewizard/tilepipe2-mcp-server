# tilepipe2-mcp-server

Model Context Protocol server for TilePipe2 autotile generation workflows, focused first on Unity-ready wall-kit output for `Zombie_Game`.

TilePipe2 source changes and headless automation hooks live in:

- https://github.com/Cheesewizard/TilePipe2

## Requirements

- Python 3.10+
- Godot 3 executable
- TilePipe2 fork with `src/headless/TilePipeHeadless.gd`

Set these environment variables:

```powershell
$env:TILEPIPE_GODOT_BIN = "C:\Path\To\Godot_v3.x.exe"
$env:TILEPIPE2_REPO = "D:\Programming\TilePipe2"
$env:TILEPIPE_WORKSPACE = "D:\Programming\tilepipe2-workspace"
$env:UNITY_PROJECT_ROOT = "D:\Programming\Zombie_Game"
```

`UNITY_PROJECT_ROOT` is optional. Generation works without Unity running; Unity MCP can be used later to refresh/import generated assets.

## Run

```powershell
uv run tilepipe2-mcp
```

## Tools

- `tilepipe_health`
- `tilepipe_list_projects`
- `tilepipe_inspect_project`
- `tilepipe_list_rulesets`
- `tilepipe_list_templates`
- `tilepipe_create_project_from_art`
- `tilepipe_create_tile`
- `tilepipe_validate_ruleset`
- `tilepipe_validate_template`
- `tilepipe_validate_tile`
- `tilepipe_render_tile`
- `tilepipe_export_texture`
- `tilepipe_export_subtiles`
- `tilepipe_export_mask_set`
- `tilepipe_create_unity_wallkit_job`
- `tilepipe_generate_unity_wallkit`
- `tilepipe_generate_wallkit_candidate`
- `tilepipe_generate_floor_candidate`
- `tilepipe_validate_candidate_complete`
- `tilepipe_prepare_unity_promotion`
- `tilepipe_promote_with_unity_mcp`
- `tilepipe_validate_unity_wallkit_output`
- `tilepipe_write_validation_manifest`
- `tilepipe_refresh_unity_assets`

## Unity Wall-Kit Workflow

`tilepipe_generate_wallkit_candidate` writes a staged output folder containing:

- a combined PNG texture
- optional split subtile PNGs
- `tilepipe_candidate_manifest.json`

The manifest records source `.tptile`, ruleset/template metadata, generated bitmasks, expected masks, missing masks, PNG dimensions, and Unity import recommendations. Active Unity runtime assets are not replaced automatically.

Use `tilepipe_prepare_unity_promotion` after candidate validation. It returns the explicit Unity MCP steps and requires a selected Unity target such as a `WallSetConfig`, RuleTile, or generated asset folder. Python never edits Unity `.asset` or `.meta` YAML directly.

`tilepipe_create_project_from_art` and `tilepipe_create_tile` can build TilePipe2 `.tptile` files from source PNG art plus an existing ruleset/template. Created projects use TilePipe2's native folder layout:

- `textures/`
- `rulesets/`
- `templates/`
- `<name>.tptile`
