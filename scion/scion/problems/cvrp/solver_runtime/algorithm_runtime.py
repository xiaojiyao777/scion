"""Active solver-design algorithm loading and telemetry context."""
from __future__ import annotations

from pathlib import Path
import random
import time
from typing import Any, Mapping

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution
from scion.problems.cvrp.solver_runtime.policy_modules import _load_policy_module
from scion.problems.cvrp.solver_runtime.solution_ops import (
    _coerce_solution,
    _objective_for_solution,
    _solution_is_valid,
)
from scion.problems.cvrp.solver_runtime.timing import _remaining_time_sec

_BASELINE_ALGORITHM_RELATIVE_PATH = "policies/baseline_algorithm.py"


def load_baseline_algorithm(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    adapter: CvrpAdapter,
) -> tuple[CvrpSolution | None, dict[str, Any]]:
    """Load and run the active branch-owned CVRP algorithm package."""

    return _load_algorithm_file(
        workspace_root=workspace_root,
        relative_path=_BASELINE_ALGORITHM_RELATIVE_PATH,
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        rng=rng,
        time_limit_sec=time_limit_sec,
        start_time=start_time,
        adapter=adapter,
    )


def _load_algorithm_file(
    *,
    workspace_root: str | Path,
    relative_path: str,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    adapter: CvrpAdapter,
) -> tuple[CvrpSolution | None, dict[str, Any]]:
    audit = solver_algorithm_defaults(relative_path)
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / relative_path).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(
            audit,
            "error",
            f"solver algorithm path escapes workspace: {relative_path}",
        )
        return None, audit
    if not policy_path.is_file():
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(
            audit,
            "error",
            f"active baseline algorithm is missing: {relative_path}",
        )
        return None, audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(audit, "error", f"algorithm load failed: {exc}")
        return None, audit

    solve_fn = getattr(module, "solve", None)
    audit["solver_algorithm_loaded"] = True
    if not callable(solve_fn):
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(audit, "error", "missing callable solve")
        return None, audit

    context = SolverAlgorithmContext(
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        rng=rng,
        time_limit_sec=time_limit_sec,
        start_time=start_time,
        adapter=adapter,
        audit=audit,
    )
    call_start_ns = time.monotonic_ns()
    try:
        raw_solution = solve_fn(instance, rng, time_limit_sec, context)
    except Exception as exc:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "exception"
        _record_solver_algorithm_event(audit, "error", f"solve failed: {exc}")
        _finalize_solver_algorithm_timing(audit, call_start_ns)
        return None, audit

    _finalize_solver_algorithm_timing(audit, call_start_ns)
    if raw_solution is None:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "inactive"
        _record_solver_algorithm_event(
            audit,
            "error",
            "active baseline algorithm returned None",
        )
        return None, audit

    solution = _coerce_solution(raw_solution)
    if solution is None:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "invalid_output"
        _record_solver_algorithm_event(
            audit,
            "error",
            "solve returned a value that cannot be coerced to CvrpSolution",
        )
        return None, audit

    valid, reason = _solution_is_valid(adapter, instance, solution)
    if not valid:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "invalid_solution"
        _record_solver_algorithm_event(
            audit,
            "error",
            f"solve returned invalid solution: {reason}",
        )
        return None, audit

    objective = _objective_for_solution(adapter, instance, solution)
    audit["solver_algorithm_active"] = True
    audit["solver_algorithm_solution_valid"] = True
    audit["solver_algorithm_solution_routes"] = len(solution.routes)
    audit["solver_algorithm_objective"] = dict(objective)
    audit["solver_algorithm_total_distance"] = float(
        objective.get("total_distance", 0.0)
    )
    audit["solver_algorithm_fleet_violation"] = float(
        objective.get("fleet_violation", 0.0)
    )
    stop_reason = str(audit.get("solver_algorithm_stop_reason") or "").strip()
    audit["solver_algorithm_stop_reason"] = (
        "completed" if stop_reason in {"", "inactive"} else stop_reason
    )
    _drop_inactive_solver_algorithm_records(audit)
    if not audit.get("solver_algorithm_phase_runtime_ms"):
        audit["solver_algorithm_phase_runtime_ms"] = {
            "solve": audit["solver_algorithm_elapsed_ms"]
        }
    return solution, audit


