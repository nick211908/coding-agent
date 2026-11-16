#!/usr/bin/env python3
"""Run isolated end-to-end Codenaut harness benchmarks using only the stdlib."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS = Path(__file__).with_name("tasks.json")
DEFAULT_OUTPUT = Path(__file__).with_name("results")


def load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks.json must contain a non-empty 'tasks' array")
    ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or not task.get("id") or not task.get("prompt"):
            raise ValueError("Each task requires a non-empty id and prompt")
        if task["id"] in ids:
            raise ValueError(f"Duplicate task id: {task['id']}")
        ids.add(task["id"])
        for rel in task.get("files", {}):
            p = Path(rel)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"Unsafe fixture path in {task['id']}: {rel}")
    return tasks


def write_fixture(workdir: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def initialize_git(workdir: Path) -> bool:
    if not shutil.which("git"):
        return False
    commands = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "bench@localhost"],
        ["git", "config", "user.name", "Codenaut Benchmark"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "benchmark baseline"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=workdir, capture_output=True, text=True)
        if result.returncode:
            return False
    return True


def collect_diff(workdir: Path, has_git: bool) -> tuple[str, list[str]]:
    if not has_git:
        return "", []
    subprocess.run(["git", "add", "-N", "."], cwd=workdir, capture_output=True)
    diff = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary", "HEAD"],
        cwd=workdir, capture_output=True, text=True,
    )
    names = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=workdir, capture_output=True, text=True,
    )
    return diff.stdout, sorted(x for x in names.stdout.splitlines() if x)


def run_command(command: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False, env=env,
        )
        return {
            "command": command, "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command, "returncode": 124,
            "stdout": exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            "stderr": exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "timed_out": True,
        }


def evaluate_assertions(task: dict[str, Any], final_text: str, diff: str,
                       changed_files: list[str], workdir: Path,
                       verify_results: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    assertions = task.get("assertions", {})
    for needle in assertions.get("stdout_contains", []):
        if needle.casefold() not in final_text.casefold():
            failures.append(f"stdout missing required text: {needle!r}")
    for rel in assertions.get("files_exist", []):
        if not (workdir / rel).is_file():
            failures.append(f"required file does not exist: {rel}")
    for item in assertions.get("file_contains", []):
        path = workdir / item["path"]
        if not path.is_file() or item["text"] not in path.read_text(encoding="utf-8"):
            failures.append(f"{item['path']} missing expected text {item['text']!r}")
    if assertions.get("must_change_files") and not changed_files:
        failures.append("expected at least one repository change")
    if assertions.get("must_not_change_files") and changed_files:
        failures.append(f"expected no repository changes; changed: {changed_files}")
    if assertions.get("preserve_files"):
        for rel in assertions["preserve_files"]:
            if not (workdir / rel).is_file():
                failures.append(f"protected file was deleted: {rel}")
    for result in verify_results:
        if result["returncode"] != 0:
            failures.append(f"verification command failed ({result['returncode']}): {' '.join(result['command'])}")
    return failures


def run_one(task: dict[str, Any], run_index: int, args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"codenaut-{task['id']}-") as tmp:
        workdir = Path(tmp)
        write_fixture(workdir, task.get("files", {}))
        has_git = initialize_git(workdir)
        config_dir = workdir / ".ai-agent"
        config_dir.mkdir(exist_ok=True)
        model = args.model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        config = (
            'approval = "yolo"\\n'
            f"max_turns = {args.max_turns}\\n"
            "hooks_enabled = false\\n"
            "skills_enabled = false\\n"
            "\\n"
            "[model]\\n"
            f'name = "{model}"\\n'
            "temperature = 0.0\\n"
        )
        (config_dir / "config.toml").write_text(config, encoding="utf-8")

        env = os.environ.copy()
        env["BASE_URL"] = env.get("BASE_URL", "https://api.groq.com/openai/v1")
        env["LANGSMITH_TRACING"] = env.get("LANGSMITH_TRACING", "false")
        env["LANGCHAIN_TRACING_V2"] = env.get("LANGCHAIN_TRACING_V2", "false")
        command = [sys.executable, "-m", "main", "--cwd", str(workdir), task["prompt"]]

        started = time.perf_counter()
        if args.dry_run:
            agent_result = {
                "returncode": 0, "stdout": "DRY RUN: agent not invoked",
                "stderr": "", "duration_seconds": 0.0, "timed_out": False,
            }
        else:
            agent_result = run_command(command, ROOT, args.timeout, env=env)
        agent_seconds = round(time.perf_counter() - started, 3)

        verify_results = []
        for verify in task.get("verify", []):
            verify_results.append(run_command(verify, workdir, args.verify_timeout))

        diff, changed_files = collect_diff(workdir, has_git)
        failures = evaluate_assertions(
            task, agent_result["stdout"], diff, changed_files, workdir, verify_results
        )
        if agent_result["returncode"] != 0:
            failures.append(f"agent process exited with code {agent_result['returncode']}")
        if agent_result["timed_out"]:
            failures.append("agent timed out")
        if not has_git and not args.dry_run:
            failures.append("git unavailable; changed-file assertions cannot be trusted")

        tool_calls = re.findall(r"(?:Calling|tool call)\s+([A-Za-z0-9_.-]+)", agent_result["stdout"], re.I)
        return {
            "task_id": task["id"], "category": task.get("category", "uncategorized"),
            "run": run_index, "model": model, "passed": not failures,
            "failures": failures, "duration_seconds": agent_seconds,
            "agent_returncode": agent_result["returncode"],
            "agent_timed_out": agent_result["timed_out"],
            "tool_call_mentions": tool_calls, "tool_call_count_observed": len(tool_calls),
            "changed_files": changed_files, "diff": diff,
            "agent_stdout": agent_result["stdout"], "agent_stderr": agent_result["stderr"],
            "verification": verify_results,
        }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(bool(r["passed"]) for r in results)
    by_task: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_task.setdefault(result["task_id"], []).append(result)
    task_summary = {}
    for task_id, rows in by_task.items():
        task_summary[task_id] = {
            "runs": len(rows),
            "pass_rate": round(sum(r["passed"] for r in rows) / len(rows), 3),
            "pass_all": all(r["passed"] for r in rows),
            "mean_duration_seconds": round(statistics.mean(r["duration_seconds"] for r in rows), 3),
        }
    return {
        "total_runs": total, "passed": passed, "failed": total - passed,
        "success_rate": round(passed / total, 3) if total else 0.0,
        "mean_duration_seconds": round(statistics.mean(r["duration_seconds"] for r in results), 3) if results else 0.0,
        "tasks": task_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--task", action="append", help="Run only this task ID; repeatable")
    parser.add_argument("--runs", type=int, default=1, help="Independent repetitions per task (default: 1)")
    parser.add_argument("--timeout", type=int, default=420, help="Agent wall-clock timeout")
    parser.add_argument("--verify-timeout", type=int, default=90)
    parser.add_argument("--max-turns", type=int, default=24)
    parser.add_argument("--model", help="Groq model ID; defaults to GROQ_MODEL or llama-3.3-70b-versatile")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="Validate task fixtures without calling Groq")
    args = parser.parse_args()

    try:
        tasks = load_tasks(args.tasks)
    except Exception as exc:
        print(f"Invalid benchmark suite: {exc}", file=sys.stderr)
        return 2
    if args.runs < 1:
        parser.error("--runs must be >= 1")
    if not args.dry_run and not os.getenv("API_KEY"):
        print("Set API_KEY to your Groq API key (or export it before running).", file=sys.stderr)
        return 2
    selected = [t for t in tasks if not args.task or t["id"] in args.task]
    if args.task and {t["id"] for t in selected} != set(args.task):
        print("Unknown task ID requested.", file=sys.stderr)
        return 2

    results = []
    for task in selected:
        for run_index in range(1, args.runs + 1):
            print(f"[{task['id']}] run {run_index}/{args.runs}: {task.get('title', task['id'])}", flush=True)
            result = run_one(task, run_index, args)
            results.append(result)
            print(f"  {'PASS' if result['passed'] else 'FAIL'} — {result['duration_seconds']}s")
            for failure in result["failures"]:
                print(f"    - {failure}")

    summary = summarize(results)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repository": "nick211908/coding-agent",
        "model": args.model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "runs_per_task": args.runs, "dry_run": args.dry_run,
        "summary": summary, "results": results,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = args.output / f"report-{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSuccess rate: {summary['success_rate']:.1%} ({summary['passed']}/{summary['total_runs']})")
    print(f"Report: {report_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
