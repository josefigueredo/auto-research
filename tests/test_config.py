"""Tests for src.config — YAML loading and dataclass validation."""

import textwrap
from pathlib import Path

import pytest

from src.config import ExecutionConfig, ResearchConfig, ScoringConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "full.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Compare API gateways"
          goal: "Architect-level comparison"
          dimensions:
            - "REST vs HTTP"
            - "WebSocket"
            - "Auth options"
          scoring:
            min_dimensions_per_iteration: 2
            target_dimensions_total: 5
            evidence_types:
              - comparison_table
              - pricing_data
          execution:
            max_iterations: 10
            compress_every: 3
            allowed_tools: "WebSearch,Read"
            max_turns: 5
            timeout_seconds: 120
            model: opus
            max_budget_per_call: 1.25
    """), encoding="utf-8")
    return p


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "minimal.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Minimal topic"
    """), encoding="utf-8")
    return p


@pytest.fixture
def no_goal_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "no_goal.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Topic without goal"
          dimensions:
            - "Dim A"
    """), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# ScoringConfig defaults
# ---------------------------------------------------------------------------

class TestScoringConfig:
    def test_defaults(self):
        sc = ScoringConfig()
        assert sc.min_dimensions_per_iteration == 1
        assert sc.target_dimensions_total == 10
        assert len(sc.evidence_types) == 5
        assert "comparison_table" in sc.evidence_types

    def test_frozen(self):
        sc = ScoringConfig()
        with pytest.raises(AttributeError):
            sc.min_dimensions_per_iteration = 99


# ---------------------------------------------------------------------------
# ExecutionConfig defaults
# ---------------------------------------------------------------------------

class TestExecutionConfig:
    def test_defaults(self):
        ec = ExecutionConfig()
        assert ec.max_iterations == 0
        assert ec.compress_every == 5
        assert ec.model == "sonnet"
        assert ec.max_budget_per_call == 0.50
        assert ec.timeout_seconds == 600
        assert ec.max_turns == 10
        assert "WebSearch" in ec.allowed_tools

    def test_frozen(self):
        ec = ExecutionConfig()
        with pytest.raises(AttributeError):
            ec.model = "opus"


# ---------------------------------------------------------------------------
# ResearchConfig.from_yaml
# ---------------------------------------------------------------------------

class TestResearchConfigFromYaml:
    def test_full_config(self, full_yaml: Path):
        cfg = ResearchConfig.from_yaml(full_yaml)
        assert cfg.topic == "Compare API gateways"
        assert cfg.goal == "Architect-level comparison"
        assert cfg.dimensions == ("REST vs HTTP", "WebSocket", "Auth options")
        assert cfg.scoring.min_dimensions_per_iteration == 2
        assert cfg.scoring.target_dimensions_total == 5
        assert cfg.scoring.evidence_types == ("comparison_table", "pricing_data")
        assert cfg.execution.max_iterations == 10
        assert cfg.execution.compress_every == 3
        assert cfg.execution.allowed_tools == "WebSearch,Read"
        assert cfg.execution.max_turns == 5
        assert cfg.execution.timeout_seconds == 120
        assert cfg.execution.model == "opus"
        assert cfg.execution.max_budget_per_call == 1.25

    def test_minimal_config_uses_defaults(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        assert cfg.topic == "Minimal topic"
        assert cfg.goal == "Minimal topic"  # falls back to topic
        assert cfg.dimensions == ()
        assert cfg.scoring == ScoringConfig()
        assert cfg.execution.model == "sonnet"
        assert cfg.execution.max_iterations == 0

    def test_goal_falls_back_to_topic(self, no_goal_yaml: Path):
        cfg = ResearchConfig.from_yaml(no_goal_yaml)
        assert cfg.goal == "Topic without goal"
        assert cfg.dimensions == ("Dim A",)

    def test_missing_topic_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("research:\n  goal: 'no topic'\n", encoding="utf-8")
        with pytest.raises(KeyError):
            ResearchConfig.from_yaml(p)

    def test_frozen(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        with pytest.raises(AttributeError):
            cfg.topic = "changed"
