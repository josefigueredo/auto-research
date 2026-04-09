"""Tests for src.config — YAML loading and dataclass validation."""

import textwrap
from pathlib import Path

import pytest

from src.config import BackendsConfig, EvaluationConfig, ExecutionConfig, MethodologyConfig, ResearchConfig, ScoringConfig, StrategyConfig


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


class TestMethodologyConfig:
    def test_defaults(self):
        mc = MethodologyConfig()
        assert mc.question == ""
        assert mc.scope == ""
        assert mc.inclusion_criteria == ()
        assert mc.recency_days == 0


class TestEvaluationConfig:
    def test_defaults(self):
        ec = EvaluationConfig()
        assert ec.benchmark_id == ""
        assert ec.run_baselines is False


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

    def test_methodology_config(self, tmp_path: Path):
        p = tmp_path / "methodology.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              methodology:
                question: "What is the best option?"
                scope: "Architectural decision support"
                inclusion_criteria:
                  - official docs
                exclusion_criteria:
                  - anonymous forum posts
                preferred_source_types:
                  - vendor docs
                  - standards
                recency_days: 180
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.methodology.question == "What is the best option?"
        assert cfg.methodology.scope == "Architectural decision support"
        assert cfg.methodology.inclusion_criteria == ("official docs",)
        assert cfg.methodology.exclusion_criteria == ("anonymous forum posts",)
        assert cfg.methodology.preferred_source_types == ("vendor docs", "standards")
        assert cfg.methodology.recency_days == 180

    def test_evaluation_config(self, tmp_path: Path):
        p = tmp_path / "evaluation.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              evaluation:
                benchmark_id: "bench-001"
                run_baselines: true
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.evaluation.benchmark_id == "bench-001"
        assert cfg.evaluation.run_baselines is True

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
        with pytest.raises(ValueError, match="topic"):
            ResearchConfig.from_yaml(p)

    def test_empty_file_raises(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="YAML mapping"):
            ResearchConfig.from_yaml(p)

    def test_missing_research_key_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("other_key: value\n", encoding="utf-8")
        with pytest.raises(ValueError, match="research"):
            ResearchConfig.from_yaml(p)

    def test_invalid_backend_raises(self, tmp_path: Path):
        p = tmp_path / "bad_backend.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    backend: chatgpt\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid backend"):
            ResearchConfig.from_yaml(p)

    def test_valid_backends(self, tmp_path: Path):
        for backend in ("claude", "codex", "gemini", "copilot"):
            p = tmp_path / f"{backend}.yaml"
            p.write_text(f"research:\n  topic: test\n  execution:\n    backend: {backend}\n", encoding="utf-8")
            cfg = ResearchConfig.from_yaml(p)
            assert cfg.execution.backend == backend

    def test_negative_budget_raises(self, tmp_path: Path):
        p = tmp_path / "bad_budget.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    max_budget_per_call: -1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-negative"):
            ResearchConfig.from_yaml(p)

    def test_zero_timeout_raises(self, tmp_path: Path):
        p = tmp_path / "bad_timeout.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    timeout_seconds: 0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="positive"):
            ResearchConfig.from_yaml(p)

    def test_frozen(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        with pytest.raises(AttributeError):
            cfg.topic = "changed"


# ---------------------------------------------------------------------------
# Multi-backend config
# ---------------------------------------------------------------------------

class TestMultiBackendConfig:
    def test_defaults(self):
        bc = BackendsConfig()
        assert bc.primary == "claude"
        assert bc.research == ("claude",)
        assert bc.judge_or_primary == "claude"
        assert bc.utility_or_primary == "claude"

    def test_all_backend_names(self):
        bc = BackendsConfig(primary="claude", research=("codex", "gemini"), judge="claude", utility="gemini")
        names = bc.all_backend_names()
        assert names == {"claude", "codex", "gemini"}

    def test_strategy_config_defaults(self):
        sc = StrategyConfig()
        assert sc.merge_mode == "best"
        assert sc.merge_threshold == 40.0
        assert sc.critique_depth == "standard"
        assert sc.refiner_sees_draft is True
        assert sc.max_parallel == 3
        assert sc.stagger_seconds == 5

    def test_backward_compat_single_backend(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        assert cfg.execution.strategy == "single"
        assert cfg.execution.backends.primary == "claude"
        assert cfg.execution.backends.research == ("claude",)

    def test_ensemble_config(self, tmp_path: Path):
        p = tmp_path / "ensemble.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test ensemble"
              execution:
                backend: claude
                strategy: ensemble
                backends:
                  primary: claude
                  research:
                    - codex
                    - gemini
                  judge: claude
                  utility: gemini
                strategy_config:
                  merge_mode: union
                  stagger_seconds: 10
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.strategy == "ensemble"
        assert cfg.execution.backends.primary == "claude"
        assert cfg.execution.backends.research == ("codex", "gemini")
        assert cfg.execution.backends.judge == "claude"
        assert cfg.execution.backends.utility == "gemini"
        assert cfg.execution.strategy_config.merge_mode == "union"
        assert cfg.execution.strategy_config.stagger_seconds == 10

    def test_invalid_strategy_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: bogus
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid strategy"):
            ResearchConfig.from_yaml(p)

    def test_invalid_research_backend_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: ensemble
                backends:
                  primary: claude
                  research:
                    - chatgpt
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid research backend"):
            ResearchConfig.from_yaml(p)

    def test_research_as_string(self, tmp_path: Path):
        p = tmp_path / "str.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: single
                backends:
                  primary: claude
                  research: codex
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.backends.research == ("codex",)
