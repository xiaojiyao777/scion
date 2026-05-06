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
import math
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
_MIN_BASELINE_TIME_FRACTION = 0.2
_MAX_BASELINE_TIME_FRACTION = 0.95
_SEARCH_POLICY_RELATIVE_PATH = "policies/search_policy.py"
_CONSTRUCTION_POLICY_RELATIVE_PATH = "policies/construction_policy.py"
_NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH = "policies/neighborhood_portfolio.py"
_DEFAULT_CONSTRUCTION_MODE = "nearest_neighbor"
_DEFAULT_CONSTRUCTION_BIAS = 0.0
_MIN_CONSTRUCTION_BIAS = 0.0
_MAX_CONSTRUCTION_BIAS = 1.0
_MAX_COMPONENT_WEIGHT = 5.0
_MAX_PORTFOLIO_TOP_K = 1000
_MAX_PORTFOLIO_ATTEMPTS = 1_000_000
_ALLOWED_PORTFOLIO_COMPONENTS = frozenset(
    {
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
    }
)
_DEFAULT_ENABLED_COMPONENTS = tuple(sorted(_ALLOWED_PORTFOLIO_COMPONENTS))
_DEFAULT_COMPONENT_WEIGHTS = {
    component: 1.0 for component in _DEFAULT_ENABLED_COMPONENTS
}
_DEFAULT_CANDIDATE_LIMITS = {
    "max_rounds": _MAX_OPERATOR_ROUNDS,
    "top_k": _MAX_PORTFOLIO_TOP_K,
    "total_attempts": _MAX_PORTFOLIO_ATTEMPTS,
    "per_component_attempts": _MAX_PORTFOLIO_ATTEMPTS,
}
_ALLOWED_CONSTRUCTION_MODES = frozenset(
    {
        "nearest_neighbor",
        "nearest_neighbor_demand_bias",
        "demand_descending",
        "sequential",
    }
)


def solve(
    instance: CvrpInstance,
    rng: random.Random,
    *,
    construction_mode: str = _DEFAULT_CONSTRUCTION_MODE,
    construction_bias: float = _DEFAULT_CONSTRUCTION_BIAS,
) -> CvrpSolution:
    """Capacity-aware nearest-neighbor construction for small fixtures."""
    mode = construction_mode
    if mode not in _ALLOWED_CONSTRUCTION_MODES:
        mode = _DEFAULT_CONSTRUCTION_MODE
    bias = min(max(float(construction_bias), _MIN_CONSTRUCTION_BIAS), _MAX_CONSTRUCTION_BIAS)
    max_demand = max((instance.demand(c) for c in instance.customer_ids), default=1)
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
            nxt = _select_construction_customer(
                feasible,
                instance=instance,
                current=current,
                rng=rng,
                mode=mode,
                bias=bias,
                max_demand=max_demand,
            )
            unvisited.remove(nxt)
            route.append(nxt)
            load += instance.demand(nxt)
            current = nxt
        if not route:
            raise ValueError("remaining customer demand exceeds vehicle capacity")
        routes.append(tuple(route))
    return CvrpSolution(routes=tuple(routes))


def _select_construction_customer(
    feasible: list[int],
    *,
    instance: CvrpInstance,
    current: int,
    rng: random.Random,
    mode: str,
    bias: float,
    max_demand: int,
) -> int:
    if mode == "sequential":
        return min(feasible)
    if mode == "demand_descending":
        return min(
            feasible,
            key=lambda c: (
                -instance.demand(c),
                instance.distance(current, c),
                rng.random(),
            ),
        )
    if mode == "nearest_neighbor_demand_bias":
        demand_scale = max(float(max_demand), 1.0)
        return min(
            feasible,
            key=lambda c: (
                instance.distance(current, c)
                - bias * (float(instance.demand(c)) / demand_scale),
                rng.random(),
            ),
        )
    return min(
        feasible,
        key=lambda c: (instance.distance(current, c), rng.random()),
    )


