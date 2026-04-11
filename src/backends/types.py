"""Shared types for the backend abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PromptMode(Enum):
    """How the backend delivers prompts to the CLI process."""

    STDIN = "stdin"
    ARGUMENT = "argument"


@dataclass(frozen=True)
class CallOptions:
    """Options for a single CLI invocation.

    Backends map these to their CLI-specific flags.  Fields that a
    backend does not support are silently ignored.
    """

    model: str = ""
    allowed_tools: str = ""
    max_turns: int = 10
    max_budget_usd: float = 0.0
    json_schema: dict[str, Any] | None = None
    working_directory: str = ""
    sanitize_environment: bool = False


@dataclass(frozen=True)
class AgentResponse:
    """Result of a single CLI invocation."""

    text: str
    cost_usd: float
    is_error: bool
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendCapabilities:
    """Declares what a backend supports.

    Used by the orchestrator's model translation layer to resolve
    per-backend differences without hardcoded hacks.

    Attributes:
        supports_json_schema: Can pass ``--json-schema`` for structured output.
        supports_budget_cap: Can pass per-call USD budget limits.
        supports_rate_limit_detection: Has proactive rate limit backoff.
        supports_tools: Can use agent tools (WebSearch, etc.).
        supports_isolated_context: Can reliably run from an isolated working
            directory with a sanitized environment in this framework's setup.
        default_model: Model to use when the config model is a Claude
            shortname (e.g. ``"sonnet"``) that this backend doesn't understand.
    """

    supports_json_schema: bool = False
    supports_budget_cap: bool = False
    supports_rate_limit_detection: bool = False
    supports_tools: bool = True
    supports_isolated_context: bool = True
    default_model: str = ""


# Claude shortnames that non-Claude backends should translate
# to their own default_model.
CLAUDE_SHORTNAMES = frozenset({"sonnet", "opus", "haiku"})
