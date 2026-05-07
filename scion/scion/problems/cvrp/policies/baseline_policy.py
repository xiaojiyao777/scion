"""Default CVRP repo-local baseline policy surface.

This policy preserves the vrp/src ALNS+VNS defaults while exposing bounded
main-search knobs to candidate proposals.
"""
from __future__ import annotations


def baseline_params(instance, time_limit_sec):
    return {
        "destroy_ratio": (0.10, 0.40),
        "segment_length": 100,
        "reaction_factor": 0.1,
        "vns_max_no_improve": 5000,
        "use_vns": True,
        "cw_threshold": 1500,
        "vns_threshold": 1200,
        "alns_threshold": 2000,
        "max_destroy_customers": 200,
    }