def solve_baseline(
    *,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    baseline_time_fraction: float = _BASELINE_TIME_FRACTION,
    construction_policy: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    """Return a baseline solution plus audit metadata.

    Real formal CVRP campaigns are configured with a SCION data-root environment
    variable pointing at the repo-local ``vrp`` directory. In that case this
    wrapper uses the imported ALNS+VNS baseline. Synthetic fixtures and JSON
    smoke tests fall back to the deterministic Scion construction.
    """

    construction_solution, construction_audit = _construct_with_policy_audit(
        instance=instance,
        rng=rng,
        construction_policy=construction_policy,
    )
    resolved = Path(instance_path).resolve(strict=False)
    is_vrp = resolved.suffix.lower() == ".vrp"
    baseline_root = _find_vrp_baseline_root()
    baseline_required = is_vrp and _baseline_required_for_instance(resolved)
    if is_vrp and baseline_required and baseline_root is not None:
        budget = _baseline_time_budget(time_limit_sec, baseline_time_fraction)
        try:
            solution, audit = _solve_with_vrp_baseline(
                instance=instance,
                instance_path=resolved,
                seed=seed,
                time_limit_sec=budget,
                baseline_root=baseline_root,
                baseline_required=baseline_required,
            )
            return solution, {**construction_audit, **audit}
        except Exception as exc:
            fallback = construction_solution
            return fallback, {
                **construction_audit,
                "baseline_mode": "scion_nearest_neighbor_fallback",
                "baseline_required": baseline_required,
                "baseline_error": f"{type(exc).__name__}: {exc}",
                "baseline_budget_s": budget,
                "baseline_routes": len(fallback.routes),
                "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
            }
    if is_vrp and baseline_required:
        fallback = construction_solution
        return fallback, {
            **construction_audit,
            "baseline_mode": "scion_nearest_neighbor_fallback",
            "baseline_required": True,
            "baseline_error": "vrp/src baseline not available for configured CVRP data root",
            "baseline_routes": len(fallback.routes),
            "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
        }

    fallback = construction_solution
    return fallback, {
        **construction_audit,
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
    max_operator_rounds: int = _MAX_OPERATOR_ROUNDS,
    post_baseline_operators_enabled: bool = True,
    neighborhood_portfolio: dict[str, Any] | None = None,
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
        "operator_no_improvement_rounds": 0,
        "operator_rounds_with_acceptance": 0,
        "operator_stop_reason": "",
        "operator_events": [],
    }
    portfolio_audit = _portfolio_audit_defaults(neighborhood_portfolio)
    audit.update(portfolio_audit)
    if not post_baseline_operators_enabled:
        audit["operator_stop_reason"] = "disabled_by_policy"
        audit["portfolio_stop_reason"] = "disabled_by_search_policy"
        return solution, audit

    operators = _load_registry_operators(
        registry_path=registry_path,
        workspace_root=workspace_root,
        audit=audit,
    )
    operators = _apply_neighborhood_portfolio(
        operators,
        audit=audit,
        max_operator_rounds=max_operator_rounds,
    )
    if not operators:
        if not audit["portfolio_stop_reason"]:
            if not registry_path or audit["operator_loaded"] == 0:
                audit["portfolio_stop_reason"] = "no_registry_operators"
            else:
                audit["portfolio_stop_reason"] = "no_enabled_components"
        return solution, audit

    current = solution
    current_objective = _objective_for_solution(adapter, instance, current)
    fatal_operator_failure = False
    max_operator_rounds = int(audit["portfolio_effective_round_limit"])
    for round_index in range(max_operator_rounds):
        if _time_exhausted(start_time, time_limit_sec):
            audit["operator_stop_reason"] = "time_limit"
            audit["portfolio_stop_reason"] = "time_limit"
            break
        round_accepted = 0
        round_completed = True
        audit["operator_rounds"] = round_index + 1
        for operator in operators:
            if _time_exhausted(start_time, time_limit_sec):
                audit["operator_stop_reason"] = "time_limit"
                audit["portfolio_stop_reason"] = "time_limit"
                round_completed = False
                break
            if _portfolio_attempt_limit_reached(audit, operator.component):
                audit["operator_stop_reason"] = "portfolio_attempt_limit"
                audit["portfolio_stop_reason"] = "attempt_limit"
                round_completed = False
                break
            audit["operator_attempts"] += 1
            component_attempts = audit["component_attempts"]
            component_attempts[operator.component] = (
                _as_nonnegative_int(component_attempts.get(operator.component)) + 1
            )
            op_start_ns = time.monotonic_ns()
            try:
                candidate = operator.instance.execute(current, instance, rng)
            except Exception as exc:
                _record_component_runtime(audit, operator.component, op_start_ns)
                audit["operator_errors"] += 1
                _record_event(audit, operator.name, "error", str(exc))
                fatal_operator_failure = True
                continue
            _record_component_runtime(audit, operator.component, op_start_ns)

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
                component_accepted = audit["component_accepted"]
                component_accepted[operator.component] = (
                    _as_nonnegative_int(component_accepted.get(operator.component)) + 1
                )
                round_accepted += 1
                _record_event(audit, operator.name, "accepted", "")
            else:
                audit["operator_skipped"] += 1
                _record_event(audit, operator.name, "skipped", "not an improvement")
        if round_accepted > 0:
            audit["operator_rounds_with_acceptance"] += 1
        elif round_completed and not fatal_operator_failure:
            audit["operator_no_improvement_rounds"] += 1
        if fatal_operator_failure:
            audit["operator_stop_reason"] = "fatal_operator_failure"
            audit["portfolio_stop_reason"] = "fatal_operator_failure"
            break
        if audit["operator_stop_reason"] == "time_limit":
            break
        if audit["operator_stop_reason"] == "portfolio_attempt_limit":
            break
        if round_completed and round_accepted == 0:
            audit["operator_stop_reason"] = "no_improvement_round"
            audit["portfolio_stop_reason"] = "no_improvement_round"
            break
    else:
        audit["operator_stop_reason"] = "max_operator_rounds"
        audit["portfolio_stop_reason"] = "max_operator_rounds"
    if not audit["portfolio_stop_reason"]:
        audit["portfolio_stop_reason"] = audit["operator_stop_reason"] or "completed"
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
    search_policy = _load_search_policy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    construction_policy = _load_construction_policy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    neighborhood_portfolio = _load_neighborhood_portfolio(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    sol, baseline_audit = solve_baseline(
        instance=instance,
        instance_path=instance_path,
        seed=args.seed,
        rng=rng,
        time_limit_sec=args.time_limit,
        baseline_time_fraction=search_policy["baseline_time_fraction"],
        construction_policy=construction_policy,
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
        max_operator_rounds=search_policy["operator_round_limit"],
        post_baseline_operators_enabled=search_policy[
            "post_baseline_operators_enabled"
        ],
        neighborhood_portfolio=neighborhood_portfolio,
    )
    raw = {"routes": [list(route) for route in sol.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    objective = dict(adapter.recompute_objective(artifact, instance))
    raw["objective"] = objective
    raw["runtime"] = {
        "elapsed_s": time.perf_counter() - start,
        "time_limit_s": args.time_limit,
        **search_policy,
        **baseline_audit,
        **operator_audit,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


class _LoadedOperator:
    def __init__(
        self,
        name: str,
        weight: float,
        instance: Any,
        order: int,
        component: str,
    ) -> None:
        self.name = name
        self.weight = weight
        self.instance = instance
        self.order = order
        self.component = component


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
        component = _operator_component(entry, instance)
        loaded.append(
            _LoadedOperator(
                name=name,
                weight=weight,
                instance=instance,
                order=index,
                component=component,
            )
        )

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


def _baseline_required_for_instance(instance_path: Path) -> bool:
    for data_root in _configured_data_roots():
        try:
            instance_path.relative_to(data_root)
        except ValueError:
            continue
        return True
    return False


def _configured_data_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for name in ("SCION_PROBLEM_DATA_ROOT", "SCION_CVRP_DATA_ROOT"):
        value = os.environ.get(name, "").strip()
        if value:
            roots.append(Path(value).expanduser().resolve(strict=False))
    return tuple(roots)


def _load_construction_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "construction_policy_path": _CONSTRUCTION_POLICY_RELATIVE_PATH,
        "construction_surface_loaded": False,
        "construction_errors": 0,
        "construction_events": [],
        "construction_mode": _DEFAULT_CONSTRUCTION_MODE,
        "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
    }
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _CONSTRUCTION_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_construction_event(audit, "error", "construction policy path escapes workspace")
        audit["construction_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction policy load failed: {exc}",
        )
        return audit

    audit["construction_surface_loaded"] = True
    audit["construction_mode"] = _construction_mode(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["construction_bias"] = _construction_bias(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _construct_with_policy_audit(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_policy: dict[str, Any] | None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    audit = dict(construction_policy or {})
    if not audit:
        audit = {
            "construction_policy_path": _CONSTRUCTION_POLICY_RELATIVE_PATH,
            "construction_surface_loaded": False,
            "construction_errors": 0,
            "construction_events": [],
            "construction_mode": _DEFAULT_CONSTRUCTION_MODE,
            "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
        }
    audit.setdefault("construction_errors", 0)
    audit.setdefault("construction_events", [])
    audit.setdefault("construction_mode", _DEFAULT_CONSTRUCTION_MODE)
    audit.setdefault("construction_bias", _DEFAULT_CONSTRUCTION_BIAS)

    start_ns = time.monotonic_ns()
    try:
        solution = solve(
            instance,
            rng,
            construction_mode=str(audit["construction_mode"]),
            construction_bias=float(audit["construction_bias"]),
        )
    except Exception as exc:
        audit["construction_errors"] = _as_nonnegative_int(audit["construction_errors"]) + 1
        _record_construction_event(
            audit,
            "error",
            f"construction failed for mode={audit['construction_mode']!r}: {exc}",
        )
        if audit["construction_mode"] == _DEFAULT_CONSTRUCTION_MODE:
            raise
        solution = solve(instance, rng)

    audit["construction_elapsed_ms"] = int((time.monotonic_ns() - start_ns) / 1_000_000)
    audit["construction_routes"] = len(solution.routes)
    audit["construction_distance"] = sum(
        instance.route_distance(route) for route in solution.routes
    )
    feasible, reason = _solution_is_valid(CvrpAdapter(object()), instance, solution)
    audit["construction_feasible"] = feasible
    if not feasible:
        audit["construction_errors"] = _as_nonnegative_int(audit["construction_errors"]) + 1
        _record_construction_event(audit, "error", f"construction infeasible: {reason}")
    return solution, audit


def _construction_mode(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> str:
    try:
        value = _call_policy_function(module, "construction_mode", instance, time_limit_sec)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(audit, "error", f"construction_mode failed: {exc}")
        return _DEFAULT_CONSTRUCTION_MODE
    if not isinstance(value, str):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_mode returned non-string value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_MODE
    mode = value.strip()
    if mode not in _ALLOWED_CONSTRUCTION_MODES:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_mode={mode!r} is not allowed",
        )
        return _DEFAULT_CONSTRUCTION_MODE
    return mode


def _construction_bias(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> float:
    try:
        value = _call_policy_function(module, "construction_bias", instance, time_limit_sec)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(audit, "error", f"construction_bias failed: {exc}")
        return _DEFAULT_CONSTRUCTION_BIAS
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_bias returned non-numeric value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_BIAS
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_bias returned non-finite value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_BIAS
    clamped = min(max(numeric, _MIN_CONSTRUCTION_BIAS), _MAX_CONSTRUCTION_BIAS)
    if clamped != numeric:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            "construction_bias="
            f"{numeric!r} outside [{_MIN_CONSTRUCTION_BIAS}, {_MAX_CONSTRUCTION_BIAS}], "
            "clamped",
        )
    return clamped


def _record_construction_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("construction_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _CONSTRUCTION_POLICY_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _as_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _load_neighborhood_portfolio(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _portfolio_audit_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_portfolio_event(audit, "error", "portfolio policy path escapes workspace")
        audit["portfolio_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"portfolio policy load failed: {exc}")
        return audit

    audit["portfolio_surface_loaded"] = True
    audit["enabled_components"] = _portfolio_enabled_components(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["component_weights"] = _portfolio_component_weights(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["candidate_limits"] = _portfolio_candidate_limits(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _portfolio_audit_defaults(
    portfolio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = dict(portfolio or {})
    audit.setdefault("portfolio_policy_path", _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH)
    audit.setdefault("portfolio_surface_loaded", False)
    audit.setdefault("portfolio_errors", 0)
    audit.setdefault("portfolio_events", [])
    audit.setdefault("enabled_components", list(_DEFAULT_ENABLED_COMPONENTS))
    audit.setdefault("component_weights", dict(_DEFAULT_COMPONENT_WEIGHTS))
    audit.setdefault("candidate_limits", dict(_DEFAULT_CANDIDATE_LIMITS))
    audit.setdefault(
        "component_attempts",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_accepted",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_runtime_ms",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault("portfolio_stop_reason", "")
    audit.setdefault(
        "portfolio_effective_round_limit",
        int(audit["candidate_limits"].get("max_rounds", _MAX_OPERATOR_ROUNDS))
        if isinstance(audit.get("candidate_limits"), Mapping)
        else _MAX_OPERATOR_ROUNDS,
    )
    return audit


def _portfolio_enabled_components(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> list[str]:
    try:
        value = _call_policy_function(module, "enabled_components", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"enabled_components failed: {exc}")
        return list(_DEFAULT_ENABLED_COMPONENTS)
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"enabled_components returned non-sequence value {value!r}",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)

    enabled: list[str] = []
    seen: set[str] = set()
    for item in value:
        component = str(item).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"enabled_components contains unknown component {component!r}",
            )
            continue
        if component not in seen:
            seen.add(component)
            enabled.append(component)
    if not enabled:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            "enabled_components produced no valid enabled components",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)
    return enabled


def _portfolio_component_weights(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, float]:
    weights = dict(_DEFAULT_COMPONENT_WEIGHTS)
    try:
        value = _call_policy_function(module, "component_weights", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"component_weights failed: {exc}")
        return weights
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"component_weights returned non-mapping value {value!r}",
        )
        return weights

    for raw_component, raw_weight in value.items():
        component = str(raw_component).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"component_weights contains unknown component {component!r}",
            )
            continue
        weight = _portfolio_float(
            raw_weight,
            default=weights[component],
            minimum=0.0,
            maximum=_MAX_COMPONENT_WEIGHT,
            field_name=f"component_weights[{component}]",
            audit=audit,
        )
        weights[component] = weight
    return weights


def _portfolio_candidate_limits(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, int]:
    limits = dict(_DEFAULT_CANDIDATE_LIMITS)
    try:
        value = _call_policy_function(module, "candidate_limits", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"candidate_limits failed: {exc}")
        return limits
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"candidate_limits returned non-mapping value {value!r}",
        )
        return limits

    known_limit_keys = {
        "max_rounds",
        "top_k",
        "total_attempts",
        "per_component_attempts",
    }
    for raw_key, raw_limit in value.items():
        key = str(raw_key).strip()
        if key in _ALLOWED_PORTFOLIO_COMPONENTS:
            limits[key] = _portfolio_int(
                raw_limit,
                default=limits.get(key, limits["per_component_attempts"]),
                minimum=0,
                maximum=_MAX_PORTFOLIO_ATTEMPTS,
                field_name=f"candidate_limits[{key}]",
                audit=audit,
            )
            continue
        if key not in known_limit_keys:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"candidate_limits contains unknown key {key!r}",
            )
            continue
        maximum = _MAX_OPERATOR_ROUNDS if key == "max_rounds" else _MAX_PORTFOLIO_ATTEMPTS
        if key == "top_k":
            maximum = _MAX_PORTFOLIO_TOP_K
        limits[key] = _portfolio_int(
            raw_limit,
            default=limits[key],
            minimum=0,
            maximum=maximum,
            field_name=f"candidate_limits[{key}]",
            audit=audit,
        )
    return limits


def _portfolio_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _portfolio_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _record_portfolio_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("portfolio_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _load_search_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "policy_path": _SEARCH_POLICY_RELATIVE_PATH,
        "policy_loaded": False,
        "policy_errors": 0,
        "policy_events": [],
        "baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "operator_round_limit": _MAX_OPERATOR_ROUNDS,
        "post_baseline_operators_enabled": True,
    }
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _SEARCH_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_policy_event(audit, "error", "policy path escapes workspace")
        audit["policy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"policy load failed: {exc}")
        return audit

    audit["policy_loaded"] = True
    audit["baseline_time_fraction"] = _policy_float(
        module=module,
        function_name="baseline_time_fraction",
        default=_BASELINE_TIME_FRACTION,
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["operator_round_limit"] = _policy_int(
        module=module,
        function_name="max_operator_rounds",
        default=_MAX_OPERATOR_ROUNDS,
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["post_baseline_operators_enabled"] = _policy_bool(
        module=module,
        function_name="enable_post_baseline_operators",
        default=True,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _load_policy_module(path: Path) -> Any:
    module_name = f"_scion_cvrp_search_policy_{abs(hash(str(path)))}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _policy_float(
    *,
    module: Any,
    function_name: str,
    default: float,
    minimum: float,
    maximum: float,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> float:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _policy_int(
    *,
    module: Any,
    function_name: str,
    default: int,
    minimum: int,
    maximum: int,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> int:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _policy_bool(
    *,
    module: Any,
    function_name: str,
    default: bool,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> bool:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if not isinstance(value, bool):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-bool value {value!r}",
        )
        return default
    return value


def _call_policy_function(
    module: Any,
    function_name: str,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> Any:
    func = getattr(module, function_name, None)
    if not callable(func):
        raise ValueError(f"missing callable {function_name}")
    return func(instance, time_limit_sec)


def _record_policy_event(audit: dict[str, Any], status: str, detail: str) -> None:
    events = audit["policy_events"]
    if len(events) >= 10:
        return
    events.append({"policy": _SEARCH_POLICY_RELATIVE_PATH, "status": status, "detail": detail})


def _baseline_time_budget(
    time_limit_sec: float,
    baseline_time_fraction: float = _BASELINE_TIME_FRACTION,
) -> float:
    if time_limit_sec <= 0:
        return 0.0
    return max(0.05, float(time_limit_sec) * float(baseline_time_fraction))


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


def _apply_neighborhood_portfolio(
    operators: tuple[_LoadedOperator, ...],
    *,
    audit: dict[str, Any],
    max_operator_rounds: int,
) -> tuple[_LoadedOperator, ...]:
    enabled = {
        str(component)
        for component in audit.get("enabled_components", [])
        if str(component) in _ALLOWED_PORTFOLIO_COMPONENTS
    }
    component_weights = audit.get("component_weights")
    if not isinstance(component_weights, Mapping):
        component_weights = _DEFAULT_COMPONENT_WEIGHTS
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        candidate_limits = _DEFAULT_CANDIDATE_LIMITS

    for component in enabled:
        audit["component_attempts"].setdefault(component, 0)
        audit["component_accepted"].setdefault(component, 0)
        audit["component_runtime_ms"].setdefault(component, 0)

    effective_rounds = min(
        max_operator_rounds,
        int(candidate_limits.get("max_rounds", _MAX_OPERATOR_ROUNDS)),
    )
    audit["portfolio_effective_round_limit"] = max(0, effective_rounds)
    top_k = max(0, int(candidate_limits.get("top_k", _MAX_PORTFOLIO_TOP_K)))

    filtered = [operator for operator in operators if operator.component in enabled]
    filtered.sort(
        key=lambda op: (
            -op.weight * float(component_weights.get(op.component, 1.0)),
            op.order,
        )
    )
    if top_k == 0:
        audit["operator_loaded"] = 0
        audit["portfolio_stop_reason"] = "top_k_zero"
        return tuple()
    scheduled = tuple(filtered[:top_k])
    audit["operator_loaded"] = len(scheduled)
    if operators and not scheduled and not audit["portfolio_stop_reason"]:
        audit["portfolio_stop_reason"] = "no_enabled_components"
    return scheduled


def _portfolio_attempt_limit_reached(
    audit: dict[str, Any],
    component: str,
) -> bool:
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        return False
    component_attempts = audit.get("component_attempts")
    if not isinstance(component_attempts, Mapping):
        return False
    total_limit = int(candidate_limits.get("total_attempts", _MAX_PORTFOLIO_ATTEMPTS))
    total_attempts = sum(_as_nonnegative_int(value) for value in component_attempts.values())
    if total_attempts >= total_limit:
        return True
    component_limit = int(
        candidate_limits.get(
            component,
            candidate_limits.get("per_component_attempts", _MAX_PORTFOLIO_ATTEMPTS),
        )
    )
    return _as_nonnegative_int(component_attempts.get(component)) >= component_limit


def _record_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    runtime = audit["component_runtime_ms"]
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + elapsed_ms


def _operator_component(entry: Mapping[str, Any], instance: Any) -> str:
    raw = entry.get("category")
    if not raw:
        raw = getattr(instance, "category", "")
    component = str(raw or "").strip()
    if component in _ALLOWED_PORTFOLIO_COMPONENTS:
        return component
    return "registry_operator"


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
