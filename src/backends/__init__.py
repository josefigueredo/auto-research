"""AI CLI backend abstraction layer.

Re-exports all public symbols so callers can use::

    from src.backends import ClaudeBackend, get_backend, AgentResponse
"""

# Import concrete backends to trigger auto-registration.
from .claude import ClaudeBackend
from .codex import CodexBackend
from .copilot import CopilotBackend
from .gemini import GeminiBackend

# Re-export public API.
from .base import Backend
from .jsonl import parse_jsonl_last_result
from .registry import get_backend, get_backends, valid_backends

# Generated from registry after all backends are imported above.
VALID_BACKENDS = valid_backends()
from .types import (
    CLAUDE_SHORTNAMES,
    AgentResponse,
    BackendCapabilities,
    CallOptions,
    PromptMode,
)

__all__ = [
    "AgentResponse",
    "Backend",
    "BackendCapabilities",
    "CallOptions",
    "CLAUDE_SHORTNAMES",
    "ClaudeBackend",
    "CodexBackend",
    "CopilotBackend",
    "GeminiBackend",
    "PromptMode",
    "VALID_BACKENDS",
    "get_backend",
    "get_backends",
    "parse_jsonl_last_result",
]
