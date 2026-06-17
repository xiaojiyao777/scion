"""Top-level ALNS+VNS search scheduler for the solver-design subject."""
from __future__ import annotations

from .acceptance import _AdaptiveWeights, _SimulatedAnnealing
from .config import (
    ENABLE_EMBEDDED_VNS,
    ENABLE_INITIAL_VNS,
    ENABLE_SIZE70_TWO_OPT_FALLBACK,
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

        current = self._initial_solution(instance, reserve)
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
            acceptance_reason = "rejected"
            iteration_elapsed_before = self.context.elapsed_ms()
            iteration_remaining_before = self._remaining_time_ms()
            candidate_after_repair_distance = None
            candidate_after_polish_distance = None
            alns_core_ms = 0
            core_phase_ms = self.context.elapsed_ms()

            try:
                removed = destroy_op(candidate, q, rng)
                if not removed:
                    alns_core_ms += self.context.elapsed_ms() - core_phase_ms
                    self.context.record_phase("alns_core", alns_core_ms)
                    destroy_weights.record(d_idx, 0.0)
                    repair_weights.record(r_idx, 0.0)
                    annealing.cool()
                    self.context.record_move("alns", attempted=1, accepted=0)
                    self._record_alns_iteration_trace(
                        iteration=iteration,
                        elapsed_ms_before=iteration_elapsed_before,
                        remaining_ms_before=iteration_remaining_before,
                        q=q,
                        destroy_operator=destroy_name,
                        repair_operator=repair_name,
                        candidate_after_repair_distance=None,
                        candidate_after_polish_distance=None,
                        accepted=False,
                        acceptance_reason="destroy_empty",
                    )
                    continue
                repair_op(candidate, removed, rng)
                candidate.remove_empty_routes()
                candidate_after_repair_distance = float(candidate.total_cost)
                alns_core_ms += self.context.elapsed_ms() - core_phase_ms
                if (
                    ENABLE_EMBEDDED_VNS
                    and self.use_vns
                    and instance.customer_count <= self.vns_threshold
                ):
                    phase_ms = self.context.elapsed_ms()
                    self.context.record_objective_probe("vns_embedded_before", candidate)
                    improved = _vns(
                        candidate,
                        _default_vns_operators(),
                        self.vns_max_no_improve,
                        self.context,
                        reserve,
                    )
                    self.context.record_phase(
                        "vns_embedded",
                        self.context.elapsed_ms() - phase_ms,
                    )
                    candidate.remove_empty_routes()
                    self.context.record_objective_probe(
                        "vns_embedded_after",
                        candidate,
                        metadata={"improved": bool(improved), "iteration": iteration},
                    )
                    if improved:
                        candidate.rebuild_index()
                    candidate_after_polish_distance = float(candidate.total_cost)
                elif self._should_run_size70_two_opt(instance):
                    self._run_size70_two_opt_polish(
                        candidate,
                        phase=_SIZE70_TWO_OPT_EMBEDDED_PHASE,
                        reserve=reserve,
                        iteration=iteration,
                        record_best_update=False,
                    )
                    candidate_after_polish_distance = float(candidate.total_cost)
                else:
                    candidate_after_polish_distance = candidate_after_repair_distance
            except ValueError:
                alns_core_ms += self.context.elapsed_ms() - core_phase_ms
                self.context.record_phase("alns_core", alns_core_ms)
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                self._record_alns_iteration_trace(
                    iteration=iteration,
                    elapsed_ms_before=iteration_elapsed_before,
                    remaining_ms_before=iteration_remaining_before,
                    q=q,
                    destroy_operator=destroy_name,
                    repair_operator=repair_name,
                    candidate_after_repair_distance=candidate_after_repair_distance,
                    candidate_after_polish_distance=candidate_after_polish_distance,
                    accepted=False,
                    acceptance_reason="repair_error",
                )
                continue

            core_phase_ms = self.context.elapsed_ms()
            if not candidate.is_feasible():
                alns_core_ms += self.context.elapsed_ms() - core_phase_ms
                self.context.record_phase("alns_core", alns_core_ms)
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                self._record_alns_iteration_trace(
                    iteration=iteration,
                    elapsed_ms_before=iteration_elapsed_before,
                    remaining_ms_before=iteration_remaining_before,
                    q=q,
                    destroy_operator=destroy_name,
                    repair_operator=repair_name,
                    candidate_after_repair_distance=candidate_after_repair_distance,
                    candidate_after_polish_distance=candidate_after_polish_distance,
                    accepted=False,
                    acceptance_reason="infeasible",
                )
                continue
            if self.max_routes is not None and len(candidate.routes) > self.max_routes:
                alns_core_ms += self.context.elapsed_ms() - core_phase_ms
                self.context.record_phase("alns_core", alns_core_ms)
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                self._record_alns_iteration_trace(
                    iteration=iteration,
                    elapsed_ms_before=iteration_elapsed_before,
                    remaining_ms_before=iteration_remaining_before,
                    q=q,
                    destroy_operator=destroy_name,
                    repair_operator=repair_name,
                    candidate_after_repair_distance=candidate_after_repair_distance,
                    candidate_after_polish_distance=candidate_after_polish_distance,
                    accepted=False,
                    acceptance_reason="route_limit",
                )
                continue

            if candidate.total_cost + _EPS < best.total_cost:
                delta = max(0.0, best.total_cost - candidate.total_cost)
                best = candidate.copy()
                current = candidate
                accepted = True
                best_improved = True
                acceptance_reason = "new_best"
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
                acceptance_reason = "improves_current"
                score = SIGMA_BETTER
            elif annealing.accept(current.total_cost, candidate.total_cost, rng):
                current = candidate
                accepted = True
                acceptance_reason = "annealing_accept"
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
            alns_core_ms += self.context.elapsed_ms() - core_phase_ms
            self.context.record_phase("alns_core", alns_core_ms)
            self._record_alns_iteration_trace(
                iteration=iteration,
                elapsed_ms_before=iteration_elapsed_before,
                remaining_ms_before=iteration_remaining_before,
                q=q,
                destroy_operator=destroy_name,
                repair_operator=repair_name,
                candidate_after_repair_distance=candidate_after_repair_distance,
                candidate_after_polish_distance=candidate_after_polish_distance,
                accepted=accepted,
                acceptance_reason=acceptance_reason,
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
        phase_ms = self.context.elapsed_ms()
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
        self.context.record_phase("construction", self.context.elapsed_ms() - phase_ms)
        self.context.record_objective_probe("initial_before_local_search", solution)
        if (
            ENABLE_INITIAL_VNS
            and self.use_vns
            and self.time_limit > 0
            and instance.customer_count <= self.vns_threshold
        ):
            phase_ms = self.context.elapsed_ms()
            self.context.record_objective_probe("vns_initial_before", solution)
            _vns(
                solution,
                _default_vns_operators(),
                self.vns_max_no_improve,
                self.context,
                reserve,
            )
            solution.remove_empty_routes()
            self.context.record_phase(
                "vns_initial",
                self.context.elapsed_ms() - phase_ms,
            )
            self.context.record_objective_probe("vns_initial_after", solution)
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
            ENABLE_SIZE70_TWO_OPT_FALLBACK
            and self.time_limit > 0
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

    def _remaining_time_ms(self):
        remaining_time_ms = getattr(self.context, "remaining_time_ms", None)
        if callable(remaining_time_ms):
            return remaining_time_ms()
        return int(max(0.0, self.context.remaining_time()) * 1000.0)

    def _record_alns_iteration_trace(
        self,
        *,
        iteration,
        elapsed_ms_before,
        remaining_ms_before,
        q,
        destroy_operator,
        repair_operator,
        candidate_after_repair_distance,
        candidate_after_polish_distance,
        accepted,
        acceptance_reason,
        best_improved=False,
    ):
        recorder = getattr(self.context, "record_alns_iteration", None)
        if not callable(recorder):
            return
        recorder(
            iteration=iteration,
            elapsed_ms_before=elapsed_ms_before,
            remaining_ms_before=remaining_ms_before,
            q=q,
            destroy_operator=destroy_operator,
            repair_operator=repair_operator,
            candidate_after_repair_distance=candidate_after_repair_distance,
            candidate_after_polish_distance=candidate_after_polish_distance,
            accepted=accepted,
            acceptance_reason=acceptance_reason,
            best_improved=best_improved,
            elapsed_ms_after=self.context.elapsed_ms(),
            remaining_ms_after=self._remaining_time_ms(),
        )
