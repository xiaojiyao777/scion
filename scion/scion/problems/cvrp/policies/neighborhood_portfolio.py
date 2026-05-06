"""Default CVRP neighborhood portfolio surface."""
from __future__ import annotations


def enabled_components(instance, time_limit_sec):
    return ["route_local", "route_pair", "ruin_recreate", "registry_operator"]


def component_weights(instance, time_limit_sec):
    return {
        "route_local": 1.0,
        "route_pair": 1.0,
        "ruin_recreate": 1.0,
        "registry_operator": 1.0,
    }


def candidate_limits(instance, time_limit_sec):
    return {
        "max_rounds": 3,
        "top_k": 16,
        "total_attempts": 100,
        "per_component_attempts": 40,
    }
