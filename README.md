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
- `tilepipe_validate_ruleset`
- `tilepipe_validate_template`
- `tilepipe_validate_tile`
- `tilepipe_render_tile`
- `tilepipe_export_texture`
- `tilepipe_export_subtiles`
- `tilepipe_create_unity_wallkit_job`
- `tilepipe_generate_unity_wallkit`
- `tilepipe_validate_unity_wallkit_output`
- `tilepipe_write_validation_manifest`
- `tilepipe_refresh_unity_assets`

## Unity Wall-Kit Workflow

`tilepipe_generate_unity_wallkit` writes a staged output folder containing:

- a combined PNG texture
- optional split subtile PNGs
- `tilepipe_wallkit_manifest.json`

The manifest records source `.tptile`, ruleset/template metadata, generated bitmasks, missing masks, and Unity import recommendations. Active Unity runtime assets are not replaced by v1 tools.
