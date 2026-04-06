"""Tests for src.cli — argument parsing, backend detection, logging setup."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import _setup_logging, main


# ---------------------------------------------------------------------------
# _setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def test_verbose(self):
        import logging
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
                backend: claude
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

    @patch("src.cli.get_backend")
    def test_backend_not_available(self, mock_get, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = False
        mock_backend.name = "claude"
        mock_backend.cli_executable.return_value = "claude"
        mock_get.return_value = mock_backend
        result = main(["--config", str(config_file)])
        assert result == 1

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_synthesize_mode(self, mock_get, mock_researcher_cls, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["--config", str(config_file), "--synthesize"])
        assert result == 0
        mock_instance.synthesize_only.assert_called_once()

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_run_mode(self, mock_get, mock_researcher_cls, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["--config", str(config_file)])
        assert result == 0
        mock_instance.run.assert_called_once()

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_flag_overrides_config(self, mock_get, mock_researcher_cls, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_researcher_cls.return_value = MagicMock()
        main(["--config", str(config_file), "--backend", "codex"])
        mock_get.assert_called_with("codex")

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_defaults_from_config(self, mock_get, mock_researcher_cls, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_researcher_cls.return_value = MagicMock()
        main(["--config", str(config_file)])
        mock_get.assert_called_with("claude")

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_custom_output_dir(self, mock_get, mock_researcher_cls, config_file, tmp_path):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_researcher_cls.return_value = MagicMock()
        custom = tmp_path / "custom_out"
        main(["--config", str(config_file), "--output", str(custom)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()

    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_passed_to_researcher(self, mock_get, mock_researcher_cls, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get.return_value = mock_backend
        mock_researcher_cls.return_value = MagicMock()
        main(["--config", str(config_file)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["backend"] is mock_backend
