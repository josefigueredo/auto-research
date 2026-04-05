"""Entry point for the autoresearch-claude framework."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ResearchConfig
from .orchestrator import AutoResearcher


def _check_claude_cli() -> bool:
    """Verify that the claude CLI is available and authenticated."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    return False


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
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

    # Validate config
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    config = ResearchConfig.from_yaml(config_path)

    # Resolve output directory
    output_dir: Path = args.output or Path("output") / config_path.stem
    output_dir = output_dir.resolve()

    if not args.resume and not args.synthesize and output_dir.exists():
        existing_iters = list((output_dir / "iterations").glob("iter_*.md"))
        if existing_iters:
            log.info(
                "Found %d existing iterations in %s. Use --resume to continue.",
                len(existing_iters),
                output_dir,
            )
            log.info("Starting fresh run instead (existing data preserved).")

    # Check claude CLI
    if not _check_claude_cli():
        log.error(
            "Claude CLI not found or not responding. "
            "Install it from https://claude.ai/download and ensure 'claude --version' works."
        )
        return 1

    # Run
    researcher = AutoResearcher(config=config, output_dir=output_dir)

    if args.synthesize:
        researcher.synthesize_only()
        return 0

    researcher.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
