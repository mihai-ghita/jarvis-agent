import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jarvis_agent.skills import Skill
from jarvis_agent.tools import TOOL_DEFINITIONS, ToolError, ToolExecutor


class FakeSandbox:
    """Stands in for `Sandbox`, returning a canned result or raising."""

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.result = result
        self.error = error

    def run_script(self, code, *, libraries=None, input_files=None, output_files=None):
        self.calls.append(
            {
                "code": code,
                "libraries": libraries,
                "input_files": input_files,
                "output_files": output_files,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


def _fake_script_result(stdout="", stderr="", exit_code=0, output_files=None):
    return SimpleNamespace(
        stdout=stdout, stderr=stderr, exit_code=exit_code, output_files=output_files or []
    )


class ToolExecutorFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace_dir = Path(self._tmpdir.name)
        self.skills = {
            "pdf-generation": Skill(
                name="pdf-generation", description="Make PDFs.", instructions="pdf instructions"
            ),
            "csv-analysis": Skill(
                name="csv-analysis", description="Analyze CSVs.", instructions="csv instructions"
            ),
        }
        self.executor = ToolExecutor(self.workspace_dir, FakeSandbox(), self.skills)

    def test_write_then_read_round_trip(self) -> None:
        self.executor.execute("write_file", {"path": "notes.txt", "content": "hello world"})
        content = self.executor.execute("read_file", {"path": "notes.txt"})
        self.assertEqual(content, "hello world")

    def test_list_files_reports_empty_directory(self) -> None:
        result = self.executor.execute("list_files", {"path": "."})
        self.assertEqual(result, "(empty directory)")

    def test_list_files_suffixes_directories_with_slash(self) -> None:
        (self.workspace_dir / "subdir").mkdir()
        (self.workspace_dir / "file.txt").write_text("x")

        result = self.executor.execute("list_files", {"path": "."})

        self.assertIn("subdir/", result.splitlines())
        self.assertIn("file.txt", result.splitlines())

    def test_read_nonexistent_file_raises_informative_tool_error(self) -> None:
        with self.assertRaises(ToolError) as cm:
            self.executor.execute("read_file", {"path": "missing.txt"})
        self.assertIn("missing.txt", str(cm.exception))

    def test_write_file_creates_missing_parent_directories(self) -> None:
        self.executor.execute("write_file", {"path": "a/b/c.txt", "content": "deep"})
        self.assertEqual((self.workspace_dir / "a" / "b" / "c.txt").read_text(), "deep")

    def test_read_file_path_traversal_rejected(self) -> None:
        with self.assertRaises(ToolError):
            self.executor.execute("read_file", {"path": "../outside.txt"})

    def test_write_file_path_traversal_rejected(self) -> None:
        with self.assertRaises(ToolError):
            self.executor.execute("write_file", {"path": "../outside.txt", "content": "x"})

    def test_list_files_path_traversal_rejected(self) -> None:
        with self.assertRaises(ToolError):
            self.executor.execute("list_files", {"path": "../"})


class ToolExecutorLoadSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace_dir = Path(self._tmpdir.name)
        self.skills = {
            "pdf-generation": Skill(
                name="pdf-generation", description="Make PDFs.", instructions="pdf instructions"
            ),
        }
        self.executor = ToolExecutor(self.workspace_dir, FakeSandbox(), self.skills)

    def test_load_skill_delegates_to_skills_registry(self) -> None:
        result = self.executor.execute("load_skill", {"name": "pdf-generation"})
        self.assertEqual(result, "pdf instructions")

    def test_load_skill_unknown_name_raises_tool_error_not_skill_not_found_error(self) -> None:
        with self.assertRaises(ToolError) as cm:
            self.executor.execute("load_skill", {"name": "does-not-exist"})
        # Confirm SkillNotFoundError was translated into ToolError, not re-raised as-is.
        self.assertIs(type(cm.exception), ToolError)


class ToolExecutorRunPythonScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace_dir = Path(self._tmpdir.name)

    def test_delegates_to_sandbox_with_expected_args(self) -> None:
        sandbox = FakeSandbox(
            result=_fake_script_result(stdout="hi", exit_code=0, output_files=["out.pdf"])
        )
        executor = ToolExecutor(self.workspace_dir, sandbox, {})

        executor.execute(
            "run_python_script",
            {
                "code": "print('hi')",
                "libraries": ["reportlab"],
                "input_files": ["in.csv"],
                "output_files": ["out.pdf"],
            },
        )

        self.assertEqual(len(sandbox.calls), 1)
        call = sandbox.calls[0]
        self.assertEqual(call["code"], "print('hi')")
        self.assertEqual(call["libraries"], ["reportlab"])
        self.assertEqual(call["input_files"], ["in.csv"])
        self.assertEqual(call["output_files"], ["out.pdf"])

    def test_missing_optional_args_default_to_empty_lists(self) -> None:
        sandbox = FakeSandbox(result=_fake_script_result(stdout="", exit_code=0, output_files=[]))
        executor = ToolExecutor(self.workspace_dir, sandbox, {})

        executor.execute("run_python_script", {"code": "print(1)"})

        call = sandbox.calls[0]
        self.assertEqual(call["libraries"], [])
        self.assertEqual(call["input_files"], [])
        self.assertEqual(call["output_files"], [])

    def test_result_mentions_exit_code_stdout_and_missing_output_files(self) -> None:
        sandbox = FakeSandbox(
            result=_fake_script_result(stdout="partial output", exit_code=1, output_files=["produced.txt"])
        )
        executor = ToolExecutor(self.workspace_dir, sandbox, {})

        result = executor.execute(
            "run_python_script",
            {"code": "print(1)", "output_files": ["produced.txt", "never_made.pdf"]},
        )

        self.assertIn("Exit code: 1", result)
        self.assertIn("partial output", result)
        self.assertIn("NOT produced", result)
        self.assertIn("never_made.pdf", result)


class ToolExecutorDispatchTests(unittest.TestCase):
    def test_unrecognized_tool_name_raises_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), FakeSandbox(), {})
            with self.assertRaises(ToolError):
                executor.execute("delete_everything", {})


class ToolDefinitionsSanityTests(unittest.TestCase):
    def test_definitions_list_has_five_entries_with_expected_names(self) -> None:
        self.assertIsInstance(TOOL_DEFINITIONS, list)
        self.assertEqual(len(TOOL_DEFINITIONS), 5)
        names = {tool["name"] for tool in TOOL_DEFINITIONS}
        self.assertEqual(
            names,
            {"read_file", "write_file", "list_files", "load_skill", "run_python_script"},
        )


if __name__ == "__main__":
    unittest.main()
