"""Research configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ScoringConfig:
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
    max_iterations: int = 0  # 0 = infinite
    compress_every: int = 5
    allowed_tools: str = "WebSearch,WebFetch,Read,Bash,Glob,Grep"
    max_turns: int = 10
    timeout_seconds: int = 300


@dataclass(frozen=True)
class ResearchConfig:
    topic: str
    goal: str
    dimensions: tuple[str, ...]
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> ResearchConfig:
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        research = raw["research"]

        scoring_raw = research.get("scoring", {})
        evidence = scoring_raw.get("evidence_types")
        scoring = ScoringConfig(
            min_dimensions_per_iteration=scoring_raw.get("min_dimensions_per_iteration", 1),
            target_dimensions_total=scoring_raw.get("target_dimensions_total", 10),
            evidence_types=tuple(evidence) if evidence else ScoringConfig.evidence_types,
        )

        exec_raw = research.get("execution", {})
        execution = ExecutionConfig(
            max_iterations=exec_raw.get("max_iterations", 0),
            compress_every=exec_raw.get("compress_every", 5),
            allowed_tools=exec_raw.get("allowed_tools", ExecutionConfig.allowed_tools),
            max_turns=exec_raw.get("max_turns", 10),
            timeout_seconds=exec_raw.get("timeout_seconds", 300),
        )

        return cls(
            topic=research["topic"],
            goal=research.get("goal", research["topic"]),
            dimensions=tuple(research.get("dimensions", [])),
            scoring=scoring,
            execution=execution,
        )
