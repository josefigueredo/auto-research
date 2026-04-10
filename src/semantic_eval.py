"""Semantic evaluation helpers for final research artifacts."""

from __future__ import annotations

from typing import Any


def semantic_weight_profile(
    *,
    goal: str,
    methodology_question: str,
    methodology_scope: str,
    benchmark_summary: dict[str, Any],
    reference_comparison: dict[str, Any],
) -> tuple[str, dict[str, float]]:
    """Choose semantic calibration weights based on task shape and available signals."""
    methodology_text = f"{goal} {methodology_question} {methodology_scope}".lower()
    has_benchmark = bool(
        benchmark_summary.get("benchmark_id")
        or benchmark_summary.get("expected_dimensions")
        or benchmark_summary.get("required_keywords")
    )
    has_references = bool(reference_comparison.get("compared_runs_count", 0))
    comparison_oriented = any(
        term in methodology_text for term in ("compare", "comparison", "evaluate", "vendor", "benchmark")
    )
    decision_oriented = any(
        term in methodology_text for term in ("decision", "recommend", "adr", "adopt", "choose")
    )

    weights = {
        "rubric_score": 0.35,
        "evidence_score": 0.2,
        "benchmark_score": 0.15,
        "consistency_score": 0.1,
        "uncertainty_score": 0.05,
        "contradiction_score": 0.05,
        "actionability_score": 0.1,
    }
    profile = "balanced"

    if comparison_oriented or has_benchmark:
        weights.update(
            {
                "rubric_score": 0.3,
                "evidence_score": 0.2,
                "benchmark_score": 0.25,
                "consistency_score": 0.1 if has_references else 0.05,
                "uncertainty_score": 0.05,
                "contradiction_score": 0.05,
                "actionability_score": 0.05,
            }
        )
        profile = "benchmark_weighted"

    if has_references:
        weights["consistency_score"] += 0.05
        weights["rubric_score"] -= 0.03
        weights["actionability_score"] -= 0.02
        profile = "consistency_weighted" if profile == "balanced" else f"{profile}+consistency"

    if decision_oriented:
        weights["actionability_score"] += 0.05
        weights["rubric_score"] -= 0.03
        weights["benchmark_score"] -= 0.02
        profile = "decision_weighted" if profile == "balanced" else f"{profile}+decision"

    total = sum(weights.values())
    normalized = {key: round(value / total, 4) for key, value in weights.items()}
    return profile, normalized


def semantic_calibration(
    *,
    enabled: bool,
    goal: str,
    methodology_question: str,
    methodology_scope: str,
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
    benchmark_summary: dict[str, Any],
    reference_comparison: dict[str, Any],
) -> dict[str, Any]:
    """Combine rubric, benchmark, evidence, and consistency into a calibrated quality score."""
    if not enabled:
        return {
            "enabled": False,
            "calibrated_score": 0.0,
            "grade": "disabled",
            "profile": "disabled",
            "weights": {},
            "components": {},
        }

    rubric_score = float(rubric.get("overall_score", 0.0))
    evidence_score = float(evidence_quality.get("average_evidence_quality_score", 0.0))
    benchmark_score = round(
        (
            float(benchmark_summary.get("dimension_coverage_score", 1.0))
            + float(benchmark_summary.get("keyword_coverage_score", 1.0))
        )
        / 2,
        2,
    )
    reference_summary = reference_comparison.get("summary", {})
    consistency_score = (
        round(
            (
                float(reference_summary.get("average_dimension_overlap", 0.0))
                + float(reference_summary.get("average_citation_overlap", 0.0))
                + float(reference_summary.get("average_claim_overlap", 0.0))
            )
            / 3,
            2,
        )
        if reference_comparison.get("compared_runs_count", 0)
        else 0.5
    )
    uncertainty_score = float(rubric.get("dimensions", {}).get("uncertainty_reporting", 0.0))
    contradiction_score = float(rubric.get("dimensions", {}).get("contradiction_handling", 1.0))
    actionability_score = float(rubric.get("dimensions", {}).get("actionability", 0.0))
    profile, weights = semantic_weight_profile(
        goal=goal,
        methodology_question=methodology_question,
        methodology_scope=methodology_scope,
        benchmark_summary=benchmark_summary,
        reference_comparison=reference_comparison,
    )

    calibrated_score = round(
        rubric_score * weights["rubric_score"]
        + evidence_score * weights["evidence_score"]
        + benchmark_score * weights["benchmark_score"]
        + consistency_score * weights["consistency_score"]
        + uncertainty_score * weights["uncertainty_score"]
        + contradiction_score * weights["contradiction_score"]
        + actionability_score * weights["actionability_score"],
        2,
    )

    if calibrated_score >= 0.85:
        grade = "well_calibrated"
    elif calibrated_score >= 0.65:
        grade = "reasonable"
    elif calibrated_score >= 0.45:
        grade = "tentative"
    else:
        grade = "weak"

    return {
        "enabled": True,
        "calibrated_score": calibrated_score,
        "grade": grade,
        "profile": profile,
        "weights": weights,
        "components": {
            "rubric_score": rubric_score,
            "evidence_score": evidence_score,
            "benchmark_score": benchmark_score,
            "consistency_score": consistency_score,
            "uncertainty_score": uncertainty_score,
            "contradiction_score": contradiction_score,
            "actionability_score": actionability_score,
        },
    }


