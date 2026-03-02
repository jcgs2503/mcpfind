# MCPFind

[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

Context-efficient MCP tool proxy with semantic search. MCPFind sits between any MCP client and your backend MCP servers, replacing hundreds of tool schemas in the agent's context with just 3 meta-tools (~500 tokens).

```
Agent (Claude Desktop, Cursor, Claude Code, etc.)
  │  Sees only: list_servers, search_tools, get_tool_schema, call_tool
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

No API key needed — MCPFind uses local embeddings by default.

## Quick Start

### 1. Configure your servers

```bash
mcpfind setup
```

The setup wizard walks you through choosing an embedding provider and adding MCP servers (GitHub, Slack, Filesystem, PostgreSQL, Brave Search, Playwright, and more). Config is saved to `~/.config/mcpfind/mcpfind.toml`.

### 2. Register with your MCP client

```bash
mcpfind install claude-code
mcpfind install cursor
mcpfind install claude-desktop
```

Pick the client you use. That's it — mcpfind is now available as an MCP server.

### 3. Verify (optional)

```bash
# List all tools discovered from your backend servers
mcpfind list-tools

# Test semantic search
mcpfind search "create a pull request"
```

## How It Works

MCPFind exposes 4 tools to the agent:

1. **`list_servers`** — List all connected MCP servers and their tool counts. Use this to see what's available.

2. **`search_tools`** — Find relevant tools by natural language query (e.g., "send an email"). Returns tool names, servers, and descriptions ranked by semantic similarity + usage frequency. Optionally filter to a specific server.

3. **`get_tool_schema`** — Pull the full input schema for a specific tool before calling it. Keeps schemas out of context until actually needed.

4. **`call_tool`** — Execute a tool on a backend server. MCPFind validates and routes the call to the correct server.

### Agent workflow

```
Agent: list_servers()
  → [{"server": "gmail", "tool_count": 5}, {"server": "github", "tool_count": 12}, ...]

Agent: search_tools("create issue", server="github")
  → [{"server": "github", "name": "create_issue", "score": 0.97}, ...]

Agent: get_tool_schema(server="github", tool="create_issue")
  → {"type": "object", "properties": {"repo": ..., "title": ..., "body": ...}}

Agent: call_tool(server="github", tool="create_issue", arguments={...})
  → "Issue created!"
```

### MFU Cache

MCPFind tracks which tools each agent uses most frequently. Frequently used tools get a ranking boost in search results via `mfu_boost_weight` (default: 0.15 — 85% semantic similarity, 15% usage frequency). Set `mfu_persist = true` to save usage data across restarts.

## Project-Specific Servers

Add servers that only apply to the current project:

```bash
cd your-project
mcpfind init
```

This creates a local `mcpfind.toml` in the project directory. When mcpfind starts, it merges global + local configs:

- **Global** (`~/.config/mcpfind/mcpfind.toml`) — your always-available servers and settings
- **Local** (`./mcpfind.toml`) — project-specific servers, merged on top

A local server with the same name as a global one overrides it. Proxy settings (embedding model, MFU weight, etc.) fall back to global if not set locally.

## Configuration Reference

### File locations

| Config | Path | Created by |
|--------|------|------------|
| Global | `~/.config/mcpfind/mcpfind.toml` | `mcpfind setup` |
| Local | `./mcpfind.toml` | `mcpfind init` |

### Format

```toml
[proxy]
embedding_provider = "local"                # "local" (default) or "openai"
embedding_model = "all-MiniLM-L6-v2"        # Model name (provider-specific)
mfu_boost_weight = 0.15                     # Frequency boost weight (0.0-1.0)
mfu_persist = true                          # Persist usage data to SQLite
default_max_results = 5                     # Default number of search results

[[servers]]
name = "github"                  # Required: unique identifier
command = "npx"                  # Required: executable to launch
args = ["-y", "@modelcontextprotocol/server-github"]  # Optional: command arguments
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }             # Optional: env vars (${VAR} expansion)
```

### Using `--config`

All commands default to layered config (global + local). To use a specific config file instead:

```bash
mcpfind serve --config /path/to/mcpfind.toml
mcpfind list-tools --config /path/to/mcpfind.toml
mcpfind search "query" --config /path/to/mcpfind.toml
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `mcpfind setup` | Interactive wizard — configure global config |
| `mcpfind init` | Create project-local `mcpfind.toml` |
| `mcpfind install <client>` | Register mcpfind with an MCP client (`claude-code`, `cursor`, `claude-desktop`) |
| `mcpfind serve` | Start the proxy server (stdio MCP transport) |
| `mcpfind list-tools` | List all discovered tools from backend servers |
| `mcpfind search "<query>"` | Test semantic search against discovered tools |

## Development

```bash
# Clone and install
git clone https://github.com/jcgs2503/mcpfind.git
cd mcpfind
uv sync

# Run tests
uv run pytest -v

# Lint and format
uv run ruff check .
uv run ruff format --check .
```
