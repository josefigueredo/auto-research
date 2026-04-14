# LLM Wiki (Claude Code)

A persistent, self-auditing knowledge base maintained by Claude Code.
Adapts [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
with production-grade enhancements.

## Layout

```
llm-wiki-claude/
    CLAUDE.md                     -- prompt: how Claude maintains the wiki
    ENHANCEMENTS.md               -- 6-phase roadmap (context + rationale)
    README.md                     -- this file
    .gitignore                    -- excludes rebuildable artifacts
    raw/                          -- source documents (you add these)
    wiki/                         -- markdown pages Claude maintains
        index.md                  -- table of contents
        log.md                    -- structured operation log
        _quality.md               -- quality dashboard
        _quality-history.jsonl    -- metric history for trend tracking
        _tags.md                  -- tag → pages index
        _pending-reviews.md       -- proposed changes awaiting approval
        _access.md                -- ownership and access policy
        _operations.jsonl         -- machine-readable op log
        _costs.md                 -- cumulative token/cost summary
        _schedule.md              -- recommended maintenance schedule
        _drafts/                  -- staged changes pending review
    docs/                         -- setup references for code items
        embedding-index.md        -- semantic search with sqlite-vec
        export-formats.md         -- single-doc / HTML / PDF exports
        import-adapters.md        -- Notion / Confluence / Slack / GH
        hooks.md                  -- Slack / GitHub / post-op hooks
```

## Quick start

1. **Point Claude Code at this directory**: `cd llm-wiki-claude` then
   open Claude Code. It will read `CLAUDE.md` automatically.

2. **Drop a source** into `raw/` (PDF, markdown, text, HTML — anything).

3. **Ask Claude to ingest it**: "ingest raw/<filename>".

4. **Ask questions**: Claude reads the index, uses the embedding index
   if available, and falls back to external search when the wiki is
   incomplete. Answers carry `[wiki]` / `[external]` provenance tags.

5. **Periodically lint**: "lint the wiki". Produces `_quality.md` with
   metrics, trends, and specific remediation suggestions.

## What's different from the original pattern

The full 6-phase roadmap (`ENHANCEMENTS.md`) is implemented through:

### Governance
- **Page ownership** (`Owner:` field) — human-owned pages go through
  a review queue before edits are applied
- **Review queue** (`wiki/_pending-reviews.md`) — structured review
  workflow with approve/reject decisions
- **Access policy** (`wiki/_access.md`) — per-page or per-directory
  locks and ownership overrides
- **Branch-based edits** — large ingests (>10 pages) propose a Git
  branch for atomic review before merging
- **Post-ingest review rotation** — Claude surfaces 3-5 low-confidence
  claims for human verification after every ingest

### Scale
- **Hierarchical directories** — `wiki/concepts/`, `wiki/topics/<topic>/`,
  `wiki/sources/` — proposed automatically beyond ~50 pages
- **Tag-based navigation** (`wiki/_tags.md`) — cross-cutting index
  regenerated during lint
- **Embedding index** (`docs/embedding-index.md`) — optional local
  semantic search via sqlite-vec when page count exceeds ~200

### Quality assurance
- **Quality dashboard with trend history** (`_quality.md` +
  `_quality-history.jsonl`) — current vs. previous metrics, grade
  (strong/good/developing/insufficient), specific remediation
- **Automated consistency checks** — cross-reference validation,
  completeness check against raw sources, link reciprocity, tag
  variants detection

### Observability
- **Structured log** (`log.md` + `_operations.jsonl`) — every
  operation logs type, initiator, pages touched, token usage, cost,
  duration. Machine-readable JSONL enables replay and trend analysis
- **Cost budgets** (`_costs.md`) — default per-op/daily/weekly caps,
  confirmation prompts on large operations
- **Error tracking** — failed operations log `Operation: failed-<type>`
  with which pages succeeded before the failure

### Integration
- **Scheduled maintenance** (`_schedule.md`) — recommended cadence
  for lint / staleness sweep / quality report with example
  Claude Code `/schedule` and cron configs
- **Hooks** (`docs/hooks.md`) — post-ingest Slack notifications,
  post-lint GitHub issues on regression, coverage-gap logging
- **Export formats** (`docs/export-formats.md`) — single-doc markdown,
  MkDocs static site, PDF via pandoc, JSON dump
- **Import adapters** (`docs/import-adapters.md`) — Notion, Confluence,
  Google Docs, Slack threads, GitHub issues, web pages

### Hybrid retrieval
- **Dual-path question answering** — routes by confidence: wiki-only
  for grounded stable pages, hybrid for volatile/partial, external-only
  with ingestion offer when not in wiki
- **Freshness signals** — `Freshness: volatile` pages always trigger
  external confirmation even when the wiki has an answer
- **Embedding index** — semantic search complements keyword grep for
  larger corpora

## Design references

- [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  — the original one-page pattern
- [autoresearch assessment](../output/karpathy_llm_wiki/synthesis.md)
  — decision-ready analysis of the gist that informed these enhancements
- [`ENHANCEMENTS.md`](ENHANCEMENTS.md) — the full production roadmap
