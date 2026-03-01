# MCPFind

[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

Context-efficient MCP tool proxy with semantic search. MCPFind sits between any MCP client and your backend MCP servers, replacing hundreds of tool schemas in the agent's context with just 3 meta-tools (~500 tokens).

```
Agent (Claude Desktop, Cursor, Claude Code, etc.)
  │  Sees only: search_tools, get_tool_schema, call_tool
  ▼
MCPFind Proxy
  ├── Vector search over all tool descriptions
  ├── Per-agent MFU cache for personalized ranking
  └── Routes calls to the correct backend server
  │
  ├──▶ Gmail MCP Server
  ├──▶ GitHub MCP Server
  ├──▶ Slack MCP Server
  └──▶ ... N servers
```

## Why

As MCP toolspaces grow, every tool schema gets dumped into the agent's context:

| Tools | Context tokens | Effect |
|-------|---------------|--------|
| 10 | ~2K | Fine |
| 50 | ~10K | Manageable |
| 200 | ~40K | Agent picks wrong tools |
| 1000 | ~200K | Unusable |

MCPFind keeps context at ~500 tokens regardless of how many tools exist behind it. Agents discover tools via semantic search, pull schemas on demand, and call tools through the proxy.

## Install

```bash
# With uv (recommended)
uv tool install mcpfind

# With pip
pip install mcpfind
```

MCPFind uses local embeddings by default (via [fastembed](https://github.com/qdrant/fastembed)) — no API key needed. To use OpenAI embeddings instead:

```bash
pip install mcpfind[openai]
export OPENAI_API_KEY="sk-..."
```

## Quick Start

### 1. Run the setup wizard

```bash
mcpfind setup
```

This walks you through choosing an embedding provider and adding popular MCP servers (GitHub, Slack, Filesystem, PostgreSQL, Brave Search, Playwright, and more). It writes your global config to `~/.config/mcpfind/mcpfind.toml`.

### 2. Verify your setup

```bash
# List all tools discovered from your backend servers
mcpfind list-tools

# Test semantic search
mcpfind search "create a pull request"
```

### 3. Run the proxy

```bash
mcpfind serve
```

This starts MCPFind as a stdio MCP server. Point your MCP client at it instead of individual servers.

## Configuration

MCPFind uses a layered config system: a **global** config shared across all projects, and an optional **project-local** config that can add or override servers per project.

### Global config (`~/.config/mcpfind/mcpfind.toml`)

Created by `mcpfind setup`. Contains your embedding provider settings and shared servers:

```toml
[proxy]
embedding_provider = "local"          # or "openai"
embedding_model = "all-MiniLM-L6-v2"  # or "text-embedding-3-small" for openai
mfu_boost_weight = 0.15
mfu_persist = true
default_max_results = 5

[[servers]]
name = "github"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }

[[servers]]
name = "slack"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-slack"]
env = { SLACK_BOT_TOKEN = "${SLACK_BOT_TOKEN}" }
```

### Project-local config (`./mcpfind.toml`)

Created by `mcpfind init` in your project directory. Contains only `[[servers]]` entries specific to the project:

```toml
[[servers]]
name = "postgres"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]

[[servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/project"]
```

### How merging works

When you run `mcpfind serve` (without `--config`):

1. Loads global config from `~/.config/mcpfind/mcpfind.toml` (if it exists)
2. Loads local config from `./mcpfind.toml` (if it exists)
3. Merges them: servers from both configs are combined. If a server has the same `name` in both, the local version wins.

In the example above, running `mcpfind serve` would give you: `github` + `slack` (global) + `postgres` + `filesystem` (local) = 4 servers.

To skip merging and use a specific file: `mcpfind serve --config path/to/config.toml`

### Manual config

You can also create either config file manually instead of using the wizard:

```bash
# Create global config directory
mkdir -p ~/.config/mcpfind
# Then write ~/.config/mcpfind/mcpfind.toml with the format shown above

# Or create a project-local config
# Just write ./mcpfind.toml with [[servers]] entries
```

## Adding MCP Servers

Each backend server is a `[[servers]]` entry in your config file:

```toml
[[servers]]
name = "gmail"              # Unique name (used in search results and call_tool)
command = "uvx"              # Command to launch the server
args = ["mcp-gmail"]         # Arguments passed to the command
env = { GMAIL_TOKEN = "${GMAIL_TOKEN}" }  # Environment variables (supports ${VAR} expansion)
```

### Examples

**GitHub:**
```toml
[[servers]]
name = "github"
command = "uvx"
args = ["mcp-server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

**Filesystem:**
```toml
[[servers]]
name = "filesystem"
command = "uvx"
args = ["mcp-server-filesystem", "/home/user/documents"]
```

**Slack:**
```toml
[[servers]]
name = "slack"
command = "uvx"
args = ["mcp-server-slack"]
env = { SLACK_BOT_TOKEN = "${SLACK_BOT_TOKEN}" }
```

**Custom / local server:**
```toml
[[servers]]
name = "my-server"
command = "python"
args = ["-m", "my_mcp_server"]
env = { MY_API_KEY = "${MY_API_KEY}" }
```

## Client Configuration

After running `mcpfind setup`, point your MCP client at MCPFind. Since MCPFind now uses the global config by default, you don't need to pass `--config`:

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcpfind": {
      "command": "mcpfind",
      "args": ["serve"],
      "env": {
        "GITHUB_TOKEN": "ghp_..."
      }
    }
  }
}
```

### Claude Code

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "mcpfind": {
      "command": "mcpfind",
      "args": ["serve"]
    }
  }
}
```

### Cursor

Add to your MCP settings:

```json
{
  "mcpServers": {
    "mcpfind": {
      "command": "mcpfind",
      "args": ["serve"]
    }
  }
}
```

## How It Works

MCPFind exposes exactly 3 tools to the agent:

1. **`search_tools`** — Find relevant tools by natural language query (e.g., "send an email"). Returns tool names, servers, and descriptions ranked by semantic similarity + usage frequency.

2. **`get_tool_schema`** — Pull the full input schema for a specific tool before calling it. Keeps schemas out of context until actually needed.

3. **`call_tool`** — Execute a tool on a backend server. MCPFind validates and routes the call to the correct server.

### Agent workflow

```
Agent: search_tools("send an email")
  → [{"server": "gmail", "name": "send_email", "score": 0.94}, ...]

Agent: get_tool_schema(server="gmail", tool="send_email")
  → {"type": "object", "properties": {"to": ..., "subject": ..., "body": ...}}

Agent: call_tool(server="gmail", tool="send_email", arguments={...})
  → "Email sent!"
```

### MFU Cache

MCPFind tracks which tools each agent uses most frequently. Frequently used tools get a ranking boost in search results via the `mfu_boost_weight` config option (default: 0.15). This means 85% of the ranking comes from semantic similarity and 15% from usage frequency.

Set `mfu_persist = true` to save usage data across restarts (stored in `mfu.db`).

## Configuration Reference

```toml
[proxy]
embedding_provider = "local"                # "local" (default) or "openai"
embedding_model = "all-MiniLM-L6-v2"        # Model name (provider-specific)
mfu_boost_weight = 0.15                     # Frequency boost weight (0.0-1.0)
mfu_persist = true                          # Persist usage data to SQLite
default_max_results = 5                     # Default number of search results

[[servers]]
name = "server-name"     # Required: unique identifier
command = "command"       # Required: executable to launch
args = ["arg1", "arg2"]  # Optional: command arguments
env = { KEY = "value" }  # Optional: environment variables (${VAR} expansion supported)
```

### File locations

| File | Purpose | Created by |
|------|---------|------------|
| `~/.config/mcpfind/mcpfind.toml` | Global config (shared across projects) | `mcpfind setup` |
| `./mcpfind.toml` | Project-local config (overrides/extends global) | `mcpfind init` |
| `~/.cache/mcpfind/embeddings.json` | Cached tool embeddings (auto-managed) | auto |
| `./mfu.db` | MFU usage tracking (when `mfu_persist = true`) | auto |

### Embedding cache

MCPFind caches tool embeddings to `~/.cache/mcpfind/embeddings.json` to avoid recomputing them on every restart. The cache is keyed by server name, tool name, and description — if any tool changes, only that entry is re-embedded. To clear the cache:

```bash
rm ~/.cache/mcpfind/embeddings.json
```

## CLI Reference

```bash
# Interactive setup — creates global config at ~/.config/mcpfind/mcpfind.toml
mcpfind setup

# Create project-local config — creates ./mcpfind.toml with project-specific servers
mcpfind init

# Start the proxy server (loads global + local config automatically)
mcpfind serve

# Start with a specific config file (skips merging)
mcpfind serve --config path/to/config.toml

# List all discovered tools
mcpfind list-tools

# Test semantic search
mcpfind search "query" --max-results 10
```

## Development

```bash
# Clone and install
git clone https://github.com/jcgs2503/mcp-lens.git
cd mcp-lens
uv sync

# Run tests
uv run pytest -v

# Lint and format
uv run ruff check .
uv run black --check .
```
