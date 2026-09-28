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

# Optional copyable falsifier, not an additional collected test or formal gate.
# The probe sandbox deliberately does not mount this host suite or Scion core.
# Paste/adapt the string as falsifier_source; do not import this test module.
# This demonstrates entry wiring and real collaborators, not mechanism quality.
# The context is an explicit lightweight fixture, NOT SolverAlgorithmContext;
# recording callbacks are no-ops, so their existence is not activation evidence.
PUBLIC_PROBE_EXAMPLE = """
import random
import time
from policies import baseline_algorithm
from policies.baseline_modules import local_search, scheduler
from policies.baseline_modules.state import _Route, _Solution
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution

def public_instance():
    return CvrpInstance(
        name="public_probe_shape", capacity=6, depot=0, allowed_routes=2,
        nodes=(CvrpNode(0, 0., 0., 0),) + tuple(
            CvrpNode(i, float(i % 4), float(i // 4), 1)
            for i in range(1, 13)
        ),
    )

class PublicContext:
    def __init__(self, seconds):
        self.start = time.perf_counter()
        self.seconds = seconds
    def remaining_time(self):
        return max(0., self.seconds - (time.perf_counter() - self.start))
    def remaining_time_ms(self):
        return int(self.remaining_time() * 1000)
    def elapsed_ms(self):
        return int((time.perf_counter() - self.start) * 1000)
    def make_solution(self, routes):
        return CvrpSolution(tuple(tuple(route) for route in routes))
    def set_stop_reason(self, reason):
        self.stop_reason = reason
    def _record(self, *args, **kwargs):
        pass
    record_phase = record_iteration = record_move = _record
    record_solution_progress = record_objective_probe = _record
    record_telemetry_event = record_best_update = record_alns_iteration = _record

def test_real_entry_and_construction(monkeypatch):
    instance = public_instance()
    original = scheduler._ALNSVNSSolver._initial_solution
    observations = []
    def observe(self, instance, reserve):
        result = original(self, instance, reserve)
        observations.append((instance.customer_count, result.is_feasible()))
        return result
    monkeypatch.setattr(scheduler._ALNSVNSSolver, "_initial_solution", observe)
    result = baseline_algorithm.solve(
        instance, random.Random(1703), .3, PublicContext(.3)
    )
    assert observations == [(12, True)]
    assert sorted(c for route in result.routes for c in route) == list(range(1, 13))
    assert all(instance.route_load(route) <= instance.capacity for route in result.routes)
    # This proves construction is reached, not that YOUR new search path is.
    # For your claim, wrap its real method and assert its functional consequence.
    # Do not turn off guards just to make an inactive path appear exercised.

def test_real_operator_collaborators():
    instance = public_instance()
    solution = _Solution(instance, [
        _Route(instance, range(1, 7)), _Route(instance, range(7, 13))
    ])
    for operation in local_search._default_vns_operators():
        current = solution.copy()
        operation(current, PublicContext(.3), 0.)
        assert current.is_feasible()
        assert abs(current.total_cost - sum(
            instance.route_distance(route) for route in current.routes_as_tuples()
        )) < 1e-6
    # If adding a new collaborator/oracle, instantiate its REAL class here.
    # A fake class with invented methods cannot establish integration correctness.
"""


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
