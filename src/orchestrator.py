"""Autonomous research loop powered by AI coding agent CLIs.

Implements the Karpathy autoresearch pattern: an infinite loop of
hypothesis generation, research execution, scoring, and keep/discard
decisions.  Each iteration invokes a configurable CLI backend in
headless mode.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import CLAUDE_SHORTNAMES, AgentResponse, Backend, CallOptions, get_backends
from .config import ResearchConfig
from .prompts import render as _render
from .scorer import (
    IterationScore,
    _MAX_FINDINGS_CHARS,
    combine_scores,
    heuristic_score,
    parse_judge_response,
    quality_score_from_judge,
)
from .strategy import Strategy, get_strategy

log = logging.getLogger("autoresearch")

KB_MAX_WORDS = 4000


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
    ) -> None:
        self.config = config
        self.backend = backend  # kept for backward compat + summary
        self.output_dir = output_dir
        self.iterations_dir = output_dir / "iterations"
        self.results_path = output_dir / "results.tsv"
        self.kb_path = output_dir / "knowledge_base.md"
        self.synthesis_path = output_dir / "synthesis.md"

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
        self.total_cost: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.per_backend_costs: dict[str, float] = {}
        self.per_backend_tokens: dict[str, dict[str, int]] = {}
        self.results: list[dict[str, str]] = []
        self._dimension_attempts: dict[str, int] = {}

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
        opts = CallOptions(
            model=model,
            allowed_tools=kwargs.pop("allowed_tools", ""),
            max_turns=kwargs.pop("max_turns", self.config.execution.max_turns),
            max_budget_usd=kwargs.pop("max_budget_usd", self.config.execution.max_budget_per_call),
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
        self.total_cost += cost
        if backend_name:
            self.per_backend_costs[backend_name] = (
                self.per_backend_costs.get(backend_name, 0.0) + cost
            )

    def _track_usage(self, resp: AgentResponse, backend_name: str = "") -> None:
        """Add cost and token counts to totals and per-backend tracking."""
        self._track_cost(resp.cost_usd, backend_name)
        self.total_input_tokens += resp.input_tokens
        self.total_output_tokens += resp.output_tokens
        if backend_name:
            entry = self.per_backend_tokens.setdefault(
                backend_name, {"input": 0, "output": 0}
            )
            entry["input"] += resp.input_tokens
            entry["output"] += resp.output_tokens

    # -- Public API --------------------------------------------------------

    def run(self) -> None:
        """Start the research loop.  ``Ctrl+C`` triggers synthesis."""
        self._setup()
        self._resume()

        log.info(
            "Starting autoresearch [%s]: %s (%d dimensions configured)",
            self.strategy.describe(),
            self.config.topic,
            len(self.config.dimensions),
        )

        try:
            while True:
                if 0 < self.config.execution.max_iterations <= self.iteration:
                    log.info("Reached max_iterations=%d, stopping.", self.iteration)
                    break
                self._run_iteration()
        except KeyboardInterrupt:
            log.info("Interrupted. Generating synthesis...")
        finally:
            self._generate_synthesis()
            self._print_summary()

    def synthesize_only(self) -> None:
        """Generate a synthesis report from existing iteration data."""
        self._setup()
        self._resume()
        self._generate_synthesis()

    # -- Setup & resume ----------------------------------------------------

    def _setup(self) -> None:
        """Create output directories and initialise results.tsv if needed."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.iterations_dir.mkdir(exist_ok=True)

        if not self.results_path.exists():
            self._write_tsv_header()

    def _resume(self) -> None:
        """Rebuild in-memory state from existing iteration files and TSV."""
        existing = sorted(self.iterations_dir.glob("iter_*.md"))
        if not existing:
            return

        log.info("Resuming from %d existing iterations.", len(existing))

        if self.results_path.exists():
            with open(self.results_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    self.results.append(dict(row))
                    dim = row.get("dimension", "")
                    status = row.get("status", "")

                    if dim:
                        self._dimension_attempts[dim] = self._dimension_attempts.get(dim, 0) + 1

                    if status == "keep":
                        try:
                            score = float(row.get("total_score", 0))
                        except (ValueError, TypeError):
                            score = 0.0
                        
                        if dim:
                            if score > self.best_scores.get(dim, 0.0):
                                self.best_scores[dim] = score
                            if dim not in self.explored_dimensions:
                                self.explored_dimensions.append(dim)
                        
                        if score > self.best_score:
                            self.best_score = score

                    if dim and self._dimension_attempts.get(dim, 0) >= self.MAX_ATTEMPTS_PER_DIMENSION:
                        if dim not in self.explored_dimensions:
                            self.explored_dimensions.append(dim)

        if self.kb_path.exists():
            self.knowledge_base = self.kb_path.read_text(encoding="utf-8")

        self.iteration = len(existing)

    # -- Core loop ---------------------------------------------------------

    def _run_iteration(self) -> None:
        """Execute one full research iteration (hypothesis -> execute -> score -> decide)."""
        self.iteration += 1
        log.info("=" * 60)
        log.info("Iteration %03d", self.iteration)
        log.info("=" * 60)

        hypothesis = self._generate_hypothesis()
        if not hypothesis:
            log.warning("Hypothesis generation failed, retrying next iteration.")
            return

        dimension = hypothesis.get("dimension", "unknown")
        questions = hypothesis.get("questions", [])
        approach = hypothesis.get("approach", "")

        self._dimension_attempts[dimension] = self._dimension_attempts.get(dimension, 0) + 1
        attempts = self._dimension_attempts[dimension]
        log.info("Dimension: %s (attempt %d/%d)", dimension, attempts, self.MAX_ATTEMPTS_PER_DIMENSION)

        findings = self._execute_research(dimension, questions, approach)
        if not findings:
            log.warning("Research execution returned empty, logging crash.")
            self._log_result(dimension, IterationScore(), "", status="crash")
            self._maybe_exhaust_dimension(dimension)
            return

        score = self._score(dimension, findings)
        prev_best = self.best_scores.get(dimension, 0.0)
        log.info(
            "Scores — coverage: %.1f, quality: %.1f, total: %.1f (dim best: %.1f, global best: %.1f)",
            score.coverage,
            score.quality,
            score.total,
            prev_best,
            self.best_score,
        )

        # Keep if it beats the previous best for THIS dimension, and is above a quality floor
        kept = score.total > prev_best and score.total >= 30.0
        if kept:
            self.best_scores[dimension] = score.total
            if score.total > self.best_score:
                self.best_score = score.total
            
            self._merge_findings(dimension, findings, score)
            log.info("KEEP — merged into knowledge base.")
        else:
            log.info("DISCARD — findings saved but not merged.")
            self._maybe_exhaust_dimension(dimension)

        self._save_iteration(dimension, findings, score, kept)
        self._log_result(
            dimension,
            score,
            hypothesis.get("rationale", ""),
            status="keep" if kept else "discard",
        )

        if self.iteration % self.config.execution.compress_every == 0:
            self._compress_knowledge_base()

    # -- Phase 1: Hypothesis -----------------------------------------------

    def _generate_hypothesis(self) -> dict[str, Any] | None:
        """Ask the agent to pick the next research dimension.

        Returns:
            A dict with ``dimension``, ``questions``, ``approach``, and
            ``rationale`` keys, or ``None`` if the call failed.
        """
        unexplored = [
            d for d in self.config.dimensions
            if d not in self.explored_dimensions
        ]

        prompt = _render(
            "hypothesis.md",
            topic=self.config.topic,
            knowledge_summary=self._kb_summary(),
            explored_dimensions=self._format_dimension_list(self.explored_dimensions),
            unexplored_dimensions=self._format_dimension_list(unexplored),
        )

        hypo_backend = self.strategy.get_hypothesis_backend()
        resp = self._call_with(hypo_backend, prompt, max_turns=3)

        if resp.is_error or not resp.text:
            return None

        self._track_usage(resp, hypo_backend.name)

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

    # -- Phase 2: Execute --------------------------------------------------

    def _execute_research(
        self, dimension: str, questions: list[str], approach: str
    ) -> str:
        """Run a research agent on the given dimension.

        Delegates to the active strategy, which may run one or multiple
        backends in parallel/serial.

        Returns:
            Markdown findings text, or an empty string on failure.
        """
        formatted_questions = "\n".join(f"- {q}" for q in questions) if questions else "- Explore broadly"

        prompt = _render(
            "research.md",
            topic=self.config.topic,
            dimension=dimension,
            questions=formatted_questions,
            approach=approach or "Use web search and official documentation",
            knowledge_summary=self._kb_summary(),
        )

        # Pass dimension for specialist routing
        kwargs: dict[str, Any] = {}
        if hasattr(self.strategy, 'route_dimension'):
            kwargs["dimension"] = dimension

        result = self.strategy.execute_research(
            prompt,
            self._invoke_for_strategy,
            allowed_tools=self.config.execution.allowed_tools,
            max_turns=self.config.execution.max_turns,
            timeout=self.config.execution.timeout_seconds,
            **kwargs,
        )

        self._track_cost(result.cost_usd, result.backend_name)

        if not result.findings:
            log.error("Research call failed.")
            return ""

        # Post-research phase (e.g. adversarial critique)
        critique = self.strategy.post_research(
            result.findings, self._invoke_for_strategy,
            timeout=self.config.execution.timeout_seconds,
        )
        if critique:
            self._track_cost(critique.cost_usd, critique.backend_name)
            # Append critique as context for the judge
            result.findings += (
                f"\n\n---\n\n## Peer Review ({critique.backend_name})\n\n"
                f"{critique.critique}"
            )

        return result.findings

    # -- Phase 3: Score ----------------------------------------------------

    def _score(self, dimension: str, findings: str) -> IterationScore:
        """Score findings using heuristics and an LLM judge.

        Returns:
            An ``IterationScore`` with coverage, quality, and combined total.
        """
        coverage = heuristic_score(findings, self.config, self.explored_dimensions)

        quality = 50.0  # fallback if judge fails
        judge_raw: dict[str, Any] = {}

        try:
            prompt = _render(
                "evaluate.md",
                topic=self.config.topic,
                dimension=dimension,
                findings=findings[:_MAX_FINDINGS_CHARS],
                knowledge_summary=self._kb_summary(),
            )

            judge_backend = self.strategy.get_judge_backend()
            resp = self._call_with(judge_backend, prompt, max_turns=3)
            self._track_usage(resp, judge_backend.name)

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

    # -- Phase 4: Keep / Merge ---------------------------------------------

    def _merge_findings(
        self, dimension: str, findings: str, score: IterationScore
    ) -> None:
        """Merge kept findings into the knowledge base and mark the dimension explored."""
        if dimension not in self.explored_dimensions:
            self.explored_dimensions.append(dimension)

        header = f"\n\n## {dimension}\n\n"
        self.knowledge_base += header + findings
        self.kb_path.write_text(self.knowledge_base, encoding="utf-8")

        for gap in score.gaps:
            if gap not in self.explored_dimensions and gap not in self.config.dimensions:
                log.info("New dimension discovered: %s", gap)

    def _maybe_exhaust_dimension(self, dimension: str) -> None:
        """Mark a dimension as explored if it has reached max attempts."""
        if self._dimension_attempts.get(dimension, 0) >= self.MAX_ATTEMPTS_PER_DIMENSION:
            if dimension not in self.explored_dimensions:
                self.explored_dimensions.append(dimension)
                log.info(
                    "Dimension exhausted after %d attempts, moving on: %s",
                    self.MAX_ATTEMPTS_PER_DIMENSION,
                    dimension,
                )

    # -- Phase 5: Log & Save -----------------------------------------------

    def _save_iteration(
        self,
        dimension: str,
        findings: str,
        score: IterationScore,
        kept: bool,
    ) -> None:
        """Write the iteration's findings to a numbered markdown file."""
        filename = f"iter_{self.iteration:03d}.md"
        path = self.iterations_dir / filename

        content = (
            f"# Iteration {self.iteration:03d} — {dimension}\n\n"
            f"**Status:** {'keep' if kept else 'discard'}  \n"
            f"**Scores:** coverage={score.coverage}, quality={score.quality}, "
            f"total={score.total}  \n"
            f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}  \n\n"
            f"---\n\n{findings}\n"
        )
        path.write_text(content, encoding="utf-8")

    def _log_result(
        self,
        dimension: str,
        score: IterationScore,
        hypothesis: str,
        *,
        status: str,
    ) -> None:
        """Append a row to results.tsv for this iteration."""
        row = {
            "iteration": f"{self.iteration:03d}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "dimension": dimension,
            "coverage_score": f"{score.coverage:.1f}",
            "quality_score": f"{score.quality:.1f}",
            "total_score": f"{score.total:.1f}",
            "status": status,
            "hypothesis": hypothesis[:120],
            "cumulative_cost_usd": f"{self.total_cost:.3f}",
            "cumulative_input_tokens": str(self.total_input_tokens),
            "cumulative_output_tokens": str(self.total_output_tokens),
        }
        self.results.append(row)

        with open(self.results_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()), delimiter="\t")
            writer.writerow(row)

    def _write_tsv_header(self) -> None:
        """Write the header row to a new results.tsv file."""
        fields = [
            "iteration",
            "timestamp",
            "dimension",
            "coverage_score",
            "quality_score",
            "total_score",
            "status",
            "hypothesis",
            "cumulative_cost_usd",
            "cumulative_input_tokens",
            "cumulative_output_tokens",
        ]
        with open(self.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
            writer.writeheader()

    # -- Compression -------------------------------------------------------

    def _compress_knowledge_base(self) -> None:
        """Distill the knowledge base if it exceeds ``KB_MAX_WORDS``."""
        word_count = len(self.knowledge_base.split())
        if word_count <= KB_MAX_WORDS:
            return

        log.info(
            "Compressing knowledge base (%d words -> target %d)...",
            word_count,
            KB_MAX_WORDS,
        )

        prompt = (
            "Distill the following research findings into a concise summary. "
            "Preserve all key facts, numbers, comparisons, and trade-offs. "
            "Remove redundancy and filler. Target length: ~3000 words.\n\n"
            f"{self.knowledge_base}"
        )

        compress_backend = self.strategy.get_compress_backend()
        resp = self._call_with(compress_backend, prompt, max_turns=3, timeout=120)
        self._track_usage(resp, compress_backend.name)

        if not resp.is_error and resp.text and len(resp.text) > 200:
            self.knowledge_base = resp.text
            self.kb_path.write_text(self.knowledge_base, encoding="utf-8")
            log.info("Knowledge base compressed to %d words.", len(resp.text.split()))

    # -- Synthesis ---------------------------------------------------------

    def _generate_synthesis(self) -> None:
        """Generate a final synthesis report from the accumulated knowledge base."""
        if not self.knowledge_base:
            log.info("No knowledge base to synthesize.")
            return

        results_summary = self._format_results_table()

        prompt = _render(
            "synthesize.md",
            topic=self.config.topic,
            knowledge_base=self.knowledge_base,
            results_summary=results_summary,
        )

        log.info("Generating final synthesis report...")
        synth_backend = self.strategy.get_synthesize_backend()
        resp = self._call_with(synth_backend, prompt, max_turns=5)
        self._track_usage(resp, synth_backend.name)

        if not resp.is_error and resp.text:
            self.synthesis_path.write_text(resp.text, encoding="utf-8")
            log.info("Synthesis saved to %s", self.synthesis_path)

    # -- Helpers -----------------------------------------------------------

    def _kb_summary(self) -> str:
        """Return a bounded summary of the knowledge base for prompt context."""
        if not self.knowledge_base:
            return "(No prior findings yet — this is the first iteration.)"
        words = self.knowledge_base.split()
        if len(words) <= KB_MAX_WORDS:
            return self.knowledge_base
        return " ".join(words[:KB_MAX_WORDS]) + "\n\n[... truncated for brevity]"

    def _format_dimension_list(self, dims: list[str]) -> str:
        """Format a list of dimensions as a markdown bullet list."""
        if not dims:
            return "(none)"
        return "\n".join(f"- {d}" for d in dims)

    def _format_results_table(self) -> str:
        """Format the results log as a markdown table for synthesis prompts."""
        if not self.results:
            return "(no results yet)"
        lines = ["| Iter | Dimension | Score | Status |", "|------|-----------|-------|--------|"]
        for r in self.results:
            lines.append(
                f"| {r.get('iteration', '?')} "
                f"| {r.get('dimension', '?')[:40]} "
                f"| {r.get('total_score', '?')} "
                f"| {r.get('status', '?')} |"
            )
        return "\n".join(lines)

    def _print_summary(self) -> None:
        """Print a session summary to stdout."""
        print("\n" + "=" * 60)
        print("  AUTORESEARCH SESSION COMPLETE")
        print("=" * 60)
        print(f"  Strategy:    {self.strategy.describe()}")
        print(f"  Topic:       {self.config.topic}")
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
        print(f"  Results:     {self.results_path}")
        if self.synthesis_path.exists():
            print(f"  Synthesis:   {self.synthesis_path}")
        print("=" * 60)
