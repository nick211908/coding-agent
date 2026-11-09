from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ui.completer import TagAndCommandCompleter
from utils.file_tags import find_file_tags, resolve_file_tags


class FileTagsResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

        (self.cwd / "main.py").write_text("print('hello world')", encoding="utf-8")
        sub = self.cwd / "src"
        sub.mkdir()
        (sub / "helper.py").write_text("def helper(): pass", encoding="utf-8")

        # Create binary file
        (self.cwd / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_find_file_tags(self) -> None:
        text = "Please review @main.py and @src/helper.py and @[path with space/file.py]"
        tags = find_file_tags(text)
        self.assertIn("main.py", tags)
        self.assertIn("src/helper.py", tags)
        self.assertIn("path with space/file.py", tags)

    def test_resolve_file_tags_attaches_content(self) -> None:
        text = "Can you inspect @main.py?"
        enriched, paths = resolve_file_tags(text, self.cwd)

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], self.cwd / "main.py")
        self.assertIn("--- Attached File: main.py ---", enriched)
        self.assertIn("print('hello world')", enriched)

    def test_resolve_multiple_tags(self) -> None:
        text = "Compare @main.py with @src/helper.py"
        enriched, paths = resolve_file_tags(text, self.cwd)

        self.assertEqual(len(paths), 2)
        self.assertIn("--- Attached File: main.py ---", enriched)
        self.assertIn("--- Attached File: src/helper.py ---", enriched)

    def test_resolve_binary_file_handled_safely(self) -> None:
        text = "Check @binary.bin"
        enriched, paths = resolve_file_tags(text, self.cwd)

        self.assertEqual(len(paths), 1)
        self.assertIn("binary file, cannot display content", enriched)

    def test_nonexistent_tag_ignored(self) -> None:
        text = "Check @does_not_exist.py"
        enriched, paths = resolve_file_tags(text, self.cwd)

        self.assertEqual(paths, [])
        self.assertEqual(enriched, text)


class TagAndCommandCompleterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

        (self.cwd / "apply_patch.py").write_text("code", encoding="utf-8")
        (self.cwd / "main.py").write_text("code", encoding="utf-8")

        ignored = self.cwd / ".venv" / "sub"
        ignored.mkdir(parents=True)
        (ignored / "hidden.py").write_text("secret", encoding="utf-8")

        self.completer = TagAndCommandCompleter(cwd=self.cwd)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_file_completion_on_at_symbol(self) -> None:
        # Document where user just typed '@'
        doc = Document("please check @", cursor_position=14)
        completions = list(self.completer.get_completions(doc, CompleteEvent()))

        texts = [c.text for c in completions]
        self.assertIn("apply_patch.py", texts)
        self.assertIn("main.py", texts)
        # Should NOT include .venv
        self.assertFalse(any(".venv" in t for t in texts))

    def test_file_completion_filters_by_prefix(self) -> None:
        doc = Document("look at @app", cursor_position=12)
        completions = list(self.completer.get_completions(doc, CompleteEvent()))

        texts = [c.text for c in completions]
        self.assertEqual(texts, ["apply_patch.py"])

    def test_slash_command_completion(self) -> None:
        doc = Document("/he", cursor_position=3)
        completions = list(self.completer.get_completions(doc, CompleteEvent()))

        texts = [c.text for c in completions]
        self.assertIn("/help", texts)

