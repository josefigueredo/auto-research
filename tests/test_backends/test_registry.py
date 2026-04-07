"""Tests for src.backends.registry — get_backend, get_backends."""

import pytest

from src.backends import (
    ClaudeBackend,
    CodexBackend,
    CopilotBackend,
    GeminiBackend,
    get_backend,
    get_backends,
)


class TestGetBackend:
    def test_claude(self):
        assert isinstance(get_backend("claude"), ClaudeBackend)

    def test_codex(self):
        assert isinstance(get_backend("codex"), CodexBackend)

    def test_gemini(self):
        assert isinstance(get_backend("gemini"), GeminiBackend)

    def test_copilot(self):
        assert isinstance(get_backend("copilot"), CopilotBackend)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("chatgpt")


class TestGetBackends:
    def test_multiple(self):
        backends = get_backends({"claude", "codex"})
        assert len(backends) == 2
        assert isinstance(backends["claude"], ClaudeBackend)
        assert isinstance(backends["codex"], CodexBackend)

    def test_invalid_in_set(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backends({"claude", "invalid"})
