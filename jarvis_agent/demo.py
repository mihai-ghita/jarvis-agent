"""Formatters for the `--demo` glass-box mode.

Pure string formatting only — no I/O, no API calls. Used by `main.py` to
show what the agent is doing at each tool call: which tool, with what
input, and what came back.
"""

from __future__ import annotations

from typing import Any

_VALUE_TRUNCATE_LEN = 200


def _truncate(text: str, limit: int = _VALUE_TRUNCATE_LEN) -> str:
    text = text.replace("\n", " ")
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _format_input(tool_input: dict[str, Any]) -> str:
    """Pretty-print a tool's input dict, one `key: value` line each,
    truncating long values (e.g. `code`, `content`) for readability."""
    if not tool_input:
        return "  (no arguments)"
    lines = []
    for key, value in tool_input.items():
        lines.append(f"  {key}: {_truncate(str(value))}")
    return "\n".join(lines)


def format_tool_call(name: str, tool_input: dict[str, Any]) -> str:
    """Render a tool invocation as a bordered, labeled block."""
    return (
        f"-- Tool call: {name} ----------------------------\n"
        f"{_format_input(tool_input)}"
    )


def format_tool_result(name: str, result: str, is_error: bool) -> str:
    """Render a tool's result (or error) as a bordered, labeled block."""
    label = "ERROR" if is_error else "Result"
    return (
        f"-- Tool {label.lower()}: {name} --------------------\n"
        f"  {_truncate(result)}"
    )


def format_concepts_banner() -> str:
    """A short, colleague-facing explainer of agent/sandbox/skills/MCP.

    Concise by design — meant to be read aloud in under a minute before a
    demo starts.
    """
    return "\n".join(
        [
            "=" * 56,
            "Concepts in this demo",
            "=" * 56,
            "",
            "AGENT  Ask Claude -> get tool calls -> execute them -> feed",
            "       results back -> repeat until a final answer. See",
            "       AgentSession.send in core.py.",
            "",
            "SANDBOX  Every run_python_script call spins up a fresh,",
            "         isolated Docker container. The host workspace is",
            "         never mounted in — files only cross that boundary",
            "         explicitly, by name. See Sandbox.run_script in",
            "         sandbox.py.",
            "",
            "SKILLS  Markdown instruction bundles. Names + one-line",
            "        descriptions are discovered up front and kept in the",
            "        system prompt; full instructions are loaded on demand",
            "        via the load_skill tool. See skills.py and",
            "        skills/pdf_generation/SKILL.md.",
            "",
            "MCP  Model Context Protocol: a standardized way for agents to",
            "     connect to *external* tool servers over a protocol.",
            "     This agent's tools are the opposite — plain Python",
            "     functions wired directly into the loop (tools.py).",
            "     Intentionally no MCP here, to stay minimal and",
            "     dependency-light; MCP is the direction you'd go to add",
            "     tools owned by other systems or teams.",
            "=" * 56,
        ]
    )
