# LLM Wiki

A persistent knowledge base maintained by Claude Code.
Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Purpose

This wiki is a structured, interlinked knowledge base.
Claude maintains the wiki. The human curates sources, asks questions, and
guides the analysis. Good answers compound over time — every investigation
that produces reusable knowledge gets filed back into the wiki.

## Folder structure

```
raw/                        -- source documents (immutable — never modify)
wiki/                       -- markdown pages maintained by Claude
wiki/index.md               -- table of contents for the entire wiki
wiki/log.md                 -- append-only record of all operations
wiki/_quality.md            -- latest quality metrics (auto-generated)
wiki/_quality-history.jsonl -- historical metric snapshots, one per lint
```

## Ingest workflow

When the user adds a new source to `raw/` and asks you to ingest it:

1. Read the full source document
2. Discuss key takeaways with the user before writing anything
3. Create a summary page in `wiki/` named after the source
4. Create or update concept pages for each major idea or entity
5. Add links `[page-name](page-name.md)` to connect related pages
6. Update `wiki/index.md` with new pages and one-line descriptions
7. Append a **structured entry** to `wiki/log.md` (see Structured log below)

A single source may touch 10-15 wiki pages. That is normal.

### Before a large ingest

If the user adds more than 5 sources at once, estimate how many pages will
be created or updated, state the estimate, and confirm before proceeding.
Prefer updating existing pages over creating new ones when content overlaps.

## Page format

Every wiki page must follow this structure:

```markdown
# Page Title

**Summary**: One to two sentences describing this page.

**Sources**: List of raw source files this page draws from.

**Last updated**: YYYY-MM-DD

**Confidence**: High | Medium | Low | Unverified

**Freshness**: stable | volatile

---

Main content. Use clear headings and short paragraphs.

Link to related concepts using [concept](concept.md) throughout the text.

## Related pages

- [related-concept-1](related-concept-1.md)
- [related-concept-2](related-concept-2.md)
```

**Freshness**:
- `stable` — conceptual or historical content that does not change often
- `volatile` — fast-moving info (pricing, API versions, release dates).
  Volatile pages must be supplemented with a fresh external lookup when
  cited in a query answer (see Question answering).

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

## Structured log

Every operation must append a structured entry to `wiki/log.md`:

```markdown
## YYYY-MM-DD HH:MM

- **Operation**: ingest | query | update | lint | merge
- **Initiated by**: @username (or "scheduled")
- **Source**: raw/filename.ext (for ingest)
- **Pages created**: [list of new pages, or "(none)"]
- **Pages updated**: [list of modified pages, or "(none)"]
- **Tokens used**: ~N input / ~N output
- **Estimated cost**: $N.NN (optional, based on model pricing)
- **Duration**: N seconds (approximate)
- **Notes**: one-line summary of what happened, or "(clean)"
```

For query operations, also log:
- **Question**: the user's question (first 100 chars)
- **Answer source**: wiki | external | hybrid | not-answered
- **Pages cited**: [list of wiki pages cited in the answer]

For lint operations, also log:
- **Metrics snapshot**: one line summary (e.g., "142 pages, 3 orphans, 12 unverified claims")

If the operation fails partway, log the failure explicitly with
`**Operation**: failed-<type>` and list which pages were successfully
written before the failure.

## Question answering (dual-path)

When the user asks a question, follow this flow:

```
1. Read wiki/index.md to find relevant pages
2. Read those pages, synthesize a candidate answer
3. Assess confidence:
   - Is the answer fully grounded in the wiki?
   - Do cited pages have High/Medium confidence?
   - Are any cited pages marked 'volatile' (always need fresh lookup)?
4. Route:
   a. Fully grounded, stable pages, High/Medium confidence
      → Return wiki-only answer. Mark as [wiki].
   b. Partially grounded OR volatile pages OR Low confidence
      → Return wiki answer, then do external lookup.
      → Combine. Mark sections [wiki] vs [external].
   c. Not in wiki
      → Say so. Offer external search.
      → If user agrees, search externally. Mark answer [external].
      → Offer to ingest the result as a new source.
5. If the answer is valuable and not already in the wiki, offer to save
   it as a new wiki page (or update an existing page).
```

