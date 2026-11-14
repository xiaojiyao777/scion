"""Static CVRP solver-design package manifest and prompt constants."""

from __future__ import annotations

BROAD_SCOPE_TERMS = (
    "hybrid",
    "alns",
    "vns",
    "lns",
    "destroy",
    "repair",
    "recombination",
    "route-pool",
    "route pool",
    "population",
    "portfolio",
    "ensemble",
    "multi-operator",
    "multi operator",
    "restart",
    "perturb",
)

ACTIVE_SOLVER_DESIGN_PACKAGE = (
    "`policies/baseline_algorithm.py` and `policies/baseline_modules/*.py`"
)

__all__ = [
    "ACTIVE_SOLVER_DESIGN_PACKAGE",
    "BROAD_SCOPE_TERMS",
]
