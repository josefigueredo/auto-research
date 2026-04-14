# LLM Wiki

A persistent, self-auditing knowledge base maintained by Claude Code.
Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
with production-grade enhancements for governance, scale, quality,
observability, integration, and hybrid retrieval.

## Purpose

Claude maintains the wiki. The human curates sources, asks questions, and
guides the analysis. Good answers compound over time — every investigation
that produces reusable knowledge gets filed back into the wiki.

## Folder structure

```
raw/                              -- source documents (immutable)
wiki/                             -- markdown pages Claude maintains
    index.md                      -- table of contents (hierarchical)
    log.md                        -- structured operation log
    _quality.md                   -- quality metrics dashboard
    _quality-history.jsonl        -- metric snapshots, one per lint
    _tags.md                      -- tag → pages index
    _pending-reviews.md           -- proposed changes awaiting approval
    _access.md                    -- page ownership and access policy
    _operations.jsonl             -- machine-readable op log (one JSON/line)
    _costs.md                     -- cumulative token/cost summary
    concepts/                     -- concept pages (cross-cutting ideas)
    topics/                       -- topical pages (grouped by subject)
    sources/                      -- per-source summary pages
docs/                             -- setup and integration references
    embedding-index.md            -- how to build/refresh local embeddings
    export-formats.md             -- export to single-doc / HTML / PDF
    import-adapters.md            -- Notion / Confluence / Slack import
    hooks.md                      -- Slack / GitHub / post-op hooks
```

Directories under `wiki/` are optional at small scale — a flat wiki works
fine for under ~50 pages. See "Hierarchical organization" below.

## Page format

Every wiki page must follow this structure:

```markdown
# Page Title

**Summary**: One to two sentences describing this page.

**Owner**: @username (or "wiki" for shared pages)

**Sources**: List of raw source files this page draws from.

**Last updated**: YYYY-MM-DD

**Confidence**: High | Medium | Low | Unverified

**Freshness**: stable | volatile

**Tags**: #tag1, #tag2, #tag3

---

Main content. Use clear headings and short paragraphs.

Link to related concepts using [concept](concept.md) throughout the text.

## Related pages

- [related-concept-1](related-concept-1.md)
- [related-concept-2](related-concept-2.md)
```

**Field semantics**:
- `Owner`: if set to a human, edits by the agent need review (see Review queue)
- `Freshness`: `volatile` pages always trigger external confirmation on query
- `Tags`: power cross-cutting navigation via `wiki/_tags.md`

## Ingest workflow

When the user adds a new source to `raw/` and asks you to ingest it:

1. Read the full source document
2. Check `wiki/_access.md` for any locked pages the source might touch
3. Discuss key takeaways with the user before writing anything
4. **Estimate scope**: how many pages will be created/updated? If >5 new
   pages or >10 updates, confirm with the user before proceeding
5. **Check cost budget** against `wiki/_costs.md` cumulative spend
6. Create a summary page in `wiki/sources/` named after the source
7. Create or update concept pages in `wiki/concepts/` or topical pages
   in `wiki/topics/` for each major idea or entity
8. Add links `[page-name](page-name.md)` to connect related pages
9. Assign `Tags:` to every new or updated page
10. Update `wiki/index.md` with new pages and one-line descriptions
11. Update `wiki/_tags.md` with new tag → page mappings
12. If any touched page has an `Owner:` other than "wiki", append a
    review entry to `wiki/_pending-reviews.md` instead of committing
    directly, and notify the user
13. Append a structured entry to `wiki/log.md`
14. Append a JSON record to `wiki/_operations.jsonl`
15. Update cumulative totals in `wiki/_costs.md`

A single source may touch 10-15 wiki pages. That is normal.

### Branch-based edits (large ingests)

For ingests estimated to create/update more than 10 pages:

1. Ask the user: "Large ingest. Create a feature branch?"
2. If yes: `git checkout -b wiki/ingest-<source-stem>-<YYYYMMDD>`
3. Commit all wiki changes atomically on the branch
4. Log the branch name and commit SHA in the log entry
5. Ask the user to review the diff before merging
6. On merge, the user runs `git merge wiki/ingest-...` manually

## Citation rules

- Every factual claim must reference its source file using
  `(source: filename.ext)` after the claim
- Every quantitative claim (numbers, dates, prices, measurements) must
  include the source and the date the source was retrieved or published
- If two sources disagree, note the contradiction explicitly and link
  both sources. Do not silently pick one
- If a claim has no source, prefix it with **[unverified]** and mark the
  page confidence as Low or Unverified
- When ingesting web content, record the URL and access date as the source

## Question answering (dual-path)

When the user asks a question:

1. Read `wiki/index.md` to find relevant pages
2. If available, use the embedding index at `wiki/_embeddings/` for
   semantic search (see `docs/embedding-index.md`)
3. If embedding index absent, grep across `wiki/` for keyword matches
4. Read candidate pages, synthesize an answer
5. Assess confidence:
   - Is the answer fully grounded in the wiki?
   - Do cited pages have High/Medium confidence?
   - Are any cited pages marked `volatile` (always need fresh lookup)?
