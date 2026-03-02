"""Install mcpfind as an MCP server into various MCP clients."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import click

from mcpfind.setup import MCP_CLIENT_CONFIGS


def _get_client_config_path(client_name: str) -> Path | None:
    """Get the platform-specific config path for a client."""
    system = platform.system()
    for client in MCP_CLIENT_CONFIGS:
        if client["name"] == client_name:
            return client["paths"].get(system)
    return None


def _merge_mcpfind_entry(config_path: Path) -> None:
    """Read a JSON MCP client config, merge in mcpfind entry, write back."""
    mcpfind_entry = {
        "command": "mcpfind",
        "args": ["serve"],
    }

    if config_path.exists():
        backup_path = config_path.with_suffix(".json.bak")
        if not backup_path.exists():
            backup_path.write_text(config_path.read_text())
            click.echo(f"  Backed up existing config to {backup_path}")

        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    servers = data.setdefault("mcpServers", {})
    if "mcpfind" in servers:
        click.echo("  mcpfind is already registered in this config.")
        if not click.confirm("  Overwrite existing entry?", default=True):
            return

    servers["mcpfind"] = mcpfind_entry
    config_path.write_text(json.dumps(data, indent=2) + "\n")
    click.echo(f"  Updated {config_path}")


def _install_claude_code() -> None:
    """Install mcpfind into Claude Code via the claude CLI."""
    if not shutil.which("claude"):
        click.echo("Error: 'claude' CLI not found on PATH.")
        click.echo(
            "Install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
        )
        raise SystemExit(1)

    click.echo("Registering mcpfind with Claude Code...")
    result = subprocess.run(
        ["claude", "mcp", "add", "-s", "user", "mcpfind", "--", "mcpfind", "serve"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"Error: {result.stderr.strip()}")
        raise SystemExit(1)

    click.echo("  Done! mcpfind registered as a user-scoped MCP server in Claude Code.")


def _install_cursor() -> None:
    """Install mcpfind into Cursor's mcp.json."""
    config_path = Path.home() / ".cursor" / "mcp.json"
    click.echo(f"Registering mcpfind with Cursor ({config_path})...")
    _merge_mcpfind_entry(config_path)


def _install_claude_desktop() -> None:
    """Install mcpfind into Claude Desktop's config."""
    config_path = _get_client_config_path("Claude Desktop")
    if config_path is None:
        click.echo("Error: unsupported platform for Claude Desktop.")
        raise SystemExit(1)

    click.echo(f"Registering mcpfind with Claude Desktop ({config_path})...")
    _merge_mcpfind_entry(config_path)


_HANDLERS = {
    "claude-code": _install_claude_code,
    "cursor": _install_cursor,
    "claude-desktop": _install_claude_desktop,
}


def install_client(client: str) -> None:
    """Install mcpfind into the specified MCP client."""
    handler = _HANDLERS[client]
    handler()

    click.echo()
    click.echo("Reminder: mcpfind uses layered config — no --config flag needed.")
    click.echo("  Global config:  mcpfind setup")
    click.echo("  Project servers: mcpfind init")
