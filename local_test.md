# Local Test — CPU Edition

A lightweight test of the autoresearch loop pattern that runs on any machine
without GPU or API keys. Uses a numpy neural network on synthetic data.

## Purpose

Validate the core loop mechanics — hypothesis, execute, measure, keep/revert —
before running the full Claude Code agent version or pointing it at real GPU
training.

## How to Run

```bash
cd C:\Users\josef\Code\autoresearch-claude
python autoresearch_runner.py
```

No dependencies beyond numpy. Completes in ~30 seconds.

## What It Does

1. **Baseline**: Train a 2-layer MLP on synthetic sine wave data.
2. **Loop**: Run 10 experiments, each changing exactly one variable:
   - Hidden layer size, learning rate, depth, activation function,
     training steps, batch size, learning rate decay
3. **Decide**: If val_loss improved, KEEP (update baseline config).
   Otherwise, DISCARD (revert to previous best).
4. **Log**: Write all results to `results.tsv`.

## Example Output

```
  Experiment   val_loss     Status     Description
  baseline     0.133491     keep       2-layer MLP, lr=0.01, hidden=[32]
  exp_001      0.139147     discard    double hidden size (32 -> 64)
  exp_005      0.114398     keep       increase training steps (200 -> 500)
  exp_009      0.106534     keep       two hidden layers of 64
  exp_010      0.069322     keep       increase learning rate (0.01 -> 0.03)

  Baseline: 0.1335 -> Best: 0.0693 (48.1% improvement)
  Kept: 3 / Discarded: 7
```

## Mapping to the Full Framework

| Local Test | autoresearch-claude |
|------------|---------------------|
| numpy MLP training | `claude -p` research call |
| `val_loss` (lower = better) | `total_score` (higher = better) |
| Predefined experiment list | Claude-generated hypotheses |
| Config keep/revert in memory | Knowledge base merge/skip |
| `results.tsv` (4 columns) | `results.tsv` (9 columns) |
| 10 experiments, then stop | Infinite loop until Ctrl+C |
