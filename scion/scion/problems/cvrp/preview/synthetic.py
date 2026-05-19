"""Synthetic CVRP preview instances and solver-design context."""
from __future__ import annotations

import random
import signal
import threading
from typing import Any, Mapping

from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.surface_schema import (
    _POLICY_PREVIEW_EXEC_TIMEOUT_SEC,
    _POLICY_PREVIEW_TIME_LIMIT_SEC,
)

def _synthetic_preview_instance() -> CvrpInstance:
    return CvrpInstance(
        name="synthetic_preview",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=3),
            CvrpNode(id=2, x=0.0, y=2.0, demand=4),
            CvrpNode(id=3, x=2.0, y=2.0, demand=2),
        ),
        allowed_routes=2,
        use_integer_cost=True,
    )

def _solver_algorithm_preview_instances(instance: CvrpInstance) -> tuple[CvrpInstance, ...]:
    return (
        instance,
        CvrpInstance(
            name="synthetic_preview_canary_5",
            capacity=8,
            depot=0,
            nodes=(
                CvrpNode(id=0, x=0.0, y=0.0, demand=0),
                CvrpNode(id=1, x=2.0, y=0.0, demand=2),
                CvrpNode(id=2, x=4.0, y=0.0, demand=2),
                CvrpNode(id=3, x=0.0, y=3.0, demand=3),
                CvrpNode(id=4, x=0.0, y=6.0, demand=3),
            ),
            bks=20.0,
            bks_routes=2,
            use_integer_cost=True,
        ),
        CvrpInstance(
            name="synthetic_preview_improvement_trap",
            capacity=99,
            depot=0,
            nodes=(
                CvrpNode(id=0, x=0.0, y=0.0, demand=0),
                CvrpNode(id=1, x=-4.0, y=5.0, demand=1),
                CvrpNode(id=2, x=7.0, y=7.0, demand=1),
                CvrpNode(id=3, x=5.0, y=2.0, demand=1),
                CvrpNode(id=4, x=10.0, y=-6.0, demand=1),
            ),
            allowed_routes=1,
            bks=43.0,
            bks_routes=1,
            use_integer_cost=True,
        ),
    )

class _PolicyPreviewTimeout(BaseException):
    pass

def _call_solver_algorithm_preview(
    func: Any,
    *,
    instance: CvrpInstance,
    rng: random.Random,
    context: "_PreviewSolverAlgorithmContext",
) -> Any:
    if (
        threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "SIGALRM")
        or not hasattr(signal, "setitimer")
    ):
        return func(instance, rng, _POLICY_PREVIEW_TIME_LIMIT_SEC, context)

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise _PolicyPreviewTimeout()

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, _POLICY_PREVIEW_EXEC_TIMEOUT_SEC)
    try:
        return func(instance, rng, _POLICY_PREVIEW_TIME_LIMIT_SEC, context)
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)