6. Route:
   - **Fully grounded, stable pages, High/Medium confidence**
     → Return wiki-only answer, tagged `[wiki]`
   - **Partially grounded OR volatile pages OR Low confidence**
     → Return wiki answer, then do external lookup, combine, tag
     sections `[wiki]` vs `[external]`
   - **Not in wiki**
     → Say so. Offer external search. On user approval, search and
     return an `[external]` answer, then offer to ingest the result
7. If the answer is valuable and not already in the wiki, offer to save
   it as a new wiki page

**Answer formatting**:
- Prefix sections with `[wiki]` or `[external]` tags
- Cite wiki pages: `See [page-name](page-name.md)`
- External sources: include URL and retrieval date
- Volatile pages: explicitly note "confirmed externally on YYYY-MM-DD"

**Never**:
- Answer confidently from the wiki without checking volatile pages externally
- Present external findings as if they came from the wiki
- Skip the save-back offer when the user's question produced reusable knowledge

Log the query with operation type `query` and record answer_source in
both `wiki/log.md` and `wiki/_operations.jsonl`.

## Structured log

Every operation appends to `wiki/log.md` (human-readable) AND
`wiki/_operations.jsonl` (machine-readable).

### `wiki/log.md` entry

```markdown
## YYYY-MM-DD HH:MM

- **Operation**: ingest | query | update | lint | merge | review
- **Initiated by**: @username (or "scheduled")
- **Source**: raw/filename.ext (for ingest)
- **Branch**: wiki/ingest-... (if branched)
- **Pages created**: [list]
- **Pages updated**: [list]
- **Tokens used**: ~N input / ~N output
- **Estimated cost**: $N.NN
- **Duration**: N seconds
- **Notes**: one-line summary
```

For `query`: also log `Question`, `Answer source` (wiki/external/hybrid/
not-answered), `Pages cited`.
For `lint`: also log `Metrics snapshot` (e.g., "142 pages, 3 orphans").
For `review`: also log `Review ID`, `Decision` (approved/rejected),
`Reviewer`.

Failed operations: `Operation: failed-<type>`, list pages successfully
written before failure, and the reason.

### `wiki/_operations.jsonl` entry

```json
{"ts": "2026-04-13T12:34:56Z", "op": "ingest", "user": "jose", "source": "raw/foo.pdf", "pages_created": ["foo.md"], "pages_updated": ["index.md"], "tokens_in": 12000, "tokens_out": 3500, "cost_usd": 0.13, "duration_s": 45, "branch": "wiki/ingest-foo-20260413", "notes": "clean"}
```

## Cost awareness and budgets

- Track cumulative token usage in `wiki/_operations.jsonl`
- Maintain a rolling summary in `wiki/_costs.md` (regenerated during lint)
- Before any single operation estimated to exceed 50,000 tokens, confirm
  with user
- If `wiki/_costs.md` shows a daily budget has been exceeded, confirm
  before continuing
- Report daily/weekly cost summaries during lint

Default budgets (override per project):
- Per-operation soft cap: 50,000 tokens
- Daily soft cap: $5 USD
- Weekly soft cap: $20 USD

## Lint (quality dashboard)

When the user asks you to lint or audit the wiki:

1. Format check — every page follows the page format
2. Contradiction check — scan for conflicting claims across pages
3. Orphan check — pages with no inbound links
4. Missing concept check — concepts referenced but without pages
5. Citation check — unverified claims count
6. Staleness check:
   - Pages older than 90 days (`Last updated`)
   - Sources older than 180 days
7. Consistency check (automated, see below)
8. Tag coherence — pages without tags, tag name variants
9. Ownership check — pages without owners
10. Cost summary — regenerate `wiki/_costs.md` from `_operations.jsonl`
11. Compute metrics, write `wiki/_quality.md`
12. Append JSON snapshot to `wiki/_quality-history.jsonl`
13. Report findings as a numbered list with **specific remediation
    suggestions**, not just problem statements

### Automated consistency checks

Beyond structural checks:

- **Cross-reference validation**: if page A says "X costs $10" and page B
  says "X costs $15", flag even if neither is marked as a contradiction
- **Completeness check**: for each raw source, verify major claims were
  captured in at least one wiki page. Flag gaps
