"""Tests for src.backends.base — Backend ABC, check_available."""

from unittest.mock import MagicMock, patch

from src.backends.claude import ClaudeBackend
from src.backends.codex import CodexBackend
from src.backends.gemini import GeminiBackend


class TestCheckAvailable:
    @patch("src.backends.base.subprocess.run")
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert ClaudeBackend().check_available() is True

    @patch("src.backends.base.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert CodexBackend().check_available() is False

    @patch("src.backends.base.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gemini", timeout=10)
        assert GeminiBackend().check_available() is False
