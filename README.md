# Autoresearch

Autonomous research framework powered by AI coding agent CLIs.
Adapts [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch)
— replacing GPU training runs with LLM agent calls for deep, iterative research
on any topic. Supports **Claude**, **Codex**, **Gemini**, and **Copilot** backends
with **multi-backend strategies** for scientific validation: ensemble research,
adversarial review, serial refinement, and specialist routing.

## The Pattern

Karpathy's original autoresearch runs an infinite loop on a GPU: modify code,
train for 5 minutes, measure loss, keep or revert. This framework applies the
same loop to knowledge research:

```plaintext
LOOP FOREVER:
  1. Hypothesis  — Agent picks the next dimension to investigate
  2. Execute     — Agent researches it (web search, docs, analysis)
  3. Score       — Heuristic + LLM judge evaluate findings
  4. Decide      — Score improved? KEEP and merge. Otherwise: DISCARD.
  5. Log         — Append to results.tsv, save iteration file
  6. Compress    — Every N iterations, distill the knowledge base
```

Each iteration produces a scored, self-contained markdown file. Findings that
beat the current best are merged into a growing knowledge base. On exit
(`Ctrl+C`) or via `--synthesize`, a final report is generated.

## Architecture

### Main Loop

```mermaid
flowchart TD
    START([cli.py --config topic.yaml]) --> INIT[Load config + check backends]
    INIT --> STRAT[Build strategy<br>single / ensemble / adversarial /<br>parallel / serial / specialist]
    STRAT --> CHECK{--resume flag?}
    CHECK -->|Yes| RESUME[Rebuild state from<br>iterations/ + results.tsv]
    CHECK -->|No| FRESH[Initialize empty<br>knowledge base]
    RESUME --> LOOP
    FRESH --> LOOP

    LOOP[[INFINITE LOOP]] --> HYPO

    subgraph ITERATION ["Each Iteration"]
        HYPO[1. HYPOTHESIS<br>primary backend<br>Pick next dimension]
        HYPO --> EXHAUST{Dimension<br>exhausted?}
        EXHAUST -->|Yes, 3+ attempts| SKIP_DIM[Skip, mark explored]
        EXHAUST -->|No| EXEC
        SKIP_DIM --> HYPO
        EXEC[2. EXECUTE<br>strategy.execute_research&#40;&#41;<br>single / parallel / serial]
        EXEC --> CRIT{Post-research?}
        CRIT -->|Adversarial| CRITIQUE[Critique by<br>adversary backend]
        CRIT -->|No| CRASH
        CRITIQUE --> CRASH
        CRASH{Crash?}
        CRASH -->|Yes| LOG_CRASH[Log crash<br>Track attempt count]
        CRASH -->|No| SCORE
        LOG_CRASH --> LOOP
        SCORE[3. SCORE<br>judge backend<br>Heuristic 40% + Judge 60%]
        SCORE --> DECIDE{total > best?}
        DECIDE -->|KEEP| MERGE[Merge findings<br>into knowledge_base.md]
        DECIDE -->|DISCARD| SAVE[Save iteration file<br>but don't merge]
        MERGE --> LOG
        SAVE --> LOG
        LOG[4. LOG to results.tsv]
    end

    LOG --> RATE{Rate limited?}
    RATE -->|>90%| WAIT_LONG[Backoff 120s]
    RATE -->|>80%| WAIT_SHORT[Cooldown 30s]
    RATE -->|OK| COMPRESS
    WAIT_LONG --> COMPRESS
    WAIT_SHORT --> COMPRESS
    COMPRESS{Every N iters?}
    COMPRESS -->|Yes| SHRINK[Compress knowledge base<br>utility backend]
    COMPRESS -->|No| LOOP
    SHRINK --> LOOP

    LOOP -.->|Ctrl+C or max_iterations| SYNTH[Generate synthesis.md<br>primary backend]
    SYNTH --> DONE([Print summary + exit])

    style LOOP fill:#f59e0b,color:#000
    style MERGE fill:#22c55e,color:#000
    style SAVE fill:#94a3b8,color:#000
    style LOG_CRASH fill:#ef4444,color:#fff
    style SYNTH fill:#3b82f6,color:#fff
    style WAIT_LONG fill:#f97316,color:#000
    style STRAT fill:#8b5cf6,color:#fff
    style CRITIQUE fill:#f59e0b,color:#000
```

