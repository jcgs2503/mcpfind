"""Embedding client wrapping OpenAI's embedding API."""

from openai import OpenAI


class EmbeddingClient:
    """Generates text embeddings via OpenAI's API."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self._client = OpenAI()
        self._model = model
        self._cache: dict[str, list[float]] = {}

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Used at startup for all tool descriptions."""
        if not texts:
            return []
        response = self._client.embeddings.create(input=texts, model=self._model)
        embeddings = [item.embedding for item in response.data]
        for text, emb in zip(texts, embeddings):
            self._cache[text] = emb
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string, with caching."""
        if query in self._cache:
            return self._cache[query]
        response = self._client.embeddings.create(input=[query], model=self._model)
        embedding = response.data[0].embedding
        self._cache[query] = embedding
        return embedding
