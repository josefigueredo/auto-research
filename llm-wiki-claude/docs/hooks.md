# Hooks

Post-operation triggers that fire after Claude completes a wiki action.
Hooks are wired via Claude Code's `~/.claude/settings.json` hooks
configuration or via CI/scheduler integration — Claude does not install
them automatically.

## Supported trigger points

| Trigger | Fires when | Use case |
|---------|-----------|----------|
| `post-ingest` | After `Operation: ingest` completes | Notify Slack, open a PR, tag a release |
| `post-lint` | After `Operation: lint` completes | Alert if quality degraded |
| `post-query` | After `Operation: query` where `answer_source: not-answered` | Log coverage gaps for future ingestion |
| `post-review-decision` | After `Operation: review` | Notify the requester of the decision |

## Example: Slack notification on ingest

Via Claude Code `PostToolUse` hook (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'if [[ $CLAUDE_FILE_PATHS =~ \"wiki/log.md\" ]]; then curl -X POST $SLACK_WEBHOOK_URL -d \"{\\\"text\\\": \\\"Wiki updated\\\"}\"; fi'"
          }
        ]
      }
    ]
  }
}
```

Simpler: run a post-ingest script the user invokes manually, or wire via
a git hook on commits to `wiki/`.

## Example: GitHub issue on quality regression

Post-lint, if `_quality.md` grade dropped:

```bash
#!/bin/bash
# In a post-lint script or CI job
current=$(grep "Current grade" wiki/_quality.md | awk '{print $NF}')
previous=$(tail -2 wiki/_quality-history.jsonl | head -1 | jq -r .grade)

if [ "$current" = "insufficient" ] && [ "$previous" != "insufficient" ]; then
  gh issue create \
    --title "Wiki quality dropped to insufficient" \
    --body "See \`wiki/_quality.md\` for details"
fi
```

## Example: log coverage gaps

When a query returns `answer_source: not-answered`, append to a gap log:

```bash
# Extract last query op from _operations.jsonl
jq 'select(.op == "query" and .answer_source == "not-answered")' \
  wiki/_operations.jsonl | \
  tail -1 | \
  jq -r '.ts + " | " + .question' \
  >> coverage-gaps.log
```

Review periodically and ingest sources that fill the gaps.

## Git hooks

Pre-commit on wiki/ changes: run lint first, fail the commit if grade
is `insufficient`:

```bash
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -q "^wiki/"; then
  grade=$(grep "Current grade" wiki/_quality.md | awk '{print $NF}')
  if [ "$grade" = "insufficient" ]; then
    echo "Wiki grade is insufficient. Fix before committing."
    exit 1
  fi
fi
```

## Claude Code SessionStart hook

Run a lint on every new Claude Code session in the wiki directory:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -f wiki/_quality.md ]; then head -20 wiki/_quality.md; fi"
          }
        ]
      }
    ]
  }
}
```

This shows the current quality dashboard in the session transcript so
every conversation starts with awareness of wiki health.
