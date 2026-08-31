"""Problem-owned smoke coverage for the public CVRP algorithm entrypoint."""

from __future__ import annotations

import importlib
import random
import time
from pathlib import Path

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.solver_runtime.algorithm_runtime import (
    load_baseline_algorithm,
)


class _Spec:
    pass


PUBLIC_DEVELOPMENT_SEEDS = (1703, 1709)


def _candidate_workspace() -> Path:
    """Return the policy workspace selected by Verification's PYTHONPATH."""

    try:
        policies = importlib.import_module("policies")
    except ModuleNotFoundError:
        policies = importlib.import_module("scion.problems.cvrp.policies")
    return Path(policies.__file__).resolve().parent.parent


def test_public_algorithm_entrypoint_returns_valid_solution() -> None:
    problem_root = Path(__file__).resolve().parents[1]
    instance_path = problem_root / "data" / "tiny_development.json"
    instance = CvrpInstance.from_json(str(instance_path))
    solution, audit = load_baseline_algorithm(
        workspace_root=_candidate_workspace(),
        instance=instance,
        instance_path=str(instance_path),
        seed=PUBLIC_DEVELOPMENT_SEEDS[0],
        rng=random.Random(PUBLIC_DEVELOPMENT_SEEDS[0]),
        time_limit_sec=0.01,
        start_time=time.perf_counter(),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
    )

    assert solution is not None
    assert audit["solver_algorithm_active"] is True
    assert audit["solver_algorithm_solution_valid"] is True
    assert audit["solver_algorithm_errors"] == 0
    assert {customer for route in solution.routes for customer in route} == set(
        instance.customer_ids
    )
    assert all(
        instance.route_load(route) <= instance.capacity for route in solution.routes
    )


def test_public_large_shape_returns_before_development_hardwall() -> None:
    """Catch catastrophic deadline overruns on an independent public shape.

    The instance is public, synthetic, and generated independently of every
    Protocol population.  The surrounding D4 sandbox owns the generous hard
    wall-clock bound; this test deliberately avoids a machine-speed assertion.
    Candidate code still has to return a valid large-instance solution under a
    much smaller solver-provided budget.
    """

    customer_count = 719
    instance = CvrpInstance(
        name="public_large_shape_deadline",
        capacity=25,
        depot=0,
        allowed_routes=29,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            *(
                CvrpNode(
                    id=customer_id,
                    x=float((customer_id * 37) % 997),
                    y=float((customer_id * 101) % 991),
                    demand=1,
                )
                for customer_id in range(1, customer_count + 1)
            ),
        ),
    )
    solution, audit = load_baseline_algorithm(
        workspace_root=_candidate_workspace(),
        instance=instance,
        instance_path="public://large-shape-deadline",
        seed=PUBLIC_DEVELOPMENT_SEEDS[1],
        rng=random.Random(PUBLIC_DEVELOPMENT_SEEDS[1]),
        time_limit_sec=0.20,
        start_time=time.perf_counter(),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
    )

    assert solution is not None
    assert audit["solver_algorithm_active"] is True
    assert audit["solver_algorithm_solution_valid"] is True
    assert audit["solver_algorithm_errors"] == 0
    customers = [customer for route in solution.routes for customer in route]
    assert sorted(customers) == list(range(1, customer_count + 1))
    assert len(customers) == len(set(customers))
    assert all(
        instance.route_load(route) <= instance.capacity for route in solution.routes
    )
