"""Autonomous research loop powered by Claude Code agents."""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import ResearchConfig
from .scorer import (
    JUDGE_SCHEMA,
    IterationScore,
    combine_scores,
    heuristic_score,
    parse_judge_response,
    quality_score_from_judge,
)

log = logging.getLogger("autoresearch")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
HEURISTIC_WEIGHT = 0.4
JUDGE_WEIGHT = 0.6
KB_MAX_WORDS = 4000
RATE_LIMIT_BACKOFF_SECONDS = 120  # wait 2 min when rate limited
RATE_LIMIT_WARN_THRESHOLD = 0.80  # slow down above 80% utilization
RATE_LIMIT_COOLDOWN_SECONDS = 30  # pause between iterations when nearing limit


# ---------------------------------------------------------------------------
# Rate limit detection
# ---------------------------------------------------------------------------

def _check_rate_limit(stdout: str) -> int:
    """Parse Claude CLI JSON output for rate limit events. Return seconds to wait."""
    if not stdout:
        return 0
    try:
        payload = json.loads(stdout)
        events = payload if isinstance(payload, list) else [payload]
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("type") == "rate_limit_event":
                info = event.get("rate_limit_info", {})
                utilization = info.get("utilization", 0)
                if utilization >= 0.90:
                    return RATE_LIMIT_BACKOFF_SECONDS
                if utilization >= RATE_LIMIT_WARN_THRESHOLD:
                    return RATE_LIMIT_COOLDOWN_SECONDS
    except (json.JSONDecodeError, TypeError):
        pass
    return 0


def _extract_rate_limit_utilization(stdout: str) -> float:
    """Extract rate limit utilization from response for throttling."""
    if not stdout:
        return 0.0
    try:
        payload = json.loads(stdout)
        events = payload if isinstance(payload, list) else [payload]
        for event in events:
            if isinstance(event, dict) and event.get("type") == "rate_limit_event":
                return event.get("rate_limit_info", {}).get("utilization", 0.0)
    except (json.JSONDecodeError, TypeError):
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Claude CLI interface
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaudeResponse:
    text: str
    cost_usd: float
    is_error: bool


