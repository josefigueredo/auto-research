"""Tests for src.backends.types — AgentResponse, CallOptions, BackendCapabilities."""

import pytest

from src.backends.types import AgentResponse, BackendCapabilities, CallOptions


class TestAgentResponse:
    def test_frozen(self):
        r = AgentResponse(text="hi", cost_usd=0.01, is_error=False)
        with pytest.raises(AttributeError):
            r.text = "changed"

    def test_defaults(self):
        r = AgentResponse(text="", cost_usd=0.0, is_error=False)
        assert r.raw == {}
        assert r.input_tokens == 0
        assert r.output_tokens == 0


class TestCallOptions:
    def test_defaults(self):
        opts = CallOptions()
        assert opts.model == ""
        assert opts.allowed_tools == ""
        assert opts.max_turns == 10
        assert opts.max_budget_usd == 0.0
        assert opts.json_schema is None


class TestBackendCapabilities:
    def test_defaults(self):
        cap = BackendCapabilities()
        assert cap.supports_json_schema is False
        assert cap.supports_budget_cap is False
        assert cap.supports_rate_limit_detection is False
        assert cap.supports_tools is True
        assert cap.default_model == ""

    def test_frozen(self):
        cap = BackendCapabilities()
        with pytest.raises(AttributeError):
            cap.default_model = "changed"
