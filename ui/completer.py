from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "code_it.egg-info",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
}

DEFAULT_IGNORED_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".lock",
    ".DS_Store",
}

COMMANDS = [
    ("/help", "Show help and command list"),
    ("/config", "Show current configuration"),
    ("/approval", "Change tool approval policy (always/prompt/never)"),
    ("/setup", "Interactive configuration wizard"),
    ("/model", "Switch LLM model"),
    ("/exit", "Exit session"),
    ("/quit", "Exit session"),
    ("/checkpoint", "Create a session checkpoint"),
    ("/resume", "Resume a previous session by ID"),
    ("/restore", "Restore session from checkpoint"),
    ("/sessions", "List all saved sessions"),
]


class TagAndCommandCompleter(Completer):
    """
    Prompt_toolkit completer that provides:
    1. Interactive @file suggestions when typing '@' anywhere in the line.
    2. Slash command suggestions when typing '/' at the beginning of the line.
    """

    def __init__(
        self,
        cwd: Path,
        ignored_dirs: set[str] | None = None,
        ignored_exts: set[str] | None = None,
    ) -> None:
        self.cwd = cwd
        self.ignored_dirs = ignored_dirs or DEFAULT_IGNORED_DIRS
        self.ignored_exts = ignored_exts or DEFAULT_IGNORED_EXTS
        self._cached_files: list[str] = []
        self._cache_mtime: float = 0.0

    def _refresh_file_list(self) -> list[str]:
        """Scan cwd for files excluding ignored directories."""
        files: list[str] = []
        try:
            for item in self.cwd.rglob("*"):
                # Check if any parent or self is in ignored dirs
                parts = set(item.relative_to(self.cwd).parts)
                if parts & self.ignored_dirs:
                    continue

                if item.is_file() and item.suffix not in self.ignored_exts:
                    rel_path = item.relative_to(self.cwd).as_posix()
                    files.append(rel_path)
        except Exception:
            pass

        # Sort files: shorter/root files first, then alphabetically
        files.sort(key=lambda p: (p.count("/"), p.lower()))
        return files

    def get_files(self) -> list[str]:
        # Simple cache with refresh
        if not self._cached_files:
            self._cached_files = self._refresh_file_list()
        return self._cached_files

    def refresh(self) -> None:
        self._cached_files = self._refresh_file_list()

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        text_before_cursor = document.text_before_cursor

        # 1. Check for slash command at start of line
        command_match = re.match(r"^/([a-zA-Z0-9_-]*)$", text_before_cursor)
        if command_match:
            prefix = "/" + command_match.group(1).lower()
            for cmd, desc in COMMANDS:
                if cmd.lower().startswith(prefix):
                    yield Completion(
                        text=cmd,
                        start_position=-len(command_match.group(0)),
                        display=cmd,
                        display_meta=desc,
                    )
            return

        # 2. Check for @ file tag anywhere in the current input
        # Matches e.g. "look at @main" or just "@" or "@sub/dir/"
        tag_match = re.search(r"@([^\s@]*)$", text_before_cursor)
        if tag_match is not None:
            tag_prefix = tag_match.group(1)
            prefix_lower = tag_prefix.lower()
            files = self.get_files()

            # Filter candidates: exact prefix or substring match
            exact_matches: list[str] = []
            sub_matches: list[str] = []

            for path in files:
                path_lower = path.lower()
                basename = path.rsplit("/", 1)[-1].lower()

                if not tag_prefix:
                    exact_matches.append(path)
                elif path_lower.startswith(prefix_lower) or basename.startswith(prefix_lower):
                    exact_matches.append(path)
                elif prefix_lower in path_lower:
                    sub_matches.append(path)

            candidates = (exact_matches + sub_matches)[:30]  # Cap at top 30 for snappy rendering

            for path in candidates:
                # If path contains spaces, wrap in brackets @[path with space]
                completion_text = f"[{path}]" if " " in path else path

                display_name = path
                meta = "file"
                if "/" in path:
                    parent_dir, name = path.rsplit("/", 1)
                    meta = parent_dir

                yield Completion(
                    text=completion_text,
                    start_position=-len(tag_prefix),
                    display=display_name,
                    display_meta=meta,
                )