### Single Iteration

```mermaid
sequenceDiagram
    participant O as orchestrator.py
    participant S as Strategy
    participant P as Primary Backend
    participant R as Research Backend(s)
    participant J as Judge Backend
    participant FS as File System

    O->>FS: Read knowledge_base.md
    O->>FS: Read prompts/hypothesis.md

    Note over O: Render prompt template<br>with knowledge summary

    O->>P: hypothesis (prompt, max_turns=3)
    P-->>O: JSON: {dimension, questions, approach}

    O->>O: Check dimension attempt count

    O->>FS: Read prompts/research.md
    O->>S: strategy.execute_research(prompt)

    alt Single / Specialist
        S->>R: one backend researches
        R-->>S: Markdown findings
    else Ensemble / Parallel
        S->>R: backends research in parallel
        R-->>S: multiple findings (pick best or merge)
    else Serial
        S->>R: drafter backend researches
        R-->>S: draft findings
        S->>R: refiner backend deepens draft
        R-->>S: refined findings
    end
    S-->>O: ResearchResult

    opt Adversarial strategy
        O->>S: strategy.post_research(findings)
        S->>R: adversary critiques findings
        R-->>S: critique text
        S-->>O: CritiqueResult (appended to findings)
    end

    O->>O: Heuristic score (regex patterns, counting)

    O->>FS: Read prompts/evaluate.md
    O->>J: judge backend scores findings
    J-->>O: JSON: {depth, accuracy, novelty, actionability}

    O->>O: Combine: 0.4 * heuristic + 0.6 * judge

    alt total_score > best_score
        O->>FS: Append findings to knowledge_base.md
        O->>FS: Write iter_NNN.md (status: keep)
    else total_score <= best_score
        O->>FS: Write iter_NNN.md (status: discard)
    end

    O->>FS: Append row to results.tsv
```

## Quick Start

```bash
uv sync

# Run with Claude (default backend, single strategy)
uv run python -m src.cli --config configs/aws_api_gateway.yaml

# Run with a different backend
uv run python -m src.cli --config configs/aws_api_gateway.yaml --backend codex

# Multi-backend: ensemble (parallel research + blind review)
uv run python -m src.cli --config configs/smoke_test_ensemble.yaml

# Multi-backend: adversarial (research + critique + adjudication)
uv run python -m src.cli --config configs/smoke_test_adversarial.yaml

# Override strategy from CLI
uv run python -m src.cli --config configs/aws_api_gateway.yaml --strategy ensemble

# Resume a previous session
uv run python -m src.cli --config configs/aws_api_gateway.yaml --resume

# Generate synthesis from existing iterations
uv run python -m src.cli --config configs/aws_api_gateway.yaml --synthesize
```

## Requirements

