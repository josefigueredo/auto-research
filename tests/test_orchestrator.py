"""Tests for src.orchestrator — prompt rendering, AutoResearcher."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends import AgentResponse, Backend, CallOptions
from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.orchestrator import AutoResearcher
from src.prompts import render as _render
from src.scorer import IterationScore
from src.strategy import ResearchCandidate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeBackend(Backend):
    """In-memory backend for testing (no subprocess calls)."""

    name = "fake"

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
        return AgentResponse(text="fake response", cost_usd=0.01, is_error=False)


# Remove from registry to avoid polluting other tests
if "fake" in Backend.__dict__.get("_REGISTRY", {}):
    del Backend._REGISTRY["fake"]


@pytest.fixture
def research_config() -> ResearchConfig:
    return ResearchConfig(
        topic="Test topic",
        goal="Test goal",
        dimensions=("Dim A", "Dim B", "Dim C"),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            max_iterations=2,
            backend="claude",
            model="sonnet",
            timeout_seconds=10,
            max_budget_per_call=0.10,
        ),
    )


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def researcher(research_config, fake_backend, tmp_path) -> AutoResearcher:
    return AutoResearcher(
        config=research_config,
        backend=fake_backend,
        output_dir=tmp_path / "output",
    )


# ---------------------------------------------------------------------------
# _render
# ---------------------------------------------------------------------------

class TestRender:
    def test_renders_template(self, tmp_path, monkeypatch):
        import src.prompts as prompts_mod
        monkeypatch.setattr(prompts_mod, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.md").write_text("Hello {name}, topic: {topic}", encoding="utf-8")
        result = _render("test.md", name="Alice", topic="APIs")
        assert result == "Hello Alice, topic: APIs"

    def test_missing_template_raises(self, tmp_path, monkeypatch):
        import src.prompts as prompts_mod
        monkeypatch.setattr(prompts_mod, "PROMPTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            _render("nonexistent.md")


# ---------------------------------------------------------------------------
# AutoResearcher — setup and resume
# ---------------------------------------------------------------------------

class TestAutoResearcherSetup:
    def test_setup_creates_dirs(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        assert researcher.output_dir.exists()
        assert researcher.iterations_dir.exists()
        assert researcher.results_path.exists()
        assert researcher.manifest_path.exists()
        assert researcher.methods_path.exists()

    def test_setup_writes_tsv_header(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        content = researcher.results_path.read_text(encoding="utf-8")
        assert "iteration" in content
        assert "dimension" in content
        assert "total_score" in content

    def test_setup_writes_run_manifest(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        manifest = json.loads(researcher.manifest_path.read_text(encoding="utf-8"))
        assert manifest["run"]["status"] == "initialized"
        assert manifest["project"]["version"] == "0.2.0"
        assert manifest["environment"]["git_commit"] == "abc123"

    def test_setup_writes_methods_artifact(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        methods = researcher.methods_path.read_text(encoding="utf-8")
        assert "# Research Methods" in methods
        assert "Test goal" in methods

    def test_finalize_writes_html_report(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = (
            "Recommend Python for orchestration-heavy workloads. "
            "High confidence. https://docs.python.org/3/"
        )
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()
        html = researcher.report_html_path.read_text(encoding="utf-8")
        assert "Autoresearch Report" in html
        assert "Developer experience" in html
        assert "Recommend Python for orchestration-heavy workloads." in html
        assert "Rubric" in html
        assert "Semantic Calibration" in html
        assert "Dashboard Summary" in html

    def test_finalize_writes_pdf_report(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=type(researcher.config.reporting)(export_html=False, export_pdf=True, report_title="PDF Report"),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/"
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()
        pdf_bytes = researcher.report_pdf_path.read_bytes()
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"PDF Report" in pdf_bytes

    def test_finalize_writes_portfolio_artifacts(self, researcher, tmp_path):
        sibling = tmp_path / "prior-run"
        sibling.mkdir()
        (sibling / "dashboard.json").write_text(
            json.dumps(
                {
                    "topic": "Previous topic",
                    "benchmark_id": "bench-001",
                    "current_strategy": "single",
                    "best_score": 75.0,
                    "rubric_grade": "good",
                    "consistency_level": "medium",
                }
            ),
            encoding="utf-8",
        )
        researcher.output_dir = tmp_path / "current-run"
        researcher.iterations_dir = researcher.output_dir / "iterations"
        researcher.results_path = researcher.output_dir / "results.tsv"
        researcher.kb_path = researcher.output_dir / "knowledge_base.md"
        researcher.synthesis_path = researcher.output_dir / "synthesis.md"
        researcher.methods_path = researcher.output_dir / "methods.md"
        researcher.manifest_path = researcher.output_dir / "run_manifest.json"
        researcher.metrics_path = researcher.output_dir / "metrics.json"
        researcher.claims_path = researcher.output_dir / "claims.json"
        researcher.citations_path = researcher.output_dir / "citations.json"
        researcher.evidence_links_path = researcher.output_dir / "evidence_links.json"
        researcher.evidence_quality_path = researcher.output_dir / "evidence_quality.json"
        researcher.rubric_path = researcher.output_dir / "rubric.json"
        researcher.contradictions_path = researcher.output_dir / "contradictions.json"
        researcher.baseline_path = researcher.output_dir / "baseline.md"
        researcher.evaluation_path = researcher.output_dir / "evaluation.json"
        researcher.comparison_path = researcher.output_dir / "comparison.json"
        researcher.strategy_summary_path = researcher.output_dir / "strategy_summary.json"
        researcher.dashboard_path = researcher.output_dir / "dashboard.json"
        researcher.semantic_calibration_path = researcher.output_dir / "semantic_calibration.json"
        researcher.semantic_review_path = researcher.output_dir / "semantic_review.json"
        researcher.report_html_path = researcher.output_dir / "report.html"
        researcher.report_pdf_path = researcher.output_dir / "report.pdf"
        researcher.portfolio_path = researcher.output_dir.parent / "portfolio.json"
        researcher.portfolio_html_path = researcher.output_dir.parent / "portfolio.html"

        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/"
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()

        portfolio = json.loads(researcher.portfolio_path.read_text(encoding="utf-8"))
        portfolio_html = researcher.portfolio_html_path.read_text(encoding="utf-8")
        assert portfolio["runs_count"] == 2
        assert portfolio["best_run"]["name"] == "current-run"
        assert "current-run" in portfolio_html
        assert "prior-run" in portfolio_html

    def test_resume_empty_dir(self, researcher):
        researcher._setup()
        researcher._resume()
        assert researcher.iteration == 0
        assert researcher.best_score == 0.0

    def test_resume_rebuilds_state(self, researcher):
        researcher._setup()

        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        (researcher.iterations_dir / "iter_002.md").write_text("# Iter 2", encoding="utf-8")

        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "cumulative_cost_usd": "0.1"},
            {"iteration": "002", "timestamp": "T", "dimension": "Dim B",
             "coverage_score": "60.0", "quality_score": "50.0", "total_score": "54.0",
             "status": "discard", "hypothesis": "h", "cumulative_cost_usd": "0.2"},
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        researcher._resume()
        assert researcher.iteration == 2
        assert researcher.best_score == 74.0
        assert researcher.best_scores["Dim A"] == 74.0
        assert "Dim A" in researcher.explored_dimensions
        assert len(researcher.results) == 2

    def test_resume_restores_discovered_dimensions_from_results(self, researcher):
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "discovered_gaps": json.dumps(["Gap X"]),
             "cumulative_cost_usd": "0.1"}
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        researcher._resume()
        assert "Gap X" in researcher.discovered_dimensions

    def test_run_without_resume_does_not_restore_state(self, researcher):
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"):
            researcher.run()
        assert researcher.iteration == 0

    def test_run_with_resume_restores_state(self, research_config, fake_backend, tmp_path):
        researcher = AutoResearcher(
            config=research_config,
            backend=fake_backend,
            output_dir=tmp_path / "output",
            resume=True,
        )
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "cumulative_cost_usd": "0.1"}
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher.run()
        assert researcher.iteration == 1
        assert researcher.best_score == 74.0

    def test_should_stop_on_target_dimensions_total(self, researcher):
        researcher.explored_dimensions = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        assert researcher._should_stop() is True

    def test_run_stops_when_target_dimensions_total_reached(self, research_config, fake_backend, tmp_path):
        researcher = AutoResearcher(
            config=research_config,
            backend=fake_backend,
            output_dir=tmp_path / "output",
        )
        researcher.explored_dimensions = [f"Dim {i}" for i in range(10)]
        with patch.object(researcher, "_run_iteration") as mock_iter, \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher.run()
        mock_iter.assert_not_called()

    def test_run_writes_metrics_artifact(self, researcher):
        researcher.results = [{"iteration": "001", "dimension": "Dim A", "total_score": "80.0", "status": "keep"}]
        researcher.explored_dimensions = ["Dim A"]
        researcher.total_input_tokens = 10
        researcher.total_output_tokens = 5
        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher.run()
        metrics = json.loads(researcher.metrics_path.read_text(encoding="utf-8"))
        assert metrics["run_status"] == "interrupted"
        assert metrics["explored_dimensions"] == ["Dim A"]
        assert metrics["total_input_tokens"] == 10

    def test_finalize_writes_provenance_artifacts(self, researcher):
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        researcher._collect_provenance(
            "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/",
            scope="iteration-001",
            dimension="Developer experience",
        )
        researcher._finalize_run_artifacts()
        claims = json.loads(researcher.claims_path.read_text(encoding="utf-8"))
        citations = json.loads(researcher.citations_path.read_text(encoding="utf-8"))
        links = json.loads(researcher.evidence_links_path.read_text(encoding="utf-8"))
        evidence_quality = json.loads(researcher.evidence_quality_path.read_text(encoding="utf-8"))
        rubric = json.loads(researcher.rubric_path.read_text(encoding="utf-8"))
        contradictions = json.loads(researcher.contradictions_path.read_text(encoding="utf-8"))
        assert any(claim["claim_type"] == "recommendation" for claim in claims)
        assert any(citation["url"].startswith("https://docs.python.org") for citation in citations)
        assert len(links) == len(claims)
        assert "average_evidence_quality_score" in evidence_quality
        assert rubric["grade"] in {"strong", "good", "developing", "insufficient"}
        assert contradictions == []

    def test_generate_baseline_and_evaluation_artifacts(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-001",
                run_baselines=True,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Developer experience Iterative knowledge"
        with patch.object(researcher, "_call_with", return_value=AgentResponse(
            text="Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/",
            cost_usd=0.0,
            is_error=False,
        )):
            researcher._generate_synthesis()
            researcher._generate_baseline()
            researcher._finalize_run_artifacts()
        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark_id"] == "bench-001"
        assert evaluation["baseline_generated"] is True
        assert evaluation["rubric"]["grade"] in {"strong", "good", "developing", "insufficient"}
        assert evaluation["summary"]["rubric_grade"] == evaluation["rubric"]["grade"]
        assert evaluation["semantic_calibration"]["grade"] in {"well_calibrated", "reasonable", "tentative", "weak"}
        assert evaluation["summary"]["semantic_calibration_grade"] == evaluation["semantic_calibration"]["grade"]
        assert evaluation["benchmark"]["benchmark_title"] == "Python orchestration smoke benchmark"
        assert evaluation["benchmark"]["all_expectations_satisfied"] is True

    def test_generate_benchmark_evaluation_without_baseline(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-002",
                run_baselines=False,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Developer experience findings"
        researcher.synthesis_path.write_text(
            "Python remains suitable for orchestration-heavy workloads. https://docs.python.org/3/",
            encoding="utf-8",
        )

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark_id"] == "bench-002"
        assert evaluation["baseline_generated"] is False
        assert evaluation["benchmark"]["benchmark_title"] == "Python orchestration coverage benchmark"
        assert evaluation["benchmark"]["covered_dimensions"] == ["Developer experience"]
        assert evaluation["benchmark"]["matched_keywords"] == ["python", "workloads"]
        assert evaluation["summary"]["benchmark_expectations_satisfied"] is True

    def test_generate_benchmark_evaluation_for_vendor_comparison_catalog(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal="Compare and recommend the best option",
            dimensions=("Cost and pricing", "Operational complexity"),
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-003",
                run_baselines=False,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.explored_dimensions = ["Cost and pricing", "Operational complexity"]
        researcher.knowledge_base = "Cost and pricing plus operational complexity trade-off and recommendation."
        researcher.synthesis_path.write_text(
            "Compare the options and recommend one based on a clear trade-off analysis of cost and pricing and operational complexity.",
            encoding="utf-8",
        )

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark"]["benchmark_title"] == "Vendor comparison decision benchmark"
        assert evaluation["benchmark"]["covered_dimensions"] == ["Cost and pricing", "Operational complexity"]
        assert evaluation["benchmark"]["matched_keywords"] == ["recommendation", "trade-off", "compare"]

    def test_generate_reference_run_comparison_artifacts(self, researcher, tmp_path):
        reference_dir = tmp_path / "prior-run"
        reference_dir.mkdir()
        (reference_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "benchmark_id": "bench-001",
                    "best_score": 80.0,
                    "explored_dimensions": ["Developer experience", "Security"],
                }
            ),
            encoding="utf-8",
        )
        (reference_dir / "run_manifest.json").write_text(
            json.dumps({"strategy": {"name": "ensemble"}, "evaluation": {"benchmark_id": "bench-001"}}),
            encoding="utf-8",
        )
        (reference_dir / "claims.json").write_text(
            json.dumps(
                [
                    {
                        "id": "synthesis-claim-001",
                        "scope": "synthesis",
                        "text": "Recommend Python for orchestration-heavy workloads.",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (reference_dir / "citations.json").write_text(
            json.dumps(
                [
                    {
                        "id": "synthesis-cite-001",
                        "scope": "synthesis",
                        "url": "https://docs.python.org/3/",
                    }
                ]
            ),
            encoding="utf-8",
        )

        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                reference_runs=(str(reference_dir),),
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()

        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.best_score = 88.0
        synthesis_text = (
            "Recommend Python for orchestration-heavy workloads. "
            "High confidence. https://docs.python.org/3/"
        )
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        comparison = json.loads(researcher.comparison_path.read_text(encoding="utf-8"))
        strategy_summary = json.loads(researcher.strategy_summary_path.read_text(encoding="utf-8"))
        dashboard = json.loads(researcher.dashboard_path.read_text(encoding="utf-8"))
        semantic_calibration = json.loads(researcher.semantic_calibration_path.read_text(encoding="utf-8"))
        assert evaluation["summary"]["reference_runs_compared"] == 1
        assert comparison["compared_runs_count"] == 1
        assert comparison["runs"][0]["strategy"] == "ensemble"
        assert comparison["runs"][0]["score_delta"] == 8.0
        assert comparison["runs"][0]["shared_dimensions"] == ["Developer experience"]
        assert comparison["summary"]["consistency_level"] in {"medium", "high", "low"}
        assert comparison["strategy_summary"]["best_reference_strategy"] == "ensemble"
        assert strategy_summary["current_strategy"] == researcher.config.execution.strategy
        assert any(item["strategy"] == "ensemble" for item in strategy_summary["strategies"])
        assert dashboard["current_strategy"] == researcher.config.execution.strategy
        assert dashboard["reference_runs_compared"] == 1
        assert dashboard["strategy_summary"]["best_reference_strategy"] == "ensemble"
        assert semantic_calibration["enabled"] is True
        assert semantic_calibration["grade"] in {"well_calibrated", "reasonable", "tentative", "weak"}

    def test_finalize_writes_semantic_review_when_enabled(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(semantic_review=True),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch.object(AutoResearcher, "_git_commit", return_value="abc123"), \
             patch.object(AutoResearcher, "_cli_version", return_value="1.0"), \
             patch.object(AutoResearcher, "_package_version", return_value="0.2.0"):
            researcher._setup()

        synthesis_text = "Recommend Python. High confidence. https://docs.python.org/3/"
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")

        def fake_call(backend, prompt, **kwargs):
            if "semantic quality judge" in prompt.lower():
                return AgentResponse(
                    text=json.dumps(
                        {
                            "dimensions": {
                                "coherence": 0.8,
                                "support": 0.7,
                                "limitations": 0.6,
                                "contradiction_handling": 0.9,
                                "decision_readiness": 0.75,
                            },
                            "grade": "good",
                            "summary": "Decision-ready with minor gaps.",
                        }
                    ),
                    cost_usd=0.0,
                    is_error=False,
                )
            return AgentResponse(text="noop", cost_usd=0.0, is_error=False)

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            researcher._finalize_run_artifacts()

        semantic_review = json.loads(researcher.semantic_review_path.read_text(encoding="utf-8"))
        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert semantic_review["enabled"] is True
        assert semantic_review["grade"] == "good"
        assert semantic_review["judge_backend"] == researcher.strategy.get_judge_backend().name
        assert evaluation["semantic_review"]["grade"] == "good"
        assert evaluation["summary"]["semantic_review_grade"] == "good"


# ---------------------------------------------------------------------------
# AutoResearcher — dimension exhaustion
# ---------------------------------------------------------------------------

class TestDimensionExhaustion:
    def test_maybe_exhaust_below_threshold(self, researcher):
        researcher._dimension_attempts["Dim A"] = 1
        researcher._maybe_exhaust_dimension("Dim A")
        assert "Dim A" not in researcher.explored_dimensions

    def test_maybe_exhaust_at_threshold(self, researcher):
        researcher._dimension_attempts["Dim A"] = 3
        researcher._maybe_exhaust_dimension("Dim A")
        assert "Dim A" in researcher.explored_dimensions

    def test_already_explored_not_duplicated(self, researcher):
        researcher.explored_dimensions.append("Dim A")
        researcher._dimension_attempts["Dim A"] = 5
        researcher._maybe_exhaust_dimension("Dim A")
        assert researcher.explored_dimensions.count("Dim A") == 1


# ---------------------------------------------------------------------------
# AutoResearcher — helpers
# ---------------------------------------------------------------------------

class TestAutoResearcherHelpers:
    def test_kb_summary_empty(self, researcher):
        assert "No prior findings" in researcher._kb_summary()

    def test_kb_summary_short(self, researcher):
        researcher.knowledge_base = "Some findings about APIs."
        assert researcher._kb_summary() == "Some findings about APIs."

    def test_kb_summary_truncated(self, researcher):
        researcher.knowledge_base = "word " * 5000
        summary = researcher._kb_summary()
        # Sandwich pattern: keeps head + tail, truncates middle
        assert "truncated" in summary
        assert summary.startswith("word")
        assert summary.rstrip().endswith("word")
        assert len(summary.split()) < 5000

    def test_format_dimension_list_empty(self, researcher):
        assert researcher._format_dimension_list([]) == "(none)"

    def test_format_dimension_list(self, researcher):
        result = researcher._format_dimension_list(["A", "B"])
        assert result == "- A\n- B"

    def test_format_results_table_empty(self, researcher):
        assert researcher._format_results_table() == "(no results yet)"

    def test_format_results_table(self, researcher):
        researcher.results = [
            {"iteration": "001", "dimension": "Dim A", "total_score": "85.0", "status": "keep"},
        ]
        table = researcher._format_results_table()
        assert "Dim A" in table
        assert "85.0" in table
        assert "keep" in table

    def test_candidate_selection_prefers_scored_best_over_longest(self, researcher):
        candidates = [
            ResearchCandidate(findings="long but weak", backend_name="claude", cost_usd=0.1),
            ResearchCandidate(findings="short but strong", backend_name="codex", cost_usd=0.1),
        ]

        def fake_score(dimension, findings):
            if findings == "long but weak":
                return IterationScore(total=40.0)
            return IterationScore(total=85.0)

        with patch.object(researcher, "_score", side_effect=fake_score):
            selected = researcher._select_candidate_findings("Dim A", candidates)

        assert selected == "short but strong"

    def test_candidate_union_merges_only_above_threshold(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            scoring=researcher.config.scoring,
            execution=ExecutionConfig(
                **{
                    **researcher.config.execution.__dict__,
                    "strategy_config": researcher.config.execution.strategy_config.__class__(
                        **{
                            **researcher.config.execution.strategy_config.__dict__,
                            "merge_mode": "union",
                            "merge_threshold": 60.0,
                        }
                    ),
                }
            ),
        )
        candidates = [
            ResearchCandidate(findings="finding A", backend_name="claude", cost_usd=0.1),
            ResearchCandidate(findings="finding B", backend_name="codex", cost_usd=0.1),
        ]

        def fake_score(dimension, findings):
            return IterationScore(total=75.0 if findings == "finding A" else 50.0)

        with patch.object(researcher, "_score", side_effect=fake_score):
            selected = researcher._select_candidate_findings("Dim A", candidates)

        assert "finding A" in selected
        assert "finding B" not in selected

    def test_generate_hypothesis_includes_discovered_dimensions(self, researcher):
        researcher.discovered_dimensions.append("New Gap")
        researcher.explored_dimensions.append("Dim A")
        with patch("src.orchestrator._render") as mock_render, \
             patch.object(researcher, "_call_with", return_value=AgentResponse(
                 text=json.dumps({"dimension": "New Gap", "questions": [], "approach": ""}),
                 cost_usd=0.0,
                 is_error=False,
             )):
            researcher._generate_hypothesis()

        render_kwargs = mock_render.call_args.kwargs
        assert "New Gap" in render_kwargs["unexplored_dimensions"]

    def test_methodology_summary_formats_constraints(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=type(researcher.config.methodology)(
                question="Which option is best?",
                scope="Architect review",
                inclusion_criteria=("official docs",),
                exclusion_criteria=("forum posts",),
                preferred_source_types=("vendor docs",),
                recency_days=180,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        summary = researcher._methodology_summary()
        assert "Which option is best?" in summary
        assert "official docs" in summary
        assert "180 days" in summary

    def test_merge_findings_queues_discovered_gaps(self, researcher):
        score = IterationScore(gaps=["Gap One", "Gap Two"])
        researcher._setup()
        researcher._merge_findings("Dim A", "findings", score)
        assert "Gap One" in researcher.discovered_dimensions
        assert "Gap Two" in researcher.discovered_dimensions

    def test_execute_research_tracks_per_backend_usage_from_candidates(self, researcher):
        class FakeStrategy:
            def execute_research(self, *args, **kwargs):
                return type("X", (), {
                    "findings": "",
                    "backend_name": "multiple",
                    "cost_usd": 0.3,
                    "per_backend_costs": {"claude": 0.1, "codex": 0.2},
                    "candidates": [
                        ResearchCandidate(findings="candidate a", backend_name="claude", cost_usd=0.1, input_tokens=10, output_tokens=2),
                        ResearchCandidate(findings="candidate b", backend_name="codex", cost_usd=0.2, input_tokens=20, output_tokens=3),
                    ],
                })()

            def post_research(self, findings, invoke, *, timeout=600):
                return None

        researcher.strategy = FakeStrategy()
        with patch("src.orchestrator._render", return_value="prompt"), \
             patch.object(researcher, "_select_candidate_findings", return_value="candidate b"):
            findings = researcher._execute_research("Dim A", [], "")

        assert findings == "candidate b"
        assert researcher.total_cost == pytest.approx(0.3)
        assert researcher.total_input_tokens == 30
        assert researcher.total_output_tokens == 5
        assert researcher.per_backend_costs["claude"] == pytest.approx(0.1)
        assert researcher.per_backend_costs["codex"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# AutoResearcher — save and log
# ---------------------------------------------------------------------------

class TestAutoResearcherSaveLog:
    def test_save_iteration(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher.iteration = 1
        researcher._save_iteration("Dim A", "findings text", IterationScore(coverage=80.0, quality=70.0, total=74.0), True)
        path = researcher.iterations_dir / "iter_001.md"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Dim A" in content
        assert "keep" in content
        assert "findings text" in content

    def test_log_result_appends_tsv(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher.iteration = 1
        researcher._log_result("Dim A", IterationScore(total=74.0), "test hypothesis", status="keep")
        content = researcher.results_path.read_text(encoding="utf-8")
        assert "Dim A" in content
        assert "keep" in content

    def test_merge_findings(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher._merge_findings("Dim A", "New findings", IterationScore())
        assert "Dim A" in researcher.explored_dimensions
        assert "New findings" in researcher.knowledge_base
        assert researcher.kb_path.read_text(encoding="utf-8") == researcher.knowledge_base


# ---------------------------------------------------------------------------
# AutoResearcher — _call delegates to backend
# ---------------------------------------------------------------------------

class TestAutoResearcherCall:
    def test_call_delegates_to_backend(self, researcher):
        researcher.backend = MagicMock()
        researcher.backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        resp = researcher._call("prompt")
        researcher.backend.invoke.assert_called_once()
        assert resp.text == "ok"

    def test_call_passes_config_defaults(self, researcher):
        mock_backend = MagicMock()
        mock_backend.name = "claude"
        mock_backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher.backend = mock_backend
        researcher._call("prompt")
        opts = mock_backend.invoke.call_args[0][1]
        assert isinstance(opts, CallOptions)
        assert opts.model == "sonnet"
        assert opts.max_budget_usd == 0.10

    def test_call_allows_overrides(self, researcher):
        mock_backend = MagicMock()
        mock_backend.name = "claude"
        mock_backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher.backend = mock_backend
        researcher._call("prompt", model="opus", max_turns=3)
        opts = mock_backend.invoke.call_args[0][1]
        assert opts.model == "opus"
        assert opts.max_turns == 3
