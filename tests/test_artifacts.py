"""Direct tests for artifact payload helpers."""

from pathlib import Path

from src.artifacts import (
    dashboard_payload,
    evaluation_payload,
    load_json_if_exists,
    metrics_payload,
    pdf_run_summary_text,
    should_write_evaluation,
)
from src.config import EvaluationConfig, ExecutionConfig, ResearchConfig, ScoringConfig


def test_load_json_if_exists(tmp_path: Path):
    path = tmp_path / "payload.json"
    assert load_json_if_exists(path, {"ok": False}) == {"ok": False}
    path.write_text('{"ok": true}', encoding="utf-8")
    assert load_json_if_exists(path, {}) == {"ok": True}


def test_metrics_evaluation_and_dashboard_payloads():
    metrics = metrics_payload(
        benchmark_id="bench-1",
        run_status="completed",
        iteration=2,
        best_score=88.0,
        explored_dimensions=["DX"],
        discovered_dimensions=["Tooling"],
        total_cost=1.25,
        total_input_tokens=100,
        total_output_tokens=20,
        per_backend_costs={"claude": 1.25},
        per_backend_tokens={"claude": {"input": 100, "output": 20}},
        results=[{"iteration": "001"}],
    )
    assert metrics["explored_dimensions_count"] == 1

    evaluation = evaluation_payload(
        benchmark_id="bench-1",
        baseline_exists=True,
        claims=[{"scope": "synthesis"}, {"scope": "baseline"}],
        citations=[{"scope": "synthesis"}, {"scope": "baseline"}],
        evidence_quality={"average_evidence_quality_score": 0.7},
        rubric={"grade": "good"},
        benchmark_summary={"all_expectations_satisfied": True},
        reference_comparison={"compared_runs_count": 1},
        semantic_review={"grade": "good"},
        semantic_calibration={"grade": "reasonable"},
    )
    assert evaluation["baseline_generated"] is True
    assert evaluation["summary"]["reference_runs_compared"] == 1

    dashboard = dashboard_payload(
        topic="Topic",
        goal="Goal",
        benchmark_id="bench-1",
        current_strategy="single",
        best_score=88.0,
        iteration=2,
        explored_dimensions=["DX"],
        rubric={"grade": "good", "overall_score": 0.8},
        evidence_quality={"average_evidence_quality_score": 0.7},
        comparison={"compared_runs_count": 1, "summary": {"consistency_level": "medium"}},
        evaluation={"summary": {"benchmark_expectations_satisfied": True}},
        strategy_summary={"current_strategy": "single"},
        semantic_calibration={"grade": "reasonable"},
        semantic_review={"grade": "good"},
    )
    assert dashboard["consistency_level"] == "medium"
    assert dashboard["rubric_grade"] == "good"


def test_pdf_summary_and_should_write_evaluation():
    text = pdf_run_summary_text(
        topic="Python",
        goal="Compare options",
        strategy="single",
        best_score=88.0,
        iteration=2,
        explored_dimensions=["DX"],
        metrics={"iterations": 2},
        rubric={"grade": "good"},
        evidence_quality={"average_evidence_quality_score": 0.7},
    )
    assert "Topic: Python" in text
    assert "Rubric grade: good" in text

    cfg = ResearchConfig(
        topic="x",
        goal="y",
        dimensions=("a",),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )
    assert should_write_evaluation(cfg) is False
    cfg = ResearchConfig(
        topic="x",
        goal="y",
        dimensions=("a",),
        evaluation=EvaluationConfig(run_baselines=True),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )
    assert should_write_evaluation(cfg) is True
