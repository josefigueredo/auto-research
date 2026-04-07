"""Tests for src.backends.codex — CodexBackend."""

from src.backends.codex import CodexBackend
from src.backends.types import CallOptions, PromptMode


class TestCodexBackend:
    def setup_method(self):
        self.backend = CodexBackend()

    def test_name(self):
        assert self.backend.name == "codex"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "o4-mini"
        assert self.backend.capabilities.supports_json_schema is False
        assert self.backend.capabilities.supports_budget_cap is False

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

    def test_build_command_passes_model(self):
        opts = CallOptions(model="o4-mini")
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert "o4-mini" in cmd
