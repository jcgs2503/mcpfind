"""Tests for the router with mocked dependencies."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcplens.index.mfu import MFUCache
from mcplens.index.vector import VectorIndex
from mcplens.models import ToolEntry
from mcplens.proxy.router import Router


@pytest.fixture
def tool_entries():
    return [
        ToolEntry(
            server="gmail",
            name="send_email",
            description="Send an email",
            full_schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            embedding=[1.0, 0.0, 0.0],
        ),
        ToolEntry(
            server="github",
            name="create_issue",
            description="Create a GitHub issue",
            full_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["repo", "title"],
            },
            embedding=[0.0, 1.0, 0.0],
        ),
        ToolEntry(
            server="slack",
            name="post_message",
            description="Post a message to Slack",
            full_schema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
            embedding=[0.0, 0.0, 1.0],
        ),
    ]


@pytest.fixture
def router(tool_entries):
    # Mock embedding client
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [1.0, 0.0, 0.0]  # Similar to gmail

    # Real vector index
    index = VectorIndex()
    index.build(tool_entries)

    # Real MFU cache (no persistence)
    mfu = MFUCache(boost_weight=0.15)

    # Mock backend manager
    mock_backend = AsyncMock()

    return Router(
        backend_manager=mock_backend,
        vector_index=index,
        mfu_cache=mfu,
        embedding_client=mock_embeddings,
        tool_entries=tool_entries,
        default_max_results=5,
    )


@pytest.mark.asyncio
async def test_search_returns_results(router):
    result = await router.handle_search({"query": "send email"})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert len(data) == 3
    # gmail:send_email should be top result (embedding matches query)
    assert data[0]["server"] == "gmail"
    assert data[0]["name"] == "send_email"


@pytest.mark.asyncio
async def test_search_respects_max_results(router):
    result = await router.handle_search({"query": "send email", "max_results": 1})
    data = json.loads(result[0].text)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_schema_returns_full_schema(router):
    result = await router.handle_get_schema({"server": "gmail", "tool": "send_email"})
    schema = json.loads(result[0].text)
    assert schema["type"] == "object"
    assert "to" in schema["properties"]
    assert "subject" in schema["properties"]


@pytest.mark.asyncio
async def test_get_schema_not_found(router):
    result = await router.handle_get_schema(
        {"server": "nonexistent", "tool": "fake_tool"}
    )
    data = json.loads(result[0].text)
    assert "error" in data


@pytest.mark.asyncio
async def test_call_tool_routes_to_backend(router):
    mock_content = MagicMock()
    mock_content.text = "Email sent!"
    router._backend.call_tool.return_value = [mock_content]

    result = await router.handle_call(
        {
            "server": "gmail",
            "tool": "send_email",
            "arguments": {
                "to": "test@example.com",
                "subject": "Hello",
                "body": "World",
            },
        }
    )

    router._backend.call_tool.assert_called_once_with(
        "gmail",
        "send_email",
        {"to": "test@example.com", "subject": "Hello", "body": "World"},
    )
    assert result[0].text == "Email sent!"


@pytest.mark.asyncio
async def test_call_tool_records_mfu(router):
    mock_content = MagicMock()
    mock_content.text = "OK"
    router._backend.call_tool.return_value = [mock_content]

    await router.handle_call(
        {
            "server": "gmail",
            "tool": "send_email",
            "arguments": {},
            "agent_id": "test_agent",
        }
    )

    counts = router._mfu.get_counts("test_agent")
    assert counts["gmail:send_email"] == 1


@pytest.mark.asyncio
async def test_call_tool_handles_error(router):
    router._backend.call_tool.side_effect = Exception("Connection failed")

    result = await router.handle_call(
        {"server": "gmail", "tool": "send_email", "arguments": {}}
    )

    data = json.loads(result[0].text)
    assert "error" in data
    assert "Connection failed" in data["error"]
