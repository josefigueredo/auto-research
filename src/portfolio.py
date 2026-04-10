"""Aggregate multiple run dashboards into a portfolio view."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from typing import Any


_PORTFOLIO_TEMPLATE_PATH = Path(__file__).with_name("templates") / "portfolio.html.tmpl"


@dataclass(frozen=True)
class PortfolioRun:
    name: str
    path: str
    topic: str
    benchmark_id: str
    current_strategy: str
    best_score: float
    rubric_grade: str
    consistency_level: str


def build_portfolio(output_root: Path) -> dict[str, Any]:
    """Build a portfolio summary from sibling run directories."""
    runs: list[PortfolioRun] = []
    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        dashboard_path = child / "dashboard.json"
        if not dashboard_path.exists():
            continue
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        runs.append(
            PortfolioRun(
                name=child.name,
                path=str(child),
                topic=str(dashboard.get("topic", "")),
                benchmark_id=str(dashboard.get("benchmark_id", "")),
                current_strategy=str(dashboard.get("current_strategy", "")),
                best_score=float(dashboard.get("best_score", 0.0)),
                rubric_grade=str(dashboard.get("rubric_grade", "insufficient")),
                consistency_level=str(dashboard.get("consistency_level", "not_available")),
            )
        )

    strategies = sorted({run.current_strategy for run in runs if run.current_strategy})
    benchmarks = sorted({run.benchmark_id for run in runs if run.benchmark_id})
    best_run = max(runs, key=lambda run: run.best_score) if runs else None
    return {
        "runs_count": len(runs),
        "strategies": strategies,
        "benchmarks": benchmarks,
        "best_run": best_run.__dict__ if best_run else {},
        "runs": [run.__dict__ for run in runs],
    }


def render_portfolio_html(title: str, portfolio: dict[str, Any]) -> str:
    """Render a standalone HTML portfolio page."""
    template = Template(_PORTFOLIO_TEMPLATE_PATH.read_text(encoding="utf-8"))
    runs_html = "".join(
        (
            "<tr>"
            f"<td>{escape(str(run['name']))}</td>"
            f"<td>{escape(str(run['topic']))}</td>"
            f"<td>{escape(str(run['benchmark_id']))}</td>"
            f"<td>{escape(str(run['current_strategy']))}</td>"
            f"<td>{escape(str(run['best_score']))}</td>"
            f"<td>{escape(str(run['rubric_grade']))}</td>"
            f"<td>{escape(str(run['consistency_level']))}</td>"
            "</tr>"
        )
        for run in portfolio.get("runs", [])
    )
    if not runs_html:
        runs_html = '<tr><td colspan="7">(no runs)</td></tr>'

    best_run = portfolio.get("best_run", {})
    return template.safe_substitute(
        title=escape(title),
        runs_count=escape(str(portfolio.get("runs_count", 0))),
        strategies=escape(", ".join(portfolio.get("strategies", [])) or "(none)"),
        benchmarks=escape(", ".join(portfolio.get("benchmarks", [])) or "(none)"),
        best_run_name=escape(str(best_run.get("name", "(none)"))),
        best_run_score=escape(str(best_run.get("best_score", ""))),
        runs_table_html=runs_html,
    )
