# CLAUDE.md — MCPLens: Context-Efficient MCP Tool Proxy

## What You're Building

An MCP server that sits between any MCP client and N backend MCP servers. Instead of exposing all tool schemas to the agent (which bloats context linearly with toolspace size), MCPLens exposes **3 meta-tools**: `search_tools`, `get_tool_schema`, and `call_tool`. Agents discover tools via semantic vector search, pull schemas on demand, and call tools through the proxy. Context stays ~500 tokens regardless of whether there are 10 or 1,000 tools behind the proxy.

```
Agent (any MCP client)
  │  Sees only: search_tools, get_tool_schema, call_tool (~500 tokens)
  │
  ▼
MCPLens Proxy (this project)
  ├── Vector Index: embeddings of all tool names + descriptions
  ├── MFU Cache: frequently used tools get priority in search results
  ├── Schema Cache: full tool schemas served on demand
  └── Router: validates + routes call_tool to correct backend MCP server
  │
  ├──▶ Gmail MCP Server
  ├──▶ Calendar MCP Server
  ├──▶ GitHub MCP Server
  ├──▶ Slack MCP Server
  └──▶ ... N MCP servers
```

MCPLens itself is an MCP server (stdio transport). Any MCP client (Claude Desktop, Cursor, Claude Code, custom agents) can use it by pointing at MCPLens instead of individual servers. Zero framework lock-in.

## Why This Exists

As MCP toolspaces grow, every current approach dumps all tool schemas into the agent's context:

- 10 tools: ~2K tokens. Fine.
- 50 tools: ~10K tokens. Manageable.
- 200 tools: ~40K tokens. Crowded. Agent starts picking wrong tools.
- 1000 tools: ~200K tokens. Unusable. Eats entire context window.

LangChain's `langgraph-bigtool` solves this but is framework-locked to LangGraph. Nullplatform's `meta-mcp-proxy` does it with fuzzy string matching (poor semantic recall). Neither has benchmarks.

MCPLens: framework-agnostic, vector search, MFU cache, benchmarked.

## The Three Meta-Tools

These are the ONLY tools the agent sees in its context:

```python
# 1. search_tools — find relevant tools by natural language query
{
    "name": "search_tools",
    "description": "Search available tools by natural language description. Returns tool names, servers, and short descriptions. Use this first to discover what tools are available for your task.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language description of what you want to do, e.g. 'send email', 'create calendar event', 'search files'"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of tools to return (default: 5)",
                "default": 5
            },
            "agent_id": {
                "type": "string",
                "description": "Agent identifier for personalized ranking. Agents that call certain tools frequently will see those tools ranked higher. Optional — defaults to 'default'."
            }
        },
        "required": ["query"]
    }
}

# 2. get_tool_schema — pull full input schema for a specific tool
{
    "name": "get_tool_schema",
    "description": "Get the full input schema for a specific tool. Use after search_tools to get the exact parameters needed before calling a tool.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name from search_tools results"},
            "tool": {"type": "string", "description": "Tool name from search_tools results"}
        },
        "required": ["server", "tool"]
    }
}

# 3. call_tool — execute a tool on a backend MCP server
{
    "name": "call_tool",
    "description": "Execute a tool on a connected MCP server. Use get_tool_schema first to know the required arguments.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name"},
            "tool": {"type": "string", "description": "Tool name"},
            "arguments": {"type": "object", "description": "Tool arguments matching the schema"},
            "agent_id": {"type": "string", "description": "Agent identifier for usage tracking (optional)"}
        },
        "required": ["server", "tool", "arguments"]
    }
}
```

## Architecture

### Vector Index

On startup, MCPLens connects to all configured MCP servers, calls `list_tools` on each, and builds a vector index:

```python
@dataclass
class ToolEntry:
    server: str          # "gmail", "github", "slack"
    name: str            # "send_email", "create_issue", "post_message"
    description: str     # original tool description from MCP server
    full_schema: dict    # complete inputSchema, stored but NOT sent to agent
    embedding: list[float]  # vector embedding of "{name}: {description}"
```

Embedding model: `text-embedding-3-small` (1536 dims, ~$0.02/1M tokens, <100ms latency). For 1000 tools with ~50 word descriptions, total embedding cost is <$0.001 one-time on startup.

Storage: in-memory numpy array for cosine similarity. No vector DB dependency. At 1000 tools × 1536 dims, the matrix is ~6MB. Search is a single matrix multiply — sub-millisecond.

### MFU (Most Frequently Used) Cache

Observation: in practice, agents repeatedly use a small subset of tools. If someone uses `gmail:send` 50 times, it should appear at the top of search results for email-related queries without needing perfect embedding similarity.

The MFU cache is **per-agent**:
- Each agent builds its own usage profile
- `boost_weight` of 0.15 means semantic relevance still drives results, but frequently used tools break ties

### MCP Server Lifecycle

On startup:
1. Spawn each configured MCP server subprocess (stdio transport) or connect (SSE)
2. Call `list_tools` on each
3. Embed all tool descriptions (batched API call to embedding model)
4. Build vector index
5. Start MCPLens as an MCP server (stdio) exposing the 3 meta-tools

## Configuration

```toml
# mcplens.toml

[proxy]
embedding_model = "text-embedding-3-small"
mfu_boost_weight = 0.15
mfu_persist = true
default_max_results = 5

[[servers]]
name = "gmail"
command = "uvx"
args = ["mcp-gmail"]
env = { GMAIL_TOKEN = "${GMAIL_TOKEN}" }

[[servers]]
name = "github"
command = "uvx"
args = ["mcp-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

## Project Structure

```
mcplens/
├── pyproject.toml
├── CLAUDE.md
├── README.md
├── mcplens.toml.example
├── src/mcplens/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── proxy/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── tools.py
│   │   └── router.py
│   ├── index/
│   │   ├── __init__.py
│   │   ├── embeddings.py
│   │   ├── vector.py
│   │   └── mfu.py
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   ├── connection.py
│   │   └── discovery.py
│   └── models.py
├── tests/
│   ├── test_vector.py
│   ├── test_mfu.py
│   ├── test_proxy.py
│   └── test_router.py
└── bench/
    ├── README.md
    ├── tool_padding.py
    ├── run_benchmark.py
    └── results/
```

## Stack

Python 3.12+ · uv · mcp SDK · openai (embeddings only) · numpy · click · tomli · pytest
