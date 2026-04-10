"""Tests for src.reporting — template-based HTML report rendering."""

from src.reporting import (
    _comparison_html,
    _dashboard_html,
    _dimensions_html,
    _evaluation_html,
    _pretty_json_like,
    _semantic_html,
    _semantic_review_html,
    _summary_cards_html,
    render_html_report,
)


def test_render_html_report_renders_core_sections_and_escapes():
    html = render_html_report(
        title="Report <Unsafe>",
        topic="Topic & Scope",
        goal="Goal > Outcome",
        manifest={
            "run": {"status": "completed", "started_at": "2026-04-10", "completed_at": "2026-04-10"},
            "strategy": {"name": "ensemble"},
        },
        metrics={
            "best_score": 91.2,
            "iterations": 3,
            "explored_dimensions_count": 2,
            "explored_dimensions": ["DX", "Security"],
            "total_cost_usd": 1.23,
        },
        evidence_quality={"average_evidence_quality_score": 0.82},
        rubric={"grade": "strong", "overall_score": 0.88},
        evaluation={"benchmark_id": "bench-001", "summary": {"rubric_grade": "strong"}},
        comparison={"compared_runs_count": 1, "summary": {"consistency_level": "high"}},
        semantic_calibration={"enabled": True, "grade": "reasonable", "calibrated_score": 0.81},
        semantic_review={"enabled": True, "grade": "good", "overall_score": 0.76, "judge_backend": "claude"},
        dashboard={"current_strategy": "ensemble"},
        methods_text="Method <1>",
        synthesis_text="Use <Python> & cite sources.",
    )

    assert "Report &lt;Unsafe&gt;" in html
    assert "Topic &amp; Scope" in html
    assert "Goal &gt; Outcome" in html
    assert "Run Summary" in html
    assert "Semantic Calibration" in html
    assert "Semantic Judge Review" in html
    assert "Dashboard Summary" in html
    assert "Consistency Comparison" in html
    assert "Method &lt;1&gt;" in html
    assert "Use &lt;Python&gt; &amp; cite sources." in html


def test_render_html_report_omits_optional_sections_when_empty():
    html = render_html_report(
        title="Plain",
        topic="Topic",
        goal="Goal",
        manifest={"run": {}, "strategy": {}},
        metrics={"explored_dimensions": []},
        evidence_quality={},
        rubric={},
        evaluation=None,
        comparison=None,
        semantic_calibration=None,
        semantic_review=None,
        dashboard=None,
        methods_text="Methods",
        synthesis_text="Synthesis",
    )

    assert "Semantic Calibration" not in html
    assert "Dashboard Summary" not in html
    assert "Semantic Judge Review" not in html
    assert "Consistency Comparison" not in html
    assert "Evaluation" not in html
    assert "<li>(none)</li>" in html


def test_helper_html_sections_behave_as_expected():
    assert "Compared runs:" in _comparison_html({"compared_runs_count": 2, "summary": {"consistency_level": "medium"}})
    assert _comparison_html({"compared_runs_count": 0}) == ""
    assert "Dashboard Summary" in _dashboard_html({"foo": "bar"})
    assert _dashboard_html(None) == ""
    assert "Benchmark:" in _evaluation_html({"benchmark_id": "bench-1", "summary": {"rubric_grade": "good"}})
    assert _evaluation_html(None) == ""
    assert "Calibrated score:" in _semantic_html({"enabled": True, "grade": "reasonable", "calibrated_score": 0.7})
    assert _semantic_html({"enabled": False}) == ""
    assert "Overall score:" in _semantic_review_html(
        {"enabled": True, "grade": "good", "overall_score": 0.74, "judge_backend": "claude"}
    )
    assert _semantic_review_html({"enabled": False}) == ""


def test_helper_formatters_cover_lists_cards_and_json_like():
    cards = _summary_cards_html({"A": 1, "B": 2})
    assert cards.count('class="card"') == 2
    assert "A" in cards and "2" in cards

    dims = _dimensions_html(["One", "Two"])
    assert "<li>One</li>" in dims
    assert "<li>Two</li>" in dims
    assert _dimensions_html([]) == "<li>(none)</li>"

    pretty = _pretty_json_like({"a": [1, {"b": "c"}]})
    assert "'a': [" in pretty
    assert "'b': 'c'" in pretty
