from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class BackendError(RuntimeError):
    """Raised when Codex cannot produce a translation."""


@dataclass(slots=True)
class CodexCLIBackend:
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "high"
    timeout_seconds: int = 120
    executable: str = "codex"

    def executable_path(self) -> str:
        explicit = Path(self.executable).expanduser()
        if explicit.is_file():
            return str(explicit.resolve())

        candidates: list[Path] = []
        install_dir = os.environ.get("CODEX_INSTALL_DIR")
        if install_dir:
            candidates.append(Path(install_dir) / "codex.exe")

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_root = Path(local_app_data)
            candidates.extend(
                [
                    local_root / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe",
                    local_root / "OpenAI" / "Codex" / "bin" / "codex.exe",
                ]
            )
            embedded_bin = local_root / "OpenAI" / "Codex" / "bin"
            if embedded_bin.is_dir():
                candidates.extend(embedded_bin.glob("*/codex.exe"))

        existing = [candidate for candidate in candidates if candidate.is_file()]
        if existing:
            newest = max(existing, key=lambda candidate: candidate.stat().st_mtime)
            return str(newest.resolve())

        path = shutil.which(self.executable)
        if path:
            return path

        raise BackendError(
            "codex.exe was not found. Install Codex CLI or set CODEX_INSTALL_DIR."
        )

    def login_status(self) -> str:
        command = [self.executable_path(), "login", "status"]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=_no_window_flag(),
        )
        message = (completed.stdout or completed.stderr).strip()
        if completed.returncode != 0:
            raise BackendError(message or "Codex is not logged in. Run codex login in a terminal first.")
        return message or "Codex is logged in."

    def translate(self, prompt: str, image_path: Path | None = None) -> str:
        with tempfile.TemporaryDirectory(prefix="lamarck-translator-") as temp_dir:
            command = [
                self.executable_path(),
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ignore-user-config",
                "--ignore-rules",
                "--color",
                "never",
                "--cd",
                temp_dir,
            ]
            if self.model.strip():
                command.extend(["--model", self.model.strip()])
            if self.reasoning_effort.strip():
                command.extend(
                    [
                        "--config",
                        f'model_reasoning_effort="{self.reasoning_effort.strip()}"',
                    ]
                )
            if image_path is not None:
                command.extend(["--image", str(image_path.resolve())])
            command.append("-")

            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    creationflags=_no_window_flag(),
                )
            except subprocess.TimeoutExpired as exc:
                raise BackendError(
                    f"Codex did not finish within {self.timeout_seconds} seconds. Please try again."
                ) from exc

        output = completed.stdout.strip()
        if completed.returncode != 0:
            details = completed.stderr.strip() or output
            if "not logged in" in details.lower():
                raise BackendError("Codex is not logged in. Run codex login in a terminal first.")
            raise BackendError(details or f"Codex failed with exit code {completed.returncode}.")
        if not output:
            raise BackendError("Codex did not return a translation.")
        return output


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
