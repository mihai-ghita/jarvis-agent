# Jarvis Agent

An interactive Python CLI for having a conversation with Claude.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set your Anthropic API key via an environment variable or a `.env` file:

   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

   Or create a `.env` file in the project root:

   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

   If both are set, the environment variable takes precedence.

## Usage

Start an interactive conversation:

```bash
python jarvis.py
```

Type your messages at the `You:` prompt. Claude's replies are printed with full conversation context preserved across turns.

To end the session, type `exit` or `quit`, or press Ctrl-D / Ctrl-C.
