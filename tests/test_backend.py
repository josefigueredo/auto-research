"""Tests for src.backend — Backend ABC, all 4 implementations, and helpers."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.backend import (
    AgentResponse,
    Backend,
    CallOptions,
    ClaudeBackend,
    CodexBackend,
    CopilotBackend,
    GeminiBackend,
    PromptMode,
    _parse_jsonl_last_result,
    get_backend,
)


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------

class TestAgentResponse:
    def test_frozen(self):
        r = AgentResponse(text="hi", cost_usd=0.01, is_error=False)
        with pytest.raises(AttributeError):
            r.text = "changed"

    def test_defaults(self):
        r = AgentResponse(text="", cost_usd=0.0, is_error=False)
        assert r.raw == {}


# ---------------------------------------------------------------------------
# CallOptions
# ---------------------------------------------------------------------------

class TestCallOptions:
    def test_defaults(self):
        opts = CallOptions()
        assert opts.model == ""
        assert opts.allowed_tools == ""
        assert opts.max_turns == 10
        assert opts.max_budget_usd == 0.0
        assert opts.json_schema is None


# ---------------------------------------------------------------------------
# get_backend registry
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ClaudeBackend
# ---------------------------------------------------------------------------

class TestClaudeBackend:
    def setup_method(self):
        self.backend = ClaudeBackend()

    def test_name(self):
        assert self.backend.name == "claude"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "claude"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[:5] == ["claude", "-p", "-", "--output-format", "json"]

    def test_build_command_full(self):
        opts = CallOptions(
            model="opus",
            allowed_tools="WebSearch,Read",
            max_turns=5,
            max_budget_usd=0.75,
        )
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "opus"
        assert "--allowedTools" in cmd
        assert "--max-turns" in cmd
        assert "--max-budget-usd" in cmd

    def test_parse_response_array(self):
        stdout = json.dumps([
            {"type": "system"},
            {"type": "result", "result": "findings", "total_cost_usd": 0.12},
        ])
        resp = self.backend.parse_response(stdout)
        assert resp.text == "findings"
        assert resp.cost_usd == 0.12
        assert resp.is_error is False

    def test_parse_response_dict(self):
        stdout = json.dumps({"result": "dict result", "cost_usd": 0.05})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "dict result"

    def test_parse_response_plain_text(self):
        resp = self.backend.parse_response("not json at all")
        assert resp.text == "not json at all"

    def test_rate_limit_detection(self):
        assert ClaudeBackend._check_rate_limit("") == 0
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.95},
        }])
        assert ClaudeBackend._check_rate_limit(data) == 120

    def test_utilization_extraction(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.73},
        }])
        assert ClaudeBackend._extract_utilization(data) == 0.73

    @patch("src.backend.subprocess.run")
    def test_invoke_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"type": "result", "result": "hello", "total_cost_usd": 0.05},
            ]),
            stderr="",
        )
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.text == "hello"
        assert resp.is_error is False
        # Verify stdin was used
        assert mock_run.call_args[1]["input"] == "prompt"

    @patch("src.backend.subprocess.run")
    def test_invoke_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.is_error is True


# ---------------------------------------------------------------------------
# CodexBackend
# ---------------------------------------------------------------------------

class TestCodexBackend:
    def setup_method(self):
        self.backend = CodexBackend()

    def test_name(self):
        assert self.backend.name == "codex"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_build_command_with_tools(self):
        opts = CallOptions(model="gpt-5-codex", allowed_tools="WebSearch")
        cmd = self.backend.build_command(opts)
        assert "codex" in cmd
        assert "exec" in cmd
        assert "--json" in cmd
        assert "--model" in cmd
        assert "--sandbox" in cmd
        assert "workspace-write" in cmd
        assert "--full-auto" in cmd

    def test_build_command_readonly(self):
        opts = CallOptions()
        cmd = self.backend.build_command(opts)
        assert "read-only" in cmd


# ---------------------------------------------------------------------------
# GeminiBackend
# ---------------------------------------------------------------------------

class TestGeminiBackend:
    def setup_method(self):
        self.backend = GeminiBackend()

    def test_name(self):
        assert self.backend.name == "gemini"

    def test_prompt_mode_argument(self):
        assert self.backend.prompt_mode() == PromptMode.ARGUMENT

    def test_build_command(self):
        opts = CallOptions(model="gemini-2.5-pro", allowed_tools="WebSearch")
        cmd = self.backend.build_command(opts)
        assert "gemini" in cmd
        assert "-p" in cmd
        assert "--model" in cmd
        assert "--yolo" in cmd
        assert "--output-format" in cmd

    def test_parse_dict_response(self):
        stdout = json.dumps({"response": "gemini output", "error": None})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "gemini output"
        assert resp.is_error is False

    def test_parse_error_response(self):
        stdout = json.dumps({"response": "partial", "error": "quota exceeded"})
        resp = self.backend.parse_response(stdout)
        assert resp.is_error is True


# ---------------------------------------------------------------------------
# CopilotBackend
# ---------------------------------------------------------------------------

class TestCopilotBackend:
    def setup_method(self):
        self.backend = CopilotBackend()

    def test_name(self):
        assert self.backend.name == "copilot"

    def test_prompt_mode_argument(self):
        assert self.backend.prompt_mode() == PromptMode.ARGUMENT

    def test_build_command(self):
        opts = CallOptions(model="claude-sonnet-4", allowed_tools="Read", max_turns=5)
        cmd = self.backend.build_command(opts)
        assert "copilot" in cmd
        assert "--model" in cmd
        assert "--allow-all" in cmd
        assert "--autopilot" in cmd
        assert "--max-autopilot-continues" in cmd
        assert "5" in cmd

    @patch("src.backend.subprocess.run")
    def test_invoke_appends_prompt_as_arg(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "copilot output"}',
            stderr="",
        )
        self.backend.invoke("short prompt", CallOptions(), timeout=10)
        cmd = mock_run.call_args[0][0]
        assert "short prompt" in cmd
        # stdin should NOT be used
        assert mock_run.call_args[1].get("input") is None


# ---------------------------------------------------------------------------
# check_available
# ---------------------------------------------------------------------------

class TestCheckAvailable:
    @patch("src.backend.subprocess.run")
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert ClaudeBackend().check_available() is True

    @patch("src.backend.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert CodexBackend().check_available() is False

    @patch("src.backend.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gemini", timeout=10)
        assert GeminiBackend().check_available() is False


# ---------------------------------------------------------------------------
# _parse_jsonl_last_result
# ---------------------------------------------------------------------------

class TestParseJsonlLastResult:
    def test_empty(self):
        resp = _parse_jsonl_last_result("")
        assert resp.is_error is True

    def test_single_result(self):
        stdout = json.dumps({"result": "output", "cost_usd": 0.03})
        resp = _parse_jsonl_last_result(stdout)
        assert resp.text == "output"
        assert resp.cost_usd == 0.03

    def test_multiple_lines(self):
        lines = [
            json.dumps({"message": "thinking..."}),
            json.dumps({"result": "final answer", "cost_usd": 0.10}),
        ]
        resp = _parse_jsonl_last_result("\n".join(lines))
        assert resp.text == "final answer"

    def test_plain_text_fallback(self):
        resp = _parse_jsonl_last_result("just plain text")
        assert resp.text == "just plain text"
        assert resp.is_error is False
