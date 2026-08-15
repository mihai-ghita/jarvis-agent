import unittest

from jarvis_agent.demo import format_concepts_banner, format_tool_call, format_tool_result


class FormatToolCallTests(unittest.TestCase):
    def test_output_is_nonempty_and_mentions_tool_name(self) -> None:
        output = format_tool_call("run_python_script", {"code": "print(1)"})
        self.assertTrue(output.strip())
        self.assertIn("run_python_script", output)

    def test_no_arguments_still_produces_readable_output(self) -> None:
        output = format_tool_call("list_files", {})
        self.assertTrue(output.strip())
        self.assertIn("list_files", output)

    def test_long_input_values_are_truncated(self) -> None:
        long_code = "x = 1\n" * 60  # well over 300 chars
        output = format_tool_call("run_python_script", {"code": long_code})

        self.assertIn("run_python_script", output)
        self.assertLess(len(output), len(long_code))
        self.assertIn("…", output)


class FormatToolResultTests(unittest.TestCase):
    def test_output_is_nonempty_and_mentions_tool_name(self) -> None:
        output = format_tool_result("read_file", "file contents here", is_error=False)
        self.assertTrue(output.strip())
        self.assertIn("read_file", output)

    def test_error_results_are_visually_distinguishable_from_success(self) -> None:
        success_output = format_tool_result("read_file", "contents", is_error=False)
        error_output = format_tool_result("read_file", "boom, it failed", is_error=True)

        self.assertNotIn("error", success_output.lower())
        self.assertIn("error", error_output.lower())

    def test_long_result_text_is_truncated(self) -> None:
        long_result = "y" * 500
        output = format_tool_result("read_file", long_result, is_error=False)

        self.assertLess(len(output), len(long_result))
        self.assertIn("…", output)


class FormatConceptsBannerTests(unittest.TestCase):
    def test_mentions_all_four_core_concepts(self) -> None:
        banner = format_concepts_banner().lower()

        self.assertIn("agent", banner)
        self.assertIn("sandbox", banner)
        self.assertIn("skill", banner)
        self.assertTrue(
            "mcp" in banner or "model context protocol" in banner,
            "banner should mention MCP or Model Context Protocol",
        )


if __name__ == "__main__":
    unittest.main()
