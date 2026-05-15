"""Stable entrypoint for the branch-owned CVRP solver-design subject.

The algorithm internals live under ``policies/baseline_modules`` so Scion can
research focused construction, destroy/repair, local-search, acceptance, and
scheduler modules without regenerating this whole entrypoint for every change.
The original ``vrp/`` source tree remains frozen and is not imported here.
"""
from __future__ import annotations

from .baseline_modules.config import (
    ALNS_THRESHOLD,
    BASELINE_TIME_FRACTION,
    CW_THRESHOLD,
    DESTROY_RATIO,
    ENABLE_BASELINE_ALGORITHM,
    MAX_DESTROY_CUSTOMERS,
    REACTION_FACTOR,
    SEGMENT_LENGTH,
    USE_VNS,
    VNS_MAX_NO_IMPROVE,
    VNS_THRESHOLD,
)
from .baseline_modules.scheduler import _ALNSVNSSolver


def solve(instance, rng, time_limit_sec, context):
    """Run the controlled solver-design algorithm."""
    if not ENABLE_BASELINE_ALGORITHM:
        return None
    solver = _ALNSVNSSolver(
        time_limit=max(0.05, float(time_limit_sec) * BASELINE_TIME_FRACTION),
        destroy_ratio=DESTROY_RATIO,
        segment_length=SEGMENT_LENGTH,
        reaction_factor=REACTION_FACTOR,
        vns_max_no_improve=VNS_MAX_NO_IMPROVE,
        use_vns=USE_VNS,
        cw_threshold=CW_THRESHOLD,
        vns_threshold=VNS_THRESHOLD,
        alns_threshold=ALNS_THRESHOLD,
        max_destroy_customers=MAX_DESTROY_CUSTOMERS,
        max_routes=instance.allowed_routes or instance.bks_routes,
        context=context,
    )
    solution = solver.solve(instance, rng)
    context.set_stop_reason(solution.stop_reason)
    return context.make_solution(solution.routes_as_tuples())
