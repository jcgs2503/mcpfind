"""Interactive setup wizard for MCPFind."""

from __future__ import annotations

from pathlib import Path

import click

# Popular MCP servers organized by category
POPULAR_SERVERS: list[dict] = [
    # Developer Tools
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
    # File & Data
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
    # Communication
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
    # Web & Search
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
    # Browser & Automation
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
    # Memory & Knowledge
    {
        "name": "memory",
        "display": "Memory (Knowledge Graph)",
        "category": "Memory & Knowledge",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env_vars": {},
    },
]


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

    # Group by category
    categories: dict[str, list[dict]] = {}
    for server in POPULAR_SERVERS:
        cat = server["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(server)

    # Display numbered list
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

    # Step 1: Embedding provider
    provider, model = _pick_embedding_provider()

    # Step 2: Pick servers
    selected_servers = _pick_servers()

    # Step 3: Configure each server
    configured = []
    for server in selected_servers:
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

    # Step 6: OpenAI install hint
    if provider == "openai":
        click.echo("\nTo use OpenAI embeddings, install the extra:")
        click.echo("  pip install mcpfind[openai]")

    click.echo("\nYou're ready to go! Run:")
    click.echo(f"  mcpfind serve --config {output_path}")
    click.echo()
