from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path

from config.config import Config, ModelConfig
from context.manager import ContextManager


class ContextManagerCompressionTests(unittest.TestCase):
    def test_needs_compression_uses_current_message_history(self) -> None:
        config = Config(
            cwd=Path.cwd(),
            model=ModelConfig(context_window=200),
        )
        manager = ContextManager(
            config=config,
            user_memory=None,
            tools=[],
            skills=[],
        )
        manager.add_user_message("x " * 120)

        self.assertTrue(manager.needs_compression())

    def test_replace_with_summary_creates_single_restoration_message(self) -> None:
        manager = ContextManager(
            config=Config(cwd=Path.cwd()),
            user_memory=None,
            tools=[],
            skills=[],
        )
        manager.add_user_message("original request")
        manager.add_assistant_message("partial response")

        manager.replace_with_summary("## ORIGINAL GOAL\nFinish the task.")

        messages = manager.get_messages()[1:]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("Context Restoration", messages[0]["content"])
        self.assertIn("Finish the task.", messages[0]["content"])

    def test_replace_with_summary_keeps_history_if_building_fails(self) -> None:
        manager = ContextManager(
            config=Config(cwd=Path.cwd()),
            user_memory=None,
            tools=[],
            skills=[],
        )
        manager.add_user_message("original request")
        original_messages = manager.get_messages()

        with patch("context.manager.count_tokens", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                manager.replace_with_summary("summary")

        self.assertEqual(manager.get_messages(), original_messages)


if __name__ == "__main__":
    unittest.main()
