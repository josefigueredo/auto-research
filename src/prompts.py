"""Prompt template loading and rendering.

Extracted from orchestrator.py to avoid circular imports — both
orchestrator.py and strategy.py need template rendering.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_template(name: str) -> str:
    """Read a prompt template file from the prompts directory.

    Raises:
        FileNotFoundError: With a user-friendly message if the template
            is missing.
    """
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {path}. "
            f"Ensure the 'prompts/' directory contains '{name}'."
        )
    return path.read_text(encoding="utf-8")


def render(template_name: str, **kwargs: str) -> str:
    """Load a prompt template and render it with the given variables.

    Args:
        template_name: Filename of the template in ``prompts/``.
        **kwargs: Template variables to substitute.

    Returns:
        The rendered prompt string.
    """
    tmpl = load_template(template_name)
    return tmpl.format(**kwargs)
