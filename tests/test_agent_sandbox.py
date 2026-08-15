import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis_agent.sandbox import ScriptResult, Sandbox, SandboxError


class FakeSandboxSession:
    """Stands in for `llm_sandbox.SandboxSession`'s context-manager API.

    Instances are callable (mimicking the `SandboxSession(...)` constructor
    call) and return themselves, so the same object can both record the
    kwargs it was constructed with and the calls made against it while
    acting as `session` in `with SandboxSession(...) as session:`.
    """

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        missing_outputs=None,
        enter_error: Exception | None = None,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.missing_outputs = set(missing_outputs or [])
        self.enter_error = enter_error
        self.call_kwargs = None
        self.copy_to_calls: list[tuple[str, str]] = []
        self.copy_from_calls: list[tuple[str, str]] = []
        self.run_calls: list[dict] = []

    def __call__(self, **kwargs):
        self.call_kwargs = kwargs
        return self

    def __enter__(self):
        if self.enter_error is not None:
            raise self.enter_error
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def copy_to_runtime(self, src: str, dest: str) -> None:
        self.copy_to_calls.append((src, dest))

    def run(self, code: str, libraries=None):
        self.run_calls.append({"code": code, "libraries": libraries})
        return SimpleNamespace(stdout=self.stdout, stderr=self.stderr, exit_code=self.exit_code)

    def copy_from_runtime(self, src: str, dest: str) -> None:
        filename = src.rsplit("/", 1)[-1]
        if filename in self.missing_outputs:
            raise FileNotFoundError(f"{src} does not exist in the container")
        self.copy_from_calls.append((src, dest))


class SandboxRunScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace_dir = Path(self._tmpdir.name)
        (self.workspace_dir / "input.csv").write_text("a,b\n1,2\n")

    def test_run_script_copies_files_runs_code_and_returns_script_result(self) -> None:
        fake_session = FakeSandboxSession(stdout="hello\n", stderr="", exit_code=0)
        with patch("jarvis_agent.sandbox.SandboxSession", fake_session):
            sandbox = Sandbox(
                self.workspace_dir, image="python:3.11-slim", lang="python", workdir="/sandbox"
            )
            result = sandbox.run_script(
                "print('hello')",
                libraries=["reportlab"],
                input_files=["input.csv"],
                output_files=["output.pdf"],
            )

        self.assertEqual(fake_session.call_kwargs["lang"], "python")
        self.assertEqual(fake_session.call_kwargs["image"], "python:3.11-slim")

        self.assertEqual(len(fake_session.copy_to_calls), 1)
        host_path, container_path = fake_session.copy_to_calls[0]
        self.assertEqual(host_path, str((self.workspace_dir / "input.csv").resolve()))
        self.assertEqual(container_path, "/sandbox/input.csv")

        self.assertEqual(len(fake_session.run_calls), 1)
        self.assertEqual(fake_session.run_calls[0]["code"], "print('hello')")
        self.assertEqual(fake_session.run_calls[0]["libraries"], ["reportlab"])

        self.assertEqual(len(fake_session.copy_from_calls), 1)
        src, dest = fake_session.copy_from_calls[0]
        self.assertEqual(src, "/sandbox/output.pdf")
        self.assertEqual(dest, str((self.workspace_dir / "output.pdf").resolve()))

        self.assertIsInstance(result, ScriptResult)
        self.assertEqual(result.stdout, "hello\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output_files, ["output.pdf"])

    def test_run_script_omits_output_files_the_script_did_not_produce(self) -> None:
        fake_session = FakeSandboxSession(
            stdout="done", stderr="", exit_code=0, missing_outputs={"missing.pdf"}
        )
        with patch("jarvis_agent.sandbox.SandboxSession", fake_session):
            sandbox = Sandbox(self.workspace_dir)
            result = sandbox.run_script(
                "print('done')",
                output_files=["missing.pdf", "present.txt"],
            )

        self.assertEqual(result.output_files, ["present.txt"])
        self.assertEqual(result.stdout, "done")
        self.assertEqual(result.exit_code, 0)

    def test_run_script_raises_sandbox_error_mentioning_docker_when_session_fails(self) -> None:
        fake_session = FakeSandboxSession(enter_error=ConnectionRefusedError("docker daemon down"))
        with patch("jarvis_agent.sandbox.SandboxSession", fake_session):
            sandbox = Sandbox(self.workspace_dir)
            with self.assertRaises(SandboxError) as cm:
                sandbox.run_script("print(1)")

        self.assertIn("Docker", str(cm.exception))


class SandboxSafePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace_dir = Path(self._tmpdir.name)
        self.sandbox = Sandbox(self.workspace_dir)

    def test_rejects_path_that_escapes_workspace(self) -> None:
        with self.assertRaises(SandboxError):
            self.sandbox._safe_path("../../etc/passwd")

    def test_accepts_normal_relative_filename(self) -> None:
        resolved = self.sandbox._safe_path("output.txt")
        self.assertEqual(resolved, (self.workspace_dir / "output.txt").resolve())


if __name__ == "__main__":
    unittest.main()