def solver_algorithm_defaults(
    relative_path: str = _BASELINE_ALGORITHM_RELATIVE_PATH,
) -> dict[str, Any]:
    return {
        "solver_algorithm_path": relative_path,
        "solver_algorithm_loaded": False,
        "solver_algorithm_active": False,
        "solver_algorithm_errors": 0,
        "solver_algorithm_events": [],
        "solver_algorithm_elapsed_ms": 0,
        "solver_algorithm_phase_runtime_ms": {"inactive": 0},
        "solver_algorithm_solution_valid": False,
        "solver_algorithm_solution_routes": 0,
        "solver_algorithm_objective": {"fleet_violation": 0.0, "total_distance": 0.0},
        "solver_algorithm_total_distance": 0.0,
        "solver_algorithm_fleet_violation": 0.0,
        "solver_algorithm_construction_calls": 0,
        "solver_algorithm_search_iterations": 0,
        "solver_algorithm_move_attempts": 0,
        "solver_algorithm_accepted_moves": 0,
        "solver_algorithm_improving_moves": 0,
        "solver_algorithm_neutral_accepted_moves": 0,
        "solver_algorithm_best_improving_moves": 0,
        "solver_algorithm_best_delta": 0.0,
        "solver_algorithm_phase_delta_sum": {"none": 0.0},
        "solver_algorithm_phase_best_delta": {"none": 0.0},
        "solver_algorithm_phase_improvement_counts": {"none": 0},
        "solver_algorithm_context_records": {"inactive": 0},
        "solver_algorithm_stop_reason": "inactive",
    }


def solver_algorithm_active(audit: Mapping[str, Any] | None) -> bool:
    return bool(audit and audit.get("solver_algorithm_active"))


class ObjectiveValue(dict):
    """Mapping objective value with lexicographic CVRP comparison helpers."""

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


class SolverAlgorithmContext:
    """Bounded helper API exposed to the active CVRP algorithm package."""

    def __init__(
        self,
        *,
        instance: CvrpInstance,
        instance_path: str,
        seed: int,
        rng: random.Random,
        time_limit_sec: float,
        start_time: float,
        adapter: CvrpAdapter,
        audit: dict[str, Any],
    ) -> None:
        self.instance = instance
        self.instance_path = instance_path
        self.seed = seed
        self.rng = rng
        self.time_limit_sec = time_limit_sec
        self._start_time = start_time
        self._adapter = adapter
        self._audit = audit

    def remaining_time(self) -> float:
        return _remaining_time_sec(self._start_time, self.time_limit_sec)

    def remaining_time_ms(self) -> int:
        return int(self.remaining_time() * 1000)

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start_time) * 1000)

    def make_solution(self, routes: Any) -> CvrpSolution:
        existing = _coerce_solution(routes)
        if existing is not None:
            return existing
        return CvrpSolution(
            routes=tuple(tuple(int(customer) for customer in route) for route in routes)
        )

    def is_valid(self, solution: Any) -> bool:
        coerced = _coerce_solution(solution)
        if coerced is None:
            return False
        valid, _reason = _solution_is_valid(self._adapter, self.instance, coerced)
        return valid

    def objective(self, solution: Any) -> ObjectiveValue:
        coerced = _coerce_solution(solution)
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        valid, reason = _solution_is_valid(self._adapter, self.instance, coerced)
        if not valid:
            raise ValueError(f"invalid solution: {reason}")
        return ObjectiveValue(_objective_for_solution(self._adapter, self.instance, coerced))

    def objective_key(self, solution: Any) -> tuple[float, float]:
        objective = self.objective(solution)
        return (float(objective[0]), float(objective[1]))

    def is_better(self, candidate: Any, incumbent: Any) -> bool:
        return self.objective_key(candidate) < self.objective_key(incumbent)

    def nearest_neighbor(self) -> CvrpSolution:
        self._audit["solver_algorithm_construction_calls"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_construction_calls")
        ) + 1
        return nearest_neighbor_solution(self.instance)

    def record_phase(self, name: str, elapsed_ms: int | float) -> None:
        phase = str(name or "").strip() or "unnamed"
        runtime = self._audit.setdefault("solver_algorithm_phase_runtime_ms", {})
        if not isinstance(runtime, dict):
            runtime = {}
            self._audit["solver_algorithm_phase_runtime_ms"] = runtime
        runtime.pop("inactive", None)
        runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + _as_nonnegative_int(
            elapsed_ms
        )
        records = self._audit.setdefault("solver_algorithm_context_records", {})
        if not isinstance(records, dict):
            records = {}
            self._audit["solver_algorithm_context_records"] = records
        records.pop("inactive", None)
        records[phase] = _as_nonnegative_int(records.get(phase)) + 1

    def record_iteration(self, phase: str = "search", count: int = 1) -> None:
        phase_name = str(phase or "").strip() or "search"
        increment = _as_nonnegative_int(count) or 1
        self._audit["solver_algorithm_search_iterations"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_search_iterations")
        ) + increment
        records = self._audit.setdefault("solver_algorithm_context_records", {})
        if not isinstance(records, dict):
            records = {}
            self._audit["solver_algorithm_context_records"] = records
        records.pop("inactive", None)
        key = f"{phase_name}_iterations"
        records[key] = _as_nonnegative_int(records.get(key)) + increment

    def record_move(
        self,
        phase: str,
        *,
        attempted: int = 1,
        accepted: int = 0,
        delta: int | float = 0.0,
        best_improved: bool = False,
    ) -> None:
        phase_name = str(phase or "").strip() or "search"
        attempts = _as_nonnegative_int(attempted)
        accepts = _as_nonnegative_int(accepted)
        if attempts <= 0 and accepts <= 0:
            attempts = 1
        self._audit["solver_algorithm_move_attempts"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_move_attempts")
        ) + attempts
        self._audit["solver_algorithm_accepted_moves"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_accepted_moves")
        ) + accepts
        try:
            delta_value = max(0.0, float(delta))
        except (TypeError, ValueError):
            delta_value = 0.0
        phase_delta = self._audit.setdefault("solver_algorithm_phase_delta_sum", {})
        if not isinstance(phase_delta, dict):
            phase_delta = {}
            self._audit["solver_algorithm_phase_delta_sum"] = phase_delta
        phase_delta.pop("none", None)
        phase_delta[phase_name] = float(phase_delta.get(phase_name, 0.0)) + delta_value
        phase_best = self._audit.setdefault("solver_algorithm_phase_best_delta", {})
        if not isinstance(phase_best, dict):
            phase_best = {}
            self._audit["solver_algorithm_phase_best_delta"] = phase_best
        phase_best.pop("none", None)
        phase_best[phase_name] = max(float(phase_best.get(phase_name, 0.0)), delta_value)
        counts = self._audit.setdefault("solver_algorithm_phase_improvement_counts", {})
        if not isinstance(counts, dict):
            counts = {}
            self._audit["solver_algorithm_phase_improvement_counts"] = counts
        if attempts > 0 or accepts > 0:
            counts.pop("none", None)
            counts.setdefault(phase_name, 0)
        if accepts > 0 and (delta_value > 0.0 or best_improved):
            counts[phase_name] = _as_nonnegative_int(counts.get(phase_name)) + accepts
            self._audit["solver_algorithm_improving_moves"] = _as_nonnegative_int(
                self._audit.get("solver_algorithm_improving_moves")
            ) + accepts
            if best_improved:
                self._audit["solver_algorithm_best_improving_moves"] = (
                    _as_nonnegative_int(
                        self._audit.get("solver_algorithm_best_improving_moves")
                    )
                    + accepts
                )
        elif accepts > 0:
            self._audit["solver_algorithm_neutral_accepted_moves"] = (
                _as_nonnegative_int(
                    self._audit.get("solver_algorithm_neutral_accepted_moves")
                )
                + accepts
            )
        self._audit["solver_algorithm_best_delta"] = max(
            float(self._audit.get("solver_algorithm_best_delta") or 0.0),
            delta_value,
        )

    def set_stop_reason(self, reason: str) -> None:
        value = str(reason or "").strip()
        if value:
            self._audit["solver_algorithm_stop_reason"] = value


