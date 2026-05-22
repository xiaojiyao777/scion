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

SOLVER_DESIGN_API_MANIFEST_FILES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/state.py",
    "policies/baseline_modules/config.py",
)

SOLVER_DESIGN_INTEGRATION_FULL_FILES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/state.py",
)

SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES = (
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/config.py",
)

__all__ = [
    "ACTIVE_SOLVER_DESIGN_PACKAGE",
    "BROAD_SCOPE_TERMS",
    "SOLVER_DESIGN_API_MANIFEST_FILES",
    "SOLVER_DESIGN_INTEGRATION_FULL_FILES",
    "SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES",
]
