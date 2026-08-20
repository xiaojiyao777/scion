"""Problem-owned unit coverage for CVRP scheduler recovery behavior."""

from __future__ import annotations

import importlib
import random

import pytest
from scion.problems.cvrp.models import CvrpInstance, CvrpNode


def _candidate_module(suffix: str):
    """Resolve editable policy code from Verification's candidate PYTHONPATH."""

    try:
        policies = importlib.import_module("policies")
    except ModuleNotFoundError:
        policies = importlib.import_module("scion.problems.cvrp.policies")
    return importlib.import_module(f"{policies.__name__}.{suffix}")


class _RecordingContext:
    def __init__(self) -> None:
        self.alns_iterations: list[dict[str, object]] = []
        self.solution_progress: dict[str, object] = {}

    def elapsed_ms(self) -> int:
        return 0

    def remaining_time(self) -> float:
        return 1.0

    def remaining_time_ms(self) -> int:
        return 1_000

    def record_phase(self, *_args, **_kwargs) -> None:
        return None

    def record_iteration(self, *_args, **_kwargs) -> None:
        return None

    def record_move(self, *_args, **_kwargs) -> None:
        return None

    def record_alns_iteration(self, **record) -> None:
        self.alns_iterations.append(record)

    def record_solution_progress(self, **record) -> None:
        self.solution_progress = record


def _instance() -> CvrpInstance:
    return CvrpInstance(
        name="scheduler_recovery",
        capacity=4,
        depot=0,
        allowed_routes=2,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=2),
            CvrpNode(id=2, x=2.0, y=0.0, demand=2),
            CvrpNode(id=3, x=0.0, y=1.0, demand=2),
            CvrpNode(id=4, x=0.0, y=2.0, demand=2),
        ),
    )


def _cross_route_improvement_instance() -> CvrpInstance:
    """Expose a strictly improving tail exchange with a unique customer set."""

    return CvrpInstance(
        name="cross_route_customer_conservation",
        capacity=2,
        depot=0,
        allowed_routes=2,
        nodes=(
            CvrpNode(id=0, x=5.0, y=-10.0, demand=0),
            CvrpNode(id=1, x=0.0, y=0.0, demand=1),
            CvrpNode(id=2, x=10.0, y=0.0, demand=1),
            CvrpNode(id=3, x=10.0, y=1.0, demand=1),
            CvrpNode(id=4, x=0.0, y=1.0, demand=1),
        ),
    )


def test_two_opt_star_preserves_each_customer_exactly_once() -> None:
    local_search = _candidate_module("baseline_modules.local_search")
    state = _candidate_module("baseline_modules.state")
    instance = _cross_route_improvement_instance()
    solution = state._Solution(
        instance,
        [
            state._Route(instance, [1, 2]),
            state._Route(instance, [3, 4]),
        ],
    )

    assert local_search._two_opt_star(solution, _RecordingContext(), 0.0)

    customers = [customer for route in solution.routes for customer in route.customers]
    assert sorted(customers) == [1, 2, 3, 4]
    assert len(customers) == len(set(customers))
    assert solution.is_feasible()


@pytest.mark.parametrize(
    ("scenario", "expected_reason"),
    [
        pytest.param("repair_value_error", "repair_error", id="repair-value-error"),
        pytest.param("candidate_infeasible", "infeasible", id="candidate-infeasible"),
        pytest.param("route_limit", "route_limit", id="route-limit"),
    ],
)
def test_scheduler_recovery_retains_valid_incumbent(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_reason: str,
) -> None:
    scheduler = _candidate_module("baseline_modules.scheduler")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    incumbent = state._Solution(
        instance,
        [
            state._Route(instance, [1, 2]),
            state._Route(instance, [3, 4]),
        ],
    )
    context = _RecordingContext()
    solver = scheduler._ALNSVNSSolver(
        time_limit=0.1,
        destroy_ratio=(0.1, 0.2),
        segment_length=10,
        reaction_factor=0.2,
        vns_max_no_improve=1,
        use_vns=True,
        cw_threshold=100,
        vns_threshold=100,
        alns_threshold=1_000,
        max_destroy_customers=2,
        max_routes=2,
        context=context,
    )

    def destroy(_candidate, _count, _rng):
        return [1]

    def repair(candidate, _removed, _rng) -> None:
        if scenario == "repair_value_error":
            raise ValueError("repair could not insert the removed customer")
        if scenario == "candidate_infeasible":
            candidate.routes[0].customers.append(3)
            candidate.rebuild_index()
            return
        moved = candidate.routes[0].customers.pop()
        candidate.routes.append(state._Route(instance, [moved]))
        candidate.rebuild_index()

    for name in (
        "_random_removal",
        "_worst_removal",
        "_shaw_removal",
        "_route_removal",
    ):
        monkeypatch.setattr(scheduler, name, destroy)
    for name in ("_greedy_insertion", "_regret2_insertion", "_regret3_insertion"):
        monkeypatch.setattr(scheduler, name, repair)

    budget_checks = iter((True, False))
    monkeypatch.setattr(solver, "_initial_solution", lambda *_args: incumbent.copy())
    monkeypatch.setattr(solver, "_within_budget", lambda *_args: next(budget_checks))
    monkeypatch.setattr(
        solver,
        "_should_run_embedded_vns",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        solver,
        "_should_run_size70_two_opt",
        lambda *_args, **_kwargs: False,
    )

    result = solver.solve(instance, random.Random(11))

    assert result.is_feasible()
    assert result.routes_as_tuples() == incumbent.routes_as_tuples()
    assert result.total_cost == incumbent.total_cost
    assert [item["acceptance_reason"] for item in context.alns_iterations] == [
        expected_reason
    ]
    assert context.solution_progress["final_route_count"] == len(incumbent.routes)
