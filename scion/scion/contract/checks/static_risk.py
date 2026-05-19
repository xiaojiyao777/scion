"""Compatibility facade for static risk contract checks."""
from __future__ import annotations

from scion.contract.checks.complexity import check_complexity_bound
from scion.contract.checks.identity import check_surface_instance_identity
from scion.contract.checks.randomness import check_non_rng_random

__all__ = [
    "check_complexity_bound",
    "check_non_rng_random",
    "check_surface_instance_identity",
]
