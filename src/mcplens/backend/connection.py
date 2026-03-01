"""MCP client connection to a single backend server."""

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcplens.models import ServerConfig


class MCPConnection:
    """Wraps a connection to a single MCP backend server."""

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None

    @property
    def name(self) -> str:
        return self._config.name

    async def connect(self) -> None:
        """Establish connection to the backend MCP server."""
        server_params = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=self._config.env if self._config.env else None,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

    async def list_tools(self) -> list[dict]:
        """List all tools available on this server."""
        if self._session is None:
            raise RuntimeError(f"Not connected to server '{self._config.name}'")
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": (
                    tool.inputSchema if hasattr(tool, "inputSchema") else {}
                ),
            }
            for tool in result.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> list:
        """Call a tool on this server and return the result content."""
        if self._session is None:
            raise RuntimeError(f"Not connected to server '{self._config.name}'")
        result = await self._session.call_tool(tool_name, arguments)
        return result.content

    async def close(self) -> None:
        """Close the connection."""
        await self._exit_stack.aclose()
