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
from scion.runtime.telemetry_events import (
    TypedTelemetryEvent,
    append_typed_telemetry_event,
)

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
    _refresh_solver_algorithm_actionability_summary(audit)
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
        "solver_algorithm_best_update_trace": [],
        "solver_algorithm_alns_iteration_trace": [],
        "solver_algorithm_objective_probes": [],
        "solver_algorithm_best_update_summary": _best_update_summary_template(),
        "solver_algorithm_phase_delta_sum": {"none": 0.0},
        "solver_algorithm_phase_best_delta": {"none": 0.0},
        "solver_algorithm_phase_improvement_counts": {"none": 0},
        "solver_algorithm_phase_move_attempts": {"none": 0},
        "solver_algorithm_phase_accepted_moves": {"none": 0},
        "solver_algorithm_runtime_budget_hit": False,
        "solver_algorithm_time_limit_ms": 0,
        "solver_algorithm_solution_progress": _solution_progress_template(),
        "solver_algorithm_actionability_summary": _actionability_summary_template(),
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
        self._audit["solver_algorithm_time_limit_ms"] = _as_nonnegative_int(
            float(time_limit_sec) * 1000.0
        )

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

    def record_telemetry_event(
        self,
        lane: str,
        mechanism_id: str,
        *,
        attribution_scope: str,
        attribution_confidence: float,
        before_ref: str | None,
        after_ref: str | None,
        missing_refs: tuple[str, ...],
        occurrences: int = 1,
        evidence_ref: str | None = None,
    ) -> None:
        """Record one typed event without changing legacy move counters."""

        append_typed_telemetry_event(
            self._audit,
            TypedTelemetryEvent(
                lane=lane,
                mechanism_id=mechanism_id,
                attribution_scope=attribution_scope,
                attribution_confidence=attribution_confidence,
                before_ref=before_ref,
                after_ref=after_ref,
                missing_refs=missing_refs,
                occurrences=occurrences,
                evidence_ref=evidence_ref,
            ),
        )

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
        phase_attempts = self._audit.setdefault(
            "solver_algorithm_phase_move_attempts",
            {},
        )
        if not isinstance(phase_attempts, dict):
            phase_attempts = {}
            self._audit["solver_algorithm_phase_move_attempts"] = phase_attempts
        phase_attempts.pop("none", None)
        phase_attempts[phase_name] = _as_nonnegative_int(
            phase_attempts.get(phase_name)
        ) + attempts
        phase_accepts = self._audit.setdefault(
            "solver_algorithm_phase_accepted_moves",
            {},
        )
        if not isinstance(phase_accepts, dict):
            phase_accepts = {}
            self._audit["solver_algorithm_phase_accepted_moves"] = phase_accepts
        phase_accepts.pop("none", None)
        phase_accepts[phase_name] = _as_nonnegative_int(
            phase_accepts.get(phase_name)
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

    def record_best_update(
        self,
        solution: Any,
        *,
        phase: str = "search",
        iteration: int | None = None,
        delta_from_previous_best: int | float = 0.0,
        destroy_operator: str | None = None,
        repair_operator: str | None = None,
        operator: str | None = None,
    ) -> None:
        """Record every incumbent update needed for CVRP solver diagnostics."""

        coerced = _coerce_solution(solution)
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        objective = self.objective(coerced)
        phase_name = str(phase or "").strip() or "search"
        try:
            update_delta = max(0.0, float(delta_from_previous_best))
        except (TypeError, ValueError):
            update_delta = 0.0
        trace = self._audit.setdefault("solver_algorithm_best_update_trace", [])
        if not isinstance(trace, list):
            trace = []
            self._audit["solver_algorithm_best_update_trace"] = trace
        event: dict[str, Any] = {
            "elapsed_ms": self.elapsed_ms(),
            "phase": phase_name,
            "iteration": _as_nonnegative_int(iteration),
            "objective": dict(objective),
            "total_distance": float(objective.get("total_distance", 0.0)),
            "route_count": len(coerced.routes),
            "delta_from_previous_best": update_delta,
        }
        operator_name = str(operator or "").strip()
        destroy_name = str(destroy_operator or "").strip()
        repair_name = str(repair_operator or "").strip()
        if operator_name:
            event["operator"] = operator_name
        if destroy_name:
            event["destroy_operator"] = destroy_name
        if repair_name:
            event["repair_operator"] = repair_name
        if destroy_name or repair_name:
            event["operator_pair"] = (
                f"{destroy_name or 'unknown'}+{repair_name or 'unknown'}"
            )
        trace.append(event)
        _refresh_solver_algorithm_best_update_summary(self._audit, event)

    def record_objective_probe(
        self,
        name: str,
        solution: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Record objective snapshots for phase attribution diagnostics."""

        coerced = _coerce_solution(solution)
        if coerced is None and callable(getattr(solution, "routes_as_tuples", None)):
            coerced = _coerce_solution(solution.routes_as_tuples())
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        objective = self.objective(coerced)
        probes = self._audit.setdefault("solver_algorithm_objective_probes", [])
        if not isinstance(probes, list):
            probes = []
            self._audit["solver_algorithm_objective_probes"] = probes
        event: dict[str, Any] = {
            "elapsed_ms": self.elapsed_ms(),
            "name": str(name or "").strip() or "objective_probe",
            "objective": dict(objective),
            "total_distance": float(objective.get("total_distance", 0.0)),
            "route_count": len(coerced.routes),
        }
        if metadata:
            event["metadata"] = {
                str(key): value
                for key, value in metadata.items()
                if isinstance(value, (str, int, float, bool)) or value is None
            }
        probes.append(event)

    def record_alns_iteration(
        self,
        *,
        iteration: int,
        elapsed_ms_before: int | float,
        remaining_ms_before: int | float,
        q: int,
        destroy_operator: str,
        repair_operator: str,
        candidate_after_repair_distance: int | float | None = None,
        candidate_after_polish_distance: int | float | None = None,
        accepted: bool = False,
        acceptance_reason: str = "",
        best_improved: bool = False,
        elapsed_ms_after: int | float | None = None,
        remaining_ms_after: int | float | None = None,
    ) -> None:
        """Record ALNS iteration diagnostics for runtime-pressure analysis."""

        trace = self._audit.setdefault("solver_algorithm_alns_iteration_trace", [])
        if not isinstance(trace, list):
            trace = []
            self._audit["solver_algorithm_alns_iteration_trace"] = trace
        event: dict[str, Any] = {
            "iteration": _as_nonnegative_int(iteration),
            "elapsed_ms_before": _as_nonnegative_int(elapsed_ms_before),
            "remaining_ms_before": _as_nonnegative_int(remaining_ms_before),
            "q": _as_nonnegative_int(q),
            "destroy_operator": str(destroy_operator or "").strip() or "unknown",
            "repair_operator": str(repair_operator or "").strip() or "unknown",
            "accepted": bool(accepted),
            "acceptance_reason": str(acceptance_reason or "").strip() or "unknown",
            "best_improved": bool(best_improved),
        }
        repair_distance = _optional_nonnegative_float(
            candidate_after_repair_distance
        )
        polish_distance = _optional_nonnegative_float(
            candidate_after_polish_distance
        )
        if repair_distance is not None:
            event["candidate_after_repair_distance"] = repair_distance
        if polish_distance is not None:
            event["candidate_after_polish_distance"] = polish_distance
        if elapsed_ms_after is not None:
            event["elapsed_ms_after"] = _as_nonnegative_int(elapsed_ms_after)
        if remaining_ms_after is not None:
            event["remaining_ms_after"] = _as_nonnegative_int(remaining_ms_after)
        trace.append(event)

    def set_stop_reason(self, reason: str) -> None:
        value = str(reason or "").strip()
        if value:
            self._audit["solver_algorithm_stop_reason"] = value

    def record_solution_progress(
        self,
        *,
        initial_route_count: int,
        final_route_count: int,
        initial_total_distance: int | float,
        final_total_distance: int | float,
        budget_hit: bool = False,
    ) -> None:
        """Record solver-local progress diagnostics without affecting comparison."""

        initial_routes = _as_nonnegative_int(initial_route_count)
        final_routes = _as_nonnegative_int(final_route_count)
        initial_distance = _as_nonnegative_float(initial_total_distance)
        final_distance = _as_nonnegative_float(final_total_distance)
        self._audit["solver_algorithm_runtime_budget_hit"] = bool(budget_hit)
        self._audit["solver_algorithm_solution_progress"] = {
            "initial_route_count": initial_routes,
            "final_route_count": final_routes,
            "route_count_delta_final_minus_initial": final_routes - initial_routes,
            "initial_total_distance": initial_distance,
            "final_total_distance": final_distance,
            "total_distance_delta_final_minus_initial": (
                final_distance - initial_distance
            ),
            "total_distance_improvement_from_initial": (
                initial_distance - final_distance
            ),
        }


def typed_events_from_legacy_record_move(
    phase: str,
    *,
    attempted: int = 1,
    accepted: int = 0,
    delta: int | float = 0.0,
    best_improved: bool = False,
) -> tuple[TypedTelemetryEvent, ...]:
    """Interpret ambiguous ``record_move`` data without claiming direct effect.

    This is a compatibility reader, not a write-through bridge.  Existing
    ``record_move`` calls may represent a move, pool admission, selector switch,
    or later associated improvement, so legacy effect-shaped values stay in the
    weaker associated-outcome lane until problem code supplies causal refs.
    """

    mechanism_id = str(phase or "").strip() or "search"
    attempts = _as_nonnegative_int(attempted)
    accepts = _as_nonnegative_int(accepted)
    try:
        delta_value = max(0.0, float(delta))
    except (TypeError, ValueError):
        delta_value = 0.0
    if attempts <= 0 and accepts <= 0:
        attempts = 1
    events: list[TypedTelemetryEvent] = []
    if attempts > 0:
        events.append(
            TypedTelemetryEvent(
                lane="attempt",
                mechanism_id=mechanism_id,
                attribution_scope="legacy_record_move",
                attribution_confidence=1.0,
                before_ref=None,
                after_ref=None,
                missing_refs=("before_ref", "after_ref"),
                occurrences=attempts,
                evidence_ref=(
                    f"runtime.solver_algorithm_phase_move_attempts.{mechanism_id}"
                ),
            )
        )
    if accepts > 0 or delta_value > 0.0 or best_improved:
        if delta_value > 0.0:
            evidence_ref = f"runtime.solver_algorithm_phase_delta_sum.{mechanism_id}"
        elif accepts > 0:
            evidence_ref = (
                f"runtime.solver_algorithm_phase_accepted_moves.{mechanism_id}"
            )
        else:
            evidence_ref = (
                f"runtime.solver_algorithm_phase_improvement_counts.{mechanism_id}"
            )
        events.append(
            TypedTelemetryEvent(
                lane="associated_outcome",
                mechanism_id=mechanism_id,
                attribution_scope="legacy_record_move_ambiguous",
                attribution_confidence=0.0,
                before_ref=None,
                after_ref=None,
                missing_refs=("before_ref", "after_ref"),
                occurrences=max(accepts, 1),
                evidence_ref=evidence_ref,
            )
        )
    return tuple(events)


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
    _refresh_solver_algorithm_actionability_summary(audit)


def _drop_inactive_solver_algorithm_records(audit: dict[str, Any]) -> None:
    for key in (
        "solver_algorithm_phase_runtime_ms",
        "solver_algorithm_context_records",
    ):
        values = audit.get(key)
        if isinstance(values, dict) and len(values) > 1:
            values.pop("inactive", None)


def _refresh_solver_algorithm_actionability_summary(audit: dict[str, Any]) -> None:
    attempts = _as_nonnegative_int(audit.get("solver_algorithm_move_attempts"))
    accepted = _as_nonnegative_int(audit.get("solver_algorithm_accepted_moves"))
    improving = _as_nonnegative_int(audit.get("solver_algorithm_improving_moves"))
    best_delta = _as_nonnegative_float(audit.get("solver_algorithm_best_delta"))
    iterations = _as_nonnegative_int(audit.get("solver_algorithm_search_iterations"))
    elapsed_ms = _as_nonnegative_int(audit.get("solver_algorithm_elapsed_ms"))
    time_limit_ms = _as_nonnegative_int(audit.get("solver_algorithm_time_limit_ms"))
    stop_reason = str(audit.get("solver_algorithm_stop_reason") or "").strip()
    budget_hit = bool(audit.get("solver_algorithm_runtime_budget_hit")) or (
        stop_reason == "time_limit"
    )
    if time_limit_ms > 0 and elapsed_ms >= int(time_limit_ms * 0.98):
        budget_hit = True

    progress = audit.get("solver_algorithm_solution_progress")
    if not isinstance(progress, dict) or not progress:
        progress = _solution_progress_template()
        audit["solver_algorithm_solution_progress"] = progress

    phase_attempts = _dict_ints(audit.get("solver_algorithm_phase_move_attempts"))
    phase_accepts = _dict_ints(audit.get("solver_algorithm_phase_accepted_moves"))
    phase_improvements = _dict_ints(
        audit.get("solver_algorithm_phase_improvement_counts")
    )
    phase_best_delta = _dict_floats(audit.get("solver_algorithm_phase_best_delta"))
    phase_delta_sum = _dict_floats(audit.get("solver_algorithm_phase_delta_sum"))
    phase_runtime = _dict_ints(audit.get("solver_algorithm_phase_runtime_ms"))
    context_records = _dict_ints(audit.get("solver_algorithm_context_records"))

    phases: dict[str, Any] = {}
    phase_names = set(phase_attempts) | set(phase_accepts) | set(phase_improvements)
    phase_names |= set(phase_best_delta) | set(phase_delta_sum) | set(phase_runtime)
    for record_name in context_records:
        if record_name.endswith("_iterations"):
            phase_names.add(record_name[: -len("_iterations")])
    phase_names.discard("none")
    phase_names.discard("inactive")
    no_effect_phase_count = 0
    no_accept_phase_count = 0
    for phase in sorted(phase_names):
        phase_iteration_count = context_records.get(f"{phase}_iterations", 0)
        phase_attempt_count = phase_attempts.get(phase, 0)
        phase_accept_count = phase_accepts.get(phase, 0)
        phase_improvement_count = phase_improvements.get(phase, 0)
        phase_best = phase_best_delta.get(phase, 0.0)
        phase_attempted = (
            phase_attempt_count > 0
            or phase_iteration_count > 0
            or phase_runtime.get(phase, 0) > 0
        )
        measurable_effect = phase_improvement_count > 0 or phase_best > 0.0
        if phase_attempted and phase_accept_count <= 0:
            status = "attempted_no_acceptance"
            no_accept_phase_count += 1
        elif phase_accept_count > 0 and not measurable_effect:
            status = "accepted_no_measurable_objective_effect"
            no_effect_phase_count += 1
        elif measurable_effect:
            status = "measurable_objective_effect"
        else:
            status = "observed_no_move"
        phases[phase] = {
            "status": status,
            "attempted": bool(phase_attempted),
            "move_attempts": phase_attempt_count,
            "accepted_moves": phase_accept_count,
            "iterations": phase_iteration_count,
            "runtime_ms": phase_runtime.get(phase, 0),
            "improvement_count": phase_improvement_count,
            "best_delta": phase_best,
            "delta_sum": phase_delta_sum.get(phase, 0.0),
        }

    no_measurable_effect = attempts > 0 and improving <= 0 and best_delta <= 0.0
    audit["solver_algorithm_runtime_budget_hit"] = bool(budget_hit)
    best_update_summary = audit.get("solver_algorithm_best_update_summary")
    if not isinstance(best_update_summary, dict):
        best_update_summary = _best_update_summary_template()
        audit["solver_algorithm_best_update_summary"] = best_update_summary
    audit["solver_algorithm_actionability_summary"] = {
        "schema": "scion.cvrp.solver_actionability.v1",
        "attempted": bool(attempts > 0 or iterations > 0),
        "move_attempts": attempts,
        "accepted_moves": accepted,
        "no_accepted_moves": bool(attempts > 0 and accepted <= 0),
        "accepted_no_measurable_objective_effect": bool(
            accepted > 0 and improving <= 0 and best_delta <= 0.0
        ),
        "candidate_emitted_no_measurable_objective_effect": bool(
            no_measurable_effect
        ),
        "improving_moves": improving,
        "best_delta": best_delta,
        "runtime_budget_hit": bool(budget_hit),
        "stop_reason": stop_reason or "inactive",
        "elapsed_ms": elapsed_ms,
        "time_limit_ms": time_limit_ms,
        "route_count_delta_final_minus_initial": progress.get(
            "route_count_delta_final_minus_initial"
        ),
        "total_distance_delta_final_minus_initial": progress.get(
            "total_distance_delta_final_minus_initial"
        ),
        "total_distance_improvement_from_initial": progress.get(
            "total_distance_improvement_from_initial"
        ),
        "phase_no_acceptance_count": no_accept_phase_count,
        "phase_no_measurable_effect_count": no_effect_phase_count,
        "best_update_summary": best_update_summary,
        "phases": phases,
    }


def _solution_progress_template() -> dict[str, Any]:
    return {
        "initial_route_count": None,
        "final_route_count": None,
        "route_count_delta_final_minus_initial": None,
        "initial_total_distance": None,
        "final_total_distance": None,
        "total_distance_delta_final_minus_initial": None,
        "total_distance_improvement_from_initial": None,
    }


def _actionability_summary_template() -> dict[str, Any]:
    return {
        "schema": "scion.cvrp.solver_actionability.v1",
        "attempted": False,
        "move_attempts": 0,
        "accepted_moves": 0,
        "no_accepted_moves": False,
        "accepted_no_measurable_objective_effect": False,
        "candidate_emitted_no_measurable_objective_effect": False,
        "improving_moves": 0,
        "best_delta": 0.0,
        "runtime_budget_hit": False,
        "stop_reason": "inactive",
        "elapsed_ms": 0,
        "time_limit_ms": 0,
        "route_count_delta_final_minus_initial": None,
        "total_distance_delta_final_minus_initial": None,
        "total_distance_improvement_from_initial": None,
        "phase_no_acceptance_count": 0,
        "phase_no_measurable_effect_count": 0,
        "best_update_summary": _best_update_summary_template(),
        "phases": {},
    }


def _best_update_summary_template() -> dict[str, Any]:
    return {
        "schema": "scion.cvrp.best_update_summary.v1",
        "best_update_count": 0,
        "first_elapsed_ms": None,
        "last_elapsed_ms": None,
        "first_iteration": None,
        "last_iteration": None,
        "update_density_per_1000_iterations": 0.0,
        "phase_counts": {},
        "operator_counts": {},
        "operator_pair_counts": {},
    }


def _refresh_solver_algorithm_best_update_summary(
    audit: dict[str, Any],
    event: Mapping[str, Any],
) -> None:
    summary = audit.setdefault(
        "solver_algorithm_best_update_summary",
        _best_update_summary_template(),
    )
    if not isinstance(summary, dict):
        summary = _best_update_summary_template()
        audit["solver_algorithm_best_update_summary"] = summary
    count = _as_nonnegative_int(summary.get("best_update_count")) + 1
    summary["best_update_count"] = count
    elapsed_ms = _as_nonnegative_int(event.get("elapsed_ms"))
    iteration = _as_nonnegative_int(event.get("iteration"))
    if summary.get("first_elapsed_ms") is None:
        summary["first_elapsed_ms"] = elapsed_ms
    if summary.get("first_iteration") is None:
        summary["first_iteration"] = iteration
    summary["last_elapsed_ms"] = elapsed_ms
    summary["last_iteration"] = iteration

    total_iterations = _as_nonnegative_int(
        audit.get("solver_algorithm_search_iterations")
    )
    if total_iterations > 0:
        summary["update_density_per_1000_iterations"] = (
            count * 1000.0 / total_iterations
        )
    else:
        summary["update_density_per_1000_iterations"] = 0.0

    phase_counts = summary.setdefault("phase_counts", {})
    if not isinstance(phase_counts, dict):
        phase_counts = {}
        summary["phase_counts"] = phase_counts
    phase = str(event.get("phase") or "search")
    phase_counts[phase] = _as_nonnegative_int(phase_counts.get(phase)) + 1

    operator_counts = summary.setdefault("operator_counts", {})
    if not isinstance(operator_counts, dict):
        operator_counts = {}
        summary["operator_counts"] = operator_counts
    operator = str(event.get("operator") or "").strip()
    if operator:
        operator_counts[operator] = (
            _as_nonnegative_int(operator_counts.get(operator)) + 1
        )

    pair_counts = summary.setdefault("operator_pair_counts", {})
    if not isinstance(pair_counts, dict):
        pair_counts = {}
        summary["operator_pair_counts"] = pair_counts
    pair = str(event.get("operator_pair") or "").strip()
    if pair:
        pair_counts[pair] = _as_nonnegative_int(pair_counts.get(pair)) + 1


def _dict_ints(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _as_nonnegative_int(item) for key, item in value.items()}


def _dict_floats(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _as_nonnegative_float(item) for key, item in value.items()}


def _as_nonnegative_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, number)


def _optional_nonnegative_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, number)


def _as_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)
