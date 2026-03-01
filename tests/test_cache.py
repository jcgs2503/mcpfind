"""Tests for embedding disk cache."""

from unittest.mock import MagicMock

from mcpfind.index.cache import (
    _cache_key,
    _load_cache,
    _save_cache,
    embed_with_cache,
)
from mcpfind.models import ToolEntry


def _make_entry(server="s", name="t", desc="d"):
    return ToolEntry(server=server, name=name, description=desc, full_schema={})


def test_cache_key_stable():
    k1 = _cache_key("s", "t", "desc")
    k2 = _cache_key("s", "t", "desc")
    assert k1 == k2


def test_cache_key_changes_with_description():
    k1 = _cache_key("s", "t", "desc v1")
    k2 = _cache_key("s", "t", "desc v2")
    assert k1 != k2


def test_load_cache_missing_file(tmp_path):
    assert _load_cache(tmp_path / "nope.json") == {}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "sub" / "cache.json"
    data = {"abc": [1.0, 2.0, 3.0]}
    _save_cache(path, data)
    loaded = _load_cache(path)
    assert loaded == data


def test_embed_with_cache_all_misses(tmp_path):
    cache_path = tmp_path / "cache.json"
    entries = [_make_entry("gmail", "send", "Send an email")]
    client = MagicMock()
    client.embed_batch.return_value = [[0.1, 0.2, 0.3]]

    embed_with_cache(entries, client, cache_path=cache_path)

    assert entries[0].embedding == [0.1, 0.2, 0.3]
    client.embed_batch.assert_called_once()
    assert cache_path.exists()


def test_embed_with_cache_all_hits(tmp_path):
    cache_path = tmp_path / "cache.json"
    entries = [_make_entry("gmail", "send", "Send an email")]

    # Warm the cache
    client = MagicMock()
    client.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    embed_with_cache(entries, client, cache_path=cache_path)

    # Second call should hit cache, no embed_batch needed
    entries2 = [_make_entry("gmail", "send", "Send an email")]
    client2 = MagicMock()
    embed_with_cache(entries2, client2, cache_path=cache_path)

    assert entries2[0].embedding == [0.1, 0.2, 0.3]
    client2.embed_batch.assert_not_called()


def test_embed_with_cache_partial_hit(tmp_path):
    cache_path = tmp_path / "cache.json"

    # Warm cache with one entry
    client = MagicMock()
    client.embed_batch.return_value = [[1.0, 2.0]]
    embed_with_cache([_make_entry("a", "t1", "d1")], client, cache_path=cache_path)

    # Now request two entries — one cached, one new
    entries = [_make_entry("a", "t1", "d1"), _make_entry("b", "t2", "d2")]
    client2 = MagicMock()
    client2.embed_batch.return_value = [[3.0, 4.0]]
    embed_with_cache(entries, client2, cache_path=cache_path)

    assert entries[0].embedding == [1.0, 2.0]  # from cache
    assert entries[1].embedding == [3.0, 4.0]  # freshly embedded
    client2.embed_batch.assert_called_once_with(["t2: d2"])
