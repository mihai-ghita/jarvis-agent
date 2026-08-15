import unittest
from types import SimpleNamespace

import anthropic
import httpx

from jarvis_agent.core import AgentSession
from jarvis_agent.tools import ToolError


class FakeMessages:
    """Stands in for `client.messages`.

    Returns responses one at a time from `responses` (a list, popped in
    order) if given, otherwise the same `response` on every call. Raises
    `error` instead, if given.
    """

    def __init__(self, responses=None, response=None, error: Exception | None = None) -> None:
        self.responses = list(responses) if responses is not None else None
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.responses is not None:
            return self.responses.pop(0)
        return self.response


class FakeClient:
    def __init__(self, responses=None, response=None, error: Exception | None = None) -> None:
        self.messages = FakeMessages(responses=responses, response=response, error=error)


class FakeToolExecutor:
    """Stands in for `ToolExecutor`; `core.py` only needs `.execute()`.

    `side_effect(name, tool_input)` returns either a result string or an
    exception instance to be raised (so tests can simulate `ToolError` or
    arbitrary bugs without a real `ToolExecutor`).
    """

    def __init__(self, side_effect=None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._side_effect = side_effect or (lambda name, tool_input: "ok")

    def execute(self, name: str, tool_input: dict) -> str:
        self.calls.append((name, tool_input))
        result = self._side_effect(name, tool_input)
        if isinstance(result, BaseException):
            raise result
        return result


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_: str, name: str, input_: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _response(content: list, stop_reason: str) -> SimpleNamespace:
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def _make_api_error(message: str = "boom") -> anthropic.APIError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIError(message, request, body=None)


def _make_session(client, tool_executor, **kwargs) -> AgentSession:
    return AgentSession(
        client,
        model="test-model",
        max_tokens=10,
        tool_executor=tool_executor,
        system_prompt="You are a test agent.",
        **kwargs,
    )


class AgentSessionToolLoopTests(unittest.TestCase):
    def test_send_executes_tool_call_and_returns_final_text(self) -> None:
        tool_block = _tool_use_block("toolu_1", "run_python_script", {"code": "print(1)"})
        first = _response([tool_block], "tool_use")
        final_text_block = _text_block("All done.")
        second = _response([final_text_block], "end_turn")
        client = FakeClient(responses=[first, second])
        tool_executor = FakeToolExecutor(lambda name, tool_input: "tool ran fine")
        session = _make_session(client, tool_executor)

        reply = session.send("Please run a script")

        self.assertEqual(reply, "All done.")
        self.assertEqual(tool_executor.calls, [("run_python_script", {"code": "print(1)"})])

        self.assertEqual(len(session.history), 4)
        self.assertEqual(session.history[0], {"role": "user", "content": "Please run a script"})
        self.assertEqual(session.history[1], {"role": "assistant", "content": [tool_block]})

        self.assertEqual(session.history[2]["role"], "user")
        self.assertEqual(len(session.history[2]["content"]), 1)
        tool_result = session.history[2]["content"][0]
        self.assertEqual(tool_result["type"], "tool_result")
        self.assertEqual(tool_result["tool_use_id"], "toolu_1")
        self.assertEqual(tool_result["content"], "tool ran fine")
        self.assertFalse(tool_result["is_error"])

        self.assertEqual(session.history[3], {"role": "assistant", "content": [final_text_block]})

    def test_send_converts_tool_error_to_is_error_result_and_continues(self) -> None:
        tool_block = _tool_use_block("toolu_1", "read_file", {"path": "missing.txt"})
        first = _response([tool_block], "tool_use")
        second = _response([_text_block("Sorry, could not read that.")], "end_turn")
        client = FakeClient(responses=[first, second])
        tool_executor = FakeToolExecutor(
            lambda name, tool_input: ToolError("File not found: 'missing.txt'.")
        )
        session = _make_session(client, tool_executor)

        reply = session.send("read missing.txt")

        self.assertEqual(reply, "Sorry, could not read that.")
        tool_result = session.history[2]["content"][0]
        self.assertTrue(tool_result["is_error"])
        self.assertEqual(tool_result["content"], "File not found: 'missing.txt'.")

    def test_send_converts_arbitrary_tool_exception_to_is_error_result(self) -> None:
        tool_block = _tool_use_block("toolu_1", "run_python_script", {"code": "boom"})
        first = _response([tool_block], "tool_use")
        second = _response([_text_block("Recovered.")], "end_turn")
        client = FakeClient(responses=[first, second])
        tool_executor = FakeToolExecutor(lambda name, tool_input: RuntimeError("unexpected bug"))
        session = _make_session(client, tool_executor)

        reply = session.send("run something")

        self.assertEqual(reply, "Recovered.")
        tool_result = session.history[2]["content"][0]
        self.assertTrue(tool_result["is_error"])
        self.assertIn("unexpected bug", tool_result["content"])

    def test_on_tool_call_callback_invoked_once_per_executed_tool(self) -> None:
        tool_block = _tool_use_block("toolu_1", "read_file", {"path": "a.txt"})
        first = _response([tool_block], "tool_use")
        second = _response([_text_block("done")], "end_turn")
        client = FakeClient(responses=[first, second])
        tool_executor = FakeToolExecutor(lambda name, tool_input: "file contents")
        recorded_calls: list[tuple] = []
        session = _make_session(
            client,
            tool_executor,
            on_tool_call=lambda name, tool_input, result, is_error: recorded_calls.append(
                (name, tool_input, result, is_error)
            ),
        )

        session.send("read a.txt")

        self.assertEqual(
            recorded_calls, [("read_file", {"path": "a.txt"}, "file contents", False)]
        )


class AgentSessionMaxStepsTests(unittest.TestCase):
    def test_send_raises_runtime_error_after_max_steps_and_rolls_back_history(self) -> None:
        tool_block = _tool_use_block("toolu_1", "run_python_script", {"code": "loop forever"})
        response = _response([tool_block], "tool_use")
        client = FakeClient(response=response)
        tool_executor = FakeToolExecutor(lambda name, tool_input: "ran")
        session = _make_session(client, tool_executor, max_steps=3)

        with self.assertRaises(RuntimeError):
            session.send("keep going")

        self.assertEqual(len(client.messages.calls), 3)
        self.assertEqual(session.history, [])


class AgentSessionApiErrorTests(unittest.TestCase):
    def test_send_rolls_back_history_to_pre_send_state_on_api_error(self) -> None:
        client = FakeClient(error=_make_api_error("service unavailable"))
        tool_executor = FakeToolExecutor(lambda name, tool_input: "ran")
        session = _make_session(client, tool_executor)
        session.history.append({"role": "user", "content": "earlier turn"})
        session.history.append({"role": "assistant", "content": "earlier reply"})
        history_before = list(session.history)

        with self.assertRaises(anthropic.APIError):
            session.send("Hi")

        self.assertEqual(session.history, history_before)


class AgentSessionExtractTextTests(unittest.TestCase):
    def test_final_response_ignores_non_text_blocks_when_extracting_text(self) -> None:
        stray_tool_block = _tool_use_block("toolu_2", "some_tool", {})
        response = _response([stray_tool_block, _text_block("final answer")], "end_turn")
        client = FakeClient(response=response)
        tool_executor = FakeToolExecutor(lambda name, tool_input: "unused")
        session = _make_session(client, tool_executor)

        reply = session.send("hi")

        self.assertEqual(reply, "final answer")

    def test_final_response_with_no_text_blocks_raises_value_error(self) -> None:
        response = _response([], "end_turn")
        client = FakeClient(response=response)
        tool_executor = FakeToolExecutor(lambda name, tool_input: "unused")
        session = _make_session(client, tool_executor)

        with self.assertRaises(ValueError):
            session.send("hi")

        self.assertEqual(session.history, [])


if __name__ == "__main__":
    unittest.main()
