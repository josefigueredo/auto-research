"""Hybrid scoring: heuristic analysis + LLM-as-judge.

The heuristic scorer counts evidence types, dimension mentions, and
structural markers in research findings.  The LLM judge provides a
qualitative assessment via a separate Claude call.  Both scores are
combined with configurable weights.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .config import ResearchConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEURISTIC_WEIGHT = 0.4
JUDGE_WEIGHT = 0.6

# Point allocation for heuristic scoring components
_DIMENSION_POINTS = 40.0
_EVIDENCE_POINTS = 35.0
_NEW_QUESTIONS_POINTS = 15.0
_LENGTH_POINTS = 10.0
_TARGET_WORD_COUNT = 500.0
_TARGET_NEW_QUESTIONS = 3.0
_MAX_FINDINGS_CHARS = 8000

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "depth": {"type": "integer", "minimum": 1, "maximum": 10},
        "accuracy": {"type": "integer", "minimum": 1, "maximum": 10},
        "novelty": {"type": "integer", "minimum": 1, "maximum": 10},
        "actionability": {"type": "integer", "minimum": 1, "maximum": 10},
        "dimensions_covered": {
            "type": "array",
            "items": {"type": "string"},
        },
        "gaps_identified": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reasoning": {"type": "string"},
    },
    "required": [
        "depth",
        "accuracy",
        "novelty",
        "actionability",
        "dimensions_covered",
        "gaps_identified",
        "reasoning",
    ],
    "additionalProperties": False,
}


@dataclass
class IterationScore:
    """Scores for a single research iteration.

    Attributes:
        coverage: Heuristic coverage score (0-100).
        quality: LLM judge quality score (0-100).
        total: Weighted combination of coverage and quality (0-100).
        dimensions_covered: Dimensions the judge identified as covered.
        gaps: Knowledge gaps the judge identified.
        judge_raw: Raw JSON response from the LLM judge.
    """

    coverage: float = 0.0
    quality: float = 0.0
    total: float = 0.0
    dimensions_covered: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    judge_raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heuristic scoring (deterministic, fast)
# ---------------------------------------------------------------------------

_EVIDENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "comparison_table": re.compile(r"\|.*\|.*\|", re.MULTILINE),
    "pricing_data": re.compile(r"\$[\d,.]+|USD|per.?million|free.?tier", re.IGNORECASE),
    "code_example": re.compile(r"```"),
    "architecture_diagram_description": re.compile(
        r"architecture|diagram|flow|topology", re.IGNORECASE
    ),
    "trade_off_analysis": re.compile(
        r"trade.?off|downside|caveat|however|on the other hand", re.IGNORECASE
    ),
}


def heuristic_score(
    findings: str,
    config: ResearchConfig,
    explored_dimensions: list[str],
) -> float:
    """Score research findings using deterministic heuristics.

    Evaluates four components:
    - Dimension mentions (``_DIMENSION_POINTS`` pts)
    - Evidence types found (``_EVIDENCE_POINTS`` pts)
    - New questions discovered (``_NEW_QUESTIONS_POINTS`` pts)
    - Substantive word count (``_LENGTH_POINTS`` pts)

    Args:
        findings: Raw markdown findings text.
        config: Research config with dimensions and scoring settings.
        explored_dimensions: Previously explored dimensions (unused
            currently, reserved for future weighting).

    Returns:
        A coverage score from 0.0 to 100.0.
    """
    if not findings:
        return 0.0

    points = 0.0
    max_points = _DIMENSION_POINTS + _EVIDENCE_POINTS + _NEW_QUESTIONS_POINTS + _LENGTH_POINTS

    # --- Dimension mentions ---
    all_dims = list(config.dimensions)
    if all_dims:
        mentioned = sum(1 for d in all_dims if _fuzzy_match(d, findings))
        points += _DIMENSION_POINTS * min(
            mentioned / max(config.scoring.min_dimensions_per_iteration, 1), 1.0
        )
    else:
        # No dimensions configured — don't penalise, redistribute weight
        max_points -= _DIMENSION_POINTS

    # --- Evidence types ---
    types_found = sum(
        1
        for etype, pattern in _EVIDENCE_PATTERNS.items()
        if etype in config.scoring.evidence_types and pattern.search(findings)
    )
    target = len(config.scoring.evidence_types)
    if target:
        points += _EVIDENCE_POINTS * min(types_found / target, 1.0)

    # --- New questions discovered ---
    new_q_section = _extract_section(findings, "New Questions")
    if new_q_section:
        bullet_count = len(re.findall(r"^[\s]*[-*]\s", new_q_section, re.MULTILINE))
        points += _NEW_QUESTIONS_POINTS * min(bullet_count / _TARGET_NEW_QUESTIONS, 1.0)

    # --- Substantive length ---
    word_count = len(findings.split())
    points += _LENGTH_POINTS * min(word_count / _TARGET_WORD_COUNT, 1.0)

    return round(100.0 * points / max_points, 1) if max_points > 0 else 0.0


# ---------------------------------------------------------------------------
# LLM judge scoring
# ---------------------------------------------------------------------------

def parse_judge_response(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from the LLM judge's response.

    Tolerates markdown fences and surrounding prose.

    Args:
        raw_text: Raw text output from the judge Claude call.

    Returns:
        Parsed JSON as a dict.

    Raises:
        json.JSONDecodeError: If no valid JSON object can be extracted.
    """
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    elif text.startswith("{"):
        pass
    else:
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]

    return json.loads(text)


