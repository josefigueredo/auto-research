"""Benchmark and cross-run comparison helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def normalize_claim_text(text: str) -> str:
    """Normalize claim text for crude overlap comparisons."""
    return " ".join(text.lower().split())


def load_benchmark_definition(benchmark_id: str, *, benchmarks_dir: Path | None = None) -> dict[str, Any]:
    """Load a bundled benchmark definition when ``benchmark_id`` maps to a YAML file."""
    benchmark_id = benchmark_id.strip()
    if not benchmark_id:
        return {}

    benchmark_root = benchmarks_dir or Path("benchmarks")
    benchmark_path = benchmark_root / f"{benchmark_id}.yaml"
    if not benchmark_path.exists():
        return {}

    with benchmark_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return {
        "benchmark_id": raw.get("benchmark_id", benchmark_id),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "expected_dimensions": list(raw.get("expected_dimensions", [])),
        "required_keywords": list(raw.get("required_keywords", [])),
    }


def benchmark_summary(
    *,
    benchmark_id: str,
    config_expected_dimensions: list[str],
    config_required_keywords: list[str],
    knowledge_text: str,
    synthesis_text: str,
    benchmarks_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate current run outputs against optional benchmark expectations."""
    benchmark_definition = load_benchmark_definition(benchmark_id, benchmarks_dir=benchmarks_dir)
    expected_dimensions = config_expected_dimensions or list(benchmark_definition.get("expected_dimensions", []))
    required_keywords = config_required_keywords or list(benchmark_definition.get("required_keywords", []))
    searchable_text = f"{knowledge_text}\n\n{synthesis_text}".lower()

    covered_dimensions = [dim for dim in expected_dimensions if dim.lower() in searchable_text]
    matched_keywords = [kw for kw in required_keywords if kw.lower() in searchable_text]

    dimension_score = len(covered_dimensions) / len(expected_dimensions) if expected_dimensions else 1.0
    keyword_score = len(matched_keywords) / len(required_keywords) if required_keywords else 1.0
    all_expectations_satisfied = (
        len(covered_dimensions) == len(expected_dimensions)
        and len(matched_keywords) == len(required_keywords)
    )

    return {
        "benchmark_id": benchmark_definition.get("benchmark_id", benchmark_id),
        "benchmark_title": benchmark_definition.get("title", ""),
        "benchmark_description": benchmark_definition.get("description", ""),
        "expected_dimensions": expected_dimensions,
        "covered_dimensions": covered_dimensions,
        "missing_dimensions": [dim for dim in expected_dimensions if dim not in covered_dimensions],
        "required_keywords": required_keywords,
        "matched_keywords": matched_keywords,
        "missing_keywords": [kw for kw in required_keywords if kw not in matched_keywords],
        "dimension_coverage_score": round(dimension_score, 2),
        "keyword_coverage_score": round(keyword_score, 2),
        "all_expectations_satisfied": all_expectations_satisfied,
    }


