"""Subprocess bridge to the TilePipe2 headless Godot entrypoint."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from typing import Any

from .config import TilePipeConfig


HEADLESS_SCRIPT = "res://src/headless/TilePipeHeadless.gd"


class TilePipeCommandError(RuntimeError):
    """Raised when TilePipe2 headless execution fails."""

    def __init__(self, message: str, result: dict[str, Any] | None = None):
        super().__init__(message)
        self.result = result or {}


class TilePipeGodotClient:
    """Runs JSON commands through the TilePipe2 Godot automation script."""

    def __init__(self, config: TilePipeConfig):
        self.config = config

    def run(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.config.validate_godot()
        self.config.validate_tilepipe_repo()

        job_dir = self.config.ensure_output_dir(self.config.workspace / "jobs" / uuid.uuid4().hex)
        request_path = job_dir / "request.json"
        response_path = job_dir / "response.json"
        request = {"command": command, **payload}
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")

        args = [
            str(self.config.godot_bin),
            "--no-window",
            "--path",
            str(self.config.tilepipe2_repo),
            "--script",
            HEADLESS_SCRIPT,
            "--request",
            str(request_path),
            "--response",
            str(response_path),
        ]

        env = os.environ.copy()
        env["TILEPIPE_REQUEST"] = str(request_path)
        env["TILEPIPE_RESPONSE"] = str(response_path)

        completed = subprocess.run(
            args,
            cwd=str(self.config.tilepipe2_repo),
            capture_output=True,
            text=True,
            timeout=self.config.timeout_seconds,
            check=False,
            env=env,
        )

        deadline = time.monotonic() + self.config.timeout_seconds
        while not response_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.1)

        result: dict[str, Any] | None = None
        if response_path.is_file():
            result = json.loads(response_path.read_text(encoding="utf-8"))

        if completed.returncode != 0:
            if result is None:
                raise TilePipeCommandError(
                    "TilePipe2 headless command failed before writing a response.",
                    {
                        "ok": False,
                        "command": command,
                        "errors": [completed.stderr.strip() or completed.stdout.strip()],
                        "outputs": {},
                        "metadata": {},
                    },
                )
            raise TilePipeCommandError("TilePipe2 headless command failed.", result)

        if result is None:
            raise TilePipeCommandError("TilePipe2 headless command did not write a response.")

        return result
