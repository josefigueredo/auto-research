"""Entry point for the autoresearch-claude framework.

Parses CLI arguments, validates the config, checks for the Claude CLI,
and launches the research loop or synthesis.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from .config import ResearchConfig
from .orchestrator import AutoResearcher


def _check_claude_cli() -> bool:
    """Return ``True`` if the ``claude`` CLI is installed and responds."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _setup_logging(verbose: bool) -> None:
    """Configure the root logger format and level.

    Args:
        verbose: If ``True``, set level to ``DEBUG``; otherwise ``INFO``.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the autoresearch CLI.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv``).

    Returns:
        Exit code: ``0`` on success, ``1`` on error.
    """
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description="Autonomous research loop powered by Claude Code agents.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a research config YAML (see configs/_template.yaml).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/<config-stem>/.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing iteration files in the output directory.",
    )
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Generate a synthesis report from existing data and exit.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("autoresearch")

    # Validate config file
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = ResearchConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load config: %s", exc)
        return 1

    # Resolve output directory
    output_dir: Path = args.output or Path("output") / config_path.stem
    output_dir = output_dir.resolve()

    # Warn about existing data when not resuming
    if not args.resume and not args.synthesize and output_dir.exists():
        iters_dir = output_dir / "iterations"
        if iters_dir.exists():
            existing_iters = list(iters_dir.glob("iter_*.md"))
            if existing_iters:
                log.info(
                    "Found %d existing iterations in %s. "
                    "Use --resume to continue, or they will be preserved alongside new data.",
                    len(existing_iters),
                    output_dir,
                )

    # Check claude CLI
    if not _check_claude_cli():
        log.error(
            "Claude CLI not found or not responding. "
            "Install it from https://claude.ai/download and ensure 'claude --version' works."
        )
        return 1

    # Run
    researcher = AutoResearcher(config=config, output_dir=output_dir)

    try:
        if args.synthesize:
            researcher.synthesize_only()
        elif args.resume:
            researcher.run()
        else:
            researcher.run()
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
