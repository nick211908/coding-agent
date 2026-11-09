import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: Literal["pending", "in_progress", "completed"]
    owner: str | None
    blockedBy: list[str]
    todos: list[dict]


class TaskStore:
    def __init__(self, cwd: Path):
        self.tasks_dir = cwd / ".tasks"

    def _get_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def _get_md_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.md"

    def save(self, task: Task) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_path(task.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(task), f, indent=2)

        md_path = self._get_md_path(task.id)
        self._write_markdown(md_path, task)

    def _write_markdown(self, path: Path, task: Task) -> None:
        lines = [
            f"# Task: {task.subject}",
            "",
            f"- **ID:** `{task.id}`",
            f"- **Status:** `{task.status}`",
            f"- **Owner:** `{task.owner or 'Unassigned'}`",
        ]
        if task.blockedBy:
            lines.append(f"- **Blocked By:** {', '.join(f'`{b}`' for b in task.blockedBy)}")

        lines.append("")
        if task.description:
            lines.extend([
                "## Description",
                task.description,
                "",
            ])

        lines.append("## Todos / Checklist")
        if task.todos:
            for todo in task.todos:
                box = "[x]" if todo.get("completed") else "[ ]"
                content = todo.get("content", "")
                todo_id = todo.get("id", "")
                lines.append(f"- {box} {content} `({todo_id})`")
        else:
            lines.append("_No todos added yet._")

        lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def load(self, task_id: str) -> Task:
        path = self._get_path(task_id)
        if not path.exists():
            raise FileNotFoundError(f"Task {task_id} not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "todos" not in data:
            data["todos"] = []
        return Task(**data)

    def create(self, subject: str, description: str = "") -> Task:
        task_id = "task_" + str(uuid.uuid4().hex)[:8]
        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            status="pending",
            owner=None,
            blockedBy=[],
            todos=[],
        )
        self.save(task)
        return task

    def list_all(self) -> list[Task]:
        if not self.tasks_dir.exists():
            return []
        tasks = []
        for file in self.tasks_dir.glob("*.json"):
            try:
                tasks.append(self.load(file.stem))
            except Exception:
                pass
        return tasks

    def update_dependencies(self, task_id: str, add_blocked_by: list[str]) -> Task:
        task = self.load(task_id)
        if task.status != "pending":
            raise ValueError(f"Task {task_id} is {task.status}, cannot update dependencies")
        if task.owner is not None:
            raise ValueError(f"Task {task_id} is already owned")
        
        for dep in add_blocked_by:
            if dep == task_id:
                raise ValueError(f"Task {task_id} cannot depend on itself")
            self.load(dep)
            if dep not in task.blockedBy:
                task.blockedBy.append(dep)
        self.save(task)
        return task

    def incomplete_dependencies(self, task: Task) -> list[str]:
        incomplete = []
        for dep_id in task.blockedBy:
            try:
                dep_task = self.load(dep_id)
                if dep_task.status != "completed":
                    incomplete.append(dep_id)
            except FileNotFoundError:
                incomplete.append(dep_id)
        return incomplete

    def can_start(self, task_id: str) -> bool:
        task = self.load(task_id)
        return len(self.incomplete_dependencies(task)) == 0


class CreateTaskParams(BaseModel):
    subject: str = Field(..., description="Short title for the task")
    description: str = Field("", description="Detailed description of the task")

class CreateTaskTool(Tool):
    name = "create_task"
    description = "Create a new pending task. Returns the task ID."
    kind = ToolKind.MEMORY
    schema = CreateTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CreateTaskParams(**invocation.params)
        task = store.create(params.subject, params.description)
        return ToolResult.success_result(f"Created task: {task.id}")


class UpdateTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to update")
    addBlockedBy: list[str] = Field(..., description="List of task IDs that must be completed before this task can start")

class UpdateTaskTool(Tool):
    name = "update_task"
    description = "Add dependencies to a task. Use this to construct a task graph."
    kind = ToolKind.MEMORY
    schema = UpdateTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = UpdateTaskParams(**invocation.params)
        try:
            task = store.update_dependencies(params.task_id, params.addBlockedBy)
            return ToolResult.success_result(f"Updated {task.id}, blockedBy: {task.blockedBy}")
        except Exception as e:
            return ToolResult.error_result(str(e))


class ClaimTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to claim")
    owner: str = Field("agent", description="The agent claiming the task")

