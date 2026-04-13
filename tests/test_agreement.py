"""Tests for inter-rater agreement metrics."""

from src.research_loop import CandidateAssessment
from src.scorer import compute_inter_rater_agreement


def _assessment(iteration, dimension, backend, total, coverage=50.0, quality=50.0):
    return CandidateAssessment(
        iteration=iteration, dimension=dimension, backend_name=backend,
        coverage=coverage, quality=quality, total=total,
    )


def test_no_assessments_returns_empty():
    result = compute_inter_rater_agreement([])
    assert result["dimensions_with_multiple_candidates"] == 0
    assert result["cohens_kappa"] is None
    assert result["decision_agreement_rate"] is None
    assert result["per_dimension"] == []


def test_single_candidate_per_dimension_returns_empty():
    """Single-backend runs produce one candidate per dimension — no agreement."""
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),
        _assessment(2, "Perf", "claude", 70.0),
    ])
    assert result["dimensions_with_multiple_candidates"] == 0


def test_two_candidates_one_dimension_reports_scores_but_no_kappa():
    """With only 1 dimension having 2+ candidates, kappa is None (needs >= 2)."""
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),
        _assessment(1, "DX", "codex", 75.0),
    ])
    assert result["dimensions_with_multiple_candidates"] == 1
    assert result["cohens_kappa"] is None
    assert result["decision_agreement_rate"] == 1.0  # both above 30
    assert result["mean_score_delta"] == 5.0
    assert len(result["per_dimension"]) == 1
    assert result["per_dimension"][0]["decision_agreed"] is True


def test_perfect_agreement_kappa_one():
    """Both backends agree on keep/discard for every dimension → kappa = 1.0."""
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),
        _assessment(1, "DX", "codex", 70.0),
        _assessment(2, "Perf", "claude", 20.0),
        _assessment(2, "Perf", "codex", 15.0),
    ])
    assert result["dimensions_with_multiple_candidates"] == 2
    assert result["cohens_kappa"] == 1.0
    assert result["decision_agreement_rate"] == 1.0


def test_no_agreement_kappa_negative_or_zero():
    """Backends disagree on every dimension → kappa <= 0."""
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),    # keep
        _assessment(1, "DX", "codex", 20.0),      # discard
        _assessment(2, "Perf", "claude", 10.0),    # discard
        _assessment(2, "Perf", "codex", 90.0),     # keep
    ])
    assert result["dimensions_with_multiple_candidates"] == 2
    assert result["decision_agreement_rate"] == 0.0
    assert result["cohens_kappa"] is not None
    assert result["cohens_kappa"] <= 0.0


def test_partial_agreement():
    """Mixed agreement across dimensions."""
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),      # both keep
        _assessment(1, "DX", "codex", 70.0),
        _assessment(2, "Perf", "claude", 80.0),    # disagree
        _assessment(2, "Perf", "codex", 20.0),
        _assessment(3, "Cost", "claude", 50.0),    # both keep
        _assessment(3, "Cost", "codex", 40.0),
    ])
    assert result["dimensions_with_multiple_candidates"] == 3
    # 2 of 3 dimensions agree
    assert result["decision_agreement_rate"] == 0.67
    assert result["cohens_kappa"] is not None


def test_mean_score_delta():
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0),
        _assessment(1, "DX", "codex", 60.0),       # delta 20
        _assessment(2, "Perf", "claude", 50.0),
        _assessment(2, "Perf", "codex", 40.0),     # delta 10
    ])
    assert result["mean_score_delta"] == 15.0


def test_per_dimension_structure():
    result = compute_inter_rater_agreement([
        _assessment(1, "DX", "claude", 80.0, coverage=60.0, quality=90.0),
        _assessment(1, "DX", "codex", 70.0, coverage=50.0, quality=80.0),
    ])
    dim = result["per_dimension"][0]
    assert dim["dimension"] == "DX"
    assert len(dim["assessments"]) == 2
    assert dim["assessments"][0]["backend"] == "claude"
    assert dim["assessments"][0]["coverage"] == 60.0
    assert dim["assessments"][0]["quality"] == 90.0
    assert dim["assessments"][1]["backend"] == "codex"
