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
_BASELINE_POLICY_RELATIVE_PATH = "policies/baseline_policy.py"
_CONSTRUCTION_POLICY_RELATIVE_PATH = "policies/construction_policy.py"
_NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH = "policies/neighborhood_portfolio.py"
_ALGORITHM_BLUEPRINT_RELATIVE_PATH = "policies/algorithm_blueprint.py"
_MAIN_SEARCH_STRATEGY_RELATIVE_PATH = "policies/main_search_strategy.py"
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
_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS = frozenset(
    {
        "intra_route_2opt",
        "inter_route_relocate",
    }
)
_ALLOWED_MAIN_SEARCH_COMPONENTS = frozenset(
    {
        "intra_route_2opt",
        "inter_route_relocate",
        "route_pair_swap",
        "bounded_destroy_repair",
    }
)
_FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS = frozenset(
    {
        "route_pair_swap",
        "bounded_destroy_repair",
    }
)
_MAX_BLUEPRINT_CONSTRUCTION_METHODS = 4
_MAX_BLUEPRINT_LOCAL_SEARCH_ROUNDS = 4
_MAX_BLUEPRINT_LOCAL_SEARCH_TOP_K = 64
_MAX_BLUEPRINT_RESTART_STAGNATION_ROUNDS = 25
_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS = 4
_MAX_MAIN_SEARCH_ROUNDS = 8
_MAX_MAIN_SEARCH_TOP_K = 128
_MAX_MAIN_SEARCH_RESTARTS = 3
_MAX_MAIN_SEARCH_RESTART_STAGNATION_ROUNDS = 25
_MAX_MAIN_SEARCH_PERTURBATIONS = 4
_MAX_MAIN_SEARCH_PERTURBATION_STRENGTH = 8
_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT = 10.0
_MAIN_SEARCH_FORMAL_BASELINE_TIME_FLOOR = 0.75
_BOUNDED_DESTROY_REPAIR_MIN_DISTANCE_IMPROVEMENT = 1.0
_MAIN_SEARCH_BDR_ACCEPT_LIMIT = 1
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FLOOR = 16
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_CEILING = 96
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FRACTION = 0.12
_ALGORITHM_BLUEPRINT_REQUIRED_KEYS = frozenset(
    {
        "enabled",
        "construction_methods",
        "construction_keep_top_k",
        "construction_bias",
        "baseline_time_fraction",
        "operator_round_limit",
        "post_baseline_operators_enabled",
        "local_search",
        "restart",
    }
)
_ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS = frozenset(
    {"enabled_components", "rounds", "top_k"}
)
_ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS = frozenset(
    {"enabled", "stagnation_rounds"}
)
_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS = frozenset(
    {
        "enabled",
        "construction",
        "baseline",
        "improvement",
        "acceptance",
        "restart",
        "perturbation",
        "post_baseline_operators_enabled",
        "operator_round_limit",
    }
)
_MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS = frozenset(
    {"methods", "keep_top_k", "bias"}
)
_MAIN_SEARCH_BASELINE_REQUIRED_KEYS = frozenset({"time_fraction", "params"})
_MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS = frozenset(
    {"enabled_components", "rounds", "top_k"}
)
_MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS = frozenset({"min_distance_improvement"})
_MAIN_SEARCH_RESTART_REQUIRED_KEYS = frozenset(
    {"enabled", "stagnation_rounds", "max_restarts"}
)
_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS = frozenset(
    {"enabled", "strength", "max_perturbations"}
)
_DEFAULT_BASELINE_POLICY_PARAMS = {
    "destroy_ratio": (0.10, 0.40),
    "segment_length": 100,
    "reaction_factor": 0.1,
    "vns_max_no_improve": 5000,
    "use_vns": True,
    "cw_threshold": 1500,
    "vns_threshold": 1200,
    "alns_threshold": 2000,
    "max_destroy_customers": 200,
}
_BASELINE_POLICY_ALLOWED_KEYS = frozenset(_DEFAULT_BASELINE_POLICY_PARAMS)


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
    baseline_policy: dict[str, Any] | None = None,
    algorithm_blueprint: dict[str, Any] | None = None,
    main_search_strategy: dict[str, Any] | None = None,
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
        algorithm_blueprint=algorithm_blueprint,
        main_search_strategy=main_search_strategy,
    )
    baseline_policy_audit = _baseline_policy_defaults()
    if baseline_policy is not None:
        baseline_policy_audit.update(baseline_policy)
    baseline_policy_params = baseline_policy_audit.get("baseline_policy_params")
    if not isinstance(baseline_policy_params, Mapping):
        baseline_policy_params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    resolved = Path(instance_path).resolve(strict=False)
    is_vrp = resolved.suffix.lower() == ".vrp"
    baseline_root = _find_vrp_baseline_root()
    baseline_required = is_vrp and _baseline_required_for_instance(resolved)
    effective_baseline_time_fraction = _effective_baseline_time_fraction(
        baseline_time_fraction,
        is_vrp=is_vrp,
        baseline_required=baseline_required,
        main_search_strategy=main_search_strategy,
    )
    baseline_fraction_audit = {
        "main_search_baseline_time_fraction_effective": (
            effective_baseline_time_fraction
        ),
        "main_search_baseline_quality_guard_applied": (
            effective_baseline_time_fraction > float(baseline_time_fraction)
        ),
    }
    if is_vrp and baseline_required and baseline_root is not None:
        budget = _baseline_time_budget(time_limit_sec, effective_baseline_time_fraction)
        try:
            solution, audit = _solve_with_vrp_baseline(
                instance=instance,
                instance_path=resolved,
                seed=seed,
                time_limit_sec=budget,
                baseline_root=baseline_root,
                baseline_required=baseline_required,
                baseline_policy_params=baseline_policy_params,
            )
            return solution, {
                **construction_audit,
                **baseline_policy_audit,
                **baseline_fraction_audit,
                **audit,
            }
        except Exception as exc:
            fallback = construction_solution
            return fallback, {
                **construction_audit,
                **baseline_policy_audit,
                **baseline_fraction_audit,
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
            **baseline_policy_audit,
            **baseline_fraction_audit,
            "baseline_mode": "scion_nearest_neighbor_fallback",
            "baseline_required": True,
            "baseline_error": "vrp/src baseline not available for configured CVRP data root",
            "baseline_routes": len(fallback.routes),
            "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
        }

    fallback = construction_solution
    return fallback, {
        **construction_audit,
        **baseline_policy_audit,
        **baseline_fraction_audit,
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
    main_search_strategy = _load_main_search_strategy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    algorithm_blueprint = _load_algorithm_blueprint(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    search_policy = _load_search_policy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    if _main_search_strategy_active(main_search_strategy):
        _apply_main_search_strategy_search_policy(
            search_policy,
            main_search_strategy=main_search_strategy,
        )
    else:
        _apply_algorithm_blueprint_search_policy(
            search_policy,
            algorithm_blueprint=algorithm_blueprint,
        )
    construction_policy = _load_construction_policy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    baseline_policy = _load_baseline_policy(
        workspace_root=Path.cwd(),
        instance=instance,
        time_limit_sec=args.time_limit,
    )
    if _main_search_strategy_active(main_search_strategy):
        _apply_main_search_strategy_baseline_policy(
            baseline_policy,
            main_search_strategy=main_search_strategy,
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
        baseline_policy=baseline_policy,
        algorithm_blueprint=(
            None if _main_search_strategy_active(main_search_strategy) else algorithm_blueprint
        ),
        main_search_strategy=main_search_strategy,
    )
    main_search_audit: dict[str, Any] = {}
    if _main_search_strategy_active(main_search_strategy):
        sol, main_search_audit = improve_with_main_search_strategy(
            sol,
            instance,
            adapter=adapter,
            rng=rng,
            time_limit_sec=args.time_limit,
            start_time=start,
            main_search_strategy=main_search_strategy,
        )
        algorithm_audit = {}
    else:
        sol, algorithm_audit = improve_with_algorithm_blueprint(
            sol,
            instance,
            adapter=adapter,
            rng=rng,
            time_limit_sec=args.time_limit,
            start_time=start,
            algorithm_blueprint=algorithm_blueprint,
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
        **algorithm_blueprint,
        **algorithm_audit,
        **main_search_strategy,
        **main_search_audit,
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
    algorithm_blueprint: dict[str, Any] | None = None,
    main_search_strategy: dict[str, Any] | None = None,
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

    if _main_search_strategy_active(main_search_strategy):
        return _construct_with_main_search_strategy(
            instance=instance,
            rng=rng,
            construction_audit=audit,
            main_search_strategy=main_search_strategy or {},
        )

    if _algorithm_blueprint_active(algorithm_blueprint):
        return _construct_with_algorithm_blueprint(
            instance=instance,
            rng=rng,
            construction_audit=audit,
            algorithm_blueprint=algorithm_blueprint or {},
        )

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


def _load_baseline_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _baseline_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _BASELINE_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_baseline_policy_event(audit, "error", "baseline policy path escapes workspace")
        audit["baseline_policy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(audit, "error", f"baseline policy load failed: {exc}")
        return audit

    audit["baseline_policy_loaded"] = True
    try:
        raw_params = _call_policy_function(
            module,
            "baseline_params",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(audit, "error", f"baseline_params failed: {exc}")
        return audit
    if not isinstance(raw_params, Mapping):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"baseline_params returned non-mapping value {raw_params!r}",
        )
        return audit

    _normalize_baseline_policy_params(dict(raw_params), audit=audit)
    return audit


def _baseline_policy_defaults() -> dict[str, Any]:
    params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return {
        "baseline_policy_path": _BASELINE_POLICY_RELATIVE_PATH,
        "baseline_policy_loaded": False,
        "baseline_policy_errors": 0,
        "baseline_policy_events": [],
        "baseline_policy_params": params,
        "baseline_destroy_ratio": list(params["destroy_ratio"]),
        "baseline_segment_length": params["segment_length"],
        "baseline_reaction_factor": params["reaction_factor"],
        "baseline_vns_max_no_improve": params["vns_max_no_improve"],
        "baseline_use_vns": params["use_vns"],
        "baseline_cw_threshold": params["cw_threshold"],
        "baseline_vns_threshold": params["vns_threshold"],
        "baseline_alns_threshold": params["alns_threshold"],
        "baseline_max_destroy_customers": params["max_destroy_customers"],
    }


def _normalize_baseline_policy_params(
    raw_params: dict[str, Any],
    *,
    audit: dict[str, Any],
) -> None:
    unknown = sorted(str(key) for key in raw_params if str(key) not in _BASELINE_POLICY_ALLOWED_KEYS)
    if unknown:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"baseline_params contains unknown keys {unknown}",
        )

    defaults = _DEFAULT_BASELINE_POLICY_PARAMS
    params = dict(defaults)
    params["destroy_ratio"] = _baseline_destroy_ratio(
        raw_params.get("destroy_ratio", defaults["destroy_ratio"]),
        audit=audit,
    )
    params["segment_length"] = _baseline_int(
        raw_params.get("segment_length", defaults["segment_length"]),
        minimum=1,
        maximum=1000,
        default=int(defaults["segment_length"]),
        field_name="segment_length",
        audit=audit,
    )
    params["reaction_factor"] = _baseline_float(
        raw_params.get("reaction_factor", defaults["reaction_factor"]),
        minimum=0.01,
        maximum=1.0,
        default=float(defaults["reaction_factor"]),
        field_name="reaction_factor",
        audit=audit,
    )
    params["vns_max_no_improve"] = _baseline_int(
        raw_params.get("vns_max_no_improve", defaults["vns_max_no_improve"]),
        minimum=0,
        maximum=20000,
        default=int(defaults["vns_max_no_improve"]),
        field_name="vns_max_no_improve",
        audit=audit,
    )
    params["use_vns"] = _baseline_bool(
        raw_params.get("use_vns", defaults["use_vns"]),
        default=bool(defaults["use_vns"]),
        field_name="use_vns",
        audit=audit,
    )
    params["cw_threshold"] = _baseline_int(
        raw_params.get("cw_threshold", defaults["cw_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["cw_threshold"]),
        field_name="cw_threshold",
        audit=audit,
    )
    params["vns_threshold"] = _baseline_int(
        raw_params.get("vns_threshold", defaults["vns_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["vns_threshold"]),
        field_name="vns_threshold",
        audit=audit,
    )
    params["alns_threshold"] = _baseline_int(
        raw_params.get("alns_threshold", defaults["alns_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["alns_threshold"]),
        field_name="alns_threshold",
        audit=audit,
    )
    params["max_destroy_customers"] = _baseline_int(
        raw_params.get("max_destroy_customers", defaults["max_destroy_customers"]),
        minimum=1,
        maximum=500,
        default=int(defaults["max_destroy_customers"]),
        field_name="max_destroy_customers",
        audit=audit,
    )

    audit["baseline_policy_params"] = params
    audit["baseline_destroy_ratio"] = list(params["destroy_ratio"])
    audit["baseline_segment_length"] = params["segment_length"]
    audit["baseline_reaction_factor"] = params["reaction_factor"]
    audit["baseline_vns_max_no_improve"] = params["vns_max_no_improve"]
    audit["baseline_use_vns"] = params["use_vns"]
    audit["baseline_cw_threshold"] = params["cw_threshold"]
    audit["baseline_vns_threshold"] = params["vns_threshold"]
    audit["baseline_alns_threshold"] = params["alns_threshold"]
    audit["baseline_max_destroy_customers"] = params["max_destroy_customers"]


def _baseline_destroy_ratio(value: Any, *, audit: dict[str, Any]) -> tuple[float, float]:
    default = _DEFAULT_BASELINE_POLICY_PARAMS["destroy_ratio"]
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio returned non-pair value {value!r}",
        )
        return default
    if len(value) != 2:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio must contain exactly two values, got {value!r}",
        )
        return default
    low = _baseline_ratio_item(value[0], "destroy_ratio[0]", audit)
    high = _baseline_ratio_item(value[1], "destroy_ratio[1]", audit)
    if low is None or high is None:
        return default
    if low > high:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio lower bound {low!r} exceeds upper bound {high!r}",
        )
        return default
    return (low, high)


def _baseline_ratio_item(value: Any, field_name: str, audit: dict[str, Any]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return None
    clamped = min(max(numeric, 0.01), 0.80)
    if clamped != numeric:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [0.01, 0.8], clamped",
        )
    return clamped


def _baseline_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _baseline_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _baseline_bool(
    value: Any,
    *,
    default: bool,
    field_name: str,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["baseline_policy_errors"] += 1
    _record_baseline_policy_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _record_baseline_policy_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("baseline_policy_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _BASELINE_POLICY_RELATIVE_PATH,
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


def _load_main_search_strategy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _main_search_strategy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _MAIN_SEARCH_STRATEGY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_main_search_event(audit, "error", "main search strategy path escapes workspace")
        audit["main_search_strategy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(audit, "error", f"main search strategy load failed: {exc}")
        return audit

    audit["main_search_strategy_loaded"] = True
    try:
        raw_plan = _call_policy_function(
            module,
            "main_search_plan",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(audit, "error", f"main_search_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"main_search_plan returned non-mapping value {raw_plan!r}",
        )
        return audit

    _normalize_main_search_strategy_plan(dict(raw_plan), instance=instance, audit=audit)
    return audit


def _main_search_strategy_defaults() -> dict[str, Any]:
    params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return {
        "main_search_strategy_path": _MAIN_SEARCH_STRATEGY_RELATIVE_PATH,
        "main_search_strategy_loaded": False,
        "main_search_strategy_active": False,
        "main_search_strategy_errors": 0,
        "main_search_strategy_events": [],
        "main_search_plan": {
            "enabled": False,
            "construction": {
                "methods": [_DEFAULT_CONSTRUCTION_MODE],
                "keep_top_k": 1,
                "bias": _DEFAULT_CONSTRUCTION_BIAS,
            },
            "baseline": {
                "time_fraction": _BASELINE_TIME_FRACTION,
                "params": {},
            },
            "improvement": {
                "enabled_components": [],
                "rounds": 0,
                "top_k": 16,
            },
            "acceptance": {
                "min_distance_improvement": 0.0,
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        "main_search_phases": ["inactive"],
        "main_search_construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
        "main_search_construction_keep_top_k": 1,
        "main_search_construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
        "main_search_baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "main_search_baseline_time_fraction_effective": _BASELINE_TIME_FRACTION,
        "main_search_baseline_quality_guard_applied": False,
        "main_search_baseline_params": params,
        "main_search_baseline_params_clamped": False,
        "main_search_baseline_param_clamps": _main_search_baseline_clamp_evidence({}),
        "main_search_post_baseline_operators_enabled": False,
        "main_search_operator_round_limit": 0,
        "main_search_components": [],
        "main_search_component_coverage_status": {
            "status": "inactive",
            "required_deep_components": sorted(
                _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
            ),
            "selected_deep_components": [],
            "missing_deep_components": sorted(
                _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
            ),
            "attempted_deep_components": [],
            "unattempted_deep_components": sorted(
                _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
            ),
        },
        "main_search_deep_components_selected": [],
        "main_search_rounds": 0,
        "main_search_top_k": 16,
        "main_search_selected_components": [],
        "main_search_attempted_components": [],
        "main_search_accepted_components": [],
        "main_search_skipped_components": [],
        "main_search_component_attempts": {},
        "main_search_component_accepted": {},
        "main_search_component_skip_reasons": {},
        "main_search_component_best_delta": {},
        "main_search_component_improvement_counts": {},
        "main_search_component_removed_counts": {},
        "main_search_component_reinserted_counts": {},
        "main_search_component_repair_fallback_counts": {},
        "main_search_component_runtime_ms": {},
        "main_search_acceptance_min_distance_improvement": 0.0,
        "main_search_component_min_distance_improvement": {},
        "main_search_bounded_destroy_repair_accept_limit": (
            _MAIN_SEARCH_BDR_ACCEPT_LIMIT
        ),
        "main_search_restart_enabled": False,
        "main_search_restart_stagnation_rounds": 0,
        "main_search_restart_count": 0,
        "main_search_perturbation_enabled": False,
        "main_search_perturbation_strength": 1,
        "main_search_perturbation_count": 0,
        "main_search_objective_delta_by_phase": {"inactive": 0.0},
        "main_search_phase_runtime_ms": {"inactive": 0},
        "main_search_elapsed_ms": 0,
        "main_search_best_returned": False,
        "main_search_stop_reason": "inactive",
    }


def _normalize_main_search_strategy_plan(
    plan: dict[str, Any],
    *,
    instance: CvrpInstance,
    audit: dict[str, Any],
) -> None:
    requested_active = _main_search_bool(
        plan.get("enabled", False),
        field_name="enabled",
        default=False,
        audit=audit,
    )
    _validate_main_search_plan_keys(plan, requested_active=requested_active, audit=audit)

    construction = _main_search_mapping_section(
        plan.get("construction", {}),
        field_name="construction",
        audit=audit,
    )
    baseline = _main_search_mapping_section(
        plan.get("baseline", {}),
        field_name="baseline",
        audit=audit,
    )
    improvement = _main_search_mapping_section(
        plan.get("improvement", {}),
        field_name="improvement",
        audit=audit,
    )
    acceptance = _main_search_mapping_section(
        plan.get("acceptance", {}),
        field_name="acceptance",
        audit=audit,
    )
    restart = _main_search_mapping_section(
        plan.get("restart", {}),
        field_name="restart",
        audit=audit,
    )
    perturbation = _main_search_mapping_section(
        plan.get("perturbation", {}),
        field_name="perturbation",
        audit=audit,
    )

    construction_methods = _main_search_string_sequence(
        construction.get("methods", [_DEFAULT_CONSTRUCTION_MODE]),
        allowed=_ALLOWED_CONSTRUCTION_MODES,
        default=[_DEFAULT_CONSTRUCTION_MODE],
        max_items=_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS,
        field_name="construction.methods",
        audit=audit,
    )
    construction_keep_top_k = _main_search_int(
        construction.get("keep_top_k", 1),
        minimum=1,
        maximum=_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS,
        default=1,
        field_name="construction.keep_top_k",
        audit=audit,
    )
    construction_bias = _main_search_float(
        construction.get("bias", _DEFAULT_CONSTRUCTION_BIAS),
        minimum=_MIN_CONSTRUCTION_BIAS,
        maximum=_MAX_CONSTRUCTION_BIAS,
        default=_DEFAULT_CONSTRUCTION_BIAS,
        field_name="construction.bias",
        audit=audit,
    )
    baseline_time_fraction = _main_search_float(
        baseline.get("time_fraction", _BASELINE_TIME_FRACTION),
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        default=_BASELINE_TIME_FRACTION,
        field_name="baseline.time_fraction",
        audit=audit,
    )
    baseline_params = _main_search_baseline_params(
        baseline.get("params", {}),
        audit=audit,
    )
    if requested_active:
        baseline_params, baseline_param_clamps = _clamp_main_search_baseline_params(
            baseline_params,
            instance=instance,
        )
    else:
        baseline_param_clamps = {}
    if baseline_param_clamps:
        _record_main_search_event(
            audit,
            "info",
            f"baseline.params conservative clamp applied: {baseline_param_clamps}",
        )
    components = _main_search_string_sequence(
        improvement.get("enabled_components", []),
        allowed=_ALLOWED_MAIN_SEARCH_COMPONENTS,
        default=[],
        max_items=len(_ALLOWED_MAIN_SEARCH_COMPONENTS),
        field_name="improvement.enabled_components",
        audit=audit,
        allow_empty=not requested_active,
    )
    components = _schedule_main_search_components(components)
    rounds = _main_search_int(
        improvement.get("rounds", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_ROUNDS,
        default=0,
        field_name="improvement.rounds",
        audit=audit,
    )
    top_k = _main_search_int(
        improvement.get("top_k", 16),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_TOP_K,
        default=16,
        field_name="improvement.top_k",
        audit=audit,
    )
    if requested_active and rounds <= 0:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            "enabled main_search_plan requires improvement.rounds > 0",
        )
    if requested_active and top_k <= 0:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            "enabled main_search_plan requires improvement.top_k > 0",
        )

    min_distance_improvement = _main_search_float(
        acceptance.get("min_distance_improvement", 0.0),
        minimum=0.0,
        maximum=_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT,
        default=0.0,
        field_name="acceptance.min_distance_improvement",
        audit=audit,
    )
    restart_enabled = _main_search_bool(
        restart.get("enabled", False),
        field_name="restart.enabled",
        default=False,
        audit=audit,
    )
    restart_stagnation = _main_search_int(
        restart.get("stagnation_rounds", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTART_STAGNATION_ROUNDS,
        default=0,
        field_name="restart.stagnation_rounds",
        audit=audit,
    )
    max_restarts = _main_search_int(
        restart.get("max_restarts", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTARTS,
        default=0,
        field_name="restart.max_restarts",
        audit=audit,
    )
    perturbation_enabled = _main_search_bool(
        perturbation.get("enabled", False),
        field_name="perturbation.enabled",
        default=False,
        audit=audit,
    )
    perturbation_strength = _main_search_int(
        perturbation.get("strength", 1),
        minimum=1,
        maximum=_MAX_MAIN_SEARCH_PERTURBATION_STRENGTH,
        default=1,
        field_name="perturbation.strength",
        audit=audit,
    )
    max_perturbations = _main_search_int(
        perturbation.get("max_perturbations", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_PERTURBATIONS,
        default=0,
        field_name="perturbation.max_perturbations",
        audit=audit,
    )
    post_baseline_enabled = _main_search_bool(
        plan.get("post_baseline_operators_enabled", False),
        field_name="post_baseline_operators_enabled",
        default=False,
        audit=audit,
    )
    operator_round_limit = _main_search_int(
        plan.get("operator_round_limit", 0),
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        default=0,
        field_name="operator_round_limit",
        audit=audit,
    )
    active = requested_active and _as_nonnegative_int(
        audit["main_search_strategy_errors"]
    ) == 0

    normalized_plan = {
        "enabled": active,
        "construction": {
            "methods": construction_methods,
            "keep_top_k": construction_keep_top_k,
            "bias": construction_bias,
        },
        "baseline": {
            "time_fraction": baseline_time_fraction,
            "params": baseline_params,
        },
        "improvement": {
            "enabled_components": components,
            "rounds": rounds,
            "top_k": top_k,
        },
        "acceptance": {
            "min_distance_improvement": min_distance_improvement,
        },
        "restart": {
            "enabled": restart_enabled,
            "stagnation_rounds": restart_stagnation,
            "max_restarts": max_restarts,
        },
        "perturbation": {
            "enabled": perturbation_enabled,
            "strength": perturbation_strength,
            "max_perturbations": max_perturbations,
        },
        "post_baseline_operators_enabled": post_baseline_enabled,
        "operator_round_limit": operator_round_limit,
    }
    audit["main_search_plan"] = normalized_plan
    audit["main_search_strategy_active"] = active
    audit["main_search_construction_methods"] = construction_methods
    audit["main_search_construction_keep_top_k"] = construction_keep_top_k
    audit["main_search_construction_bias"] = construction_bias
    audit["main_search_baseline_time_fraction"] = baseline_time_fraction
    audit["main_search_baseline_time_fraction_effective"] = baseline_time_fraction
    audit["main_search_baseline_quality_guard_applied"] = False
    audit["main_search_baseline_params"] = baseline_params
    audit["main_search_baseline_params_clamped"] = bool(baseline_param_clamps)
    audit["main_search_baseline_param_clamps"] = (
        _main_search_baseline_clamp_evidence(baseline_param_clamps)
    )
    audit["main_search_post_baseline_operators_enabled"] = post_baseline_enabled
    audit["main_search_operator_round_limit"] = operator_round_limit
    audit["main_search_components"] = components
    _refresh_main_search_component_coverage_status(audit, components)
    audit["main_search_rounds"] = rounds
    audit["main_search_top_k"] = top_k
    audit["main_search_selected_components"] = list(components)
    audit["main_search_attempted_components"] = []
    audit["main_search_accepted_components"] = []
    audit["main_search_skipped_components"] = []
    audit["main_search_component_attempts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_accepted"] = {
        component: 0 for component in components
    }
    audit["main_search_component_skip_reasons"] = {
        component: {} for component in components
    }
    audit["main_search_component_best_delta"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_improvement_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_removed_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_reinserted_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_repair_fallback_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_runtime_ms"] = {
        component: 0 for component in components
    }
    audit["main_search_acceptance_min_distance_improvement"] = min_distance_improvement
    audit["main_search_component_min_distance_improvement"] = {
        component: _main_search_component_min_distance_improvement(
            component,
            min_distance_improvement,
        )
        for component in components
    }
    audit["main_search_bounded_destroy_repair_accept_limit"] = (
        _MAIN_SEARCH_BDR_ACCEPT_LIMIT
    )
    audit["main_search_restart_enabled"] = restart_enabled
    audit["main_search_restart_stagnation_rounds"] = restart_stagnation
    audit["main_search_restart_count"] = 0
    audit["main_search_perturbation_enabled"] = perturbation_enabled
    audit["main_search_perturbation_strength"] = perturbation_strength
    audit["main_search_perturbation_count"] = 0
    if active:
        audit["main_search_phases"] = ["plan_loaded"]
        audit["main_search_objective_delta_by_phase"] = {"plan_loaded": 0.0}
        audit["main_search_phase_runtime_ms"] = {"plan_loaded": 0}
        audit["main_search_best_returned"] = False
        audit["main_search_stop_reason"] = "plan_loaded"
    elif requested_active:
        audit["main_search_phases"] = ["plan_invalid"]
        audit["main_search_objective_delta_by_phase"] = {"plan_invalid": 0.0}
        audit["main_search_phase_runtime_ms"] = {"plan_invalid": 0}
        audit["main_search_best_returned"] = False
        audit["main_search_stop_reason"] = "invalid_plan"


def _validate_main_search_plan_keys(
    plan: Mapping[str, Any],
    *,
    requested_active: bool,
    audit: dict[str, Any],
) -> None:
    _validate_main_search_section_keys(
        plan,
        allowed=_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS,
        required=_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS,
        requested_active=requested_active,
        field_name="main_search_plan",
        audit=audit,
    )
    section_specs = {
        "construction": _MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS,
        "baseline": _MAIN_SEARCH_BASELINE_REQUIRED_KEYS,
        "improvement": _MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS,
        "acceptance": _MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS,
        "restart": _MAIN_SEARCH_RESTART_REQUIRED_KEYS,
        "perturbation": _MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS,
    }
    for section_name, allowed in section_specs.items():
        section = plan.get(section_name)
        if isinstance(section, Mapping):
            _validate_main_search_section_keys(
                section,
                allowed=allowed,
                required=allowed,
                requested_active=requested_active,
                field_name=section_name,
                audit=audit,
            )


def _validate_main_search_section_keys(
    section: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    requested_active: bool,
    field_name: str,
    audit: dict[str, Any],
) -> None:
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} contains unknown keys {unknown}",
        )
    if requested_active:
        missing = sorted(key for key in required if key not in section)
        if missing:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"enabled {field_name} missing required keys {missing}",
            )


def _main_search_mapping_section(
    value: Any,
    *,
    field_name: str,
    audit: dict[str, Any],
) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    audit["main_search_strategy_errors"] += 1
    _record_main_search_event(
        audit,
        "error",
        f"{field_name} returned non-mapping value {value!r}",
    )
    return {}


def _main_search_baseline_params(
    value: Any,
    *,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"baseline.params returned non-mapping value {value!r}",
        )
        return dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    baseline_audit = _baseline_policy_defaults()
    _normalize_baseline_policy_params(dict(value), audit=baseline_audit)
    for event in baseline_audit.get("baseline_policy_events", []):
        if isinstance(event, Mapping):
            detail = event.get("detail")
            if detail:
                _record_main_search_event(
                    audit,
                    "error",
                    f"baseline.params invalid: {detail}",
                )
    audit["main_search_strategy_errors"] += _as_nonnegative_int(
        baseline_audit.get("baseline_policy_errors")
    )
    params = baseline_audit.get("baseline_policy_params")
    if not isinstance(params, Mapping):
        return dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return dict(params)


def _clamp_main_search_baseline_params(
    params: Mapping[str, Any],
    *,
    instance: CvrpInstance,
) -> tuple[dict[str, Any], dict[str, Any]]:
    clamped = dict(params)
    changes: dict[str, Any] = {}

    destroy_ratio = clamped.get("destroy_ratio")
    if isinstance(destroy_ratio, (list, tuple)) and len(destroy_ratio) == 2:
        low = float(destroy_ratio[0])
        high = min(float(destroy_ratio[1]), 0.35)
        if high < low:
            high = low
        if (low, high) != (float(destroy_ratio[0]), float(destroy_ratio[1])):
            changes["destroy_ratio"] = {
                "requested": tuple(destroy_ratio),
                "effective": (low, high),
            }
        clamped["destroy_ratio"] = (low, high)

    segment_length = int(clamped.get("segment_length", 100))
    if segment_length > 200:
        changes["segment_length"] = {
            "requested": segment_length,
            "effective": 200,
        }
        clamped["segment_length"] = 200

    reaction_factor = float(clamped.get("reaction_factor", 0.1))
    if reaction_factor < 0.08:
        changes["reaction_factor"] = {
            "requested": reaction_factor,
            "effective": 0.08,
        }
        clamped["reaction_factor"] = 0.08

    vns_max_no_improve = int(clamped.get("vns_max_no_improve", 5000))
    if vns_max_no_improve > 7000:
        changes["vns_max_no_improve"] = {
            "requested": vns_max_no_improve,
            "effective": 7000,
        }
        clamped["vns_max_no_improve"] = 7000

    adaptive_destroy_cap = max(
        _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FLOOR,
        min(
            _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_CEILING,
            int(
                math.ceil(
                    max(1, instance.customer_count)
                    * _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FRACTION
                )
            ),
        ),
    )
    max_destroy_customers = int(clamped.get("max_destroy_customers", adaptive_destroy_cap))
    if max_destroy_customers > adaptive_destroy_cap:
        changes["max_destroy_customers"] = {
            "requested": max_destroy_customers,
            "effective": adaptive_destroy_cap,
        }
        clamped["max_destroy_customers"] = adaptive_destroy_cap

    return clamped, changes


def _main_search_baseline_clamp_evidence(
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    fields = sorted(str(field) for field in changes)
    return {
        "applied": bool(fields),
        "status": "clamped" if fields else "no_clamps",
        "count": len(fields),
        "fields": fields,
        "clamps": _json_safe_runtime_value(dict(changes)),
    }


def _json_safe_runtime_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_runtime_value(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe_runtime_value(nested) for nested in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _schedule_main_search_components(components: list[str]) -> list[str]:
    if not (
        "route_pair_swap" in components
        and "bounded_destroy_repair" in components
    ):
        return components
    priority = {"route_pair_swap": 0, "bounded_destroy_repair": 1}
    return sorted(
        components,
        key=lambda component: (priority.get(component, -1), components.index(component)),
    )


def _apply_main_search_strategy_search_policy(
    search_policy: dict[str, Any],
    *,
    main_search_strategy: dict[str, Any],
) -> None:
    if not _main_search_strategy_active(main_search_strategy):
        return
    search_policy["baseline_time_fraction"] = main_search_strategy[
        "main_search_baseline_time_fraction"
    ]
    search_policy["operator_round_limit"] = main_search_strategy[
        "main_search_operator_round_limit"
    ]
    search_policy["post_baseline_operators_enabled"] = main_search_strategy[
        "main_search_post_baseline_operators_enabled"
    ]


def _apply_main_search_strategy_baseline_policy(
    baseline_policy: dict[str, Any],
    *,
    main_search_strategy: dict[str, Any],
) -> None:
    if not _main_search_strategy_active(main_search_strategy):
        return
    params = dict(main_search_strategy.get("main_search_baseline_params") or {})
    baseline_policy["baseline_policy_params"] = params
    baseline_policy["baseline_destroy_ratio"] = list(params["destroy_ratio"])
    baseline_policy["baseline_segment_length"] = params["segment_length"]
    baseline_policy["baseline_reaction_factor"] = params["reaction_factor"]
    baseline_policy["baseline_vns_max_no_improve"] = params["vns_max_no_improve"]
    baseline_policy["baseline_use_vns"] = params["use_vns"]
    baseline_policy["baseline_cw_threshold"] = params["cw_threshold"]
    baseline_policy["baseline_vns_threshold"] = params["vns_threshold"]
    baseline_policy["baseline_alns_threshold"] = params["alns_threshold"]
    baseline_policy["baseline_max_destroy_customers"] = params["max_destroy_customers"]


def _main_search_strategy_active(main_search_strategy: Mapping[str, Any] | None) -> bool:
    return bool(
        main_search_strategy
        and main_search_strategy.get("main_search_strategy_active")
    )


def _main_search_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["main_search_strategy_errors"] += 1
    _record_main_search_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _main_search_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _main_search_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _main_search_string_sequence(
    value: Any,
    *,
    allowed: frozenset[str],
    default: list[str],
    max_items: int,
    field_name: str,
    audit: dict[str, Any],
    allow_empty: bool = False,
) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-sequence value {value!r}",
        )
        return list(default)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text not in allowed:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"{field_name} contains unknown value {text!r}",
            )
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
        if len(normalized) >= max_items:
            break
    if not normalized and not allow_empty:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} produced no valid values",
        )
        return list(default)
    return normalized


def _record_main_search_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("main_search_strategy_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _MAIN_SEARCH_STRATEGY_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _load_algorithm_blueprint(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _algorithm_blueprint_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _ALGORITHM_BLUEPRINT_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_algorithm_event(audit, "error", "algorithm blueprint path escapes workspace")
        audit["algorithm_blueprint_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(audit, "error", f"algorithm blueprint load failed: {exc}")
        return audit

    audit["algorithm_blueprint_loaded"] = True
    try:
        raw_plan = _call_policy_function(
            module,
            "algorithm_plan",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(audit, "error", f"algorithm_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"algorithm_plan returned non-mapping value {raw_plan!r}",
        )
        return audit

    _normalize_algorithm_blueprint_plan(dict(raw_plan), audit=audit)
    return audit


def _algorithm_blueprint_defaults() -> dict[str, Any]:
    return {
        "algorithm_blueprint_path": _ALGORITHM_BLUEPRINT_RELATIVE_PATH,
        "algorithm_blueprint_loaded": False,
        "algorithm_blueprint_active": False,
        "algorithm_blueprint_errors": 0,
        "algorithm_blueprint_events": [],
        "algorithm_plan": {
            "enabled": False,
            "construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
            "construction_keep_top_k": 1,
            "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
            "baseline_time_fraction": _BASELINE_TIME_FRACTION,
            "operator_round_limit": _MAX_OPERATOR_ROUNDS,
            "post_baseline_operators_enabled": True,
            "local_search": {
                "enabled_components": [],
                "rounds": 0,
                "top_k": 16,
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
            },
        },
        "algorithm_phases_executed": ["inactive"],
        "algorithm_construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
        "algorithm_construction_keep_top_k": 1,
        "algorithm_baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "algorithm_operator_round_limit": _MAX_OPERATOR_ROUNDS,
        "algorithm_post_baseline_operators_enabled": True,
        "algorithm_local_search_components": [],
        "algorithm_local_search_rounds": 0,
        "algorithm_local_search_top_k": 16,
        "algorithm_local_search_attempts": 0,
        "algorithm_local_search_accepted": 0,
        "algorithm_restart_enabled": False,
        "algorithm_restart_stagnation_rounds": 0,
        "algorithm_restart_count": 0,
        "algorithm_best_delta_by_phase": {"inactive": 0.0},
        "algorithm_phase_runtime_ms": {"inactive": 0},
        "algorithm_stop_reason": "inactive",
    }


def _normalize_algorithm_blueprint_plan(
    plan: dict[str, Any],
    *,
    audit: dict[str, Any],
) -> None:
    requested_active = _algorithm_bool(
        plan.get("enabled", False),
        field_name="enabled",
        default=False,
        audit=audit,
    )
    _validate_algorithm_plan_keys(
        plan,
        requested_active=requested_active,
        audit=audit,
    )
    construction_methods = _algorithm_string_sequence(
        plan.get("construction_methods", [_DEFAULT_CONSTRUCTION_MODE]),
        allowed=_ALLOWED_CONSTRUCTION_MODES,
        default=[_DEFAULT_CONSTRUCTION_MODE],
        max_items=_MAX_BLUEPRINT_CONSTRUCTION_METHODS,
        field_name="construction_methods",
        audit=audit,
    )
    construction_keep_top_k = _algorithm_int(
        plan.get("construction_keep_top_k", 1),
        minimum=1,
        maximum=_MAX_BLUEPRINT_CONSTRUCTION_METHODS,
        default=1,
        field_name="construction_keep_top_k",
        audit=audit,
    )
    construction_bias = _algorithm_float(
        plan.get("construction_bias", _DEFAULT_CONSTRUCTION_BIAS),
        minimum=_MIN_CONSTRUCTION_BIAS,
        maximum=_MAX_CONSTRUCTION_BIAS,
        default=_DEFAULT_CONSTRUCTION_BIAS,
        field_name="construction_bias",
        audit=audit,
    )
    baseline_time_fraction = _algorithm_float(
        plan.get("baseline_time_fraction", _BASELINE_TIME_FRACTION),
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        default=_BASELINE_TIME_FRACTION,
        field_name="baseline_time_fraction",
        audit=audit,
    )
    operator_round_limit = _algorithm_int(
        plan.get("operator_round_limit", _MAX_OPERATOR_ROUNDS),
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        default=_MAX_OPERATOR_ROUNDS,
        field_name="operator_round_limit",
        audit=audit,
    )
    post_baseline_enabled = _algorithm_bool(
        plan.get("post_baseline_operators_enabled", True),
        field_name="post_baseline_operators_enabled",
        default=True,
        audit=audit,
    )
    local_search = plan.get("local_search", {})
    if not isinstance(local_search, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"local_search returned non-mapping value {local_search!r}",
        )
        local_search = {}
    local_components = _algorithm_string_sequence(
        local_search.get("enabled_components", []),
        allowed=_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS,
        default=[],
        max_items=len(_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS),
        field_name="local_search.enabled_components",
        audit=audit,
        allow_empty=True,
    )
    local_rounds = _algorithm_int(
        local_search.get("rounds", 0),
        minimum=0,
        maximum=_MAX_BLUEPRINT_LOCAL_SEARCH_ROUNDS,
        default=0,
        field_name="local_search.rounds",
        audit=audit,
    )
    local_top_k = _algorithm_int(
        local_search.get("top_k", 16),
        minimum=0,
        maximum=_MAX_BLUEPRINT_LOCAL_SEARCH_TOP_K,
        default=16,
        field_name="local_search.top_k",
        audit=audit,
    )
    restart = plan.get("restart", {})
    if not isinstance(restart, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"restart returned non-mapping value {restart!r}",
        )
        restart = {}
    restart_enabled = _algorithm_bool(
        restart.get("enabled", False),
        field_name="restart.enabled",
        default=False,
        audit=audit,
    )
    restart_stagnation = _algorithm_int(
        restart.get("stagnation_rounds", 0),
        minimum=0,
        maximum=_MAX_BLUEPRINT_RESTART_STAGNATION_ROUNDS,
        default=0,
        field_name="restart.stagnation_rounds",
        audit=audit,
    )
    active = requested_active and _as_nonnegative_int(
        audit["algorithm_blueprint_errors"]
    ) == 0

    normalized_plan = {
        "enabled": active,
        "construction_methods": construction_methods,
        "construction_keep_top_k": construction_keep_top_k,
        "construction_bias": construction_bias,
        "baseline_time_fraction": baseline_time_fraction,
        "operator_round_limit": operator_round_limit,
        "post_baseline_operators_enabled": post_baseline_enabled,
        "local_search": {
            "enabled_components": local_components,
            "rounds": local_rounds,
            "top_k": local_top_k,
        },
        "restart": {
            "enabled": restart_enabled,
            "stagnation_rounds": restart_stagnation,
        },
    }
    audit["algorithm_plan"] = normalized_plan
    audit["algorithm_blueprint_active"] = active
    audit["algorithm_construction_methods"] = construction_methods
    audit["algorithm_construction_keep_top_k"] = construction_keep_top_k
    audit["algorithm_baseline_time_fraction"] = baseline_time_fraction
    audit["algorithm_operator_round_limit"] = operator_round_limit
    audit["algorithm_post_baseline_operators_enabled"] = post_baseline_enabled
    audit["algorithm_local_search_components"] = local_components
    audit["algorithm_local_search_rounds"] = local_rounds
    audit["algorithm_local_search_top_k"] = local_top_k
    audit["algorithm_restart_enabled"] = restart_enabled
    audit["algorithm_restart_stagnation_rounds"] = restart_stagnation
    if active:
        audit["algorithm_phases_executed"] = ["plan_loaded"]
        audit["algorithm_best_delta_by_phase"] = {"plan_loaded": 0.0}
        audit["algorithm_phase_runtime_ms"] = {"plan_loaded": 0}
        audit["algorithm_stop_reason"] = "plan_loaded"
    elif requested_active:
        audit["algorithm_phases_executed"] = ["plan_invalid"]
        audit["algorithm_best_delta_by_phase"] = {"plan_invalid": 0.0}
        audit["algorithm_phase_runtime_ms"] = {"plan_invalid": 0}
        audit["algorithm_stop_reason"] = "invalid_plan"


def _validate_algorithm_plan_keys(
    plan: Mapping[str, Any],
    *,
    requested_active: bool,
    audit: dict[str, Any],
) -> None:
    allowed_top = _ALGORITHM_BLUEPRINT_REQUIRED_KEYS
    unknown = sorted(str(key) for key in plan if str(key) not in allowed_top)
    if unknown:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"algorithm_plan contains unknown keys {unknown}",
        )
    if requested_active:
        missing = sorted(key for key in allowed_top if key not in plan)
        if missing:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"enabled algorithm_plan missing required keys {missing}",
            )
    local_search = plan.get("local_search")
    if isinstance(local_search, Mapping):
        local_unknown = sorted(
            str(key)
            for key in local_search
            if str(key) not in _ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS
        )
        if local_unknown:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"local_search contains unknown keys {local_unknown}",
            )
        if requested_active:
            local_missing = sorted(
                key
                for key in _ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS
                if key not in local_search
            )
            if local_missing:
                audit["algorithm_blueprint_errors"] += 1
                _record_algorithm_event(
                    audit,
                    "error",
                    f"enabled local_search missing required keys {local_missing}",
                )
    restart = plan.get("restart")
    if isinstance(restart, Mapping):
        restart_unknown = sorted(
            str(key)
            for key in restart
            if str(key) not in _ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS
        )
        if restart_unknown:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"restart contains unknown keys {restart_unknown}",
            )
        if requested_active:
            restart_missing = sorted(
                key
                for key in _ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS
                if key not in restart
            )
            if restart_missing:
                audit["algorithm_blueprint_errors"] += 1
                _record_algorithm_event(
                    audit,
                    "error",
                    f"enabled restart missing required keys {restart_missing}",
                )


def _apply_algorithm_blueprint_search_policy(
    search_policy: dict[str, Any],
    *,
    algorithm_blueprint: dict[str, Any],
) -> None:
    if not _algorithm_blueprint_active(algorithm_blueprint):
        return
    search_policy["baseline_time_fraction"] = algorithm_blueprint[
        "algorithm_baseline_time_fraction"
    ]
    search_policy["operator_round_limit"] = algorithm_blueprint[
        "algorithm_operator_round_limit"
    ]
    search_policy["post_baseline_operators_enabled"] = algorithm_blueprint[
        "algorithm_post_baseline_operators_enabled"
    ]


def _algorithm_blueprint_active(algorithm_blueprint: Mapping[str, Any] | None) -> bool:
    return bool(algorithm_blueprint and algorithm_blueprint.get("algorithm_blueprint_active"))


def _algorithm_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["algorithm_blueprint_errors"] += 1
    _record_algorithm_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _algorithm_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _algorithm_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _algorithm_string_sequence(
    value: Any,
    *,
    allowed: frozenset[str],
    default: list[str],
    max_items: int,
    field_name: str,
    audit: dict[str, Any],
    allow_empty: bool = False,
) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-sequence value {value!r}",
        )
        return list(default)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text not in allowed:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"{field_name} contains unknown value {text!r}",
            )
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
        if len(normalized) >= max_items:
            break
    if not normalized and not allow_empty:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} produced no valid values",
        )
        return list(default)
    return normalized


def _record_algorithm_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("algorithm_blueprint_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _ALGORITHM_BLUEPRINT_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _construct_with_algorithm_blueprint(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_audit: dict[str, Any],
    algorithm_blueprint: dict[str, Any],
) -> tuple[CvrpSolution, dict[str, Any]]:
    start_ns = time.monotonic_ns()
    methods = [
        method
        for method in algorithm_blueprint.get("algorithm_construction_methods", [])
        if method in _ALLOWED_CONSTRUCTION_MODES
    ]
    if not methods:
        methods = [_DEFAULT_CONSTRUCTION_MODE]
    keep_top_k = _as_nonnegative_int(
        algorithm_blueprint.get("algorithm_construction_keep_top_k", 1)
    )
    methods = methods[: max(1, min(keep_top_k, len(methods)))]
    bias = float(
        algorithm_blueprint.get("algorithm_plan", {}).get(
            "construction_bias",
            algorithm_blueprint.get("construction_bias", _DEFAULT_CONSTRUCTION_BIAS),
        )
    )

    adapter = CvrpAdapter(object())  # type: ignore[arg-type]
    best_solution: CvrpSolution | None = None
    best_objective: dict[str, int | float] | None = None
    first_objective: dict[str, int | float] | None = None
    tried: list[str] = []
    for method in methods:
        tried.append(method)
        try:
            candidate = solve(
                instance,
                rng,
                construction_mode=method,
                construction_bias=bias,
            )
        except Exception as exc:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"algorithm construction failed for mode={method!r}: {exc}",
            )
            continue
        valid, reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"algorithm construction infeasible for mode={method!r}: {reason}",
            )
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        if first_objective is None:
            first_objective = objective
        if best_objective is None or _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
            construction_audit["construction_mode"] = method

    if best_solution is None:
        construction_audit["construction_errors"] = (
            _as_nonnegative_int(construction_audit["construction_errors"]) + 1
        )
        _record_construction_event(
            construction_audit,
            "error",
            "algorithm construction ensemble produced no valid solution",
        )
        best_solution = solve(instance, rng)
        best_objective = _objective_for_solution(adapter, instance, best_solution)

    construction_audit["construction_elapsed_ms"] = int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )
    construction_audit["construction_routes"] = len(best_solution.routes)
    construction_audit["construction_distance"] = sum(
        instance.route_distance(route) for route in best_solution.routes
    )
    construction_audit["construction_feasible"] = True
    construction_audit["algorithm_construction_methods_tried"] = tried
    _append_algorithm_phase(algorithm_blueprint, "construction_ensemble")
    _set_algorithm_phase_runtime(
        algorithm_blueprint,
        "construction_ensemble",
        start_ns,
    )
    if first_objective is not None and best_objective is not None:
        algorithm_blueprint.setdefault("algorithm_best_delta_by_phase", {})[
            "construction_ensemble"
        ] = _objective_distance_delta(first_objective, best_objective)
    return best_solution, construction_audit


def _construct_with_main_search_strategy(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_audit: dict[str, Any],
    main_search_strategy: dict[str, Any],
) -> tuple[CvrpSolution, dict[str, Any]]:
    start_ns = time.monotonic_ns()
    methods = [
        method
        for method in main_search_strategy.get("main_search_construction_methods", [])
        if method in _ALLOWED_CONSTRUCTION_MODES
    ]
    if not methods:
        methods = [_DEFAULT_CONSTRUCTION_MODE]
    keep_top_k = max(
        1,
        min(
            _as_nonnegative_int(
                main_search_strategy.get("main_search_construction_keep_top_k", 1)
            ),
            len(methods),
        ),
    )
    bias = float(
        main_search_strategy.get(
            "main_search_construction_bias",
            _DEFAULT_CONSTRUCTION_BIAS,
        )
    )

    adapter = CvrpAdapter(object())  # type: ignore[arg-type]
    candidates: list[tuple[dict[str, int | float], CvrpSolution, str]] = []
    tried: list[str] = []
    for method in methods:
        tried.append(method)
        try:
            candidate = solve(
                instance,
                rng,
                construction_mode=method,
                construction_bias=bias,
            )
        except Exception as exc:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"main search construction failed for mode={method!r}: {exc}",
            )
            continue
        valid, reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"main search construction infeasible for mode={method!r}: {reason}",
            )
            continue
        candidates.append((_objective_for_solution(adapter, instance, candidate), candidate, method))

    first_objective = candidates[0][0] if candidates else None
    if not candidates:
        construction_audit["construction_errors"] = (
            _as_nonnegative_int(construction_audit["construction_errors"]) + 1
        )
        _record_construction_event(
            construction_audit,
            "error",
            "main search construction ensemble produced no valid solution",
        )
        best_solution = solve(instance, rng)
        best_objective = _objective_for_solution(adapter, instance, best_solution)
        best_method = _DEFAULT_CONSTRUCTION_MODE
    else:
        candidates.sort(
            key=lambda item: (
                float(item[0].get("fleet_violation", 0)),
                float(item[0].get("total_distance", 0.0)),
            )
        )
        kept = candidates[:keep_top_k]
        best_objective, best_solution, best_method = kept[0]

    construction_audit["construction_elapsed_ms"] = int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )
    construction_audit["construction_mode"] = best_method
    construction_audit["construction_routes"] = len(best_solution.routes)
    construction_audit["construction_distance"] = sum(
        instance.route_distance(route) for route in best_solution.routes
    )
    construction_audit["construction_feasible"] = True
    construction_audit["main_search_construction_methods_tried"] = tried
    _append_main_search_phase(main_search_strategy, "construction")
    _set_main_search_phase_runtime(main_search_strategy, "construction", start_ns)
    if first_objective is not None:
        main_search_strategy.setdefault("main_search_objective_delta_by_phase", {})[
            "construction"
        ] = _objective_distance_delta(first_objective, best_objective)
    return best_solution, construction_audit


