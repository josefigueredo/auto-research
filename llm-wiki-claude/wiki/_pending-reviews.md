# Pending Reviews

Claude appends an entry here when a proposed change touches a page with
a human owner. The owner reviews the draft under `wiki/_drafts/` and
approves or rejects.

Entry schema (from `CLAUDE.md` → Review queue):

```markdown
## Review #N — YYYY-MM-DD HH:MM

- **Page**: page-name.md
- **Owner**: @username
- **Proposed by**: agent (@claude)
- **Operation**: ingest | update | merge
- **Summary**: one-line description
- **Draft**: wiki/_drafts/page-name.md
- **Status**: pending | approved | rejected
```

---

_(no reviews pending)_
