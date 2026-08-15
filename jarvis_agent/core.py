"""Core agent logic: the hand-rolled Claude tool-use loop.

No stdin/stdout here — this module is UI-agnostic and testable in isolation.
`on_tool_call` is the only side-channel, so callers (e.g. `--demo` mode)
decide what to do with each tool invocation.
"""

from __future__ import annotations

from typing import Callable

import anthropic

from jarvis_agent.tools import ToolError, ToolExecutor, TOOL_DEFINITIONS

OnToolCall = Callable[[str, dict, str, bool], None]


class AgentSession:
    """Maintains conversation history and runs the tool-use loop per turn."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        max_tokens: int,
        tool_executor: ToolExecutor,
        system_prompt: str,
        max_steps: int = 10,
        on_tool_call: OnToolCall | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self._tool_executor = tool_executor
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.on_tool_call = on_tool_call
        self.history: list[dict] = []

    def send(self, user_text: str) -> str:
        """Append a user turn, run the tool-use loop, and return the final reply.

        On any exception, history is rolled back to exactly what it was
        before this call (mirroring `ChatSession.send`'s rollback, but
        covering the tool-result messages appended across loop iterations
        too).
        """
        history_len_before = len(self.history)
        self.history.append({"role": "user", "content": user_text})

        try:
            for _ in range(self.max_steps):
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=TOOL_DEFINITIONS,
                    messages=self.history,
                )
                self.history.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    return self._extract_text(response)

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    result_text, is_error = self._execute_tool(block.name, block.input)
                    if self.on_tool_call is not None:
                        self.on_tool_call(block.name, block.input, result_text, is_error)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                            "is_error": is_error,
                        }
                    )
                self.history.append({"role": "user", "content": tool_results})
        except Exception:
            del self.history[history_len_before:]
            raise

        del self.history[history_len_before:]
        raise RuntimeError(
            f"Agent exceeded the maximum of {self.max_steps} tool-use steps "
            "without finishing."
        )

    def _execute_tool(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Run one tool call, converting any failure into an error result.

        Never raises — a tool/sandbox bug shouldn't crash the agent loop;
        Claude sees the error and can react to it instead.
        """
        try:
            return self._tool_executor.execute(name, tool_input), False
        except ToolError as exc:
            return str(exc), True
        except Exception as exc:
            return f"Unexpected error running tool '{name}': {exc}", True

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        """Join all text blocks in the response content, in order.

        Raises a `ValueError` if the response contains no text blocks.
        """
        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise ValueError("API response contained no text content blocks")
        return "".join(text_blocks)
