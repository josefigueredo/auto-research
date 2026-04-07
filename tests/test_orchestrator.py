"""Tests for src.orchestrator — prompt rendering, AutoResearcher."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backend import AgentResponse, Backend, CallOptions
from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.orchestrator import AutoResearcher, _render


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeBackend(Backend):
    """In-memory backend for testing (no subprocess calls)."""

    name = "fake"

    def cli_executable(self) -> str:
        return "fake-cli"

    def prompt_mode(self):
        from src.backend import PromptMode
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
        import src.orchestrator as orch
        monkeypatch.setattr(orch, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.md").write_text("Hello {name}, topic: {topic}", encoding="utf-8")
        result = _render("test.md", name="Alice", topic="APIs")
        assert result == "Hello Alice, topic: APIs"

    def test_missing_template_raises(self, tmp_path, monkeypatch):
        import src.orchestrator as orch
        monkeypatch.setattr(orch, "PROMPTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            _render("nonexistent.md")


# ---------------------------------------------------------------------------
# AutoResearcher — setup and resume
# ---------------------------------------------------------------------------

class TestAutoResearcherSetup:
    def test_setup_creates_dirs(self, researcher):
        researcher._setup()
        assert researcher.output_dir.exists()
        assert researcher.iterations_dir.exists()
        assert researcher.results_path.exists()

    def test_setup_writes_tsv_header(self, researcher):
        researcher._setup()
        content = researcher.results_path.read_text(encoding="utf-8")
        assert "iteration" in content
        assert "dimension" in content
        assert "total_score" in content

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
        assert summary.endswith("[... truncated for brevity]")
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
        researcher.backend = MagicMock()
        researcher.backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher._call("prompt")
        opts = researcher.backend.invoke.call_args[0][1]
        assert isinstance(opts, CallOptions)
        assert opts.model == "sonnet"
        assert opts.max_budget_usd == 0.10

    def test_call_allows_overrides(self, researcher):
        researcher.backend = MagicMock()
        researcher.backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher._call("prompt", model="opus", max_turns=3)
        opts = researcher.backend.invoke.call_args[0][1]
        assert opts.model == "opus"
        assert opts.max_turns == 3
