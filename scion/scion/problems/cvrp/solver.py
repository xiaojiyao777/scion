"""CVRP solver wrapper used by Scion campaigns.

The wrapper owns the Scion operator boundary. For real CVRPLIB ``.vrp`` runs it
uses the repository CVRP baseline under ``vrp/src`` when available, then applies
generated Scion operators as a bounded post-baseline improvement layer. JSON
fixtures keep the small deterministic construction path used by tests.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Mapping

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution


_MAX_OPERATOR_ROUNDS = 20
_OBJECTIVE_TOLERANCE = 1e-9
_BASELINE_TIME_FRACTION = 0.8


def solve(instance: CvrpInstance, rng: random.Random) -> CvrpSolution:
    """Capacity-aware nearest-neighbor construction for small fixtures."""
    unvisited = set(instance.customer_ids)
    routes: list[tuple[int, ...]] = []
    while unvisited:
        route: list[int] = []
        load = 0
        current = instance.depot
        while True:
            feasible = [
                c for c in unvisited
                if load + instance.demand(c) <= instance.capacity
            ]
            if not feasible:
                break
            nxt = min(
                feasible,
                key=lambda c: (instance.distance(current, c), rng.random()),
            )
            unvisited.remove(nxt)
            route.append(nxt)
            load += instance.demand(nxt)
            current = nxt
        if not route:
            raise ValueError("remaining customer demand exceeds vehicle capacity")
        routes.append(tuple(route))
    return CvrpSolution(routes=tuple(routes))


def solve_baseline(
    *,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
) -> tuple[CvrpSolution, dict[str, Any]]:
    """Return a baseline solution plus audit metadata.

    Real formal CVRP campaigns are configured with a SCION data-root environment
    variable pointing at the repo-local ``vrp`` directory. In that case this
    wrapper uses the imported ALNS+VNS baseline. Synthetic fixtures and JSON
    smoke tests fall back to the deterministic Scion construction.
    """

    resolved = Path(instance_path)
    baseline_root = _find_vrp_baseline_root()
    baseline_required = resolved.suffix.lower() == ".vrp" and baseline_root is not None
    if resolved.suffix.lower() == ".vrp" and baseline_root is not None:
        budget = _baseline_time_budget(time_limit_sec)
        try:
            solution, audit = _solve_with_vrp_baseline(
                instance=instance,
                instance_path=resolved,
                seed=seed,
                time_limit_sec=budget,
                baseline_root=baseline_root,
                baseline_required=baseline_required,
            )
            return solution, audit
        except Exception as exc:
            # Synthetic fixtures and developer machines may not have the full
            # baseline dependency path available. The audit keeps the fallback
            # visible; formal runs should treat repeated fallback as a setup
            # problem before interpreting quality.
            fallback = solve(instance, rng)
            return fallback, {
                "baseline_mode": "scion_nearest_neighbor_fallback",
                "baseline_required": baseline_required,
                "baseline_error": f"{type(exc).__name__}: {exc}",
                "baseline_budget_s": budget,
                "baseline_routes": len(fallback.routes),
                "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
            }
    if resolved.suffix.lower() == ".vrp" and baseline_required:
        fallback = solve(instance, rng)
        return fallback, {
            "baseline_mode": "scion_nearest_neighbor_fallback",
            "baseline_required": True,
            "baseline_error": "vrp/src baseline not available for configured CVRP data root",
            "baseline_routes": len(fallback.routes),
            "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
        }

    fallback = solve(instance, rng)
    return fallback, {
        "baseline_mode": "scion_nearest_neighbor",
        "baseline_required": False,
        "baseline_routes": len(fallback.routes),
        "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
    }


def improve_with_registry_operators(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    registry_path: str,
    workspace_root: str | Path,
    time_limit_sec: float,
    start_time: float,
) -> tuple[CvrpSolution, dict[str, Any]]:
    """Apply registry operators with bounded, auditable acceptance."""

    audit: dict[str, Any] = {
        "operator_registry_path": registry_path or "",
        "operator_loaded": 0,
        "operator_attempts": 0,
        "operator_accepted": 0,
        "operator_skipped": 0,
        "operator_errors": 0,
        "operator_invalid_outputs": 0,
        "operator_rounds": 0,
        "operator_events": [],
    }
    operators = _load_registry_operators(
        registry_path=registry_path,
        workspace_root=workspace_root,
        audit=audit,
    )
    if not operators:
        return solution, audit

    current = solution
    current_objective = _objective_for_solution(adapter, instance, current)
    fatal_operator_failure = False
    for round_index in range(_MAX_OPERATOR_ROUNDS):
        if _time_exhausted(start_time, time_limit_sec):
            break
        audit["operator_rounds"] = round_index + 1
        for operator in operators:
            if _time_exhausted(start_time, time_limit_sec):
                break
            audit["operator_attempts"] += 1
            try:
                candidate = operator.instance.execute(current, instance, rng)
            except Exception as exc:
                audit["operator_errors"] += 1
                _record_event(audit, operator.name, "error", str(exc))
                fatal_operator_failure = True
                continue

            candidate_solution = _coerce_solution(candidate)
            if candidate_solution is None:
                audit["operator_skipped"] += 1
                audit["operator_errors"] += 1
                audit["operator_invalid_outputs"] += 1
                _record_event(audit, operator.name, "error", "returned invalid solution object")
                fatal_operator_failure = True
                continue

            valid, reason = _solution_is_valid(adapter, instance, candidate_solution)
            if not valid:
                audit["operator_skipped"] += 1
                audit["operator_errors"] += 1
                audit["operator_invalid_outputs"] += 1
                _record_event(audit, operator.name, "error", reason)
                fatal_operator_failure = True
                continue

            candidate_objective = _objective_for_solution(adapter, instance, candidate_solution)
            if _lexicographic_improves(candidate_objective, current_objective):
                current = candidate_solution
                current_objective = candidate_objective
                audit["operator_accepted"] += 1
                _record_event(audit, operator.name, "accepted", "")
            else:
                audit["operator_skipped"] += 1
                _record_event(audit, operator.name, "skipped", "not an improvement")
        if fatal_operator_failure:
            break
    return current, audit


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--registry", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    start = time.perf_counter()

    class _Spec:
        pass

    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance_path = _resolve_instance_path(args.instance)
    instance = adapter.load_instance(instance_path)
    rng = random.Random(args.seed)
    sol, baseline_audit = solve_baseline(
        instance=instance,
        instance_path=instance_path,
        seed=args.seed,
        rng=rng,
        time_limit_sec=args.time_limit,
    )
    sol, operator_audit = improve_with_registry_operators(
        sol,
        instance,
        adapter=adapter,
        rng=rng,
        registry_path=args.registry,
        workspace_root=Path.cwd(),
        time_limit_sec=args.time_limit,
        start_time=start,
    )
    raw = {"routes": [list(route) for route in sol.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    objective = dict(adapter.recompute_objective(artifact, instance))
    raw["objective"] = objective
    raw["runtime"] = {
        "elapsed_s": time.perf_counter() - start,
        "time_limit_s": args.time_limit,
        **baseline_audit,
        **operator_audit,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


class _LoadedOperator:
    def __init__(self, name: str, weight: float, instance: Any, order: int) -> None:
        self.name = name
        self.weight = weight
        self.instance = instance
        self.order = order


def _load_registry_operators(
    *,
    registry_path: str,
    workspace_root: str | Path,
    audit: dict[str, Any],
) -> tuple[_LoadedOperator, ...]:
    if not registry_path:
        return tuple()
    path = Path(registry_path)
    if not path.exists():
        return tuple()

    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", f"registry read failed: {exc}")
        return tuple()

    raw_operators = payload.get("operators", []) if isinstance(payload, Mapping) else []
    if not isinstance(raw_operators, list):
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", "operators field is not a list")
        return tuple()

    workspace = Path(workspace_root).resolve()
    loaded: list[_LoadedOperator] = []
    for index, entry in enumerate(raw_operators):
        if not isinstance(entry, Mapping):
            audit["operator_skipped"] += 1
            _record_event(audit, f"entry-{index}", "skipped", "registry entry is not a mapping")
            continue
        name = str(entry.get("name") or f"operator-{index}")
        file_path = str(entry.get("file_path") or "").strip()
        class_name = str(entry.get("class_name") or "").strip()
        weight = _coerce_weight(entry.get("weight"))
        target = _operator_path(workspace, file_path)
        if target is None:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator path escapes workspace")
            continue
        if not class_name:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "missing class_name")
            continue
        if not target.is_file():
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", f"operator file not found: {file_path}")
            continue
        try:
            instance = _load_operator_instance(target, class_name, index)
        except Exception as exc:
            audit["operator_errors"] += 1
            _record_event(audit, name, "error", str(exc))
            continue
        if not hasattr(instance, "execute"):
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator has no execute method")
            continue
        loaded.append(_LoadedOperator(name=name, weight=weight, instance=instance, order=index))

    loaded.sort(key=lambda op: (-op.weight, op.order))
    audit["operator_loaded"] = len(loaded)
    return tuple(loaded)


def _resolve_instance_path(instance_path: str) -> str:
    """Resolve formal-run case paths without copying benchmark data into workspaces."""

    path = Path(instance_path)
    if path.is_absolute() or path.exists():
        return str(path)

    for data_root in _configured_data_roots():
        candidate = data_root / path
        if candidate.exists():
            return str(candidate)
    return instance_path


def _find_vrp_baseline_root() -> Path | None:
    for candidate in _configured_data_roots():
        if (candidate / "src" / "solver.py").is_file():
            return candidate
    return None


def _configured_data_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for name in ("SCION_PROBLEM_DATA_ROOT", "SCION_CVRP_DATA_ROOT"):
        value = os.environ.get(name, "").strip()
        if value:
            roots.append(Path(value))
    return tuple(roots)


def _baseline_time_budget(time_limit_sec: float) -> float:
    if time_limit_sec <= 0:
        return 0.0
    return max(0.05, float(time_limit_sec) * _BASELINE_TIME_FRACTION)


def _solve_with_vrp_baseline(
    *,
    instance: CvrpInstance,
    instance_path: Path,
    seed: int,
    time_limit_sec: float,
    baseline_root: Path,
    baseline_required: bool,
) -> tuple[CvrpSolution, dict[str, Any]]:
    root = str(baseline_root)
    if root not in sys.path:
        sys.path.insert(0, root)

    from src.parser import parse_vrp  # type: ignore
    from src.solver import solve as solve_vrp  # type: ignore

    vrp_instance = parse_vrp(str(instance_path))
    allowed_routes = instance.allowed_routes
    if allowed_routes is None:
        allowed_routes = instance.bks_routes
    result = solve_vrp(
        vrp_instance,
        time_limit=time_limit_sec,
        seed=seed,
        max_routes=allowed_routes,
    )
    routes = tuple(
        tuple(
            _map_vrp_customer_to_scion(
                int(customer),
                vrp_instance.depot,
                vrp_instance.dimension,
            )
            for customer in route.customers
        )
        for route in result.solution.routes
        if route.customers
    )
    solution = CvrpSolution(routes=routes)
    audit = {
        "baseline_mode": "vrp_alns_vns",
        "baseline_required": baseline_required,
        "baseline_budget_s": time_limit_sec,
        "baseline_elapsed_s": result.elapsed,
        "baseline_iterations": result.iterations,
        "baseline_cost": result.best_cost,
        "baseline_routes": len(routes),
    }
    valid, reason = _solution_is_valid(CvrpAdapter(object()), instance, solution)
    if not valid:
        raise ValueError(f"vrp baseline produced invalid Scion solution: {reason}")
    return solution, audit


def _map_vrp_customer_to_scion(customer: int, depot: int, dimension: int) -> int:
    """Map vrp/src zero-based node ids to Scion's depot-first id space."""
    raw_id = customer + 1
    raw_depot_id = depot + 1
    if raw_id == raw_depot_id:
        return 0
    scion_id = 1
    for candidate_raw_id in range(1, dimension + 1):
        if candidate_raw_id == raw_depot_id:
            continue
        if candidate_raw_id == raw_id:
            return scion_id
        scion_id += 1
    raise ValueError(f"unknown vrp customer id {customer}")


