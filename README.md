# Jarvis Agent

An interactive command-line chat with Claude.

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

Start the chat:

```bash
python -m jarvis_simple_chat
```

Or, equivalently, using the root-level script:

```bash
python jarvis-simple-chat.py
```

Type your message at the `You:` prompt and press Enter to send. Claude's reply is printed after a `Claude:` prefix. Conversation context is preserved across turns.

### Controls

- **Enter** — send your message
- **`exit` or `quit`** — end the session
- **Ctrl+C** — end the session

If `ANTHROPIC_API_KEY` is missing, the program prints an error and exits immediately.

### Demo mode

For presentations or teaching how a chat with an LLM actually works, run with `--demo`:

```bash
python -m jarvis_simple_chat --demo
```

After every reply, this prints two extra panels:

- **Claude API call** — the exact request about to be sent, including the full conversation history resent on every turn (the API itself is stateless).
- **Context after this turn** — the updated history, with the just-appended message flagged, plus a rough token estimate (`chars / 4`).

This makes it visible that "memory" in a chat is just the client resending the whole conversation each time, and that the assistant's own replies become part of the context for the next call.

## Tests

Run the unit tests with:

```bash
python -m unittest discover -s tests
```
