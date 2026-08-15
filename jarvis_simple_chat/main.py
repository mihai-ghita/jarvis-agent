"""Thin REPL: handles stdin/stdout and wires config, client, and session."""

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


def main() -> None:
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

        try:
            reply = session.send(user_input)
        except anthropic.APIError as exc:
            print(f"Error: API request failed: {exc}", file=sys.stderr)
            continue

        print(f"Jarvis: {reply}\n")


if __name__ == "__main__":
    main()
