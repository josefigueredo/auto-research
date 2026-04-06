# autoresearch-claude

Autonomous research framework powered by Claude Code agents.
Adapts [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch)
— replacing GPU training runs with LLM agent calls for deep, iterative research
on any topic.

## The Pattern

Karpathy's original autoresearch runs an infinite loop on a GPU: modify code,
train for 5 minutes, measure loss, keep or revert. This framework applies the
same loop to knowledge research:

```
LOOP FOREVER:
  1. Hypothesis  — Claude picks the next dimension to investigate
  2. Execute     — Claude researches it (web search, docs, analysis)
  3. Score       — Heuristic + LLM judge evaluate findings
  4. Decide      — Score improved? KEEP and merge. Otherwise: DISCARD.
  5. Log         — Append to results.tsv, save iteration file
  6. Compress    — Every N iterations, distill the knowledge base
```

Each iteration produces a scored, self-contained markdown file. Findings that
beat the current best are merged into a growing knowledge base. On exit
(`Ctrl+C`) or via `--synthesize`, a final report is generated.

## Quick Start

```bash
# Install dependencies
uv sync

# Run with the demo config (AWS API Gateway comparison)
uv run python -m src.cli --config configs/aws_api_gateway.yaml

# Resume a previous session
uv run python -m src.cli --config configs/aws_api_gateway.yaml --resume

# Generate a synthesis report from existing iterations
uv run python -m src.cli --config configs/aws_api_gateway.yaml --synthesize

# Verbose logging
uv run python -m src.cli --config configs/aws_api_gateway.yaml -v
```

## Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/download) installed and authenticated
- `claude --version` must work from the terminal

## Project Structure

```
autoresearch-claude/
    src/
        cli.py              Entry point (--config, --resume, --synthesize, -v)
        config.py           YAML config loader with frozen dataclasses
        orchestrator.py     AutoResearcher class — the infinite loop
        scorer.py           Heuristic scoring + LLM-as-judge
    configs/
        aws_api_gateway.yaml   Demo: AWS API Gateway comparison
        _template.yaml         Copy this for new research topics
    prompts/
        hypothesis.md       Picks next dimension to explore (returns JSON)
        research.md         Deep research with web search tools
        evaluate.md         LLM judge: depth, accuracy, novelty, actionability
        synthesize.md       Final report generation
    output/                 Runtime artifacts (gitignored)
        <config-name>/
            results.tsv         Experiment log (TSV)
            knowledge_base.md   Accumulated findings
            iterations/         Per-iteration markdown files
            synthesis.md        Final synthesized report
    diagrams.md            Architecture diagrams (Mermaid)
    autoresearch_runner.py CPU-only local test of the loop pattern (numpy)
```

## Creating a New Research Topic

1. Copy `configs/_template.yaml` to `configs/your_topic.yaml`.
2. Fill in the fields:

```yaml
research:
  topic: "Your research question"
  goal: "What the final deliverable should look like"
  dimensions:
    - "First dimension to explore"
    - "Second dimension to explore"
  execution:
    model: sonnet             # sonnet (default), opus, or haiku
    max_iterations: 0         # 0 = infinite
    max_turns: 10             # claude agent turns per research call
    max_budget_per_call: 0.50 # USD cap per invocation
    timeout_seconds: 600      # per-call timeout
    compress_every: 5         # compress knowledge base every N iterations
```

3. Run: `uv run python -m src.cli --config configs/your_topic.yaml`

## Configuration Reference

| Field | Default | Description |
|-------|---------|-------------|
| `topic` | (required) | The research question |
| `goal` | same as topic | Description of desired output |
| `dimensions` | `[]` | List of dimensions to explore |
| `model` | `sonnet` | Claude model: `sonnet`, `opus`, or `haiku` |
| `max_iterations` | `0` | Max iterations (0 = infinite) |
| `max_turns` | `10` | Agent turns per research call |
| `max_budget_per_call` | `0.50` | USD cap per Claude invocation |
| `timeout_seconds` | `600` | Timeout per invocation in seconds |
| `compress_every` | `5` | Compress knowledge base every N iterations |
| `allowed_tools` | `WebSearch,...` | Tools available to the research agent |
| `min_dimensions_per_iteration` | `1` | Min dimensions expected per iteration |
| `target_dimensions_total` | `10` | Target total dimensions to cover |
| `evidence_types` | see template | Evidence types for heuristic scoring |

## How Scoring Works

Each iteration is scored on two axes:

**Heuristic (40%)** — deterministic, fast:
- Dimensions covered vs config list
- Evidence types found (tables, pricing, code, trade-offs)
- New questions discovered
- Substantive word count

**LLM Judge (60%)** — qualitative, via a separate Claude call:
- Depth (1-10): beyond surface-level feature lists?
- Accuracy (1-10): verifiable facts, qualified claims?
- Novelty (1-10): new information vs prior knowledge base?
- Actionability (1-10): could a decision-maker act on this?

Combined: `total = 0.4 * heuristic + 0.6 * judge`. If `total > best_score`,
findings are merged into the knowledge base (KEEP). Otherwise, the iteration
file is saved but findings are not merged (DISCARD).

## Resilience Features

- **Crash recovery**: Dimensions are retried up to 3 times, then skipped.
- **Resume**: `--resume` rebuilds state from existing iteration files.
- **Rate limiting**: Detects Claude CLI rate limit events, backs off 30-120s.
- **Budget cap**: `--max-budget-usd` on every Claude call prevents runaway costs.
- **Large prompts**: Prompts are piped via stdin, avoiding Windows 32KB
  command-line limits.
- **Graceful shutdown**: `Ctrl+C` generates a synthesis report before exiting.

## Mapping to the Original Autoresearch

| Karpathy's autoresearch | This framework |
|-------------------------|----------------|
| `train.py` (model code) | Research config YAML |
| `uv run train.py` | `claude -p - --model sonnet` |
| `val_bpb` (lower = better) | `total_score` (higher = better) |
| `git commit` / `git reset` | Merge / skip findings in knowledge base |
| `results.tsv` | `results.tsv` (same pattern, research metrics) |
| `program.md` | Orchestrator + prompt templates |
| 5-minute time budget | `--max-turns` + `--timeout` per call |
| Single GPU | Claude Code CLI (no hardware required) |

## Demo Results: AWS API Gateway

The included demo config (`configs/aws_api_gateway.yaml`) was run to completion.
Results:

- **13 iterations** across 3 sessions
- **3 kept** (scores: 85.2, 89.5, 92.5)
- Dimensions covered: REST vs HTTP API, WebSocket API, authentication,
  rate limiting, integration patterns, observability, deployment, cost modeling
- Final synthesis: 400+ lines, architect-grade comparison report
- Total cost: ~$2 in Claude API usage

The synthesis report is generated via:
```bash
uv run python -m src.cli --config configs/aws_api_gateway.yaml --synthesize
```

## Related Projects

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — the original GPU-based framework
- [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx) — Windows RTX adaptation for consumer GPUs