- **Link reciprocity**: if A links to B, check whether B should link back
  (or explicitly explain why not in B's `## Related pages`)
- **Tag variants**: flag `#machine-learning` vs `#ML` vs `#machineLearning`

### `wiki/_quality.md` format

See Phase 1 CLAUDE.md. Key metrics:
- Total pages / orphans / pages-without-sources
- Link density, tag density
- Unverified claims count
- Stale pages / stale sources
- Source coverage (ingested / total in `raw/`)
- Contradictions flagged
- Volatile pages count
- Ownership coverage (pages with explicit owner)
- **Grade**: strong | good | developing | insufficient
- **Remediation suggestions** — specific, actionable

## Staleness policy

- Pages not updated in 90 days → flagged during lint
- Sources older than 180 days → re-verification flag on pages that cite them
- Newer source version available → flag for re-ingestion
- Volatile pages older than 7 days → always re-verify externally on query

## Merge and conflict resolution

If two wiki pages contain contradictory information:

1. Identify the conflict explicitly in both pages
2. Note which source each side comes from and its date
3. If one source is clearly more authoritative or recent, note that
   but preserve both views
4. Create a `## Contradictions` section in affected pages
5. Log with `**Operation**: merge` in `wiki/log.md`
6. If pages are owned by different users, append to `_pending-reviews.md`

## Review queue (human-in-the-loop)

After any operation that modifies pages with `Owner` ≠ "wiki", instead
of committing directly:

1. Stage the proposed change (in memory or in a draft file under
   `wiki/_drafts/`)
2. Append an entry to `wiki/_pending-reviews.md`:

```markdown
## Review #N — YYYY-MM-DD HH:MM

- **Page**: page-name.md
- **Owner**: @username
- **Proposed by**: agent (@claude)
- **Operation**: ingest | update | merge
- **Summary**: one-line description of the change
- **Draft**: wiki/_drafts/page-name.md
- **Status**: pending | approved | rejected
```

3. Notify the user
4. When the owner responds:
   - Approved → apply the draft, log `Operation: review` with decision
   - Rejected → delete the draft, log the rejection and reason

Post-ingest review rotation: after every ingest, proactively surface
3-5 of the most uncertain or lowest-confidence claims and ask the user
to verify them. Track human-verified claims separately from agent-only.

## Access control

`wiki/_access.md` declares:
- Pages/directories that are **locked** (require approval to modify)
- Per-user ownership maps
- Override rules (e.g., "wiki/topics/japan/ owned by @alice")

Before any write, Claude:
1. Reads `wiki/_access.md`
2. If the target page is locked, routes through the review queue
3. If the target is outside the user's owned areas, asks for confirmation

## Hierarchical organization

Small wikis (< ~50 pages) can use a flat `wiki/` structure. Beyond that,
migrate to:

- `wiki/concepts/` — cross-cutting ideas (e.g., `transformers.md`)
- `wiki/topics/<topic>/` — subject-specific pages
- `wiki/sources/` — per-source summary pages (one per raw file)

When the wiki exceeds 50 pages, during the next lint, propose a
migration plan and ask the user to approve before moving files.

`wiki/index.md` becomes a category-level TOC linking to sub-indexes in
each directory (`wiki/concepts/index.md`, `wiki/topics/<topic>/index.md`).

## Tag-based navigation

Every page declares `Tags:`. During lint, Claude regenerates
`wiki/_tags.md`:

```markdown
# Tag Index

**Last updated**: YYYY-MM-DD

## #pricing
- [aws-api-gateway.md](aws-api-gateway.md)
- [lambda-costs.md](lambda-costs.md)

## #security
- [iam-patterns.md](iam-patterns.md)
- [secrets-management.md](secrets-management.md)
```

During query answering, if the user mentions a tag-like term, also
consult `wiki/_tags.md` for cross-cutting matches.

## Scheduled maintenance

If the environment supports Claude Code `/schedule` or external cron,
the wiki benefits from recurring operations:

- **Weekly lint** — catches drift before it compounds
- **Monthly staleness sweep** — re-verify volatile pages, flag stale sources
- **Quarterly full quality report** — trend analysis across lint history

When asked to "schedule maintenance", Claude documents the recommended
schedule in `wiki/_schedule.md` but does not install the schedule itself
(that's user action via their environment's scheduler).

## External hooks

Documented in `docs/hooks.md`. Patterns:

- **Post-ingest** → notify a Slack channel, post to a GitHub issue, etc.
- **Post-lint** → if quality degraded, open a tracking issue
- **Post-query** → if the answer was "not in wiki", log the gap

Claude does not install hooks automatically. The user wires them via
Claude Code hooks configuration or their CI.

## Export / import

See `docs/export-formats.md` and `docs/import-adapters.md` for how
to:
- Export wiki to single concatenated markdown (for LLM context)
- Export to static HTML site
- Export to PDF
- Import from Notion, Confluence, Google Docs, Slack threads, GitHub

Import produces files in `raw/` — Claude then ingests them via the
normal workflow.

## Embedding index (optional, for scale)

For wikis beyond ~200 pages or when keyword search fails, maintain a
local embedding index. See `docs/embedding-index.md` for the setup.

Claude rebuilds the index during lint when the page count grows >10%
since the last index build.

## Rules

- Never modify anything in the `raw/` folder
- Always update `wiki/index.md`, append to `wiki/log.md` and
  `wiki/_operations.jsonl` after any change
- Keep page names lowercase with hyphens
- Use standard markdown links `[text](file.md)`
- Write in clear, plain language
- When uncertain about categorization, ask the user
- When lint produces poor metrics, suggest specific remediation, not
  just problem statements
- When answering about volatile topics, always do a fresh external lookup
  even if the wiki has an answer
- Never present external findings as wiki content without an `[external]` tag
- Pages with non-"wiki" owners go through the review queue, never direct
- Before any >50k-token operation, confirm with the user
- Before modifying a locked page (per `_access.md`), require approval
