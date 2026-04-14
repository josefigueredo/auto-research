# Scheduled Maintenance

Recommended recurring operations. Claude does not install schedules
automatically — these are declarative suggestions for the human to wire
up via Claude Code `/schedule`, cron, or CI.

## Recommended cadence

| Operation | Cadence | Why |
|-----------|---------|-----|
| Lint | Weekly | Catches drift before it compounds |
| Staleness sweep | Monthly | Re-verifies volatile pages, flags stale sources |
| Full quality report | Quarterly | Trend analysis across lint history |
| Cost report | Weekly | Tracks token spend against budgets |

## Example Claude Code `/schedule` config

```bash
/schedule weekly "Lint the wiki and report metrics"
/schedule monthly "Run a staleness sweep on the wiki"
```

## Example cron

```
# Weekly lint on Monday mornings
0 9 * * 1 cd /path/to/wiki && claude -p "lint the wiki"

# Monthly staleness sweep on the 1st
0 9 1 * * cd /path/to/wiki && claude -p "run a staleness sweep"
```

## Status

_(no schedules installed — wire them via your environment's scheduler)_
