# Architecture Diagrams

Render these with any Mermaid-compatible viewer: VS Code Mermaid extension,
[mermaid.live](https://mermaid.live), or GitHub markdown preview.

## 1. Main Loop

```mermaid
flowchart TD
    START([cli.py --config topic.yaml]) --> INIT[Load config + check claude CLI]
    INIT --> CHECK{--resume flag?}
    CHECK -->|Yes| RESUME[Rebuild state from<br>iterations/ + results.tsv]
    CHECK -->|No| FRESH[Initialize empty<br>knowledge base]
    RESUME --> LOOP
    FRESH --> LOOP

    LOOP[[INFINITE LOOP]] --> HYPO

    subgraph ITERATION ["Each Iteration (~3 Claude calls)"]
        HYPO[1. HYPOTHESIS<br>claude -p - &#60;stdin<br>Pick next dimension]
        HYPO --> EXHAUST{Dimension<br>exhausted?}
        EXHAUST -->|Yes, 3+ attempts| SKIP_DIM[Skip, mark explored]
        EXHAUST -->|No| EXEC
        SKIP_DIM --> HYPO
        EXEC[2. EXECUTE<br>claude --model sonnet<br>WebSearch + WebFetch]
        EXEC --> CRASH{Crash?}
        CRASH -->|Yes| LOG_CRASH[Log crash<br>Track attempt count]
        CRASH -->|No| SCORE
        LOG_CRASH --> LOOP
        SCORE[3. SCORE<br>Heuristic 40% + Judge 60%]
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
    COMPRESS -->|Yes| SHRINK[Compress knowledge base]
    COMPRESS -->|No| LOOP
    SHRINK --> LOOP

    LOOP -.->|Ctrl+C or max_iterations| SYNTH[Generate synthesis.md]
    SYNTH --> DONE([Print summary + exit])

    style LOOP fill:#f59e0b,color:#000
    style MERGE fill:#22c55e,color:#000
    style SAVE fill:#94a3b8,color:#000
    style LOG_CRASH fill:#ef4444,color:#fff
    style SYNTH fill:#3b82f6,color:#fff
    style WAIT_LONG fill:#f97316,color:#000
```

## 2. Single Iteration — Sequence Diagram

```mermaid
sequenceDiagram
    participant O as orchestrator.py
    participant C as Claude CLI<br>(stdin pipe)
    participant FS as File System

    O->>FS: Read knowledge_base.md
    O->>FS: Read prompts/hypothesis.md

    Note over O: Render prompt template<br>with knowledge summary

    O->>C: echo prompt | claude -p -<br>--model sonnet --max-budget-usd 0.50
    C-->>O: JSON: {dimension, questions, approach}

    O->>O: Check dimension attempt count

    O->>FS: Read prompts/research.md
    O->>C: echo prompt | claude -p -<br>--model sonnet --allowedTools WebSearch,...
    Note over C: Agent searches web,<br>fetches docs, cross-references
    C-->>O: Markdown findings

    O->>O: Heuristic score (regex patterns, counting)

    O->>FS: Read prompts/evaluate.md
    O->>C: echo prompt | claude -p -<br>--model sonnet (judge call)
    C-->>O: JSON: {depth, accuracy, novelty, actionability}

    O->>O: Combine: 0.4 * heuristic + 0.6 * judge

    alt total_score > best_score
        O->>FS: Append findings to knowledge_base.md
        O->>FS: Write iter_NNN.md (status: keep)
    else total_score <= best_score
        O->>FS: Write iter_NNN.md (status: discard)
    end

    O->>FS: Append row to results.tsv
    O->>O: Check rate limit utilization
```

## 3. Scoring System

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

## 4. Resilience — Rate Limiting and Retry

```mermaid
flowchart TD
    CALL[Claude CLI call] --> RC{Return code}
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

## 5. Dimension Exhaustion

```mermaid
flowchart TD
    HYPO[Hypothesis generator<br>picks dimension] --> ATT{Attempt count<br>for this dimension?}
    ATT -->|"< 3"| RUN[Run research]
    ATT -->|">= 3"| EXHAUST[Mark as explored]
    RUN --> RESULT{Result?}
    RESULT -->|Keep| EXPLORED[Add to explored list]
    RESULT -->|Discard| INC[Increment attempt count]
    RESULT -->|Crash| INC
    INC --> CHECK{Attempt >= 3?}
    CHECK -->|Yes| EXHAUST
    CHECK -->|No| NEXT[Next iteration<br>may retry]
    EXHAUST --> SKIP[Hypothesis generator<br>skips this dimension]
    EXPLORED --> SKIP

    style EXHAUST fill:#f97316,color:#000
    style EXPLORED fill:#22c55e,color:#000
```

## 6. Context Management

```mermaid
flowchart TD
    subgraph PROMPT ["Research Prompt Assembly"]
        T1["knowledge_base.md<br>(capped at ~4000 words)"]
        T2["Prompt template<br>(hypothesis / research / evaluate)"]
        T3["Dimension list<br>(explored + unexplored)"]
    end

    T1 & T2 & T3 --> RENDER[Render template<br>with str.format]
    RENDER --> STDIN["Pipe via stdin<br>(avoids 32KB Windows limit)"]
    STDIN --> CLAUDE["claude -p -<br>--model sonnet<br>--max-budget-usd 0.50"]

    subgraph COMPRESSION ["Every N Iterations"]
        KB[knowledge_base.md<br>growing unbounded] --> CALL["claude -p -<br>'Distill and deduplicate'"]
        CALL --> KBC[knowledge_base.md<br>compressed to ~3000 words]
    end

    style STDIN fill:#3b82f6,color:#fff
```

## 7. File Flow

```mermaid
flowchart TD
    CONFIG["configs/topic.yaml<br>topic, dimensions, model,<br>budget, tools"] --> CLI[cli.py<br>--config --resume --synthesize]
    CLI --> ORCH[orchestrator.py<br>AutoResearcher class]

    ORCH -->|reads| P1[prompts/hypothesis.md]
    ORCH -->|reads| P2[prompts/research.md]
    ORCH -->|reads| P3[prompts/evaluate.md]

    ORCH -->|writes| KB[output/topic/knowledge_base.md]
    ORCH -->|writes| ITER["output/topic/iterations/iter_NNN.md"]
    ORCH -->|appends| TSV[output/topic/results.tsv]

    ORCH -.->|on exit| P4[prompts/synthesize.md]
    P4 -.-> SYN[output/topic/synthesis.md]

    SCORER[scorer.py<br>heuristic + judge] -->|called by| ORCH
    CONF_MOD[config.py<br>frozen dataclasses] -->|loaded by| CLI

    style CONFIG fill:#f59e0b,color:#000
    style KB fill:#22c55e,color:#000
    style SYN fill:#3b82f6,color:#fff
    style TSV fill:#8b5cf6,color:#fff
```

## 8. Original vs Claude Code Version

```mermaid
flowchart LR
    subgraph ORIGINAL ["Karpathy's Autoresearch"]
        direction TB
        OA[Agent modifies train.py] --> OB[git commit]
        OB --> OC["uv run train.py<br>(5 min GPU training)"]
        OC --> OD["grep val_bpb run.log"]
        OD --> OE{Improved?}
        OE -->|Yes| OF[Keep commit]
        OE -->|No| OG[git reset]
    end

    subgraph CLAUDE ["autoresearch-claude"]
        direction TB
        CA["claude -p hypothesis.md<br>(pick dimension)"] --> CB["claude -p research.md<br>(WebSearch + analysis)"]
        CB --> CC["Heuristic + LLM judge<br>(score findings)"]
        CC --> CD{Improved?}
        CD -->|Yes| CE[Merge to knowledge base]
        CD -->|No| CF[Save but skip merge]
    end

    ORIGINAL ~~~ CLAUDE
```
