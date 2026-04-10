"""Direct tests for goal-shape and lightweight execution helpers."""

from src.constraints import (
    coerce_to_bullets,
    format_results_table,
    goal_constraints_summary,
    goal_requires_bullets,
    goal_word_limit,
    is_lightweight_goal,
    is_lightweight_mode,
    postprocess_goal_output,
    synthesis_knowledge_context,
    synthesis_results_summary,
    trim_to_word_limit,
)


def test_is_lightweight_goal_and_mode():
    assert is_lightweight_goal("Provide a bullet-point list under 100 words")
    assert is_lightweight_mode(
        explicit_enabled=False,
        goal="Brief answer under 100 words",
        topic="Python",
        dimensions_count=4,
        max_iterations=5,
        allowed_tools="WebSearch",
    )
    assert is_lightweight_mode(
        explicit_enabled=False,
        goal="Normal goal",
        topic="Topic",
        dimensions_count=2,
        max_iterations=1,
        allowed_tools="",
    )


def test_goal_constraints_summary_surfaces_shape_and_limit():
    summary = goal_constraints_summary("A bullet-point list under 100 words", lightweight_mode=True)
    assert "bullet points" in summary
    assert "under 100 words" in summary
    assert "lightweight mode is active" in summary
    assert goal_word_limit("Under 75 words please") == 75
    assert goal_requires_bullets("Give me a bullet list")


def test_postprocess_goal_output_applies_bullets_and_word_limit():
    text = "Python is easy to learn. It has a large ecosystem. Packaging can be fragmented."
    processed = postprocess_goal_output(text, goal="Bullet-point list under 8 words")
    assert processed.startswith("- ")
    assert len(processed.split()) <= 8


def test_bullet_helpers_and_synthesis_views():
    assert coerce_to_bullets("* one\n* two") == "- one\n- two"
    assert trim_to_word_limit("- one two three\n- four five six", 4).startswith("- one")

    results = [
        {"iteration": "001", "dimension": "DX", "total_score": "80.0", "status": "keep"},
        {"iteration": "002", "dimension": "Tooling", "total_score": "75.0", "status": "discard"},
    ]
    assert "| Iter |" in format_results_table(results)
    assert "- Iter 001:" in synthesis_results_summary(results, lightweight_mode=True)

    kb = "word " * 900
    assert "[lightweight mode: truncated knowledge base]" in synthesis_knowledge_context(
        kb,
        lightweight_mode=True,
        lightweight_kb_words=50,
    )
