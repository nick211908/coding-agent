from __future__ import annotations

import re
from pathlib import Path

from utils.paths import is_binary_file, resolve_path

# Matches @[path/to/file] or @path/to/file
TAG_PATTERN = re.compile(r"@\[([^\]]+)\]|@([a-zA-Z0-9_\-\./\\]+)")
MAX_ATTACHED_FILE_CHARS = 40_000
MAX_ATTACHED_FILE_LINES = 600


def find_file_tags(text: str) -> list[str]:
    """Extract all candidate file paths tagged with @ in text."""
    matches = TAG_PATTERN.findall(text)
    tags: list[str] = []
    for bracket_match, bare_match in matches:
        candidate = (bracket_match or bare_match).strip()
        # Avoid email addresses (e.g. user@domain.com) if preceded by word characters
        if candidate and candidate not in tags:
            tags.append(candidate)
    return tags


def resolve_file_tags(text: str, cwd: Path) -> tuple[str, list[Path]]:
    """
    Finds @file tags in text, checks if they exist in cwd, and appends
    their contents as formatted context blocks.
    Returns (augmented_text, list_of_resolved_paths).
    """
    candidates = find_file_tags(text)
    if not candidates:
        return text, []

    attached_blocks: list[str] = []
    resolved_paths: list[Path] = []

    for tag in candidates:
        # Check if the tag is part of an email address in the original text (e.g. test@example.com)
        if re.search(rf"\b[A-Za-z0-9._%+-]+@{re.escape(tag)}\b", text):
            continue

        resolved = resolve_path(cwd, tag)
        if resolved.exists() and resolved.is_file():
            if is_binary_file(resolved):
                attached_blocks.append(
                    f"\n[Attached File: {tag} (binary file, cannot display content)]"
                )
                resolved_paths.append(resolved)
                continue

            try:
                content = resolved.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                attached_blocks.append(
                    f"\n[Attached File: {tag} (read error: {e})]"
                )
                continue

            lines = content.splitlines()
            truncated = False
            if len(lines) > MAX_ATTACHED_FILE_LINES or len(content) > MAX_ATTACHED_FILE_CHARS:
                lines = lines[:MAX_ATTACHED_FILE_LINES]
                truncated = True

            snippet = "\n".join(lines)
            suffix = f"\n... [Truncated {len(content.splitlines()) - MAX_ATTACHED_FILE_LINES} lines]" if truncated else ""

            ext = resolved.suffix.lstrip(".")
            lang = ext if ext else ""

            attached_blocks.append(
                f"\n--- Attached File: {tag} ---\n```{lang}\n{snippet}{suffix}\n```"
            )
            resolved_paths.append(resolved)

    if not attached_blocks:
        return text, []

    augmented = text + "\n" + "\n".join(attached_blocks)
    return augmented, resolved_paths

