# tau-bench: Tool-selection Accuracy Under scale

Measures how well LLMs select the correct tool as the number of available
tools grows, comparing **raw MCP** (all schemas in context) vs **MCPFind**
(semantic search proxy).

## What it measures

Given a natural language task (e.g., "send an email to John"), can the model
pick the correct tool out of N available tools?

| Metric | Description |
|--------|-------------|
| **accuracy** | Did the model select the correct tool? |
| **tokens_prompt** | Input tokens consumed |
| **tokens_completion** | Output tokens consumed |
| **latency_ms** | End-to-end response time |

## How it works

```
                        ┌─────────────────────────┐
                        │  Task Corpus (tasks.json)│
                        │  "send email" → gmail:   │
                        │     send_email            │
                        └────────────┬──────────────┘
                                     │
               ┌─────────────────────┴──────────────────────┐
               ▼                                            ▼
     ┌─────────────────┐                          ┌─────────────────┐
     │   Raw MCP Mode  │                          │  MCPFind Mode   │
     │                 │                          │                 │
     │ System prompt:  │                          │ System prompt:  │
     │ All N tool      │                          │ 4 meta-tools    │
     │ schemas         │                          │ (~500 tokens)   │
     │                 │                          │                 │
     │ "Pick a tool"   │                          │ Turn 1: search  │
     │                 │                          │ Turn 2: schema  │
     │                 │                          │ Turn 3: call    │
     └────────┬────────┘                          └────────┬────────┘
              │                                            │
              ▼                                            ▼
     ┌──────────────────────────────────────────────────────┐
     │              Results (results/*.json)                 │
     │  accuracy, tokens, latency per (mode, scale, model)  │
     └──────────────────────────────────────────────────────┘
```

## Tool corpus

`tools.py` generates realistic tool definitions:

- **Target tools**: 20 real tools across 5 servers (gmail, github, slack,
  filesystem, calendar) that are the correct answers for tasks
- **Distractor tools**: Configurable number of plausible-but-irrelevant tools
  generated from a pool of ~50 server/tool templates. Names and descriptions
  are varied so they aren't trivially distinguishable from targets.

Scale points: **10, 50, 100, 200, 500, 1000** total tools.

## Tasks

`tasks.json` defines query → expected tool pairs:

```json
{
  "query": "send an email to the engineering team about the release",
  "expected_server": "gmail",
  "expected_tool": "send_email",
  "category": "communication"
}
```

30 tasks across categories: communication, dev-tools, files, scheduling, search.

## Running

```bash
# Install benchmark dependencies
uv pip install anthropic openai

# Run full benchmark
python benchmarks/tau-bench/run.py

# Run specific model / scale
python benchmarks/tau-bench/run.py --model claude-sonnet-4-20250514 --scales 10,100,500

# Run only mcpfind mode
python benchmarks/tau-bench/run.py --mode mcpfind

# Output to specific directory
python benchmarks/tau-bench/run.py --output benchmarks/tau-bench/results/
```

## Output

Results are saved as JSON:

```json
{
  "model": "claude-sonnet-4-20250514",
  "mode": "raw",
  "scale": 200,
  "tasks": 30,
  "accuracy": 0.73,
  "avg_prompt_tokens": 42150,
  "avg_completion_tokens": 85,
  "avg_latency_ms": 2340,
  "results": [...]
}
```
