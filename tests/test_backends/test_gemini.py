"""Tests for src.backends.gemini — GeminiBackend."""

import json
from unittest.mock import MagicMock, patch

from src.backends.gemini import GeminiBackend
from src.backends.types import CallOptions, PromptMode


class TestGeminiBackend:
    def setup_method(self):
        self.backend = GeminiBackend()

    def test_name(self):
        assert self.backend.name == "gemini"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "gemini"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "gemini-2.5-flash"
        assert self.backend.capabilities.supports_json_schema is False
        assert self.backend.capabilities.supports_budget_cap is False

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[:3] == ["gemini", "-p", ""]
        assert "--output-format" in cmd
        assert "--yolo" not in cmd

    def test_build_command_with_model(self):
        opts = CallOptions(model="gemini-2.5-pro")
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "gemini-2.5-pro"

    def test_build_command_with_tools(self):
        opts = CallOptions(allowed_tools="WebSearch")
        cmd = self.backend.build_command(opts)
        assert "--yolo" in cmd

    def test_parse_dict_response(self):
        stdout = json.dumps({"response": "gemini output", "error": None})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "gemini output"
        assert resp.is_error is False

    def test_parse_dict_response_with_tokens(self):
        stdout = json.dumps({
            "response": "4",
            "stats": {
                "models": {
                    "gemini-2.5-flash": {
                        "tokens": {"input": 5500, "candidates": 1, "total": 5517, "cached": 0, "thoughts": 16}
                    }
                }
            }
        })
        resp = self.backend.parse_response(stdout)
        assert resp.text == "4"
        assert resp.input_tokens == 5500
        assert resp.output_tokens == 1

    def test_parse_dict_response_uses_result_key(self):
        stdout = json.dumps({"result": "via result key"})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "via result key"

    def test_parse_error_response(self):
        stdout = json.dumps({"response": "partial", "error": "quota exceeded"})
        resp = self.backend.parse_response(stdout)
        assert resp.is_error is True

    def test_parse_plain_text(self):
        resp = self.backend.parse_response("not json")
        assert resp.text == "not json"
        assert resp.is_error is False

    @patch.object(GeminiBackend, "_run_process")
    def test_invoke_uses_stdin(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"response": "4"}),
            stderr="",
        )
        resp = self.backend.invoke("What is 2+2?", CallOptions(), timeout=10)
        assert resp.text == "4"
        assert mock_run.call_args[1]["input"] == "What is 2+2?"
