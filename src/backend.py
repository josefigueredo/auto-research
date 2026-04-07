"""Backward-compatibility shim.

All backend code has moved to :mod:`src.backends`.  This module re-exports
every public symbol so existing imports continue to work::

    from src.backend import ClaudeBackend, get_backend  # still works
    from .backend import VALID_BACKENDS                 # still works
"""

# Re-export everything from the new package.
from .backends import *  # noqa: F401, F403

# Also expose the old private helper name for test compatibility.
from .backends import parse_jsonl_last_result as _parse_jsonl_last_result  # noqa: F401
