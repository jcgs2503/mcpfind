"""Disk cache for tool embeddings to avoid recomputing on restart."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "mcpfind" / "embeddings.json"


def _cache_key(server: str, name: str, description: str) -> str:
    """Generate a stable cache key from tool identity + description."""
    content = f"{server}:{name}:{description}"
    return hashlib.sha256(content.encode()).hexdigest()


def _load_cache(path: Path) -> dict[str, list[float]]:
    """Load cached embeddings from disk."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load embedding cache: %s", e)
        return {}


def _save_cache(path: Path, cache: dict[str, list[float]]) -> None:
    """Save embeddings cache to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache))


def embed_with_cache(
    entries: list,
    embedding_client,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> None:
    """Embed tool entries, using disk cache for hits and only computing misses.

    Modifies entries in-place by setting their .embedding field.

    Args:
        entries: List of ToolEntry objects with server, name, description fields.
        embedding_client: An embedding client with embed_batch() method.
        cache_path: Path to the JSON cache file.
    """
    cache = _load_cache(cache_path)

    # Separate hits from misses
    hits = 0
    miss_indices: list[int] = []
    miss_texts: list[str] = []

    for i, entry in enumerate(entries):
        key = _cache_key(entry.server, entry.name, entry.description)
        cached = cache.get(key)
        if cached is not None:
            entry.embedding = cached
            hits += 1
        else:
            miss_indices.append(i)
            miss_texts.append(f"{entry.name}: {entry.description}")

    if hits:
        logger.info("Embedding cache: %d hits, %d misses", hits, len(miss_indices))

    # Embed misses
    if miss_texts:
        new_embeddings = embedding_client.embed_batch(miss_texts)
        for idx, emb in zip(miss_indices, new_embeddings):
            entry = entries[idx]
            entry.embedding = emb
            key = _cache_key(entry.server, entry.name, entry.description)
            cache[key] = emb

        _save_cache(cache_path, cache)
        logger.info("Cached %d new embeddings to %s", len(miss_texts), cache_path)
    elif hits:
        logger.info("All embeddings loaded from cache")
