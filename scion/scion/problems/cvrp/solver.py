"""CVRP solver public facade and active algorithm runtime shell."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import time
from typing import Any

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution
from scion.problems.cvrp.solver_runtime.algorithm_runtime import (
    ObjectiveValue as _ObjectiveValue,
    SolverAlgorithmContext as _SolverAlgorithmContext,
    load_baseline_algorithm as _load_baseline_algorithm,
    nearest_neighbor_solution as _nearest_neighbor_solution,
    solver_algorithm_active as _solver_algorithm_active,
    solver_algorithm_defaults as _solver_algorithm_defaults,
)

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
    construction_mode: str = "nearest_neighbor",
    construction_bias: float = 0.0,
) -> CvrpSolution:
    """Small deterministic construction fallback for invalid algorithm branches.

    The active research path is ``policies/baseline_algorithm.py`` and
    ``policies/baseline_modules/*``. This fallback exists only so the executable
    can still emit a structurally valid payload when that active package fails
    selected-surface runtime validation.
    """

    mode = str(construction_mode or "nearest_neighbor").strip()
    if mode not in _ALLOWED_CONSTRUCTION_MODES:
        mode = "nearest_neighbor"
    if mode == "nearest_neighbor":
        return _nearest_neighbor_solution(instance)

    customers = list(instance.customer_ids)
    if mode == "demand_descending":
        customers.sort(key=lambda customer: (-instance.demand(customer), customer))
    elif mode == "sequential":
        customers.sort()
    elif mode == "nearest_neighbor_demand_bias":
        try:
            bias = max(0.0, min(1.0, float(construction_bias)))
        except (TypeError, ValueError):
            bias = 0.0
        customers = _nearest_neighbor_order(instance, demand_bias=bias)
    return _pack_ordered_customers(instance, customers)


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
    solution, algorithm_audit = _load_baseline_algorithm(
        workspace_root=Path.cwd(),
        instance=instance,
        instance_path=instance_path,
        seed=args.seed,
        rng=rng,
        time_limit_sec=args.time_limit,
        start_time=start,
        adapter=adapter,
    )
    if not _solver_algorithm_active(algorithm_audit) or solution is None:
        solution = solve(instance, rng)
        algorithm_audit.setdefault("solver_algorithm_events", []).append(
            {
                "policy": algorithm_audit.get(
                    "solver_algorithm_path",
                    "policies/baseline_algorithm.py",
                ),
                "status": "warning",
                "detail": "active algorithm failed; emitted nearest-neighbor fallback",
            }
        )

    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    objective = dict(adapter.recompute_objective(artifact, instance))
    raw["objective"] = objective
    raw["runtime"] = {
        "elapsed_s": time.perf_counter() - start,
        "time_limit_s": args.time_limit,
        "registry_path_ignored": bool(str(args.registry or "").strip()),
        **algorithm_audit,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


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


def _configured_data_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for name in ("SCION_PROBLEM_DATA_ROOT", "SCION_CVRP_DATA_ROOT"):
        value = os.environ.get(name, "").strip()
        if value:
            roots.append(Path(value).expanduser().resolve(strict=False))
    return tuple(roots)


def _nearest_neighbor_order(
    instance: CvrpInstance,
    *,
    demand_bias: float,
) -> list[int]:
    unvisited = set(instance.customer_ids)
    ordered: list[int] = []
    current = instance.depot
    while unvisited:
        next_customer = min(
            unvisited,
            key=lambda customer: (
                instance.distance(current, customer)
                - demand_bias * float(instance.demand(customer)),
                customer,
            ),
        )
        ordered.append(next_customer)
        unvisited.remove(next_customer)
        current = next_customer
    return ordered


def _pack_ordered_customers(
    instance: CvrpInstance,
    ordered_customers: list[int],
) -> CvrpSolution:
    routes: list[tuple[int, ...]] = []
    route: list[int] = []
    load = 0
    for customer in ordered_customers:
        demand = instance.demand(customer)
        if route and load + demand > instance.capacity:
            routes.append(tuple(route))
            route = []
            load = 0
        if demand > instance.capacity:
            raise ValueError(f"customer {customer} demand exceeds capacity")
        route.append(customer)
        load += demand
    if route:
        routes.append(tuple(route))
    return CvrpSolution(routes=tuple(routes))


if __name__ == "__main__":
    _main()
