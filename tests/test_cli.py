"""Tests for src.cli — argument parsing, Claude CLI check, logging setup."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import _check_claude_cli, _setup_logging, main


# ---------------------------------------------------------------------------
# _check_claude_cli
# ---------------------------------------------------------------------------

class TestCheckClaudeCli:
    @patch("src.cli.subprocess.run")
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert _check_claude_cli() is True

    @patch("src.cli.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert _check_claude_cli() is False

    @patch("src.cli.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)
        assert _check_claude_cli() is False

    @patch("src.cli.subprocess.run")
    def test_nonzero_rc(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert _check_claude_cli() is False


# ---------------------------------------------------------------------------
# _setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def test_verbose(self):
        import logging
        # Reset root logger handlers so basicConfig takes effect
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        _setup_logging(verbose=True)
        assert root.level <= logging.DEBUG

    def test_normal(self):
        import logging
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        _setup_logging(verbose=False)
        assert root.level <= logging.INFO


# ---------------------------------------------------------------------------
# main — argument parsing and early exits
# ---------------------------------------------------------------------------

class TestMain:
    @pytest.fixture
    def config_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "test.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                max_iterations: 1
                model: sonnet
        """), encoding="utf-8")
        return p

    def test_missing_config(self, tmp_path):
        result = main(["--config", str(tmp_path / "nonexistent.yaml")])
        assert result == 1

    def test_malformed_config(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not_research: true\n", encoding="utf-8")
        result = main(["--config", str(bad)])
        assert result == 1

    @patch("src.cli._check_claude_cli", return_value=False)
    def test_no_claude_cli(self, mock_check, config_file):
        result = main(["--config", str(config_file)])
        assert result == 1

    @patch("src.cli.AutoResearcher")
    @patch("src.cli._check_claude_cli", return_value=True)
    def test_synthesize_mode(self, mock_check, mock_researcher_cls, config_file):
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["--config", str(config_file), "--synthesize"])
        assert result == 0
        mock_instance.synthesize_only.assert_called_once()

    @patch("src.cli.AutoResearcher")
    @patch("src.cli._check_claude_cli", return_value=True)
    def test_run_mode(self, mock_check, mock_researcher_cls, config_file):
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["--config", str(config_file)])
        assert result == 0
        mock_instance.run.assert_called_once()

    @patch("src.cli.AutoResearcher")
    @patch("src.cli._check_claude_cli", return_value=True)
    def test_output_dir_default(self, mock_check, mock_researcher_cls, config_file):
        mock_researcher_cls.return_value = MagicMock()
        main(["--config", str(config_file)])
        _, kwargs = mock_researcher_cls.call_args
        assert "test" in str(kwargs["output_dir"])  # derived from config stem

    @patch("src.cli.AutoResearcher")
    @patch("src.cli._check_claude_cli", return_value=True)
    def test_custom_output_dir(self, mock_check, mock_researcher_cls, config_file, tmp_path):
        custom = tmp_path / "custom_out"
        mock_researcher_cls.return_value = MagicMock()
        main(["--config", str(config_file), "--output", str(custom)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()
