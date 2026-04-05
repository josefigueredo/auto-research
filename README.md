# autoresearch-claude

Autonomous research framework powered by Claude Code agents.
Implements [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch)
with LLM agent calls replacing GPU training runs.

## How It Works

```
LOOP FOREVER:
  1. Hypothesis  — Claude picks the next research dimension
  2. Execute     — Claude researches it (web search, docs, analysis)
  3. Score       — Heuristic + LLM judge evaluate the findings
  4. Decide      — If score improved: KEEP and merge. Otherwise: DISCARD.
  5. Log         — Append to results.tsv, save iteration file
```

Press `Ctrl+C` to stop. A synthesis report is generated on exit.

## Quick Start

```bash
# Install
uv sync

# Run with the demo config
uv run python -m src.cli --config configs/aws_api_gateway.yaml

# Resume a previous session
uv run python -m src.cli --config configs/aws_api_gateway.yaml --resume

# Generate synthesis from existing data
uv run python -m src.cli --config configs/aws_api_gateway.yaml --synthesize
```

## Project Structure

```
configs/              Research topic configurations (YAML)
prompts/              Prompt templates for each loop phase
src/
  cli.py              Entry point
  config.py           Config loading and validation
  orchestrator.py     The main research loop
  scorer.py           Heuristic + LLM-as-judge scoring
output/               Runtime artifacts (gitignored)
  results.tsv         Experiment log
  knowledge_base.md   Accumulated findings
  iterations/         Per-iteration markdown files
  synthesis.md        Final report
diagrams.md           Architecture diagrams (Mermaid)
```

## Creating a New Research Topic

1. Copy `configs/_template.yaml` to `configs/your_topic.yaml`.
2. Fill in `topic`, `goal`, and `dimensions`.
3. Run: `uv run python -m src.cli --config configs/your_topic.yaml`

## Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/download) installed and authenticated
- `claude --version` must work from the terminal
