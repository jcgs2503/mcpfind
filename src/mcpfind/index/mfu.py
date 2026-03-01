"""Most Frequently Used (MFU) cache for personalized tool ranking."""

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


class MFUCache:
    """Tracks per-agent tool usage and boosts search scores accordingly."""

    def __init__(
        self, boost_weight: float = 0.15, persist_path: Path | None = None
    ) -> None:
        self._boost_weight = boost_weight
        self._counts: dict[str, Counter[str]] = defaultdict(Counter)
        self._db_path = persist_path
        if self._db_path:
            self._init_db()
            self._load_from_db()

    def _init_db(self) -> None:
        """Initialize SQLite database for persistence."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mfu_counts "
            "(agent_id TEXT, tool_key TEXT, count INTEGER, "
            "PRIMARY KEY (agent_id, tool_key))"
        )
        conn.commit()
        conn.close()

    def _load_from_db(self) -> None:
        """Load counts from SQLite."""
        if not self._db_path:
            return
        conn = sqlite3.connect(str(self._db_path))
        for row in conn.execute("SELECT agent_id, tool_key, count FROM mfu_counts"):
            self._counts[row[0]][row[1]] = row[2]
        conn.close()

    def _persist(self, agent_id: str, tool_key: str) -> None:
        """Persist a single count update to SQLite."""
        if not self._db_path:
            return
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "INSERT OR REPLACE INTO mfu_counts (agent_id, tool_key, count) "
            "VALUES (?, ?, ?)",
            (agent_id, tool_key, self._counts[agent_id][tool_key]),
        )
        conn.commit()
        conn.close()

    def record_call(self, agent_id: str, server: str, tool: str) -> None:
        """Record a tool call for usage tracking."""
        tool_key = f"{server}:{tool}"
        self._counts[agent_id][tool_key] += 1
        self._persist(agent_id, tool_key)

    def boost_scores(
        self,
        agent_id: str,
        results: list[tuple[str, str, float]],
    ) -> list[tuple[str, str, float]]:
        """Blend similarity scores with usage frequency.

        Args:
            agent_id: The agent whose usage profile to apply.
            results: List of (server, tool, similarity_score) tuples.

        Returns:
            Re-scored and re-sorted list of (server, tool, boosted_score) tuples.
        """
        agent_counts = self._counts.get(agent_id)
        if not agent_counts:
            return results

        total_calls = sum(agent_counts.values())
        if total_calls == 0:
            return results

        boosted = []
        for server, tool, score in results:
            tool_key = f"{server}:{tool}"
            freq = agent_counts.get(tool_key, 0) / total_calls
            boosted_score = (1 - self._boost_weight) * score + self._boost_weight * freq
            boosted.append((server, tool, boosted_score))

        boosted.sort(key=lambda x: x[2], reverse=True)
        return boosted

    def get_counts(self, agent_id: str) -> dict[str, int]:
        """Get usage counts for an agent (for debugging/inspection)."""
        return dict(self._counts.get(agent_id, {}))
