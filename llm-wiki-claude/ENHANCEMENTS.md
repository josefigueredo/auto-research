# LLM Wiki — Production-Grade Enhancement Plan

## Current state

The CLAUDE.md implements Karpathy's core pattern: ingest raw sources into a
compiled wiki, maintain cross-links, answer questions from wiki state, lint
for quality. This works well for personal/small-team use at ~100 sources.

## What "production grade" means here

Moving from a personal knowledge tool to something a team or organization
can rely on daily. The gaps are: governance, scale, observability, quality
assurance, and integration with external systems.

---

## Phase 1: Governance and multi-user support

**Problem**: The current design assumes one curator + one agent. At team
scale, concurrent edits, ownership, and review are unaddressed.

### 1.1 Page ownership and review

- Add `**Owner**: @username` to the page format
- Edits by the agent to pages owned by someone else should be flagged
  for review rather than applied directly
- Add a `wiki/_pending-reviews.md` file listing proposed changes that
  need human approval

### 1.2 Change log with structured entries

Replace free-form `log.md` entries with structured records:

```markdown
## 2026-04-13

- **Action**: ingest
- **Source**: raw/api-gateway-comparison.pdf
- **Pages created**: api-gateway.md, lambda-integration.md
- **Pages updated**: index.md, aws-services.md
- **Tokens used**: ~12,000 input / ~3,500 output
- **Initiated by**: @jose
- **Reviewed by**: (pending)
```

### 1.3 Branch-based edits (Git workflow)

For large ingests or controversial updates:
- Create a Git branch before making changes
- Commit all wiki changes atomically
- The user reviews the diff before merging to main
- Log entry includes the commit SHA

### 1.4 Access control hints

Add a `wiki/_access.md` file that declares:
- Which pages are "locked" (require explicit approval to modify)
- Which users/agents can modify which sections
- The agent reads this before any write operation

---

## Phase 2: Scale and navigation

**Problem**: Index-first navigation degrades at hundreds of pages. The
flat `wiki/` directory becomes unwieldy.

### 2.1 Hierarchical directory structure

```
wiki/
  index.md
  log.md
  _quality.md
  concepts/
    machine-learning.md
    transformers.md
  topics/
    japan-travel/
      tokyo.md
      kyoto.md
  sources/
    paper-attention-is-all-you-need.md
```

The index.md becomes a category-level table of contents linking to
sub-indexes in each directory.

### 2.2 Tag-based navigation

Add `**Tags**: #tag1, #tag2` to the page format. During lint, generate a
`wiki/_tags.md` file that maps tags to pages. This enables cross-cutting
navigation (e.g., all pages tagged `#pricing` regardless of directory).

### 2.3 Search integration

For corpora beyond ~200 pages, add a search command:
- When the user asks to search, grep across all wiki pages for keywords
- Rank results by recency and link density
- For larger deployments, integrate with a local embedding index
  (Chroma, SQLite-vec, or similar)

---

## Phase 3: Quality assurance and evaluation

**Problem**: No way to measure whether the wiki is actually good, complete,
or improving over time.

### 3.1 Quality metrics dashboard

Extend `wiki/_quality.md` to track over time:

| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
| Total pages | 142 | 135 | +7 |
| Orphan pages | 3 | 5 | -2 |
| Unverified claims | 12 | 18 | -6 |
| Source coverage | 87% | 82% | +5% |
| Avg links/page | 4.2 | 3.8 | +0.4 |
| Stale pages (>90d) | 8 | 5 | +3 |

Store historical snapshots in `wiki/_quality-history.json` so trends can
be computed.

### 3.2 Automated consistency checks

Beyond lint, add deeper checks:
- **Cross-reference validation**: if page A says "X costs $10/month" and
  page B says "X costs $15/month", flag it even if neither is marked as
  a contradiction
- **Completeness check**: for each raw source, verify that all major
  claims were captured in at least one wiki page
