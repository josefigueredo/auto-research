# Export Formats

How to export the wiki to shareable formats. Claude executes these
workflows on request ("export the wiki to HTML", "export to a single
markdown for Claude context").

## Single-document markdown (for LLM context)

Concatenate all wiki pages into one markdown file for use as LLM context.

```bash
{
  for f in wiki/index.md wiki/log.md wiki/_quality.md; do
    cat "$f"
    echo ""
  done
  find wiki -name "*.md" -not -name "_*" -not -path "wiki/index.md" | while read f; do
    echo -e "\n\n---\n\n# File: $f\n"
    cat "$f"
  done
} > wiki-export.md
```

Output: `wiki-export.md` (one file, chronologically ordered).

## Static HTML site

Use [MkDocs](https://www.mkdocs.org/) with the Material theme.

```bash
pip install mkdocs mkdocs-material
```

`mkdocs.yml`:
```yaml
site_name: LLM Wiki
docs_dir: wiki
theme:
  name: material
  features:
    - navigation.tabs
    - search.highlight
plugins:
  - search
markdown_extensions:
  - admonition
  - toc:
      permalink: true
```

Build: `mkdocs build` (output in `site/`). Serve: `mkdocs serve`.

## PDF

Via pandoc (aggregate markdown → PDF):

```bash
pandoc wiki-export.md -o wiki-export.pdf \
  --toc --toc-depth=2 \
  --metadata title="LLM Wiki Export" \
  --pdf-engine=xelatex
```

Requires pandoc and a LaTeX distribution (TeX Live, MiKTeX, or BasicTeX).

## JSON dump (for programmatic consumers)

Structure for downstream processing:

```python
import json
from pathlib import Path

pages = []
for md in Path("wiki").rglob("*.md"):
    if md.name.startswith("_"):
        continue
    text = md.read_text(encoding="utf-8")
    # Parse header fields from frontmatter-style markdown
    pages.append({
        "path": str(md.relative_to("wiki")),
        "content": text,
        # TODO: extract Summary, Sources, Last updated, Confidence, Tags
    })

Path("wiki-export.json").write_text(json.dumps(pages, indent=2))
```
