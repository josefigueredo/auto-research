"""Hybrid scoring: heuristic analysis + LLM-as-judge."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ResearchConfig

JUDGE_SCHEMA = {
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
    coverage: float = 0.0
    quality: float = 0.0
    total: float = 0.0
    dimensions_covered: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    judge_raw: dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "keep" if self.total > 0 else "discard"


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
    """Return a coverage score from 0 to 100."""
    points = 0.0
    max_points = 0.0

    # --- Dimension mentions (40 pts) ---
    max_points += 40.0
    all_dims = list(config.dimensions)
    mentioned = sum(
        1
        for d in all_dims
        if _fuzzy_match(d, findings)
    )
    if all_dims:
        points += 40.0 * min(mentioned / max(config.scoring.min_dimensions_per_iteration, 1), 1.0)

    # --- Evidence types (35 pts) ---
    max_points += 35.0
    types_found = sum(
        1
        for etype, pattern in _EVIDENCE_PATTERNS.items()
        if etype in config.scoring.evidence_types and pattern.search(findings)
    )
    target = len(config.scoring.evidence_types)
    if target:
        points += 35.0 * min(types_found / target, 1.0)

    # --- New questions discovered (15 pts) ---
    max_points += 15.0
    new_q_section = _extract_section(findings, "New Questions")
    if new_q_section:
        bullet_count = len(re.findall(r"^[\s]*[-*\d]", new_q_section, re.MULTILINE))
        points += 15.0 * min(bullet_count / 3.0, 1.0)

    # --- Substantive length (10 pts) ---
    max_points += 10.0
    word_count = len(findings.split())
    points += 10.0 * min(word_count / 500.0, 1.0)

    return round(100.0 * points / max_points, 1) if max_points else 0.0


# ---------------------------------------------------------------------------
# LLM judge scoring
# ---------------------------------------------------------------------------

def parse_judge_response(raw_text: str) -> dict:
    """Extract JSON from the judge's response, tolerating markdown fences."""
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


def quality_score_from_judge(judge: dict) -> float:
    """Convert judge axes (1-10 each) into a 0-100 quality score."""
    axes = ["depth", "accuracy", "novelty", "actionability"]
    raw = sum(judge.get(a, 5) for a in axes)
    return round(raw / (len(axes) * 10) * 100.0, 1)


def combine_scores(coverage: float, quality: float) -> float:
    """Weighted combination: 40% heuristic, 60% judge."""
    return round(0.4 * coverage + 0.6 * quality, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fuzzy_match(dimension: str, text: str) -> bool:
    """Check if key terms from a dimension label appear in the text."""
    keywords = [w.lower() for w in dimension.split() if len(w) > 3]
    if not keywords:
        return False
    matches = sum(1 for kw in keywords if kw in text.lower())
    return matches >= max(len(keywords) // 2, 1)


def _extract_section(text: str, heading: str) -> str:
    """Extract content under a markdown heading."""
    pattern = rf"^#+\s*{re.escape(heading)}.*?\n(.*?)(?=^#+\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""
