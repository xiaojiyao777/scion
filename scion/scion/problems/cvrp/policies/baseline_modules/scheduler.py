"""Top-level ALNS+VNS search scheduler for the solver-design subject."""
from __future__ import annotations

from .acceptance import _AdaptiveWeights, _SimulatedAnnealing
from .config import (
    EXIT_RESERVE_FRACTION,
    SIGMA_ACCEPTED,
    SIGMA_BEST,
    SIGMA_BETTER,
    SIZE70_TWO_OPT_MIN_CUSTOMERS,
    _EPS,
)
from .construction import (
    _capacity_balanced_construction,
    _clarke_wright_savings,
    _nearest_neighbor,
    _sweep_construction,
)
from .destroy_repair import (
    _greedy_insertion,
    _random_removal,
    _regret2_insertion,
    _regret3_insertion,
    _route_removal,
    _shaw_removal,
    _worst_removal,
)
from .local_search import _default_vns_operators, _two_opt_intra_polish, _vns

_SIZE70_TWO_OPT_INITIAL_PHASE = "size70_two_opt_initial"
_SIZE70_TWO_OPT_EMBEDDED_PHASE = "size70_two_opt_embedded"


class _ALNSVNSSolver:
    def __init__(
        self,
        *,
        time_limit,
        destroy_ratio,
        segment_length,
        reaction_factor,
        vns_max_no_improve,
        use_vns,
        cw_threshold,
        vns_threshold,
        alns_threshold,
        max_destroy_customers,
        max_routes,
        context,
    ):
        self.time_limit = float(time_limit)
        self.destroy_ratio = destroy_ratio
        self.segment_length = max(1, int(segment_length))
        self.reaction_factor = float(reaction_factor)
        self.vns_max_no_improve = int(vns_max_no_improve)
        self.use_vns = bool(use_vns)
        self.cw_threshold = int(cw_threshold)
        self.vns_threshold = int(vns_threshold)
        self.alns_threshold = int(alns_threshold)
        self.max_destroy_customers = max(1, int(max_destroy_customers))
        self.max_routes = int(max_routes) if max_routes is not None else None
        self.context = context

    def solve(self, instance, rng):
        start_ms = self.context.elapsed_ms()
        reserve = max(0.05, self.time_limit * EXIT_RESERVE_FRACTION)

        phase_ms = self.context.elapsed_ms()
        current = self._initial_solution(instance, reserve)
        self.context.record_phase("construction", self.context.elapsed_ms() - phase_ms)
        initial_route_count = len(current.routes)
        initial_total_distance = float(current.total_cost)
        best = current.copy()

        destroy_ops = [
            ("random", _random_removal),
            ("worst", _worst_removal),
            ("shaw", _shaw_removal),
            ("route", _route_removal),
        ]
        repair_ops = [
            ("greedy", _greedy_insertion),
            ("regret2", _regret2_insertion),
            ("regret3", _regret3_insertion),
        ]
        destroy_weights = _AdaptiveWeights([name for name, _ in destroy_ops], self.reaction_factor)
        repair_weights = _AdaptiveWeights([name for name, _ in repair_ops], self.reaction_factor)
        estimated_iterations = max(100, int(self.time_limit * 50))
        annealing = _SimulatedAnnealing(current.total_cost, estimated_iterations)

        if instance.customer_count > self.alns_threshold or self.time_limit <= 0:
            best.stop_reason = "alns_threshold"
            self.context.record_solution_progress(
                initial_route_count=initial_route_count,
                final_route_count=len(best.routes),
                initial_total_distance=initial_total_distance,
                final_total_distance=float(best.total_cost),
                budget_hit=False,
            )
            return best

        low, high = self.destroy_ratio
        low = max(0.0, min(float(low), float(high)))
        high = max(low, float(high))
        iteration = 0

        while self._within_budget(start_ms, reserve):
            iteration += 1
            self.context.record_iteration("alns", 1)
            candidate = current.copy()
            q_ratio = rng.uniform(low, high)
            q = max(1, int(round(instance.customer_count * q_ratio)))
            q = min(q, self.max_destroy_customers)

            d_idx = destroy_weights.choose(rng)
            r_idx = repair_weights.choose(rng)
            destroy_name, destroy_op = destroy_ops[d_idx]
            repair_name, repair_op = repair_ops[r_idx]
            score = 0.0
            accepted = False
            best_improved = False
            delta = 0.0

            try:
                removed = destroy_op(candidate, q, rng)
                if not removed:
                    destroy_weights.record(d_idx, 0.0)
                    repair_weights.record(r_idx, 0.0)
                    annealing.cool()
                    self.context.record_move("alns", attempted=1, accepted=0)
                    continue
                repair_op(candidate, removed, rng)
                candidate.remove_empty_routes()
                if self.use_vns and instance.customer_count <= self.vns_threshold:
                    phase_ms = self.context.elapsed_ms()
                    improved = _vns(
                        candidate,
                        _default_vns_operators(),
                        self.vns_max_no_improve,
                        self.context,
                        reserve,
                    )
                    self.context.record_phase("vns_embedded", self.context.elapsed_ms() - phase_ms)
                    candidate.remove_empty_routes()
                    if improved:
                        candidate.rebuild_index()
                elif self._should_run_size70_two_opt(instance):
                    self._run_size70_two_opt_polish(
                        candidate,
                        phase=_SIZE70_TWO_OPT_EMBEDDED_PHASE,
                        reserve=reserve,
                        iteration=iteration,
                        record_best_update=False,
                    )
            except ValueError:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue

            if not candidate.is_feasible():
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue
            if self.max_routes is not None and len(candidate.routes) > self.max_routes:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue

            if candidate.total_cost + _EPS < best.total_cost:
                delta = max(0.0, best.total_cost - candidate.total_cost)
                best = candidate.copy()
                current = candidate
                accepted = True
                best_improved = True
                score = SIGMA_BEST
                self.context.record_best_update(
                    best.routes_as_tuples(),
                    phase="alns",
                    iteration=iteration,
                    delta_from_previous_best=delta,
                    destroy_operator=destroy_name,
                    repair_operator=repair_name,
                )
            elif candidate.total_cost + _EPS < current.total_cost:
                current = candidate
                accepted = True
                score = SIGMA_BETTER
            elif annealing.accept(current.total_cost, candidate.total_cost, rng):
                current = candidate
                accepted = True
                score = SIGMA_ACCEPTED

            destroy_weights.record(d_idx, score)
            repair_weights.record(r_idx, score)
            self.context.record_move(
                "alns",
                attempted=1,
                accepted=1 if accepted else 0,
                delta=delta,
                best_improved=best_improved,
            )
            if iteration % self.segment_length == 0:
                destroy_weights.update()
                repair_weights.update()
            annealing.cool()

        destroy_weights.update()
        repair_weights.update()
        budget_hit = self.context.remaining_time() <= reserve
        best.stop_reason = "time_limit" if budget_hit else "completed"
        self.context.record_solution_progress(
            initial_route_count=initial_route_count,
            final_route_count=len(best.routes),
            initial_total_distance=initial_total_distance,
            final_total_distance=float(best.total_cost),
            budget_hit=budget_hit,
        )
        return best

    def _initial_solution(self, instance, reserve):
        if instance.customer_count > self.cw_threshold:
            solution = _sweep_construction(instance)
        else:
            solution = _clarke_wright_savings(instance, target_routes=self.max_routes)
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            solution = _capacity_balanced_construction(instance, self.max_routes)
        if not solution.is_feasible():
            solution = _nearest_neighbor(instance)
        if not solution.is_feasible():
            raise ValueError(f"unable to construct feasible solution for {instance.name}")
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            raise ValueError(
                f"initial solution uses {len(solution.routes)} routes; "
                f"max_routes={self.max_routes}"
            )
        if self.use_vns and self.time_limit > 0 and instance.customer_count <= self.vns_threshold:
            phase_ms = self.context.elapsed_ms()
            _vns(
                solution,
                _default_vns_operators(),
                self.vns_max_no_improve,
                self.context,
                reserve,
            )
            self.context.record_phase("vns_initial", self.context.elapsed_ms() - phase_ms)
            solution.remove_empty_routes()
        elif self._should_run_size70_two_opt(instance):
            self._run_size70_two_opt_polish(
                solution,
                phase=_SIZE70_TWO_OPT_INITIAL_PHASE,
                reserve=reserve,
                iteration=0,
                record_best_update=True,
            )
        return solution

    def _should_run_size70_two_opt(self, instance):
        return (
            self.time_limit > 0
            and instance.customer_count >= SIZE70_TWO_OPT_MIN_CUSTOMERS
            and (not self.use_vns or instance.customer_count > self.vns_threshold)
        )

    def _run_size70_two_opt_polish(
        self,
        solution,
        *,
        phase,
        reserve,
        iteration,
        record_best_update,
    ):
        if self.context.remaining_time() <= reserve:
            return False
        phase_ms = self.context.elapsed_ms()
        accepted_moves, delta_sum = _two_opt_intra_polish(
            solution,
            self.context,
            reserve,
            phase,
        )
        self.context.record_phase(phase, self.context.elapsed_ms() - phase_ms)
        if accepted_moves > 0:
            solution.remove_empty_routes()
            solution.rebuild_index()
            if record_best_update:
                self.context.record_best_update(
                    solution.routes_as_tuples(),
                    phase=phase,
                    iteration=iteration,
                    delta_from_previous_best=delta_sum,
                    operator="two_opt_intra",
                )
        return accepted_moves > 0

    def _within_budget(self, start_ms, reserve):
        elapsed_s = max(0.0, (self.context.elapsed_ms() - start_ms) / 1000.0)
        return elapsed_s < self.time_limit and self.context.remaining_time() > reserve
