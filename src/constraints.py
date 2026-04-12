"""Goal-shape and lightweight execution helpers.

These helpers keep delivery constraints separate from the orchestration loop so
short-form enforcement and lightweight-mode behavior can evolve independently.
"""

from __future__ import annotations

import re
from typing import Any


LIGHTWEIGHT_GOAL_PHRASES = (
    "under 100 words",
    "under 150 words",
    "under 200 words",
    "bullet-point list",
    "bullet point list",
    "brief answer",
    "short answer",
)


def is_lightweight_goal(goal: str) -> bool:
    """Return True when the goal clearly asks for a short-form deliverable."""
    lowered = goal.lower()
    return any(phrase in lowered for phrase in LIGHTWEIGHT_GOAL_PHRASES)


def is_lightweight_mode(
    *,
    explicit_enabled: bool,
    goal: str,
    topic: str,
) -> bool:
    """Return True when the run should optimize for brevity and low overhead.

    Lightweight mode activates in two cases:
    1. The config explicitly sets ``lightweight_mode: true``.
    2. The goal text contains a user-facing brevity phrase (e.g.
       "under 100 words", "bullet-point list").

    Run size (iteration count, dimension count, tool availability) does NOT
    auto-activate lightweight mode — a 1-iteration run with a long-form goal
    should produce long-form output.
    """
    if explicit_enabled:
        return True

    goal_text = f"{goal} {topic}".lower()
    return is_lightweight_goal(goal_text)


def goal_constraints_summary(goal: str, *, lightweight_mode: bool) -> str:
    """Extract explicit deliverable constraints from the goal text."""
    goal = goal.strip()
    if not goal:
        return "- Deliverable shape: not explicitly constrained."

    lines: list[str] = [f"- Deliverable goal: {goal}"]
    lowered = goal.lower()
    if "bullet" in lowered:
        lines.append("- Format: use bullet points instead of a long narrative report.")
    if "table" in lowered:
        lines.append("- Format: include a compact table if it helps satisfy the goal.")
    word_match = re.search(r"under\s+(\d+)\s+words?", lowered)
    if word_match:
        lines.append(f"- Hard limit: keep the final answer under {word_match.group(1)} words.")
    if any(term in lowered for term in ("brief", "short", "concise")):
        lines.append("- Style: be concise and avoid extra sections.")
    if lightweight_mode:
        lines.append("- Mode: lightweight mode is active; prefer the shortest output that still satisfies the goal.")
    return "\n".join(lines)


def goal_word_limit(goal: str) -> int | None:
    """Return an explicit 'under N words' constraint when present."""
    match = re.search(r"under\s+(\d+)\s+words?", goal.lower())
    return int(match.group(1)) if match else None


def goal_requires_bullets(goal: str) -> bool:
    """Return True when the goal explicitly asks for bullets/list output."""
    lowered = goal.lower()
    return "bullet-point" in lowered or "bullet point" in lowered or "bullet" in lowered or "list" in lowered


def postprocess_goal_output(text: str, *, goal: str) -> str:
    """Deterministically repair short-form outputs to obey explicit goal constraints."""
    text = text.strip()
    if not text:
        return text

    if goal_requires_bullets(goal):
        text = coerce_to_bullets(text)

    word_limit = goal_word_limit(goal)
    if word_limit:
        text = trim_to_word_limit(text, word_limit)

    return text.strip()


def trim_to_word_limit(text: str, word_limit: int) -> str:
    """Trim text while preserving basic bullet structure."""
    words = text.split()
    if len(words) <= word_limit:
        return text

    trimmed = " ".join(words[:word_limit]).rstrip(" ,;:-")
    bullet_lines = [line for line in trimmed.splitlines() if line.strip()]
    if bullet_lines and all(line.lstrip().startswith("-") for line in bullet_lines):
        return "\n".join(line.rstrip() for line in bullet_lines)
    return trimmed


def coerce_to_bullets(text: str) -> str:
    """Convert paragraphs/sentences into compact bullet lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullets = [line for line in lines if line.startswith(("- ", "* "))]
    if bullets:
        return "\n".join("- " + line[2:].strip() if line.startswith("* ") else line for line in bullets)

    cleaned = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE).strip()
    sentence_parts = re.split(r"(?<=[.!?])\s+", cleaned)
    compact = [part.strip(" -") for part in sentence_parts if part.strip()]
    if not compact:
        compact = [cleaned]
    compact = compact[:6]
    return "\n".join(f"- {part}" for part in compact if part)


def synthesis_knowledge_context(
    knowledge_base: str,
    *,
    lightweight_mode: bool,
    lightweight_kb_words: int,
) -> str:
    """Return the knowledge context to send to synthesis."""
    if not lightweight_mode:
        return knowledge_base

    words = knowledge_base.split()
    if len(words) <= lightweight_kb_words:
        return knowledge_base
    return " ".join(words[:lightweight_kb_words]) + "\n\n[lightweight mode: truncated knowledge base]"


def synthesis_results_summary(results: list[dict[str, Any]], *, lightweight_mode: bool) -> str:
    """Return a run summary tailored for synthesis prompting."""
    if not results:
        return "(no results yet)"
    if not lightweight_mode:
        return format_results_table(results)

    recent = results[-3:]
    return "\n".join(
        f"- Iter {row.get('iteration', '?')}: {row.get('dimension', '?')} — score {row.get('total_score', '?')} ({row.get('status', '?')})"
        for row in recent
    )


def format_results_table(results: list[dict[str, Any]]) -> str:
    """Format the results log as a markdown table for synthesis prompts."""
    if not results:
        return "(no results yet)"
    lines = ["| Iter | Dimension | Score | Status |", "|------|-----------|-------|--------|"]
    for row in results:
        lines.append(
            f"| {row.get('iteration', '?')} "
            f"| {row.get('dimension', '?')[:40]} "
            f"| {row.get('total_score', '?')} "
            f"| {row.get('status', '?')} |"
        )
    return "\n".join(lines)
