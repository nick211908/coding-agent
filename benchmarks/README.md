# Codenaut harness benchmark

A reproducible, isolated end-to-end benchmark for the Codenaut CLI. The runner uses only Python's standard library; each task gets a fresh temporary repository, a project-local Codenaut config, a Git baseline, and an independent verification step.

## Requirements

- Python 3.13+ (matches Codenaut's `pyproject.toml`)
- Install Codenaut's project dependencies in the current checkout (`uv sync` recommended)
- Git
- A Groq API key for live runs

## Configure Groq

PowerShell:

```powershell
$env:API_KEY = "gsk_..."
$env:BASE_URL = "https://api.groq.com/openai/v1"
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
```

macOS/Linux:

```bash
export API_KEY="gsk_..."
export BASE_URL="https://api.groq.com/openai/v1"
export GROQ_MODEL="llama-3.3-70b-versatile"
```

The runner writes a temporary `.ai-agent/config.toml` per task with temperature 0, a bounded turn budget, hooks and skills disabled, and YOLO approval so the non-interactive CLI can edit its disposable fixture. Never point this benchmark at a real working directory: tasks execute model-generated code and shell commands in a temporary directory. This is process isolation, not a security sandbox. For untrusted models/tasks, run the entire benchmark inside a disposable container with no host mounts and restricted network access.

## Run

From the Codenaut repository root:

```bash
# Validate task definitions and fixture setup without API calls
python benchmarks/run.py --dry-run

# One live pass over the suite
python benchmarks/run.py

# Three independent attempts per task (recommended for reliability)
python benchmarks/run.py --runs 3

# Run selected task(s)
python benchmarks/run.py --task C01 --task C05 --runs 3

# Override model and limits
python benchmarks/run.py --model llama-3.3-70b-versatile --timeout 600 --max-turns 30
```

Set `API_KEY` to the Groq key. `BASE_URL` defaults to Groq's OpenAI-compatible endpoint. `GROQ_MODEL` can override the default model. Reports are written to `benchmarks/results/report-<timestamp>.json`.

## Included task coverage

| ID | Category | What it measures |
|---|---|---|
| C01 | Debugging | Localized bug diagnosis and regression tests |
| C02 | Feature | Implementing a behavioral contract |
| C03 | Multi-file | Cross-module change and backward compatibility |
| C04 | Repository understanding | Read-only inspection and accurate explanation |
| C05 | Recovery | Fixing an initially failing test without weakening it |
| C06 | Subagent orchestration | Delegation to the read-only codebase investigator |
| C07 | Safety | Preserve sentinel data while implementing a feature |

Each task runs against a fresh fixture. The runner evaluates exit status, independent tests, expected output, changed-file policy, and sentinel preservation. The JSON report includes wall-clock duration, process output, tool-call mentions visible in CLI output, verification logs, changed files, and diffs.

## Metrics and interpretation

- **Task success rate:** passed runs / all runs.
- **Per-task pass rate:** successes / repetitions for that task.
- **Pass^k:** `pass_all` is true only when every repetition passes; this is a useful stability indicator.
- **Latency:** wall-clock time from CLI invocation to process completion.
- **Observed tool calls:** best-effort parsing of tool-call labels printed by the CLI, not a canonical event trace.

The current runner does not estimate token cost because the CLI does not expose a stable machine-readable usage stream. For exact tool-call counts, token usage, retry attribution, and subagent traces, add a JSONL event sink at the `AgentEvent` / `LLMClient` boundary in a follow-up instrumentation change. If LangSmith tracing is enabled, compare its trace data separately; the runner disables tracing by default to keep runs isolated.

## Important benchmark caveats

1. A passing task means the independent verifier passed; it does not prove the implementation is optimal.
2. Model output is stochastic even at temperature 0. Repeat tasks and report both mean pass rate and all-runs-pass.
3. Do not compare model or harness versions unless the model ID, task fixtures, timeout, turn budget, dependencies, and environment are held constant.
4. The suite intentionally tests end-to-end behavior. It is not a replacement for unit tests of stream parsing, tool registry exception handling, approval decisions, loop detection, context compaction, MCP transport failures, or persistence restore.
5. The benchmark uses the project config's `approval = "yolo"` only inside disposable temporary fixtures. Never use that policy for ordinary development directories.

## Suggested next phase: deterministic fault injection

After establishing this baseline, add mocked unit tests around:
- streamed tool-call fragments split across multiple chunks;
- non-stream completion preserving tool calls;
- connection/rate-limit failure before and after the first streamed chunk;
- malformed tool arguments and unknown tool names;
- tool execution exceptions and hook exceptions;
- loop detection and max-turn termination;
- MCP timeout/disconnect and subagent deadline enforcement;
- context compaction failure and checkpoint restore.

Keep these deterministic tests separate from live Groq task success. That separation lets you distinguish harness defects from model decision failures.
