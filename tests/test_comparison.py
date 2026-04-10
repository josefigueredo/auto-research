"""Direct tests for benchmark and cross-run comparison helpers."""

from pathlib import Path

from src.comparison import (
    benchmark_summary,
    load_benchmark_definition,
    reference_run_comparison,
    summarize_strategies,
)


def test_load_benchmark_definition_from_custom_dir(tmp_path: Path):
    benchmarks_dir = tmp_path / "benchmarks"
    benchmarks_dir.mkdir()
    (benchmarks_dir / "bench-x.yaml").write_text(
        "benchmark_id: bench-x\ntitle: Demo\nexpected_dimensions:\n  - DX\nrequired_keywords:\n  - python\n",
        encoding="utf-8",
    )
    result = load_benchmark_definition("bench-x", benchmarks_dir=benchmarks_dir)
    assert result["benchmark_id"] == "bench-x"
    assert result["title"] == "Demo"


def test_benchmark_summary_prefers_config_expectations_over_catalog(tmp_path: Path):
    benchmarks_dir = tmp_path / "benchmarks"
    benchmarks_dir.mkdir()
    (benchmarks_dir / "bench-a.yaml").write_text(
        "benchmark_id: bench-a\nexpected_dimensions:\n  - Wrong\nrequired_keywords:\n  - wrong\n",
        encoding="utf-8",
    )
    summary = benchmark_summary(
        benchmark_id="bench-a",
        config_expected_dimensions=["Developer experience"],
        config_required_keywords=["python"],
        knowledge_text="Developer experience matters",
        synthesis_text="Python is great",
        benchmarks_dir=benchmarks_dir,
    )
    assert summary["covered_dimensions"] == ["Developer experience"]
    assert summary["matched_keywords"] == ["python"]


def test_summarize_strategies_and_reference_run_comparison(tmp_path: Path):
    ref_dir = tmp_path / "run1"
    ref_dir.mkdir()
    (ref_dir / "metrics.json").write_text(
        '{"best_score": 80.0, "explored_dimensions": ["DX"], "benchmark_id": "bench-1"}',
        encoding="utf-8",
    )
    (ref_dir / "run_manifest.json").write_text(
        '{"strategy": {"name": "ensemble"}, "evaluation": {"benchmark_id": "bench-1"}}',
        encoding="utf-8",
    )
    (ref_dir / "claims.json").write_text(
        '[{"scope":"synthesis","text":"Python is easy to learn."}]',
        encoding="utf-8",
    )
    (ref_dir / "citations.json").write_text(
        '[{"url":"https://docs.python.org"}]',
        encoding="utf-8",
    )

    comparison = reference_run_comparison(
        reference_runs=[str(ref_dir)],
        current_strategy="single",
        current_best_score=88.0,
        current_dimensions=["DX"],
        claims=[{"scope": "synthesis", "text": "Python is easy to learn."}],
        citations=[{"url": "https://docs.python.org"}],
    )
    assert comparison["compared_runs_count"] == 1
    assert comparison["summary"]["consistency_level"] == "high"
    assert comparison["strategy_summary"]["best_reference_strategy"] == "ensemble"

    summary = summarize_strategies(
        current_strategy="single",
        current_best_score=88.0,
        successful_runs=comparison["runs"],
    )
    assert summary["current_strategy"] == "single"
    assert any(item["strategy"] == "ensemble" for item in summary["strategies"])
