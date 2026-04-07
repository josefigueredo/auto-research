"""Tests for src.backends.copilot — CopilotBackend."""

import json
from unittest.mock import MagicMock, patch

from src.backends.copilot import CopilotBackend
from src.backends.types import CallOptions, PromptMode


class TestCopilotBackend:
    def setup_method(self):
        self.backend = CopilotBackend()

    def test_name(self):
        assert self.backend.name == "copilot"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "copilot"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "gpt-4.1"
        assert self.backend.capabilities.supports_json_schema is False
        assert self.backend.capabilities.supports_budget_cap is False

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[:3] == ["copilot", "-p", "-"]
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--silent" in cmd
        assert "--autopilot" in cmd

    def test_build_command_with_model(self):
        opts = CallOptions(model="gpt-4.1")
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "gpt-4.1"

    def test_build_command_with_tools(self):
        opts = CallOptions(allowed_tools="Read")
        cmd = self.backend.build_command(opts)
        assert "--allow-all" in cmd

    def test_build_command_with_turns(self):
        opts = CallOptions(max_turns=5)
        cmd = self.backend.build_command(opts)
        assert "--max-autopilot-continues" in cmd
        assert "5" in cmd

    def test_parse_response_assistant_message(self):
        lines = [
            json.dumps({"type": "session.mcp_servers_loaded", "data": {}}),
            json.dumps({
                "type": "assistant.message",
                "data": {"content": "The answer is 4."},
            }),
            json.dumps({"type": "result", "sessionId": "abc", "exitCode": 0}),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == "The answer is 4."
        assert resp.is_error is False

    def test_parse_response_empty(self):
        resp = self.backend.parse_response("")
        assert resp.is_error is True

    def test_parse_response_fallback_to_jsonl(self):
        stdout = json.dumps({"result": "fallback output"})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "fallback output"

    @patch.object(CopilotBackend, "_run_process")
    def test_invoke_uses_stdin(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "type": "assistant.message",
                "data": {"content": "copilot reply"},
            }),
            stderr="",
        )
        resp = self.backend.invoke("test prompt", CallOptions(), timeout=10)
        assert resp.text == "copilot reply"
        # Verify stdin was used
        assert mock_run.call_args[1]["input"] == "test prompt"
