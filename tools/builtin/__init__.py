from tools.builtin.apply_patch import ApplyPatchTool
from tools.builtin.edit_file import EditTool
from tools.builtin.glob import GlobTool
from tools.builtin.grep import GrepTool
from tools.builtin.list_dir import ListDirTool
from tools.builtin.memory import MemoryTool
from tools.builtin.read_file import ReadFileTool
from tools.builtin.shell import ShellTool
from tools.builtin.tasks import (
    ClaimTaskTool,
    CompleteTaskTool,
    CreateTaskTool,
    GetTaskTool,
    ListTasksTool,
    UpdateTaskTool,
    AddTodoTool,
    CompleteTodoTool,
)
from tools.builtin.web_fetch import WebFetchTool
from tools.builtin.web_search import WebSearchTool
from tools.builtin.write_file import WriteFileTool

__all__ = [
    "ApplyPatchTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "CreateTaskTool",
    "UpdateTaskTool",
    "ClaimTaskTool",
    "CompleteTaskTool",
    "GetTaskTool",
    "ListTasksTool",
    "AddTodoTool",
    "CompleteTodoTool",
    "MemoryTool",
]


def get_all_builtin_tools() -> list[type]:
    return [
        ApplyPatchTool,
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
        WebFetchTool,
        CreateTaskTool,
        UpdateTaskTool,
        ClaimTaskTool,
        CompleteTaskTool,
        GetTaskTool,
        ListTasksTool,
        AddTodoTool,
        CompleteTodoTool,
        MemoryTool,
    ]