def call_claude(
    prompt: str,
    *,
    allowed_tools: str = "",
    max_turns: int = 10,
    timeout: int = 300,
    json_schema: dict | None = None,
) -> ClaudeResponse:
    """Invoke Claude Code CLI in headless mode and return the result."""
    cmd: list[str] = ["claude", "-p", prompt, "--output-format", "json"]

    if allowed_tools:
        cmd.extend(["--allowedTools", allowed_tools])
    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])
    if json_schema:
        cmd.extend(["--json-schema", json.dumps(json_schema)])

    log.debug("Claude CLI: %s", " ".join(cmd[:6]) + " ...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        log.warning("Claude CLI timed out after %ds.", timeout)
        return ClaudeResponse(text="", cost_usd=0.0, is_error=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Check for rate limiting in stdout (JSON may still have events)
        rate_wait = _check_rate_limit(result.stdout)
        if rate_wait > 0:
            log.warning("Rate limited. Waiting %d seconds before next call...", rate_wait)
            time.sleep(rate_wait)
        else:
            log.error("Claude CLI failed (rc=%d): %s", result.returncode, stderr)
        return ClaudeResponse(text="", cost_usd=0.0, is_error=True)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ClaudeResponse(text=result.stdout, cost_usd=0.0, is_error=False)

    # The JSON output is either a dict with "result" or an array of events.
    if isinstance(payload, dict):
        return ClaudeResponse(
            text=payload.get("result", ""),
            cost_usd=payload.get("cost_usd", 0.0),
            is_error=payload.get("is_error", False),
        )

    # Array format: find the last "result" event.
    text = ""
    cost = 0.0
    for event in reversed(payload):
        if isinstance(event, dict) and event.get("type") == "result":
            text = event.get("result", "")
            cost = event.get("total_cost_usd", event.get("cost_usd", 0.0))
            break

    # Proactive throttling on successful responses
    utilization = _extract_rate_limit_utilization(result.stdout)
    if utilization >= RATE_LIMIT_WARN_THRESHOLD:
        wait = RATE_LIMIT_BACKOFF_SECONDS if utilization >= 0.90 else RATE_LIMIT_COOLDOWN_SECONDS
        log.info("Rate limit at %.0f%%, cooling down %ds...", utilization * 100, wait)
        time.sleep(wait)

    return ClaudeResponse(text=text, cost_usd=cost, is_error=False)


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def _load_template(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


def _render(template_name: str, **kwargs: str) -> str:
    tmpl = _load_template(template_name)
    return tmpl.format(**kwargs)


# ---------------------------------------------------------------------------
# AutoResearcher
# ---------------------------------------------------------------------------

class AutoResearcher:
    """Autonomous research loop.

    Mirrors Karpathy's autoresearch pattern:
    Hypothesis -> Execute -> Measure -> Evaluate -> Keep/Revert -> Log -> Repeat
    """

    def __init__(self, config: ResearchConfig, output_dir: Path) -> None:
        self.config = config
        self.output_dir = output_dir
        self.iterations_dir = output_dir / "iterations"
        self.results_path = output_dir / "results.tsv"
        self.kb_path = output_dir / "knowledge_base.md"
        self.synthesis_path = output_dir / "synthesis.md"

        self.iteration = 0
        self.best_score = 0.0
        self.knowledge_base = ""
        self.explored_dimensions: list[str] = []
        self.total_cost = 0.0
        self.results: list[dict[str, str]] = []
        self._dimension_attempts: dict[str, int] = {}

    MAX_ATTEMPTS_PER_DIMENSION = 3

    # -- Public API --------------------------------------------------------

    def run(self) -> None:
        """Start the infinite research loop. Ctrl+C triggers synthesis."""
        self._setup()
        self._resume()

        log.info(
            "Starting autoresearch: %s (%d dimensions configured)",
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
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.iterations_dir.mkdir(exist_ok=True)

        if not self.results_path.exists():
            self._write_tsv_header()

    def _resume(self) -> None:
        """Rebuild state from existing iteration files."""
        existing = sorted(self.iterations_dir.glob("iter_*.md"))
        if not existing:
            return

        log.info("Resuming from %d existing iterations.", len(existing))

        # Reload results.tsv
        if self.results_path.exists():
            with open(self.results_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    self.results.append(dict(row))
                    dim = row.get("dimension", "")
                    status = row.get("status", "")

                    # Track attempts per dimension
                    if dim:
                        self._dimension_attempts[dim] = self._dimension_attempts.get(dim, 0) + 1

                    if status == "keep":
                        score = float(row.get("total_score", 0))
                        if score > self.best_score:
                            self.best_score = score
                        if dim and dim not in self.explored_dimensions:
                            self.explored_dimensions.append(dim)

                    # Mark exhausted dimensions as explored so we move on
                    if dim and self._dimension_attempts.get(dim, 0) >= self.MAX_ATTEMPTS_PER_DIMENSION:
                        if dim not in self.explored_dimensions:
                            self.explored_dimensions.append(dim)

        # Reload knowledge base
        if self.kb_path.exists():
            self.knowledge_base = self.kb_path.read_text(encoding="utf-8")

        self.iteration = len(existing)

    # -- Core loop ---------------------------------------------------------

    def _run_iteration(self) -> None:
        self.iteration += 1
        log.info("=" * 60)
        log.info("Iteration %03d", self.iteration)
        log.info("=" * 60)

        # 1. Hypothesis
        hypothesis = self._generate_hypothesis()
        if not hypothesis:
            log.warning("Hypothesis generation failed, retrying next iteration.")
            return

        dimension = hypothesis.get("dimension", "unknown")
        questions = hypothesis.get("questions", [])
        approach = hypothesis.get("approach", "")

        # Track attempts per dimension
        self._dimension_attempts[dimension] = self._dimension_attempts.get(dimension, 0) + 1
        attempts = self._dimension_attempts[dimension]
        log.info("Dimension: %s (attempt %d/%d)", dimension, attempts, self.MAX_ATTEMPTS_PER_DIMENSION)

        # 2. Execute research
        findings = self._execute_research(dimension, questions, approach)
        if not findings:
            log.warning("Research execution returned empty, logging crash.")
            self._log_result(dimension, IterationScore(), "", status="crash")
            self._maybe_exhaust_dimension(dimension)
            return

        # 3. Score
        score = self._score(dimension, findings)
        log.info(
            "Scores — coverage: %.1f, quality: %.1f, total: %.1f (best: %.1f)",
            score.coverage,
            score.quality,
            score.total,
            self.best_score,
        )

        # 4. Decide: keep or discard
        kept = score.total > self.best_score
        if kept:
            self.best_score = score.total
            self._merge_findings(dimension, findings, score)
            log.info("KEEP — merged into knowledge base.")
        else:
            log.info("DISCARD — findings saved but not merged.")
            self._maybe_exhaust_dimension(dimension)

        # 5. Save iteration file + log
        self._save_iteration(dimension, findings, score, kept)
        self._log_result(
            dimension,
            score,
            hypothesis.get("rationale", ""),
            status="keep" if kept else "discard",
        )

        # 6. Periodic compression
        if self.iteration % self.config.execution.compress_every == 0:
            self._compress_knowledge_base()

    # -- Phase 1: Hypothesis -----------------------------------------------

    def _generate_hypothesis(self) -> dict | None:
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

        resp = call_claude(
            prompt,
            max_turns=3,
            timeout=self.config.execution.timeout_seconds,
        )

        if resp.is_error or not resp.text:
            return None

        self.total_cost += resp.cost_usd

        try:
            return json.loads(resp.text)
        except json.JSONDecodeError:
            # Try extracting JSON from within the text
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
        formatted_questions = "\n".join(f"- {q}" for q in questions) if questions else "- Explore broadly"

        prompt = _render(
            "research.md",
            topic=self.config.topic,
            dimension=dimension,
            questions=formatted_questions,
            approach=approach or "Use web search and official documentation",
            knowledge_summary=self._kb_summary(),
        )

        resp = call_claude(
            prompt,
            allowed_tools=self.config.execution.allowed_tools,
            max_turns=self.config.execution.max_turns,
            timeout=self.config.execution.timeout_seconds,
        )

        self.total_cost += resp.cost_usd

        if resp.is_error:
            log.error("Research call failed.")
            return ""

        return resp.text

    # -- Phase 3: Score ----------------------------------------------------

    def _score(self, dimension: str, findings: str) -> IterationScore:
        # Heuristic
        coverage = heuristic_score(findings, self.config, self.explored_dimensions)

        # LLM judge
        quality = 50.0  # fallback
        judge_raw: dict = {}

        try:
            prompt = _render(
                "evaluate.md",
                topic=self.config.topic,
                dimension=dimension,
                findings=findings[:8000],  # cap to avoid token blowup
                knowledge_summary=self._kb_summary(),
            )

            resp = call_claude(
                prompt,
                max_turns=3,
                timeout=self.config.execution.timeout_seconds,
            )
            self.total_cost += resp.cost_usd

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
        if dimension not in self.explored_dimensions:
            self.explored_dimensions.append(dimension)

        header = f"\n\n## {dimension}\n\n"
        self.knowledge_base += header + findings
        self.kb_path.write_text(self.knowledge_base, encoding="utf-8")

        # Register discovered dimensions from gaps
        for gap in score.gaps:
            if gap not in self.explored_dimensions and gap not in [
                d for d in self.config.dimensions
            ]:
                log.info("New dimension discovered: %s", gap)

    def _maybe_exhaust_dimension(self, dimension: str) -> None:
        """Mark a dimension as explored if max attempts reached."""
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
        row = {
            "iteration": f"{self.iteration:03d}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "dimension": dimension,
            "coverage_score": f"{score.coverage:.1f}",
            "quality_score": f"{score.quality:.1f}",
            "total_score": f"{score.total:.1f}",
            "status": status,
            "hypothesis": hypothesis[:120],
            "cost_usd": f"{self.total_cost:.3f}",
        }
        self.results.append(row)

        with open(self.results_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()), delimiter="\t")
            writer.writerow(row)

    def _write_tsv_header(self) -> None:
        fields = [
            "iteration",
            "timestamp",
            "dimension",
            "coverage_score",
            "quality_score",
            "total_score",
            "status",
            "hypothesis",
            "cost_usd",
        ]
        with open(self.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
            writer.writeheader()

    # -- Compression -------------------------------------------------------

    def _compress_knowledge_base(self) -> None:
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

        resp = call_claude(prompt, max_turns=3, timeout=120)
        self.total_cost += resp.cost_usd

        if not resp.is_error and resp.text and len(resp.text) > 200:
            self.knowledge_base = resp.text
            self.kb_path.write_text(self.knowledge_base, encoding="utf-8")
            log.info("Knowledge base compressed to %d words.", len(resp.text.split()))

    # -- Synthesis ---------------------------------------------------------

    def _generate_synthesis(self) -> None:
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
        resp = call_claude(
            prompt,
            max_turns=5,
            timeout=self.config.execution.timeout_seconds,
        )
        self.total_cost += resp.cost_usd

        if not resp.is_error and resp.text:
            self.synthesis_path.write_text(resp.text, encoding="utf-8")
            log.info("Synthesis saved to %s", self.synthesis_path)

    # -- Helpers -----------------------------------------------------------

    def _kb_summary(self) -> str:
        """Return a bounded summary of the knowledge base for prompt injection."""
        if not self.knowledge_base:
            return "(No prior findings yet — this is the first iteration.)"
        words = self.knowledge_base.split()
        if len(words) <= KB_MAX_WORDS:
            return self.knowledge_base
        return " ".join(words[:KB_MAX_WORDS]) + "\n\n[... truncated for brevity]"

    def _format_dimension_list(self, dims: list[str]) -> str:
        if not dims:
            return "(none)"
        return "\n".join(f"- {d}" for d in dims)

    def _format_results_table(self) -> str:
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
        print("\n" + "=" * 60)
        print("  AUTORESEARCH SESSION COMPLETE")
        print("=" * 60)
        print(f"  Topic:       {self.config.topic}")
        print(f"  Iterations:  {self.iteration}")
        print(f"  Best score:  {self.best_score:.1f}")
        print(f"  Total cost:  ${self.total_cost:.3f}")
        print(f"  Dimensions:  {len(self.explored_dimensions)} explored")
        print(f"  Results:     {self.results_path}")
        if self.synthesis_path.exists():
            print(f"  Synthesis:   {self.synthesis_path}")
        print("=" * 60)
