"""Top-level ALNS+VNS search scheduler for the solver-design subject."""
from __future__ import annotations

from .acceptance import _AdaptiveWeights, _SimulatedAnnealing
from .config import EXIT_RESERVE_FRACTION, SIGMA_ACCEPTED, SIGMA_BEST, SIGMA_BETTER, _EPS
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
from .local_search import _default_vns_operators, _vns


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
            _repair_name, repair_op = repair_ops[r_idx]
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
        best.stop_reason = "time_limit" if self.context.remaining_time() <= reserve else "completed"
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
        return solution

    def _within_budget(self, start_ms, reserve):
        elapsed_s = max(0.0, (self.context.elapsed_ms() - start_ms) / 1000.0)
        return elapsed_s < self.time_limit and self.context.remaining_time() > reserve
