# Jarvis Agent

An interactive Python TUI for having a conversation with Claude.

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

Start the chat TUI:

```bash
python jarvis.py
```

The app opens a scrollable chat view with an input bar at the bottom. Type your message and press Enter to send. Claude's replies stream in token-by-token and are rendered as Markdown. Conversation context is preserved across turns.

### Controls

- **Enter** — send your message
- **Scroll** — use the mouse wheel or keyboard to browse chat history
- **`exit` or `quit`** — end the session
- **Ctrl+Q** — quit the app
- **Ctrl+C** — quit the app

If `ANTHROPIC_API_KEY` is missing, the app still opens and shows an error in the chat log instead of starting a conversation.
