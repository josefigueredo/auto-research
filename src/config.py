"""Research configuration loading and validation.

Provides frozen dataclasses for scoring, execution, and top-level research
configuration.  Configs are loaded from YAML files via
``ResearchConfig.from_yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .backends import VALID_BACKENDS

# Valid multi-backend strategy names.
VALID_STRATEGIES = ("single", "ensemble", "adversarial", "parallel", "serial", "specialist")


@dataclass(frozen=True)
class BackendsConfig:
    """Role-to-backend mapping for multi-backend strategies.

    Attributes:
        primary: Backend for hypothesis generation and synthesis.
        research: Backends used for the execution phase.  In ensemble/parallel
            strategies multiple backends research independently.
        judge: Backend used for scoring/evaluation (should differ from
            research backends to avoid confirmation bias).
        utility: Backend used for mechanical tasks (compression).
    """

    primary: str = "claude"
    research: tuple[str, ...] = ("claude",)
    judge: str = ""  # empty → falls back to primary
    utility: str = ""  # empty → falls back to primary

    @property
    def judge_or_primary(self) -> str:
        return self.judge or self.primary

    @property
    def utility_or_primary(self) -> str:
        return self.utility or self.primary

    def all_backend_names(self) -> set[str]:
        """Return the set of all backend names referenced in this config."""
        names = {self.primary, *self.research}
        if self.judge:
            names.add(self.judge)
        if self.utility:
            names.add(self.utility)
        return names


@dataclass(frozen=True)
class StrategyConfig:
    """Strategy-specific settings for multi-backend research.

    Attributes:
        merge_mode: How to combine results from parallel execution.
            ``"best"`` keeps only the highest-scoring result.
            ``"union"`` merges all results that pass the threshold.
        merge_threshold: Minimum score for a result to be merge-eligible
            (only used when ``merge_mode="union"``).
        critique_depth: Depth of adversarial critique.
            ``"light"`` does a factual spot-check, ``"standard"`` is balanced,
            ``"thorough"`` is line-by-line.
        refiner_sees_draft: Whether the refiner backend receives the
            drafter's output as context (serial strategy).
        max_parallel: Maximum number of backends to run concurrently.
        stagger_seconds: Delay between launching parallel backends to
            reduce simultaneous rate-limit pressure.
    """

    merge_mode: str = "best"
    merge_threshold: float = 40.0
    critique_depth: str = "standard"
    refiner_sees_draft: bool = True
    max_parallel: int = 3
    stagger_seconds: int = 5


@dataclass(frozen=True)
class ScoringConfig:
    """Controls how each research iteration is scored.

    Attributes:
        min_dimensions_per_iteration: Minimum dimensions expected per iteration
            for full heuristic credit.
        target_dimensions_total: Target number of dimensions across all
            iterations.
        evidence_types: Tuple of evidence type labels the heuristic scorer
            looks for (e.g. ``"comparison_table"``, ``"pricing_data"``).
    """

    min_dimensions_per_iteration: int = 1
    target_dimensions_total: int = 10
    evidence_types: tuple[str, ...] = (
        "comparison_table",
        "pricing_data",
        "code_example",
        "architecture_diagram_description",
        "trade_off_analysis",
    )


@dataclass(frozen=True)
class ExecutionConfig:
    """Runtime parameters for the research loop.

    Attributes:
        max_iterations: Maximum iterations before stopping.  ``0`` means
            infinite (run until interrupted).
        compress_every: Compress the knowledge base every *N* iterations.
        allowed_tools: Comma-separated list of tools available to the agent.
        max_turns: Maximum agent turns per CLI invocation.
        timeout_seconds: Per-invocation timeout in seconds.
        backend: CLI backend to use (``"claude"``, ``"codex"``, ``"gemini"``,
            or ``"copilot"``).
        model: Model name (backend-specific, e.g. ``"sonnet"`` for Claude).
        max_budget_per_call: USD cap per CLI invocation (backends that don't
            support per-call budgets ignore this).
    """

    max_iterations: int = 0
    compress_every: int = 5
    allowed_tools: str = "WebSearch,WebFetch,Read,Bash,Glob,Grep"
    max_turns: int = 10
    timeout_seconds: int = 600
    backend: str = "claude"
    model: str = "sonnet"
    max_budget_per_call: float = 0.50
    strategy: str = "single"
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)


@dataclass(frozen=True)
class ResearchConfig:
    """Top-level research configuration loaded from a YAML file.

    Attributes:
        topic: The research question.
        goal: Description of the desired deliverable.
        dimensions: Tuple of dimensions to explore.
        scoring: Scoring parameters.
        execution: Execution / runtime parameters.
    """

    topic: str
    goal: str
    dimensions: tuple[str, ...]
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> ResearchConfig:
        """Load a research config from a YAML file.

        The YAML must contain a top-level ``research`` key with at least a
        ``topic`` field.  All other fields are optional and fall back to
        dataclass defaults.

        Args:
            path: Path to the YAML config file.

        Returns:
            A validated ``ResearchConfig`` instance.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is empty, malformed, or missing required
                fields.
        """
        with open(path, encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

        if "research" not in raw:
            raise ValueError("Config file must contain a top-level 'research' key")

        research: dict[str, Any] = raw["research"]

        if "topic" not in research:
            raise ValueError("Config 'research' section must contain a 'topic' field")

        # --- Scoring ----------------------------------------------------------
        scoring_raw: dict[str, Any] = research.get("scoring", {})
        evidence = scoring_raw.get("evidence_types")
        scoring_defaults = ScoringConfig()
        scoring = ScoringConfig(
            min_dimensions_per_iteration=scoring_raw.get(
                "min_dimensions_per_iteration",
                scoring_defaults.min_dimensions_per_iteration,
            ),
            target_dimensions_total=scoring_raw.get(
                "target_dimensions_total",
                scoring_defaults.target_dimensions_total,
            ),
            evidence_types=tuple(evidence) if evidence else scoring_defaults.evidence_types,
        )

        # --- Execution --------------------------------------------------------
        exec_raw: dict[str, Any] = research.get("execution", {})
        exec_defaults = ExecutionConfig()

        backend = exec_raw.get("backend", exec_defaults.backend)
        if backend not in VALID_BACKENDS:
            raise ValueError(
                f"Invalid backend '{backend}'. Must be one of: {', '.join(VALID_BACKENDS)}"
            )

        model = exec_raw.get("model", exec_defaults.model)

        max_budget = exec_raw.get("max_budget_per_call", exec_defaults.max_budget_per_call)
        if max_budget < 0:
            raise ValueError(f"max_budget_per_call must be non-negative, got {max_budget}")

        timeout = exec_raw.get("timeout_seconds", exec_defaults.timeout_seconds)
        if timeout <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout}")

        # --- Strategy / multi-backend -----------------------------------------
        strategy = exec_raw.get("strategy", "single")
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(VALID_STRATEGIES)}"
            )

        backends_raw: dict[str, Any] = exec_raw.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get("research", [backend])
            if isinstance(research_val, str):
                research_val = [research_val]
            for name in research_val:
                if name not in VALID_BACKENDS:
                    raise ValueError(f"Invalid research backend '{name}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            primary = backends_raw.get("primary", backend)
            if primary not in VALID_BACKENDS:
                raise ValueError(f"Invalid primary backend '{primary}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            judge = backends_raw.get("judge", "")
            if judge and judge not in VALID_BACKENDS:
                raise ValueError(f"Invalid judge backend '{judge}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            utility = backends_raw.get("utility", "")
            if utility and utility not in VALID_BACKENDS:
                raise ValueError(f"Invalid utility backend '{utility}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            backends_config = BackendsConfig(
                primary=primary,
                research=tuple(research_val),
                judge=judge,
                utility=utility,
            )
            # Warn if judge is also a researcher (defeats blind review)
            if strategy != "single" and judge and judge in research_val:
                import logging
                logging.getLogger("autoresearch").warning(
                    "Judge backend '%s' is also a research backend — blind review is compromised.",
                    judge,
                )
        else:
            # Backward compat: single backend → populate roles from it
            backends_config = BackendsConfig(
                primary=backend,
                research=(backend,),
            )

        strat_raw: dict[str, Any] = exec_raw.get("strategy_config", {})
        strategy_config = StrategyConfig(
            merge_mode=strat_raw.get("merge_mode", "best"),
            merge_threshold=strat_raw.get("merge_threshold", 40.0),
            critique_depth=strat_raw.get("critique_depth", "standard"),
            refiner_sees_draft=strat_raw.get("refiner_sees_draft", True),
            max_parallel=strat_raw.get("max_parallel", 3),
            stagger_seconds=strat_raw.get("stagger_seconds", 5),
        )

        execution = ExecutionConfig(
            max_iterations=exec_raw.get("max_iterations", exec_defaults.max_iterations),
            compress_every=exec_raw.get("compress_every", exec_defaults.compress_every),
            allowed_tools=exec_raw.get("allowed_tools", exec_defaults.allowed_tools),
            max_turns=exec_raw.get("max_turns", exec_defaults.max_turns),
            timeout_seconds=timeout,
            backend=backend,
            model=model,
            max_budget_per_call=max_budget,
            strategy=strategy,
            backends=backends_config,
            strategy_config=strategy_config,
        )

        return cls(
            topic=research["topic"],
            goal=research.get("goal", research["topic"]),
            dimensions=tuple(research.get("dimensions", [])),
            scoring=scoring,
            execution=execution,
        )
