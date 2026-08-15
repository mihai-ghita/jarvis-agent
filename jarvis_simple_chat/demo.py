"""Formatters for the `--demo` glass-box mode.

Pure string formatting only — no I/O, no API calls. Used by `main.py` to show
what actually gets sent to and stored by the Claude API on each turn.
"""

from __future__ import annotations

from typing import Any

_ROLE_WIDTH = 11
_CONTENT_TRUNCATE_LEN = 60
_MARKER_PAD_WIDTH = 40


def _content_text(content: Any) -> str:
    """Best-effort plain-text rendering of a message's `content` field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text is not None:
                parts.append(text)
        return "".join(parts)
    return str(content)


def _truncate(text: str, limit: int = _CONTENT_TRUNCATE_LEN) -> str:
    text = text.replace("\n", " ")
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _format_line(idx: int, role: str, content: Any, marker: str | None = None) -> str:
    text = _truncate(_content_text(content))
    role_field = role.ljust(_ROLE_WIDTH)
    if marker:
        content_field = text.ljust(_MARKER_PAD_WIDTH)
        return f"  [{idx}] {role_field}{content_field}<- {marker}"
    return f"  [{idx}] {role_field}{text}"


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough `chars / 4` approximation — good enough to show cost growth."""
    total_chars = sum(len(_content_text(msg.get("content", ""))) for msg in messages)
    return total_chars // 4


def format_api_call(model: str, max_tokens: int, messages: list[dict[str, Any]]) -> str:
    """Render the outgoing `messages.create` request: model, size, full history."""
    lines = [
        "-- Claude API call --------------------------------",
        "POST /v1/messages",
        f"model:      {model}",
        f"max_tokens: {max_tokens}",
        f"messages:   {len(messages)}  (full history resent every turn)",
        "",
    ]
    last_idx = len(messages) - 1
    for i, msg in enumerate(messages):
        marker = "new this turn" if i == last_idx else None
        lines.append(_format_line(i + 1, msg["role"], msg["content"], marker))
    return "\n".join(lines)


def format_context(history: list[dict[str, Any]]) -> str:
    """Render the stored history after a turn — what the next call will resend."""
    token_estimate = _estimate_tokens(history)
    lines = [
        f"-- Context after this turn ({len(history)} messages, "
        f"~{token_estimate} tokens) --"
    ]
    last_idx = len(history) - 1
    for i, msg in enumerate(history):
        marker = "just appended" if i == last_idx else None
        lines.append(_format_line(i + 1, msg["role"], msg["content"], marker))
    return "\n".join(lines)
