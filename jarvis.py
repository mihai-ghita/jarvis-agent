#!/usr/bin/env python3
"""Interactive conversation with Claude."""

import os
import sys

import anthropic
from dotenv import load_dotenv

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 1024
EXIT_COMMANDS = {"exit", "quit"}


def main() -> None:
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY is not set in the environment "
            "or .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic()
    messages: list[dict[str, str]] = []

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

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            print(f"Error: API request failed: {exc}", file=sys.stderr)
            messages.pop()
            continue

        reply = response.content[0].text
        print(f"Claude: {reply}\n")
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
