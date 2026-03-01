"""MCPFind MCP proxy server."""

import logging
from pathlib import Path

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcpfind.backend.discovery import discover_all_tools
from mcpfind.backend.manager import BackendManager
from mcpfind.index.embeddings import create_embedding_client
from mcpfind.index.mfu import MFUCache
from mcpfind.index.vector import VectorIndex
from mcpfind.models import ProxyConfig
from mcpfind.proxy.router import Router
from mcpfind.proxy.tools import META_TOOLS

logger = logging.getLogger(__name__)


async def run_proxy(config: ProxyConfig) -> None:
    """Start the MCPFind proxy server."""

    # Start backend connections
    manager = BackendManager(config.servers)
    await manager.start_all()

    try:
        # Discover all tools
        entries = await discover_all_tools(manager)
        logger.info("Discovered %d tools total", len(entries))

        # Embed tool descriptions (with disk cache)
        embedding_client = create_embedding_client(
            provider=config.embedding_provider, model=config.embedding_model
        )
        if entries:
            from mcpfind.index.cache import embed_with_cache

            embed_with_cache(entries, embedding_client)

        # Build vector index
        index = VectorIndex()
        index.build(entries)

        # Initialize MFU cache
        mfu_path = Path("mfu.db") if config.mfu_persist else None
        mfu_cache = MFUCache(
            boost_weight=config.mfu_boost_weight, persist_path=mfu_path
        )

        # Initialize router
        router = Router(
            backend_manager=manager,
            vector_index=index,
            mfu_cache=mfu_cache,
            embedding_client=embedding_client,
            tool_entries=entries,
            default_max_results=config.default_max_results,
        )

        # Create MCP server
        app = Server("mcpfind")

        @app.list_tools()
        async def list_tools():
            return META_TOOLS

        @app.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "search_tools":
                return await router.handle_search(arguments)
            elif name == "get_tool_schema":
                return await router.handle_get_schema(arguments)
            elif name == "call_tool":
                return await router.handle_call(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

        # Run server
        logger.info("MCPFind proxy server starting...")
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        await manager.stop_all()
