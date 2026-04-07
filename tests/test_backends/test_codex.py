"""Tests for src.backends.codex — CodexBackend."""

import json
from unittest.mock import MagicMock, patch

from src.backends.codex import CodexBackend
from src.backends.types import CallOptions, PromptMode


class TestCodexBackend:
    def setup_method(self):
        self.backend = CodexBackend()

    def test_name(self):
        assert self.backend.name == "codex"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "codex"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "o4-mini"
        assert self.backend.capabilities.supports_json_schema is False
        assert self.backend.capabilities.supports_budget_cap is False

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[:3] == ["codex", "exec", "--json"]
        assert "read-only" in cmd
        assert "--full-auto" not in cmd

    def test_build_command_with_tools(self):
        opts = CallOptions(model="o4-mini", allowed_tools="WebSearch")
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert "workspace-write" in cmd
        assert "--full-auto" in cmd

    def test_build_command_passes_model(self):
        opts = CallOptions(model="o4-mini")
        cmd = self.backend.build_command(opts)
        assert cmd[cmd.index("--model") + 1] == "o4-mini"

    @patch.object(CodexBackend, "_run_process")
    def test_invoke_uses_stdin(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "codex output"}),
            stderr="",
        )
        resp = self.backend.invoke("test prompt", CallOptions(), timeout=10)
        assert resp.text == "codex output"
        assert mock_run.call_args[1]["input"] == "test prompt"
