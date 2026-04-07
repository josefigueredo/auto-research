"""Tests for src.strategy — multi-backend research strategies."""

from unittest.mock import MagicMock

import pytest

from src.backends import AgentResponse
from src.config import BackendsConfig, StrategyConfig
from src.strategy import (
    AdversarialStrategy,
    CritiqueResult,
    EnsembleStrategy,
    ParallelStrategy,
    ResearchResult,
    SerialStrategy,
    SingleStrategy,
    SpecialistStrategy,
    get_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(name: str) -> MagicMock:
    b = MagicMock()
    b.name = name
    return b


def _make_invoke(text: str = "findings", cost: float = 0.1):
    """Return a mock invoke callback that returns a fixed response."""
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        return AgentResponse(text=text, cost_usd=cost, is_error=False)
    return invoke


def _make_invoke_per_backend(responses: dict[str, str]):
    """Return an invoke callback that returns different text per backend name."""
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        text = responses.get(backend.name, "")
        return AgentResponse(text=text, cost_usd=0.1, is_error=False)
    return invoke


def _make_invoke_error():
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        return AgentResponse(text="", cost_usd=0.0, is_error=True)
    return invoke


def _strategy(
    cls,
    primary="claude",
    research=("claude",),
    judge="",
    utility="",
    **strategy_kwargs,
):
    backends_config = BackendsConfig(
        primary=primary, research=tuple(research), judge=judge, utility=utility,
    )
    strategy_config = StrategyConfig(**strategy_kwargs)
    backend_names = backends_config.all_backend_names()
    backends = {name: _make_backend(name) for name in backend_names}
    return cls(backends_config, strategy_config, backends)


# ---------------------------------------------------------------------------
# get_strategy factory
# ---------------------------------------------------------------------------

class TestGetStrategy:
    def test_valid_strategies(self):
        for name in ("single", "ensemble", "adversarial", "parallel", "serial", "specialist"):
            bc = BackendsConfig()
            sc = StrategyConfig()
            backends = {"claude": _make_backend("claude")}
            s = get_strategy(name, bc, sc, backends)
            assert s.name == name

    def test_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("bogus", BackendsConfig(), StrategyConfig(), {})


# ---------------------------------------------------------------------------
# SingleStrategy
# ---------------------------------------------------------------------------

class TestSingleStrategy:
    def test_execute_success(self):
        s = _strategy(SingleStrategy)
        result = s.execute_research("prompt", _make_invoke("hello"))
        assert result.findings == "hello"
        assert result.backend_name == "claude"
        assert result.cost_usd == 0.1

    def test_execute_error(self):
        s = _strategy(SingleStrategy)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""

    def test_describe(self):
        s = _strategy(SingleStrategy)
        assert "single" in s.describe()
        assert "claude" in s.describe()

    def test_hypothesis_backend(self):
        s = _strategy(SingleStrategy)
        assert s.get_hypothesis_backend().name == "claude"

    def test_judge_backend_fallback(self):
        s = _strategy(SingleStrategy)
        assert s.get_judge_backend().name == "claude"

    def test_no_post_research(self):
        s = _strategy(SingleStrategy)
        assert s.post_research("findings", _make_invoke()) is None


# ---------------------------------------------------------------------------
# EnsembleStrategy
# ---------------------------------------------------------------------------

class TestEnsembleStrategy:
    def test_parallel_execution(self):
        s = _strategy(EnsembleStrategy, research=("claude", "codex"), stagger_seconds=0)
        invoke = _make_invoke_per_backend({"claude": "short", "codex": "much longer findings"})
        result = s.execute_research("prompt", invoke)
        # Should pick the longest
        assert result.findings == "much longer findings"
        assert result.backend_name == "codex"

    def test_all_fail(self):
        s = _strategy(EnsembleStrategy, research=("claude", "codex"), stagger_seconds=0)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""
        assert result.backend_name == "none"

    def test_union_merge(self):
        s = _strategy(EnsembleStrategy, research=("claude", "codex"), merge_mode="union", stagger_seconds=0)
        invoke = _make_invoke_per_backend({"claude": "finding A", "codex": "finding B"})
        result = s.execute_research("prompt", invoke)
        assert "finding A" in result.findings
        assert "finding B" in result.findings
        assert result.backend_name == "merged"

    def test_judge_isolation(self):
        s = _strategy(EnsembleStrategy, research=("codex", "gemini"), judge="claude")
        assert s.get_judge_backend().name == "claude"
        assert "claude" not in [b.name for b in s.research_backends]

    def test_describe(self):
        s = _strategy(EnsembleStrategy, research=("claude", "codex"), judge="gemini")
        desc = s.describe()
        assert "ensemble" in desc
        assert "claude" in desc
        assert "codex" in desc


# ---------------------------------------------------------------------------
# AdversarialStrategy
# ---------------------------------------------------------------------------

class TestAdversarialStrategy:
    def test_execute_uses_first_research_backend(self):
        s = _strategy(AdversarialStrategy, research=("codex", "claude"))
        result = s.execute_research("prompt", _make_invoke("research output"))
        assert result.findings == "research output"
        assert result.backend_name == "codex"

    def test_post_research_critique(self):
        s = _strategy(AdversarialStrategy, research=("codex", "claude"))
        critique = s.post_research("findings text", _make_invoke("errors found"))
        assert critique is not None
        assert critique.critique == "errors found"
        assert critique.backend_name == "claude"

    def test_post_research_empty_findings(self):
        s = _strategy(AdversarialStrategy, research=("codex", "claude"))
        assert s.post_research("", _make_invoke()) is None

    def test_describe(self):
        s = _strategy(AdversarialStrategy, research=("codex", "claude"))
        desc = s.describe()
        assert "adversarial" in desc


# ---------------------------------------------------------------------------
# ParallelStrategy
# ---------------------------------------------------------------------------

class TestParallelStrategy:
    def test_picks_longest(self):
        s = _strategy(ParallelStrategy, research=("claude", "codex", "gemini"), stagger_seconds=0)
        invoke = _make_invoke_per_backend({
            "claude": "a",
            "codex": "bb",
            "gemini": "ccc",
        })
        result = s.execute_research("prompt", invoke)
        assert result.findings == "ccc"
        assert result.backend_name == "gemini"

    def test_all_fail(self):
        s = _strategy(ParallelStrategy, research=("claude", "codex"), stagger_seconds=0)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""


# ---------------------------------------------------------------------------
# SerialStrategy
# ---------------------------------------------------------------------------

class TestSerialStrategy:
    def test_draft_then_refine(self):
        s = _strategy(SerialStrategy, research=("gemini", "claude"), stagger_seconds=0)
        call_count = [0]
        def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentResponse(text="draft", cost_usd=0.05, is_error=False)
            return AgentResponse(text="refined", cost_usd=0.15, is_error=False)

        result = s.execute_research("prompt", invoke)
        assert result.findings == "refined"
        assert "gemini" in result.backend_name
        assert "claude" in result.backend_name
        assert result.cost_usd == pytest.approx(0.20)

    def test_draft_fails_returns_empty(self):
        s = _strategy(SerialStrategy, research=("gemini", "claude"))
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""

    def test_refine_fails_returns_draft(self):
        s = _strategy(SerialStrategy, research=("gemini", "claude"))
        call_count = [0]
        def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentResponse(text="draft", cost_usd=0.05, is_error=False)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        result = s.execute_research("prompt", invoke)
        assert result.findings == "draft"

    def test_single_backend_fallback(self):
        s = _strategy(SerialStrategy, research=("claude",))
        result = s.execute_research("prompt", _make_invoke("solo"))
        assert result.findings == "solo"


# ---------------------------------------------------------------------------
# SpecialistStrategy
# ---------------------------------------------------------------------------

class TestSpecialistStrategy:
    def test_routing_code_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude", "codex", "gemini"))
        backend = s.route_dimension("SDK implementation and code examples")
        assert backend.name == "codex"

    def test_routing_pricing_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude", "codex", "gemini"))
        backend = s.route_dimension("pricing comparison and market overview")
        assert backend.name == "gemini"

    def test_routing_architecture_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude", "codex", "gemini"))
        backend = s.route_dimension("architecture trade-off analysis")
        assert backend.name == "claude"

    def test_routing_fallback(self):
        s = _strategy(SpecialistStrategy, research=("claude", "codex"))
        backend = s.route_dimension("random unrelated topic")
        assert backend.name == "claude"  # falls back to primary

    def test_execute_with_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude", "codex"))
        result = s.execute_research(
            "prompt", _make_invoke("coded"),
            dimension="code implementation",
        )
        assert result.findings == "coded"


# ---------------------------------------------------------------------------
# Backend role helpers
# ---------------------------------------------------------------------------

class TestBackendRoles:
    def test_utility_fallback_to_primary(self):
        s = _strategy(SingleStrategy, primary="claude", utility="")
        assert s.get_compress_backend().name == "claude"

    def test_utility_explicit(self):
        s = _strategy(SingleStrategy, primary="claude", utility="gemini")
        assert s.get_compress_backend().name == "gemini"

    def test_judge_fallback_to_primary(self):
        s = _strategy(SingleStrategy, primary="claude", judge="")
        assert s.get_judge_backend().name == "claude"

    def test_judge_explicit(self):
        s = _strategy(EnsembleStrategy, primary="claude", research=("codex",), judge="gemini")
        assert s.get_judge_backend().name == "gemini"

    def test_synthesize_uses_primary(self):
        s = _strategy(SingleStrategy, primary="codex")
        assert s.get_synthesize_backend().name == "codex"
