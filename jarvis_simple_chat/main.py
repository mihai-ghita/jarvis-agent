"""Thin REPL: handles stdin/stdout and wires config, client, and session."""

import argparse
import sys

import anthropic
from dotenv import load_dotenv

from jarvis_simple_chat.config import (
    EXIT_COMMANDS,
    MAX_TOKENS,
    MODEL,
    require_api_key,
)
from jarvis_simple_chat.core import ChatSession
from jarvis_simple_chat.demo import format_api_call, format_context

_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _colorize(text: str) -> str:
    """Wrap `text` in yellow ANSI codes, unless stdout isn't a terminal."""
    if not sys.stdout.isatty():
        return text
    return f"{_YELLOW}{text}{_RESET}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive command-line chat with Claude.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Glass-box mode: after each turn, print the outgoing Claude API "
            "call and the resulting conversation context. Useful for "
            "presentations."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    load_dotenv()
    require_api_key()

    client = anthropic.Anthropic()
    session = ChatSession(client, model=MODEL, max_tokens=MAX_TOKENS)

    print("Jarvis — type 'exit' or 'quit' to end the conversation.\n")

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

        if args.demo:
            print("Calling Claude...\n")

        try:
            reply = session.send(user_input)
        except anthropic.APIError as exc:
            print(f"Error: API request failed: {exc}", file=sys.stderr)
            continue

        if args.demo:
            # `send()` already appended both turns; drop the assistant reply
            # to reconstruct what was actually sent on the wire.
            print(format_api_call(session.model, session.max_tokens, session.history[:-1]))
            print()

        print(_colorize(f"Jarvis: {reply}") + "\n")

        if args.demo:
            print(format_context(session.history))
            print()


if __name__ == "__main__":
    main()
