"""In-memory vector index for tool search using numpy."""

import numpy as np

from mcplens.models import ToolEntry


class VectorIndex:
    """Cosine similarity search over tool embeddings."""

    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None
        self._entries: list[ToolEntry] = []

    def build(self, entries: list[ToolEntry]) -> None:
        """Build the index from tool entries with pre-computed embeddings."""
        self._entries = entries
        if not entries:
            self._matrix = None
            return
        matrix = np.array([e.embedding for e in entries], dtype=np.float32)
        # Normalize rows for cosine similarity via dot product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        self._matrix = matrix / norms

    def search(
        self, query_embedding: list[float], k: int = 5
    ) -> list[tuple[int, float]]:
        """Search for top-k most similar tools.

        Returns list of (index, score) tuples sorted by descending score.
        """
        if self._matrix is None or len(self._entries) == 0:
            return []

        query = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        scores = self._matrix @ query
        k = min(k, len(self._entries))

        # Use argpartition for efficiency on large arrays
        if k < len(scores):
            top_indices = np.argpartition(scores, -k)[-k:]
        else:
            top_indices = np.arange(len(scores))

        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return [(int(i), float(scores[i])) for i in top_indices]

    def get_entry(self, index: int) -> ToolEntry:
        """Get a tool entry by index."""
        return self._entries[index]
