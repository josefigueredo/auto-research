# Scientific Rigor Roadmap

## Context

Autoresearch is a methodologically-aware autonomous research system, not a
fully validated scientific research engine. This document captures a
literature-informed roadmap for closing the gap, based on PRISMA, GRADE,
PROSPERO, and reproducibility standards.

Research conducted by Codex (April 2026) using web search against primary
sources.

## Current positioning

- **Autonomous agent research system?** Yes
- **Professional research workflow?** Yes
- **Full scientific rigor?** Not yet
- **Useful and serious?** Definitely yes

The system should evolve from *agentic research automation* to
*protocol-driven, independently-audited evidence synthesis*.

---

## 1. Pre-registered review protocols

Before a run, freeze: question, scope, inclusion/exclusion criteria, search
sources, stopping criteria, scoring rules.

This is the closest analogue to preregistration and systematic review
protocols. It reduces hindsight bias and post-hoc criterion drift.

**Current state:** `methodology:` section exists with question, scope,
inclusion/exclusion criteria. Frozen in `run_manifest.json` + `methods.md`.

**Gap:** Missing explicit search sources declaration, stopping criteria
rationale, scoring rule justification. These are config fields.

**Sources:**
- PRISMA 2020: https://www.bmj.com/content/372/bmj.n71
- PROSPERO overview: https://pubmed.ncbi.nlm.nih.gov/31173570/
- OSF preregistration: https://help.osf.io/article/111-updated-registrations-the-interface

---

## 2. Dual independent review for study selection and extraction

For each candidate source/claim: run two independent extractors/judges,
compare decisions, require adjudication on disagreement. Compute inter-rater
reliability (Cohen's kappa).

**Current state:** `adversarial` and `ensemble` strategies run 2+ independent
backends. Adversarial has critique + adjudication.

**Gap:** No inter-rater agreement metrics computed or reported. The
infrastructure exists but agreement is not quantified.

**Sources:**
- Inter-rater reliability / kappa: https://pmc.ncbi.nlm.nih.gov/articles/PMC3900052/
- PRISMA 2020 explanation: https://www.bmj.com/content/372/bmj.n160

---

## 3. GRADE-like certainty model

For each key conclusion, rate evidence on explicit domains: risk of bias,
inconsistency, indirectness, imprecision, publication bias. Produce evidence
tables, summary of findings, and certainty labels tied to explicit criteria.

**Current state:** "high/medium/low/unresolved" confidence labels via regex.
Rubric has `uncertainty_reporting` dimension.

**Gap:** Labels are surface-level keywords, not structured assessment. GRADE
requires rating each conclusion on 5 domains.

**Sources:**
- GRADE Working Group: https://www.gradeworkinggroup.org/
- GRADE handbook: https://www.cochrane.org/hr/learn/courses-and-resources/cochrane-methodology/grade-approach/grade-handbook

---

## 4. PRISMA-style reporting artifacts

Add: search log, source screening log, exclusion reasons, flow diagram,
final evidence table.

**Current state:** `claims.json`, `citations.json`, `evidence_links.json`,
`methods.md`, `rubric.json` exist.

**Gap:** No search log (what URLs were fetched and when), no screening log
(which sources were included/excluded and why), no exclusion reasons per
source, no PRISMA flow diagram.

**Sources:**
- PRISMA 2020 statement: https://www.bmj.com/content/372/bmj.n71
- PRISMA explanation/elaboration: https://www.bmj.com/content/372/bmj.n160

---

## 5. Artifact-grade reproducibility

Every result should be reproducible with: fixed config, frozen prompts, exact
model/backend versions, saved raw outputs, one-command rerun, archived
artifacts.

**Current state:** `run_manifest.json` captures config snapshot, git commit,
backend versions, timestamps. `--resume` rebuilds state.

**Gap:** Prompt templates not snapshotted per-run, raw CLI stdout not saved,
no one-command exact-rerun script.

**Sources:**
- National Academies reproducibility: https://www.ncbi.nlm.nih.gov/books/NBK547531/
- ACM artifact review and badging: https://reviewers.acm.org/training-course/artifact-review-and-badging
- Reproducibility standards for ML: https://www.nature.com/articles/s41592-021-01256-7

---

## 6. External validation against gold-standard tasks

Benchmark tasks with human-verified gold answers, blinded human review,
repeated runs, variance estimates, calibration curves.

**Current state:** Benchmark catalog exists (`benchmarks/`). Rubric
calibration tests exist (positive/negative/mediocre controls).

**Gap:** No human-verified gold answers, no blinded human review protocol, no
variance estimates, no calibration curves. This is a research program, not a
code change.

**Sources:**
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST trustworthy AI: https://www.nist.gov/node/1674681

---

## Implementation priority

| Effort | Item | Impact |
|---|---|---|
| Small (1 session) | Inter-rater agreement (kappa) for ensemble/adversarial | Quantifies dual-review claim |
| Small (1 session) | Search + screening log artifacts | PRISMA items 1-2 of 4 |
| Small (config only) | Extend `methodology:` fields | Completes pre-registration |
| Medium (2-3 sessions) | Raw output snapshots + frozen prompts per run | Full reproducibility |
| Medium (2-3 sessions) | GRADE-lite certainty tables | Biggest quality signal upgrade |
| Large (ongoing) | Gold-standard benchmarks with human answers | External validation |

## Recommended first step

Add inter-rater agreement metrics to ensemble/adversarial strategies. The
infrastructure already exists; computing kappa is ~50 lines. This turns the
"dual independent review" from aspirational to quantifiable.

## Strongest single upgrade (from Codex)

Add a **Systematic Review Mode** combining:
1. Pre-registered protocol
2. Dual independent screening/extraction
3. GRADE-style certainty tables
4. PRISMA-style reporting

This would move the system from *agentic research automation* to
*protocol-driven, independently-audited evidence synthesis*.