class _PreviewSolverAlgorithmContext:
    def __init__(self, instance: CvrpInstance, rng: random.Random) -> None:
        self.instance = instance
        self.rng = rng
        self.time_limit_sec = _POLICY_PREVIEW_TIME_LIMIT_SEC
        self._phase_runtime_ms: dict[str, int] = {}
        self._remaining_time_calls = 0
        self._search_iterations = 0
        self._move_attempts = 0
        self._accepted_moves = 0
        self._stop_reason = ""

    @property
    def search_iterations(self) -> int:
        return self._search_iterations

    @property
    def move_attempts(self) -> int:
        return self._move_attempts

    @property
    def accepted_moves(self) -> int:
        return self._accepted_moves

    def remaining_time(self) -> float:
        self._remaining_time_calls += 1
        return max(0.0, self.time_limit_sec - (0.05 * self._remaining_time_calls))

    def remaining_time_ms(self) -> int:
        return int(self.remaining_time() * 1000)

    def elapsed_ms(self) -> int:
        return 0

    def make_solution(self, routes: Any) -> CvrpSolution:
        existing = _coerce_preview_solution(routes)
        if existing is not None:
            return existing
        return _coerce_preview_solution({"routes": routes}) or CvrpSolution(routes=())

    def is_valid(self, solution: Any) -> bool:
        coerced = _coerce_preview_solution(solution)
        if coerced is None:
            return False
        valid, _reason = _preview_solution_is_valid(self.instance, coerced)
        return valid

    def objective(self, solution: Any) -> "_PreviewObjectiveValue":
        coerced = _coerce_preview_solution(solution)
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        valid, reason = _preview_solution_is_valid(self.instance, coerced)
        if not valid:
            raise ValueError(reason)
        return _PreviewObjectiveValue(
            {
                "fleet_violation": 0.0,
                "total_distance": sum(
                    self.instance.route_distance(route) for route in coerced.routes
                ),
            }
        )

    def objective_key(self, solution: Any) -> tuple[float, float]:
        objective = self.objective(solution)
        return (float(objective[0]), float(objective[1]))

    def is_better(self, candidate: Any, incumbent: Any) -> bool:
        return self.objective_key(candidate) < self.objective_key(incumbent)

    def nearest_neighbor(self) -> CvrpSolution:
        unvisited = set(self.instance.customer_ids)
        routes: list[tuple[int, ...]] = []
        while unvisited:
            route: list[int] = []
            load = 0
            current = self.instance.depot
            while True:
                feasible = [
                    customer
                    for customer in unvisited
                    if load + self.instance.demand(customer) <= self.instance.capacity
                ]
                if not feasible:
                    break
                nxt = min(
                    feasible,
                    key=lambda customer: self.instance.distance(current, customer),
                )
                unvisited.remove(nxt)
                route.append(nxt)
                load += self.instance.demand(nxt)
                current = nxt
            if not route:
                raise ValueError("remaining customer demand exceeds capacity")
            routes.append(tuple(route))
        return CvrpSolution(routes=tuple(routes))

    def record_phase(self, name: str, elapsed_ms: int | float) -> None:
        phase = str(name or "").strip() or "unnamed"
        self._phase_runtime_ms[phase] = self._phase_runtime_ms.get(phase, 0) + int(
            max(0, elapsed_ms)
        )

    def record_iteration(self, phase: str = "search", count: int = 1) -> None:
        del phase
        try:
            increment = int(count)
        except (TypeError, ValueError):
            increment = 1
        self._search_iterations += max(1, increment)

    def record_move(
        self,
        phase: str,
        *,
        attempted: int = 1,
        accepted: int = 0,
        delta: int | float = 0.0,
        best_improved: bool = False,
    ) -> None:
        del phase, delta, best_improved
        try:
            attempts = int(attempted)
        except (TypeError, ValueError):
            attempts = 1
        try:
            accepts = int(accepted)
        except (TypeError, ValueError):
            accepts = 0
        self._move_attempts += max(1, attempts)
        self._accepted_moves += max(0, accepts)

    def set_stop_reason(self, reason: str) -> None:
        self._stop_reason = str(reason or "").strip()

class _PreviewObjectiveValue(dict):
    def _key(self) -> tuple[float, float]:
        return (
            float(self.get("fleet_violation", 0.0)),
            float(self.get("total_distance", 0.0)),
        )

    @staticmethod
    def _coerce_key(other: Any) -> tuple[float, float] | None:
        if isinstance(other, Mapping):
            return (
                float(other.get("fleet_violation", 0.0)),
                float(other.get("total_distance", 0.0)),
            )
        if isinstance(other, (list, tuple)) and len(other) >= 2:
            return (float(other[0]), float(other[1]))
        return None

    def __getitem__(self, key: Any) -> Any:
        if key == 0:
            return self.get("fleet_violation", 0.0)
        if key == 1:
            return self.get("total_distance", 0.0)
        return super().__getitem__(key)

    def __lt__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() < other_key

    def __le__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() <= other_key

    def __gt__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() > other_key

    def __ge__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() >= other_key

def _coerce_preview_solution(candidate: Any) -> CvrpSolution | None:
    if isinstance(candidate, CvrpSolution):
        return candidate
    routes = candidate.get("routes") if isinstance(candidate, Mapping) else getattr(
        candidate,
        "routes",
        None,
    )
    if routes is None:
        return None
    try:
        return CvrpSolution(
            routes=tuple(tuple(int(customer) for customer in route) for route in routes)
        )
    except (TypeError, ValueError):
        return None

def _preview_solution_is_valid(
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> tuple[bool, str]:
    seen: list[int] = []
    allowed = set(instance.customer_ids)
    for route in solution.routes:
        if not route:
            return False, "empty route"
        if instance.route_load(route) > instance.capacity:
            return False, "route exceeds capacity"
        for customer in route:
            if customer not in allowed:
                return False, f"unknown customer {customer}"
            seen.append(customer)
    if sorted(seen) != sorted(allowed):
        return False, "routes must cover each customer exactly once"
    if instance.allowed_routes is not None and len(solution.routes) > instance.allowed_routes:
        return False, "route count exceeds allowed_routes"
    return True, ""
