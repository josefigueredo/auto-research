"""Entry point for the autoresearch-claude framework.

Parses CLI arguments, validates the config, checks for the selected
backend CLI, and launches the research loop or synthesis.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .backend import VALID_BACKENDS, get_backend, get_backends
from .config import VALID_STRATEGIES, ResearchConfig
from .orchestrator import AutoResearcher
from .strategy import get_strategy


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
        description="Autonomous research loop powered by AI coding agent CLIs.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a research config YAML (see configs/_template.yaml).",
    )
    parser.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        default=None,
        help="CLI backend to use. Overrides the config file. Default: claude.",
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
        "--strategy",
        choices=VALID_STRATEGIES,
        default=None,
        help="Multi-backend strategy. Overrides the config file.",
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

    # Resolve backend (CLI flag overrides config file)
    backend_name = args.backend or config.execution.backend
    backend = get_backend(backend_name)

    # Resolve strategy (CLI flag overrides config file)
    strategy_name = args.strategy or config.execution.strategy

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

    # Build multi-backend set and check availability
    all_names = config.execution.backends.all_backend_names()
    if strategy_name == "single":
        all_names = {backend_name}
    backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    # Build strategy
    strategy = get_strategy(
        strategy_name,
        config.execution.backends,
        config.execution.strategy_config,
        backends,
    )

    # Run
    researcher = AutoResearcher(
        config=config,
        backend=backend,
        output_dir=output_dir,
        backends=backends,
        strategy=strategy,
    )

    try:
        if args.synthesize:
            researcher.synthesize_only()
        else:
            researcher.run()
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
