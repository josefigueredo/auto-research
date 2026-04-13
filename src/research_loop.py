"""Core research iteration loop.

Extracted from orchestrator.py to isolate the hypothesis -> research ->
score -> keep/discard cycle.  All backend invocation goes through
callbacks on the LoopContext so this module has no direct backend
dependency.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .backends import AgentResponse
from .config import ResearchConfig
from .prompts import render as _render
from .run_io import append_result_row, build_result_row, write_iteration_markdown
from .run_state import maybe_exhaust_dimension, merge_findings
from .scorer import (
    IterationScore,
    combine_scores,
    heuristic_score,
    parse_judge_response,
    quality_score_from_judge,
)
from .strategy import ResearchCandidate

log = logging.getLogger(__name__)

_MAX_FINDINGS_CHARS = 60_000


@dataclass
class LoopContext:
    """Immutable bundle of callbacks and config for the research loop.

    Created once per run by the orchestrator, threading through the backend
    invocation and state-tracking functions the loop needs without importing
    orchestrator internals.
    """

    config: ResearchConfig
    strategy: Any
    call_with: Callable[..., AgentResponse]
    invoke_for_strategy: Callable[..., AgentResponse]
    track_usage: Callable[[AgentResponse, str], None]
    track_cost: Callable[[float, str], None]
    track_candidate_usage: Callable[[ResearchCandidate], None]
    collect_provenance: Callable[..., None]
    methodology_summary: Callable[[], str]
    kb_summary: Callable[[], str]
    format_dimension_list: Callable[[list[str]], str]
    goal_constraints_summary: Callable[[], str]


@dataclass
class CandidateAssessment:
    """Score snapshot for one backend's findings on a dimension.

    Collected during multi-candidate selection so inter-rater agreement
    can be computed after the run.  Without this, per-candidate scores
    are discarded when the winner is selected.
    """

    iteration: int
    dimension: str
    backend_name: str
    coverage: float
    quality: float
    total: float


@dataclass
class LoopState:
    """Mutable state for the research loop, shared with the orchestrator."""

    knowledge_base: str = ""
    kb_path: Path = field(default_factory=lambda: Path("knowledge_base.md"))
    explored_dimensions: list[str] = field(default_factory=list)
    discovered_dimensions: list[str] = field(default_factory=list)
    dimension_attempts: dict[str, int] = field(default_factory=dict)
    best_score: float = 0.0
    best_scores: dict[str, float] = field(default_factory=dict)
    iteration: int = 0
    results: list[dict[str, str]] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    iterations_dir: Path = field(default_factory=lambda: Path("iterations"))
    results_path: Path = field(default_factory=lambda: Path("results.tsv"))
    candidate_assessments: list[CandidateAssessment] = field(default_factory=list)

    MAX_ATTEMPTS_PER_DIMENSION: int = 3
    KB_MAX_WORDS: int = 8000


def run_iteration(ctx: LoopContext, state: LoopState) -> None:
    """Execute one full research iteration (hypothesis -> execute -> score -> decide)."""
    state.iteration += 1
    log.info("=" * 60)
    log.info("Iteration %03d", state.iteration)
    log.info("=" * 60)

    hypothesis = _generate_hypothesis(ctx, state)
    if not hypothesis:
        log.warning("Hypothesis generation failed, retrying next iteration.")
        return

    dimension = hypothesis.get("dimension", "unknown")
    questions = hypothesis.get("questions", [])
    approach = hypothesis.get("approach", "")

    state.dimension_attempts[dimension] = state.dimension_attempts.get(dimension, 0) + 1
    attempts = state.dimension_attempts[dimension]
    log.info("Dimension: %s (attempt %d/%d)", dimension, attempts, state.MAX_ATTEMPTS_PER_DIMENSION)

    findings = _execute_research(ctx, state, dimension, questions, approach)
    if not findings:
        log.warning("Research execution returned empty, logging crash.")
        _log_result(state, dimension, IterationScore(), "", status="crash")
        _maybe_exhaust(state, dimension)
        return

    score = _score(ctx, state, dimension, findings)
    prev_best = state.best_scores.get(dimension, 0.0)
    log.info(
        "Scores — coverage: %.1f, quality: %.1f, total: %.1f (dim best: %.1f, global best: %.1f)",
        score.coverage, score.quality, score.total, prev_best, state.best_score,
    )

    kept = score.total > prev_best and score.total >= 30.0
    if kept:
        state.best_scores[dimension] = score.total
        if score.total > state.best_score:
            state.best_score = score.total
        _merge(ctx, state, dimension, findings, score)
        log.info("KEEP — merged into knowledge base.")
    else:
        log.info("DISCARD — findings saved but not merged.")
        _maybe_exhaust(state, dimension)

    write_iteration_markdown(
        iterations_dir=state.iterations_dir,
        iteration=state.iteration,
        dimension=dimension,
        findings=findings,
        score=score,
        kept=kept,
    )
    ctx.collect_provenance(findings, scope=f"iteration-{state.iteration:03d}", dimension=dimension)
    _log_result(
        state, dimension, score, hypothesis.get("rationale", ""),
        status="keep" if kept else "discard",
    )

    if state.iteration % ctx.config.execution.compress_every == 0:
        _compress_knowledge_base(ctx, state)


def _generate_hypothesis(ctx: LoopContext, state: LoopState) -> dict[str, Any] | None:
    """Ask the agent to pick the next research dimension."""
    unexplored = [
        d for d in [*ctx.config.dimensions, *state.discovered_dimensions]
        if d not in state.explored_dimensions
    ]

    prompt = _render(
        "hypothesis.md",
        topic=ctx.config.topic,
        methodology=ctx.methodology_summary(),
        knowledge_summary=ctx.kb_summary(),
        explored_dimensions=ctx.format_dimension_list(state.explored_dimensions),
        unexplored_dimensions=ctx.format_dimension_list(unexplored),
    )

    hypo_backend = ctx.strategy.get_hypothesis_backend()
    resp = ctx.call_with(hypo_backend, prompt, max_turns=3)

    if resp.is_error or not resp.text:
        return None

    ctx.track_usage(resp, hypo_backend.name)

    try:
        return json.loads(resp.text)
    except json.JSONDecodeError:
        text = resp.text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        log.warning("Could not parse hypothesis JSON: %.200s", resp.text)
        return None


def _execute_research(
    ctx: LoopContext,
    state: LoopState,
    dimension: str,
    questions: list[str],
    approach: str,
) -> str:
    """Run a research agent on the given dimension."""
    formatted_questions = "\n".join(f"- {q}" for q in questions) if questions else "- Explore broadly"

    prompt = _render(
        "research.md",
        topic=ctx.config.topic,
        methodology=ctx.methodology_summary(),
        dimension=dimension,
        questions=formatted_questions,
        approach=approach or "Use web search and official documentation",
        knowledge_summary=ctx.kb_summary(),
    )

    kwargs: dict[str, Any] = {}
    if hasattr(ctx.strategy, "route_dimension"):
        kwargs["dimension"] = dimension

    result = ctx.strategy.execute_research(
        prompt,
        ctx.invoke_for_strategy,
        allowed_tools=ctx.config.execution.allowed_tools,
        max_turns=ctx.config.execution.max_turns,
        timeout=ctx.config.execution.timeout_seconds,
        **kwargs,
    )

    if result.candidates is not None:
        for candidate in result.candidates:
            ctx.track_candidate_usage(candidate)
    else:
        ctx.track_cost(result.cost_usd, result.backend_name)

    findings = result.findings
    if result.candidates and len(result.candidates) > 1:
        findings = _select_candidate_findings(ctx, state, dimension, result.candidates)
    elif result.candidates and len(result.candidates) == 1 and not findings:
        findings = result.candidates[0].findings

    if not findings:
        log.error("Research call failed.")
        return ""

    critique = ctx.strategy.post_research(
        findings, ctx.invoke_for_strategy,
        timeout=ctx.config.execution.timeout_seconds,
    )
    if critique:
        ctx.track_cost(critique.cost_usd, critique.backend_name)
        findings += (
            f"\n\n---\n\n## Peer Review ({critique.backend_name})\n\n"
            f"{critique.critique}"
        )

    return findings


def _select_candidate_findings(
    ctx: LoopContext,
    state: LoopState,
    dimension: str,
    candidates: list[ResearchCandidate],
) -> str:
    """Select or merge the best findings from multiple backend candidates."""
    if not candidates:
        return ""

    ranked = sorted(
        candidates,
        key=lambda c: heuristic_score(c.findings, ctx.config, state.explored_dimensions),
        reverse=True,
    )
    merge_mode = ctx.config.execution.strategy_config.merge_mode
    threshold = ctx.config.execution.strategy_config.merge_threshold

    if merge_mode == "union":
        selected: list[tuple[ResearchCandidate, IterationScore]] = []
        for candidate in ranked:
            score = _score(ctx, state, dimension, candidate.findings)
            state.candidate_assessments.append(CandidateAssessment(
                iteration=state.iteration, dimension=dimension,
                backend_name=candidate.backend_name,
                coverage=score.coverage, quality=score.quality, total=score.total,
            ))
            if score.total >= threshold:
                selected.append((candidate, score))
        if not selected:
            return ""
        selected.sort(key=lambda item: item[1].total, reverse=True)
        log.info(
            "Merged %d candidate findings above threshold %.1f for dimension '%s'.",
            len(selected), threshold, dimension,
        )
        return "\n\n---\n\n".join(
            f"<!-- source: {candidate.backend_name}; score: {score.total:.1f} -->\n{candidate.findings}"
            for candidate, score in selected
        )

    shortlist = ranked[: min(2, len(ranked))]
    best_candidate = shortlist[0]
    best_score = -1.0

    for candidate in shortlist:
        score = _score(ctx, state, dimension, candidate.findings)
        state.candidate_assessments.append(CandidateAssessment(
            iteration=state.iteration, dimension=dimension,
            backend_name=candidate.backend_name,
            coverage=score.coverage, quality=score.quality, total=score.total,
        ))
        if score.total > best_score:
            best_candidate = candidate
            best_score = score.total

    log.info(
        "Selected %s from %d candidates for dimension '%s' (score %.1f).",
        best_candidate.backend_name, len(candidates), dimension, best_score,
    )
    return best_candidate.findings


def _score(ctx: LoopContext, state: LoopState, dimension: str, findings: str) -> IterationScore:
    """Score findings using heuristics and an LLM judge."""
    coverage = heuristic_score(findings, ctx.config, state.explored_dimensions)

    quality = 50.0
    judge_raw: dict[str, Any] = {}

    try:
        prompt = _render(
            "evaluate.md",
            topic=ctx.config.topic,
            goal=ctx.config.goal,
            methodology=ctx.methodology_summary(),
            goal_constraints=ctx.goal_constraints_summary(),
            dimension=dimension,
            findings=findings[:_MAX_FINDINGS_CHARS],
            knowledge_summary=ctx.kb_summary(),
        )

        judge_backend = ctx.strategy.get_judge_backend()
        resp = ctx.call_with(judge_backend, prompt, max_turns=3)
        ctx.track_usage(resp, judge_backend.name)

        if not resp.is_error and resp.text:
            judge_raw = parse_judge_response(resp.text)
            quality = quality_score_from_judge(judge_raw)
    except Exception as exc:
        log.warning("Judge scoring failed, using fallback: %s", exc)

    total = combine_scores(coverage, quality)

    return IterationScore(
        coverage=coverage,
        quality=quality,
        total=total,
        dimensions_covered=judge_raw.get("dimensions_covered", [dimension]),
        gaps=judge_raw.get("gaps_identified", []),
        judge_raw=judge_raw,
    )


def _merge(ctx: LoopContext, state: LoopState, dimension: str, findings: str, score: IterationScore) -> None:
    """Merge kept findings into the knowledge base."""
    merged = merge_findings(
        dimension=dimension,
        findings=findings,
        gaps=score.gaps,
        knowledge_base=state.knowledge_base,
        explored_dimensions=state.explored_dimensions,
        discovered_dimensions=state.discovered_dimensions,
        configured_dimensions=ctx.config.dimensions,
    )
    state.knowledge_base = merged["knowledge_base"]
    state.explored_dimensions = merged["explored_dimensions"]
    state.discovered_dimensions = merged["discovered_dimensions"]
    state.kb_path.write_text(state.knowledge_base, encoding="utf-8")
    for gap in score.gaps:
        if gap in state.discovered_dimensions:
            log.info("New dimension discovered: %s", gap)


def _maybe_exhaust(state: LoopState, dimension: str) -> None:
    """Mark a dimension as explored if it has reached max attempts."""
    exhausted = maybe_exhaust_dimension(
        dimension=dimension,
        dimension_attempts=state.dimension_attempts,
        explored_dimensions=state.explored_dimensions,
        max_attempts_per_dimension=state.MAX_ATTEMPTS_PER_DIMENSION,
    )
    if exhausted:
        log.info(
            "Dimension exhausted after %d attempts, moving on: %s",
            state.MAX_ATTEMPTS_PER_DIMENSION, dimension,
        )


def _log_result(
    state: LoopState,
    dimension: str,
    score: IterationScore,
    hypothesis: str,
    *,
    status: str,
) -> None:
    """Append a row to results.tsv for this iteration."""
    row = build_result_row(
        iteration=state.iteration,
        dimension=dimension,
        score=score,
        hypothesis=hypothesis,
        status=status,
        total_cost_usd=state.total_cost,
        total_input_tokens=state.total_input_tokens,
        total_output_tokens=state.total_output_tokens,
    )
    state.results.append(row)
    append_result_row(state.results_path, row)


def _compress_knowledge_base(ctx: LoopContext, state: LoopState) -> None:
    """Distill the knowledge base if it exceeds the word limit."""
    word_count = len(state.knowledge_base.split())
    if word_count <= state.KB_MAX_WORDS:
        return

    log.info(
        "Compressing knowledge base (%d words -> target %d)...",
        word_count, state.KB_MAX_WORDS,
    )

    prompt = (
        "Distill the following research findings into a concise summary. "
        "Preserve all key facts, numbers, comparisons, and trade-offs. "
        "Remove redundancy and filler. Target length: ~3000 words.\n\n"
        f"{state.knowledge_base}"
    )

    compress_backend = ctx.strategy.get_compress_backend()
    resp = ctx.call_with(compress_backend, prompt, max_turns=3, timeout=120)
    ctx.track_usage(resp, compress_backend.name)

    if not resp.is_error and resp.text and len(resp.text) > 200:
        state.knowledge_base = resp.text
        state.kb_path.write_text(state.knowledge_base, encoding="utf-8")
        log.info("Knowledge base compressed to %d words.", len(resp.text.split()))
