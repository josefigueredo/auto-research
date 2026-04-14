# Access and Ownership Policy

Declare ownership and access rules for pages and directories. Claude
reads this file before any write operation.

## Ownership

Default: all pages are owned by `wiki` (freely editable by Claude).
Override per-page or per-directory below.

```yaml
# Per-directory defaults
# wiki/topics/japan/: @alice
# wiki/concepts/security/: @bob

# Per-page overrides
# wiki/concepts/payment-processing.md: @carol
```

## Locked pages

Pages or directories listed here require explicit human approval for
any modification, regardless of owner.

```yaml
# locked:
#   - wiki/concepts/security-baseline.md
#   - wiki/topics/compliance/
```

## Review policy

- Pages owned by a specific user → edits by Claude go to the review queue
- Locked pages → edits require explicit approval in addition to review
- "wiki"-owned pages → Claude can edit directly without review

---

_(no overrides configured — all pages are wiki-owned)_
