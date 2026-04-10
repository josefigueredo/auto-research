"""Direct tests for semantic evaluation helpers."""

from src.semantic_eval import (
    semantic_calibration,
    semantic_review_disabled,
    semantic_review_empty,
    semantic_review_fallback,
    semantic_review_from_payload,
    semantic_weight_profile,
)


def test_semantic_weight_profile_and_calibration():
    profile, weights = semantic_weight_profile(
        goal="Compare vendors and recommend one",
        methodology_question="Which is best?",
        methodology_scope="Architecture decision",
        benchmark_summary={"benchmark_id": "bench-1", "expected_dimensions": ["DX"]},
        reference_comparison={"compared_runs_count": 2},
    )
    assert "benchmark_weighted" in profile
    assert "consistency" in profile
    assert round(sum(weights.values()), 4) == 1.0

    calibrated = semantic_calibration(
        enabled=True,
        goal="Compare vendors and recommend one",
        methodology_question="Which is best?",
        methodology_scope="Architecture decision",
        rubric={"overall_score": 0.8, "dimensions": {"uncertainty_reporting": 0.6, "contradiction_handling": 1.0, "actionability": 0.9}},
        evidence_quality={"average_evidence_quality_score": 0.7},
        benchmark_summary={"benchmark_id": "bench-1", "dimension_coverage_score": 1.0, "keyword_coverage_score": 0.8},
        reference_comparison={"compared_runs_count": 1, "summary": {"average_dimension_overlap": 0.7, "average_citation_overlap": 0.6, "average_claim_overlap": 0.8}},
    )
    assert calibrated["enabled"] is True
    assert calibrated["grade"] in {"well_calibrated", "reasonable", "tentative", "weak"}
    assert calibrated["profile"]


def test_semantic_review_helpers():
    assert semantic_review_disabled()["grade"] == "disabled"
    assert semantic_review_empty(judge_backend="claude")["judge_backend"] == "claude"

    fallback = semantic_review_fallback(
        judge_backend="claude",
        rubric={"overall_score": 0.72, "grade": "good", "dimensions": {"actionability": 0.8, "uncertainty_reporting": 0.5, "contradiction_handling": 0.9}},
        evidence_quality={"average_evidence_quality_score": 0.66},
        raw_response="oops",
    )
    assert fallback["enabled"] is True
    assert fallback["grade"] == "good"

    reviewed = semantic_review_from_payload(
        {
            "dimensions": {
                "coherence": 0.8,
                "support": 0.7,
                "limitations": 0.6,
                "contradiction_handling": 0.9,
                "decision_readiness": 0.75,
            },
            "summary": "Looks solid",
        },
        judge_backend="claude",
        raw_response='{"ok":true}',
    )
    assert reviewed["overall_score"] == 0.75
    assert reviewed["grade"] in {"strong", "good"}
