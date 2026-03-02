#!/usr/bin/env python3
"""tau-bench: Tool-selection Accuracy Under scale.

Benchmarks LLM tool selection accuracy as toolspace scales,
comparing raw MCP (all schemas in context) vs MCPFind (search proxy).

Modes:
  recall  — search recall only (no API keys needed, fast)
  raw     — all tool schemas in LLM context (needs LLM API key)
  mcpfind — semantic search then LLM picks (needs LLM API key)
  both    — raw + mcpfind
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tools import (
    TARGET_TOOLS,
    format_tool_schema_for_prompt,
    generate_corpus,
)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

RAW_SYSTEM = """\
You are a helpful assistant with access to the following tools.
When the user asks you to do something, respond with a JSON object
containing the tool you would call.

Available tools:

{tool_schemas}

Respond with ONLY a JSON object in this exact format, nothing else:
{{"server": "<server_name>", "tool": "<tool_name>"}}"""

MCPFIND_SYSTEM = """\
You are a helpful assistant. You have access to a tool proxy with these meta-tools:

1. list_servers() — List all connected MCP servers and tool counts.
2. search_tools(query, server?) — Search tools by natural language.
3. get_tool_schema(server, tool) — Get full input schema for a tool.
4. call_tool(server, tool, arguments) — Execute a tool.

The user will ask you to do something. First, decide which tool to use
by calling search_tools with a relevant query. Then respond with the
tool you would call.

Respond with ONLY a JSON object in this exact format, nothing else:
{{"server": "<server_name>", "tool": "<tool_name>"}}

Here are the search results for the user's request:

{search_results}"""

# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------


def _call_anthropic(
    model: str, system: str, user_msg: str
) -> tuple[str, int, int, float]:
    """Call Anthropic API. Returns (text, prompt_tok, comp_tok, ms)."""
    import anthropic

    client = anthropic.Anthropic()
    t0 = time.monotonic()
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    latency = (time.monotonic() - t0) * 1000
    text = resp.content[0].text
    return (
        text,
        resp.usage.input_tokens,
        resp.usage.output_tokens,
        latency,
    )


def _call_openai(model: str, system: str, user_msg: str) -> tuple[str, int, int, float]:
    """Call OpenAI API. Returns (text, prompt_tok, comp_tok, ms)."""
    import openai

    client = openai.OpenAI()
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        max_tokens=256,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    latency = (time.monotonic() - t0) * 1000
    text = resp.choices[0].message.content
    return (
        text,
        resp.usage.prompt_tokens,
        resp.usage.completion_tokens,
        latency,
    )


def call_llm(model: str, system: str, user_msg: str) -> tuple[str, int, int, float]:
    """Route to the correct API based on model name."""
    if model.startswith("claude"):
        return _call_anthropic(model, system, user_msg)
    elif model.startswith("gpt") or model.startswith("o"):
        return _call_openai(model, system, user_msg)
    else:
        raise ValueError(f"Unknown model provider for: {model}")


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

_embedding_cache: dict[str, object] = {}


def _get_embedder(provider: str):
    """Get or create an embedding model. Cached to avoid re-init."""
    if provider in _embedding_cache:
        return _embedding_cache[provider]

    if provider == "local":
        from fastembed import TextEmbedding

        model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        _embedding_cache[provider] = model
        return model
    elif provider == "openai":
        import openai

        client = openai.OpenAI()
        _embedding_cache[provider] = client
        return client
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


def embed_texts(texts: list[str], provider: str):
    """Embed a list of texts. Returns numpy array of shape (n, dim)."""
    import numpy as np

    if provider == "local":
        model = _get_embedder("local")
        return np.array(list(model.embed(texts)), dtype=np.float32)
    elif provider == "openai":
        client = _get_embedder("openai")
        # OpenAI batch limit is 2048, chunk if needed
        all_embs = []
        for i in range(0, len(texts), 2048):
            batch = texts[i : i + 2048]
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            all_embs.extend([d.embedding for d in resp.data])
        return np.array(all_embs, dtype=np.float32)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Search simulation (for MCPFind and recall modes)
# ---------------------------------------------------------------------------


def simulate_mcpfind_search(
    query: str,
    corpus: list[dict],
    k: int = 5,
    embedder: str = "local",
    _corpus_cache: dict | None = None,
) -> list[dict]:
    """Simulate MCPFind search using embeddings.

    Args:
        query: Natural language search query.
        corpus: Tool corpus to search.
        k: Number of results to return.
        embedder: "local" or "openai".
        _corpus_cache: Optional dict to cache corpus embeddings
            across calls (mutated in place).
    """
    import numpy as np

    # Embed corpus (use cache if provided)
    cache_key = f"{embedder}:{len(corpus)}"
    if _corpus_cache is not None and cache_key in _corpus_cache:
        corpus_embs = _corpus_cache[cache_key]
    else:
        texts = [f"{t['name']}: {t['description']}" for t in corpus]
        corpus_embs = embed_texts(texts, embedder)
        norms = np.linalg.norm(corpus_embs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        corpus_embs = corpus_embs / norms
        if _corpus_cache is not None:
            _corpus_cache[cache_key] = corpus_embs

    # Embed query
    query_emb = embed_texts([query], embedder)[0]
    norm = np.linalg.norm(query_emb)
    if norm > 0:
        query_emb = query_emb / norm

    # Cosine similarity
    scores = corpus_embs @ query_emb
    top_k = min(k, len(corpus))
    top_indices = np.argpartition(scores, -top_k)[-top_k:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

    results = []
    for i in top_indices:
        results.append(
            {
                "server": corpus[i]["server"],
                "name": corpus[i]["name"],
                "description": corpus[i]["description"],
                "score": round(float(scores[i]), 4),
            }
        )
    return results


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------


def parse_tool_selection(
    text: str,
) -> tuple[str | None, str | None]:
    """Extract server and tool from LLM response."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return data.get("server"), data.get("tool")
        except json.JSONDecodeError:
            pass
    return None, None


