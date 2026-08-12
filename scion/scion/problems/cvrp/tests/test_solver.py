"""Problem-owned smoke coverage for the public CVRP algorithm entrypoint."""

from __future__ import annotations

import importlib
import random
import time
from pathlib import Path

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance
from scion.problems.cvrp.solver_runtime.algorithm_runtime import (
    load_baseline_algorithm,
)


class _Spec:
    pass


def _candidate_workspace() -> Path:
    """Return the policy workspace selected by Verification's PYTHONPATH."""

    try:
        policies = importlib.import_module("policies")
    except ModuleNotFoundError:
        policies = importlib.import_module("scion.problems.cvrp.policies")
    return Path(policies.__file__).resolve().parent.parent


def test_public_algorithm_entrypoint_returns_valid_solution() -> None:
    problem_root = Path(__file__).resolve().parents[1]
    instance_path = problem_root / "data" / "tiny_canary.json"
    instance = CvrpInstance.from_json(str(instance_path))
    solution, audit = load_baseline_algorithm(
        workspace_root=_candidate_workspace(),
        instance=instance,
        instance_path=str(instance_path),
        seed=11,
        rng=random.Random(11),
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