- Python 3.10+
- At least one supported AI coding CLI installed and authenticated:
  - [Claude Code](https://claude.ai/download) (`claude`)
  - [OpenAI Codex](https://developers.openai.com/codex) (`codex`)
  - [Google Gemini CLI](https://github.com/google-gemini/gemini-cli) (`gemini`)
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) (`copilot`)

## Project Structure

```plaintext
autoresearch/
    src/
        cli.py              Entry point (--config, --backend, --strategy, --resume, --synthesize)
        config.py           YAML config loader with frozen dataclasses
        backend.py          Backend ABC + Claude, Codex, Gemini, Copilot implementations
        orchestrator.py     AutoResearcher class — the infinite loop
        scorer.py           Heuristic scoring + LLM-as-judge
        strategy.py         Multi-backend strategies (ensemble, adversarial, serial, etc.)
    configs/
        aws_api_gateway.yaml        Demo: AWS API Gateway comparison
        _template.yaml              Copy this for new research topics
        smoke_test_claude.yaml      Single-backend smoke tests
        smoke_test_ensemble.yaml    Multi-backend smoke tests
        smoke_test_adversarial.yaml
        smoke_test_serial.yaml
        smoke_test_specialist.yaml
    prompts/
        hypothesis.md       Picks next dimension to explore (returns JSON)
        research.md         Deep research with web search tools
        evaluate.md         LLM judge: depth, accuracy, novelty, actionability
        synthesize.md       Final report generation
        critique.md         Adversarial critique of findings
        refine.md           Serial refinement of draft findings
        merge.md            Merge parallel research outputs
    tests/                  Test suite (pytest, 160 tests)
    output/                 Runtime artifacts (gitignored)
        <config-name>/
            results.tsv         Experiment log (TSV)
            knowledge_base.md   Accumulated findings
            iterations/         Per-iteration markdown files
            synthesis.md        Final synthesized report
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
        backend: claude        # claude, codex, gemini, or copilot
        model: sonnet          # see model reference below
        max_iterations: 0
        max_turns: 10
        max_budget_per_call: 0.50
        timeout_seconds: 600
        compress_every: 5
    ```

3. Run: `uv run python -m src.cli --config configs/your_topic.yaml`

## Configuration Reference

| Field | Default | Description |
|-------|---------|-------------|
| `topic` | (required) | The research question |
| `goal` | same as topic | Description of desired output |
| `dimensions` | `[]` | Dimensions to explore |
| `backend` | `claude` | CLI backend: `claude`, `codex`, `gemini`, or `copilot` |
| `model` | `sonnet` | Model name (backend-specific, see table below) |
| `max_iterations` | `0` | Max iterations (`0` = infinite) |
| `max_turns` | `10` | Agent turns per research call |
| `max_budget_per_call` | `0.50` | USD cap per invocation (Claude only) |
| `timeout_seconds` | `600` | Timeout per invocation in seconds |
| `compress_every` | `5` | Compress knowledge base every N iterations |
| `allowed_tools` | `WebSearch,...` | Tools available to the research agent |
| `strategy` | `single` | Multi-backend strategy (see below) |
| `backends.primary` | same as `backend` | Backend for hypothesis + synthesis |
| `backends.research` | same as `backend` | Backend(s) for research execution |
| `backends.judge` | same as primary | Backend for scoring (blind review) |
| `backends.utility` | same as primary | Backend for compression (cheapest) |
| `min_dimensions_per_iteration` | `1` | Min dimensions expected per iteration |
| `target_dimensions_total` | `10` | Target total dimensions to cover |
| `evidence_types` | see template | Evidence types for heuristic scoring |

### Models by Backend

| Backend | Top Model | Recommended | Budget |
|---------|-----------|-------------|--------|
| **claude** | `opus` | `sonnet` | `haiku` |
| **codex** | `gpt-5.4` | `gpt-5.4-mini` | `gpt-5.3-codex` |
| **gemini** | `gemini-3.1-pro-preview` | `gemini-3-flash-preview` | `gemini-2.5-flash` |
| **copilot** | `claude-opus-4.6` | `claude-sonnet-4.6` | `gpt-5.4-mini` |

## How Scoring Works

```mermaid
flowchart LR
    subgraph HEURISTIC ["Heuristic Score (40%)"]
        H1[Dimensions covered<br>vs config list]
        H2[Evidence types<br>tables / pricing / code /<br>diagrams / trade-offs]
        H3[New questions<br>discovered]
        H4[Word count<br>vs 500-word target]
        H1 & H2 & H3 & H4 --> HS[coverage_score<br>0-100]
    end

    subgraph JUDGE ["LLM Judge Score (60%)"]
        J1[depth: 1-10]
        J2[accuracy: 1-10]
        J3[novelty: 1-10]
        J4[actionability: 1-10]
        J1 & J2 & J3 & J4 --> JS[quality_score<br>0-100]
    end

    HS --> TOTAL["total_score<br>0.4 * coverage + 0.6 * quality"]
    JS --> TOTAL
    TOTAL --> CMP{"> best_score?"}
    CMP -->|Yes| KEEP["KEEP<br>merge to knowledge base"]
    CMP -->|No| DISCARD["DISCARD<br>save file, skip merge"]

    style KEEP fill:#22c55e,color:#000
    style DISCARD fill:#ef4444,color:#fff
```

**Heuristic (40%)** — deterministic, fast:
- Dimensions covered vs config list
- Evidence types found (tables, pricing, code, trade-offs)
- New questions discovered
- Substantive word count

**LLM Judge (60%)** — qualitative, via a separate agent call:
- Depth (1-10): beyond surface-level feature lists?
- Accuracy (1-10): verifiable facts, qualified claims?
- Novelty (1-10): new information vs prior knowledge base?
- Actionability (1-10): could a decision-maker act on this?

Combined: `total = 0.4 * heuristic + 0.6 * judge`. If `total > best_score`,
findings are merged into the knowledge base (**KEEP**). Otherwise, the iteration
file is saved but findings are not merged (**DISCARD**).

## Multi-Backend Strategies

By default, one backend handles every phase. Multi-backend strategies assign
different backends to different roles, applying scientific validation
principles: independent replication and blind peer review.

### Strategy Overview

| Strategy | Execution | Cost | Best For |
|----------|-----------|------|----------|
| **single** | One backend for everything | 1x | Simple runs, single provider |
| **ensemble** | 2 backends research in parallel | ~1.5x | Default for quality — replication + blind review |
| **adversarial** | Research + critique + adjudication | ~1.3x | Accuracy on hallucination-prone topics |
| **parallel** | All backends independently | Nx | High-stakes completeness |
| **serial** | Draft by cheap backend, refined by precise one | ~1.5x | Depth over breadth |
| **specialist** | Route dimensions by keyword match | 1x | Heterogeneous dimensions |

### Ensemble Strategy

```mermaid
flowchart LR
    PROMPT[Research Prompt] --> PAR

    subgraph PAR ["Parallel Execution"]
        A[Backend A<br>e.g. Claude]
        B[Backend B<br>e.g. Codex]
    end

    A --> RA[Findings A]
    B --> RB[Findings B]

    RA --> SEL{Pick best<br>or merge}
    RB --> SEL

    SEL --> FINDINGS[Best Findings]
    FINDINGS --> JUDGE[Judge Backend<br>different from A and B<br>blind review]
    JUDGE --> SCORE[Score]

    style PAR fill:#dbeafe,color:#000
    style JUDGE fill:#fef3c7,color:#000
    style SEL fill:#f59e0b,color:#000
```

Two backends research the same dimension independently.  A **different**
backend scores the findings without knowing which backend produced them
— blind peer review.  Eliminates self-confirmation bias.

### Adversarial Strategy

```mermaid
flowchart LR
    PROMPT[Research Prompt] --> RES[Researcher<br>e.g. Codex]
    RES --> FINDINGS[Findings]
    FINDINGS --> ADV[Adversary<br>e.g. Claude]
    ADV --> CRITIQUE[Critique:<br>errors, gaps,<br>unsupported claims]
    FINDINGS --> COMBINED[Findings +<br>Critique]
    CRITIQUE --> COMBINED
    COMBINED --> JUDGE[Judge Backend<br>sees both]
    JUDGE --> SCORE[Score]

    style RES fill:#dbeafe,color:#000
    style ADV fill:#fecaca,color:#000
    style JUDGE fill:#fef3c7,color:#000
```

One backend researches. A second backend critiques the findings for
factual errors and gaps. The judge sees both findings and critique.

### Serial Strategy

```mermaid
flowchart LR
    PROMPT[Research Prompt] --> DRAFT[Drafter<br>e.g. Codex<br>fast / cheap]
    DRAFT --> D[Draft Findings]
    D --> REFINE[Refiner<br>e.g. Claude<br>precise / deep]
    PROMPT --> REFINE
    REFINE --> FINAL[Refined Findings]
    FINAL --> JUDGE[Judge Backend]
    JUDGE --> SCORE[Score]

    style DRAFT fill:#d1fae5,color:#000
    style REFINE fill:#dbeafe,color:#000
    style JUDGE fill:#fef3c7,color:#000
```

A fast/cheap backend does a broad sweep. A precise/expensive backend
reads the draft and deepens, corrects, and adds nuance.

### Specialist Strategy

```mermaid
flowchart TD
    DIM[Dimension Name] --> ROUTE{Keyword<br>Match}
    ROUTE -->|code, SDK, API| CODEX[Codex]
    ROUTE -->|pricing, comparison| GEMINI[Gemini]
    ROUTE -->|architecture, trade-off| CLAUDE[Claude]
    ROUTE -->|no match| PRIMARY[Primary Backend]

    CODEX --> RESEARCH[Research Findings]
    GEMINI --> RESEARCH
    CLAUDE --> RESEARCH
    PRIMARY --> RESEARCH

    style ROUTE fill:#f59e0b,color:#000
```

Routes each dimension to the backend best suited for it based on keyword
matching. No duplication — just smarter routing.

### Backend Role Assignment

The key principle: **the judge must be a different provider than the
researchers** to avoid self-confirmation bias.

| Role | Ideal Backend | Why |
|------|---------------|-----|
| **primary** (hypothesis, synthesis) | claude | Best strategic reasoning |
| **research** | codex + gemini | Independent replication across providers |
| **judge** | claude | Blind review — never touched the research |
| **utility** (compress) | gemini | Cheapest, mechanical task |

### Multi-Backend Config Example

```yaml
research:
  topic: "Your research question"
  execution:
    backend: claude
    strategy: ensemble
    backends:
      primary: claude           # hypothesis + synthesis (best reasoner)
      research:                 # independent replication
        - codex
        - gemini
      judge: claude             # blind review (different provider than researchers)
      utility: gemini           # compression (cheapest)
    strategy_config:
      merge_mode: best          # best | union
      stagger_seconds: 5        # delay between parallel launches
```

## Resilience

```mermaid
flowchart TD
    CALL[Backend CLI call] --> RC{Return code}
    RC -->|rc=0| PARSE[Parse JSON response]
    RC -->|rc=1| CHECK_RL{Rate limit<br>in stdout?}

    CHECK_RL -->|utilization >= 90%| WAIT120[Sleep 120s]
    CHECK_RL -->|utilization >= 80%| WAIT30[Sleep 30s]
    CHECK_RL -->|No rate limit| LOG_ERR[Log error]

    WAIT120 --> RETURN_ERR[Return is_error=True]
    WAIT30 --> RETURN_ERR
    LOG_ERR --> RETURN_ERR

    PARSE --> CHECK_OK{utilization<br>in response?}
    CHECK_OK -->|>= 90%| COOL120[Proactive cooldown 120s]
    CHECK_OK -->|>= 80%| COOL30[Proactive cooldown 30s]
    CHECK_OK -->|< 80%| RETURN_OK[Return result]
    COOL120 --> RETURN_OK
    COOL30 --> RETURN_OK

    CALL -->|TimeoutExpired| RETURN_ERR

    style WAIT120 fill:#f97316,color:#000
    style WAIT30 fill:#fbbf24,color:#000
    style RETURN_ERR fill:#ef4444,color:#fff
    style RETURN_OK fill:#22c55e,color:#000
```

- **Crash recovery**: Dimensions are retried up to 3 times, then skipped.
- **Resume**: `--resume` rebuilds state from existing iteration files and TSV.
- **Rate limiting**: Detects rate limit events (Claude), backs off 30-120s.
- **Budget cap**: `--max-budget-usd` per call prevents runaway costs (Claude).
- **Large prompts**: Piped via stdin to avoid the Windows 32KB command-line limit.
- **Graceful shutdown**: `Ctrl+C` generates a synthesis report before exiting.
- **Config validation**: Model, budget, timeout, and required fields are validated
  on load with clear error messages.

## Mapping to the Original

| Karpathy's autoresearch | This framework |
|-------------------------|----------------|
| `train.py` (model code) | Research config YAML |
| `uv run train.py` | `<backend> -p - --model <model>` |
| `val_bpb` (lower = better) | `total_score` (higher = better) |
| `git commit` / `git reset` | Merge / skip findings in knowledge base |
| `results.tsv` | `results.tsv` (same pattern, research metrics) |
| `program.md` | Orchestrator + prompt templates |
| 5-minute time budget | `--max-turns` + `--timeout` per call |
| Single GPU | Any supported AI CLI (no hardware required) |

## Demo Results: AWS API Gateway

The included demo config (`configs/aws_api_gateway.yaml`) was run to completion:

- **13 iterations** across 3 sessions
- **3 kept** (scores: 85.2, 89.5, 92.5)
- Dimensions covered: REST vs HTTP API, WebSocket API, authentication,
  rate limiting, integration patterns, observability, deployment, cost modeling
- Final synthesis: 400+ lines, architect-grade comparison report
- Total cost: ~$2 (run with Claude backend)

```bash
uv run python -m src.cli --config configs/aws_api_gateway.yaml --synthesize
```

## Running Tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

160 tests covering all modules (backend, config, scorer, orchestrator, cli, strategy).

## Related Projects

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — the original GPU-based framework
