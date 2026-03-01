"""Tests for the vector index."""

import numpy as np

from mcplens.index.vector import VectorIndex
from mcplens.models import ToolEntry


def _make_entry(server: str, name: str, embedding: list[float]) -> ToolEntry:
    return ToolEntry(
        server=server,
        name=name,
        description=f"{name} description",
        full_schema={},
        embedding=embedding,
    )


def test_empty_index_returns_nothing():
    index = VectorIndex()
    index.build([])
    results = index.search([1.0, 0.0, 0.0], k=5)
    assert results == []


def test_search_returns_correct_ranking():
    # Create entries with known embeddings
    entries = [
        _make_entry("s1", "tool_a", [1.0, 0.0, 0.0]),
        _make_entry("s1", "tool_b", [0.0, 1.0, 0.0]),
        _make_entry("s2", "tool_c", [0.7, 0.7, 0.0]),
    ]
    index = VectorIndex()
    index.build(entries)

    # Query similar to tool_a
    results = index.search([1.0, 0.0, 0.0], k=3)

    assert len(results) == 3
    # tool_a should be first (exact match)
    assert results[0][0] == 0
    assert results[0][1] > 0.99
    # tool_c should be second (partial match)
    assert results[1][0] == 2


def test_search_respects_k():
    entries = [
        _make_entry("s", f"tool_{i}", [float(i == j) for j in range(5)])
        for i in range(5)
    ]
    index = VectorIndex()
    index.build(entries)

    results = index.search([1.0, 0.0, 0.0, 0.0, 0.0], k=2)
    assert len(results) == 2


def test_get_entry():
    entry = _make_entry("server1", "my_tool", [1.0, 0.0])
    index = VectorIndex()
    index.build([entry])

    retrieved = index.get_entry(0)
    assert retrieved.server == "server1"
    assert retrieved.name == "my_tool"


def test_search_with_random_embeddings():
    """Test with higher-dimensional embeddings to simulate real usage."""
    rng = np.random.default_rng(42)
    dim = 64
    n_tools = 20

    entries = []
    for i in range(n_tools):
        emb = rng.standard_normal(dim).tolist()
        entries.append(_make_entry("server", f"tool_{i}", emb))

    index = VectorIndex()
    index.build(entries)

    # Search with first tool's embedding — should return itself as top result
    results = index.search(entries[0].embedding, k=5)
    assert results[0][0] == 0
    assert results[0][1] > 0.99
