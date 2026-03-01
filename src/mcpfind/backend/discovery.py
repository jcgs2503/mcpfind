"""Tool discovery across all backend MCP servers."""

import logging

from mcpfind.backend.manager import BackendManager
from mcpfind.models import ToolEntry

logger = logging.getLogger(__name__)


async def discover_all_tools(manager: BackendManager) -> list[ToolEntry]:
    """Discover all tools from all connected backend servers.

    Returns a list of ToolEntry objects (without embeddings — those are
    added later by the embedding client).
    """
    entries: list[ToolEntry] = []

    for name, conn in manager.connections.items():
        try:
            tools = await conn.list_tools()
            for tool in tools:
                entries.append(
                    ToolEntry(
                        server=name,
                        name=tool["name"],
                        description=tool["description"],
                        full_schema=tool.get("inputSchema", {}),
                    )
                )
            logger.info("Discovered %d tools from server '%s'", len(tools), name)
        except Exception:
            logger.exception("Failed to discover tools from server '%s'", name)

    logger.info("Total tools discovered: %d", len(entries))
    return entries
