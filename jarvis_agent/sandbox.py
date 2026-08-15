"""Thin wrapper around `llm_sandbox`'s Docker-backed script execution.

No agent/tool logic here — this module only knows how to run a script inside
an isolated container and move files across the host/container boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_sandbox import SandboxBackend, SandboxSession

from jarvis_agent.config import SANDBOX_IMAGE, SANDBOX_LANG, SANDBOX_WORKDIR


@dataclass(frozen=True)
class ScriptResult:
    """Outcome of running a script in the sandbox."""

    stdout: str
    stderr: str
    exit_code: int
    output_files: list[str]


class SandboxError(Exception):
    """Raised when the sandbox itself fails (e.g. Docker unavailable)."""


class Sandbox:
    """Runs Python scripts inside a fresh Docker container per call."""

    def __init__(
        self,
        workspace_dir: Path,
        image: str = SANDBOX_IMAGE,
        lang: str = SANDBOX_LANG,
        workdir: str = SANDBOX_WORKDIR,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.image = image
        self.lang = lang
        self.workdir = workdir

    def run_script(
        self,
        code: str,
        *,
        libraries: list[str] | None = None,
        input_files: list[str] | None = None,
        output_files: list[str] | None = None,
    ) -> ScriptResult:
        """Run `code` in a fresh container, copying files across the boundary.

        Each entry in `input_files`/`output_files` is a filename relative to
        `workspace_dir`, mapped to `{workdir}/{name}` inside the container.
        A requested output file that the script never produced is silently
        omitted from the result (visible instead via stdout/stderr/exit_code)
        rather than raising.
        """
        try:
            with SandboxSession(
                backend=SandboxBackend.DOCKER,
                lang=self.lang,
                image=self.image,
            ) as session:
                for name in input_files or []:
                    session.copy_to_runtime(
                        str(self._safe_path(name)), f"{self.workdir}/{name}"
                    )
                result = session.run(code, libraries=libraries)
                copied: list[str] = []
                for name in output_files or []:
                    try:
                        session.copy_from_runtime(
                            f"{self.workdir}/{name}", str(self._safe_path(name))
                        )
                        copied.append(name)
                    except Exception:
                        pass
        except SandboxError:
            raise
        except Exception as exc:
            raise SandboxError(
                "Could not start the Docker sandbox — is the Docker daemon "
                "running?"
            ) from exc

        return ScriptResult(result.stdout, result.stderr, result.exit_code, copied)

    def _safe_path(self, name: str) -> Path:
        """Resolve `name` against `workspace_dir`, rejecting path traversal."""
        resolved = (self.workspace_dir / name).resolve()
        if not resolved.is_relative_to(self.workspace_dir.resolve()):
            raise SandboxError(
                f"Refusing to access '{name}': path escapes the workspace "
                "directory."
            )
        return resolved
