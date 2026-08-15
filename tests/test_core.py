import unittest
from types import SimpleNamespace

import anthropic
import httpx

from jarvis_simple_chat.core import ChatSession


class FakeMessages:
    """Stands in for `client.messages`, returning a canned response or raising."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.messages = FakeMessages(response=response, error=error)


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _make_api_error(message: str = "boom") -> anthropic.APIError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIError(message, request, body=None)


class ChatSessionTests(unittest.TestCase):
    def test_send_updates_history_on_success(self) -> None:
        response = SimpleNamespace(content=[_text_block("Hello there")])
        client = FakeClient(response=response)
        session = ChatSession(client, model="test-model", max_tokens=10)

        reply = session.send("Hi")

        self.assertEqual(reply, "Hello there")
        self.assertEqual(
            session.history,
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello there"},
            ],
        )

    def test_send_rolls_back_user_turn_on_api_error(self) -> None:
        client = FakeClient(error=_make_api_error("service unavailable"))
        session = ChatSession(client, model="test-model", max_tokens=10)

        with self.assertRaises(anthropic.APIError):
            session.send("Hi")

        self.assertEqual(session.history, [])

    def test_send_extracts_text_blocks_not_first_block(self) -> None:
        non_text_block = SimpleNamespace(type="tool_use", input={"x": 1})
        response = SimpleNamespace(
            content=[non_text_block, _text_block("real reply")]
        )
        client = FakeClient(response=response)
        session = ChatSession(client, model="test-model", max_tokens=10)

        reply = session.send("Hi")

        self.assertEqual(reply, "real reply")

    def test_send_joins_multiple_text_blocks(self) -> None:
        response = SimpleNamespace(
            content=[_text_block("part one. "), _text_block("part two.")]
        )
        client = FakeClient(response=response)
        session = ChatSession(client, model="test-model", max_tokens=10)

        reply = session.send("Hi")

        self.assertEqual(reply, "part one. part two.")

    def test_send_raises_on_no_text_blocks(self) -> None:
        non_text_block = SimpleNamespace(type="tool_use", input={"x": 1})
        response = SimpleNamespace(content=[non_text_block])
        client = FakeClient(response=response)
        session = ChatSession(client, model="test-model", max_tokens=10)

        with self.assertRaises(ValueError):
            session.send("Hi")


if __name__ == "__main__":
    unittest.main()
