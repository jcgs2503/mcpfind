"""Meta-tool definitions and schemas for the MCPFind proxy."""

from mcp.types import Tool

SEARCH_TOOLS = Tool(
    name="search_tools",
    description=(
        "Search available tools by natural language description. "
        "Returns tool names, servers, and short descriptions. "
        "Use this first to discover what tools are available for your task."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural language description of what you want to do, "
                    "e.g. 'send email', 'create calendar event', 'search files'"
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of tools to return (default: 5)",
                "default": 5,
            },
            "agent_id": {
                "type": "string",
                "description": (
                    "Agent identifier for personalized ranking. "
                    "Optional — defaults to 'default'."
                ),
            },
        },
        "required": ["query"],
    },
)

GET_TOOL_SCHEMA = Tool(
    name="get_tool_schema",
    description=(
        "Get the full input schema for a specific tool. "
        "Use after search_tools to get the exact parameters needed "
        "before calling a tool."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Server name from search_tools results",
            },
            "tool": {
                "type": "string",
                "description": "Tool name from search_tools results",
            },
        },
        "required": ["server", "tool"],
    },
)

CALL_TOOL = Tool(
    name="call_tool",
    description=(
        "Execute a tool on a connected MCP server. "
        "Use get_tool_schema first to know the required arguments."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name"},
            "tool": {"type": "string", "description": "Tool name"},
            "arguments": {
                "type": "object",
                "description": "Tool arguments matching the schema",
            },
            "agent_id": {
                "type": "string",
                "description": "Agent identifier for usage tracking (optional)",
            },
        },
        "required": ["server", "tool", "arguments"],
    },
)

META_TOOLS = [SEARCH_TOOLS, GET_TOOL_SCHEMA, CALL_TOOL]