def _operator_path(workspace: Path, file_path: str) -> Path | None:
    if not file_path:
        return None
    rel = Path(file_path)
    if rel.is_absolute():
        return None
    target = (workspace / rel).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        return None
    return target


def _load_operator_instance(path: Path, class_name: str, index: int) -> Any:
    module_name = f"_scion_cvrp_operator_{index}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    cls = getattr(module, class_name)
    return cls()


def _coerce_weight(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _coerce_solution(candidate: Any) -> CvrpSolution | None:
    """Accept canonical or structurally equivalent CvrpSolution objects.

    Generated operators commonly import ``CvrpSolution`` from workspace-local
    ``models.py`` while the solver imports the package model. Those are distinct
    class objects in Python, but the solution contract is structural: a routes
    tuple of customer-id sequences. Coercing here preserves the adapter boundary
    while still rejecting genuinely invalid outputs fail-closed.
    """

    if isinstance(candidate, CvrpSolution):
        return candidate
    routes = getattr(candidate, "routes", None)
    if routes is None:
        return None
    try:
        normalized = tuple(
            tuple(int(customer) for customer in route)
            for route in routes
        )
    except (TypeError, ValueError):
        return None
    return CvrpSolution(routes=normalized)


def _solution_is_valid(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> tuple[bool, str]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    try:
        artifact = adapter.deserialize_solver_output(raw, instance)
        raw["objective"] = dict(adapter.recompute_objective(artifact, instance))
        artifact = adapter.deserialize_solver_output(raw, instance)
        consistency = adapter.check_solution_consistency(artifact, instance)
        if not consistency.passed:
            return False, "; ".join(consistency.reasons[:3])
        feasibility = adapter.check_feasibility(artifact, instance)
        if not feasibility.passed:
            return False, "; ".join(feasibility.reasons[:3])
    except Exception as exc:
        return False, str(exc)
    return True, ""


def _objective_for_solution(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> dict[str, int | float]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    return dict(adapter.recompute_objective(artifact, instance))


def _lexicographic_improves(
    candidate: Mapping[str, int | float],
    current: Mapping[str, int | float],
) -> bool:
    candidate_fleet = float(candidate.get("fleet_violation", 0))
    current_fleet = float(current.get("fleet_violation", 0))
    if candidate_fleet < current_fleet:
        return True
    if candidate_fleet > current_fleet:
        return False
    candidate_distance = float(candidate.get("total_distance", 0.0))
    current_distance = float(current.get("total_distance", 0.0))
    return candidate_distance < current_distance - _OBJECTIVE_TOLERANCE


def _time_exhausted(start_time: float, time_limit_sec: float) -> bool:
    if time_limit_sec <= 0:
        return False
    return time.perf_counter() - start_time >= time_limit_sec


def _record_event(
    audit: dict[str, Any],
    operator_name: str,
    status: str,
    detail: str,
) -> None:
    events = audit["operator_events"]
    if len(events) >= 20:
        return
    payload = {"operator": operator_name, "status": status}
    if detail:
        payload["detail"] = detail
    events.append(payload)


if __name__ == "__main__":
    _main()
