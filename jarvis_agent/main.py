"""Thin REPL: handles stdin/stdout and wires config, client, and session."""

import argparse
import sys

import anthropic
from dotenv import load_dotenv

from jarvis_agent.config import (
    EXIT_COMMANDS,
    MAX_AGENT_STEPS,
    MAX_TOKENS,
    MODEL,
    SKILLS_DIR,
    WORKSPACE_DIR,
    require_api_key,
)
from jarvis_agent.core import AgentSession
from jarvis_agent.demo import format_concepts_banner, format_tool_call, format_tool_result
from jarvis_agent.sandbox import Sandbox
from jarvis_agent.skills import Skill, discover_skills, format_skills_catalog
from jarvis_agent.tools import ToolExecutor

_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _colorize(text: str) -> str:
    """Wrap `text` in yellow ANSI codes, unless stdout isn't a terminal."""
    if not sys.stdout.isatty():
        return text
    return f"{_YELLOW}{text}{_RESET}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive command-line agent with a file workspace and a Docker sandbox.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Glass-box mode: print each tool call, its sandbox/skill "
            "execution, and its result as the agent works. Useful for "
            "presentations."
        ),
    )
    return parser.parse_args(argv)


def _build_system_prompt(skills: dict[str, Skill]) -> str:
    return (
        "You are Jarvis, an agent that can read and write files in your "
        "workspace and generate and execute Python scripts inside an "
        "isolated Docker sandbox. You are currently used to generate PDFs.\n\n"
        f"Your workspace directory is: {WORKSPACE_DIR}\n\n"
        "Available skills (call `load_skill` to get full instructions "
        "before using one):\n"
        f"{format_skills_catalog(skills)}"
    )


def main() -> None:
    args = parse_args()

    load_dotenv()
    require_api_key()

    if args.demo:
        print(format_concepts_banner())
        print()

    client = anthropic.Anthropic()
    skills = discover_skills(SKILLS_DIR)
    sandbox = Sandbox(WORKSPACE_DIR)
    tool_executor = ToolExecutor(WORKSPACE_DIR, sandbox, skills)

    on_tool_call = None
    if args.demo:

        def on_tool_call(name, tool_input, result_text, is_error):
            print(format_tool_call(name, tool_input))
            print(format_tool_result(name, result_text, is_error))
            print()

    session = AgentSession(
        client,
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tool_executor=tool_executor,
        system_prompt=_build_system_prompt(skills),
        max_steps=MAX_AGENT_STEPS,
        on_tool_call=on_tool_call,
    )

    print(f"Jarvis — workspace: {WORKSPACE_DIR}")
    print("Type 'exit' or 'quit' to end the conversation.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.lower() in EXIT_COMMANDS:
            break

        try:
            reply = session.send(user_input)
        except anthropic.APIError as exc:
            print(f"Error: API request failed: {exc}", file=sys.stderr)
            continue
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue

        print(_colorize(f"Jarvis: {reply}") + "\n")


if __name__ == "__main__":
    main()
