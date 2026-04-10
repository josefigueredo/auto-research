"""HTML reporting helpers for autoresearch run artifacts."""

from __future__ import annotations

from html import escape
from typing import Any


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
    methods_text: str,
    synthesis_text: str,
) -> str:
    """Render a lightweight standalone HTML report from run artifacts."""
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

    evaluation_html = ""
    if evaluation:
        evaluation_html = f"""
        <section>
          <h2>Evaluation</h2>
          <p><strong>Benchmark:</strong> {escape(str(evaluation.get("benchmark_id", "")))}</p>
          <p><strong>Rubric grade:</strong> {escape(str(evaluation.get("summary", {}).get("rubric_grade", "")))}</p>
          <pre>{escape(_pretty_json_like(evaluation))}</pre>
        </section>
        """

    comparison_html = ""
    if comparison and comparison.get("compared_runs_count", 0):
        comparison_html = f"""
        <section>
          <h2>Consistency Comparison</h2>
          <p><strong>Compared runs:</strong> {comparison.get("compared_runs_count", 0)}</p>
          <p><strong>Consistency level:</strong> {escape(str(comparison.get("summary", {}).get("consistency_level", "")))}</p>
          <pre>{escape(_pretty_json_like(comparison))}</pre>
        </section>
        """

    cards_html = "".join(
        f'<div class="card"><div class="label">{escape(str(label))}</div><div class="value">{escape(str(value))}</div></div>'
        for label, value in summary_cards.items()
    )

    explored_dimensions = metrics.get("explored_dimensions", [])
    dimensions_html = "".join(f"<li>{escape(str(dim))}</li>" for dim in explored_dimensions) or "<li>(none)</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 1100px; line-height: 1.5; color: #1f2937; }}
    h1, h2, h3 {{ color: #111827; }}
    .meta {{ color: #4b5563; margin-bottom: 1.5rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 1rem; background: #f9fafb; }}
    .label {{ font-size: 0.85rem; color: #6b7280; }}
    .value {{ font-size: 1.25rem; font-weight: 700; margin-top: 0.3rem; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f3f4f6; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb; }}
    ul {{ padding-left: 1.25rem; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <div class="meta">
      <div><strong>Topic:</strong> {escape(topic)}</div>
      <div><strong>Goal:</strong> {escape(goal)}</div>
      <div><strong>Strategy:</strong> {escape(str(strategy.get("name", "")))}</div>
      <div><strong>Status:</strong> {escape(str(run.get("status", "")))}</div>
      <div><strong>Started:</strong> {escape(str(run.get("started_at", "")))}</div>
      <div><strong>Completed:</strong> {escape(str(run.get("completed_at", "")))}</div>
    </div>
  </header>

  <section>
    <h2>Run Summary</h2>
    <div class="grid">{cards_html}</div>
  </section>

  <section>
    <h2>Dimensions Explored</h2>
    <ul>{dimensions_html}</ul>
  </section>

  <section>
    <h2>Methods</h2>
    <pre>{escape(methods_text)}</pre>
  </section>

  <section>
    <h2>Synthesis</h2>
    <pre>{escape(synthesis_text)}</pre>
  </section>

  <section>
    <h2>Evidence Quality</h2>
    <pre>{escape(_pretty_json_like(evidence_quality))}</pre>
  </section>

  <section>
    <h2>Rubric</h2>
    <pre>{escape(_pretty_json_like(rubric))}</pre>
  </section>

  {evaluation_html}
  {comparison_html}
</body>
</html>
"""


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
