"""Tests for src.orchestrator — rate limiting, CLI interface, prompt rendering, AutoResearcher."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.orchestrator import (
    AutoResearcher,
    ClaudeResponse,
    _check_rate_limit,
    _extract_rate_limit_utilization,
    _render,
    call_claude,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def research_config() -> ResearchConfig:
    return ResearchConfig(
        topic="Test topic",
        goal="Test goal",
        dimensions=("Dim A", "Dim B", "Dim C"),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            max_iterations=2,
            model="sonnet",
            timeout_seconds=10,
            max_budget_per_call=0.10,
        ),
    )


@pytest.fixture
def researcher(research_config, tmp_path) -> AutoResearcher:
    return AutoResearcher(config=research_config, output_dir=tmp_path / "output")


def _make_cli_output(result_text="hello", cost=0.05, utilization=None):
    """Build a mock Claude CLI JSON array output."""
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "result", "subtype": "success", "result": result_text,
         "total_cost_usd": cost, "is_error": False},
    ]
    if utilization is not None:
        events.insert(1, {
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": utilization, "status": "allowed"},
        })
    return json.dumps(events)


# ---------------------------------------------------------------------------
# _check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def test_empty_string(self):
        assert _check_rate_limit("") == 0

    def test_no_rate_limit_event(self):
        data = json.dumps([{"type": "result", "result": "ok"}])
        assert _check_rate_limit(data) == 0

    def test_low_utilization(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.5},
        }])
        assert _check_rate_limit(data) == 0

    def test_warning_utilization(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.85},
        }])
        assert _check_rate_limit(data) == 30  # RATE_LIMIT_COOLDOWN_SECONDS

    def test_high_utilization(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.95},
        }])
        assert _check_rate_limit(data) == 120  # RATE_LIMIT_BACKOFF_SECONDS

    def test_invalid_json(self):
        assert _check_rate_limit("not json") == 0

    def test_dict_format(self):
        data = json.dumps({
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.92},
        })
        assert _check_rate_limit(data) == 120


# ---------------------------------------------------------------------------
# _extract_rate_limit_utilization
# ---------------------------------------------------------------------------

class TestExtractRateLimitUtilization:
    def test_empty(self):
        assert _extract_rate_limit_utilization("") == 0.0

    def test_extracts_value(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.73},
        }])
        assert _extract_rate_limit_utilization(data) == 0.73

    def test_no_event(self):
        data = json.dumps([{"type": "result"}])
        assert _extract_rate_limit_utilization(data) == 0.0

    def test_invalid_json(self):
        assert _extract_rate_limit_utilization("{bad") == 0.0


# ---------------------------------------------------------------------------
# ClaudeResponse
# ---------------------------------------------------------------------------

class TestClaudeResponse:
    def test_frozen(self):
        r = ClaudeResponse(text="hi", cost_usd=0.01, is_error=False)
        with pytest.raises(AttributeError):
            r.text = "changed"

    def test_fields(self):
        r = ClaudeResponse(text="result", cost_usd=1.5, is_error=True)
        assert r.text == "result"
        assert r.cost_usd == 1.5
        assert r.is_error is True


# ---------------------------------------------------------------------------
# call_claude (mocked subprocess)
# ---------------------------------------------------------------------------

class TestCallClaude:
    @patch("src.orchestrator.subprocess.run")
    def test_successful_array_response(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_make_cli_output("research findings", 0.12),
            stderr="",
        )
        resp = call_claude("test prompt", model="sonnet", timeout=10)
        assert resp.text == "research findings"
        assert resp.cost_usd == 0.12
        assert resp.is_error is False

    @patch("src.orchestrator.subprocess.run")
    def test_successful_dict_response(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "dict result", "cost_usd": 0.05, "is_error": False}),
            stderr="",
        )
        resp = call_claude("test", timeout=10)
        assert resp.text == "dict result"

    @patch("src.orchestrator.subprocess.run")
    def test_non_json_response(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="plain text response",
            stderr="",
        )
        resp = call_claude("test", timeout=10)
        assert resp.text == "plain text response"
        assert resp.is_error is False

    @patch("src.orchestrator.subprocess.run")
    def test_rc1_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="some error",
        )
        resp = call_claude("test", timeout=10)
        assert resp.is_error is True
        assert resp.text == ""

    @patch("src.orchestrator.subprocess.run")
    def test_timeout_error(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)
        resp = call_claude("test", timeout=10)
        assert resp.is_error is True

    @patch("src.orchestrator.subprocess.run")
    def test_builds_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_make_cli_output(),
            stderr="",
        )
        call_claude(
            "prompt text",
            model="opus",
            allowed_tools="WebSearch,Read",
            max_turns=5,
            max_budget_usd=0.75,
            timeout=30,
        )
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "-" in cmd  # stdin marker
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "opus"
        assert "--allowedTools" in cmd
        assert "--max-turns" in cmd
        assert "--max-budget-usd" in cmd

    @patch("src.orchestrator.subprocess.run")
    def test_prompt_sent_via_stdin(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_make_cli_output(),
            stderr="",
        )
        call_claude("my long prompt", timeout=10)
        assert mock_run.call_args[1]["input"] == "my long prompt"


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

        # Create fake iteration files
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        (researcher.iterations_dir / "iter_002.md").write_text("# Iter 2", encoding="utf-8")

        # Create fake results.tsv
        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "cost_usd": "0.1"},
            {"iteration": "002", "timestamp": "T", "dimension": "Dim B",
             "coverage_score": "60.0", "quality_score": "50.0", "total_score": "54.0",
             "status": "discard", "hypothesis": "h", "cost_usd": "0.2"},
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        researcher._resume()
        assert researcher.iteration == 2
        assert researcher.best_score == 74.0
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
# AutoResearcher — _call helper
# ---------------------------------------------------------------------------

class TestAutoResearcherCall:
    @patch("src.orchestrator.call_claude")
    def test_call_passes_defaults(self, mock_claude, researcher):
        mock_claude.return_value = ClaudeResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher._call("prompt")
        _, kwargs = mock_claude.call_args
        assert kwargs["model"] == "sonnet"
        assert kwargs["max_budget_usd"] == 0.10
        assert kwargs["timeout"] == 10

    @patch("src.orchestrator.call_claude")
    def test_call_allows_overrides(self, mock_claude, researcher):
        mock_claude.return_value = ClaudeResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher._call("prompt", model="opus", max_turns=3)
        _, kwargs = mock_claude.call_args
        assert kwargs["model"] == "opus"
        assert kwargs["max_turns"] == 3
