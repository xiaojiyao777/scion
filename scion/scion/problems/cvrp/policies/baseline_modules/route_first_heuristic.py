"""Route-first comparison solver for the CVRP solver-design subject."""
from __future__ import annotations

from .config import EXIT_RESERVE_FRACTION, _EPS
from .construction import _capacity_balanced_construction, _nearest_neighbor
from .route_first_improvement import improve_route_first_solution
from .route_first_seeding import route_first_seed_candidates
from .state import _Solution

_PHASE = "route_first_heuristic"


class RouteFirstHeuristicSolver:
    """Independent route-first heuristic, kept separate from ALNS+VNS."""

    def __init__(
        self,
        *,
        time_limit,
        max_routes,
        max_starts,
        local_search_passes,
        context,
    ):
        self.time_limit = float(time_limit)
        self.max_routes = int(max_routes) if max_routes is not None else None
        self.max_starts = max(1, int(max_starts))
        self.local_search_passes = max(1, int(local_search_passes))
        self.context = context

    def solve(self, instance, rng):
        del rng
        start_ms = self.context.elapsed_ms()
        phase_ms = self.context.elapsed_ms()
        reserve = max(0.02, self.time_limit * EXIT_RESERVE_FRACTION)
        best = None
        initial_route_count = 0
        initial_total_distance = 0.0
        budget_hit = False

        for seed in route_first_seed_candidates(
            instance,
            max_routes=self.max_routes,
            max_starts=self.max_starts,
        ):
            if not self._within_budget(start_ms, reserve):
                budget_hit = True
                break
            candidate = self._guard_solution(instance, seed)
            if best is None:
                initial_route_count = len(candidate.routes)
                initial_total_distance = float(candidate.total_cost)
            improve_route_first_solution(
                candidate,
                context=self.context,
                phase=_PHASE,
                max_passes=self.local_search_passes,
                within_budget=lambda: self._within_budget(start_ms, reserve),
            )
            best = self._accept_if_better(best, candidate)
            if not self._within_budget(start_ms, reserve):
                budget_hit = True
                break

        if best is None:
            best = self._guard_solution(instance, _nearest_neighbor(instance))
            initial_route_count = len(best.routes)
            initial_total_distance = float(best.total_cost)
            self.context.record_iteration(_PHASE, 1)
            self.context.record_move(_PHASE, attempted=1, accepted=0)

        best.stop_reason = "time_limit" if budget_hit else "completed"
        self.context.record_phase(_PHASE, self.context.elapsed_ms() - phase_ms)
        self.context.record_solution_progress(
            initial_route_count=initial_route_count,
            final_route_count=len(best.routes),
            initial_total_distance=initial_total_distance,
            final_total_distance=float(best.total_cost),
            budget_hit=budget_hit,
        )
        return best

    def _accept_if_better(self, best, candidate):
        if best is None:
            return candidate.copy()
        if candidate.total_cost + _EPS >= best.total_cost:
            return best
        delta = float(best.total_cost - candidate.total_cost)
        self.context.record_iteration(_PHASE, 1)
        self.context.record_move(
            _PHASE,
            attempted=1,
            accepted=1,
            delta=delta,
            best_improved=True,
        )
        return candidate.copy()

    def _guard_solution(self, instance, solution):
        solution.remove_empty_routes()
        if solution.is_feasible() and self._within_route_cap(solution):
            return solution
        guarded = self._capacity_guard(instance)
        if guarded.is_feasible() and self._within_route_cap(guarded):
            return guarded
        fallback = _nearest_neighbor(instance)
        fallback.remove_empty_routes()
        if fallback.is_feasible() and self._within_route_cap(fallback):
            return fallback
        raise ValueError(
            f"unable to construct feasible route-first solution for {instance.name}"
        )

    def _capacity_guard(self, instance):
        if self.max_routes is None:
            return _Solution(instance, [])
        try:
            return _capacity_balanced_construction(instance, self.max_routes)
        except ValueError:
            return _Solution(instance, [])

    def _within_route_cap(self, solution):
        return self.max_routes is None or len(solution.routes) <= self.max_routes

    def _within_budget(self, start_ms, reserve):
        elapsed_s = max(0.0, (self.context.elapsed_ms() - start_ms) / 1000.0)
        return elapsed_s < self.time_limit and self.context.remaining_time() > reserve
