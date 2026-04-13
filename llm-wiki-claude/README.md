# LLM Wiki (Claude Code)

A persistent, self-auditing knowledge base maintained by Claude Code.
Adapts [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
with production-grade enhancements.

## Layout

```
llm-wiki-claude/
    CLAUDE.md                    -- prompt: how Claude maintains the wiki
    ENHANCEMENTS.md              -- 6-phase production roadmap
    README.md                    -- this file
    raw/                         -- source documents (you add these)
    wiki/                        -- markdown pages Claude maintains
        index.md                 -- table of contents
        log.md                   -- structured operation log
        _quality.md              -- quality dashboard
        _quality-history.jsonl   -- metric history for trend tracking
```

## Quick start

1. **Point Claude Code at this directory**: `cd llm-wiki-claude` then open
   Claude Code. It will read `CLAUDE.md` automatically.

2. **Drop a source** into `raw/` (PDF, markdown, text, HTML — anything).

3. **Ask Claude to ingest it**: "ingest raw/<filename>". Claude will
   discuss key takeaways, create summary + concept pages, update the
   index, and log a structured entry.

4. **Ask questions**: Claude reads the index first, cites wiki pages in
   answers, and does external lookups when the wiki falls short (marked
   `[external]`).

5. **Periodically lint**: "lint the wiki". Produces `_quality.md` with
   metrics, trends, and specific remediation suggestions.

## What's different from the original pattern

Three top-priority enhancements already baked into `CLAUDE.md`:

### 1. Structured operation log

Every operation writes a machine-parseable entry with operation type,
initiator, pages touched, token usage, cost estimate, and duration. No
free-form prose — enables auditing, cost tracking, and replay.

### 2. Quality dashboard with trend history

Lint produces `_quality.md` showing current vs. previous metrics (pages,
orphans, unverified claims, source coverage, link density, staleness) and
a trend column. Each lint appends to `_quality-history.jsonl` so trends
can be computed across arbitrary time ranges.

A calibrated grade (strong / good / developing / insufficient) summarizes
wiki health in one label.

### 3. Dual-path question answering

When you ask a question, Claude routes based on confidence:
- **Fully grounded in stable wiki pages** → wiki-only answer, `[wiki]` tagged
- **Partial or volatile** → wiki answer + external fresh lookup, both tagged
- **Not in wiki** → offers to search externally and ingest the result

Answers carry explicit provenance tags so you always know whether a claim
came from your curated wiki or a fresh external source.

Volatile pages (marked `**Freshness**: volatile` in the page format) always
trigger an external confirmation lookup, even if the wiki has an answer.
This closes the pricing/API-version/release-date staleness gap.

## Roadmap

See [ENHANCEMENTS.md](ENHANCEMENTS.md) for the full 6-phase production
enhancement plan. The three above are Phase 1. Next up:

- Page ownership and review queue (Phase 1.1)
- Hierarchical directory structure (Phase 2.1)
- Embedding index for larger corpora (Phase 6.2)

## Design references

- [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  — the original one-page pattern
- [autoresearch assessment](../output/karpathy_llm_wiki/synthesis.md)
  — decision-ready analysis of the gist that informed the enhancements
