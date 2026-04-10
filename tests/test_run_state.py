"""Direct tests for runtime state helpers."""

from pathlib import Path

from src.backends import AgentResponse
from src.run_state import (
    UsageTotals,
    maybe_exhaust_dimension,
    merge_findings,
    resume_state,
    track_candidate_usage,
    track_cost,
    track_usage,
)
from src.strategy import ResearchCandidate


def test_usage_tracking_and_candidate_tracking():
    usage = UsageTotals()
    track_cost(usage, 1.25, "claude")
    track_usage(
        usage,
        AgentResponse(text="ok", cost_usd=0.5, is_error=False, input_tokens=10, output_tokens=3),
        "claude",
    )
    track_candidate_usage(
        usage,
        ResearchCandidate(
            backend_name="gemini",
            findings="x",
            cost_usd=0.25,
            input_tokens=5,
            output_tokens=2,
        ),
    )
    assert usage.total_cost == 2.0
    assert usage.total_input_tokens == 15
    assert usage.per_backend_costs["claude"] == 1.75
    assert usage.per_backend_tokens["gemini"]["output"] == 2


def test_merge_findings_and_exhaust_dimension():
    merged = merge_findings(
        dimension="DX",
        findings="Good tooling",
        gaps=["Testing"],
        knowledge_base="",
        explored_dimensions=[],
        discovered_dimensions=[],
        configured_dimensions=["DX"],
    )
    assert "## DX" in merged["knowledge_base"]
    assert "DX" in merged["explored_dimensions"]
    assert "Testing" in merged["discovered_dimensions"]

    explored = []
    exhausted = maybe_exhaust_dimension(
        dimension="DX",
        dimension_attempts={"DX": 3},
        explored_dimensions=explored,
        max_attempts_per_dimension=3,
    )
    assert exhausted is True
    assert explored == ["DX"]


def test_resume_state_rebuilds_tracking(tmp_path: Path):
    iterations_dir = tmp_path / "iterations"
    iterations_dir.mkdir()
    (iterations_dir / "iter_001.md").write_text("dummy", encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    results_path.write_text(
        "iteration\ttimestamp\tdimension\tcoverage_score\tquality_score\ttotal_score\tstatus\thypothesis\tdiscovered_gaps\tcumulative_cost_usd\tcumulative_input_tokens\tcumulative_output_tokens\n"
        "001\t2026-01-01T00:00:00\tDX\t80.0\t80.0\t80.0\tkeep\thypo\t[\"Testing\"]\t0.100\t10\t2\n",
        encoding="utf-8",
    )
    kb_path = tmp_path / "knowledge_base.md"
    kb_path.write_text("KB", encoding="utf-8")

    state = resume_state(
        iterations_dir=iterations_dir,
        results_path=results_path,
        knowledge_base_path=kb_path,
        configured_dimensions=["DX"],
        max_attempts_per_dimension=3,
    )
    assert state["iteration"] == 1
    assert state["best_score"] == 80.0
    assert state["explored_dimensions"] == ["DX"]
    assert state["discovered_dimensions"] == ["Testing"]
    assert state["knowledge_base"] == "KB"
