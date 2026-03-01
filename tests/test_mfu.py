"""Tests for the MFU cache."""

import tempfile
from pathlib import Path

from mcplens.index.mfu import MFUCache


def test_boost_with_no_history():
    cache = MFUCache(boost_weight=0.15)
    results = [("server", "tool_a", 0.9), ("server", "tool_b", 0.8)]
    boosted = cache.boost_scores("agent1", results)
    # No history, scores unchanged
    assert boosted == results


def test_boost_increases_frequent_tool_score():
    cache = MFUCache(boost_weight=0.15)

    # Record many calls to tool_b
    for _ in range(10):
        cache.record_call("agent1", "server", "tool_b")

    results = [
        ("server", "tool_a", 0.9),
        ("server", "tool_b", 0.8),
    ]
    boosted = cache.boost_scores("agent1", results)

    # tool_b should now rank higher due to frequency boost
    assert boosted[0][1] == "tool_b"
    assert boosted[0][2] > 0.8  # Score should be boosted


def test_per_agent_isolation():
    cache = MFUCache(boost_weight=0.15)

    for _ in range(10):
        cache.record_call("agent1", "server", "tool_a")

    results = [("server", "tool_a", 0.5), ("server", "tool_b", 0.9)]

    # agent1 should get tool_a boosted
    boosted_agent1 = cache.boost_scores("agent1", results)

    # agent2 should have no boost — scores unchanged from input
    boosted_agent2 = cache.boost_scores("agent2", results)
    assert boosted_agent2 == results  # No change for unknown agent

    # agent1: tool_a = 0.85*0.5 + 0.15*1.0 = 0.575
    #         tool_b = 0.85*0.9 + 0.15*0.0 = 0.765
    # tool_b still wins, but tool_a score is boosted
    assert boosted_agent1[0][1] == "tool_b"
    tool_a_boosted = next(s for _, n, s in boosted_agent1 if n == "tool_a")
    assert tool_a_boosted > 0.5


def test_boost_weight_effect():
    """Higher boost_weight gives more weight to frequency."""
    results = [
        ("server", "tool_a", 0.5),
        ("server", "tool_b", 0.9),
    ]

    # With low boost weight
    cache_low = MFUCache(boost_weight=0.1)
    for _ in range(10):
        cache_low.record_call("agent", "server", "tool_a")
    boosted_low = cache_low.boost_scores("agent", results)

    # With high boost weight
    cache_high = MFUCache(boost_weight=0.5)
    for _ in range(10):
        cache_high.record_call("agent", "server", "tool_a")
    boosted_high = cache_high.boost_scores("agent", results)

    # tool_a should get a bigger boost with higher weight
    tool_a_low = next(s for _, n, s in boosted_low if n == "tool_a")
    tool_a_high = next(s for _, n, s in boosted_high if n == "tool_a")
    assert tool_a_high > tool_a_low


def test_sqlite_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_mfu.db"

        # Write some data
        cache1 = MFUCache(boost_weight=0.15, persist_path=db_path)
        cache1.record_call("agent1", "server", "tool_a")
        cache1.record_call("agent1", "server", "tool_a")
        cache1.record_call("agent1", "server", "tool_b")

        # Load in a new instance
        cache2 = MFUCache(boost_weight=0.15, persist_path=db_path)
        counts = cache2.get_counts("agent1")
        assert counts["server:tool_a"] == 2
        assert counts["server:tool_b"] == 1


def test_get_counts():
    cache = MFUCache(boost_weight=0.15)
    cache.record_call("agent1", "gmail", "send")
    cache.record_call("agent1", "gmail", "send")
    cache.record_call("agent1", "github", "create_issue")

    counts = cache.get_counts("agent1")
    assert counts == {"gmail:send": 2, "github:create_issue": 1}
    assert cache.get_counts("unknown_agent") == {}
