# AutoResearch Local Test — CPU Edition

A faithful miniature of [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch),
designed to run on any machine (no GPU required) in under 2 minutes.

---

## What This Tests

The original autoresearch loop optimizes a GPT model on a single GPU in 5-minute
experiment cycles. This local test applies the **exact same pattern** to a smaller
problem: optimizing a numpy neural network on synthetic data.

The goal is to validate that the loop works — hypothesis, execute, measure, evaluate,
keep/revert — before pointing it at expensive GPU workloads.

---

## The Pattern (Mirrors `program.md`)

```
LOOP:
  1. Propose   — Pick an experiment (architecture, hyperparameters, etc.)
  2. Execute   — Train the model with the new configuration
  3. Measure   — Record validation loss (lower is better, like val_bpb)
  4. Evaluate  — Compare against the current best
  5. Decide    — If improved: KEEP. If not: REVERT.
  6. Log       — Append result to results.tsv
```

---

## Step-by-Step Explanation

### Step 0 — Initialize

- Generate a synthetic regression dataset (sine wave + noise).
- Split into train (80%) and validation (20%).
- Define a baseline config: small 2-layer neural network, learning rate 0.01,
  batch size 32, 200 training steps.
- This mirrors the "first run = establish baseline" rule from `program.md`.

### Step 1 — Baseline Run

- Train with default config.
- Record validation MSE as the **baseline metric** (equivalent to `val_bpb`).
- Log to `results.tsv` with status `keep`.

### Step 2..N — Experiment Loop

Each iteration:

1. **Hypothesis**: The runner picks the next experiment from a predefined list.
   Each experiment modifies exactly **one variable** (single-variable testing,
   per the MindStudio article's guidance). Examples:
   - Double the hidden layer size (32 -> 64)
   - Halve the learning rate (0.01 -> 0.005)
   - Add a third hidden layer
   - Switch activation from ReLU to Tanh
   - Increase training steps (200 -> 400)
   - Increase batch size (32 -> 64)
   - Add learning rate decay

2. **Execute**: Train a fresh model with the modified config for a fixed time
   budget (mirrors the 5-minute wall-clock constraint — here scaled to ~2 seconds).

3. **Measure**: Evaluate on the held-out validation set. Record val_loss (MSE).

4. **Evaluate**: Compare val_loss against the current best.

5. **Decide**:
   - If val_loss < best: **KEEP** — this becomes the new baseline config.
   - If val_loss >= best: **DISCARD** — revert to previous best config.

6. **Log**: Append a row to `results.tsv` with experiment ID, val_loss, status,
   and description.

### Step Final — Summary

- Print the full results table.
- Print the best configuration found.
- Print improvement over baseline (percentage).

---

## Output Files

| File | Purpose |
|------|---------|
| `results.tsv` | Tab-separated log of all experiments (like the original) |
| `autoresearch_local_test.md` | This file — the test plan |
| `autoresearch_runner.py` | The executable script |

### results.tsv Format (Same as Original)

```
experiment	val_loss	status	description
baseline	0.042310	keep	2-layer MLP, lr=0.01, hidden=32, steps=200
exp_001 	0.038200	keep	double hidden size (32 -> 64)
exp_002 	0.041500	discard	halve learning rate (0.01 -> 0.005)
```

---

## How to Run

```bash
cd C:\Users\josef\Code\OpenResearch
python autoresearch_runner.py
```

No dependencies beyond numpy (included in the project's venv). Runs in ~30 seconds.

---

## Mapping to the Original

| Original (`program.md`) | Local Test |
|--------------------------|------------|
| `train.py` on GPU | numpy MLP on CPU |
| `val_bpb` (bits per byte) | `val_loss` (MSE) |
| 5-minute time budget | ~2-second time budget per experiment |
| LLM agent proposes changes | Predefined experiment queue |
| `git commit` / `git reset` | Config keep/revert in memory |
| `results.tsv` (5 columns) | `results.tsv` (4 columns) |
| Runs indefinitely | Runs N experiments then stops |

The key difference: the original uses an LLM agent to **generate** hypotheses.
This test uses a fixed experiment list. To close that gap, point Claude Code at
this runner with instructions to propose and execute new experiments — that
completes the loop.

---

## Next Step: Full Agent Loop

Once this test validates the pattern, the real autoresearch loop can be run by:

1. Setting up GPU access (local or EC2 — g5.xlarge for A10G, p4d.24xlarge for A100)
2. Running `uv run prepare.py` to download data
3. Pointing Claude Code at `program.md` and letting it iterate on `train.py`