- **Link reciprocity**: if A links to B, B should link back to A (or
  there should be a reason it doesn't)

### 3.3 Human-in-the-loop review queue

After each ingest or major update:
- Generate a summary of all changes made
- List the most uncertain or lowest-confidence claims
- Ask the user to verify 3-5 specific claims (rotating selection)
- Track which claims have been human-verified vs. agent-only

---

## Phase 4: Observability and cost management

**Problem**: No visibility into what the agent is doing, how much it costs,
or whether operations are succeeding.

### 4.1 Operation logging with token tracking

Every agent operation logs:
- Timestamp
- Operation type (ingest, query, lint, update)
- Input/output token count
- Cost estimate (based on model pricing)
- Pages read and written
- Duration

Store in `wiki/_operations.json` (machine-readable) and summarize in
`wiki/log.md` (human-readable).

### 4.2 Cost budgets

Add to CLAUDE.md:
```
## Cost awareness
- Track cumulative token usage in wiki/_operations.json
- Before any operation estimated to exceed 50,000 tokens, confirm with user
- Report daily/weekly cost summaries during lint
```

### 4.3 Error tracking

When an ingest or update fails partway:
- Log the failure in `wiki/log.md` with the error
- Note which pages were successfully updated and which weren't
- On next operation, check for incomplete previous operations and
  offer to resume

---

## Phase 5: Integration and automation

**Problem**: The wiki is isolated — it doesn't connect to the team's
existing tools or workflows.

### 5.1 Hooks for external triggers

Define hooks that fire after wiki operations:
- Post-ingest: notify a Slack channel with a summary of changes
- Post-lint: if quality metrics degraded, open a GitHub issue
- Post-query: if the answer was "not in wiki," log the gap for future
  ingestion

### 5.2 Scheduled maintenance

Automate recurring operations:
- Weekly lint run (via cron or Claude Code `/schedule`)
- Monthly staleness sweep
- Quarterly full quality report

### 5.3 Export formats

Support exporting the wiki to:
- A single concatenated markdown document (for LLM context)
- A static HTML site (using a static site generator)
- A PDF report (for sharing with stakeholders)

### 5.4 Import from existing knowledge bases

Ingest adapters for:
- Notion exports (markdown)
- Confluence exports (HTML → markdown)
- Google Docs (via API or export)
- Slack thread bookmarks
- GitHub issue/discussion threads

---

## Phase 6: Hybrid retrieval layer

**Problem**: Compiled memory works for durable synthesis but misses fresh
or high-recall queries. The current design has no escape hatch.

### 6.1 Dual-path query answering

```
User asks a question
  → Check wiki/index.md and relevant pages
  → If answer found with high confidence → return wiki answer
  → If answer not found or low confidence:
      → Search externally (web, embeddings, or API)
      → Return answer with "[external]" label
      → Offer to ingest result into wiki
```

### 6.2 Embedding index as a complement

For larger wikis, maintain a lightweight embedding index alongside the
markdown files:
- Re-index on every ingest or update
- Use for semantic search when keyword grep fails
- Store in `wiki/_embeddings/` (gitignored, rebuildable)

### 6.3 Freshness signals

For pages that track fast-moving information (pricing, API versions,
release dates):
- Mark with `**Freshness**: volatile` in the page header
- During question answering, always supplement volatile pages with a
  fresh external lookup
- Log when a volatile page's information was last externally confirmed

---

## Implementation priority

| Phase | Effort | Impact | Dependency |
|-------|--------|--------|------------|
| 1.2 Structured log entries | Small | High | None |
| 3.1 Quality metrics dashboard | Small | High | None |
| 1.1 Page ownership + review | Medium | High | None |
| 4.1 Token tracking | Small | Medium | None |
| 2.2 Tag-based navigation | Small | Medium | None |
| 6.1 Dual-path query answering | Medium | High | None |
| 3.3 Human review queue | Medium | High | 1.1 |
| 1.3 Branch-based edits | Medium | Medium | Git workflow |
| 2.1 Hierarchical directories | Medium | Medium | Existing wiki migration |
| 4.2 Cost budgets | Small | Medium | 4.1 |
| 3.2 Automated consistency checks | Medium | Medium | None |
| 5.2 Scheduled maintenance | Small | Medium | Claude Code hooks |
| 5.1 External hooks (Slack, GitHub) | Medium | Medium | MCP servers |
| 6.2 Embedding index | Large | High | Chroma/SQLite-vec |
| 5.3 Export formats | Medium | Low | None |
| 5.4 Import adapters | Large | Medium | Per-source format |
| 6.3 Freshness signals | Medium | Medium | 6.1 |
| 2.3 Search integration | Large | High | 6.2 |
| 1.4 Access control | Medium | Low | 1.1 |

## Recommended first 3

1. **Structured log entries (1.2)** — immediate, zero-cost improvement to
   auditability. Change the log format in CLAUDE.md and it takes effect
   on the next operation.

2. **Quality metrics dashboard (3.1)** — makes the wiki self-aware. After
   every lint, you know whether it's improving or degrading. This is the
   rubric equivalent for the wiki.

3. **Dual-path query answering (6.1)** — the highest-impact UX improvement.
   The wiki stops being a dead end when it doesn't know something and
   starts growing from every question.
