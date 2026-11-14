"""Stable entrypoint for the branch-owned CVRP solver-design subject.

The algorithm internals live under ``policies/baseline_modules`` so Scion can
research focused construction, destroy/repair, local-search, acceptance, and
scheduler modules without regenerating this whole entrypoint for every change.
The original ``vrp/`` source tree remains frozen and is not imported here.
"""

from __future__ import annotations

import time

from .baseline_modules.config import (
    ALNS_THRESHOLD,
    BASELINE_TIME_FRACTION,
    CW_THRESHOLD,
    DESTROY_RATIO,
    ENABLE_BASELINE_ALGORITHM,
    MAX_DESTROY_CUSTOMERS,
    REACTION_FACTOR,
    ROUTE_FIRST_LOCAL_SEARCH_PASSES,
    ROUTE_FIRST_MAX_STARTS,
    SEGMENT_LENGTH,
    SOLVER_VARIANT,
    USE_VNS,
    VNS_MAX_NO_IMPROVE,
    VNS_THRESHOLD,
)
from .baseline_modules.scheduler import _ALNSVNSSolver


class _DeadlineContext:
    """Expose the tighter of the runner and algorithm-local deadlines."""

    def __init__(self, context, time_limit_sec, *, clock=time.perf_counter):
        self._context = context
        self._clock = clock
        self._deadline = clock() + max(0.0, float(time_limit_sec))

    def remaining_time(self):
        outer_remaining = max(0.0, float(self._context.remaining_time()))
        local_remaining = max(0.0, self._deadline - self._clock())
        return min(outer_remaining, local_remaining)

    def remaining_time_ms(self):
        return int(self.remaining_time() * 1000.0)

    def elapsed_ms(self):
        return self._context.elapsed_ms()

    def make_solution(self, routes):
        return self._context.make_solution(routes)

    def set_stop_reason(self, reason):
        return self._context.set_stop_reason(reason)

    def record_phase(self, *args, **kwargs):
        return self._context.record_phase(*args, **kwargs)

    def record_iteration(self, *args, **kwargs):
        return self._context.record_iteration(*args, **kwargs)

    def record_move(self, *args, **kwargs):
        return self._context.record_move(*args, **kwargs)

    def record_solution_progress(self, *args, **kwargs):
        return self._context.record_solution_progress(*args, **kwargs)

    def record_objective_probe(self, *args, **kwargs):
        return self._context.record_objective_probe(*args, **kwargs)

    def record_telemetry_event(self, *args, **kwargs):
        return self._context.record_telemetry_event(*args, **kwargs)

    def record_best_update(self, *args, **kwargs):
        return self._context.record_best_update(*args, **kwargs)

    def record_alns_iteration(self, *args, **kwargs):
        return self._context.record_alns_iteration(*args, **kwargs)


def solve(instance, rng, time_limit_sec, context):
    """Run the controlled solver-design algorithm."""
    if not ENABLE_BASELINE_ALGORITHM:
        return None
    time_limit = _algorithm_time_limit(time_limit_sec)
    deadline_context = _DeadlineContext(context, time_limit)
    solver = _make_solver(instance, time_limit_sec, deadline_context)
    solution = solver.solve(instance, rng)
    deadline_context.set_stop_reason(solution.stop_reason)
    return deadline_context.make_solution(solution.routes_as_tuples())


def _algorithm_time_limit(time_limit_sec):
    return max(0.05, float(time_limit_sec) * BASELINE_TIME_FRACTION)


def _make_solver(instance, time_limit_sec, context):
    variant = str(SOLVER_VARIANT or "alns_vns").strip()
    time_limit = _algorithm_time_limit(time_limit_sec)
    max_routes = instance.allowed_routes or instance.bks_routes
    if variant == "alns_vns":
        return _ALNSVNSSolver(
            time_limit=time_limit,
            destroy_ratio=DESTROY_RATIO,
            segment_length=SEGMENT_LENGTH,
            reaction_factor=REACTION_FACTOR,
            vns_max_no_improve=VNS_MAX_NO_IMPROVE,
            use_vns=USE_VNS,
            cw_threshold=CW_THRESHOLD,
            vns_threshold=VNS_THRESHOLD,
            alns_threshold=ALNS_THRESHOLD,
            max_destroy_customers=MAX_DESTROY_CUSTOMERS,
            max_routes=max_routes,
            context=context,
        )
    if variant == "route_first_heuristic":
        from .baseline_modules.route_first_heuristic import RouteFirstHeuristicSolver

        return RouteFirstHeuristicSolver(
            time_limit=time_limit,
            max_routes=max_routes,
            max_starts=ROUTE_FIRST_MAX_STARTS,
            local_search_passes=ROUTE_FIRST_LOCAL_SEARCH_PASSES,
            context=context,
        )
    raise ValueError(f"unknown CVRP solver variant: {variant}")
