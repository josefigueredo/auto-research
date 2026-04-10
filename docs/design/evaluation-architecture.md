# Evaluation Architecture

## Why this exists

The framework started as a lean autonomous research loop:

1. generate a hypothesis
2. execute research
3. score findings
4. keep or discard
5. synthesize a final deliverable

As the project gained provenance, benchmarking, reporting, and semantic review,
the evaluation surface expanded faster than the design docs. This note defines
the evaluation stack so future work can extend it without further bloating the
orchestrator.

## Design goals

- Keep the **core loop** small and understandable.
- Treat advanced evaluation as **optional research-ops layers**.
- Prefer **artifact-first evaluation**: score from structured run artifacts
  before adding more model calls.
- Make cross-run and benchmark comparisons **machine-readable**.
- Allow short-form and lightweight runs to be scored fairly without forcing
  every deliverable to look like a long report.

## Core vs optional

### Core runtime

These responsibilities define the framework itself:

- config loading and backend selection
- hypothesis generation
- research execution via strategy
- heuristic + judge iteration scoring
- keep/discard merge policy
- resume and accounting
- synthesis generation

### Optional research-ops layers

These are valuable, but they are not required to use the core loop:

- provenance extraction (`claims.json`, `citations.json`)
- evidence linking and contradiction detection
- rubric scoring and evidence-quality summaries
- baseline comparison
- benchmark expectation checks
- reference-run consistency comparison
- semantic review and semantic calibration
- HTML/PDF/portfolio reporting

Users should be able to understand and adopt the core loop without opting into
the full research-ops suite.

## Evaluation data flow

```text
iteration findings / synthesis / baseline
    -> claims + citations
    -> evidence links + contradiction detection
    -> evidence quality summary
    -> rubric scoring
    -> benchmark comparison
    -> reference-run comparison
    -> semantic review (optional model pass)
    -> semantic calibration
    -> dashboard / report artifacts
```

## Modules and responsibilities

### `src/provenance.py`

Owns single-run extraction and scoring derived from generated text:

- claim extraction
- citation extraction
- claim-to-citation linking
- contradiction detection
- evidence-quality summary
- rubric scoring

This module should stay focused on **within-run structured evidence**.

### `src/comparison.py`

Owns comparisons against external expectations or past runs:

- benchmark catalog loading
- benchmark expectation matching
- claim normalization for overlap analysis
- reference-run comparison
- strategy summary rollups

This module should stay focused on **cross-artifact and cross-run comparison**.

### `src/semantic_eval.py`

Owns higher-level semantic assessment helpers:

- semantic-review normalization/fallbacks
- semantic calibration
- calibration weight profiles

This module should stay focused on **meta-evaluation of run quality**.

### `src/artifacts.py`

Owns artifact payload construction and lightweight filesystem helpers:

- manifest payload assembly
- metrics payload assembly
- evaluation payload assembly
- dashboard payload assembly
- PDF run-summary text
- JSON artifact loading helpers

This module should stay focused on **artifact contracts**, not orchestration.

### `src/constraints.py`

Owns output-shape and lightweight execution rules:

- lightweight mode detection
- goal constraint summaries
- bullet/word-limit postprocessing
- synthesis context trimming

This module isolates a class of “prompt obedience vs artifact bloat” fixes from
the main orchestration loop.

### `src/orchestrator.py`

Should only coordinate:

- runtime state
- backend calls
- phase ordering
- artifact write orchestration

It should **call** the above modules, not re-implement their logic.

## Artifact contract

### Core artifacts

- `results.tsv`
- `knowledge_base.md`
- `synthesis.md`
- `run_manifest.json`
- `metrics.json`
- `methods.md`

### Optional evaluation artifacts

- `claims.json`
- `citations.json`
- `evidence_links.json`
- `evidence_quality.json`
- `contradictions.json`
- `rubric.json`
- `evaluation.json`
- `comparison.json`
- `strategy_summary.json`
- `semantic_review.json`
- `semantic_calibration.json`
- `dashboard.json`

### Optional reporting artifacts

- `report.html`
- `report.pdf`
- `portfolio.json`
- `portfolio.html`

## Guidance for future features

When adding new capabilities:

1. Decide whether the feature is **core** or **optional**.
2. If it only consumes existing artifacts, prefer adding it to an extracted
   helper module instead of the orchestrator.
3. If it needs a new model pass, justify why artifact-derived scoring is not
   sufficient.
4. Add or update a machine-readable artifact before expanding the HTML/PDF
   layer.
5. Keep short-form/lightweight runs first-class: do not force report-oriented
   metrics onto tiny deliverables.

## Planned follow-up

- further trim `src/orchestrator.py` by moving remaining artifact-writing and
  report-assembly helpers behind narrower interfaces
- keep the evaluation stack documented here as features evolve

## Refactor changelog

### 2026-04-10 — orchestrator responsibility extraction

This cleanup pass moved non-runtime concerns out of `src/orchestrator.py` into
focused helper modules:

- `src/constraints.py` — goal-shape enforcement and lightweight-mode helpers
- `src/comparison.py` — benchmark and reference-run comparison helpers
- `src/semantic_eval.py` — semantic calibration and semantic-review helpers
- `src/artifacts.py` — manifest/metrics/evaluation/dashboard payload builders

Measured against the previous committed state, `src/orchestrator.py` shrank by
**561 lines** (from **2002** to **1441** lines) while preserving behavior.

The orchestrator now more clearly owns:

- runtime state
- backend call sequencing
- iteration lifecycle
- artifact write timing

The extracted modules now own:

- pure constraint logic
- pure comparison logic
- pure semantic-evaluation logic
- artifact payload contracts
