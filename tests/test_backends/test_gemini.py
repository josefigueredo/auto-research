"""Tests for src.backends.gemini — GeminiBackend."""

import json

from src.backends.gemini import GeminiBackend
from src.backends.types import CallOptions, PromptMode


class TestGeminiBackend:
    def setup_method(self):
        self.backend = GeminiBackend()

    def test_name(self):
        assert self.backend.name == "gemini"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "gemini-2.5-flash"

    def test_build_command(self):
        opts = CallOptions(model="gemini-2.5-pro", allowed_tools="WebSearch")
        cmd = self.backend.build_command(opts)
        assert "gemini" in cmd
        assert "-p" in cmd
        assert "--model" in cmd
        assert "--yolo" in cmd
        assert "--output-format" in cmd

    def test_build_command_passes_model(self):
        opts = CallOptions(model="gemini-2.5-flash")
        cmd = self.backend.build_command(opts)
        assert "gemini-2.5-flash" in cmd

    def test_parse_dict_response(self):
        stdout = json.dumps({"response": "gemini output", "error": None})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "gemini output"
        assert resp.is_error is False

    def test_parse_error_response(self):
        stdout = json.dumps({"response": "partial", "error": "quota exceeded"})
        resp = self.backend.parse_response(stdout)
        assert resp.is_error is True
