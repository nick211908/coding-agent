# code-it

A terminal-based, OpenAI-compatible coding agent that reads, edits, and runs code in your project through a ReAct-style tool-calling loop with approvals, hooks, MCP, and session persistence.

## Install

Prerequisites: Python 3.13+.

Install from the repo while developing:

```bash
pip install -e .
```

Build distributable artifacts:

```bash
python -m build
```

This creates:

- `dist/code_it-<version>-py3-none-any.whl`
- `dist/code_it-<version>.tar.gz`

## First Run

After installation, use the console entry point:

```bash
code-it --configure
```

This prompts for:

- your API key
- an optional base URL for any OpenAI-compatible provider

The values are saved in your user config file at:

- Windows: `%APPDATA%\code-it\config.toml`
- macOS: `~/Library/Application Support/code-it/config.toml`
- Linux: `~/.config/code-it/config.toml`

You can still use a project-local `.env` file or `API_KEY` and `BASE_URL` environment variables, but they are no longer required for packaged installs.

## Usage

Run interactively:

```bash
code-it
```

Run a single prompt:

```bash
code-it "Summarize what this repo does"
```

Target a specific working directory:

```bash
code-it --cwd /path/to/project "Find and fix the failing test"
```

Update saved credentials later:

```bash
code-it --configure
```

Inside an interactive session:

```text
[user]> /setup                  # update saved API credentials
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

## Project Config

Project-level overrides still live in `.ai-agent/config.toml`.

You can also add:

- `AGENT.MD` for project-specific developer instructions
- `.ai-agent/skills/<skill-name>/SKILL.md` for reusable skills
- `.ai-agent/tools/*.py` for custom tools

## Publish Checklist

1. Bump `version` in `pyproject.toml`.
2. Run tests.
3. Build the wheel and sdist.
4. Test-install the wheel in a fresh virtual environment.
5. Upload to TestPyPI.
6. Verify `code-it --configure` and `code-it` both work.
7. Publish to PyPI.

## License

Distributed under the [MIT License](LICENSE).
