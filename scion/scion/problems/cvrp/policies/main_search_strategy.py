"""Default CVRP main-search strategy surface.

This singleton policy is intentionally inactive by default. Candidate proposals
can enable it to let the CVRP package own the complete construction, baseline,
improvement-loop, restart/perturbation, and optional registry-operator schedule
without editing solver.py.

Forced diagnostic candidates should keep this file as the only edited target,
set enabled=True, select both deep components route_pair_swap and
bounded_destroy_repair, and use 5 improvement rounds with top_k 64 or 128 so
runtime audit can show selected, attempted, skipped, and accepted coverage.
Formal-like .vrp diagnostics should keep baseline.time_fraction at 0.75 or
higher so accepted moves compete against a strong repo-local baseline. The
perturbation schedule can be after_no_improvement, before_first_round, or
before_each_round; use a pre-improvement schedule only when the hypothesis
needs to test whether recovery moves can escape a strong baseline local
optimum. The checked-in default remains inactive.
"""
from __future__ import annotations


def main_search_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "construction": {
            "methods": ["nearest_neighbor"],
            "keep_top_k": 1,
            "bias": 0.0,
        },
        "baseline": {
            "time_fraction": 0.8,
            "params": {},
        },
        "improvement": {
            "enabled_components": [],
            "rounds": 0,
            "top_k": 16,
        },
        "acceptance": {
            "min_distance_improvement": 0.0,
        },
        "restart": {
            "enabled": False,
            "stagnation_rounds": 0,
            "max_restarts": 0,
        },
        "perturbation": {
            "enabled": False,
            "strength": 1,
            "max_perturbations": 0,
            "schedule": "after_no_improvement",
        },
        "post_baseline_operators_enabled": False,
        "operator_round_limit": 0,
    }
