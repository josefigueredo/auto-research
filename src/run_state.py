"""Runtime state helpers for the autoresearch loop."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .backends import AgentResponse
from .strategy import ResearchCandidate


@dataclass
class UsageTotals:
    """Mutable usage/accounting state for a run."""

    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    per_backend_costs: dict[str, float] = field(default_factory=dict)
    per_backend_tokens: dict[str, dict[str, int]] = field(default_factory=dict)


def track_cost(usage: UsageTotals, cost: float, backend_name: str = "") -> None:
    """Add cost to totals."""
    usage.total_cost += cost
    if backend_name:
        usage.per_backend_costs[backend_name] = usage.per_backend_costs.get(backend_name, 0.0) + cost


def track_usage(usage: UsageTotals, resp: AgentResponse, backend_name: str = "") -> None:
    """Add cost and token counts to totals and per-backend tracking."""
    track_cost(usage, resp.cost_usd, backend_name)
    usage.total_input_tokens += resp.input_tokens
    usage.total_output_tokens += resp.output_tokens
    if backend_name:
        entry = usage.per_backend_tokens.setdefault(backend_name, {"input": 0, "output": 0})
        entry["input"] += resp.input_tokens
        entry["output"] += resp.output_tokens


def track_candidate_usage(usage: UsageTotals, candidate: ResearchCandidate) -> None:
    """Record usage for a strategy-produced research candidate."""
    track_usage(
        usage,
        AgentResponse(
            text=candidate.findings,
            cost_usd=candidate.cost_usd,
            is_error=False,
            input_tokens=candidate.input_tokens,
            output_tokens=candidate.output_tokens,
        ),
        candidate.backend_name,
    )


def resume_state(
    *,
    iterations_dir: Path,
    results_path: Path,
    knowledge_base_path: Path,
    configured_dimensions: tuple[str, ...] | list[str],
    max_attempts_per_dimension: int,
) -> dict[str, Any]:
    """Rebuild mutable state from existing iteration files and TSV."""
    existing = sorted(iterations_dir.glob("iter_*.md"))
    if not existing:
        return {
            "iteration": 0,
            "results": [],
            "best_score": 0.0,
            "best_scores": {},
            "explored_dimensions": [],
            "discovered_dimensions": [],
            "dimension_attempts": {},
            "knowledge_base": knowledge_base_path.read_text(encoding="utf-8") if knowledge_base_path.exists() else "",
        }

    results: list[dict[str, str]] = []
    best_score = 0.0
    best_scores: dict[str, float] = {}
    explored_dimensions: list[str] = []
    discovered_dimensions: list[str] = []
    dimension_attempts: dict[str, int] = {}

    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                results.append(dict(row))
                dim = row.get("dimension", "")
                status = row.get("status", "")

                if dim:
                    dimension_attempts[dim] = dimension_attempts.get(dim, 0) + 1

                if status == "keep":
                    try:
                        score = float(row.get("total_score", 0))
                    except (ValueError, TypeError):
                        score = 0.0

                    if dim:
                        if score > best_scores.get(dim, 0.0):
                            best_scores[dim] = score
                        if dim not in explored_dimensions:
                            explored_dimensions.append(dim)

                    if score > best_score:
                        best_score = score

                gaps_raw = row.get("discovered_gaps", "")
                if gaps_raw:
                    try:
                        gaps = json.loads(gaps_raw)
                    except (json.JSONDecodeError, TypeError):
                        gaps = []
                    for gap in gaps:
                        if (
                            gap
                            and gap not in explored_dimensions
                            and gap not in configured_dimensions
                            and gap not in discovered_dimensions
                        ):
                            discovered_dimensions.append(gap)

                if dim and dimension_attempts.get(dim, 0) >= max_attempts_per_dimension:
                    if dim not in explored_dimensions:
                        explored_dimensions.append(dim)

    knowledge_base = knowledge_base_path.read_text(encoding="utf-8") if knowledge_base_path.exists() else ""
    return {
        "iteration": len(existing),
        "results": results,
        "best_score": best_score,
        "best_scores": best_scores,
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
        "dimension_attempts": dimension_attempts,
        "knowledge_base": knowledge_base,
    }


def merge_findings(
    *,
    dimension: str,
    findings: str,
    gaps: list[str],
    knowledge_base: str,
    explored_dimensions: list[str],
    discovered_dimensions: list[str],
    configured_dimensions: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Merge kept findings into the knowledge base and update dimension tracking."""
    if dimension not in explored_dimensions:
        explored_dimensions.append(dimension)

    knowledge_base += f"\n\n## {dimension}\n\n" + findings
    for gap in gaps:
        if (
            gap not in explored_dimensions
            and gap not in configured_dimensions
            and gap not in discovered_dimensions
        ):
            discovered_dimensions.append(gap)

    return {
        "knowledge_base": knowledge_base,
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
    }


def maybe_exhaust_dimension(
    *,
    dimension: str,
    dimension_attempts: dict[str, int],
    explored_dimensions: list[str],
    max_attempts_per_dimension: int,
) -> bool:
    """Mark a dimension as explored if it has reached max attempts."""
    if dimension_attempts.get(dimension, 0) >= max_attempts_per_dimension:
        if dimension not in explored_dimensions:
            explored_dimensions.append(dimension)
        return True
    return False
