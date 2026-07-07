# code-it

A terminal-based, OpenAI-compatible coding agent that reads, edits, and runs code in your project through a ReAct-style tool-calling loop — with approvals, hooks, MCP, and session persistence built in.

## Highlights

- **Agentic loop** — sends your request to an LLM, executes any tool calls it asks for (read/write/edit files, shell, grep, glob, web search/fetch), feeds results back, and repeats until it produces a final answer.
- **Built-in tool suite** — `read_file`, `write_file`, `edit_file`, `shell`, `list_dir`, `grep`, `glob`, `web_search`, `web_fetch`, `todo`, and `memory` tools out of the box.
- **MCP support** — connect additional tools from external MCP servers over stdio or HTTP/SSE.
- **Safety approvals** — configurable approval policies (`on-request`, `on-failure`, `auto`, `auto-edit`, `never`, `yolo`) gate risky/mutating tool calls before they run.
- **Lifecycle hooks** — run your own shell scripts before/after the agent runs or before/after any tool call.
- **Session persistence** — save, list, resume, checkpoint, and restore conversations across runs.
- **Provider-agnostic** — works with any OpenAI-compatible endpoint (OpenAI, OpenRouter, local models, etc.) via `API_KEY` / `BASE_URL`.
- **Rich terminal UI** — streaming responses, colorized tool-call output, and diffs, powered by `rich`.

## Installation and Setup

**Prerequisites:** Python 3.13+ and [uv](https://docs.astral.sh/uv/) (recommended) or `pip`.

1. **Clone the repo**
   ```bash
   git clone git@github.com:nick211908/coding-agent.git
   cd coding-agent
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```
   or, with plain pip:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # .venv\Scripts\activate on Windows
   pip install -e .
   ```

3. **Configure your API credentials**

   Create a `.env` file in the project root:
   ```bash
   API_KEY=your-api-key-here
   BASE_URL=https://openrouter.ai/api/v1   # or any OpenAI-compatible endpoint
   ```

4. **(Optional) Project-level config**

   Drop a `.ai-agent/config.toml` in your project to override model, approval policy, hooks, MCP servers, etc., and/or an `AGENT.MD` file for project-specific developer instructions that get injected into the system prompt.

## Usage Examples

Run interactively:
```bash
uv run main.py
```

Run a single one-shot prompt:
```bash
uv run main.py "Summarize what this repo does"
```

Target a specific working directory:
```bash
uv run main.py --cwd /path/to/project "Find and fix the failing test"
```

Inside an interactive session:
```
[user]> /tools                  # list available tools
[user]> /mcp                    # list connected MCP servers
[user]> /approval auto-edit     # change the approval policy
[user]> /save                   # save the current session
[user]> /sessions               # list saved sessions
[user]> /resume <session_id>    # resume a saved session
[user]> /checkpoint             # snapshot the current session
[user]> /stats                  # show token/turn usage stats
[user]> /exit                   # quit
```

## Contribution Guidelines

1. Fork the repo and create a feature branch off `main`: `git checkout -b feature/your-feature`.
2. Keep the codebase's existing style: type-hinted Python, `pydantic` models for config/data, and small, single-responsibility modules under `agent/`, `tools/`, `context/`, `safety/`, `hooks/`, etc.
3. Add or update tests where relevant (`scripts/` currently holds test/dev utilities) and make sure the CLI still runs (`uv run main.py`) before submitting.
4. Use clear, descriptive commit messages.
5. Open a pull request against `main` describing what changed and why; link any related issues.
6. Be respectful and constructive in code review — small, focused PRs are easier to merge than large ones.

## License

Distributed under the [MIT License](LICENSE).

## Contact

- **Maintainer:** [nick211908](https://github.com/nick211908)
- **Issues / bug reports:** [github.com/nick211908/coding-agent/issues](https://github.com/nick211908/coding-agent/issues)
- **Repository:** [github.com/nick211908/coding-agent](https://github.com/nick211908/coding-agent)
