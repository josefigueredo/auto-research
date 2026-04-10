"""Autonomous research loop powered by AI coding agent CLIs.

Implements the Karpathy autoresearch pattern: an infinite loop of
hypothesis generation, research execution, scoring, and keep/discard
decisions.  Each iteration invokes a configurable CLI backend in
headless mode.
"""

from __future__ import annotations

import csv
import importlib.metadata
import json
import logging
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .backends import CLAUDE_SHORTNAMES, AgentResponse, Backend, CallOptions, get_backends
from .config import ResearchConfig
from .provenance import (
    detect_claim_conflicts,
    extract_citations,
    extract_claims,
    link_claims_to_citations,
    score_research_rubric,
    summarize_evidence_quality,
)
from .prompts import render as _render
from .reporting import render_html_report
from .scorer import (
    IterationScore,
    _MAX_FINDINGS_CHARS,
    combine_scores,
    heuristic_score,
    parse_judge_response,
    quality_score_from_judge,
)
from .strategy import ResearchCandidate, Strategy, get_strategy

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
        self.report_html_path = output_dir / "report.html"

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

    def _track_candidate_usage(self, candidate: ResearchCandidate) -> None:
        """Record usage for a strategy-produced research candidate."""
        self._track_usage(
            AgentResponse(
                text=candidate.findings,
                cost_usd=candidate.cost_usd,
                is_error=False,
                input_tokens=candidate.input_tokens,
                output_tokens=candidate.output_tokens,
            ),
            candidate.backend_name,
        )

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
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.iterations_dir.mkdir(exist_ok=True)
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()

        if not self.results_path.exists():
            self._write_tsv_header()
        self._write_methods()
        self._write_run_manifest()

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

                    gaps_raw = row.get("discovered_gaps", "")
                    if gaps_raw:
                        try:
                            gaps = json.loads(gaps_raw)
                        except (json.JSONDecodeError, TypeError):
                            gaps = []
                        for gap in gaps:
                            if (
                                gap
                                and gap not in self.explored_dimensions
                                and gap not in self.config.dimensions
                                and gap not in self.discovered_dimensions
                            ):
                                self.discovered_dimensions.append(gap)

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
            d for d in [*self.config.dimensions, *self.discovered_dimensions]
            if d not in self.explored_dimensions
        ]

        prompt = _render(
            "hypothesis.md",
            topic=self.config.topic,
            methodology=self._methodology_summary(),
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
            methodology=self._methodology_summary(),
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

        if result.candidates is not None:
            for candidate in result.candidates:
                self._track_candidate_usage(candidate)
        else:
            self._track_cost(result.cost_usd, result.backend_name)

        findings = result.findings
        if result.candidates and len(result.candidates) > 1:
            findings = self._select_candidate_findings(dimension, result.candidates)
        elif result.candidates and len(result.candidates) == 1 and not findings:
            findings = result.candidates[0].findings

        if not findings:
            log.error("Research call failed.")
            return ""

        # Post-research phase (e.g. adversarial critique)
        critique = self.strategy.post_research(
            findings, self._invoke_for_strategy,
            timeout=self.config.execution.timeout_seconds,
        )
        if critique:
            self._track_cost(critique.cost_usd, critique.backend_name)
            # Append critique as context for the judge
            findings += (
                f"\n\n---\n\n## Peer Review ({critique.backend_name})\n\n"
                f"{critique.critique}"
            )

        return findings

    def _select_candidate_findings(
        self,
        dimension: str,
        candidates: list[ResearchCandidate],
    ) -> str:
        """Select or merge the best findings from multiple backend candidates."""
        if not candidates:
            return ""

        ranked = sorted(
            candidates,
            key=lambda c: heuristic_score(c.findings, self.config, self.explored_dimensions),
            reverse=True,
        )
        merge_mode = self.config.execution.strategy_config.merge_mode
        threshold = self.config.execution.strategy_config.merge_threshold

        if merge_mode == "union":
            selected: list[tuple[ResearchCandidate, IterationScore]] = []
            for candidate in ranked:
                score = self._score(dimension, candidate.findings)
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
            score = self._score(dimension, candidate.findings)
            if score.total > best_score:
                best_candidate = candidate
                best_score = score.total

        log.info(
            "Selected %s from %d candidates for dimension '%s' (score %.1f).",
            best_candidate.backend_name,
            len(candidates),
            dimension,
            best_score,
        )
        return best_candidate.findings

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
                methodology=self._methodology_summary(),
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
            if (
                gap not in self.explored_dimensions
                and gap not in self.config.dimensions
                and gap not in self.discovered_dimensions
            ):
                self.discovered_dimensions.append(gap)
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
        self._collect_provenance(findings, scope=f"iteration-{self.iteration:03d}", dimension=dimension)

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
            "discovered_gaps": json.dumps(score.gaps),
            "cumulative_cost_usd": f"{self.total_cost:.3f}",
            "cumulative_input_tokens": str(self.total_input_tokens),
            "cumulative_output_tokens": str(self.total_output_tokens),
        }
        self.results.append(row)

        with open(self.results_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()), delimiter="\t", quoting=csv.QUOTE_MINIMAL)
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
            "discovered_gaps",
            "cumulative_cost_usd",
            "cumulative_input_tokens",
            "cumulative_output_tokens",
        ]
        with open(self.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
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
            methodology=self._methodology_summary(),
            knowledge_base=self.knowledge_base,
            results_summary=results_summary,
        )

        log.info("Generating final synthesis report...")
        synth_backend = self.strategy.get_synthesize_backend()
        resp = self._call_with(synth_backend, prompt, max_turns=5)
        self._track_usage(resp, synth_backend.name)

        if not resp.is_error and resp.text:
            self.synthesis_path.write_text(resp.text, encoding="utf-8")
            self._collect_provenance(resp.text, scope="synthesis")
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

    def _finalize_run_artifacts(self) -> None:
        """Write final manifest and metrics artifacts."""
        self._run_completed_at = datetime.now(timezone.utc).isoformat()
        self._write_run_manifest()
        self._write_metrics()
        self._write_provenance_artifacts()
        self._write_html_report()

    def _write_run_manifest(self) -> None:
        """Write a machine-readable manifest for reproducibility."""
        payload = {
            "project": {
                "name": "autoresearch",
                "version": self._package_version(),
            },
            "run": {
                "status": self._run_status,
                "started_at": self._run_started_at,
                "completed_at": self._run_completed_at,
                "resume_requested": self.resume,
                "output_dir": str(self.output_dir.resolve()),
            },
            "config": {
                "path": str(self.config_path.resolve()) if self.config_path else None,
                "snapshot": asdict(self.config),
            },
            "strategy": {
                "name": self.config.execution.strategy,
                "description": self.strategy.describe(),
            },
              "evaluation": {
                  "benchmark_id": self.config.evaluation.benchmark_id,
                  "run_baselines": self.config.evaluation.run_baselines,
              },
              "reporting": {
                  "export_html": self.config.reporting.export_html,
                  "report_title": self.config.reporting.report_title,
              },
              "environment": {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "git_commit": self._git_commit(),
            },
            "backends": {
                name: {
                    "cli": backend.cli_executable(),
                    "version": self._cli_version(backend.cli_executable()),
                }
                for name, backend in self.backends.items()
            },
        }
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_metrics(self) -> None:
        """Write machine-readable run metrics."""
        payload = {
            "run_status": self._run_status,
            "benchmark_id": self.config.evaluation.benchmark_id,
            "iterations": self.iteration,
            "best_score": self.best_score,
            "explored_dimensions_count": len(self.explored_dimensions),
            "explored_dimensions": self.explored_dimensions,
            "discovered_dimensions": self.discovered_dimensions,
            "total_cost_usd": self.total_cost,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "per_backend_costs": self.per_backend_costs,
            "per_backend_tokens": self.per_backend_tokens,
            "results": self.results,
        }
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
        rubric = score_research_rubric(self._claims, self._citations, evidence_links, contradictions)
        self.evidence_links_path.write_text(json.dumps(evidence_links, indent=2), encoding="utf-8")
        self.evidence_quality_path.write_text(json.dumps(evidence_quality, indent=2), encoding="utf-8")
        self.rubric_path.write_text(json.dumps(rubric, indent=2), encoding="utf-8")
        self.contradictions_path.write_text(json.dumps(contradictions, indent=2), encoding="utf-8")
        self._write_evaluation_artifact(evidence_quality, rubric)

    def _generate_baseline(self) -> None:
        """Generate an optional single-pass baseline answer for comparison."""
        if not self.config.evaluation.run_baselines:
            return
        prompt = _render(
            "baseline.md",
            topic=self.config.topic,
            methodology=self._methodology_summary(),
        )
        baseline_backend = self.strategy.get_synthesize_backend()
        resp = self._call_with(baseline_backend, prompt, max_turns=3)
        self._track_usage(resp, baseline_backend.name)
        if not resp.is_error and resp.text:
            self.baseline_path.write_text(resp.text, encoding="utf-8")
            self._collect_provenance(resp.text, scope="baseline")

    def _write_evaluation_artifact(self, evidence_quality: dict[str, Any], rubric: dict[str, Any]) -> None:
        """Write optional evaluation summary comparing iterative output to a baseline."""
        if (
            not self.config.evaluation.run_baselines
            and not self.config.evaluation.benchmark_id
            and not self.config.evaluation.reference_runs
        ):
            return

        baseline_claims = [claim for claim in self._claims if claim.get("scope") == "baseline"]
        synthesis_claims = [claim for claim in self._claims if claim.get("scope") == "synthesis"]
        baseline_citations = [citation for citation in self._citations if citation.get("scope") == "baseline"]
        synthesis_citations = [citation for citation in self._citations if citation.get("scope") == "synthesis"]
        benchmark_summary = self._benchmark_summary()
        reference_comparison = self._reference_run_comparison()

        payload = {
            "benchmark_id": self.config.evaluation.benchmark_id,
            "baseline_generated": self.baseline_path.exists(),
            "iterative_synthesis": {
                "claims_count": len(synthesis_claims),
                "citations_count": len(synthesis_citations),
            },
            "baseline": {
                "claims_count": len(baseline_claims),
                "citations_count": len(baseline_citations),
            },
            "evidence_quality": evidence_quality,
            "rubric": rubric,
            "benchmark": benchmark_summary,
            "reference_comparison": reference_comparison,
            "summary": {
                "iterative_has_more_claims_than_baseline": len(synthesis_claims) > len(baseline_claims),
                "iterative_has_more_citations_than_baseline": len(synthesis_citations) > len(baseline_citations),
                "benchmark_expectations_satisfied": benchmark_summary.get("all_expectations_satisfied", True),
                "reference_runs_compared": reference_comparison.get("compared_runs_count", 0),
                "rubric_grade": rubric.get("grade", "insufficient"),
            },
        }
        self.evaluation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.comparison_path.write_text(json.dumps(reference_comparison, indent=2), encoding="utf-8")

    def _write_html_report(self) -> None:
        """Render a standalone HTML report when enabled."""
        if not self.config.reporting.export_html:
            return

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        metrics = json.loads(self.metrics_path.read_text(encoding="utf-8")) if self.metrics_path.exists() else {}
        evidence_quality = (
            json.loads(self.evidence_quality_path.read_text(encoding="utf-8"))
            if self.evidence_quality_path.exists()
            else {}
        )
        rubric = json.loads(self.rubric_path.read_text(encoding="utf-8")) if self.rubric_path.exists() else {}
        evaluation = (
            json.loads(self.evaluation_path.read_text(encoding="utf-8"))
            if self.evaluation_path.exists()
            else None
        )
        comparison = (
            json.loads(self.comparison_path.read_text(encoding="utf-8"))
            if self.comparison_path.exists()
            else None
        )
        methods_text = self.methods_path.read_text(encoding="utf-8") if self.methods_path.exists() else ""
        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        title = self.config.reporting.report_title or f"Autoresearch Report — {self.config.topic}"
        html = render_html_report(
            title=title,
            topic=self.config.topic,
            goal=self.config.goal,
            manifest=manifest,
            metrics=metrics,
            evidence_quality=evidence_quality,
            rubric=rubric,
            evaluation=evaluation,
            comparison=comparison,
            methods_text=methods_text,
            synthesis_text=synthesis_text,
        )
        self.report_html_path.write_text(html, encoding="utf-8")

    @staticmethod
    def _normalize_claim_text(text: str) -> str:
        """Normalize claim text for crude overlap comparisons."""
        return " ".join(text.lower().split())

    def _reference_run_comparison(self) -> dict[str, Any]:
        """Compare the current run to referenced prior outputs for consistency analysis."""
        if not self.config.evaluation.reference_runs:
            return {
                "compared_runs_count": 0,
                "runs": [],
                "summary": {
                    "average_dimension_overlap": 0.0,
                    "average_citation_overlap": 0.0,
                    "average_claim_overlap": 0.0,
                    "average_score_delta": 0.0,
                    "consistency_level": "not_available",
                },
            }

        current_dimensions = set(self.explored_dimensions)
        current_citations = {citation.get("url", "") for citation in self._citations if citation.get("url")}
        current_claims = {
            self._normalize_claim_text(claim.get("text", ""))
            for claim in self._claims
            if claim.get("scope") == "synthesis" and claim.get("text")
        }

        runs: list[dict[str, Any]] = []
        for raw_path in self.config.evaluation.reference_runs:
            ref_dir = Path(raw_path)
            metrics_path = ref_dir / "metrics.json"
            manifest_path = ref_dir / "run_manifest.json"
            claims_path = ref_dir / "claims.json"
            citations_path = ref_dir / "citations.json"
            if not metrics_path.exists():
                runs.append(
                    {
                        "path": str(ref_dir),
                        "status": "missing_metrics",
                    }
                )
                continue

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.exists()
                else {}
            )
            claims = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else []
            citations = json.loads(citations_path.read_text(encoding="utf-8")) if citations_path.exists() else []

            ref_dimensions = set(metrics.get("explored_dimensions", []))
            ref_citations = {citation.get("url", "") for citation in citations if citation.get("url")}
            ref_claims = {
                self._normalize_claim_text(claim.get("text", ""))
                for claim in claims
                if claim.get("scope") == "synthesis" and claim.get("text")
            }

            dimension_union = current_dimensions | ref_dimensions
            citation_union = current_citations | ref_citations
            claim_union = current_claims | ref_claims

            dimension_overlap = (
                len(current_dimensions & ref_dimensions) / len(dimension_union)
                if dimension_union
                else 1.0
            )
            citation_overlap = (
                len(current_citations & ref_citations) / len(citation_union)
                if citation_union
                else 1.0
            )
            claim_overlap = (
                len(current_claims & ref_claims) / len(claim_union)
                if claim_union
                else 1.0
            )

            runs.append(
                {
                    "path": str(ref_dir),
                    "status": "ok",
                    "strategy": manifest.get("strategy", {}).get("name", ""),
                    "benchmark_id": metrics.get("benchmark_id") or manifest.get("evaluation", {}).get("benchmark_id", ""),
                    "best_score": metrics.get("best_score", 0.0),
                    "score_delta": round(self.best_score - float(metrics.get("best_score", 0.0)), 2),
                    "dimension_overlap": round(dimension_overlap, 2),
                    "citation_overlap": round(citation_overlap, 2),
                    "claim_overlap": round(claim_overlap, 2),
                    "shared_dimensions": sorted(current_dimensions & ref_dimensions),
                }
            )

        successful = [run for run in runs if run.get("status") == "ok"]
        if not successful:
            return {
                "compared_runs_count": 0,
                "runs": runs,
                "summary": {
                    "average_dimension_overlap": 0.0,
                    "average_citation_overlap": 0.0,
                    "average_claim_overlap": 0.0,
                    "average_score_delta": 0.0,
                    "consistency_level": "not_available",
                },
            }

        avg_dimension = round(sum(run["dimension_overlap"] for run in successful) / len(successful), 2)
        avg_citation = round(sum(run["citation_overlap"] for run in successful) / len(successful), 2)
        avg_claim = round(sum(run["claim_overlap"] for run in successful) / len(successful), 2)
        avg_score_delta = round(sum(run["score_delta"] for run in successful) / len(successful), 2)
        consistency_signal = round((avg_dimension + avg_citation + avg_claim) / 3, 2)
        if consistency_signal >= 0.75:
            consistency_level = "high"
        elif consistency_signal >= 0.4:
            consistency_level = "medium"
        else:
            consistency_level = "low"

        return {
            "compared_runs_count": len(successful),
            "runs": runs,
            "summary": {
                "average_dimension_overlap": avg_dimension,
                "average_citation_overlap": avg_citation,
                "average_claim_overlap": avg_claim,
                "average_score_delta": avg_score_delta,
                "consistency_level": consistency_level,
            },
        }

    def _load_benchmark_definition(self) -> dict[str, Any]:
        """Load a bundled benchmark definition when ``benchmark_id`` maps to a YAML file."""
        benchmark_id = self.config.evaluation.benchmark_id.strip()
        if not benchmark_id:
            return {}

        benchmark_path = Path("benchmarks") / f"{benchmark_id}.yaml"
        if not benchmark_path.exists():
            return {}

        with benchmark_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return {
            "benchmark_id": raw.get("benchmark_id", benchmark_id),
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "expected_dimensions": list(raw.get("expected_dimensions", [])),
            "required_keywords": list(raw.get("required_keywords", [])),
        }

    def _benchmark_summary(self) -> dict[str, Any]:
        """Evaluate current run outputs against optional benchmark expectations."""
        benchmark_definition = self._load_benchmark_definition()
        expected_dimensions = (
            list(self.config.evaluation.expected_dimensions)
            or list(benchmark_definition.get("expected_dimensions", []))
        )
        required_keywords = (
            list(self.config.evaluation.required_keywords)
            or list(benchmark_definition.get("required_keywords", []))
        )
        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        knowledge_text = self.knowledge_base or ""
        searchable_text = f"{knowledge_text}\n\n{synthesis_text}".lower()

        covered_dimensions = [dim for dim in expected_dimensions if dim.lower() in searchable_text]
        matched_keywords = [kw for kw in required_keywords if kw.lower() in searchable_text]

        dimension_score = (
            len(covered_dimensions) / len(expected_dimensions) if expected_dimensions else 1.0
        )
        keyword_score = (
            len(matched_keywords) / len(required_keywords) if required_keywords else 1.0
        )
        all_expectations_satisfied = (
            len(covered_dimensions) == len(expected_dimensions)
            and len(matched_keywords) == len(required_keywords)
        )

        return {
            "benchmark_id": benchmark_definition.get("benchmark_id", self.config.evaluation.benchmark_id),
            "benchmark_title": benchmark_definition.get("title", ""),
            "benchmark_description": benchmark_definition.get("description", ""),
            "expected_dimensions": expected_dimensions,
            "covered_dimensions": covered_dimensions,
            "missing_dimensions": [dim for dim in expected_dimensions if dim not in covered_dimensions],
            "required_keywords": required_keywords,
            "matched_keywords": matched_keywords,
            "missing_keywords": [kw for kw in required_keywords if kw not in matched_keywords],
            "dimension_coverage_score": round(dimension_score, 2),
            "keyword_coverage_score": round(keyword_score, 2),
            "all_expectations_satisfied": all_expectations_satisfied,
        }

    @staticmethod
    def _git_commit() -> str | None:
        """Return the current git commit SHA if available."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    @staticmethod
    def _cli_version(executable: str) -> str | None:
        """Return a CLI version string when available."""
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    @staticmethod
    def _package_version() -> str | None:
        """Return the installed package version if available."""
        try:
            return importlib.metadata.version("autoresearch")
        except importlib.metadata.PackageNotFoundError:
            return None
