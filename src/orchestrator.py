"""Autonomous research loop powered by AI coding agent CLIs.

Implements the Karpathy autoresearch pattern: an infinite loop of
hypothesis generation, research execution, scoring, and keep/discard
decisions.  Each iteration invokes a configurable CLI backend in
headless mode.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import CLAUDE_SHORTNAMES, AgentResponse, Backend, CallOptions, get_backends
from .artifacts import (
    cli_version,
    dashboard_payload,
    evaluation_payload,
    git_commit,
    load_json_if_exists,
    metrics_payload,
    package_version,
    run_manifest_payload,
    should_write_evaluation,
    write_dashboard,
    write_html_report,
    write_pdf_report,
    write_portfolio,
)
from .config import ResearchConfig
from .constraints import (
    format_results_table,
    goal_constraints_summary,
    is_lightweight_mode,
    postprocess_goal_output,
    synthesis_knowledge_context,
    synthesis_results_summary,
)
from .comparison import benchmark_summary, reference_run_comparison
from .provenance import (
    detect_claim_conflicts,
    extract_citations,
    extract_claims,
    link_claims_to_citations,
    score_research_rubric,
    summarize_evidence_quality,
)
from .prompts import render as _render
from . import research_loop as loop_mod
from .pdf_report import render_simple_pdf
from .portfolio import build_portfolio, render_portfolio_html
from .reporting import render_html_report as render_html_report_fn
from .run_io import setup_output_dir, write_results_header
from .run_state import UsageTotals, resume_state, track_candidate_usage, track_cost, track_usage
from .semantic_eval import (
    semantic_calibration,
    semantic_review_disabled,
    semantic_review_empty,
    semantic_review_fallback,
    semantic_review_from_payload,
)
from .strategy import ResearchCandidate, Strategy, get_strategy

log = logging.getLogger("autoresearch")

KB_MAX_WORDS = 4000
LIGHTWEIGHT_KB_WORDS = 800


# ---------------------------------------------------------------------------
# AutoResearcher
# ---------------------------------------------------------------------------

class AutoResearcher:
    """Autonomous research loop.

    Mirrors Karpathy's autoresearch pattern:
    Hypothesis -> Execute -> Score -> Keep/Revert -> Log -> Repeat.

    Supports multi-backend strategies: each research phase can use a
    different backend, and the execution phase can run in parallel
    across backends.

    Args:
        config: Research configuration.
        backend: Default CLI backend (used when strategy is ``"single"``).
        output_dir: Directory for all output artifacts.
        backends: Optional pre-built backend instances (keyed by name).
            If ``None``, built from config.
        strategy: Optional pre-built strategy.  If ``None``, built from config.
    """

    MAX_ATTEMPTS_PER_DIMENSION = 3

    def __init__(
        self,
        config: ResearchConfig,
        backend: Backend,
        output_dir: Path,
        backends: dict[str, Backend] | None = None,
        strategy: Strategy | None = None,
        resume: bool = False,
        config_path: Path | None = None,
    ) -> None:
        self.config = config
        self.backend = backend  # kept for backward compat + summary
        self.resume = resume
        self.config_path = config_path
        self.output_dir = output_dir
        self.iterations_dir = output_dir / "iterations"
        self.results_path = output_dir / "results.tsv"
        self.kb_path = output_dir / "knowledge_base.md"
        self.synthesis_path = output_dir / "synthesis.md"
        self.methods_path = output_dir / "methods.md"
        self.manifest_path = output_dir / "run_manifest.json"
        self.metrics_path = output_dir / "metrics.json"
        self.claims_path = output_dir / "claims.json"
        self.citations_path = output_dir / "citations.json"
        self.evidence_links_path = output_dir / "evidence_links.json"
        self.evidence_quality_path = output_dir / "evidence_quality.json"
        self.rubric_path = output_dir / "rubric.json"
        self.contradictions_path = output_dir / "contradictions.json"
        self.baseline_path = output_dir / "baseline.md"
        self.evaluation_path = output_dir / "evaluation.json"
        self.comparison_path = output_dir / "comparison.json"
        self.strategy_summary_path = output_dir / "strategy_summary.json"
        self.dashboard_path = output_dir / "dashboard.json"
        self.semantic_calibration_path = output_dir / "semantic_calibration.json"
        self.semantic_review_path = output_dir / "semantic_review.json"
        self.report_html_path = output_dir / "report.html"
        self.report_pdf_path = output_dir / "report.pdf"
        self.portfolio_path = output_dir.parent / "portfolio.json"
        self.portfolio_html_path = output_dir.parent / "portfolio.html"

        # Multi-backend support
        if backends is None:
            all_names = config.execution.backends.all_backend_names()
            self.backends = get_backends(all_names)
        else:
            self.backends = backends

        if strategy is None:
            self.strategy = get_strategy(
                config.execution.strategy,
                config.execution.backends,
                config.execution.strategy_config,
                self.backends,
            )
        else:
            self.strategy = strategy

        self.iteration: int = 0
        self.best_score: float = 0.0
        self.best_scores: dict[str, float] = {}
        self.knowledge_base: str = ""
        self.explored_dimensions: list[str] = []
        self.discovered_dimensions: list[str] = []
        self.total_cost: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.per_backend_costs: dict[str, float] = {}
        self.per_backend_tokens: dict[str, dict[str, int]] = {}
        self.results: list[dict[str, str]] = []
        self._dimension_attempts: dict[str, int] = {}
        self._run_started_at: str | None = None
        self._run_completed_at: str | None = None
        self._run_status: str = "initialized"
        self._claims: list[dict[str, Any]] = []
        self._citations: list[dict[str, Any]] = []
        self._candidate_assessments: list = []
        self._usage = UsageTotals()
        self._backend_workdir: Path | None = None

    def _call(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Invoke the default backend with config defaults.

        For backward compatibility.  New code should use ``_call_with``.
        """
        backend = kwargs.pop("_backend", self.backend)
        return self._call_with(backend, prompt, **kwargs)

    @staticmethod
    def _resolve_model(backend: Backend, config_model: str) -> str:
        """Translate the config model name for a specific backend.

        If the config uses a Claude shortname (``"sonnet"``, ``"opus"``,
        ``"haiku"``) and the backend is not Claude, substitute that
        backend's ``capabilities.default_model`` instead.
        """
        if config_model in CLAUDE_SHORTNAMES and backend.name != "claude":
            resolved = backend.capabilities.default_model
            if resolved:
                log.debug(
                    "Model '%s' not valid for %s, using '%s'.",
                    config_model, backend.name, resolved,
                )
                return resolved
        return config_model

    def _call_with(self, backend: Backend, prompt: str, **kwargs: Any) -> AgentResponse:
        """Invoke a specific backend with default options from config.

        Keyword arguments override the defaults from ``self.config.execution``.
        Automatically translates Claude model shortnames for non-Claude backends.
        """
        config_model = kwargs.pop("model", self.config.execution.model)
        model = self._resolve_model(backend, config_model)
        isolated = self._should_isolate_backend(backend)
        opts = CallOptions(
            model=model,
            allowed_tools=kwargs.pop("allowed_tools", ""),
            max_turns=kwargs.pop("max_turns", self.config.execution.max_turns),
            max_budget_usd=kwargs.pop("max_budget_usd", self.config.execution.max_budget_per_call),
            working_directory=str(self._backend_runtime_dir()) if isolated and self._backend_runtime_dir() else "",
            sanitize_environment=isolated and self.config.execution.sanitize_backend_env,
        )
        timeout = kwargs.pop("timeout", self.config.execution.timeout_seconds)
        return backend.invoke(prompt, opts, timeout=timeout)

    def _invoke_for_strategy(
        self,
        backend: Backend,
        prompt: str,
        *,
        allowed_tools: str = "",
        max_turns: int = 0,
        timeout: int = 0,
    ) -> AgentResponse:
        """Callback passed to strategies for backend invocation.

        Applies config defaults for any zero/empty values.
        """
        return self._call_with(
            backend,
            prompt,
            allowed_tools=allowed_tools or "",
            max_turns=max_turns or self.config.execution.max_turns,
            timeout=timeout or self.config.execution.timeout_seconds,
        )

    def _track_cost(self, cost: float, backend_name: str = "") -> None:
        """Add cost to totals (no token data available)."""
        track_cost(self._usage, cost, backend_name)
        self.total_cost = self._usage.total_cost
        self.per_backend_costs = self._usage.per_backend_costs

    def _track_usage(self, resp: AgentResponse, backend_name: str = "") -> None:
        """Add cost and token counts to totals and per-backend tracking."""
        track_usage(self._usage, resp, backend_name)
        self.total_cost = self._usage.total_cost
        self.total_input_tokens = self._usage.total_input_tokens
        self.total_output_tokens = self._usage.total_output_tokens
        self.per_backend_costs = self._usage.per_backend_costs
        self.per_backend_tokens = self._usage.per_backend_tokens

    def _track_candidate_usage(self, candidate: ResearchCandidate) -> None:
        """Record usage for a strategy-produced research candidate."""
        track_candidate_usage(self._usage, candidate)
        self.total_cost = self._usage.total_cost
        self.total_input_tokens = self._usage.total_input_tokens
        self.total_output_tokens = self._usage.total_output_tokens
        self.per_backend_costs = self._usage.per_backend_costs
        self.per_backend_tokens = self._usage.per_backend_tokens

    # -- Public API --------------------------------------------------------

    def run(self) -> None:
        """Start the research loop.  ``Ctrl+C`` triggers synthesis."""
        self._setup()
        if self.resume:
            self._resume()
        self._run_status = "running"

        log.info(
            "Starting autoresearch [%s]: %s (%d dimensions configured)",
            self.strategy.describe(),
            self.config.topic,
            len(self.config.dimensions),
        )

        try:
            while True:
                if self._should_stop():
                    break
                self._run_iteration()
        except KeyboardInterrupt:
            log.info("Interrupted. Generating synthesis...")
            self._run_status = "interrupted"
        finally:
            if self._run_status == "running":
                self._run_status = "completed"
            self._generate_synthesis()
            self._generate_baseline()
            self._finalize_run_artifacts()
            self._print_summary()

    def synthesize_only(self) -> None:
        """Generate a synthesis report from existing iteration data."""
        self._setup()
        self._resume()
        self._run_status = "synthesis_only"
        self._generate_synthesis()
        self._generate_baseline()
        self._finalize_run_artifacts()

    def _should_stop(self) -> bool:
        """Return True when runtime stopping criteria have been met."""
        if 0 < self.config.execution.max_iterations <= self.iteration:
            log.info("Reached max_iterations=%d, stopping.", self.iteration)
            return True

        target = self.config.scoring.target_dimensions_total
        if target > 0 and len(self.explored_dimensions) >= target:
            log.info(
                "Reached target_dimensions_total=%d with %d explored dimensions, stopping.",
                target,
                len(self.explored_dimensions),
            )
            return True

        return False

    # -- Setup & resume ----------------------------------------------------

    def _setup(self) -> None:
        """Create output directories and initialise results.tsv if needed."""
        setup_output_dir(self.output_dir, self.iterations_dir)
        self._ensure_backend_runtime_dir()
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()

        if not self.results_path.exists():
            self._write_tsv_header()
        self._write_methods()
        self._write_run_manifest()

    def _resume(self) -> None:
        """Rebuild in-memory state from existing iteration files and TSV."""
        state = resume_state(
            iterations_dir=self.iterations_dir,
            results_path=self.results_path,
            knowledge_base_path=self.kb_path,
            configured_dimensions=self.config.dimensions,
            max_attempts_per_dimension=self.MAX_ATTEMPTS_PER_DIMENSION,
        )
        if not state["iteration"]:
            return

        log.info("Resuming from %d existing iterations.", state["iteration"])
        self.results = state["results"]
        self.best_score = state["best_score"]
        self.best_scores = state["best_scores"]
        self.explored_dimensions = state["explored_dimensions"]
        self.discovered_dimensions = state["discovered_dimensions"]
        self._dimension_attempts = state["dimension_attempts"]
        self.knowledge_base = state["knowledge_base"]
        self.iteration = state["iteration"]

    # -- Core loop ---------------------------------------------------------

    def _build_loop_context(self) -> "loop_mod.LoopContext":
        """Create the callback bundle for the research loop."""
        return loop_mod.LoopContext(
            config=self.config,
            strategy=self.strategy,
            call_with=self._call_with,
            invoke_for_strategy=self._invoke_for_strategy,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            track_candidate_usage=self._track_candidate_usage,
            collect_provenance=self._collect_provenance,
            methodology_summary=self._methodology_summary,
            kb_summary=self._kb_summary,
            format_dimension_list=self._format_dimension_list,
            goal_constraints_summary=self._goal_constraints_summary,
        )

    def _build_loop_state(self) -> "loop_mod.LoopState":
        """Create a LoopState that shares mutable state with the orchestrator."""
        return loop_mod.LoopState(
            knowledge_base=self.knowledge_base,
            kb_path=self.kb_path,
            explored_dimensions=self.explored_dimensions,
            discovered_dimensions=self.discovered_dimensions,
            dimension_attempts=self._dimension_attempts,
            best_score=self.best_score,
            best_scores=self.best_scores,
            iteration=self.iteration,
            results=self.results,
            total_cost=self.total_cost,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            iterations_dir=self.iterations_dir,
            results_path=self.results_path,
            candidate_assessments=self._candidate_assessments,
        )

    def _sync_from_loop_state(self, state: "loop_mod.LoopState") -> None:
        """Copy mutable state back from the loop into the orchestrator."""
        self.knowledge_base = state.knowledge_base
        self.explored_dimensions = state.explored_dimensions
        self.discovered_dimensions = state.discovered_dimensions
        self._dimension_attempts = state.dimension_attempts
        self.best_score = state.best_score
        self.best_scores = state.best_scores
        self.iteration = state.iteration
        self.results = state.results
        self._candidate_assessments = state.candidate_assessments

    def _run_iteration(self) -> None:
        """Execute one full research iteration via the extracted loop module."""
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        loop_mod.run_iteration(ctx, state)
        self._sync_from_loop_state(state)

    # -- Loop shims (delegate to research_loop, keep tests green) ----------
    # TODO: remove these when tests are rewritten to test research_loop directly

    def _generate_hypothesis(self) -> dict[str, Any] | None:
        return loop_mod._generate_hypothesis(self._build_loop_context(), self._build_loop_state())

    def _execute_research(self, dimension: str, questions: list[str], approach: str) -> str:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._execute_research(ctx, state, dimension, questions, approach)

    def _select_candidate_findings(self, dimension: str, candidates: list) -> str:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._select_candidate_findings(ctx, state, dimension, candidates)

    def _score(self, dimension: str, findings: str):
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._score(ctx, state, dimension, findings)

    def _merge_findings(self, dimension: str, findings: str, score) -> None:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        loop_mod._merge(ctx, state, dimension, findings, score)
        self._sync_from_loop_state(state)

    def _maybe_exhaust_dimension(self, dimension: str) -> None:
        state = self._build_loop_state()
        loop_mod._maybe_exhaust(state, dimension)
        self._sync_from_loop_state(state)

    def _save_iteration(self, dimension: str, findings: str, score, kept: bool) -> None:
        from .run_io import write_iteration_markdown
        write_iteration_markdown(
            iterations_dir=self.iterations_dir, iteration=self.iteration,
            dimension=dimension, findings=findings, score=score, kept=kept,
        )
        self._collect_provenance(findings, scope=f"iteration-{self.iteration:03d}", dimension=dimension)

    def _log_result(self, dimension: str, score, hypothesis: str, *, status: str) -> None:
        from .run_io import build_result_row, append_result_row
        row = build_result_row(
            iteration=self.iteration, dimension=dimension, score=score,
            hypothesis=hypothesis, status=status, total_cost_usd=self.total_cost,
            total_input_tokens=self.total_input_tokens, total_output_tokens=self.total_output_tokens,
        )
        self.results.append(row)
        append_result_row(self.results_path, row)

    def _write_tsv_header(self) -> None:
        """Write the header row to a new results.tsv file."""
        write_results_header(self.results_path)

    # -- Synthesis ---------------------------------------------------------

    def _generate_synthesis(self) -> None:
        """Generate a final synthesis report from the accumulated knowledge base."""
        if not self.knowledge_base:
            log.info("No knowledge base to synthesize.")
            return

        results_summary = self._synthesis_results_summary()
        knowledge_context = self._synthesis_knowledge_context()

        prompt = _render(
            "synthesize.md",
            topic=self.config.topic,
            goal=self.config.goal,
            methodology=self._methodology_summary(),
            goal_constraints=self._goal_constraints_summary(),
            lightweight_mode="yes" if self._is_lightweight_mode() else "no",
            knowledge_base=knowledge_context,
            results_summary=results_summary,
        )

        log.info("Generating final synthesis report...")
        synth_backend = self.strategy.get_synthesize_backend()
        resp = self._call_with(synth_backend, prompt, max_turns=5)
        self._track_usage(resp, synth_backend.name)

        if not resp.is_error and resp.text:
            final_text = self._postprocess_goal_output(resp.text)
            self.synthesis_path.write_text(final_text, encoding="utf-8")
            self._collect_provenance(final_text, scope="synthesis")
            log.info("Synthesis saved to %s", self.synthesis_path)

    # -- Helpers -----------------------------------------------------------

    def _kb_summary(self) -> str:
        """Return a bounded summary of the knowledge base for prompt context.

        Uses a sandwich pattern: keeps early findings (context) plus
        the most recent findings (freshest data), truncating the middle.
        """
        if not self.knowledge_base:
            return "(No prior findings yet — this is the first iteration.)"
        words = self.knowledge_base.split()
        if len(words) <= KB_MAX_WORDS:
            return self.knowledge_base
        head_size = KB_MAX_WORDS // 3
        tail_size = KB_MAX_WORDS - head_size
        head = " ".join(words[:head_size])
        tail = " ".join(words[-tail_size:])
        return f"{head}\n\n[... {len(words) - KB_MAX_WORDS} words truncated ...]\n\n{tail}"

    def _format_dimension_list(self, dims: list[str]) -> str:
        """Format a list of dimensions as a markdown bullet list."""
        if not dims:
            return "(none)"
        return "\n".join(f"- {d}" for d in dims)

    def _methodology_summary(self) -> str:
        """Format methodology guidance for prompts and reporting."""
        methodology = self.config.methodology
        lines: list[str] = []
        if methodology.question:
            lines.append(f"- Question: {methodology.question}")
        if methodology.scope:
            lines.append(f"- Scope: {methodology.scope}")
        if methodology.inclusion_criteria:
            lines.append("- Inclusion criteria:")
            lines.extend(f"  - {item}" for item in methodology.inclusion_criteria)
        if methodology.exclusion_criteria:
            lines.append("- Exclusion criteria:")
            lines.extend(f"  - {item}" for item in methodology.exclusion_criteria)
        if methodology.preferred_source_types:
            lines.append("- Preferred source types:")
            lines.extend(f"  - {item}" for item in methodology.preferred_source_types)
        if methodology.recency_days > 0:
            lines.append(f"- Prefer sources from the last {methodology.recency_days} days for unstable facts.")
        return "\n".join(lines) if lines else "(No explicit methodology constraints.)"

    def _ensure_backend_runtime_dir(self) -> None:
        """Create a neutral working directory for backend subprocesses when enabled."""
        if not self.config.execution.isolate_backend_context:
            return
        if self._backend_workdir is None:
            self._backend_workdir = Path(tempfile.mkdtemp(prefix="autoresearch-backend-"))

    def _backend_runtime_dir(self) -> Path | None:
        """Return the isolated backend working directory, if enabled."""
        if not self.config.execution.isolate_backend_context:
            return None
        self._ensure_backend_runtime_dir()
        return self._backend_workdir

    def _should_isolate_backend(self, backend: Backend) -> bool:
        """Return True when backend-context isolation should be applied."""
        return self.config.execution.isolate_backend_context

    def _is_lightweight_mode(self) -> bool:
        """Return True when the run should optimize for brevity and low overhead."""
        return is_lightweight_mode(
            explicit_enabled=self.config.execution.lightweight_mode,
            goal=self.config.goal,
            topic=self.config.topic,
        )

    def _goal_constraints_summary(self) -> str:
        """Extract explicit deliverable constraints from the goal text."""
        return goal_constraints_summary(self.config.goal, lightweight_mode=self._is_lightweight_mode())

    def _postprocess_goal_output(self, text: str) -> str:
        """Deterministically repair short-form outputs to obey explicit goal constraints."""
        return postprocess_goal_output(text, goal=self.config.goal)

    def _synthesis_knowledge_context(self) -> str:
        """Return the knowledge context to send to synthesis."""
        return synthesis_knowledge_context(
            self.knowledge_base,
            lightweight_mode=self._is_lightweight_mode(),
            lightweight_kb_words=LIGHTWEIGHT_KB_WORDS,
        )

    def _synthesis_results_summary(self) -> str:
        """Return a run summary tailored for synthesis prompting."""
        return synthesis_results_summary(self.results, lightweight_mode=self._is_lightweight_mode())

    def _format_results_table(self) -> str:
        """Format the results log as a markdown table for synthesis prompts."""
        return format_results_table(self.results)

    def _write_methods(self) -> None:
        """Write a human-readable methods artifact for the run."""
        content = (
            f"# Research Methods\n\n"
            f"## Goal\n\n{self.config.goal}\n\n"
            f"## Topic\n\n{self.config.topic}\n\n"
            f"## Methodology\n\n{self._methodology_summary()}\n\n"
            f"## Runtime\n\n"
            f"- Strategy: {self.strategy.describe()}\n"
            f"- Resume requested: {self.resume}\n"
            f"- Max iterations: {self.config.execution.max_iterations}\n"
            f"- Lightweight mode: {self._is_lightweight_mode()}\n"
            f"- Target dimensions total: {self.config.scoring.target_dimensions_total}\n"
            f"- Allowed tools: {self.config.execution.allowed_tools or '(none)'}\n"
        )
        self.methods_path.write_text(content, encoding="utf-8")

    def _print_summary(self) -> None:
        """Print a session summary to stdout."""
        print("\n" + "=" * 60)
        print("  AUTORESEARCH SESSION COMPLETE")
        print("=" * 60)
        print(f"  Strategy:    {self.strategy.describe()}")
        print(f"  Topic:       {self.config.topic}")
        print()
        print(f"  Iterations:  {self.iteration}")
        print(f"  Best score:  {self.best_score:.1f}")
        print(f"  Total cost:  ${self.total_cost:.3f}")
        print(f"  Tokens:      {self.total_input_tokens:,} in / {self.total_output_tokens:,} out")
        if self.per_backend_costs or self.per_backend_tokens:
            all_names = sorted(set(self.per_backend_costs) | set(self.per_backend_tokens))
            for name in all_names:
                cost = self.per_backend_costs.get(name, 0.0)
                tok = self.per_backend_tokens.get(name, {"input": 0, "output": 0})
                print(f"    {name}: {tok['input']:,} in / {tok['output']:,} out (${cost:.3f})")
        print(f"  Dimensions:  {len(self.explored_dimensions)} explored")
        self._print_rubric_summary()
        self._print_agreement_summary()
        print(f"  Results:     {self.results_path}")
        if self.synthesis_path.exists():
            print(f"  Synthesis:   {self.synthesis_path}")
        print("=" * 60)

    def _print_rubric_summary(self) -> None:
        """Print rubric grade in the completion banner if available."""
        from .artifacts import load_json_if_exists

        rubric = load_json_if_exists(self.rubric_path, {})
        if not rubric:
            return
        grade = rubric.get("grade", "?")
        score = rubric.get("overall_score", 0.0)
        dims = rubric.get("dimensions", {})
        print()
        print(f"  Rubric:      {grade} ({score:.2f})")
        print(f"    evidence_quality:      {dims.get('evidence_quality', 0):.2f}")
        print(f"    citation_coverage:     {dims.get('citation_coverage', 0):.2f}")
        print(f"    source_diversity:      {dims.get('source_diversity', 0):.2f}")
        print(f"    uncertainty_reporting: {dims.get('uncertainty_reporting', 0):.2f}")
        print(f"    actionability:         {dims.get('actionability', 0):.2f}")
        print(f"    contradiction_handling:{dims.get('contradiction_handling', 0):.2f}")
        print()

    def _print_agreement_summary(self) -> None:
        """Print inter-rater agreement in the completion banner if available."""
        from .artifacts import load_json_if_exists

        agreement = load_json_if_exists(self.output_dir / "agreement.json", {})
        if not agreement or agreement.get("dimensions_with_multiple_candidates", 0) == 0:
            return
        n = agreement["dimensions_with_multiple_candidates"]
        rate = agreement.get("decision_agreement_rate")
        kappa = agreement.get("cohens_kappa")
        delta = agreement.get("mean_score_delta")
        parts = [f"{n} dimensions"]
        if rate is not None:
            parts.append(f"{rate:.0%} decision agreement")
        if kappa is not None:
            parts.append(f"kappa {kappa:.2f}")
        print(f"  Agreement:   {', '.join(parts)}")
        if delta is not None:
            print(f"    mean score delta: {delta:.1f}")
        print()

    def _finalize_run_artifacts(self) -> None:
        """Write final manifest and metrics artifacts."""
        self._run_completed_at = datetime.now(timezone.utc).isoformat()
        self._write_run_manifest()
        self._write_metrics()
        self._write_agreement_artifact()
        self._write_provenance_artifacts()
        self._write_dashboard_artifact()
        self._write_html_report()
        self._write_pdf_report()
        self._write_portfolio_artifacts()

    def _write_agreement_artifact(self) -> None:
        """Compute and write inter-rater agreement when multi-candidate data exists."""
        from .scorer import compute_inter_rater_agreement

        agreement = compute_inter_rater_agreement(self._candidate_assessments)
        if agreement["dimensions_with_multiple_candidates"] > 0:
            agreement_path = self.output_dir / "agreement.json"
            agreement_path.write_text(json.dumps(agreement, indent=2), encoding="utf-8")

    def _write_run_manifest(self) -> None:
        """Write a machine-readable manifest for reproducibility."""
        payload = run_manifest_payload(
            config=self.config,
            strategy_description=self.strategy.describe(),
            backends=self.backends,
            output_dir=self.output_dir,
            resume=self.resume,
            config_path=self.config_path,
            run_status=self._run_status,
            run_started_at=self._run_started_at,
            run_completed_at=self._run_completed_at,
            package_version=package_version(),
            git_commit=git_commit(),
            cli_version_resolver=cli_version,
        )
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_metrics(self) -> None:
        """Write machine-readable run metrics."""
        payload = metrics_payload(
            benchmark_id=self.config.evaluation.benchmark_id,
            run_status=self._run_status,
            iteration=self.iteration,
            best_score=self.best_score,
            explored_dimensions=self.explored_dimensions,
            discovered_dimensions=self.discovered_dimensions,
            total_cost=self.total_cost,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            per_backend_costs=self.per_backend_costs,
            per_backend_tokens=self.per_backend_tokens,
            results=self.results,
        )
        self.metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _collect_provenance(self, text: str, *, scope: str, dimension: str = "") -> None:
        """Collect claims and citations from generated content."""
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for claim in extract_claims(text, scope=scope, dimension=dimension):
            claim["id"] = f"{scope}-{claim['id']}"
            self._claims.append(claim)
        for citation in extract_citations(text, scope=scope, retrieved_at=retrieved_at):
            citation["id"] = f"{scope}-{citation['id']}"
            self._citations.append(citation)

    def _write_provenance_artifacts(self) -> None:
        """Write claim and citation artifacts."""
        self.claims_path.write_text(json.dumps(self._claims, indent=2), encoding="utf-8")
        self.citations_path.write_text(json.dumps(self._citations, indent=2), encoding="utf-8")
        evidence_links = link_claims_to_citations(self._claims, self._citations)
        evidence_quality = summarize_evidence_quality(self._claims, evidence_links)
        contradictions = detect_claim_conflicts(self._claims)
        rubric = score_research_rubric(
            self._claims,
            self._citations,
            evidence_links,
            contradictions,
        )
        benchmark_summary = self._benchmark_summary()
        reference_comparison = self._reference_run_comparison()
        semantic_review = self._semantic_review(
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            contradictions=contradictions,
        )
        semantic_calibration = self._semantic_calibration(
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
        )
        self.evidence_links_path.write_text(json.dumps(evidence_links, indent=2), encoding="utf-8")
        self.evidence_quality_path.write_text(json.dumps(evidence_quality, indent=2), encoding="utf-8")
        self.rubric_path.write_text(json.dumps(rubric, indent=2), encoding="utf-8")
        self.contradictions_path.write_text(json.dumps(contradictions, indent=2), encoding="utf-8")
        self.semantic_review_path.write_text(json.dumps(semantic_review, indent=2), encoding="utf-8")
        self.semantic_calibration_path.write_text(
            json.dumps(semantic_calibration, indent=2),
            encoding="utf-8",
        )
        self._write_evaluation_artifact(
            evidence_quality,
            rubric,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
            semantic_review=semantic_review,
            semantic_calibration=semantic_calibration,
        )

    def _generate_baseline(self) -> None:
        """Generate an optional single-pass baseline answer for comparison."""
        if not self.config.evaluation.run_baselines:
            return
        prompt = _render(
            "baseline.md",
            topic=self.config.topic,
            goal=self.config.goal,
            methodology=self._methodology_summary(),
            goal_constraints=self._goal_constraints_summary(),
            lightweight_mode="yes" if self._is_lightweight_mode() else "no",
        )
        baseline_backend = self.strategy.get_synthesize_backend()
        resp = self._call_with(baseline_backend, prompt, max_turns=3)
        self._track_usage(resp, baseline_backend.name)
        if not resp.is_error and resp.text:
            final_text = self._postprocess_goal_output(resp.text)
            self.baseline_path.write_text(final_text, encoding="utf-8")
            self._collect_provenance(final_text, scope="baseline")

    def _write_evaluation_artifact(
        self,
        evidence_quality: dict[str, Any],
        rubric: dict[str, Any],
        *,
        benchmark_summary: dict[str, Any],
        reference_comparison: dict[str, Any],
        semantic_review: dict[str, Any],
        semantic_calibration: dict[str, Any],
    ) -> None:
        """Write optional evaluation summary comparing iterative output to a baseline."""
        if not should_write_evaluation(self.config):
            return

        payload = evaluation_payload(
            benchmark_id=self.config.evaluation.benchmark_id,
            baseline_exists=self.baseline_path.exists(),
            claims=self._claims,
            citations=self._citations,
            evidence_quality=evidence_quality,
            rubric=rubric,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
            semantic_review=semantic_review,
            semantic_calibration=semantic_calibration,
        )
        self.evaluation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.comparison_path.write_text(json.dumps(reference_comparison, indent=2), encoding="utf-8")
        self.strategy_summary_path.write_text(
            json.dumps(reference_comparison.get("strategy_summary", {}), indent=2),
            encoding="utf-8",
        )

    def _write_html_report(self) -> None:
        write_html_report(self.output_dir, config=self.config, render_fn=render_html_report_fn)

    def _write_pdf_report(self) -> None:
        write_pdf_report(
            self.output_dir,
            config=self.config,
            best_score=self.best_score,
            iteration=self.iteration,
            explored_dimensions=self.explored_dimensions,
            render_pdf_fn=render_simple_pdf,
        )

    def _write_dashboard_artifact(self) -> None:
        write_dashboard(
            self.output_dir,
            config=self.config,
            best_score=self.best_score,
            iteration=self.iteration,
            explored_dimensions=self.explored_dimensions,
        )

    def _write_portfolio_artifacts(self) -> None:
        write_portfolio(self.output_dir, build_portfolio, render_portfolio_html)

    def _semantic_review(
        self,
        *,
        rubric: dict[str, Any],
        evidence_quality: dict[str, Any],
        benchmark_summary: dict[str, Any],
        contradictions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Optionally run a final judge pass over the synthesized report."""
        if not self.config.evaluation.semantic_review:
            return semantic_review_disabled()

        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        judge_backend = self.strategy.get_judge_backend()
        if not synthesis_text.strip():
            return semantic_review_empty(judge_backend=judge_backend.name)

        prompt = _render(
            "semantic_judge.md",
            topic=self.config.topic,
            methodology=self._methodology_summary(),
            synthesis=synthesis_text,
            rubric=json.dumps(rubric, indent=2),
            evidence_quality=json.dumps(evidence_quality, indent=2),
            benchmark_summary=json.dumps(benchmark_summary, indent=2),
            contradictions=json.dumps(contradictions, indent=2),
        )
        resp = self._call_with(judge_backend, prompt, max_turns=3)
        self._track_usage(resp, judge_backend.name)

        fallback = semantic_review_fallback(
            judge_backend=judge_backend.name,
            rubric=rubric,
            evidence_quality=evidence_quality,
            raw_response=resp.text,
        )

        if resp.is_error or not resp.text:
            return fallback
        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError:
            return fallback

        return semantic_review_from_payload(payload, judge_backend=judge_backend.name, raw_response=resp.text)

    def _semantic_calibration(
        self,
        *,
        rubric: dict[str, Any],
        evidence_quality: dict[str, Any],
        benchmark_summary: dict[str, Any],
        reference_comparison: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine rubric, benchmark, evidence, and consistency into a calibrated quality score."""
        return semantic_calibration(
            enabled=self.config.evaluation.semantic_calibration,
            goal=self.config.goal,
            methodology_question=self.config.methodology.question,
            methodology_scope=self.config.methodology.scope,
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
        )

    def _reference_run_comparison(self) -> dict[str, Any]:
        """Compare the current run to referenced prior outputs for consistency analysis."""
        return reference_run_comparison(
            reference_runs=self.config.evaluation.reference_runs,
            current_strategy=self.config.execution.strategy,
            current_best_score=self.best_score,
            current_dimensions=self.explored_dimensions,
            claims=self._claims,
            citations=self._citations,
        )

    def _benchmark_summary(self) -> dict[str, Any]:
        """Evaluate current run outputs against optional benchmark expectations."""
        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        return benchmark_summary(
            benchmark_id=self.config.evaluation.benchmark_id,
            config_expected_dimensions=list(self.config.evaluation.expected_dimensions),
            config_required_keywords=list(self.config.evaluation.required_keywords),
            knowledge_text=self.knowledge_base or "",
            synthesis_text=synthesis_text,
        )

