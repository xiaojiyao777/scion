"""Default CVRP solver-algorithm research hook.

This file is intentionally inactive by default. Candidate proposals may replace
``solve`` with a complete CVRP heuristic under Scion's fixed problem contract:
the algorithm can construct and improve routes, but the adapter/solver remains
the authority for feasibility, objective computation, runtime limits, and
protocol evaluation.
"""
from __future__ import annotations


def solve(instance, rng, time_limit_sec, context):
    """Return None so the checked-in champion uses the stable baseline path."""
    return None
