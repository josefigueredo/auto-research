# AutoResearch Claude Code Agent — Architecture Diagrams

## 1. Main Loop Flow

```mermaid
flowchart TD
    START([cli.py --config aws_api_gateway.yaml]) --> INIT[Load config + resume state]
    INIT --> CHECK{Existing iterations?}
    CHECK -->|Yes| RESUME[Rebuild knowledge base from iteration files]
    CHECK -->|No| FRESH[Initialize empty knowledge base]
    RESUME --> LOOP
    FRESH --> LOOP

    LOOP[[INFINITE LOOP]] --> HYPO

    subgraph ITERATION ["Each Iteration"]
        HYPO[1. HYPOTHESIS<br>claude -p hypothesis.md<br>Pick next dimension to explore]
        HYPO --> EXEC[2. EXECUTE<br>claude -p research.md<br>Deep research with WebSearch/WebFetch]
        EXEC --> SCORE[3. SCORE<br>Heuristic + LLM Judge]
        SCORE --> DECIDE{4. DECIDE<br>total_score > best_score?}
        DECIDE -->|Yes: KEEP| MERGE[Merge findings into<br>knowledge_base.md]
        DECIDE -->|No: DISCARD| SKIP[Keep iteration file<br>but don't merge]
        MERGE --> LOG[5. LOG<br>Append to results.tsv<br>Save iter_NNN.md]
        SKIP --> LOG
    end

    LOG --> COMPRESS{Every 5 iterations?}
    COMPRESS -->|Yes| SHRINK[Compress knowledge_base.md<br>via claude -p]
    COMPRESS -->|No| LOOP
    SHRINK --> LOOP

    LOOP -.->|Ctrl+C| SYNTH[Generate synthesis.md<br>Final report]
    SYNTH --> DONE([Exit])

    style LOOP fill:#f59e0b,color:#000
    style MERGE fill:#22c55e,color:#000
    style SKIP fill:#ef4444,color:#fff
    style SYNTH fill:#3b82f6,color:#fff
```

## 2. Sequence Diagram — Single Iteration

```mermaid
sequenceDiagram
    participant O as orchestrator.py
    participant C1 as Claude CLI<br>(Hypothesis)
    participant C2 as Claude CLI<br>(Research)
    participant C3 as Claude CLI<br>(Judge)
    participant FS as File System

    O->>FS: Read knowledge_base.md + config
    O->>C1: claude -p hypothesis.md<br>--output-format json
    C1-->>O: {dimension, questions, approach}

    O->>C2: claude -p research.md<br>--allowedTools WebSearch,WebFetch,...
    Note over C2: Agent searches web,<br>fetches AWS docs,<br>compares sources
    C2-->>O: {findings_markdown, new_questions}

    O->>O: Heuristic score<br>(dimensions, evidence types, word count)

    O->>C3: claude -p evaluate.md<br>--json-schema {depth, accuracy, novelty, actionability}
    C3-->>O: {depth: 8, accuracy: 7, novelty: 9, actionability: 8}

    O->>O: Combine scores<br>total = 0.4 * heuristic + 0.6 * judge

    alt total_score > best_score
        O->>FS: Merge findings → knowledge_base.md
        O->>FS: Save iter_NNN.md (status: keep)
    else total_score <= best_score
        O->>FS: Save iter_NNN.md (status: discard)
    end

    O->>FS: Append row to results.tsv
```

## 3. Scoring System

```mermaid
flowchart LR
    subgraph HEURISTIC ["Heuristic Score (40%)"]
        H1[Dimensions covered<br>vs config list]
        H2[Evidence types found<br>tables/pricing/code/tradeoffs]
        H3[New questions<br>discovered]
        H4[Word count<br>relative to target]
        H1 & H2 & H3 & H4 --> HS[coverage_score<br>0-100]
    end

    subgraph JUDGE ["LLM Judge Score (60%)"]
        J1[depth: 1-10]
        J2[accuracy: 1-10]
        J3[novelty: 1-10]
        J4[actionability: 1-10]
        J1 & J2 & J3 & J4 --> JS[quality_score<br>0-100]
    end

    HS --> TOTAL[total_score<br>0.4 * coverage + 0.6 * quality]
    JS --> TOTAL
    TOTAL --> CMP{> best_score?}
    CMP -->|Yes| KEEP[KEEP]
    CMP -->|No| DISCARD[DISCARD]

    style KEEP fill:#22c55e,color:#000
    style DISCARD fill:#ef4444,color:#fff
```

## 4. Context Management — Token Budget

```mermaid
flowchart TD
    subgraph CONTEXT ["What Each Research Call Receives"]
        T1["Tier 1: Compressed knowledge base<br>(~4000 words max)"]
        T2["Tier 2: Full text of last 2 iterations"]
        T3["Tier 3: Dimension summary list<br>(one line per explored dimension)"]
    end

    subgraph COMPRESSION ["Every 5 Iterations"]
        KB[knowledge_base.md<br>growing...] --> CALL[claude -p<br>'Distill and deduplicate']
        CALL --> KBC[knowledge_base.md<br>compressed ~4000 words]
    end

    T1 & T2 & T3 --> PROMPT[Research prompt<br>~6000 words total context]
```

## 5. Mapping: Original vs Claude Code Version

```mermaid
flowchart LR
    subgraph ORIGINAL ["Original Autoresearch (GPU)"]
        direction TB
        OA[Agent modifies train.py] --> OB[git commit]
        OB --> OC[uv run train.py<br>5 min GPU training]
        OC --> OD[grep val_bpb run.log]
        OD --> OE{Improved?}
        OE -->|Yes| OF[Keep commit]
        OE -->|No| OG[git reset]
    end

    subgraph CLAUDE ["Claude Code Version"]
        direction TB
        CA[claude -p hypothesis.md<br>Pick dimension] --> CB[claude -p research.md<br>WebSearch + analysis]
        CB --> CC[Heuristic + LLM judge<br>Score findings]
        CC --> CD{Improved?}
        CD -->|Yes| CE[Merge to knowledge base]
        CD -->|No| CF[Skip merge]
    end

    ORIGINAL ~~~ CLAUDE
```

## 6. File Flow

```mermaid
flowchart TD
    CONFIG[configs/aws_api_gateway.yaml] --> CLI[cli.py]
    CLI --> ORCH[orchestrator.py]

    ORCH --> |reads| P1[prompts/hypothesis.md]
    ORCH --> |reads| P2[prompts/research.md]
    ORCH --> |reads| P3[prompts/evaluate.md]

    ORCH --> |writes| KB[output/knowledge_base.md]
    ORCH --> |writes| ITER[output/iterations/iter_NNN.md]
    ORCH --> |appends| TSV[output/results.tsv]

    ORCH -.-> |on Ctrl+C| P4[prompts/synthesize.md]
    P4 -.-> SYN[output/synthesis.md]

    SCORER[scorer.py] --> |called by| ORCH

    style CONFIG fill:#f59e0b,color:#000
    style KB fill:#22c55e,color:#000
    style SYN fill:#3b82f6,color:#fff
```
