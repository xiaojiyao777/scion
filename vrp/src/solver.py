from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from .acceptance import SimulatedAnnealing
from .alns.destroy import DESTROY_OPERATORS
from .alns.repair import REPAIR_OPERATORS
from .alns.weights import AdaptiveWeights
from .construction import (
    capacity_balanced_construction,
    clarke_wright_savings,
    nearest_neighbor,
    sweep_construction,
)
from .local_search.operators import (
    or_opt_1,
    or_opt_2,
    or_opt_3,
    relocate,
    swap,
    two_opt_intra,
    two_opt_star,
)
from .local_search.vns import NeighborhoodOperator, vns
from .models import Instance, Solution

SIGMA_BEST = 33.0
SIGMA_BETTER = 9.0
SIGMA_ACCEPTED = 13.0


@dataclass
class SolverResult:
    solution: Solution
    best_cost: float
    iterations: int
    elapsed: float
    history: list[dict[str, float]] = field(default_factory=list)
    destroy_weights: dict[str, float] = field(default_factory=dict)
    repair_weights: dict[str, float] = field(default_factory=dict)


def default_vns_operators() -> list[NeighborhoodOperator]:
    return [
        two_opt_intra,
        relocate,
        or_opt_1,
        or_opt_2,
        or_opt_3,
        swap,
        two_opt_star,
    ]


class ALNSVNSSolver:
    """CVRP solver using ALNS as the outer loop and VNS as local search."""

    def __init__(
        self,
        time_limit: float = 60.0,
        seed: int | None = None,
        destroy_ratio: tuple[float, float] = (0.10, 0.40),
        segment_length: int = 100,
        reaction_factor: float = 0.1,
        vns_max_no_improve: int = 5000,
        use_vns: bool = True,
        cw_threshold: int = 1500,
        vns_threshold: int = 1200,
        alns_threshold: int = 2000,
        max_destroy_customers: int = 200,
        max_routes: int | None = None,
        verbose: bool = False,
    ):
        self.time_limit = float(time_limit)
        self.rng = random.Random(seed)
        self.destroy_ratio = destroy_ratio
        self.segment_length = max(1, segment_length)
        self.reaction_factor = reaction_factor
        self.vns_max_no_improve = vns_max_no_improve
        self.use_vns = use_vns
        self.cw_threshold = cw_threshold
        self.vns_threshold = vns_threshold
        self.alns_threshold = alns_threshold
        self.max_destroy_customers = max(1, max_destroy_customers)
        self.max_routes = max_routes
        self.verbose = verbose

    def _initial_solution(self, instance: Instance) -> Solution:
        if instance.num_customers > self.cw_threshold:
            solution = sweep_construction(instance)
        else:
            solution = clarke_wright_savings(instance, target_routes=self.max_routes)
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            solution = capacity_balanced_construction(instance, self.max_routes)
        if not solution.is_feasible():
            solution = nearest_neighbor(instance)
        if not solution.is_feasible():
            raise ValueError(f"Unable to construct a feasible solution for {instance.name}")
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            raise ValueError(
                f"Initial solution uses {len(solution.routes)} routes, "
                f"exceeds max_routes={self.max_routes}"
            )
        if self.use_vns and self.time_limit > 0 and instance.num_customers <= self.vns_threshold:
            vns(solution, default_vns_operators(), self.vns_max_no_improve)
            solution.remove_empty_routes()
        return solution

    def solve(self, instance: Instance) -> SolverResult:
        start = time.perf_counter()
        current = self._initial_solution(instance)
        best = current.copy()

        destroy_names = [name for name, _ in DESTROY_OPERATORS]
        repair_names = [name for name, _ in REPAIR_OPERATORS]
        destroy_weights = AdaptiveWeights(destroy_names, self.reaction_factor)
        repair_weights = AdaptiveWeights(repair_names, self.reaction_factor)

        estimated_iterations = max(100, int(self.time_limit * 50))
        annealing = SimulatedAnnealing(current.total_cost, estimated_iterations)

        history: list[dict[str, float]] = [
            {
                "iteration": 0.0,
                "elapsed": 0.0,
                "best": best.total_cost,
                "current": current.total_cost,
                "temperature": annealing.temperature,
            }
        ]

        if instance.num_customers > self.alns_threshold or self.time_limit <= 0:
            elapsed = time.perf_counter() - start
            return SolverResult(
                solution=best,
                best_cost=best.total_cost,
                iterations=0,
                elapsed=elapsed,
                history=history,
                destroy_weights={},
                repair_weights={},
            )

        low, high = self.destroy_ratio
        low = max(0.0, min(low, high))
        high = max(low, high)
        iteration = 0

        while time.perf_counter() - start < self.time_limit:
            iteration += 1
            candidate = current.copy()

            q_ratio = self.rng.uniform(low, high)
            q = max(1, int(round(instance.num_customers * q_ratio)))
            q = min(q, self.max_destroy_customers)

            d_idx = destroy_weights.choose(self.rng)
            r_idx = repair_weights.choose(self.rng)
            destroy_name, destroy_op = DESTROY_OPERATORS[d_idx]
            repair_name, repair_op = REPAIR_OPERATORS[r_idx]

            try:
                removed = destroy_op(candidate, q, self.rng)
                if not removed:
                    destroy_weights.record(d_idx, 0.0)
                    repair_weights.record(r_idx, 0.0)
                    annealing.cool()
                    continue

                repair_op(candidate, removed, self.rng)
                candidate.remove_empty_routes()
                if self.use_vns and instance.num_customers <= self.vns_threshold:
                    vns(candidate, default_vns_operators(), self.vns_max_no_improve)
                    candidate.remove_empty_routes()
            except ValueError:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                continue

            if not candidate.is_feasible():
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                continue
            if self.max_routes is not None and len(candidate.routes) > self.max_routes:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                continue

            score = 0.0
            accepted = False
            if candidate.total_cost + 1e-9 < best.total_cost:
                best = candidate.copy()
                current = candidate
                accepted = True
                score = SIGMA_BEST
            elif candidate.total_cost + 1e-9 < current.total_cost:
                current = candidate
                accepted = True
                score = SIGMA_BETTER
            elif annealing.accept(current.total_cost, candidate.total_cost, self.rng):
                current = candidate
                accepted = True
                score = SIGMA_ACCEPTED

            destroy_weights.record(d_idx, score)
            repair_weights.record(r_idx, score)

            elapsed = time.perf_counter() - start
            history.append(
                {
                    "iteration": float(iteration),
                    "elapsed": elapsed,
                    "best": best.total_cost,
                    "current": current.total_cost,
                    "candidate": candidate.total_cost,
                    "temperature": annealing.temperature,
                    "accepted": 1.0 if accepted else 0.0,
                }
            )

            if iteration % self.segment_length == 0:
                destroy_weights.update()
                repair_weights.update()

            if self.verbose and iteration % 50 == 0:
                print(
                    f"iter={iteration} best={best.total_cost:.3f} "
                    f"current={current.total_cost:.3f} "
                    f"destroy={destroy_name} repair={repair_name}"
                )

            annealing.cool()

        destroy_weights.update()
        repair_weights.update()
        elapsed = time.perf_counter() - start
        return SolverResult(
            solution=best,
            best_cost=best.total_cost,
            iterations=iteration,
            elapsed=elapsed,
            history=history,
            destroy_weights=destroy_weights.snapshot(),
            repair_weights=repair_weights.snapshot(),
        )


def solve(instance: Instance, **kwargs: Any) -> SolverResult:
    return ALNSVNSSolver(**kwargs).solve(instance)
