"""Multi-backend research strategies.

Each strategy defines how backends are assigned to research phases and how
results from parallel or serial execution are combined.

Strategies:
- **single** — One backend for everything (current default, backward compat).
- **ensemble** — Parallel research with blind judging by a different backend.
- **adversarial** — Research + critique + adjudication across backends.
- **parallel** — All backends research independently, best result wins.
- **serial** — Draft by one backend, refined by another.
- **specialist** — Route dimensions to the most suitable backend.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .backends import AgentResponse, Backend, CallOptions
from .config import BackendsConfig, StrategyConfig
from .prompts import render as _render

log = logging.getLogger("autoresearch")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class ResearchResult:
    """Output from a strategy's execute phase.

    Attributes:
        findings: Markdown findings text (may be merged from multiple backends).
        backend_name: Name of the backend that produced the result (or
            ``"merged"`` if multiple backends contributed).
        cost_usd: Total cost across all backend calls in this phase.
        per_backend_costs: Cost breakdown by backend name.
    """

    findings: str
    backend_name: str
    cost_usd: float
    per_backend_costs: dict[str, float]


@dataclass
class CritiqueResult:
    """Output from an adversarial critique phase.

    Attributes:
        critique: The critique text identifying errors, gaps, unsupported claims.
        backend_name: Name of the backend that produced the critique.
        cost_usd: Cost of the critique call.
    """

    critique: str
    backend_name: str
    cost_usd: float


# ---------------------------------------------------------------------------
# Callback protocol — used by strategies to invoke backends via the
# orchestrator (which owns prompt rendering, config, and cost tracking).
# ---------------------------------------------------------------------------

class InvokeCallback:
    """Protocol for the orchestrator to provide backend invocation to strategies.

    Strategies call ``invoke(backend, prompt, **kwargs)`` rather than calling
    ``backend.invoke()`` directly, so the orchestrator can track costs, apply
    config defaults, and log consistently.
    """

    def __call__(
        self,
        backend: Backend,
        prompt: str,
        *,
        allowed_tools: str = "",
        max_turns: int = 0,
        timeout: int = 0,
    ) -> AgentResponse:
        ...


# ---------------------------------------------------------------------------
# Abstract strategy
# ---------------------------------------------------------------------------

class Strategy(ABC):
    """Base class for multi-backend research strategies."""

    name: str

    def __init__(
        self,
        backends_config: BackendsConfig,
        strategy_config: StrategyConfig,
        backends: dict[str, Backend],
    ) -> None:
        self.backends_config = backends_config
        self.strategy_config = strategy_config
        self.backends = backends

        # Validate all referenced backend names exist in the instantiated set.
        for role_name in [
            backends_config.primary,
            *backends_config.research,
            backends_config.judge,
            backends_config.utility,
        ]:
            if role_name and role_name not in backends:
                raise ValueError(
                    f"Backend '{role_name}' referenced in config but not instantiated. "
                    f"Available: {', '.join(backends)}"
                )

    @property
    def primary(self) -> Backend:
        return self.backends[self.backends_config.primary]

    @property
    def judge(self) -> Backend:
        return self.backends[self.backends_config.judge_or_primary]

    @property
    def utility(self) -> Backend:
        return self.backends[self.backends_config.utility_or_primary]

    @property
    def research_backends(self) -> list[Backend]:
        return [self.backends[n] for n in self.backends_config.research]

    def get_hypothesis_backend(self) -> Backend:
        """Backend for hypothesis generation.  Default: primary."""
        return self.primary

    def get_judge_backend(self) -> Backend:
        """Backend for scoring/evaluation.  Default: judge (or primary)."""
        return self.judge

    def get_compress_backend(self) -> Backend:
        """Backend for knowledge base compression.  Default: utility (or primary)."""
        return self.utility

    def get_synthesize_backend(self) -> Backend:
        """Backend for final synthesis.  Default: primary."""
        return self.primary

    @abstractmethod
    def execute_research(
        self,
        prompt: str,
        invoke: InvokeCallback,
        *,
        allowed_tools: str = "",
        max_turns: int = 10,
        timeout: int = 600,
    ) -> ResearchResult:
        """Execute the research phase of an iteration.

        Args:
            prompt: The rendered research prompt.
            invoke: Callback to invoke a backend (handles config defaults).
            allowed_tools: Tools available to the research agent.
            max_turns: Maximum agent turns per call.
            timeout: Per-call timeout in seconds.

        Returns:
            A ``ResearchResult`` with findings and cost breakdown.
        """

    def post_research(
        self,
        findings: str,
        invoke: InvokeCallback,
        *,
        timeout: int = 600,
    ) -> CritiqueResult | None:
        """Optional post-research phase (e.g. adversarial critique).

        Default implementation returns ``None`` (no post-processing).
        Override in strategies that add critique, refinement, etc.
        """
        return None

    def describe(self) -> str:
        """Human-readable description for logging."""
        return f"{self.name} strategy"


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

class SingleStrategy(Strategy):
    """One backend for everything.  Backward-compatible default."""

    name = "single"

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600
    ) -> ResearchResult:
        backend = self.research_backends[0]
        resp = invoke(
            backend, prompt,
            allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
        )
        return ResearchResult(
            findings=resp.text if not resp.is_error else "",
            backend_name=backend.name,
            cost_usd=resp.cost_usd,
            per_backend_costs={backend.name: resp.cost_usd},
        )

    def describe(self) -> str:
        return f"single ({self.backends_config.primary})"


class EnsembleStrategy(Strategy):
    """Parallel research by 2+ backends, blind judging by a different backend.

    Two researchers work independently on the same prompt.  The judge backend
    (configured separately) evaluates findings without knowing which backend
    produced them — a form of blind peer review.  The highest-scoring result
    is kept (or results above the threshold are merged, depending on config).
    """

    name = "ensemble"

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600
    ) -> ResearchResult:
        research = self.research_backends
        stagger = self.strategy_config.stagger_seconds
        results: list[tuple[str, AgentResponse]] = []

        with ThreadPoolExecutor(max_workers=self.strategy_config.max_parallel) as pool:
            futures = {}
            for i, backend in enumerate(research):
                if i > 0 and stagger > 0:
                    time.sleep(stagger)
                fut = pool.submit(
                    invoke, backend, prompt,
                    allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
                )
                futures[fut] = backend.name

            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    resp = fut.result()
                    results.append((name, resp))
                except Exception as exc:
                    log.warning("Ensemble: %s failed: %s", name, exc)
                    results.append((name, AgentResponse(text="", cost_usd=0.0, is_error=True)))

        # Collect costs
        per_backend: dict[str, float] = {}
        for name, resp in results:
            per_backend[name] = per_backend.get(name, 0.0) + resp.cost_usd

        # Pick the longest non-error result as the best candidate
        # (actual quality scoring happens later in the orchestrator)
        valid = [(name, resp) for name, resp in results if not resp.is_error and resp.text]
        if not valid:
            return ResearchResult(
                findings="", backend_name="none", cost_usd=sum(per_backend.values()),
                per_backend_costs=per_backend,
            )

        if self.strategy_config.merge_mode == "union":
            # Merge all valid findings under labeled sections
            merged = []
            for name, resp in valid:
                merged.append(f"<!-- source: {name} -->\n{resp.text}")
            return ResearchResult(
                findings="\n\n---\n\n".join(merged),
                backend_name="merged",
                cost_usd=sum(per_backend.values()),
                per_backend_costs=per_backend,
            )

        # Default: pick the longest (proxy for most substantive)
        best_name, best_resp = max(valid, key=lambda x: len(x[1].text))
        log.info(
            "Ensemble: picked %s (%d chars) from %d valid results.",
            best_name, len(best_resp.text), len(valid),
        )
        return ResearchResult(
            findings=best_resp.text,
            backend_name=best_name,
            cost_usd=sum(per_backend.values()),
            per_backend_costs=per_backend,
        )

    def describe(self) -> str:
        names = ", ".join(self.backends_config.research)
        judge = self.backends_config.judge_or_primary
        return f"ensemble (research: [{names}], judge: {judge})"


class AdversarialStrategy(Strategy):
    """Research by one backend, critique by another, adjudication by a third.

    Adds a post-research critique phase.  The adversary receives the findings
    and writes a critique identifying factual errors, unsupported claims, and
    gaps.  The judge then sees both findings and critique when scoring.
    """

    name = "adversarial"

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600
    ) -> ResearchResult:
        # Use the first research backend as the researcher
        backend = self.research_backends[0]
        resp = invoke(
            backend, prompt,
            allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
        )
        return ResearchResult(
            findings=resp.text if not resp.is_error else "",
            backend_name=backend.name,
            cost_usd=resp.cost_usd,
            per_backend_costs={backend.name: resp.cost_usd},
        )

    def post_research(
        self, findings, invoke, *, timeout=600
    ) -> CritiqueResult | None:
        if not findings:
            return None

        # Use a second research backend (or primary if only one research backend)
        adversary_name = (
            self.backends_config.research[1]
            if len(self.backends_config.research) > 1
            else self.backends_config.primary
        )
        adversary = self.backends[adversary_name]

        depth = self.strategy_config.critique_depth
        depth_instruction = {
            "light": "Do a quick factual spot-check.",
            "standard": "Identify factual errors, unsupported claims, and important gaps.",
            "thorough": "Perform a line-by-line review for accuracy, completeness, and nuance.",
        }.get(depth, "Identify factual errors, unsupported claims, and important gaps.")

        try:
            critique_prompt = _render(
                "critique.md",
                findings=findings,
                depth_instruction=depth_instruction,
            )
        except FileNotFoundError:
            critique_prompt = (
                f"Review the following research findings critically. "
                f"{depth_instruction}\n\n"
                f"For each issue found, explain what is wrong and why it matters.\n\n"
                f"---\n\n{findings}"
            )

        resp = invoke(adversary, critique_prompt, max_turns=3, timeout=timeout)

        if resp.is_error or not resp.text:
            return None

        return CritiqueResult(
            critique=resp.text,
            backend_name=adversary.name,
            cost_usd=resp.cost_usd,
        )

    def describe(self) -> str:
        researcher = self.backends_config.research[0] if self.backends_config.research else "?"
        adversary = (
            self.backends_config.research[1]
            if len(self.backends_config.research) > 1
            else self.backends_config.primary
        )
        return f"adversarial (researcher: {researcher}, adversary: {adversary}, judge: {self.backends_config.judge_or_primary})"


class ParallelStrategy(Strategy):
    """All backends research independently; best result (or top-K merged) wins.

    Like a multi-site clinical trial: each backend explores the same dimension
    independently.  The judge scores each result, and the best survives.
    """

    name = "parallel"

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600
    ) -> ResearchResult:
        # Same as ensemble but uses ALL backends
        research = self.research_backends
        stagger = self.strategy_config.stagger_seconds
        results: list[tuple[str, AgentResponse]] = []

        with ThreadPoolExecutor(max_workers=self.strategy_config.max_parallel) as pool:
            futures = {}
            for i, backend in enumerate(research):
                if i > 0 and stagger > 0:
                    time.sleep(stagger)
                fut = pool.submit(
                    invoke, backend, prompt,
                    allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
                )
                futures[fut] = backend.name

            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    resp = fut.result()
                    results.append((name, resp))
                except Exception as exc:
                    log.warning("Parallel: %s failed: %s", name, exc)
                    results.append((name, AgentResponse(text="", cost_usd=0.0, is_error=True)))

        per_backend: dict[str, float] = {}
        for name, resp in results:
            per_backend[name] = per_backend.get(name, 0.0) + resp.cost_usd

        valid = [(name, resp) for name, resp in results if not resp.is_error and resp.text]
        if not valid:
            return ResearchResult(
                findings="", backend_name="none",
                cost_usd=sum(per_backend.values()),
                per_backend_costs=per_backend,
            )

        # Pick longest as best proxy
        best_name, best_resp = max(valid, key=lambda x: len(x[1].text))
        log.info(
            "Parallel: picked %s (%d chars) from %d valid results.",
            best_name, len(best_resp.text), len(valid),
        )
        return ResearchResult(
            findings=best_resp.text,
            backend_name=best_name,
            cost_usd=sum(per_backend.values()),
            per_backend_costs=per_backend,
        )

    def describe(self) -> str:
        names = ", ".join(self.backends_config.research)
        return f"parallel (backends: [{names}])"


class SerialStrategy(Strategy):
    """Draft by one backend, refined by another.

    The drafter (typically fast/cheap) does a broad sweep.  The refiner
    (typically precise/expensive) reads the draft and deepens, corrects,
    and adds nuance.
    """

    name = "serial"

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600
    ) -> ResearchResult:
        research = self.research_backends
        if len(research) < 2:
            # Fallback: single backend acts as both drafter and refiner
            log.warning("Serial strategy requires 2+ research backends; falling back to single.")
            backend = research[0]
            resp = invoke(
                backend, prompt,
                allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
            )
            return ResearchResult(
                findings=resp.text if not resp.is_error else "",
                backend_name=backend.name,
                cost_usd=resp.cost_usd,
                per_backend_costs={backend.name: resp.cost_usd},
            )

        drafter = research[0]
        refiner = research[1]
        per_backend: dict[str, float] = {}

        # Phase 1: Draft
        log.info("Serial: drafting with %s...", drafter.name)
        draft_resp = invoke(
            drafter, prompt,
            allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
        )
        per_backend[drafter.name] = draft_resp.cost_usd

        if draft_resp.is_error or not draft_resp.text:
            return ResearchResult(
                findings="", backend_name=drafter.name,
                cost_usd=sum(per_backend.values()),
                per_backend_costs=per_backend,
            )

        # Phase 2: Refine
        if self.strategy_config.refiner_sees_draft:
            try:
                refine_prompt = _render(
                    "refine.md",
                    draft=draft_resp.text,
                    original_prompt=prompt,
                )
            except FileNotFoundError:
                refine_prompt = (
                    f"Below is a research draft. Deepen, correct, and add nuance. "
                    f"Preserve the structure (Findings, Evidence, Trade-offs, New Questions).\n\n"
                    f"---\n\nORIGINAL TASK:\n{prompt}\n\n---\n\nDRAFT:\n{draft_resp.text}"
                )
        else:
            refine_prompt = prompt

        log.info("Serial: refining with %s...", refiner.name)
        refine_resp = invoke(
            refiner, refine_prompt,
            allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
        )
        per_backend[refiner.name] = refine_resp.cost_usd

        if refine_resp.is_error or not refine_resp.text:
            # Fallback to draft
            return ResearchResult(
                findings=draft_resp.text,
                backend_name=drafter.name,
                cost_usd=sum(per_backend.values()),
                per_backend_costs=per_backend,
            )

        return ResearchResult(
            findings=refine_resp.text,
            backend_name=f"{drafter.name}+{refiner.name}",
            cost_usd=sum(per_backend.values()),
            per_backend_costs=per_backend,
        )

    def describe(self) -> str:
        names = [n for n in self.backends_config.research]
        if len(names) >= 2:
            return f"serial (drafter: {names[0]}, refiner: {names[1]})"
        return f"serial ({names[0] if names else '?'})"


class SpecialistStrategy(Strategy):
    """Route dimensions to the backend best suited for them.

    The routing is based on keyword matching: each backend is associated
    with keywords, and the dimension name is matched against them.
    Falls back to the primary backend if no match is found.

    Note: This strategy does not change the per-call behavior — it changes
    which backend handles a given dimension.  The orchestrator sets the
    active research backend before calling ``execute_research``.
    """

    name = "specialist"

    # Default keyword associations
    DEFAULT_KEYWORDS: dict[str, list[str]] = {
        "codex": ["code", "implementation", "API", "SDK", "library", "example", "programming"],
        "gemini": ["comparison", "overview", "landscape", "pricing", "market", "alternatives", "cost"],
        "claude": ["trade-off", "architecture", "design", "security", "reasoning", "analysis", "strategy"],
        "copilot": ["integration", "workflow", "tooling", "IDE", "developer experience"],
    }

    def route_dimension(self, dimension: str) -> Backend:
        """Pick the best backend for a given dimension based on keyword match."""
        dim_lower = dimension.lower()
        best_name = self.backends_config.primary
        best_score = 0

        for backend_name in self.backends_config.research:
            keywords = self.DEFAULT_KEYWORDS.get(backend_name, [])
            score = sum(1 for kw in keywords if kw.lower() in dim_lower)
            if score > best_score:
                best_score = score
                best_name = backend_name

        return self.backends[best_name]

    def execute_research(
        self, prompt, invoke, *, allowed_tools="", max_turns=10, timeout=600,
        dimension: str = "",
    ) -> ResearchResult:
        backend = self.route_dimension(dimension) if dimension else self.research_backends[0]
        log.info("Specialist: routing to %s for dimension '%s'.", backend.name, dimension)

        resp = invoke(
            backend, prompt,
            allowed_tools=allowed_tools, max_turns=max_turns, timeout=timeout,
        )
        return ResearchResult(
            findings=resp.text if not resp.is_error else "",
            backend_name=backend.name,
            cost_usd=resp.cost_usd,
            per_backend_costs={backend.name: resp.cost_usd},
        )

    def describe(self) -> str:
        names = ", ".join(self.backends_config.research)
        return f"specialist (pool: [{names}])"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "single": SingleStrategy,
    "ensemble": EnsembleStrategy,
    "adversarial": AdversarialStrategy,
    "parallel": ParallelStrategy,
    "serial": SerialStrategy,
    "specialist": SpecialistStrategy,
}


def get_strategy(
    strategy_name: str,
    backends_config: BackendsConfig,
    strategy_config: StrategyConfig,
    backends: dict[str, Backend],
) -> Strategy:
    """Instantiate a strategy by name.

    Args:
        strategy_name: One of ``"single"``, ``"ensemble"``, ``"adversarial"``,
            ``"parallel"``, ``"serial"``, ``"specialist"``.
        backends_config: Role-to-backend-name mapping.
        strategy_config: Strategy-specific settings.
        backends: Pre-instantiated backend instances keyed by name.

    Raises:
        ValueError: If the strategy name is not recognised.
    """
    cls = _STRATEGY_REGISTRY.get(strategy_name)
    if cls is None:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Must be one of: {', '.join(_STRATEGY_REGISTRY)}"
        )
    return cls(backends_config, strategy_config, backends)
