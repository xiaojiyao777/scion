"""CVRP research-surface exposure policy."""
from __future__ import annotations

from typing import Any, Iterable

ACTIVE_RESEARCH_SURFACE_NAMES = ("solver_design",)

LEGACY_RESEARCH_SURFACE_NAMES: tuple[str, ...] = ()

_ACTIVE = frozenset(ACTIVE_RESEARCH_SURFACE_NAMES)
_LEGACY = frozenset(LEGACY_RESEARCH_SURFACE_NAMES)


def is_active_research_surface(surface_name: str) -> bool:
    return str(surface_name or "").strip() in _ACTIVE


def is_legacy_research_surface(surface_name: str) -> bool:
    return str(surface_name or "").strip() in _LEGACY


def active_research_surfaces(surfaces: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(
        surface
        for surface in surfaces
        if is_active_research_surface(str(getattr(surface, "name", "") or ""))
    )
