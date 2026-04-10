"""HTML reporting helpers for autoresearch run artifacts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from typing import Any


_TEMPLATES_DIR = Path(__file__).with_name("templates")
_TEMPLATE_PATH = _TEMPLATES_DIR / "report.html.tmpl"
_MAIN_CSS_PATH = _TEMPLATES_DIR / "report.css"
_PRINT_CSS_PATH = _TEMPLATES_DIR / "report_print.css"
_PARTIALS_DIR = _TEMPLATES_DIR / "partials"
_HEADER_TEMPLATE_PATH = _PARTIALS_DIR / "report_header.tmpl"
_JSON_SECTION_TEMPLATE_PATH = _PARTIALS_DIR / "json_section.tmpl"


def render_html_report(
    *,
    title: str,
    topic: str,
    goal: str,
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    evidence_quality: dict[str, Any],
    rubric: dict[str, Any],
    evaluation: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    semantic_calibration: dict[str, Any] | None,
    semantic_review: dict[str, Any] | None,
    dashboard: dict[str, Any] | None,
    methods_text: str,
    synthesis_text: str,
) -> str:
    """Render a standalone HTML report from a filesystem template."""
    run = manifest.get("run", {})
    strategy = manifest.get("strategy", {})
    summary_cards = {
        "Best score": metrics.get("best_score", 0.0),
        "Iterations": metrics.get("iterations", 0),
        "Rubric grade": rubric.get("grade", "insufficient"),
        "Evidence quality": evidence_quality.get("average_evidence_quality_score", 0.0),
        "Explored dimensions": metrics.get("explored_dimensions_count", len(metrics.get("explored_dimensions", []))),
        "Total cost (USD)": metrics.get("total_cost_usd", 0.0),
    }

    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    header_template = Template(_HEADER_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(
        title=escape(title),
        main_css=_MAIN_CSS_PATH.read_text(encoding="utf-8").strip(),
        print_css=_PRINT_CSS_PATH.read_text(encoding="utf-8").strip(),
        header_html=header_template.safe_substitute(
            title=escape(title),
            topic=escape(topic),
            goal=escape(goal),
            strategy_name=escape(str(strategy.get("name", ""))),
            run_status=escape(str(run.get("status", ""))),
            started_at=escape(str(run.get("started_at", ""))),
            completed_at=escape(str(run.get("completed_at", ""))),
        ),
        topic=escape(topic),
        goal=escape(goal),
        strategy_name=escape(str(strategy.get("name", ""))),
        run_status=escape(str(run.get("status", ""))),
        started_at=escape(str(run.get("started_at", ""))),
        completed_at=escape(str(run.get("completed_at", ""))),
        summary_cards_html=_summary_cards_html(summary_cards),
        dimensions_html=_dimensions_html(metrics.get("explored_dimensions", [])),
        methods_text=escape(methods_text),
        synthesis_text=escape(synthesis_text),
        evidence_quality_text=escape(_pretty_json_like(evidence_quality)),
        rubric_text=escape(_pretty_json_like(rubric)),
        semantic_html=_semantic_html(semantic_calibration),
        semantic_review_html=_semantic_review_html(semantic_review),
        dashboard_html=_dashboard_html(dashboard),
        evaluation_html=_evaluation_html(evaluation),
        comparison_html=_comparison_html(comparison),
    )


def _summary_cards_html(summary_cards: dict[str, Any]) -> str:
    return "".join(
        f'<div class="card"><div class="label">{escape(str(label))}</div><div class="value">{escape(str(value))}</div></div>'
        for label, value in summary_cards.items()
    )


def _dimensions_html(dimensions: list[Any]) -> str:
    return "".join(f"<li>{escape(str(dim))}</li>" for dim in dimensions) or "<li>(none)</li>"


def _evaluation_html(evaluation: dict[str, Any] | None) -> str:
    if not evaluation:
        return ""
    return _json_section_html(
        "Evaluation",
        evaluation,
        [
            ("Benchmark", evaluation.get("benchmark_id", "")),
            ("Rubric grade", evaluation.get("summary", {}).get("rubric_grade", "")),
        ],
    )


def _comparison_html(comparison: dict[str, Any] | None) -> str:
    if not comparison or not comparison.get("compared_runs_count", 0):
        return ""
    return _json_section_html(
        "Consistency Comparison",
        comparison,
        [
            ("Compared runs", comparison.get("compared_runs_count", 0)),
            ("Consistency level", comparison.get("summary", {}).get("consistency_level", "")),
        ],
    )


def _dashboard_html(dashboard: dict[str, Any] | None) -> str:
    if not dashboard:
        return ""
    return _json_section_html("Dashboard Summary", dashboard)


def _semantic_html(semantic_calibration: dict[str, Any] | None) -> str:
    if not semantic_calibration or not semantic_calibration.get("enabled", False):
        return ""
    return _json_section_html(
        "Semantic Calibration",
        semantic_calibration,
        [
            ("Grade", semantic_calibration.get("grade", "")),
            ("Calibrated score", semantic_calibration.get("calibrated_score", "")),
        ],
    )


def _semantic_review_html(semantic_review: dict[str, Any] | None) -> str:
    if not semantic_review or not semantic_review.get("enabled", False):
        return ""
    return _json_section_html(
        "Semantic Judge Review",
        semantic_review,
        [
            ("Grade", semantic_review.get("grade", "")),
            ("Overall score", semantic_review.get("overall_score", "")),
            ("Judge backend", semantic_review.get("judge_backend", "")),
        ],
    )


def _json_section_html(
    heading: str,
    payload: dict[str, Any],
    meta_rows: list[tuple[str, Any]] | None = None,
) -> str:
    """Render a consistent JSON-like section via the shared partial template."""
    template = Template(_JSON_SECTION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    meta_html = "".join(
        f'<p><strong>{escape(str(label))}:</strong> {escape(str(value))}</p>'
        for label, value in (meta_rows or [])
        if value not in ("", None)
    )
    return template.safe_substitute(
        heading=escape(heading),
        meta_html=meta_html,
        body_text=escape(_pretty_json_like(payload)),
    )


def _pretty_json_like(value: Any, indent: int = 2) -> str:
    """Format nested dict/list structures without importing json again."""
    if isinstance(value, dict):
        lines = ["{"]
        for idx, (key, item) in enumerate(value.items()):
            suffix = "," if idx < len(value) - 1 else ""
            lines.append(" " * indent + f"{key!r}: " + _pretty_json_like(item, indent + 2) + suffix)
        lines.append(" " * (indent - 2) + "}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = ["["]
        for idx, item in enumerate(value):
            suffix = "," if idx < len(value) - 1 else ""
            lines.append(" " * indent + _pretty_json_like(item, indent + 2) + suffix)
        lines.append(" " * (indent - 2) + "]")
        return "\n".join(lines)
    return repr(value)
