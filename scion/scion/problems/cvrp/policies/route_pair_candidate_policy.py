"""Default CVRP route-pair candidate mechanism policy surface."""
from __future__ import annotations


def route_pair_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "scoring_terms": [
            "route_distance",
            "removal_saving",
            "distance_saving",
        ],
        "move_families": ["customer_swap"],
        "candidate_limits": {
            "pair_cap": 0,
            "position_cap": 0,
        },
    }

