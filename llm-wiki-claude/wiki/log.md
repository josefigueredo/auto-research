# Operation Log

Append-only log of all wiki operations. Claude adds a structured entry
here after every ingest, query, update, lint, or merge.

Entry schema (defined in `CLAUDE.md` → Structured log):

```markdown
## YYYY-MM-DD HH:MM

- **Operation**: ingest | query | update | lint | merge
- **Initiated by**: @username
- **Source**: raw/filename.ext (for ingest)
- **Pages created**: [list]
- **Pages updated**: [list]
- **Tokens used**: ~N input / ~N output
- **Estimated cost**: $N.NN
- **Duration**: N seconds
- **Notes**: one-line summary
```

---

_(no operations logged yet)_
