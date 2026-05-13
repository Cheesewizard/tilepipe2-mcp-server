"""Configuration and path policy for the TilePipe2 MCP server."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class TilePipeConfig(BaseModel):
	"""Runtime configuration for TilePipe2 automation."""

	godot_bin: Path | None = Field(default=None)
	tilepipe2_repo: Path = Field(default_factory=lambda: Path("D:/Programming/TilePipe2"))
	workspace: Path = Field(default_factory=lambda: Path("D:/Programming/tilepipe2-workspace"))
	unity_project_root: Path | None = Field(default_factory=lambda: Path("D:/Programming/Zombie_Game"))
	timeout_seconds: int = 120

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.tilepipe2_repo = self.tilepipe2_repo.expanduser().resolve()
		self.workspace = self.workspace.expanduser().resolve()
		self.workspace.mkdir(parents=True, exist_ok=True)
		if self.godot_bin is not None:
			self.godot_bin = self.godot_bin.expanduser().resolve()
		if self.unity_project_root is not None:
			self.unity_project_root = self.unity_project_root.expanduser().resolve()

	@classmethod
	def from_env(cls) -> "TilePipeConfig":
		godot_value = os.getenv("TILEPIPE_GODOT_BIN")
		unity_value = os.getenv("UNITY_PROJECT_ROOT", "D:/Programming/Zombie_Game")
		return cls(
			godot_bin=Path(godot_value) if godot_value else None,
			tilepipe2_repo=Path(os.getenv("TILEPIPE2_REPO", "D:/Programming/TilePipe2")),
			workspace=Path(os.getenv("TILEPIPE_WORKSPACE", "D:/Programming/tilepipe2-workspace")),
			unity_project_root=Path(unity_value) if unity_value else None,
			timeout_seconds=int(os.getenv("TILEPIPE_TIMEOUT", "120")),
		)

	def validate_godot(self) -> None:
		if self.godot_bin is None:
			raise ValueError("TILEPIPE_GODOT_BIN is required and must point to a Godot 3 executable.")
		if not self.godot_bin.is_file():
			raise ValueError(f"TILEPIPE_GODOT_BIN does not exist: {self.godot_bin}")

	def validate_tilepipe_repo(self) -> None:
		if not (self.tilepipe2_repo / "project.godot").is_file():
			raise ValueError(f"TilePipe2 repo does not contain project.godot: {self.tilepipe2_repo}")
		if not (self.tilepipe2_repo / "src" / "headless" / "TilePipeHeadless.gd").is_file():
			raise ValueError("TilePipe2 headless script is missing from src/headless/TilePipeHeadless.gd")

	def resolve_read_path(self, path: str | Path) -> Path:
		return Path(path).expanduser().resolve()

	def resolve_output_path(self, path: str | Path) -> Path:
		resolved = Path(path).expanduser().resolve()
		if self._is_under(resolved, self.workspace):
			return resolved
		if self.unity_project_root is not None and self._is_under(resolved, self.unity_project_root):
			return resolved
		raise ValueError(
			f"Output path must stay under workspace or Unity project root: {resolved}"
		)

	def ensure_output_dir(self, path: str | Path) -> Path:
		resolved = self.resolve_output_path(path)
		resolved.mkdir(parents=True, exist_ok=True)
		return resolved

	def ensure_parent_dir(self, path: str | Path) -> Path:
		resolved = self.resolve_output_path(path)
		resolved.parent.mkdir(parents=True, exist_ok=True)
		return resolved

	@staticmethod
	def _is_under(path: Path, root: Path) -> bool:
		try:
			path.relative_to(root)
			return True
		except ValueError:
			return False