def nearest_neighbor_solution(instance: CvrpInstance) -> CvrpSolution:
    unvisited = set(instance.customer_ids)
    routes: list[tuple[int, ...]] = []
    while unvisited:
        route: list[int] = []
        load = 0
        current = instance.depot
        while True:
            feasible = [
                customer
                for customer in unvisited
                if load + instance.demand(customer) <= instance.capacity
            ]
            if not feasible:
                break
            next_customer = min(
                feasible,
                key=lambda customer: (instance.distance(current, customer), customer),
            )
            route.append(next_customer)
            load += instance.demand(next_customer)
            unvisited.remove(next_customer)
            current = next_customer
        if not route:
            raise ValueError("remaining customer demand exceeds capacity")
        routes.append(tuple(route))
    return CvrpSolution(routes=tuple(routes))


def _record_solver_algorithm_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("solver_algorithm_events", [])
    if len(events) >= 20:
        return
    events.append(
        {
            "policy": str(
                audit.get("solver_algorithm_path") or _BASELINE_ALGORITHM_RELATIVE_PATH
            ),
            "status": status,
            "detail": detail,
        }
    )


def _finalize_solver_algorithm_timing(
    audit: dict[str, Any],
    call_start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - call_start_ns) / 1_000_000)
    audit["solver_algorithm_elapsed_ms"] = elapsed_ms
    phase_runtime = audit.get("solver_algorithm_phase_runtime_ms")
    if not isinstance(phase_runtime, dict) or not phase_runtime:
        audit["solver_algorithm_phase_runtime_ms"] = {"solve": elapsed_ms}


def _drop_inactive_solver_algorithm_records(audit: dict[str, Any]) -> None:
    for key in (
        "solver_algorithm_phase_runtime_ms",
        "solver_algorithm_context_records",
    ):
        values = audit.get(key)
        if isinstance(values, dict) and len(values) > 1:
            values.pop("inactive", None)


def _as_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)
