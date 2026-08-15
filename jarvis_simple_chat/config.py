"""Shared settings and environment checks for the simple chat REPL."""

import os
import sys

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 1024
EXIT_COMMANDS = {"exit", "quit"}


def require_api_key() -> str:
    """Validate that ANTHROPIC_API_KEY is set and return it, or exit."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY is not set in the environment "
            "or .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key
