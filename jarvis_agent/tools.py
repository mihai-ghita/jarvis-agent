"""Tool schemas and dispatch for the agent's file/skill/sandbox actions.

`TOOL_DEFINITIONS` is handed to the Anthropic API verbatim; `ToolExecutor`
is the host-side implementation Claude's `tool_use` blocks are dispatched
to. No API/network logic here — that lives in `core.py`.
"""

from __future__ import annotations

from pathlib import Path

from jarvis_agent.sandbox import Sandbox, SandboxError
from jarvis_agent.skills import Skill, SkillNotFoundError, load_skill

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the full text content of a file in the agent's workspace. "
            "Use this to inspect existing files before editing them or to "
            "pull in data a script will need."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the file, relative to the workspace root "
                        "(e.g. 'notes.txt' or 'reports/summary.md')."
                    ),
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file in the agent's workspace, "
            "creating it (and any parent directories) if needed, or "
            "overwriting it if it already exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the file, relative to the workspace root "
                        "(e.g. 'notes.txt' or 'reports/summary.md')."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "The full text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List the files and subdirectories at a path in the agent's "
            "workspace. Non-recursive — only shows the immediate contents "
            "of the given directory. Directory entries are suffixed with "
            "'/'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory to list, relative to the workspace root. "
                        "Defaults to the workspace root itself."
                    ),
                },
            },
        },
    },
    {
        "name": "load_skill",
        "description": (
            "Fetch the full instructions for a named skill. A catalog of "
            "available skill names and short descriptions is already "
            "included in the system prompt — call this tool with one of "
            "those names to get the complete, detailed instructions before "
            "attempting the task the skill covers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact skill name from the catalog (e.g. 'pdf-generation').",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "run_python_script",
        "description": (
            "Run a Python script inside a fresh, isolated Docker sandbox "
            "and return its stdout, stderr, and exit code. Use this to "
            "generate files (e.g. PDFs), process data, or run any code "
            "rather than executing it on the host. The script runs with "
            "its working directory at /sandbox; any input files should be "
            "read from /sandbox/<filename> and any files you want copied "
            "back to the workspace should be written to /sandbox/<filename>, "
            "matching the names listed in input_files/output_files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The full Python source code to execute in the sandbox.",
                },
                "libraries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Pip package names to install in the sandbox before "
                        "running the script (e.g. ['reportlab']). Leave "
                        "empty if the script only needs the standard "
                        "library."
                    ),
                },
                "input_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Workspace-relative filenames to copy into the "
                        "sandbox before running the script, available at "
                        "/sandbox/<filename>."
                    ),
                },
                "output_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Filenames the script is expected to produce at "
                        "/sandbox/<filename>; each one that exists after the "
                        "run is copied back to the workspace root. Any name "
                        "listed here that the script didn't actually "
                        "produce is reported back so you can notice and fix "
                        "the script."
                    ),
                },
            },
            "required": ["code"],
        },
    },
]


class ToolError(Exception):
    """Raised when a tool call fails; converted to an `is_error` tool_result."""


class ToolExecutor:
    """Executes tool_use calls against the workspace, skills, and sandbox."""

    def __init__(
        self,
        workspace_dir: Path,
        sandbox: Sandbox,
        skills: dict[str, Skill],
    ) -> None:
        self.workspace_dir = workspace_dir
        self.sandbox = sandbox
        self.skills = skills

    def execute(self, name: str, tool_input: dict) -> str:
        """Dispatch a tool_use call by name and return its result text.

        Raises `ToolError` if `name` isn't a recognized tool.
        """
        if name == "read_file":
            return self._read_file(tool_input["path"])
        if name == "write_file":
            return self._write_file(tool_input["path"], tool_input["content"])
        if name == "list_files":
            return self._list_files(tool_input.get("path", "."))
        if name == "load_skill":
            return self._load_skill(tool_input["name"])
        if name == "run_python_script":
            return self._run_python_script(
                tool_input["code"],
                libraries=tool_input.get("libraries") or [],
                input_files=tool_input.get("input_files") or [],
                output_files=tool_input.get("output_files") or [],
            )
        raise ToolError(f"Unknown tool '{name}'.")

    def _safe_workspace_path(self, path: str) -> Path:
        """Resolve `path` against `workspace_dir`, rejecting path traversal."""
        resolved = (self.workspace_dir / path).resolve()
        if not resolved.is_relative_to(self.workspace_dir.resolve()):
            raise ToolError(
                f"Refusing to access '{path}': path escapes the workspace "
                "directory."
            )
        return resolved

    def _read_file(self, path: str) -> str:
        resolved = self._safe_workspace_path(path)
        if not resolved.is_file():
            raise ToolError(f"File not found: '{path}'.")
        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ToolError(f"'{path}' is not a UTF-8 text file.") from None

    def _write_file(self, path: str, content: str) -> str:
        resolved = self._safe_workspace_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Wrote {len(content.encode('utf-8'))} bytes to {path}."

    def _list_files(self, path: str) -> str:
        resolved = self._safe_workspace_path(path)
        if not resolved.is_dir():
            raise ToolError(f"Not a directory: '{path}'.")
        entries = sorted(resolved.iterdir(), key=lambda p: p.name)
        if not entries:
            return "(empty directory)"
        return "\n".join(
            f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries
        )

    def _load_skill(self, name: str) -> str:
        try:
            return load_skill(self.skills, name)
        except SkillNotFoundError as exc:
            raise ToolError(str(exc)) from exc

    def _run_python_script(
        self,
        code: str,
        *,
        libraries: list[str],
        input_files: list[str],
        output_files: list[str],
    ) -> str:
        try:
            result = self.sandbox.run_script(
                code,
                libraries=libraries,
                input_files=input_files,
                output_files=output_files,
            )
        except SandboxError as exc:
            raise ToolError(str(exc)) from exc

        missing = [name for name in output_files if name not in result.output_files]

        lines = [f"Exit code: {result.exit_code}"]
        if result.stdout.strip():
            lines.append(f"stdout:\n{result.stdout.strip()}")
        else:
            lines.append("stdout: (empty)")
        if result.stderr.strip():
            lines.append(f"stderr:\n{result.stderr.strip()}")
        if result.output_files:
            lines.append(f"Output files copied to workspace: {', '.join(result.output_files)}")
        if missing:
            lines.append(
                f"Requested output files NOT produced: {', '.join(missing)}"
            )
        return "\n".join(lines)
