"""Tests for src.backends.copilot — CopilotBackend."""

from unittest.mock import MagicMock, patch

from src.backends.copilot import CopilotBackend
from src.backends.types import CallOptions, PromptMode


class TestCopilotBackend:
    def setup_method(self):
        self.backend = CopilotBackend()

    def test_name(self):
        assert self.backend.name == "copilot"

    def test_prompt_mode_argument(self):
        assert self.backend.prompt_mode() == PromptMode.ARGUMENT

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "claude-sonnet-4-6"

    def test_build_command(self):
        opts = CallOptions(model="claude-sonnet-4", allowed_tools="Read", max_turns=5)
        cmd = self.backend.build_command(opts)
        assert "copilot" in cmd
        assert "--model" in cmd
        assert "--allow-all" in cmd
        assert "--autopilot" in cmd
        assert "--max-autopilot-continues" in cmd
        assert "5" in cmd

    @patch.object(CopilotBackend, "_run_process")
    def test_invoke_appends_prompt_as_arg(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "copilot output"}',
            stderr="",
        )
        self.backend.invoke("short prompt", CallOptions(), timeout=10)
        cmd = mock_run.call_args[0][0]
        assert "short prompt" in cmd