def run_recall_mode(
    tasks: list[dict],
    corpus: list[dict],
    search_k: int = 5,
    embedder: str = "local",
) -> dict:
    """Measure search recall only — no LLM calls needed."""
    corpus_cache: dict = {}
    results = []
    hits = 0

    for i, task in enumerate(tasks):
        query = task["query"]
        label = f"  recall [{i + 1}/{len(tasks)}]"
        print(f"{label} {query[:50]}...", end=" ")
        sys.stdout.flush()

        search_results = simulate_mcpfind_search(
            query,
            corpus,
            k=search_k,
            embedder=embedder,
            _corpus_cache=corpus_cache,
        )

        hit = any(
            r["server"] == task["expected_server"]
            and r["name"] == task["expected_tool"]
            for r in search_results
        )
        if hit:
            hits += 1
            print("HIT")
        else:
            print("MISS")

        # Find rank of correct tool (if present at all)
        rank = None
        for j, r in enumerate(search_results):
            if (
                r["server"] == task["expected_server"]
                and r["name"] == task["expected_tool"]
            ):
                rank = j + 1
                break

        results.append(
            {
                "query": query,
                "expected": (f"{task['expected_server']}:{task['expected_tool']}"),
                "hit": hit,
                "rank": rank,
                "top_results": [
                    f"{r['server']}:{r['name']} ({r['score']})" for r in search_results
                ],
            }
        )

    n = len(tasks)
    # Mean Reciprocal Rank
    mrr_sum = sum(1.0 / r["rank"] for r in results if r["rank"] is not None)
    return {
        "mode": "recall",
        "embedder": embedder,
        "scale": len(corpus),
        "search_k": search_k,
        "tasks": n,
        "recall_at_k": round(hits / n, 4),
        "hits": hits,
        "mrr": round(mrr_sum / n, 4),
        "results": results,
    }