def quality_score_from_judge(judge: dict[str, Any]) -> float:
    """Convert LLM judge axes (1-10 each) into a 0-100 quality score.

    Missing axes default to 5 (neutral).

    Args:
        judge: Parsed judge response with ``depth``, ``accuracy``,
            ``novelty``, and ``actionability`` keys.

    Returns:
        Quality score from 0.0 to 100.0.
    """
    axes = ["depth", "accuracy", "novelty", "actionability"]
    raw = sum(judge.get(a, 5) for a in axes)
    return round(raw / (len(axes) * 10) * 100.0, 1)


def combine_scores(coverage: float, quality: float) -> float:
    """Weighted combination of heuristic and judge scores.

    Uses ``HEURISTIC_WEIGHT`` (40%) and ``JUDGE_WEIGHT`` (60%).

    Args:
        coverage: Heuristic coverage score (0-100).
        quality: LLM judge quality score (0-100).

    Returns:
        Combined score from 0.0 to 100.0.
    """
    return round(HEURISTIC_WEIGHT * coverage + JUDGE_WEIGHT * quality, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEEP_THRESHOLD = 30.0


def compute_inter_rater_agreement(
    assessments: list[Any],
    *,
    keep_threshold: float = _KEEP_THRESHOLD,
) -> dict[str, Any]:
    """Compute inter-rater agreement from multi-candidate assessments.

    Groups assessments by dimension.  For each dimension with 2+ candidates,
    records the per-backend scores and whether both backends agreed on the
    keep/discard decision (score >= *keep_threshold*).

    When 2+ dimensions have multi-candidate data, computes Cohen's kappa
    on the binary keep/discard decisions.

    Args:
        assessments: List of ``CandidateAssessment`` objects (from
            ``LoopState.candidate_assessments``).
        keep_threshold: Score at or above which findings are considered
            "keep".  Matches the threshold in ``run_iteration``.

    Returns:
        Agreement summary dict.  Empty ``per_dimension`` list when no
        multi-candidate data exists.
    """
    from collections import defaultdict

    by_dim: dict[str, list[Any]] = defaultdict(list)
    for a in assessments:
        by_dim[a.dimension].append(a)

    per_dimension: list[dict[str, Any]] = []
    for dim, items in by_dim.items():
        if len(items) < 2:
            continue
        entries = [
            {"backend": a.backend_name, "coverage": a.coverage, "quality": a.quality, "total": a.total}
            for a in items
        ]
        decisions = [a.total >= keep_threshold for a in items]
        per_dimension.append({
            "dimension": dim,
            "assessments": entries,
            "decision_agreed": len(set(decisions)) == 1,
        })

    n_dims = len(per_dimension)
    if n_dims == 0:
        return {
            "dimensions_with_multiple_candidates": 0,
            "decision_agreement_rate": None,
            "cohens_kappa": None,
            "mean_score_delta": None,
            "per_dimension": [],
        }

    agreed = sum(1 for d in per_dimension if d["decision_agreed"])
    agreement_rate = round(agreed / n_dims, 2)

    deltas = []
    for d in per_dimension:
        scores = [a["total"] for a in d["assessments"]]
        deltas.append(max(scores) - min(scores))
    mean_delta = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

    kappa = _cohens_kappa(per_dimension, keep_threshold) if n_dims >= 2 else None

    return {
        "dimensions_with_multiple_candidates": n_dims,
        "decision_agreement_rate": agreement_rate,
        "cohens_kappa": kappa,
        "mean_score_delta": mean_delta,
        "per_dimension": per_dimension,
    }


def _cohens_kappa(
    per_dimension: list[dict[str, Any]],
    keep_threshold: float,
) -> float | None:
    """Compute Cohen's kappa on binary keep/discard decisions.

    Uses the first two assessments per dimension as rater A and rater B.
    Returns None if there are fewer than 2 dimensions or if the expected
    agreement is 1.0 (all same category → kappa undefined).
    """
    if len(per_dimension) < 2:
        return None

    # Build 2x2 contingency: (raterA_keep, raterB_keep)
    a_b = {"kk": 0, "kd": 0, "dk": 0, "dd": 0}
    for d in per_dimension:
        items = d["assessments"]
        a_keep = items[0]["total"] >= keep_threshold
        b_keep = items[1]["total"] >= keep_threshold
        if a_keep and b_keep:
            a_b["kk"] += 1
        elif a_keep and not b_keep:
            a_b["kd"] += 1
        elif not a_keep and b_keep:
            a_b["dk"] += 1
        else:
            a_b["dd"] += 1

    n = sum(a_b.values())
    if n == 0:
        return None
    p_o = (a_b["kk"] + a_b["dd"]) / n  # observed agreement
    p_a_keep = (a_b["kk"] + a_b["kd"]) / n
    p_b_keep = (a_b["kk"] + a_b["dk"]) / n
    p_e = p_a_keep * p_b_keep + (1 - p_a_keep) * (1 - p_b_keep)  # expected by chance

    if p_e >= 1.0:
        return None  # degenerate: all same category
    return round((p_o - p_e) / (1.0 - p_e), 2)


def _fuzzy_match(dimension: str, text: str) -> bool:
    """Check if key terms from a dimension label appear in the text.

    Words with 3 or fewer characters are ignored.  A match requires at
    least half of the remaining keywords to be present (case-insensitive).
    """
    keywords = [w.lower() for w in dimension.split() if len(w) > 3]
    if not keywords:
        return False
    matches = sum(1 for kw in keywords if kw in text.lower())
    return matches >= max(len(keywords) // 2, 1)


def _extract_section(text: str, heading: str) -> str:
    """Extract the content under a markdown heading.

    Returns the text between the matched heading and the next heading of
    equal or higher level, or end of string.
    """
    pattern = rf"^#+\s*{re.escape(heading)}.*?\n(.*?)(?=^#+\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""