def summarize_strategies(
    *,
    current_strategy: str,
    current_best_score: float,
    successful_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate comparison metrics by strategy, including the current run."""
    strategies: dict[str, dict[str, Any]] = {
        current_strategy: {
            "strategy": current_strategy,
            "role": "current",
            "runs_count": 1,
            "average_best_score": round(current_best_score, 2),
            "average_score_delta": 0.0,
            "average_dimension_overlap": 1.0,
            "average_citation_overlap": 1.0,
            "average_claim_overlap": 1.0,
        }
    }

    buckets: dict[str, list[dict[str, Any]]] = {}
    for run in successful_runs:
        strategy = str(run.get("strategy", "") or "unknown")
        buckets.setdefault(strategy, []).append(run)

    for strategy, runs in buckets.items():
        strategies[strategy] = {
            "strategy": strategy,
            "role": "reference",
            "runs_count": len(runs),
            "average_best_score": round(sum(float(run.get("best_score", 0.0)) for run in runs) / len(runs), 2),
            "average_score_delta": round(sum(float(run.get("score_delta", 0.0)) for run in runs) / len(runs), 2),
            "average_dimension_overlap": round(
                sum(float(run.get("dimension_overlap", 0.0)) for run in runs) / len(runs),
                2,
            ),
            "average_citation_overlap": round(
                sum(float(run.get("citation_overlap", 0.0)) for run in runs) / len(runs),
                2,
            ),
            "average_claim_overlap": round(
                sum(float(run.get("claim_overlap", 0.0)) for run in runs) / len(runs),
                2,
            ),
        }

    ordered = sorted(strategies.values(), key=lambda item: (item["role"] != "current", -item["average_best_score"]))
    best_reference = next((entry for entry in ordered if entry["role"] == "reference"), None)
    return {
        "current_strategy": current_strategy,
        "strategies": ordered,
        "best_reference_strategy": best_reference["strategy"] if best_reference else "",
    }


def reference_run_comparison(
    *,
    reference_runs: tuple[str, ...] | list[str],
    current_strategy: str,
    current_best_score: float,
    current_dimensions: list[str],
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare the current run to referenced prior outputs for consistency analysis."""
    if not reference_runs:
        return {
            "compared_runs_count": 0,
            "runs": [],
            "strategy_summary": summarize_strategies(
                current_strategy=current_strategy,
                current_best_score=current_best_score,
                successful_runs=[],
            ),
            "summary": {
                "average_dimension_overlap": 0.0,
                "average_citation_overlap": 0.0,
                "average_claim_overlap": 0.0,
                "average_score_delta": 0.0,
                "consistency_level": "not_available",
            },
        }

    current_dimensions_set = set(current_dimensions)
    current_citations = {citation.get("url", "") for citation in citations if citation.get("url")}
    current_claims = {
        normalize_claim_text(claim.get("text", ""))
        for claim in claims
        if claim.get("scope") == "synthesis" and claim.get("text")
    }

    runs: list[dict[str, Any]] = []
    for raw_path in reference_runs:
        ref_dir = Path(raw_path)
        metrics_path = ref_dir / "metrics.json"
        manifest_path = ref_dir / "run_manifest.json"
        claims_path = ref_dir / "claims.json"
        citations_path = ref_dir / "citations.json"
        if not metrics_path.exists():
            runs.append({"path": str(ref_dir), "status": "missing_metrics"})
            continue

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        ref_claim_records = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else []
        ref_citations_records = json.loads(citations_path.read_text(encoding="utf-8")) if citations_path.exists() else []

        ref_dimensions = set(metrics.get("explored_dimensions", []))
        ref_citations = {citation.get("url", "") for citation in ref_citations_records if citation.get("url")}
        ref_claims = {
            normalize_claim_text(claim.get("text", ""))
            for claim in ref_claim_records
            if claim.get("scope") == "synthesis" and claim.get("text")
        }

        dimension_union = current_dimensions_set | ref_dimensions
        citation_union = current_citations | ref_citations
        claim_union = current_claims | ref_claims

        dimension_overlap = len(current_dimensions_set & ref_dimensions) / len(dimension_union) if dimension_union else 1.0
        citation_overlap = len(current_citations & ref_citations) / len(citation_union) if citation_union else 1.0
        claim_overlap = len(current_claims & ref_claims) / len(claim_union) if claim_union else 1.0

        runs.append(
            {
                "path": str(ref_dir),
                "status": "ok",
                "strategy": manifest.get("strategy", {}).get("name", ""),
                "benchmark_id": metrics.get("benchmark_id") or manifest.get("evaluation", {}).get("benchmark_id", ""),
                "best_score": metrics.get("best_score", 0.0),
                "score_delta": round(current_best_score - float(metrics.get("best_score", 0.0)), 2),
                "dimension_overlap": round(dimension_overlap, 2),
                "citation_overlap": round(citation_overlap, 2),
                "claim_overlap": round(claim_overlap, 2),
                "shared_dimensions": sorted(current_dimensions_set & ref_dimensions),
            }
        )

    successful = [run for run in runs if run.get("status") == "ok"]
    if not successful:
        return {
            "compared_runs_count": 0,
            "runs": runs,
            "strategy_summary": summarize_strategies(
                current_strategy=current_strategy,
                current_best_score=current_best_score,
                successful_runs=[],
            ),
            "summary": {
                "average_dimension_overlap": 0.0,
                "average_citation_overlap": 0.0,
                "average_claim_overlap": 0.0,
                "average_score_delta": 0.0,
                "consistency_level": "not_available",
            },
        }

    avg_dimension = round(sum(run["dimension_overlap"] for run in successful) / len(successful), 2)
    avg_citation = round(sum(run["citation_overlap"] for run in successful) / len(successful), 2)
    avg_claim = round(sum(run["claim_overlap"] for run in successful) / len(successful), 2)
    avg_score_delta = round(sum(run["score_delta"] for run in successful) / len(successful), 2)
    consistency_signal = round((avg_dimension + avg_citation + avg_claim) / 3, 2)
    if consistency_signal >= 0.75:
        consistency_level = "high"
    elif consistency_signal >= 0.4:
        consistency_level = "medium"
    else:
        consistency_level = "low"

    return {
        "compared_runs_count": len(successful),
        "runs": runs,
        "strategy_summary": summarize_strategies(
            current_strategy=current_strategy,
            current_best_score=current_best_score,
            successful_runs=successful,
        ),
        "summary": {
            "average_dimension_overlap": avg_dimension,
            "average_citation_overlap": avg_citation,
            "average_claim_overlap": avg_claim,
            "average_score_delta": avg_score_delta,
            "consistency_level": consistency_level,
        },
    }