def run_raw_mode(
    model: str,
    tasks: list[dict],
    corpus: list[dict],
) -> dict:
    """Run benchmark in raw MCP mode (all schemas in context)."""
    schemas_text = "\n\n".join(format_tool_schema_for_prompt(t) for t in corpus)
    system = RAW_SYSTEM.format(tool_schemas=schemas_text)

    results = []
    correct = 0
    total_prompt = 0
    total_completion = 0
    total_latency = 0.0

    for i, task in enumerate(tasks):
        label = f"  raw [{i + 1}/{len(tasks)}]"
        print(f"{label} {task['query'][:50]}...", end=" ")
        sys.stdout.flush()

        text, pt, ct, lat = call_llm(model, system, task["query"])
        server, tool = parse_tool_selection(text)

        is_correct = server == task["expected_server"] and tool == task["expected_tool"]
        if is_correct:
            correct += 1
            print("OK")
        else:
            print(f"MISS (got {server}:{tool})")

        total_prompt += pt
        total_completion += ct
        total_latency += lat

        results.append(
            {
                "query": task["query"],
                "expected": (f"{task['expected_server']}:{task['expected_tool']}"),
                "predicted": f"{server}:{tool}",
                "correct": is_correct,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "latency_ms": round(lat, 1),
                "raw_response": text[:200],
            }
        )

    n = len(tasks)
    return {
        "mode": "raw",
        "model": model,
        "scale": len(corpus),
        "tasks": n,
        "accuracy": round(correct / n, 4),
        "correct": correct,
        "avg_prompt_tokens": round(total_prompt / n),
        "avg_completion_tokens": round(total_completion / n),
        "avg_latency_ms": round(total_latency / n, 1),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "results": results,
    }


