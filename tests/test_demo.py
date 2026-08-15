import unittest

from jarvis_simple_chat.demo import format_api_call, format_context


class FormatApiCallTests(unittest.TestCase):
    def test_header_reports_model_size_and_count(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        output = format_api_call("test-model", 10, messages)
        lines = output.splitlines()

        self.assertEqual(lines[0], "-- Claude API call --------------------------------")
        self.assertEqual(lines[1], "POST /v1/messages")
        self.assertEqual(lines[2], "model:      test-model")
        self.assertEqual(lines[3], "max_tokens: 10")
        self.assertEqual(
            lines[4], "messages:   1  (full history resent every turn)"
        )
        self.assertEqual(lines[5], "")

    def test_last_message_marked_as_new_this_turn(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
            {"role": "user", "content": "what did I just say?"},
        ]
        output = format_api_call("test-model", 10, messages)
        message_lines = output.splitlines()[6:]

        self.assertEqual(len(message_lines), 3)
        self.assertNotIn("<-", message_lines[0])
        self.assertNotIn("<-", message_lines[1])
        self.assertTrue(message_lines[2].endswith("<- new this turn"))

        self.assertIn("[1]", message_lines[0])
        self.assertIn("user", message_lines[0])
        self.assertIn("Hello", message_lines[0])
        self.assertIn("[2]", message_lines[1])
        self.assertIn("assistant", message_lines[1])
        self.assertIn("[3]", message_lines[2])

    def test_single_new_turn_is_marked_even_alone(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        output = format_api_call("test-model", 10, messages)
        message_line = output.splitlines()[6]

        self.assertTrue(message_line.endswith("<- new this turn"))


class FormatContextTests(unittest.TestCase):
    def test_empty_history_reports_zero_messages_and_tokens(self) -> None:
        output = format_context([])
        self.assertEqual(
            output, "-- Context after this turn (0 messages, ~0 tokens) --"
        )

    def test_reports_message_count_and_token_estimate(self) -> None:
        # 5 + 8 = 13 chars -> 13 // 4 == 3 (chars/4 approximation)
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        output = format_context(history)
        header = output.splitlines()[0]

        self.assertEqual(
            header, "-- Context after this turn (2 messages, ~3 tokens) --"
        )

    def test_last_message_marked_as_just_appended(self) -> None:
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        output = format_context(history)
        message_lines = output.splitlines()[1:]

        self.assertNotIn("<-", message_lines[0])
        self.assertTrue(message_lines[1].endswith("<- just appended"))


class TruncationTests(unittest.TestCase):
    def test_long_content_is_truncated_with_ellipsis(self) -> None:
        long_content = "x" * 100
        history = [{"role": "user", "content": long_content}]
        output = format_context(history)
        message_line = output.splitlines()[1]

        self.assertIn("…", message_line)
        self.assertNotIn("x" * 100, message_line)

    def test_newlines_in_content_are_flattened(self) -> None:
        history = [{"role": "user", "content": "line one\nline two"}]
        output = format_context(history)
        message_line = output.splitlines()[1]

        self.assertNotIn("\n", message_line)
        self.assertIn("line one line two", message_line)


if __name__ == "__main__":
    unittest.main()
