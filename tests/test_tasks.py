from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.config import Config
from tools.base import ToolInvocation
from tools.builtin.tasks import (
    AddTodoTool,
    ClaimTaskTool,
    CompleteTaskTool,
    CompleteTodoTool,
    CreateTaskTool,
    TaskStore,
)


class TaskStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.config = Config(cwd=self.cwd)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_directory_created_lazily(self) -> None:
        """Instantiating TaskStore or querying list_all should not create .tasks."""
        store = TaskStore(self.cwd)
        tasks_dir = self.cwd / ".tasks"
        self.assertFalse(tasks_dir.exists())

        all_tasks = store.list_all()
        self.assertEqual(all_tasks, [])
        self.assertFalse(tasks_dir.exists())

    def test_create_task_writes_json_and_markdown(self) -> None:
        """Creating a task should create .tasks, {task_id}.json, and {task_id}.md."""
        store = TaskStore(self.cwd)
        task = store.create(subject="Build auth system", description="Implement JWT tokens")

        tasks_dir = self.cwd / ".tasks"
        self.assertTrue(tasks_dir.exists())

        json_file = tasks_dir / f"{task.id}.json"
        md_file = tasks_dir / f"{task.id}.md"

        self.assertTrue(json_file.exists())
        self.assertTrue(md_file.exists())

        md_content = md_file.read_text(encoding="utf-8")
        self.assertIn("# Task: Build auth system", md_content)
        self.assertIn("Implement JWT tokens", md_content)
        self.assertIn("- **Status:** `pending`", md_content)
        self.assertIn("## Todos / Checklist", md_content)

    async def test_task_tools_update_markdown(self) -> None:
        """Task tools (create, claim, add_todo, complete_todo) should keep markdown in sync."""
        create_tool = CreateTaskTool(self.config)
        claim_tool = ClaimTaskTool(self.config)
        add_todo_tool = AddTodoTool(self.config)
        complete_todo_tool = CompleteTodoTool(self.config)

        # 1. Create task
        res = await create_tool.execute(
            ToolInvocation(params={"subject": "Refactor API", "description": "Clean up endpoints"}, cwd=self.cwd)
        )
        self.assertTrue(res.success)
        task_id = res.output.split(": ")[-1].strip()

        tasks_dir = self.cwd / ".tasks"
        md_file = tasks_dir / f"{task_id}.md"
        self.assertTrue(md_file.exists())

        # 2. Claim task
        await claim_tool.execute(
            ToolInvocation(params={"task_id": task_id, "owner": "developer"}, cwd=self.cwd)
        )
        md_content = md_file.read_text(encoding="utf-8")
        self.assertIn("- **Status:** `in_progress`", md_content)
        self.assertIn("- **Owner:** `developer`", md_content)

        # 3. Add todo
        res_todo = await add_todo_tool.execute(
            ToolInvocation(params={"task_id": task_id, "content": "Write unit tests"}, cwd=self.cwd)
        )
        self.assertTrue(res_todo.success)
        # Extract todo id from: Added todo [xxxxxx]: ...
        todo_id = res_todo.output.split("[")[1].split("]")[0]

        md_content = md_file.read_text(encoding="utf-8")
        self.assertIn(f"- [ ] Write unit tests `({todo_id})`", md_content)

        # 4. Complete todo
        await complete_todo_tool.execute(
            ToolInvocation(params={"task_id": task_id, "todo_id": todo_id}, cwd=self.cwd)
        )
        md_content = md_file.read_text(encoding="utf-8")
        self.assertIn(f"- [x] Write unit tests `({todo_id})`", md_content)