**Answer formatting**:
- Prefix sections with `[wiki]` or `[external]` tags
- Cite specific wiki pages: `See [page-name](page-name.md)`
- For external sources: include the URL and retrieval date
- For volatile pages: explicitly note "confirmed externally on YYYY-MM-DD"

**Never**:
- Answer confidently from the wiki without checking volatile pages externally
- Present external findings as if they came from the wiki
- Skip the save-back offer when the user's question produced reusable knowledge

## Lint (quality dashboard)

When the user asks you to lint or audit the wiki:

1. Check for contradictions between pages
2. Find orphan pages (no inbound links from other pages)
3. Identify concepts mentioned in pages that lack their own page
4. Flag claims marked **[unverified]** that could be verified
5. Flag pages whose `Last updated` date is older than 90 days
6. Flag pages whose source files are older than 180 days (staleness)
7. Check that all pages follow the page format above
8. Compute quality metrics and write them to `wiki/_quality.md`
9. Append the metrics snapshot to `wiki/_quality-history.jsonl`
10. Report findings as a numbered list with suggested fixes

### `wiki/_quality.md` format

```markdown
# Wiki Quality Dashboard

**Last lint**: YYYY-MM-DD HH:MM

## Current metrics

| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
| Total pages | N | N | +/- N |
| Orphan pages | N | N | +/- N |
| Pages with no sources | N | N | +/- N |
| Unverified claims | N | N | +/- N |
| Stale pages (>90 days) | N | N | +/- N |
| Stale sources (>180 days) | N | N | +/- N |
| Source coverage | N% | N% | +/- N% |
| Average links per page | N.N | N.N | +/- N.N |
| Contradictions flagged | N | N | +/- N |
| Volatile pages | N | N | +/- N |

## Grade

**Current grade**: strong | good | developing | insufficient

Grading rubric (each 0.0–1.0, averaged):
- Source coverage: ingested / total in raw/
- Link density: min(1.0, avg_links_per_page / 3)
- Citation quality: 1 − (unverified_claims / total_claims)
- Freshness: 1 − (stale_pages / total_pages)
- Structural integrity: 1 − (orphan_pages / total_pages)

## Remediation suggestions

[Auto-generated list of specific fixes, not just problem statements.
 e.g., "Page tokyo.md has 0 inbound links. Suggest linking from
 [japan-travel.md](japan-travel.md) where Tokyo is mentioned."]
```

### `wiki/_quality-history.jsonl` format

One JSON object per line, one line per lint run:

```json
{"timestamp": "2026-04-13T12:34:56Z", "total_pages": 142, "orphan_pages": 3, "unverified_claims": 12, "source_coverage": 0.87, "avg_links_per_page": 4.2, "stale_pages": 8, "grade": "good", "overall_score": 0.71}
```

This enables trend analysis across lint runs without re-parsing all pages.

## Staleness policy

- Pages not updated in 90 days are flagged during lint
- Sources older than 180 days trigger a re-verification flag on all pages
  that cite them
- During lint, if a page's primary source has a newer version available
  (e.g., updated documentation), flag it for re-ingestion

## Merge and conflict resolution

If two wiki pages contain contradictory information about the same topic:

1. Identify the conflict explicitly in both pages
2. Note which source each side comes from and its date
3. If one source is clearly more authoritative or recent, note that but
   preserve both views
4. Create a `## Contradictions` section in the affected pages
5. Log the contradiction with `**Operation**: merge` in `wiki/log.md`

## Rules

- Never modify anything in the `raw/` folder
- Always update `wiki/index.md` and append to `wiki/log.md` after changes
- Keep page names lowercase with hyphens (e.g., `machine-learning.md`)
- Use standard markdown links `[text](file.md)`, not `[[wiki-links]]`
- Write in clear, plain language
- When uncertain about how to categorize something, ask the user
- When a lint produces poor metrics, suggest specific remediation steps
  rather than just listing problems
- When answering questions about volatile topics, always do a fresh
  external lookup even if the wiki has an answer
- Never present external findings as wiki content without an `[external]` tag
