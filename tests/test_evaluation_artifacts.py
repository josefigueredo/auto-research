"""Focused tests for evaluation artifact helpers."""

from pathlib import Path

import pytest

from src.backends import AgentResponse, Backend
from src.config import EvaluationConfig, ExecutionConfig, ResearchConfig, ScoringConfig
from src.orchestrator import AutoResearcher


class FakeBackend(Backend):
    name = "fake-eval"

    def cli_executable(self) -> str:
        return "fake-cli"

    def prompt_mode(self):
        from src.backends import PromptMode

        return PromptMode.STDIN

    def build_command(self, opts):
        return ["fake-cli", "-p", "-"]

    def parse_response(self, stdout):
        return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

    def check_available(self) -> bool:
        return True

    def invoke(self, prompt, opts, timeout=300):
        return AgentResponse(text="fake response", cost_usd=0.0, is_error=False)


@pytest.fixture
def researcher(tmp_path: Path) -> AutoResearcher:
    cfg = ResearchConfig(
        topic="Eval topic",
        goal="Eval goal",
        dimensions=("DX",),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(max_iterations=1, backend="claude", model="sonnet"),
    )
    return AutoResearcher(config=cfg, backend=FakeBackend(), output_dir=tmp_path / "output")


def test_semantic_calibration_can_be_disabled(researcher: AutoResearcher):
    researcher.config = ResearchConfig(
        topic=researcher.config.topic,
        goal=researcher.config.goal,
        dimensions=researcher.config.dimensions,
        methodology=researcher.config.methodology,
        evaluation=EvaluationConfig(semantic_calibration=False),
        reporting=researcher.config.reporting,
        scoring=researcher.config.scoring,
        execution=researcher.config.execution,
    )
    result = researcher._semantic_calibration(
        rubric={"overall_score": 0.8, "dimensions": {"uncertainty_reporting": 0.7, "contradiction_handling": 1.0}},
        evidence_quality={"average_evidence_quality_score": 0.75},
        benchmark_summary={"dimension_coverage_score": 1.0, "keyword_coverage_score": 1.0},
        reference_comparison={"compared_runs_count": 0},
    )
    assert result["enabled"] is False
    assert result["grade"] == "disabled"
    assert result["profile"] == "disabled"


def test_semantic_review_can_be_disabled(researcher: AutoResearcher):
    result = researcher._semantic_review(
        rubric={"overall_score": 0.8, "grade": "good", "dimensions": {}},
        evidence_quality={"average_evidence_quality_score": 0.75},
        benchmark_summary={},
        contradictions=[],
    )
    assert result["enabled"] is False
    assert result["grade"] == "disabled"


def test_strategy_summary_handles_current_and_reference_runs():
    from src.comparison import summarize_strategies

    summary = summarize_strategies(
        current_strategy="single",
        current_best_score=88.0,
        successful_runs=[
            {
                "strategy": "ensemble",
                "best_score": 80.0,
                "score_delta": 8.0,
                "dimension_overlap": 0.5,
                "citation_overlap": 0.4,
                "claim_overlap": 0.6,
            },
            {
                "strategy": "ensemble",
                "best_score": 82.0,
                "score_delta": 6.0,
                "dimension_overlap": 0.7,
                "citation_overlap": 0.5,
                "claim_overlap": 0.65,
            },
        ],
    )
    assert summary["current_strategy"] == "single"
    assert summary["best_reference_strategy"] == "ensemble"
    ensemble = next(item for item in summary["strategies"] if item["strategy"] == "ensemble")
    assert ensemble["runs_count"] == 2
    assert ensemble["average_best_score"] == 81.0


def test_semantic_weight_profile_adjusts_for_benchmarks_and_references():
    from src.semantic_eval import semantic_weight_profile

    profile, weights = semantic_weight_profile(
        goal="Compare and recommend the best option",
        methodology_question="",
        methodology_scope="",
        benchmark_summary={"expected_dimensions": ["DX"], "required_keywords": ["python"]},
        reference_comparison={"compared_runs_count": 2},
    )
    assert "benchmark_weighted" in profile
    assert "consistency" in profile
    assert "decision" in profile
    assert round(sum(weights.values()), 4) == 1.0
    assert weights["benchmark_score"] > 0.0


def test_dashboard_writer_includes_semantic_calibration(researcher: AutoResearcher):
    researcher.output_dir.mkdir(parents=True, exist_ok=True)
    researcher.rubric_path.write_text('{"grade":"good","overall_score":0.7}', encoding="utf-8")
    researcher.evidence_quality_path.write_text('{"average_evidence_quality_score":0.6}', encoding="utf-8")
    researcher.comparison_path.write_text(
        '{"compared_runs_count":1,"summary":{"consistency_level":"medium"}}',
        encoding="utf-8",
    )
    researcher.evaluation_path.write_text(
        '{"summary":{"benchmark_expectations_satisfied":true}}',
        encoding="utf-8",
    )
    researcher.strategy_summary_path.write_text(
        '{"current_strategy":"single","strategies":[]}',
        encoding="utf-8",
    )
    researcher.semantic_calibration_path.write_text(
        '{"enabled":true,"grade":"reasonable","calibrated_score":0.72}',
        encoding="utf-8",
    )
    researcher.semantic_review_path.write_text(
        '{"enabled":true,"grade":"good","overall_score":0.78,"judge_backend":"fake-eval"}',
        encoding="utf-8",
    )
    researcher.explored_dimensions = ["DX"]
    researcher.iteration = 1
    researcher.best_score = 88.0

    researcher._write_dashboard_artifact()
    dashboard = researcher.dashboard_path.read_text(encoding="utf-8")
    assert '"calibrated_score": 0.72' in dashboard
    assert '"overall_score": 0.78' in dashboard
    assert '"consistency_level": "medium"' in dashboard
