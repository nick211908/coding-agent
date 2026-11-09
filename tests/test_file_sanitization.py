from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.config import Config
from tools.base import ToolInvocation
from tools.builtin.edit_file import EditTool
from tools.builtin.write_file import WriteFileTool
from utils.text import clean_created_content


class CleanCreatedContentTests(unittest.TestCase):
    def test_strip_standalone_at_at(self) -> None:
        raw = "@@\ndef foo():\n    return 42"
        self.assertEqual(clean_created_content(raw), "def foo():\n    return 42")

    def test_strip_unified_diff_hunk_header(self) -> None:
        raw = "@@ -0,0 +1,5 @@\nimport os\nimport sys"
        self.assertEqual(clean_created_content(raw), "import os\nimport sys")

    def test_strip_unified_diff_with_trailing_signature(self) -> None:
        raw = "@@ -0,0 +1,5 @@ def foo():\ndef foo():\n    return 42"
        self.assertEqual(clean_created_content(raw), "def foo():\n    return 42")

    def test_strip_full_git_diff_with_plus_prefixes(self) -> None:
        raw = (
            "--- /dev/null\n"
            "+++ b/test.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def bar():\n"
            "+    return 'hello'\n"
        )
        self.assertEqual(clean_created_content(raw), "def bar():\n    return 'hello'")

    def test_strip_markdown_code_fence(self) -> None:
        raw = "```python\nprint('hello')\n```"
        self.assertEqual(clean_created_content(raw), "print('hello')")

    def test_strip_search_replace_block(self) -> None:
        raw = "<<<<<<< SEARCH\n=======\nprint('hello')\n>>>>>>> REPLACE"
        self.assertEqual(clean_created_content(raw), "print('hello')")

    def test_clean_content_untouched(self) -> None:
        clean = "import math\n\ndef calculate():\n    return math.pi"
        self.assertEqual(clean_created_content(clean), clean)

    def test_markdown_bullet_list_not_stripped(self) -> None:
        md = "# Notes\n+ Item one\n+ Item two"
        self.assertEqual(clean_created_content(md), md)


class FileToolsSanitizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.config = Config(cwd=self.cwd)

    async def asyncTearDown(self) -> None:
        self.tmp.cleanup()

    async def test_write_file_sanitizes_leading_at_at(self) -> None:
        tool = WriteFileTool(self.config)
        invocation = ToolInvocation(
            params={
                "path": "test_script.py",
                "content": "@@\ndef main():\n    pass",
            },
            cwd=self.cwd,
        )
        result = await tool.execute(invocation)
        self.assertTrue(result.success)

        target = self.cwd / "test_script.py"
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "def main():\n    pass")

    async def test_edit_new_file_sanitizes_leading_at_at(self) -> None:
        tool = EditTool(self.config)
        invocation = ToolInvocation(
            params={
                "path": "new_created.py",
                "old_string": "",
                "new_string": "@@ -0,0 +1,2 @@\n+x = 10\n+y = 20",
            },
            cwd=self.cwd,
        )
        result = await tool.execute(invocation)
        self.assertTrue(result.success)

        target = self.cwd / "new_created.py"
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "x = 10\ny = 20")

