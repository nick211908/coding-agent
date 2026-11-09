from langsmith import traceable
import asyncio
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import click

from config.config import ApprovalPolicy, Config
from config.loader import get_system_config_path, load_config, save_system_config
from ui.tui import TUI, get_console

if TYPE_CHECKING:
    from agent.agent import Agent

console = get_console()


def configure_credentials_interactively(config: Config | None = None) -> Config:
    config = config or load_config(cwd=None)
    current_base_url = config.base_url or ""

    console.print("[bold]Credential Setup[/bold]")
    api_key = click.prompt("API key", hide_input=True).strip()
    base_url = click.prompt(
        "Base URL (leave blank for provider default)",
        default=current_base_url,
        show_default=bool(current_base_url),
    ).strip()

    save_system_config(
        {
            "api_key": api_key,
            "base_url": base_url or None,
        }
    )
    config.set_credentials(api_key=api_key, base_url=base_url or None)
    console.print(
        f"[success]Credentials saved to {get_system_config_path()}[/success]"
    )
    return config


class CLI:
    def __init__(self, config: Config):
        from agent.persistence import PersistenceManager, SessionSnapshot
        from ui.prompt import InteractivePrompt

        self.agent: Agent | None = None
        self.config = config
        self.tui = TUI(config, console)
        self.interactive_prompt = InteractivePrompt(self.config.cwd)
        self._persistence_manager_cls = PersistenceManager
        self._session_snapshot_cls = SessionSnapshot

    async def run_single(self, message: str) -> str | None:
        from agent.agent import Agent

        async with Agent(self.config) as agent:
            self.agent = agent
            return await self._process_message(message)

    async def run_interactive(self) -> str | None:
        from agent.agent import Agent

        self.tui.print_welcome(
            "code-it",
            lines=[
                f"model: {self.config.model_name}",
                f"cwd: {self.config.cwd}",
                "commands: /help /config /approval /setup /model /exit",
            ],
        )

        async with Agent(
            self.config,
            confirmation_callback=self.tui.handle_confirmation,
        ) as agent:
            self.agent = agent

            while True:
                try:
                    self.tui.print_current_state()
                    console.print()
                    user_input = await self.interactive_prompt.get_input()
                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = await self._handle_command(user_input)
                        if not should_continue:
                            break
                        continue

                    await self._process_message(user_input)
                    self.interactive_prompt.refresh_completions()
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break

        console.print("\n[dim]Goodbye![/dim]")

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            return None
        return tool.kind.value
    @traceable
    async def _process_message(self, message: str) -> str | None:
        from agent.events import AgentEventType
        from utils.file_tags import resolve_file_tags
        from utils.paths import display_path_rel_to_cwd

        if not self.agent:
            return None

        enriched_message, tagged_files = resolve_file_tags(message, self.config.cwd)
        if tagged_files:
            file_names = ", ".join(
                display_path_rel_to_cwd(str(f), self.config.cwd) for f in tagged_files
            )
            console.print(f"[dim]📎 Tagged {len(tagged_files)} file(s): {file_names}[/dim]")
        message = enriched_message

        assistant_streaming = True
        final_response: str | None = None

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                if not assistant_streaming:
                    self.tui.begin_assistant()
                    assistant_streaming = True
                self.tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                if assistant_streaming:
                    self.tui.end_assistant()
                    assistant_streaming = False
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                console.print(f"\n[error]Error: {error}[/error]")
            elif event.type == AgentEventType.COMPACTION_START:
                console.print("\n[dim]Compacting conversation context...[/dim]")
            elif event.type == AgentEventType.COMPACTION_COMPLETE:
                console.print("[success]Context compacted.[/success]")
            elif event.type == AgentEventType.COMPACTION_ERROR:
                error = event.data.get("error", "Compaction failed")
                console.print(f"\n[error]Context compaction failed: {error}[/error]")
            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_start(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("arguments", {}),
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("diff"),
                    event.data.get("truncated", False),
                    event.data.get("exit_code"),
                )

        return final_response

    async def _handle_command(self, command: str) -> bool:
        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""
        if cmd_name == "/exit" or cmd_name == "/quit":
            return False
        elif command == "/help":
            self.tui.show_help()
        elif command == "/clear":
            self.agent.session.context_manager.clear()
            self.agent.session.loop_detector.clear()
            console.print("[success]Conversation cleared [/success]")
        elif command == "/config":
            console.print("\n[bold]Current Configuration[/bold]")
            console.print(f"  Model: {self.config.model_name}")
            console.print(f"  Temperature: {self.config.temperature}")
            console.print(f"  Approval: {self.config.approval.value}")
            console.print(f"  Working Dir: {self.config.cwd}")
            console.print(f"  Max Turns: {self.config.max_turns}")
            console.print(f"  Hooks Enabled: {self.config.hooks_enabled}")
            console.print(f"  Base URL: {self.config.base_url or 'provider default'}")
        elif cmd_name == "/model":
            if cmd_args:
                self.config.model_name = cmd_args
                console.print(f"[success]Model changed to: {cmd_args} [/success]")
            else:
                console.print(f"Current model: {self.config.model_name}")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    approval = ApprovalPolicy(cmd_args)
                    self.config.approval = approval
                    console.print(
                        f"[success]Approval policy changed to: {cmd_args} [/success]"
                    )
                except ValueError:
                    console.print(
                        f"[error]Incorrect approval policy: {cmd_args} [/error]"
                    )
                    console.print(
                        f"Valid options: {', '.join(p.value for p in ApprovalPolicy)}"
                    )
            else:
                console.print(f"Current approval policy: {self.config.approval.value}")
        elif cmd_name == "/setup":
            self.config = configure_credentials_interactively(self.config)
            self.tui = TUI(self.config, console)
        elif cmd_name == "/stats":
            stats = self.agent.session.get_stats()
            console.print("\n[bold]Session Statistics [/bold]")
            for key, value in stats.items():
                console.print(f"   {key}: {value}")
        elif cmd_name == "/tools":
            tools = self.agent.session.tool_registry.get_tools()
            console.print(f"\n[bold]Available tools ({len(tools)}) [/bold]")
            for tool in tools:
                console.print(f"  • {tool.name}")
        elif cmd_name == "/mcp":
            mcp_servers = self.agent.session.mcp_manager.get_all_servers()
            console.print(f"\n[bold]MCP Servers ({len(mcp_servers)}) [/bold]")
            for server in mcp_servers:
                status = server["status"]
                status_color = "green" if status == "connected" else "red"
                console.print(
                    f"  • {server['name']}: [{status_color}]{status}[/{status_color}] ({server['tools']} tools)"
                )
        elif cmd_name == "/save":
            persistence_manager = self._persistence_manager_cls()
            session_snapshot = self._session_snapshot_cls(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            persistence_manager.save_session(session_snapshot)
            console.print(
                f"[success]Session saved: {self.agent.session.session_id}[/success]"
            )
        elif cmd_name == "/sessions":
            persistence_manager = self._persistence_manager_cls()
            sessions = persistence_manager.list_sessions()
            console.print("\n[bold]Saved Sessions[/bold]")
            for saved_session in sessions:
                console.print(
                    f"  • {saved_session['session_id']} (turns: {saved_session['turn_count']}, updated: {saved_session['updated_at']})"
                )
        elif cmd_name == "/resume":
            if not cmd_args:
                console.print("[error]Usage: /resume <session_id> [/error]")
            else:
                from agent.session import Session

                persistence_manager = self._persistence_manager_cls()
                snapshot = persistence_manager.load_session(cmd_args)
                if not snapshot:
                    console.print("[error]Session does not exist [/error]")
                else:
                    session = Session(config=self.config)
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""),
                                msg.get("tool_calls"),
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""),
                                msg.get("content", ""),
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}[/success]"
                    )
        elif cmd_name == "/checkpoint":
            persistence_manager = self._persistence_manager_cls()
            session_snapshot = self._session_snapshot_cls(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            checkpoint_id = persistence_manager.save_checkpoint(session_snapshot)
            console.print(f"[success]Checkpoint created: {checkpoint_id}[/success]")
        elif cmd_name == "/restore":
            if not cmd_args:
                console.print("[error]Usage: /restore <checkpoint_id> [/error]")
            else:
                from agent.session import Session

                persistence_manager = self._persistence_manager_cls()
                snapshot = persistence_manager.load_checkpoint(cmd_args)
                if not snapshot:
                    console.print("[error]Checkpoint does not exist [/error]")
                else:
                    session = Session(config=self.config)
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""),
                                msg.get("tool_calls"),
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""),
                                msg.get("content", ""),
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}, checkpoint: {cmd_args}[/success]"
                    )
        else:
            console.print(f"[error]Unknown command: {cmd_name}[/error]")

        return True


@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--cwd",
    "-c",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
@click.option(
    "--configure",
    is_flag=True,
    help="Prompt for API credentials and save them to the user config file.",
)
def main(prompt: str | None, cwd: Path | None, configure: bool) -> None:
    try:
        config = load_config(cwd=cwd)
    except Exception as error:
        console.print(f"[error]Configuration Error: {error}[/error]")
        sys.exit(1)

    if configure:
        configure_credentials_interactively(config)
        return

    if not config.api_key:
        if click.confirm("No API key configured. Set it up now?", default=True):
            config = configure_credentials_interactively(config)
        else:
            console.print(
                "[error]No API key found. Run `code-it --configure` to save one.[/error]"
            )
            sys.exit(1)

    errors = config.validate()
    if errors:
        for error in errors:
            console.print(f"[error]{error}[/error]")
        sys.exit(1)

    cli = CLI(config)
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())


if __name__ == "__main__":
    main()