def improve_with_main_search_strategy(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    main_search_strategy: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    if not _main_search_strategy_active(main_search_strategy):
        return solution, {}

    assert main_search_strategy is not None
    audit = dict(main_search_strategy)
    _append_main_search_phase(audit, "baseline")
    audit.setdefault("main_search_phase_runtime_ms", {}).setdefault("baseline", 0)

    components = [
        component
        for component in audit.get("main_search_components", [])
        if component in _ALLOWED_MAIN_SEARCH_COMPONENTS
    ]
    rounds = _as_nonnegative_int(audit.get("main_search_rounds", 0))
    top_k = _as_nonnegative_int(audit.get("main_search_top_k", 16))
    min_distance_improvement = float(
        audit.get("main_search_acceptance_min_distance_improvement", 0.0)
    )
    component_min_distance_improvement = audit.get(
        "main_search_component_min_distance_improvement",
        {},
    )
    if not isinstance(component_min_distance_improvement, Mapping):
        component_min_distance_improvement = {}
    if not components or rounds <= 0 or top_k <= 0:
        audit["main_search_stop_reason"] = "improvement_loop_disabled"
        return solution, audit

    phase_start_ns = time.monotonic_ns()
    initial_objective = _objective_for_solution(adapter, instance, solution)
    best_solution = solution
    best_objective = dict(initial_objective)
    current = solution
    current_objective = dict(initial_objective)
    no_improvement_rounds = 0
    stop_reason = "max_main_search_rounds"

    _append_main_search_phase(audit, "improvement_loop")
    for round_index in range(rounds):
        if _time_exhausted(start_time, time_limit_sec):
            stop_reason = "time_limit"
            break
        audit["main_search_rounds"] = round_index + 1
        round_accepted = 0
        round_route_pair_improved = False
        for component in components:
            if _time_exhausted(start_time, time_limit_sec):
                stop_reason = "time_limit"
                break
            if (
                component == "bounded_destroy_repair"
                and "route_pair_swap" in components
                and round_route_pair_improved
            ):
                _record_main_search_component_skip(
                    audit,
                    component,
                    "route_pair_phase_improved",
                )
                continue
            if (
                component == "bounded_destroy_repair"
                and _as_nonnegative_int(
                    audit.get("main_search_component_accepted", {}).get(
                        "bounded_destroy_repair",
                        0,
                    )
                )
                >= _as_nonnegative_int(
                    audit.get(
                        "main_search_bounded_destroy_repair_accept_limit",
                        _MAIN_SEARCH_BDR_ACCEPT_LIMIT,
                    )
                )
            ):
                _record_main_search_component_skip(
                    audit,
                    component,
                    "bounded_destroy_repair_accept_limit_reached",
                )
                continue
            component_start_ns = time.monotonic_ns()
            _record_main_search_component_attempted(audit, component)
            candidate, attempts, component_telemetry = _main_search_component_candidate(
                component,
                current,
                instance,
                adapter=adapter,
                current_objective=current_objective,
                top_k=top_k,
            )
            _record_main_search_component_attempts(audit, component, attempts)
            _record_main_search_component_repair_counts(
                audit,
                component,
                component_telemetry,
            )
            _record_main_search_component_runtime(audit, component, component_start_ns)
            if candidate is None:
                _record_main_search_component_skip(
                    audit,
                    component,
                    _main_search_skip_reason(component_telemetry, attempts),
                )
                continue
            candidate_objective = _objective_for_solution(adapter, instance, candidate)
            candidate_delta = _objective_distance_delta(
                current_objective,
                candidate_objective,
            )
            _record_main_search_component_candidate_delta(
                audit,
                component,
                candidate_delta,
            )
            effective_min_distance_improvement = float(
                component_min_distance_improvement.get(
                    component,
                    _main_search_component_min_distance_improvement(
                        component,
                        min_distance_improvement,
                    ),
                )
            )
            if not _main_search_accepts(
                candidate_objective,
                current_objective,
                min_distance_improvement=effective_min_distance_improvement,
            ):
                _record_main_search_component_skip(
                    audit,
                    component,
                    "candidate_below_acceptance_threshold",
                )
                continue
            valid, reason = _solution_is_valid(adapter, instance, candidate)
            if not valid:
                audit["main_search_strategy_errors"] = (
                    _as_nonnegative_int(audit.get("main_search_strategy_errors")) + 1
                )
                _record_main_search_event(
                    audit,
                    "error",
                    f"{component} produced invalid solution: {reason}",
                )
                _record_main_search_component_skip(
                    audit,
                    component,
                    "invalid_component_output",
                )
                stop_reason = "invalid_component_output"
                break
            current = candidate
            current_objective = candidate_objective
            _record_main_search_component_accepted(audit, component)
            round_accepted += 1
            if component == "route_pair_swap":
                round_route_pair_improved = True
            if _lexicographic_improves(current_objective, best_objective):
                best_solution = current
                best_objective = dict(current_objective)
        if stop_reason in {"time_limit", "invalid_component_output"}:
            break
        if round_accepted > 0:
            no_improvement_rounds = 0
            continue
        no_improvement_rounds += 1
        stagnation_limit = _as_nonnegative_int(
            audit.get("main_search_restart_stagnation_rounds", 0)
        )
        restart_limit = _main_search_plan_int(audit, "restart", "max_restarts")
        perturb_limit = _main_search_plan_int(audit, "perturbation", "max_perturbations")
        if (
            bool(audit.get("main_search_perturbation_enabled"))
            and _as_nonnegative_int(audit.get("main_search_perturbation_count")) < perturb_limit
        ):
            perturbed = _perturb_solution(
                best_solution,
                instance,
                rng=rng,
                strength=_as_nonnegative_int(
                    audit.get("main_search_perturbation_strength", 1)
                ),
            )
            if perturbed is not None:
                valid, reason = _solution_is_valid(adapter, instance, perturbed)
                if valid:
                    current = perturbed
                    current_objective = _objective_for_solution(adapter, instance, current)
                    audit["main_search_perturbation_count"] = (
                        _as_nonnegative_int(audit.get("main_search_perturbation_count")) + 1
                    )
                    _append_main_search_phase(audit, "perturbation")
                    continue
                audit["main_search_strategy_errors"] = (
                    _as_nonnegative_int(audit.get("main_search_strategy_errors")) + 1
                )
                _record_main_search_event(
                    audit,
                    "error",
                    f"perturbation produced invalid solution: {reason}",
                )
                stop_reason = "invalid_perturbation"
                break
        if (
            bool(audit.get("main_search_restart_enabled"))
            and stagnation_limit
            and no_improvement_rounds >= stagnation_limit
            and _as_nonnegative_int(audit.get("main_search_restart_count")) < restart_limit
        ):
            audit["main_search_restart_count"] = (
                _as_nonnegative_int(audit.get("main_search_restart_count")) + 1
            )
            current = best_solution
            current_objective = dict(best_objective)
            _append_main_search_phase(audit, "restart")
            no_improvement_rounds = 0
            continue
        stop_reason = "no_main_search_improvement"
        break

    _set_main_search_phase_runtime(audit, "improvement_loop", phase_start_ns)
    audit.setdefault("main_search_objective_delta_by_phase", {})[
        "improvement_loop"
    ] = _objective_distance_delta(initial_objective, best_objective)
    audit["main_search_elapsed_ms"] = sum(
        _as_nonnegative_int(value)
        for value in audit.get("main_search_phase_runtime_ms", {}).values()
    )
    audit["main_search_best_returned"] = True
    audit["main_search_stop_reason"] = stop_reason
    return best_solution, audit


def _effective_baseline_time_fraction(
    baseline_time_fraction: float,
    *,
    is_vrp: bool,
    baseline_required: bool,
    main_search_strategy: Mapping[str, Any] | None,
) -> float:
    fraction = float(baseline_time_fraction)
    if not (
        is_vrp
        and baseline_required
        and _main_search_strategy_active(main_search_strategy)
    ):
        return fraction
    return max(fraction, _MAIN_SEARCH_FORMAL_BASELINE_TIME_FLOOR)


def _main_search_component_min_distance_improvement(
    component: str,
    requested_min_distance_improvement: float,
) -> float:
    threshold = max(0.0, float(requested_min_distance_improvement))
    if component == "bounded_destroy_repair":
        return max(threshold, _BOUNDED_DESTROY_REPAIR_MIN_DISTANCE_IMPROVEMENT)
    return threshold


def _main_search_component_candidate(
    component: str,
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    if component == "intra_route_2opt":
        candidate, attempts = _best_intra_route_2opt(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
        return candidate, attempts, {}
    if component == "inter_route_relocate":
        candidate, attempts = _best_inter_route_relocate(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
        return candidate, attempts, {}
    if component == "route_pair_swap":
        candidate, attempts = _best_route_pair_swap(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
        return candidate, attempts, {}
    if component == "bounded_destroy_repair":
        return _best_bounded_destroy_repair(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
    return None, 0, {"skip_reason": "unknown_component"}


def improve_with_algorithm_blueprint(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    algorithm_blueprint: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    if not _algorithm_blueprint_active(algorithm_blueprint):
        return solution, {}

    assert algorithm_blueprint is not None
    audit = dict(algorithm_blueprint)
    _append_algorithm_phase(audit, "baseline")
    audit.setdefault("algorithm_phase_runtime_ms", {}).setdefault("baseline", 0)
    components = [
        component
        for component in audit.get("algorithm_local_search_components", [])
        if component in _ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS
    ]
    rounds = _as_nonnegative_int(audit.get("algorithm_local_search_rounds", 0))
    top_k = _as_nonnegative_int(audit.get("algorithm_local_search_top_k", 16))
    if not components or rounds <= 0 or top_k <= 0:
        audit["algorithm_stop_reason"] = "local_search_disabled"
        return solution, audit

    phase_start_ns = time.monotonic_ns()
    initial_objective = _objective_for_solution(adapter, instance, solution)
    current = solution
    current_objective = dict(initial_objective)
    no_improvement_rounds = 0
    stop_reason = "max_local_search_rounds"

    _append_algorithm_phase(audit, "local_search")
    for round_index in range(rounds):
        if _time_exhausted(start_time, time_limit_sec):
            stop_reason = "time_limit"
            break
        audit["algorithm_local_search_rounds"] = round_index + 1
        round_accepted = 0
        for component in components:
            if _time_exhausted(start_time, time_limit_sec):
                stop_reason = "time_limit"
                break
            component_start_ns = time.monotonic_ns()
            if component == "intra_route_2opt":
                candidate, attempts = _best_intra_route_2opt(
                    current,
                    instance,
                    adapter=adapter,
                    current_objective=current_objective,
                    top_k=top_k,
                )
            elif component == "inter_route_relocate":
                candidate, attempts = _best_inter_route_relocate(
                    current,
                    instance,
                    adapter=adapter,
                    current_objective=current_objective,
                    top_k=top_k,
                )
            else:
                candidate, attempts = None, 0
            audit["algorithm_local_search_attempts"] = (
                _as_nonnegative_int(audit.get("algorithm_local_search_attempts")) + attempts
            )
            _record_algorithm_component_runtime(audit, component, component_start_ns)
            if candidate is None:
                continue
            candidate_objective = _objective_for_solution(adapter, instance, candidate)
            if _lexicographic_improves(candidate_objective, current_objective):
                current = candidate
                current_objective = candidate_objective
                audit["algorithm_local_search_accepted"] = (
                    _as_nonnegative_int(audit.get("algorithm_local_search_accepted")) + 1
                )
                round_accepted += 1
        if stop_reason == "time_limit":
            break
        if round_accepted > 0:
            no_improvement_rounds = 0
            continue
        no_improvement_rounds += 1
        stagnation_limit = _as_nonnegative_int(
            audit.get("algorithm_restart_stagnation_rounds", 0)
        )
        if bool(audit.get("algorithm_restart_enabled")) and stagnation_limit:
            if no_improvement_rounds >= stagnation_limit:
                audit["algorithm_restart_count"] = (
                    _as_nonnegative_int(audit.get("algorithm_restart_count")) + 1
                )
                stop_reason = "restart_stagnation_limit"
                break
        else:
            stop_reason = "no_local_search_improvement"
            break

    _set_algorithm_phase_runtime(audit, "local_search", phase_start_ns)
    audit.setdefault("algorithm_best_delta_by_phase", {})[
        "local_search"
    ] = _objective_distance_delta(initial_objective, current_objective)
    audit["algorithm_stop_reason"] = stop_reason
    return current, audit


def _best_intra_route_2opt(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for route_index, route in enumerate(routes):
        if len(route) < 2:
            continue
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                if attempts >= top_k:
                    return best_solution, attempts
                attempts += 1
                candidate_routes = [list(item) for item in routes]
                candidate_routes[route_index] = (
                    route[:i] + list(reversed(route[i : j + 1])) + route[j + 1 :]
                )
                candidate = CvrpSolution(
                    routes=tuple(tuple(item) for item in candidate_routes if item)
                )
                objective = _objective_for_solution(adapter, instance, candidate)
                if _lexicographic_improves(objective, best_objective):
                    best_solution = candidate
                    best_objective = objective
    return best_solution, attempts


def _best_inter_route_relocate(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for source_index, source_route in enumerate(routes):
        for customer_pos, customer in enumerate(source_route):
            for dest_index, dest_route in enumerate(routes):
                if dest_index == source_index:
                    continue
                for insert_pos in range(len(dest_route) + 1):
                    if attempts >= top_k:
                        return best_solution, attempts
                    attempts += 1
                    candidate_routes = [list(item) for item in routes]
                    moved = candidate_routes[source_index].pop(customer_pos)
                    candidate_routes[dest_index].insert(insert_pos, moved)
                    if instance.route_load(tuple(candidate_routes[dest_index])) > instance.capacity:
                        continue
                    normalized_routes = [
                        tuple(route) for route in candidate_routes if route
                    ]
                    candidate = CvrpSolution(routes=tuple(normalized_routes))
                    valid, _reason = _solution_is_valid(adapter, instance, candidate)
                    if not valid:
                        continue
                    objective = _objective_for_solution(adapter, instance, candidate)
                    if _lexicographic_improves(objective, best_objective):
                        best_solution = candidate
                        best_objective = objective
    return best_solution, attempts


def _best_route_pair_swap(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    ranked_swaps = _rank_route_pair_swap_candidates(routes, instance, top_k=top_k)
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for _estimated_delta, left_index, right_index, left_pos, right_pos in ranked_swaps:
        if attempts >= top_k:
            return best_solution, attempts
        attempts += 1
        candidate_routes = [list(item) for item in routes]
        (
            candidate_routes[left_index][left_pos],
            candidate_routes[right_index][right_pos],
        ) = (
            candidate_routes[right_index][right_pos],
            candidate_routes[left_index][left_pos],
        )
        if (
            instance.route_load(tuple(candidate_routes[left_index])) > instance.capacity
            or instance.route_load(tuple(candidate_routes[right_index]))
            > instance.capacity
        ):
            continue
        candidate = CvrpSolution(
            routes=tuple(tuple(route) for route in candidate_routes if route)
        )
        valid, _reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        if _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
    return best_solution, attempts


def _best_bounded_destroy_repair(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    routes = [list(route) for route in solution.routes]
    telemetry = {
        "removed_count": 0,
        "reinserted_count": 0,
        "repair_fallback_count": 0,
        "skip_reason": "",
    }
    customer_count = sum(len(route) for route in routes)
    if customer_count < 2 or top_k <= 0:
        telemetry["skip_reason"] = "insufficient_destroy_budget"
        return None, 0, telemetry

    destroy_count = _bounded_destroy_count(customer_count, top_k)
    removable = _rank_worst_removal_customers(routes, instance)
    if len(removable) < destroy_count:
        telemetry["skip_reason"] = "insufficient_removal_candidates"
        return None, 0, telemetry

    total_attempts = 0
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    best_removed = 0
    best_reinserted = 0
    last_reason = ""

    for selected in _bounded_destroy_repair_subsets(removable, destroy_count):
        remaining_budget = top_k - total_attempts
        if remaining_budget <= 0:
            if not last_reason:
                last_reason = "repair_budget_exhausted"
            break
        if total_attempts > 0:
            telemetry["repair_fallback_count"] += 1
        base_routes, removed_customers, removal_reason = _remove_destroy_subset(
            routes,
            selected,
        )
        if base_routes is None:
            telemetry["skip_reason"] = removal_reason
            return None, total_attempts, telemetry

        repaired_routes, attempts, reinserted_count, repair_reason = (
            _repair_destroyed_customers_with_regret2(
                base_routes,
                removed_customers,
                instance,
                top_k=remaining_budget,
            )
        )
        total_attempts += attempts
        if reinserted_count != len(removed_customers):
            last_reason = repair_reason or "incomplete_repair"
            best_removed = max(best_removed, len(removed_customers))
            best_reinserted = max(best_reinserted, reinserted_count)
            continue

        candidate = CvrpSolution(
            routes=tuple(tuple(route) for route in repaired_routes if route)
        )
        valid, _reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            last_reason = "invalid_repair_solution"
            best_removed = max(best_removed, len(removed_customers))
            best_reinserted = max(best_reinserted, reinserted_count)
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        best_removed = max(best_removed, len(removed_customers))
        best_reinserted = max(best_reinserted, reinserted_count)
        if _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
            telemetry["removed_count"] = len(removed_customers)
            telemetry["reinserted_count"] = reinserted_count
        else:
            last_reason = "repair_produced_no_improvement"

    if best_solution is not None:
        return best_solution, total_attempts, telemetry
    telemetry["removed_count"] = best_removed
    telemetry["reinserted_count"] = best_reinserted
    if (
        last_reason == "repair_budget_exhausted"
        and best_removed > 0
        and best_reinserted == best_removed
    ):
        last_reason = "repair_produced_no_improvement"
    telemetry["skip_reason"] = last_reason or "repair_produced_no_improvement"
    return None, total_attempts, telemetry


def _rank_route_pair_swap_candidates(
    routes: list[list[int]],
    instance: CvrpInstance,
    *,
    top_k: int,
) -> list[tuple[float, int, int, int, int]]:
    if len(routes) < 2 or top_k <= 0:
        return []

    route_distances = [instance.route_distance(tuple(route)) for route in routes]
    route_worst_savings = [
        max(
            (_route_removal_saving(route, pos, instance) for pos in range(len(route))),
            default=0.0,
        )
        for route in routes
    ]
    route_pairs: list[tuple[float, int, int]] = []
    for left_index, left_route in enumerate(routes):
        if not left_route:
            continue
        for right_index in range(left_index + 1, len(routes)):
            if not routes[right_index]:
                continue
            score = (
                route_distances[left_index]
                + route_distances[right_index]
                + route_worst_savings[left_index]
                + route_worst_savings[right_index]
            )
            route_pairs.append((float(score), left_index, right_index))
    route_pairs.sort(key=lambda item: (-item[0], item[1], item[2]))

    pair_cap = max(1, min(len(route_pairs), max(8, top_k * 2)))
    position_cap = max(2, min(8, top_k + 1))
    ranked: list[tuple[float, int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for _score, left_index, right_index in route_pairs[:pair_cap]:
        left_route = routes[left_index]
        right_route = routes[right_index]
        left_positions = _rank_swap_positions(left_route, instance, position_cap)
        right_positions = _rank_swap_positions(right_route, instance, position_cap)
        before_distance = route_distances[left_index] + route_distances[right_index]
        for left_pos in left_positions:
            for right_pos in right_positions:
                key = (left_index, right_index, left_pos, right_pos)
                if key in seen:
                    continue
                seen.add(key)
                candidate_left = list(left_route)
                candidate_right = list(right_route)
                candidate_left[left_pos], candidate_right[right_pos] = (
                    candidate_right[right_pos],
                    candidate_left[left_pos],
                )
                if (
                    instance.route_load(tuple(candidate_left)) > instance.capacity
                    or instance.route_load(tuple(candidate_right)) > instance.capacity
                ):
                    estimated_delta = float("-inf")
                else:
                    after_distance = instance.route_distance(
                        tuple(candidate_left)
                    ) + instance.route_distance(tuple(candidate_right))
                    estimated_delta = float(before_distance - after_distance)
                ranked.append(
                    (estimated_delta, left_index, right_index, left_pos, right_pos)
                )
    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3], item[4]))
    return ranked[: max(0, top_k)]


def _rank_swap_positions(
    route: list[int],
    instance: CvrpInstance,
    limit: int,
) -> list[int]:
    records = [
        (
            _route_removal_saving(route, pos, instance),
            pos == 0 or pos == len(route) - 1,
            -pos,
            pos,
        )
        for pos in range(len(route))
    ]
    records.sort(key=lambda item: (-item[0], not item[1], item[2]))
    return [pos for _saving, _is_endpoint, _neg_pos, pos in records[:limit]]


def _rank_worst_removal_customers(
    routes: list[list[int]],
    instance: CvrpInstance,
) -> list[tuple[float, int, int, int]]:
    removable: list[tuple[float, int, int, int]] = []
    for route_index, route in enumerate(routes):
        for pos, customer in enumerate(route):
            removable.append(
                (
                    _route_removal_saving(route, pos, instance),
                    route_index,
                    pos,
                    customer,
                )
            )
    removable.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return removable


def _bounded_destroy_repair_subsets(
    removable: list[tuple[float, int, int, int]],
    destroy_count: int,
) -> list[list[tuple[float, int, int, int]]]:
    max_count = min(len(removable), destroy_count)
    if max_count <= 0:
        return []
    sizes = [max_count]
    for size in (4, 3, 2, 1):
        if 0 < size < max_count and size not in sizes:
            sizes.append(size)
    return [removable[:size] for size in sizes]


def _remove_destroy_subset(
    routes: list[list[int]],
    selected: list[tuple[float, int, int, int]],
) -> tuple[list[list[int]] | None, list[int], str]:
    base_routes = [list(route) for route in routes]
    removed_customers = [
        customer for _saving, _route_index, _pos, customer in selected
    ]
    for _saving, route_index, pos, customer in sorted(
        selected,
        key=lambda item: (item[1], item[2]),
        reverse=True,
    ):
        if route_index >= len(base_routes) or pos >= len(base_routes[route_index]):
            return None, removed_customers, "stale_removal_position"
        removed = base_routes[route_index].pop(pos)
        if removed != customer:
            return None, removed_customers, "stale_removal_customer"
    return base_routes, removed_customers, ""


def _route_removal_saving(
    route: list[int],
    pos: int,
    instance: CvrpInstance,
) -> float:
    customer = route[pos]
    prev_node = instance.depot if pos == 0 else route[pos - 1]
    next_node = instance.depot if pos == len(route) - 1 else route[pos + 1]
    return float(
        instance.distance(prev_node, customer)
        + instance.distance(customer, next_node)
        - instance.distance(prev_node, next_node)
    )


def _bounded_destroy_count(customer_count: int, top_k: int) -> int:
    if customer_count <= 1:
        return customer_count
    budget_count = max(2, min(6, max(2, top_k // 4)))
    return min(max(2, customer_count - 1), budget_count)


def _repair_destroyed_customers_with_regret2(
    base_routes: list[list[int]],
    removed_customers: list[int],
    instance: CvrpInstance,
    *,
    top_k: int,
) -> tuple[list[list[int]], int, int, str]:
    routes = [list(route) for route in base_routes]
    pending = list(removed_customers)
    attempts = 0
    reinserted_count = 0
    while pending:
        if attempts >= top_k:
            return routes, attempts, reinserted_count, "repair_budget_exhausted"
        remaining_budget = max(0, top_k - attempts)
        per_customer_budget = _repair_candidate_budget_per_customer(
            remaining_budget,
            len(pending),
        )
        ranked_customers: list[
            tuple[float, float, int, _RepairInsertion, list[_RepairInsertion]]
        ] = []
        for customer in pending:
            customer_budget = min(per_customer_budget, top_k - attempts)
            if customer_budget <= 0:
                break
            insertions = _bounded_regret_insertions(
                routes,
                customer,
                instance,
                remaining_budget=customer_budget,
            )
            attempts += len(insertions)
            if not insertions:
                continue
            best = insertions[0]
            if len(insertions) >= 2:
                regret = insertions[1].delta - best.delta
            else:
                regret = float("inf")
            ranked_customers.append((regret, best.delta, customer, best, insertions))
        if not ranked_customers:
            reason = "repair_budget_exhausted" if attempts >= top_k else "no_feasible_insertion"
            return routes, attempts, reinserted_count, reason
        ranked_customers.sort(key=lambda item: (-item[0], item[1], item[2]))
        _regret, _best_delta, customer, insertion, _insertions = ranked_customers[0]
        if insertion.route_index == len(routes):
            routes.append([customer])
        else:
            routes[insertion.route_index].insert(insertion.insert_pos, customer)
        pending.remove(customer)
        reinserted_count += 1
    return routes, attempts, reinserted_count, ""


def _repair_candidate_budget_per_customer(
    remaining_budget: int,
    pending_count: int,
) -> int:
    if remaining_budget <= 0 or pending_count <= 0:
        return 0
    return max(1, min(4, remaining_budget // pending_count))


class _RepairInsertion:
    def __init__(self, route_index: int, insert_pos: int, delta: float) -> None:
        self.route_index = route_index
        self.insert_pos = insert_pos
        self.delta = delta


def _bounded_regret_insertions(
    routes: list[list[int]],
    customer: int,
    instance: CvrpInstance,
    *,
    remaining_budget: int,
) -> list[_RepairInsertion]:
    if remaining_budget <= 0:
        return []
    records: list[_RepairInsertion] = []
    demand = instance.demand(customer)
    per_route_cap = max(1, min(8, remaining_budget))
    for route_index, route in enumerate(routes):
        if len(records) >= remaining_budget:
            break
        if instance.route_load(tuple(route)) + demand > instance.capacity:
            continue
        route_records = [
            _RepairInsertion(
                route_index,
                insert_pos,
                _insertion_delta(route, customer, insert_pos, instance),
            )
            for insert_pos in range(len(route) + 1)
        ]
        route_records.sort(
            key=lambda item: (item.delta, -item.insert_pos, item.route_index)
        )
        take = min(per_route_cap, remaining_budget - len(records))
        records.extend(route_records[:take])
    if len(records) < remaining_budget and demand <= instance.capacity:
        records.append(
            _RepairInsertion(
                len(routes),
                0,
                instance.route_distance((customer,)),
            )
        )
    records.sort(key=lambda item: (item.delta, -item.insert_pos, item.route_index))
    return records[:remaining_budget]


def _insertion_delta(
    route: list[int],
    customer: int,
    insert_pos: int,
    instance: CvrpInstance,
) -> float:
    prev_node = instance.depot if insert_pos == 0 else route[insert_pos - 1]
    next_node = instance.depot if insert_pos == len(route) else route[insert_pos]
    return float(
        instance.distance(prev_node, customer)
        + instance.distance(customer, next_node)
        - instance.distance(prev_node, next_node)
    )


def _main_search_accepts(
    candidate: Mapping[str, int | float],
    current: Mapping[str, int | float],
    *,
    min_distance_improvement: float,
) -> bool:
    candidate_fleet = float(candidate.get("fleet_violation", 0))
    current_fleet = float(current.get("fleet_violation", 0))
    if candidate_fleet < current_fleet:
        return True
    if candidate_fleet > current_fleet:
        return False
    candidate_distance = float(candidate.get("total_distance", 0.0))
    current_distance = float(current.get("total_distance", 0.0))
    threshold = max(_OBJECTIVE_TOLERANCE, float(min_distance_improvement))
    return candidate_distance < current_distance - threshold


def _main_search_plan_int(
    audit: Mapping[str, Any],
    section_name: str,
    field_name: str,
) -> int:
    plan = audit.get("main_search_plan")
    if not isinstance(plan, Mapping):
        return 0
    section = plan.get(section_name)
    if not isinstance(section, Mapping):
        return 0
    return _as_nonnegative_int(section.get(field_name))


def _perturb_solution(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    rng: random.Random,
    strength: int,
) -> CvrpSolution | None:
    routes = [list(route) for route in solution.routes]
    for _ in range(max(1, strength)):
        candidates = [
            index for index, route in enumerate(routes)
            if len(route) >= 2
        ]
        if not candidates:
            return None
        route_index = rng.choice(candidates)
        route = routes[route_index]
        left = rng.randrange(len(route))
        right = rng.randrange(len(route))
        if left == right:
            continue
        route[left], route[right] = route[right], route[left]
    candidate = CvrpSolution(routes=tuple(tuple(route) for route in routes if route))
    if all(instance.route_load(route) <= instance.capacity for route in candidate.routes):
        return candidate
    return None


def _record_main_search_component_attempts(
    audit: dict[str, Any],
    component: str,
    attempts: int,
) -> None:
    component_attempts = audit.setdefault("main_search_component_attempts", {})
    component_attempts[component] = (
        _as_nonnegative_int(component_attempts.get(component)) + attempts
    )


def _record_main_search_component_attempted(
    audit: dict[str, Any],
    component: str,
) -> None:
    attempted = audit.setdefault("main_search_attempted_components", [])
    if not isinstance(attempted, list):
        attempted = []
        audit["main_search_attempted_components"] = attempted
    if component not in attempted:
        attempted.append(component)
    _refresh_main_search_component_coverage_status(audit)


def _refresh_main_search_component_coverage_status(
    audit: dict[str, Any],
    selected_components: list[str] | None = None,
) -> None:
    selected = (
        list(selected_components)
        if selected_components is not None
        else list(audit.get("main_search_selected_components") or [])
    )
    attempted = list(audit.get("main_search_attempted_components") or [])
    required = sorted(_FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS)
    selected_deep = [
        component
        for component in selected
        if component in _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
    ]
    attempted_deep = [
        component
        for component in attempted
        if component in _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
    ]
    missing = [
        component
        for component in required
        if component not in set(selected_deep)
    ]
    unattempted = [
        component
        for component in required
        if component not in set(attempted_deep)
    ]
    active = bool(audit.get("main_search_strategy_active"))
    if not active:
        status = "inactive"
    elif missing:
        status = "missing_forced_diagnostic_deep_components"
    elif unattempted:
        status = "selected_not_attempted"
    else:
        status = "deep_components_attempted"
    audit["main_search_deep_components_selected"] = selected_deep
    audit["main_search_component_coverage_status"] = {
        "status": status,
        "required_deep_components": required,
        "selected_deep_components": selected_deep,
        "missing_deep_components": missing,
        "attempted_deep_components": attempted_deep,
        "unattempted_deep_components": unattempted,
    }


def _record_main_search_component_accepted(
    audit: dict[str, Any],
    component: str,
) -> None:
    component_accepted = audit.setdefault("main_search_component_accepted", {})
    component_accepted[component] = (
        _as_nonnegative_int(component_accepted.get(component)) + 1
    )
    accepted = audit.setdefault("main_search_accepted_components", [])
    if not isinstance(accepted, list):
        accepted = []
        audit["main_search_accepted_components"] = accepted
    if component not in accepted:
        accepted.append(component)


def _record_main_search_component_skip(
    audit: dict[str, Any],
    component: str,
    reason: str,
) -> None:
    normalized_reason = reason.strip() if reason else "skipped"
    skipped = audit.setdefault("main_search_skipped_components", [])
    if not isinstance(skipped, list):
        skipped = []
        audit["main_search_skipped_components"] = skipped
    if component not in skipped:
        skipped.append(component)
    all_reasons = audit.setdefault("main_search_component_skip_reasons", {})
    component_reasons = all_reasons.setdefault(component, {})
    if not isinstance(component_reasons, dict):
        component_reasons = {}
        all_reasons[component] = component_reasons
    component_reasons[normalized_reason] = (
        _as_nonnegative_int(component_reasons.get(normalized_reason)) + 1
    )


def _main_search_skip_reason(
    telemetry: Mapping[str, Any],
    attempts: int,
) -> str:
    reason = telemetry.get("skip_reason") if isinstance(telemetry, Mapping) else None
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if attempts <= 0:
        return "no_candidates"
    return "no_improving_candidate"


def _record_main_search_component_candidate_delta(
    audit: dict[str, Any],
    component: str,
    delta: float,
) -> None:
    best_delta = audit.setdefault("main_search_component_best_delta", {})
    current_best = float(best_delta.get(component, 0.0) or 0.0)
    if delta > current_best:
        best_delta[component] = float(delta)
    improvement_counts = audit.setdefault(
        "main_search_component_improvement_counts",
        {},
    )
    if delta > _OBJECTIVE_TOLERANCE:
        improvement_counts[component] = (
            _as_nonnegative_int(improvement_counts.get(component)) + 1
        )


def _record_main_search_component_repair_counts(
    audit: dict[str, Any],
    component: str,
    telemetry: Mapping[str, Any],
) -> None:
    removed = _as_nonnegative_int(telemetry.get("removed_count"))
    reinserted = _as_nonnegative_int(telemetry.get("reinserted_count"))
    fallback = _as_nonnegative_int(telemetry.get("repair_fallback_count"))
    if removed:
        removed_counts = audit.setdefault("main_search_component_removed_counts", {})
        removed_counts[component] = (
            _as_nonnegative_int(removed_counts.get(component)) + removed
        )
    if reinserted:
        reinserted_counts = audit.setdefault(
            "main_search_component_reinserted_counts",
            {},
        )
        reinserted_counts[component] = (
            _as_nonnegative_int(reinserted_counts.get(component)) + reinserted
        )
    if fallback:
        fallback_counts = audit.setdefault(
            "main_search_component_repair_fallback_counts",
            {},
        )
        fallback_counts[component] = (
            _as_nonnegative_int(fallback_counts.get(component)) + fallback
        )


def _record_main_search_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("main_search_component_runtime_ms", {})
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _append_main_search_phase(audit: dict[str, Any], phase: str) -> None:
    phases = audit.setdefault("main_search_phases", [])
    if not isinstance(phases, list):
        phases = []
        audit["main_search_phases"] = phases
    if phases == ["inactive"] or phases == ["plan_invalid"]:
        phases.clear()
    if phase not in phases:
        phases.append(phase)


def _set_main_search_phase_runtime(
    audit: dict[str, Any],
    phase: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("main_search_phase_runtime_ms", {})
    runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _record_algorithm_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("algorithm_component_runtime_ms", {})
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _append_algorithm_phase(audit: dict[str, Any], phase: str) -> None:
    phases = audit.setdefault("algorithm_phases_executed", [])
    if not isinstance(phases, list):
        phases = []
        audit["algorithm_phases_executed"] = phases
    if phases == ["inactive"] or phases == ["plan_invalid"]:
        phases.clear()
    if phase not in phases:
        phases.append(phase)


def _set_algorithm_phase_runtime(
    audit: dict[str, Any],
    phase: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("algorithm_phase_runtime_ms", {})
    runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _objective_distance_delta(
    before: Mapping[str, int | float],
    after: Mapping[str, int | float],
) -> float:
    if float(after.get("fleet_violation", 0)) != float(before.get("fleet_violation", 0)):
        return float(before.get("fleet_violation", 0)) - float(
            after.get("fleet_violation", 0)
        )
    return float(before.get("total_distance", 0.0)) - float(
        after.get("total_distance", 0.0)
    )


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
    baseline_policy_params: Mapping[str, Any] | None = None,
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
        **dict(baseline_policy_params or {}),
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
