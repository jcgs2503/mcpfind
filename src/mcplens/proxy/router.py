"""Router that wires meta-tool calls to backend services."""

import json
import logging

from mcp.types import TextContent

from mcplens.backend.manager import BackendManager
from mcplens.index.embeddings import BaseEmbeddingClient
from mcplens.index.mfu import MFUCache
from mcplens.index.vector import VectorIndex
from mcplens.models import SearchResult, ToolEntry

logger = logging.getLogger(__name__)


class Router:
    """Routes meta-tool calls to the appropriate backend services."""

    def __init__(
        self,
        backend_manager: BackendManager,
        vector_index: VectorIndex,
        mfu_cache: MFUCache,
        embedding_client: BaseEmbeddingClient,
        tool_entries: list[ToolEntry],
        default_max_results: int = 5,
    ) -> None:
        self._backend = backend_manager
        self._index = vector_index
        self._mfu = mfu_cache
        self._embeddings = embedding_client
        self._entries = tool_entries
        self._default_max_results = default_max_results

        # Build lookup for get_tool_schema
        self._schema_lookup: dict[str, dict] = {}
        for entry in tool_entries:
            key = f"{entry.server}:{entry.name}"
            self._schema_lookup[key] = entry.full_schema

    async def handle_search(self, arguments: dict) -> list[TextContent]:
        """Handle search_tools meta-tool call."""
        query = arguments["query"]
        max_results = arguments.get("max_results", self._default_max_results)
        agent_id = arguments.get("agent_id", "default")

        query_embedding = self._embeddings.embed_query(query)
        raw_results = self._index.search(query_embedding, k=max_results)

        # Build results with scores
        scored = []
        for idx, score in raw_results:
            entry = self._index.get_entry(idx)
            scored.append((entry.server, entry.name, score))

        # Apply MFU boost
        boosted = self._mfu.boost_scores(agent_id, scored)

        # Format results
        results = []
        for server, name, score in boosted[:max_results]:
            entry = next(
                e for e in self._entries if e.server == server and e.name == name
            )
            results.append(
                SearchResult(
                    server=server,
                    name=name,
                    description=entry.description,
                    score=round(score, 4),
                )
            )

        output = [
            {
                "server": r.server,
                "name": r.name,
                "description": r.description,
                "score": r.score,
            }
            for r in results
        ]
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    async def handle_get_schema(self, arguments: dict) -> list[TextContent]:
        """Handle get_tool_schema meta-tool call."""
        server = arguments["server"]
        tool = arguments["tool"]
        key = f"{server}:{tool}"

        schema = self._schema_lookup.get(key)
        if schema is None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"Tool '{tool}' not found on server '{server}'"}
                    ),
                )
            ]

        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    async def handle_call(self, arguments: dict) -> list[TextContent]:
        """Handle call_tool meta-tool call."""
        server = arguments["server"]
        tool = arguments["tool"]
        tool_args = arguments["arguments"]
        agent_id = arguments.get("agent_id", "default")

        # Record usage
        self._mfu.record_call(agent_id, server, tool)

        try:
            result_content = await self._backend.call_tool(server, tool, tool_args)
            # Convert MCP content objects to TextContent
            output = []
            for item in result_content:
                if hasattr(item, "text"):
                    output.append(TextContent(type="text", text=item.text))
                else:
                    output.append(TextContent(type="text", text=json.dumps(str(item))))
            return output if output else [TextContent(type="text", text="OK")]
        except Exception as e:
            logger.exception("Error calling %s:%s", server, tool)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}),
                )
            ]
