"""Backend registry — discovery and instantiation by name."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Backend

_REGISTRY: dict[str, type[Backend]] = {}


def _register(name: str, cls: type[Backend]) -> None:
    """Called by ``Backend.__init_subclass__`` to auto-register backends."""
    _REGISTRY[name] = cls


def valid_backends() -> tuple[str, ...]:
    """Return all registered backend names (derived from the registry)."""
    return tuple(sorted(_REGISTRY))


def get_backend(name: str) -> Backend:
    """Instantiate a backend by name.

    Raises:
        ValueError: If the name is not recognised.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown backend '{name}'. Must be one of: {', '.join(valid_backends())}"
        )
    return cls()


def get_backends(backend_names: set[str]) -> dict[str, Backend]:
    """Instantiate a set of backends by name, deduplicating instances."""
    return {name: get_backend(name) for name in backend_names}
