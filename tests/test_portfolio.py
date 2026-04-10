"""Tests for src.portfolio — multi-run portfolio aggregation."""

import json

from src.portfolio import build_portfolio, render_portfolio_html


def test_build_portfolio_collects_dashboards(tmp_path):
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    (run_a / "dashboard.json").write_text(
        json.dumps(
            {
                "topic": "Topic A",
                "benchmark_id": "bench-001",
                "current_strategy": "single",
                "best_score": 72.5,
                "rubric_grade": "good",
                "consistency_level": "medium",
            }
        ),
        encoding="utf-8",
    )
    (run_b / "dashboard.json").write_text(
        json.dumps(
            {
                "topic": "Topic B",
                "benchmark_id": "bench-002",
                "current_strategy": "ensemble",
                "best_score": 88.1,
                "rubric_grade": "strong",
                "consistency_level": "high",
            }
        ),
        encoding="utf-8",
    )

    portfolio = build_portfolio(tmp_path)
    assert portfolio["runs_count"] == 2
    assert portfolio["best_run"]["name"] == "run-b"
    assert set(portfolio["strategies"]) == {"single", "ensemble"}
    assert set(portfolio["benchmarks"]) == {"bench-001", "bench-002"}


def test_render_portfolio_html_renders_table():
    html = render_portfolio_html(
        "Portfolio",
        {
            "runs_count": 1,
            "strategies": ["ensemble"],
            "benchmarks": ["bench-001"],
            "best_run": {"name": "run-b", "best_score": 88.1},
            "runs": [
                {
                    "name": "run-b",
                    "topic": "Topic B",
                    "benchmark_id": "bench-001",
                    "current_strategy": "ensemble",
                    "best_score": 88.1,
                    "rubric_grade": "strong",
                    "consistency_level": "high",
                }
            ],
        },
    )
    assert "Portfolio" in html
    assert "run-b" in html
    assert "Topic B" in html
    assert "ensemble" in html
