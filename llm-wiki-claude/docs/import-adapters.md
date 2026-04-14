# Import Adapters

How to bring external knowledge into `raw/` so Claude can ingest it via
the normal workflow. Import adapters convert source formats into
markdown or preserve them as-is if they are already a supported format.

## General principle

All imports land in `raw/` as immutable sources. Claude then treats them
the same as any other source.

## Notion

Export a Notion workspace or page:

1. In Notion: **Settings → Settings & members → Export content**
2. Choose **Markdown & CSV**
3. Unzip into `raw/notion-<date>/`

Notion's export produces markdown files with subdirectories for nested
pages. Claude can ingest these directly; consider asking for a scoped
ingest ("ingest only raw/notion-20260413/product/") to avoid a single
massive operation.

## Confluence

Confluence exports HTML. Convert to markdown:

```bash
pip install markdownify
```

```python
import markdownify
from pathlib import Path

for html in Path("raw/confluence-export").rglob("*.html"):
    md_text = markdownify.markdownify(html.read_text(encoding="utf-8"))
    md_path = html.with_suffix(".md")
    md_path.write_text(md_text, encoding="utf-8")
```

## Google Docs

Two paths:

1. **Export as markdown** (2026-era Google Docs supports this directly):
   File → Download → Markdown (.md)
2. **Via Drive API** (automated, requires OAuth setup):
   Use `google-api-python-client` to fetch docs as text

## Slack threads

Slack doesn't export individual threads cleanly. Options:

1. Copy-paste thread into a markdown file in `raw/slack-<topic>-<date>.md`
   with attribution:
   ```markdown
   # Slack: #channel — YYYY-MM-DD

   Source: Slack thread in #channel, captured YYYY-MM-DD

   **@alice**: original message
   **@bob**: reply
   ...
   ```

2. Use Slack's workspace export (admin-only) and filter for relevant
   channels/threads. Output is JSON; convert to markdown per thread.

## GitHub issues / discussions

Via `gh` CLI:

```bash
# Single issue
gh issue view 123 --json title,body,comments > raw/gh-issue-123.json

# Convert to markdown
gh issue view 123 > raw/gh-issue-123.md

# Bulk export
gh issue list --state all --limit 100 --json number,title,body,comments \
  > raw/gh-issues.json
```

## Web pages

For single pages:
```bash
curl -L https://example.com/article | \
  python -c "import sys, markdownify; print(markdownify.markdownify(sys.stdin.read()))" \
  > raw/article.md
```

For documentation sites, consider [httrack](https://www.httrack.com/) or
a scoped scrape with `wget --recursive --level=2 --convert-links`.

## After importing

1. Files are in `raw/`
2. Ask Claude: "ingest the new sources in raw/<subdir>"
3. Claude will check the size (>5 sources triggers confirmation),
   discuss takeaways, and run the ingest workflow

## Importer ergonomics

If a specific import source gets used repeatedly, add a wrapper script
under `scripts/` in the project and document it in this file.