class ClaimTaskTool(Tool):
    name = "claim_task"
    description = "Claim a pending, unblocked task and set its status to in_progress."
    kind = ToolKind.MEMORY
    schema = ClaimTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = ClaimTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "pending":
                return ToolResult.error_result(f"Task {params.task_id} is {task.status}, cannot claim")
            
            incomplete = store.incomplete_dependencies(task)
            if incomplete:
                return ToolResult.error_result(f"Blocked by incomplete tasks: {incomplete}")

            task.owner = params.owner
            task.status = "in_progress"
            store.save(task)
            return ToolResult.success_result(f"Claimed {task.id} ({task.subject})")
        except Exception as e:
            return ToolResult.error_result(str(e))


class CompleteTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to complete")
    owner: str = Field("agent", description="The agent completing the task")

class CompleteTaskTool(Tool):
    name = "complete_task"
    description = "Mark an in_progress task as completed. Checks for any newly unblocked tasks."
    kind = ToolKind.MEMORY
    schema = CompleteTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CompleteTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "in_progress":
                return ToolResult.error_result(f"Task {params.task_id} is {task.status}, cannot complete")
            if task.owner != params.owner:
                return ToolResult.error_result(f"Task {params.task_id} is owned by {task.owner}, not {params.owner}")
            
            all_tasks = store.list_all()
            ready_before = {t.id for t in all_tasks if t.status == "pending" and t.blockedBy and store.can_start(t.id)}
            
            task.status = "completed"
            store.save(task)
            
            unblocked = [t.subject for t in store.list_all() if t.status == "pending" and t.blockedBy and t.id not in ready_before and store.can_start(t.id)]
            msg = f"Completed {task.id} ({task.subject})"
            if unblocked:
                msg += f"\nUnblocked: {', '.join(unblocked)}"
            return ToolResult.success_result(msg)
        except Exception as e:
            return ToolResult.error_result(str(e))


class ListTasksParams(BaseModel):
    pass

class ListTasksTool(Tool):
    name = "list_tasks"
    description = "List all tasks and their current statuses."
    kind = ToolKind.MEMORY
    schema = ListTasksParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        tasks = store.list_all()
        if not tasks:
            return ToolResult.success_result("No tasks found.")
        
        lines = ["Tasks:"]
        for t in tasks:
            blocked_info = f" (blocked by: {', '.join(t.blockedBy)})" if t.blockedBy else ""
            lines.append(f"  [{t.id}] {t.status.upper()} - {t.subject}{blocked_info}")
        return ToolResult.success_result("\n".join(lines))


class GetTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to view")

class GetTaskTool(Tool):
    name = "get_task"
    description = "View the full JSON details of a specific task."
    kind = ToolKind.MEMORY
    schema = GetTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = GetTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            return ToolResult.success_result(json.dumps(asdict(task), indent=2))
        except Exception as e:
            return ToolResult.error_result(str(e))


class AddTodoParams(BaseModel):
    task_id: str = Field(..., description="ID of the in_progress task")
    content: str = Field(..., description="Description of the todo step")

class AddTodoTool(Tool):
    name = "add_todo"
    description = "Add a sub-step (todo) to an in_progress task's checklist."
    kind = ToolKind.MEMORY
    schema = AddTodoParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = AddTodoParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "in_progress":
                return ToolResult.error_result(f"Task {params.task_id} is not in_progress")
            
            todo_id = str(uuid.uuid4().hex)[:6]
            task.todos.append({"id": todo_id, "content": params.content, "completed": False})
            store.save(task)
            return ToolResult.success_result(f"Added todo [{todo_id}]: {params.content}")
        except Exception as e:
            return ToolResult.error_result(str(e))


class CompleteTodoParams(BaseModel):
    task_id: str = Field(..., description="ID of the task")
    todo_id: str = Field(..., description="ID of the todo to mark as completed")

class CompleteTodoTool(Tool):
    name = "complete_todo"
    description = "Mark a sub-step (todo) as completed in the active task."
    kind = ToolKind.MEMORY
    schema = CompleteTodoParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CompleteTodoParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            for todo in task.todos:
                if todo["id"] == params.todo_id:
                    if todo["completed"]:
                        return ToolResult.success_result(f"Todo {params.todo_id} is already completed")
                    todo["completed"] = True
                    store.save(task)
                    return ToolResult.success_result(f"Completed todo [{params.todo_id}]: {todo['content']}")
            return ToolResult.error_result(f"Todo {params.todo_id} not found in task {params.task_id}")
        except Exception as e:
            return ToolResult.error_result(str(e))
