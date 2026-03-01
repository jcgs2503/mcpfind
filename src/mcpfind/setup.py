"""Interactive setup wizard for MCPFind."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import click

# Known MCP client config locations
MCP_CLIENT_CONFIGS: list[dict] = [
    {
        "name": "Claude Desktop",
        "paths": {
            "Darwin": Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json",
            "Linux": Path.home() / ".config" / "claude" / "claude_desktop_config.json",
            "Windows": Path.home()
            / "AppData"
            / "Roaming"
            / "Claude"
            / "claude_desktop_config.json",
        },
    },
    {
        "name": "Claude Code",
        "paths": {
            "Darwin": Path.home() / ".claude" / "mcp.json",
            "Linux": Path.home() / ".claude" / "mcp.json",
            "Windows": Path.home() / ".claude" / "mcp.json",
        },
    },
    {
        "name": "Cursor",
        "paths": {
            "Darwin": Path.home() / ".cursor" / "mcp.json",
            "Linux": Path.home() / ".cursor" / "mcp.json",
            "Windows": Path.home() / ".cursor" / "mcp.json",
        },
    },
]

# Popular MCP servers organized by category
POPULAR_SERVERS: list[dict] = [
    {
        "name": "github",
        "display": "GitHub",
        "category": "Developer Tools",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_vars": {"GITHUB_TOKEN": "GitHub personal access token"},
    },
    {
        "name": "gitlab",
        "display": "GitLab",
        "category": "Developer Tools",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gitlab"],
        "env_vars": {
            "GITLAB_TOKEN": "GitLab personal access token",
            "GITLAB_API_URL": "GitLab API URL (default: https://gitlab.com/api/v4)",
        },
    },
    {
        "name": "filesystem",
        "display": "Filesystem",
        "category": "File & Data",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "extra_args_prompt": "Allowed directory path(s) (space-separated)",
        "env_vars": {},
    },
    {
        "name": "postgres",
        "display": "PostgreSQL",
        "category": "File & Data",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "extra_args_prompt": "PostgreSQL connection string",
        "env_vars": {},
    },
    {
        "name": "sqlite",
        "display": "SQLite",
        "category": "File & Data",
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path"],
        "extra_args_prompt": "Path to SQLite database file",
        "env_vars": {},
    },
    {
        "name": "slack",
        "display": "Slack",
        "category": "Communication",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env_vars": {"SLACK_BOT_TOKEN": "Slack bot token (xoxb-...)"},
    },
    {
        "name": "google-drive",
        "display": "Google Drive",
        "category": "Communication",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gdrive"],
        "env_vars": {},
    },
    {
        "name": "brave-search",
        "display": "Brave Search",
        "category": "Web & Search",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env_vars": {"BRAVE_API_KEY": "Brave Search API key"},
    },
    {
        "name": "fetch",
        "display": "Fetch (HTTP)",
        "category": "Web & Search",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "env_vars": {},
    },
    {
        "name": "playwright",
        "display": "Playwright (Browser)",
        "category": "Browser & Automation",
        "command": "npx",
        "args": ["-y", "@playwright/mcp"],
        "env_vars": {},
    },
    {
        "name": "puppeteer",
        "display": "Puppeteer (Browser)",
        "category": "Browser & Automation",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "env_vars": {},
    },
    {
        "name": "memory",
        "display": "Memory (Knowledge Graph)",
        "category": "Memory & Knowledge",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env_vars": {},
    },
]


def _detect_client_configs() -> list[tuple[str, Path, dict]]:
    """Detect existing MCP client configs and parse their servers.

    Returns list of (client_name, config_path, servers_dict).
    """
    system = platform.system()
    found = []

    for client in MCP_CLIENT_CONFIGS:
        path = client["paths"].get(system)
        if path and path.exists():
            try:
                data = json.loads(path.read_text())
                servers = data.get("mcpServers", {})
                if servers:
                    found.append((client["name"], path, servers))
            except (json.JSONDecodeError, OSError):
                continue

    return found


def _import_from_clients(
    detected: list[tuple[str, Path, dict]],
) -> list[dict]:
    """Let user import servers from detected MCP client configs."""
    click.echo("\n--- Import Existing MCP Servers ---\n")
    click.echo("Found MCP servers in:\n")

    all_servers: list[tuple[str, str, dict]] = []  # (client, name, config)

    for client_name, config_path, servers in detected:
        click.echo(f"  {client_name} ({config_path}):")
        for name, config in servers.items():
            click.echo(f"    - {name}")
            all_servers.append((client_name, name, config))
        click.echo()

    click.echo(f"  Total: {len(all_servers)} server(s) found\n")

    if not click.confirm("Import these servers into MCPFind?", default=True):
        return []

    # Let user deselect specific servers
    imported = []
    for client_name, name, config in all_servers:
        if click.confirm(f"  Import '{name}' from {client_name}?", default=True):
            server_entry = {
                "name": name,
                "command": config.get("command", ""),
                "args": config.get("args", []),
                "env": config.get("env", {}),
            }
            # Clean out empty env values
            server_entry["env"] = {k: v for k, v in server_entry["env"].items() if v}
            imported.append(server_entry)

    if imported:
        click.echo(f"\n  Imported {len(imported)} server(s).")

    return imported


def _install_to_clients(
    detected: list[tuple[str, Path, dict]],
    config_path: str,
) -> None:
    """Replace individual MCP servers in client configs with MCPFind proxy."""
    click.echo("\n--- Install MCPFind into MCP Clients ---\n")
    click.echo(
        "This will replace individual MCP servers in your client configs\n"
        "with a single MCPFind proxy entry. Your original servers will be\n"
        "managed by MCPFind via the config file.\n"
    )

    abs_config = str(Path(config_path).resolve())

    mcpfind_entry = {
        "command": "mcpfind",
        "args": ["serve", "--config", abs_config],
    }

    system = platform.system()
    for client in MCP_CLIENT_CONFIGS:
        path = client["paths"].get(system)
        if not path or not path.exists():
            continue

        client_name = client["name"]
        if not click.confirm(f"  Replace servers in {client_name} with MCPFind proxy?"):
            continue

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            click.echo(f"    Could not read {path}, skipping.")
            continue

        old_servers = data.get("mcpServers", {})

        # Back up original config
        backup_path = path.with_suffix(".json.bak")
        if not backup_path.exists():
            backup_path.write_text(json.dumps(data, indent=2))
            click.echo(f"    Backed up to {backup_path}")

        # Replace with MCPFind entry
        data["mcpServers"] = {"mcpfind": mcpfind_entry}
        path.write_text(json.dumps(data, indent=2) + "\n")
        click.echo(
            f"    Updated {client_name} — "
            f"replaced {len(old_servers)} server(s) with MCPFind proxy."
        )


def _pick_embedding_provider() -> tuple[str, str]:
    """Ask user to choose embedding provider."""
    click.echo("\n--- Embedding Provider ---\n")
    click.echo("MCPFind uses embeddings to search your tools by meaning.\n")
    click.echo("  [1] Local (default) — runs on your machine, no API key needed")
    click.echo("  [2] OpenAI — better quality, requires OPENAI_API_KEY\n")

    choice = click.prompt("Choose embedding provider", default="1", type=str)

    if choice == "2":
        model = click.prompt("OpenAI model", default="text-embedding-3-small", type=str)
        return "openai", model
    return "local", "all-MiniLM-L6-v2"


def _pick_servers() -> list[dict]:
    """Let user pick from popular MCP servers."""
    click.echo("\n--- Add MCP Servers ---\n")
    click.echo("Select servers to add (you can add custom ones later).\n")

    categories: dict[str, list[dict]] = {}
    for server in POPULAR_SERVERS:
        cat = server["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(server)

    numbered: list[dict] = []
    for category, servers in categories.items():
        click.echo(f"  {category}:")
        for server in servers:
            idx = len(numbered) + 1
            click.echo(f"    [{idx:2d}] {server['display']}")
            numbered.append(server)
        click.echo()

    selections = click.prompt(
        "Enter server numbers (comma-separated, or 'none')",
        default="none",
        type=str,
    )

    if selections.strip().lower() == "none":
        return []

    selected = []
    for part in selections.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(numbered):
                selected.append(numbered[idx])

    return selected


def _configure_server(server: dict) -> dict:
    """Prompt for server-specific configuration."""
    click.echo(f"\n  Configuring {server['display']}...")

    env = {}
    for var, description in server.get("env_vars", {}).items():
        value = click.prompt(f"    {description} ({var})", default="", type=str)
        if value:
            env[var] = value

    extra_args: list[str] = []
    if "extra_args_prompt" in server:
        value = click.prompt(f"    {server['extra_args_prompt']}", default="", type=str)
        if value:
            extra_args = value.split()

    return {
        "name": server["name"],
        "command": server["command"],
        "args": server["args"] + extra_args,
        "env": env,
    }


def _build_toml(
    provider: str,
    model: str,
    servers: list[dict],
) -> str:
    """Generate mcpfind.toml content."""
    lines = ["[proxy]"]
    lines.append(f'embedding_provider = "{provider}"')
    lines.append(f'embedding_model = "{model}"')
    lines.append("mfu_boost_weight = 0.15")
    lines.append("mfu_persist = true")
    lines.append("default_max_results = 5")

    for server in servers:
        lines.append("")
        lines.append("[[servers]]")
        lines.append(f'name = "{server["name"]}"')
        lines.append(f'command = "{server["command"]}"')

        args_str = ", ".join(f'"{a}"' for a in server["args"])
        lines.append(f"args = [{args_str}]")

        if server.get("env"):
            env_parts = []
            for k, v in server["env"].items():
                env_parts.append(f'{k} = "{v}"')
            env_str = ", ".join(env_parts)
            lines.append(f"env = {{ {env_str} }}")

    lines.append("")
    return "\n".join(lines)


def run_setup() -> None:
    """Run the interactive setup wizard."""
    click.echo("=" * 50)
    click.echo("  MCPFind Setup")
    click.echo("=" * 50)
    click.echo("\nThis wizard will create a mcpfind.toml config file.")

    # Step 1: Detect existing MCP client configs
    detected = _detect_client_configs()
    imported_servers: list[dict] = []
    if detected:
        imported_servers = _import_from_clients(detected)

    # Step 2: Embedding provider
    provider, model = _pick_embedding_provider()

    # Step 3: Pick additional servers from catalog
    configured = list(imported_servers)

    # Check if user already has servers imported
    if imported_servers:
        add_more = click.confirm("\nAdd more servers from the catalog?", default=False)
    else:
        add_more = True

    if add_more:
        # Filter out already-imported server names
        existing_names = {s["name"] for s in configured}
        selected_servers = _pick_servers()
        for server in selected_servers:
            if server["name"] not in existing_names:
                configured.append(_configure_server(server))

    # Step 4: Custom server
    while True:
        add_custom = click.confirm("\nAdd a custom MCP server?", default=False)
        if not add_custom:
            break

        name = click.prompt("  Server name", type=str)
        command = click.prompt("  Command (e.g., uvx, npx, python)", type=str)
        args_str = click.prompt("  Arguments (space-separated)", default="", type=str)
        args = args_str.split() if args_str else []

        env: dict[str, str] = {}
        while click.confirm("  Add an environment variable?", default=False):
            key = click.prompt("    Variable name", type=str)
            value = click.prompt(f"    Value for {key}", type=str)
            env[key] = value

        configured.append({"name": name, "command": command, "args": args, "env": env})

    # Step 5: Write config
    toml_content = _build_toml(provider, model, configured)

    click.echo("\n--- Generated Configuration ---\n")
    click.echo(toml_content)

    output_path = click.prompt("\nSave to", default="mcpfind.toml", type=str)
    path = Path(output_path)

    if path.exists():
        if not click.confirm(f"  {path} already exists. Overwrite?"):
            click.echo("Setup cancelled.")
            return

    path.write_text(toml_content)
    click.echo(f"\nConfig saved to {path}")

    # Step 6: Install MCPFind proxy into client configs
    if detected and configured:
        _install_to_clients(detected, output_path)

    # Step 7: Final instructions
    if provider == "openai":
        click.echo("\nTo use OpenAI embeddings, install the extra:")
        click.echo("  pip install mcpfind[openai]")

    click.echo("\nYou're ready to go! Run:")
    click.echo(f"  mcpfind serve --config {output_path}")
    click.echo()