def run_mcpfind_mode(
    model: str,
    tasks: list[dict],
    corpus: list[dict],
    search_k: int = 5,
    embedder: str = "local",
) -> dict:
    """Run benchmark in MCPFind mode (search then select)."""
    corpus_cache: dict = {}
    results = []
    correct = 0
    total_prompt = 0
    total_completion = 0
    total_latency = 0.0

    for i, task in enumerate(tasks):
        label = f"  mcpfind [{i + 1}/{len(tasks)}]"
        print(f"{label} {task['query'][:50]}...", end=" ")
        sys.stdout.flush()

        search_results = simulate_mcpfind_search(
            task["query"],
            corpus,
            k=search_k,
            embedder=embedder,
            _corpus_cache=corpus_cache,
        )
        search_text = json.dumps(search_results, indent=2)

        system = MCPFIND_SYSTEM.format(search_results=search_text)
        text, pt, ct, lat = call_llm(model, system, task["query"])
        server, tool = parse_tool_selection(text)

        is_correct = server == task["expected_server"] and tool == task["expected_tool"]
        if is_correct:
            correct += 1
            print("OK")
        else:
            print(f"MISS (got {server}:{tool})")

        total_prompt += pt
        total_completion += ct
        total_latency += lat

        search_hit = any(
            r["server"] == task["expected_server"]
            and r["name"] == task["expected_tool"]
            for r in search_results
        )

        results.append(
            {
                "query": task["query"],
                "expected": (f"{task['expected_server']}:{task['expected_tool']}"),
                "predicted": f"{server}:{tool}",
                "correct": is_correct,
                "search_hit": search_hit,
                "search_results": [
                    f"{r['server']}:{r['name']} ({r['score']})" for r in search_results
                ],
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "latency_ms": round(lat, 1),
                "raw_response": text[:200],
            }
        )

    n = len(tasks)
    search_hits = sum(1 for r in results if r.get("search_hit", False))
    return {
        "mode": "mcpfind",
        "model": model,
        "embedder": embedder,
        "scale": len(corpus),
        "search_k": search_k,
        "tasks": n,
        "accuracy": round(correct / n, 4),
        "correct": correct,
        "search_recall": round(search_hits / n, 4),
        "avg_prompt_tokens": round(total_prompt / n),
        "avg_completion_tokens": round(total_completion / n),
        "avg_latency_ms": round(total_latency / n, 1),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_summary(all_results: list[dict]) -> None:
    """Print a summary table of results."""
    print("\n" + "=" * 78)
    print("RESULTS SUMMARY")
    print("=" * 78)

    # Separate recall results from LLM results
    recall_results = [r for r in all_results if r["mode"] == "recall"]
    llm_results = [r for r in all_results if r["mode"] != "recall"]

    if recall_results:
        print(f"\n{'Embedder':<20} {'Scale':>6} {'Recall@k':>9} {'MRR':>6} {'k':>3}")
        print("-" * 50)
        for r in sorted(
            recall_results,
            key=lambda x: (x["embedder"], x["scale"]),
        ):
            print(
                f"{r['embedder']:<20} {r['scale']:>6} "
                f"{r['recall_at_k']:>8.0%} "
                f"{r['mrr']:>6.3f} {r['search_k']:>3}"
            )

    if llm_results:
        print(
            f"\n{'Model':<25} {'Mode':<10} {'Scale':>6} "
            f"{'Acc':>5} {'Prompt':>7} {'Comp':>5} "
            f"{'Lat':>7}"
        )
        print("-" * 78)
        for r in sorted(
            llm_results,
            key=lambda x: (
                x["model"],
                x["mode"],
                x["scale"],
            ),
        ):
            extra = ""
            if r["mode"] == "mcpfind":
                sr = r["search_recall"]
                extra = f"  recall={sr:.0%}"
            print(
                f"{r['model']:<25} {r['mode']:<10} "
                f"{r['scale']:>6} "
                f"{r['accuracy']:>4.0%} "
                f"{r['avg_prompt_tokens']:>7} "
                f"{r['avg_completion_tokens']:>5} "
                f"{r['avg_latency_ms']:>6.0f}ms"
                f"{extra}"
            )

    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(
        description=("tau-bench: Tool-selection Accuracy Under scale")
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to benchmark (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--scales",
        default="20,50,100,200,500",
        help="Comma-separated tool counts (default: 20,50,100,200,500)",
    )
    parser.add_argument(
        "--mode",
        choices=["recall", "raw", "mcpfind", "both"],
        default="both",
        help="Benchmark mode (default: both). "
        "'recall' measures search only — no LLM API key needed.",
    )
    parser.add_argument(
        "--embedder",
        choices=["local", "openai"],
        default="local",
        help="Embedding provider for search (default: local). "
        "'openai' requires OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--search-k",
        type=int,
        default=5,
        help="Number of search results (default: 5)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: benchmarks/tau-bench/results/)",
    )
    parser.add_argument(
        "--tasks",
        default=None,
        help="Path to tasks JSON (default: tasks.json in same dir)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for corpus generation (default: 42)",
    )

    args = parser.parse_args()

    # Load tasks
    tasks_path = args.tasks or (Path(__file__).parent / "tasks.json")
    tasks = json.loads(Path(tasks_path).read_text())
    print(f"Loaded {len(tasks)} tasks")

    scales = [int(s.strip()) for s in args.scales.split(",")]

    if args.mode == "recall":
        modes = ["recall"]
    elif args.mode == "both":
        modes = ["raw", "mcpfind"]
    else:
        modes = [args.mode]

    output_dir = Path(args.output) if args.output else Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    for scale in scales:
        print(f"\n{'=' * 60}")
        print(f"Scale: {scale} tools | Embedder: {args.embedder}")
        print(f"{'=' * 60}")

        corpus = generate_corpus(scale, seed=args.seed)
        n_dist = scale - len(TARGET_TOOLS)
        n_tgt = len(TARGET_TOOLS)
        print(f"Corpus: {n_tgt} target + {n_dist} distractor")

        for mode in modes:
            print(f"\n--- Mode: {mode} ---")

            if mode == "recall":
                result = run_recall_mode(
                    tasks,
                    corpus,
                    search_k=args.search_k,
                    embedder=args.embedder,
                )
            elif mode == "raw":
                result = run_raw_mode(args.model, tasks, corpus)
            else:
                result = run_mcpfind_mode(
                    args.model,
                    tasks,
                    corpus,
                    search_k=args.search_k,
                    embedder=args.embedder,
                )

            all_results.append(result)

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            if mode == "recall":
                label = f"{args.embedder}_recall"
            else:
                label = f"{args.model}_{mode}"
            fname = f"{label}_{scale}_{ts}.json"
            out_path = output_dir / fname
            out_path.write_text(json.dumps(result, indent=2) + "\n")
            print(f"  Saved: {out_path}")

    print_summary(all_results)

    # Save combined summary
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = output_dir / f"summary_{ts}.json"
    summary = {
        "model": args.model,
        "embedder": args.embedder,
        "scales": scales,
        "modes": modes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": [
            {k: v for k, v in r.items() if k != "results"} for r in all_results
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
