# code-it

A terminal-based, OpenAI-compatible coding agent that reads, edits, and runs code in your project through a ReAct-style tool-calling loop with approvals, hooks, MCP, and session persistence.

## Install

Prerequisites: Python 3.13+ and `uv`.

Install dependencies into the project-managed environment:

```bash
uv sync
```

Build distributable artifacts:

```bash
uv build
```

This creates:

- `dist/code_it-<version>-py3-none-any.whl`
- `dist/code_it-<version>.tar.gz`

## First Run

After syncing the project environment, configure credentials:

```bash
uv run code-it --configure
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
uv run code-it
```

Run a single prompt:

```bash
uv run code-it "Summarize what this repo does"
```

Target a specific working directory:

```bash
uv run code-it --cwd /path/to/project "Find and fix the failing test"
```

Update saved credentials later:

```bash
uv run code-it --configure
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
3. Build the wheel and sdist with `uv build --no-sources`.
4. Test the CLI with `uv run code-it --configure`.
5. Upload to TestPyPI.
6. Verify both `uv run code-it --configure` and `uv run code-it` work.
7. Publish to PyPI.

## Publish With uv

Recommended local release flow:

```bash
uv sync --frozen
uv run python -m unittest tests.test_config_loader tests.test_skills
uv build --no-sources
uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py
uv run --isolated --no-project --with dist/*.tar.gz tests/smoke_test.py
```

TestPyPI publish:

```bash
$env:UV_PUBLISH_TOKEN="pypi-***"
uv publish --publish-url https://test.pypi.org/legacy/
```

PyPI publish:

```bash
$env:UV_PUBLISH_TOKEN="pypi-***"
uv publish
```

For the first release, verify the package name on PyPI before publishing. If `code-it` is already taken, rename `project.name` in `pyproject.toml` before uploading.

## Trusted Publishing

A GitHub Actions release workflow is included at `.github/workflows/publish.yml`.

To use it:

1. Create the project on PyPI.
2. In the PyPI project settings, add a Trusted Publisher for this GitHub repository.
3. In GitHub, create an environment named `pypi`.
4. Push a version tag like `v0.1.0`.

That workflow will:

- sync with `uv`
- run the unit tests
- build the wheel and source distribution
- smoke-test both artifacts
- publish with `uv publish`

## Why `uv` Instead of `pip install -e .`

This repository already carries a `uv.lock`, so `uv sync` is the safer default for development. It avoids polluting a shared Python installation and reduces resolver conflicts with unrelated packages already installed on your machine.

## License

Distributed under the [MIT License](LICENSE).
