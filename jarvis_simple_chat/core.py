"""Core chat logic: conversation history and Claude API calls.

No stdin/stdout here — this module is UI-agnostic and testable in isolation.
"""

import anthropic


class ChatSession:
    """Maintains conversation history and sends turns to an Anthropic
    client."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        max_tokens: int,
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.history: list[anthropic.types.MessageParam] = []

    def send(self, user_text: str) -> str:
        """Append a user turn, call the API, and return the assistant's reply.

        On `anthropic.APIError`, the unanswered user turn is rolled back
        from history before the exception is re-raised.
        """
        self.history.append({"role": "user", "content": user_text})

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=self.history,
            )
        except anthropic.APIError:
            self.history.pop()
            raise

        reply = self._extract_text(response)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        """Join all text blocks in the response content, in order.

        Raises a `ValueError` if the response contains no text blocks.
        """
        text_blocks = [
            block.text
            for block in response.content
            if block.type == "text"
        ]
        if not text_blocks:
            raise ValueError("API response contained no text content blocks")
        return "".join(text_blocks)
