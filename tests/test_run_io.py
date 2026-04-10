"""Direct tests for runtime file I/O helpers."""

from pathlib import Path

from src.run_io import (
    append_result_row,
    build_result_row,
    setup_output_dir,
    write_iteration_markdown,
    write_results_header,
)
from src.scorer import IterationScore


def test_setup_and_results_header(tmp_path: Path):
    output_dir = tmp_path / "out"
    iterations_dir = output_dir / "iterations"
    results_path = output_dir / "results.tsv"
    setup_output_dir(output_dir, iterations_dir)
    write_results_header(results_path)
    assert output_dir.exists()
    assert iterations_dir.exists()
    header = results_path.read_text(encoding="utf-8")
    assert "iteration\ttimestamp\tdimension" in header


def test_build_append_row_and_iteration_markdown(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    write_results_header(results_path)
    score = IterationScore(coverage=80.0, quality=75.0, total=77.0, gaps=["Testing"])
    row = build_result_row(
        iteration=1,
        dimension="DX",
        score=score,
        hypothesis="A" * 150,
        status="keep",
        total_cost_usd=0.25,
        total_input_tokens=10,
        total_output_tokens=3,
    )
    append_result_row(results_path, row)
    text = results_path.read_text(encoding="utf-8")
    assert "001" in text
    assert "DX" in text
    assert row["hypothesis"] == "A" * 120

    path = write_iteration_markdown(
        iterations_dir=tmp_path,
        iteration=1,
        dimension="DX",
        findings="Research findings",
        score=score,
        kept=True,
    )
    content = path.read_text(encoding="utf-8")
    assert "# Iteration 001 — DX" in content
    assert "Research findings" in content
