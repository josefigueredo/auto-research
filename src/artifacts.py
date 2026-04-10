"""Artifact payload builders and filesystem loading helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def load_json_if_exists(path: Path, default: Any) -> Any:
    """Return parsed JSON from *path* when it exists, else *default*."""
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_manifest_payload(
    *,
    config: Any,
    strategy_description: str,
    backends: dict[str, Any],
    output_dir: Path,
    resume: bool,
    config_path: Path | None,
    run_status: str,
    run_started_at: str | None,
    run_completed_at: str | None,
    package_version: str | None,
    git_commit: str | None,
    cli_version_resolver: Any,
) -> dict[str, Any]:
    """Build the machine-readable manifest payload for a run."""
    return {
        "project": {
            "name": "autoresearch",
            "version": package_version,
        },
        "run": {
            "status": run_status,
            "started_at": run_started_at,
            "completed_at": run_completed_at,
            "resume_requested": resume,
            "output_dir": str(output_dir.resolve()),
        },
        "config": {
            "path": str(config_path.resolve()) if config_path else None,
            "snapshot": asdict(config),
        },
        "strategy": {
            "name": config.execution.strategy,
            "description": strategy_description,
        },
        "evaluation": {
            "benchmark_id": config.evaluation.benchmark_id,
            "run_baselines": config.evaluation.run_baselines,
            "semantic_review": config.evaluation.semantic_review,
        },
        "reporting": {
            "export_html": config.reporting.export_html,
            "export_pdf": config.reporting.export_pdf,
            "report_title": config.reporting.report_title,
        },
        "environment": {
            "python_version": __import__("platform").python_version(),
            "platform": __import__("platform").platform(),
            "git_commit": git_commit,
        },
        "backends": {
            name: {
                "cli": backend.cli_executable(),
                "version": cli_version_resolver(backend.cli_executable()),
            }
            for name, backend in backends.items()
        },
    }


def metrics_payload(
    *,
    benchmark_id: str,
    run_status: str,
    iteration: int,
    best_score: float,
    explored_dimensions: list[str],
    discovered_dimensions: list[str],
    total_cost: float,
    total_input_tokens: int,
    total_output_tokens: int,
    per_backend_costs: dict[str, float],
    per_backend_tokens: dict[str, dict[str, int]],
    results: list[dict[str, str]],
) -> dict[str, Any]:
    """Build the machine-readable metrics payload."""
    return {
        "run_status": run_status,
        "benchmark_id": benchmark_id,
        "iterations": iteration,
        "best_score": best_score,
        "explored_dimensions_count": len(explored_dimensions),
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
        "total_cost_usd": total_cost,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "per_backend_costs": per_backend_costs,
        "per_backend_tokens": per_backend_tokens,
        "results": results,
    }


def should_write_evaluation(config: Any) -> bool:
    """Return True when any evaluation artifact should be emitted."""
    return bool(
        config.evaluation.run_baselines
        or config.evaluation.benchmark_id
        or config.evaluation.reference_runs
        or config.evaluation.semantic_review
    )


def evaluation_payload(
    *,
    benchmark_id: str,
    baseline_exists: bool,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    evidence_quality: dict[str, Any],
    rubric: dict[str, Any],
    benchmark_summary: dict[str, Any],
    reference_comparison: dict[str, Any],
    semantic_review: dict[str, Any],
    semantic_calibration: dict[str, Any],
) -> dict[str, Any]:
    """Build the aggregated evaluation artifact payload."""
    baseline_claims = [claim for claim in claims if claim.get("scope") == "baseline"]
    synthesis_claims = [claim for claim in claims if claim.get("scope") == "synthesis"]
    baseline_citations = [citation for citation in citations if citation.get("scope") == "baseline"]
    synthesis_citations = [citation for citation in citations if citation.get("scope") == "synthesis"]
    return {
        "benchmark_id": benchmark_id,
        "baseline_generated": baseline_exists,
        "iterative_synthesis": {
            "claims_count": len(synthesis_claims),
            "citations_count": len(synthesis_citations),
        },
        "baseline": {
            "claims_count": len(baseline_claims),
            "citations_count": len(baseline_citations),
        },
        "evidence_quality": evidence_quality,
        "rubric": rubric,
        "benchmark": benchmark_summary,
        "reference_comparison": reference_comparison,
        "semantic_review": semantic_review,
        "semantic_calibration": semantic_calibration,
        "summary": {
            "iterative_has_more_claims_than_baseline": len(synthesis_claims) > len(baseline_claims),
            "iterative_has_more_citations_than_baseline": len(synthesis_citations) > len(baseline_citations),
            "benchmark_expectations_satisfied": benchmark_summary.get("all_expectations_satisfied", True),
            "reference_runs_compared": reference_comparison.get("compared_runs_count", 0),
            "rubric_grade": rubric.get("grade", "insufficient"),
            "semantic_review_grade": semantic_review.get("grade", "disabled"),
            "semantic_calibration_grade": semantic_calibration.get("grade", "disabled"),
        },
    }


def dashboard_payload(
    *,
    topic: str,
    goal: str,
    benchmark_id: str,
    current_strategy: str,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
    comparison: dict[str, Any],
    evaluation: dict[str, Any],
    strategy_summary: dict[str, Any],
    semantic_calibration: dict[str, Any],
    semantic_review: dict[str, Any],
) -> dict[str, Any]:
    """Build the stakeholder-facing dashboard artifact payload."""
    return {
        "topic": topic,
        "goal": goal,
        "benchmark_id": benchmark_id,
        "current_strategy": current_strategy,
        "best_score": best_score,
        "rubric_grade": rubric.get("grade", "insufficient"),
        "rubric_overall_score": rubric.get("overall_score", 0.0),
        "evidence_quality_score": evidence_quality.get("average_evidence_quality_score", 0.0),
        "iterations": iteration,
        "explored_dimensions_count": len(explored_dimensions),
        "explored_dimensions": explored_dimensions,
        "strategy_summary": strategy_summary,
        "consistency_level": comparison.get("summary", {}).get("consistency_level", "not_available"),
        "reference_runs_compared": comparison.get("compared_runs_count", 0),
        "benchmark_expectations_satisfied": evaluation.get("summary", {}).get(
            "benchmark_expectations_satisfied", True
        ),
        "semantic_calibration": semantic_calibration,
        "semantic_review": semantic_review,
    }


def pdf_run_summary_text(
    *,
    topic: str,
    goal: str,
    strategy: str,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    metrics: dict[str, Any],
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
) -> str:
    """Format core run summary text for PDF export."""
    return (
        f"Topic: {topic}\n"
        f"Goal: {goal}\n"
        f"Strategy: {strategy}\n"
        f"Best score: {metrics.get('best_score', best_score)}\n"
        f"Iterations: {metrics.get('iterations', iteration)}\n"
        f"Rubric grade: {rubric.get('grade', 'insufficient')}\n"
        f"Evidence quality: {evidence_quality.get('average_evidence_quality_score', 0.0)}\n"
        f"Explored dimensions: {', '.join(metrics.get('explored_dimensions', explored_dimensions)) or '(none)'}\n"
    )
