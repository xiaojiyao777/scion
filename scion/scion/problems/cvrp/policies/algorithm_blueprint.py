"""Default CVRP algorithm-blueprint surface.

This top-level surface is intentionally inactive by default so existing policy
surfaces keep their behavior. Candidate proposals can enable it to coordinate
construction, baseline budget, package-owned local search, and restart knobs
through one bounded plan.
"""
from __future__ import annotations


def algorithm_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "construction_methods": ["nearest_neighbor"],
        "construction_keep_top_k": 1,
        "construction_bias": 0.0,
        "baseline_time_fraction": 0.8,
        "operator_round_limit": 20,
        "post_baseline_operators_enabled": True,
        "local_search": {
            "enabled_components": [],
            "rounds": 0,
            "top_k": 16,
        },
        "restart": {
            "enabled": False,
            "stagnation_rounds": 0,
        },
    }