def semantic_review_disabled() -> dict[str, Any]:
    """Return the disabled semantic-review payload."""
    return {
        "enabled": False,
        "overall_score": 0.0,
        "grade": "disabled",
        "judge_backend": "",
        "dimensions": {},
        "summary": "",
    }


def semantic_review_empty(*, judge_backend: str) -> dict[str, Any]:
    """Return a semantic-review payload for empty synthesis."""
    return {
        "enabled": True,
        "overall_score": 0.0,
        "grade": "weak",
        "judge_backend": judge_backend,
        "dimensions": {
            "coherence": 0.0,
            "support": 0.0,
            "limitations": 0.0,
            "contradiction_handling": 0.0,
            "decision_readiness": 0.0,
        },
        "summary": "No synthesis was available for semantic review.",
        "raw_response": "",
    }


def semantic_review_fallback(
    *,
    judge_backend: str,
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
    raw_response: str,
) -> dict[str, Any]:
    """Build a fallback semantic review derived from rubric and evidence quality."""
    return {
        "enabled": True,
        "judge_backend": judge_backend,
        "overall_score": float(rubric.get("overall_score", 0.0)),
        "grade": rubric.get("grade", "developing"),
        "dimensions": {
            "coherence": float(rubric.get("dimensions", {}).get("actionability", 0.0)),
            "support": float(evidence_quality.get("average_evidence_quality_score", 0.0)),
            "limitations": float(rubric.get("dimensions", {}).get("uncertainty_reporting", 0.0)),
            "contradiction_handling": float(rubric.get("dimensions", {}).get("contradiction_handling", 0.0)),
            "decision_readiness": float(rubric.get("dimensions", {}).get("actionability", 0.0)),
        },
        "summary": "Fallback semantic review derived from rubric and evidence quality.",
        "raw_response": raw_response,
    }


def semantic_review_from_payload(
    payload: dict[str, Any],
    *,
    judge_backend: str,
    raw_response: str,
) -> dict[str, Any]:
    """Normalize a parsed semantic-review payload."""
    dimensions = payload.get("dimensions", {})
    dimension_scores = [
        float(dimensions.get(key, 0.0))
        for key in ("coherence", "support", "limitations", "contradiction_handling", "decision_readiness")
    ]
    overall_score = round(sum(dimension_scores) / len(dimension_scores), 2) if dimension_scores else 0.0
    grade = payload.get("grade") or (
        "strong"
        if overall_score >= 0.8
        else "good"
        if overall_score >= 0.6
        else "developing"
        if overall_score >= 0.4
        else "weak"
    )
    return {
        "enabled": True,
        "judge_backend": judge_backend,
        "overall_score": overall_score,
        "grade": grade,
        "dimensions": {
            "coherence": float(dimensions.get("coherence", 0.0)),
            "support": float(dimensions.get("support", 0.0)),
            "limitations": float(dimensions.get("limitations", 0.0)),
            "contradiction_handling": float(dimensions.get("contradiction_handling", 0.0)),
            "decision_readiness": float(dimensions.get("decision_readiness", 0.0)),
        },
        "summary": payload.get("summary", ""),
        "raw_response": raw_response,
    }
