from __future__ import annotations

import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style

from config.loader import get_data_dir
from ui.completer import TagAndCommandCompleter

PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "#5fafff bold",
        "completion-menu.completion": "bg:#2b2b2b #e0e0e0",
        "completion-menu.completion.current": "bg:#005f87 #ffffff bold",
        "completion-menu.meta.completion": "bg:#222222 #888888",
        "completion-menu.meta.completion.current": "bg:#004f72 #ffffff",
        "scrollbar.background": "bg:#1e1e1e",
        "scrollbar.button": "bg:#555555",
    }
)


class InteractivePrompt:
    """Manages prompt_toolkit session with file tag and command autocompletion."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.completer = TagAndCommandCompleter(cwd=self.cwd)

        # Setup history
        try:
            data_dir = get_data_dir()
            data_dir.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(data_dir / "history.txt"))
        except Exception:
            history = InMemoryHistory()

        self.session: PromptSession = PromptSession(
            completer=self.completer,
            complete_while_typing=True,
            style=PROMPT_STYLE,
            history=history,
        )

    def refresh_completions(self) -> None:
        """Refresh cached files in completer (e.g. after file operations)."""
        self.completer.refresh()

    async def get_input(self) -> str:
        """Prompt user asynchronously with completion popup support."""
        if not sys.stdin.isatty():
            # Fallback for piped or non-interactive environments
            line = sys.stdin.readline()
            if not line:
                raise EOFError
            return line.strip()

        formatted_prompt = HTML("<ansibrightblue><b>&gt; </b></ansibrightblue>")
        result = await self.session.prompt_async(formatted_prompt)
        return result.strip()

