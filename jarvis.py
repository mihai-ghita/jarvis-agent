import os
import time
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Markdown, Rule, Static

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 1024
EXIT_COMMANDS = {"exit", "quit"}
THINKING_PLACEHOLDER = "Thinking..."
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class JarvisApp(App):
    CSS_PATH = "jarvis.tcss"
    ENABLE_COMMAND_PALETTE = False
    ESCAPE_TO_MINIMIZE = False

    status_text = reactive("OFFLINE")
    message_count = reactive(0)

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("J.A.R.V.I.S.", id="title-wordmark"),
            Static("Just A Rather Very Intelligent System", id="title-tagline"),
            Rule(classes="title-rule"),
            id="title-bar",
        )
        yield Horizontal(
            Vertical(
                Static("● OFFLINE", id="status-line", classes="sidebar-value status-offline"),
                Rule(classes="sidebar-rule"),
                Static("Model", classes="sidebar-label"),
                Static(MODEL, id="model-line", classes="sidebar-value"),
                Rule(classes="sidebar-rule"),
                Static("Messages", classes="sidebar-label"),
                Static("0", id="message-count-line", classes="sidebar-value"),
                Rule(classes="sidebar-rule"),
                Static("Session", classes="sidebar-label"),
                Static("00:00", id="session-clock", classes="sidebar-value"),
                id="sidebar",
            ),
            Vertical(
                VerticalScroll(id="chat-log"),
                Input(placeholder="Message Jarvis...", id="chat-input"),
                id="chat-panel",
            ),
            id="body",
        )

    def on_mount(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.client: anthropic.Anthropic | None = None
        self._streaming = False
        self._session_start = time.time()
        self._spinner_frame = 0
        self._spinner_timer = None
        self.set_interval(1, self._update_session_clock)

        sidebar = self.query_one("#sidebar", Vertical)
        sidebar.border_title = "SYSTEM STATUS"
        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.border_title = "COMM LOG"
        self._set_input_title(streaming=False)

        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.status_text = "OFFLINE"
            self.append_error_message(
                "ANTHROPIC_API_KEY is not set in the environment or .env file."
            )
            self.query_one("#chat-input", Input).disabled = True
            return

        self.client = anthropic.Anthropic()
        self.status_text = "ONLINE"
        self.query_one("#chat-input", Input).focus()

    def watch_status_text(self, status: str) -> None:
        status_line = self.query_one("#status-line", Static)
        status_class = {
            "ONLINE": "status-online",
            "OFFLINE": "status-offline",
            "THINKING…": "status-thinking",
        }.get(status, "status-offline")
        status_line.set_classes(f"sidebar-value {status_class}")

        if status == "THINKING…":
            self._start_spinner()
        else:
            self._stop_spinner()
            status_line.update(f"● {status}")

    def watch_message_count(self, count: int) -> None:
        self.query_one("#message-count-line", Static).update(str(count))
        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.border_subtitle = f"{count} MSG" if count else ""

    def _start_spinner(self) -> None:
        if self._spinner_timer is not None:
            return
        self._spinner_frame = 0
        self._spinner_timer = self.set_interval(0.12, self._tick_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def _tick_spinner(self) -> None:
        frame = SPINNER_FRAMES[self._spinner_frame % len(SPINNER_FRAMES)]
        self._spinner_frame += 1
        self.query_one("#status-line", Static).update(f"{frame} THINKING…")

    def _set_input_title(self, streaming: bool) -> None:
        chat_input = self.query_one("#chat-input", Input)
        chat_input.border_title = "TRANSMITTING…" if streaming else "INPUT"

    def _update_session_clock(self) -> None:
        elapsed = int(time.time() - self._session_start)
        minutes, seconds = divmod(elapsed, 60)
        self.query_one("#session-clock", Static).update(f"{minutes:02d}:{seconds:02d}")

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _mount_message(
        self,
        label: str,
        content: Static | Markdown,
        bubble_class: str,
    ) -> None:
        chat_log = self.query_one("#chat-log", VerticalScroll)
        bubble = Vertical(content, classes=f"message-bubble {bubble_class}")
        bubble.border_title = label
        bubble.border_subtitle = self._timestamp()
        chat_log.mount(bubble)
        self.scroll_chat_to_end()

    def append_user_message(self, text: str) -> None:
        self._mount_message("▸ YOU", Static(text, classes="message-content"), "user-message")
        self.message_count += 1

    def append_assistant_message(self, text: str = "") -> Markdown:
        content = Markdown(
            text or THINKING_PLACEHOLDER,
            classes="message-content",
        )
        if not text:
            content.add_class("thinking")
        self._mount_message("▸ JARVIS", content, "assistant-message")
        return content

    def append_error_message(self, text: str) -> None:
        self._mount_message("⚠ ERROR", Static(text, classes="message-content"), "error-message")

    def scroll_chat_to_end(self) -> None:
        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.scroll_end(animate=False)

    def set_input_enabled(self, enabled: bool) -> None:
        chat_input = self.query_one("#chat-input", Input)
        chat_input.disabled = not enabled
        self._set_input_title(streaming=not enabled)
        if enabled:
            chat_input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._streaming or self.client is None:
            return

        text = event.value.strip()
        if not text:
            return

        if text.lower() in EXIT_COMMANDS:
            self.exit()
            return

        self.query_one("#chat-input", Input).clear()
        self.append_user_message(text)
        self.messages.append({"role": "user", "content": text})
        assistant_widget = self.append_assistant_message()
        self._streaming = True
        self.status_text = "THINKING…"
        self.set_input_enabled(False)
        self.run_worker(
            lambda: self.stream_reply(assistant_widget),
            thread=True,
            exclusive=True,
            exit_on_error=False,
        )

    def stream_reply(self, assistant_widget: Markdown) -> None:
        assert self.client is not None

        def update_assistant_widget(text: str) -> None:
            if assistant_widget.has_class("thinking"):
                assistant_widget.remove_class("thinking")
            assistant_widget.update(text)
            self.scroll_chat_to_end()

        def show_error(text: str) -> None:
            self.messages.pop()
            assistant_widget.parent.remove()
            self.append_error_message(text)

        def finish_streaming() -> None:
            self._streaming = False
            self.status_text = "ONLINE"
            self.set_input_enabled(True)

        buffer = ""
        try:
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=self.messages,
            ) as stream:
                for chunk in stream.text_stream:
                    buffer += chunk
                    self.call_from_thread(update_assistant_widget, buffer)
        except anthropic.APIError as exc:
            self.call_from_thread(
                show_error, f"API request failed: {exc}"
            )
            self.call_from_thread(finish_streaming)
            return
        except Exception as exc:
            self.call_from_thread(
                show_error, f"Unexpected error: {exc}"
            )
            self.call_from_thread(finish_streaming)
            return

        self.messages.append({"role": "assistant", "content": buffer})
        self.message_count += 1
        self.call_from_thread(finish_streaming)


def main() -> None:
    load_dotenv()
    app = JarvisApp()
    app.run()


if __name__ == "__main__":
    main()
