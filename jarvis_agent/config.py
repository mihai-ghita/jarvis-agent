"""Shared settings and environment checks for the Jarvis agent."""

import os
import sys
from pathlib import Path

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2048
MAX_AGENT_STEPS = 10
EXIT_COMMANDS = {"exit", "quit"}

WORKSPACE_DIR = Path(__file__).resolve().parent / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

SANDBOX_IMAGE = "python:3.11-slim"
SANDBOX_LANG = "python"
SANDBOX_WORKDIR = "/sandbox"


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
