# tau-bench: Tool-selection Accuracy Under scale

Measures how well LLMs select the correct tool as the number of available
tools grows, comparing **raw MCP** (all schemas in context) vs **MCPFind**
(semantic search proxy).

## Modes

| Mode | What it measures | API keys needed |
|------|-----------------|-----------------|
| `recall` | Search recall & MRR — does the correct tool appear in top-k? | None (local) or `OPENAI_API_KEY` (openai embedder) |
| `raw` | LLM accuracy with all tool schemas in context | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| `mcpfind` | LLM accuracy with only search results in context | LLM key + optionally `OPENAI_API_KEY` for openai embedder |
| `both` | Runs raw + mcpfind | LLM key |

## Quick start

```bash
# Search recall only — free, no API keys needed (uses local embeddings)
python benchmarks/tau-bench/run.py --mode recall

# Compare local vs OpenAI embeddings on recall
python benchmarks/tau-bench/run.py --mode recall --embedder local
python benchmarks/tau-bench/run.py --mode recall --embedder openai

# Full benchmark (needs ANTHROPIC_API_KEY)
python benchmarks/tau-bench/run.py --mode both --model claude-sonnet-4-20250514

# MCPFind mode with OpenAI embeddings
python benchmarks/tau-bench/run.py --mode mcpfind --embedder openai

# Custom scales
python benchmarks/tau-bench/run.py --mode recall --scales 20,100,500,1000
```

## What it measures

Given a natural language task (e.g., "send an email to John"), can the model
pick the correct tool out of N available tools?

| Metric | Mode | Description |
|--------|------|-------------|
| **recall@k** | recall | Was the correct tool in the top-k search results? |
| **MRR** | recall | Mean Reciprocal Rank of the correct tool |
| **accuracy** | raw, mcpfind | Did the LLM select the correct tool? |
| **tokens_prompt** | raw, mcpfind | Input tokens consumed |
| **tokens_completion** | raw, mcpfind | Output tokens consumed |
| **latency_ms** | raw, mcpfind | End-to-end response time |

## Tool corpus

`tools.py` generates realistic tool definitions:

- **Target tools**: 20 real tools across 5 servers (gmail, github, slack,
  filesystem, calendar) — these are the correct answers for tasks
- **Distractor tools**: Configurable number of plausible-but-irrelevant tools
  generated from 40 servers x 15 actions x 30 entities (~18K unique pool)

Scale points: **20, 50, 100, 200, 500, 1000** total tools.

## Tasks

`tasks.json` defines 30 query/expected-tool pairs across categories:
communication, dev-tools, files, scheduling.

## Embedding providers

| Provider | Model | Dimensions | Cost | Speed |
|----------|-------|-----------|------|-------|
| `local` | all-MiniLM-L6-v2 (fastembed) | 384 | Free | ~10-50ms/batch |
| `openai` | text-embedding-3-small | 1536 | ~$0.02/1M tokens | ~100-500ms/batch |

## Output

Results are saved as JSON in `results/`. Example summary:

```
==============================================================================
RESULTS SUMMARY
==============================================================================

Embedder              Scale  Recall@k    MRR   k
--------------------------------------------------
local                    20      100%  1.000   5
local                   200       93%  0.870   5
local                  1000       87%  0.720   5
openai                   20      100%  1.000   5
openai                  200       97%  0.940   5
openai                 1000       93%  0.850   5
==============================================================================
```
