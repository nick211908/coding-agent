from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.config import Config
from tools.base import ToolInvocation
from tools.builtin import ApplyPatchTool, get_all_builtin_tools
from tools.registry import ToolRegistry


class ApplyPatchRegistrationTests(unittest.TestCase):
    def test_apply_patch_in_builtin_tools(self) -> None:
        all_tools = get_all_builtin_tools()
        self.assertIn(ApplyPatchTool, all_tools)

    def test_tool_registry_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            config = Config(cwd=cwd)
            registry = ToolRegistry(config)
            tool = ApplyPatchTool(config)
            registry.register(tool)

            retrieved = registry.get("apply_patch")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "apply_patch")


class ApplyPatchExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp_dir.name)
        self.config = Config(cwd=self.cwd)
        self.tool = ApplyPatchTool(self.config)

    async def asyncTearDown(self) -> None:
        self.tmp_dir.cleanup()

    async def test_create_file(self) -> None:
        patch = (
            "*** Begin Patch\n"
            "*** Create File: hello.txt\n"
            "Hello, world!\n"
            "This is a new file.\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        created_file = self.cwd / "hello.txt"
        self.assertTrue(created_file.exists())
        self.assertEqual(created_file.read_text(encoding="utf-8"), "Hello, world!\nThis is a new file.")

    async def test_update_file(self) -> None:
        target = self.cwd / "code.py"
        target.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Update File: code.py\n"
            "<<<<<<< SEARCH\n"
            "    return a - b\n"
            "=======\n"
            "    return a + b\n"
            ">>>>>>> REPLACE\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "def add(a, b):\n    return a + b\n")

    async def test_delete_file(self) -> None:
        target = self.cwd / "temp.txt"
        target.write_text("delete me", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Delete File: temp.txt\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertFalse(target.exists())

    async def test_rename_file(self) -> None:
        old_file = self.cwd / "old_name.txt"
        old_file.write_text("content to keep", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Rename File: old_name.txt -> new_name.txt\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertFalse(old_file.exists())
        new_file = self.cwd / "new_name.txt"
        self.assertTrue(new_file.exists())
        self.assertEqual(new_file.read_text(encoding="utf-8"), "content to keep")

    async def test_multi_file_patch(self) -> None:
        existing = self.cwd / "module.py"
        existing.write_text("x = 1\n", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Create File: new_mod.py\n"
            "y = 2\n"
            "*** Update File: module.py\n"
            "<<<<<<< SEARCH\n"
            "x = 1\n"
            "=======\n"
            "x = 100\n"
            ">>>>>>> REPLACE\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertEqual((self.cwd / "new_mod.py").read_text(encoding="utf-8"), "y = 2")
        self.assertEqual(existing.read_text(encoding="utf-8"), "x = 100\n")

    async def test_dry_run_does_not_modify_disk(self) -> None:
        target = self.cwd / "untouched.txt"
        target.write_text("initial", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Update File: untouched.txt\n"
            "<<<<<<< SEARCH\n"
            "initial\n"
            "=======\n"
            "modified\n"
            ">>>>>>> REPLACE\n"
            "*** Create File: should_not_exist.txt\n"
            "sample\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch, "dry_run": True}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertIn("[DRY RUN]", result.output)
        self.assertEqual(target.read_text(encoding="utf-8"), "initial")
        self.assertFalse((self.cwd / "should_not_exist.txt").exists())

    async def test_search_content_mismatch_returns_error(self) -> None:
        target = self.cwd / "file.txt"
        target.write_text("actual text", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Update File: file.txt\n"
            "<<<<<<< SEARCH\n"
            "nonexistent text\n"
            "=======\n"
            "replacement\n"
            ">>>>>>> REPLACE\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        result = await self.tool.execute(invocation)

        self.assertTrue(result.success)
        self.assertIn("ERROR: Search content not found", result.output)
        self.assertEqual(target.read_text(encoding="utf-8"), "actual text")

    async def test_get_confirmation_flags_delete_as_dangerous(self) -> None:
        target = self.cwd / "remove.py"
        target.write_text("delete this", encoding="utf-8")

        patch = (
            "*** Begin Patch\n"
            "*** Delete File: remove.py\n"
            "*** End Patch\n"
        )
        invocation = ToolInvocation(params={"patch": patch}, cwd=self.cwd)
        confirmation = await self.tool.get_confirmation(invocation)

        self.assertIsNotNone(confirmation)
        self.assertTrue(confirmation.is_dangerous)
        self.assertIn(target, confirmation.affected_paths)

