"""Manages connections to all backend MCP servers."""

import logging

from mcpfind.backend.connection import MCPConnection
from mcpfind.models import ServerConfig

logger = logging.getLogger(__name__)


class BackendManager:
    """Spawns and manages all configured backend MCP servers."""

    def __init__(self, server_configs: list[ServerConfig]) -> None:
        self._configs = server_configs
        self._connections: dict[str, MCPConnection] = {}

    async def start_all(self) -> None:
        """Connect to all configured backend servers."""
        for config in self._configs:
            conn = MCPConnection(config)
            try:
                await conn.connect()
                self._connections[config.name] = conn
                logger.info("Connected to server '%s'", config.name)
            except Exception:
                logger.exception("Failed to connect to server '%s'", config.name)

    async def stop_all(self) -> None:
        """Close all backend connections."""
        for name, conn in self._connections.items():
            try:
                await conn.close()
                logger.info("Disconnected from server '%s'", name)
            except Exception:
                logger.exception("Error closing connection to '%s'", name)
        self._connections.clear()

    def get_connection(self, server_name: str) -> MCPConnection:
        """Get a connection by server name."""
        if server_name not in self._connections:
            raise KeyError(f"No connection to server '{server_name}'")
        return self._connections[server_name]

    async def call_tool(self, server: str, tool: str, arguments: dict) -> list:
        """Call a tool on a specific backend server."""
        conn = self.get_connection(server)
        return await conn.call_tool(tool, arguments)

    @property
    def connections(self) -> dict[str, MCPConnection]:
        return self._connections
