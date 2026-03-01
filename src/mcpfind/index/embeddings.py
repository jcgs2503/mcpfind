"""Embedding client with local (fastembed) and OpenAI backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbeddingClient(ABC):
    """Abstract embedding client interface."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""


class LocalEmbeddingClient(BaseEmbeddingClient):
    """Generates embeddings locally using fastembed (ONNX-based)."""

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model)
        self._cache: dict[str, list[float]] = {}

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = [emb.tolist() for emb in self._model.embed(texts)]
        for text, emb in zip(texts, embeddings):
            self._cache[text] = emb
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        if query in self._cache:
            return self._cache[query]
        embedding = list(self._model.embed([query]))[0].tolist()
        self._cache[query] = embedding
        return embedding


class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """Generates embeddings via OpenAI's API. Requires OPENAI_API_KEY."""

    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI

        self._client = OpenAI()
        self._model = model
        self._cache: dict[str, list[float]] = {}

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(input=texts, model=self._model)
        embeddings = [item.embedding for item in response.data]
        for text, emb in zip(texts, embeddings):
            self._cache[text] = emb
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        if query in self._cache:
            return self._cache[query]
        response = self._client.embeddings.create(input=[query], model=self._model)
        embedding = response.data[0].embedding
        self._cache[query] = embedding
        return embedding


def create_embedding_client(
    provider: str = "local", model: str | None = None
) -> BaseEmbeddingClient:
    """Create an embedding client based on provider.

    Args:
        provider: "local" (default, uses fastembed) or "openai".
        model: Model name override. Defaults to "all-MiniLM-L6-v2" for local,
               "text-embedding-3-small" for openai.
    """
    if provider == "openai":
        return OpenAIEmbeddingClient(model=model or "text-embedding-3-small")
    else:
        return LocalEmbeddingClient(model=model or "all-MiniLM-L6-v2")
