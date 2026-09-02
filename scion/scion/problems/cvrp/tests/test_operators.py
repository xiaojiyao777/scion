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


class _ExpiringContext(_RecordingContext):
    def __init__(self, *, live_checks: int) -> None:
        super().__init__()
        self.live_checks = live_checks

    def remaining_time(self) -> float:
        self.live_checks -= 1
        return 1.0 if self.live_checks >= 0 else 0.0


@pytest.mark.parametrize(
    ("operator_name", "is_destroy"),
    [
        ("_random_removal", True),
        ("_worst_removal", True),
        ("_shaw_removal", True),
        ("_route_removal", True),
        ("_greedy_insertion", False),
        ("_regret2_insertion", False),
        ("_regret3_insertion", False),
    ],
)
def test_destroy_and_repair_require_deadline_context(
    operator_name: str,
    is_destroy: bool,
) -> None:
    destroy_repair = _candidate_module("baseline_modules.destroy_repair")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    solution = state._Solution(
        instance,
        [
            state._Route(instance, [1, 2]),
            state._Route(instance, [3, 4]),
        ],
    )
    operator = getattr(destroy_repair, operator_name)

    with pytest.raises(TypeError, match="context"):
        operator(solution, 2 if is_destroy else [2], random.Random(1703))


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
    "repair_name", ["_greedy_insertion", "_regret2_insertion", "_regret3_insertion"]
)
def test_repair_deadline_polling_preserves_live_path(repair_name: str) -> None:
    destroy_repair = _candidate_module("baseline_modules.destroy_repair")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    control = state._Solution(
        instance,
        [
            state._Route(instance, [1]),
            state._Route(instance, [3]),
        ],
    )
    observed = control.copy()
    repair = getattr(destroy_repair, repair_name)

    repair(
        control,
        [2, 4],
        random.Random(1703),
        context=None,
        reserve=0.0,
    )
    repair(
        observed,
        [2, 4],
        random.Random(1703),
        context=_RecordingContext(),
        reserve=0.1,
    )

    assert observed.routes_as_tuples() == control.routes_as_tuples()
    assert observed.total_cost == control.total_cost


@pytest.mark.parametrize(
    "repair_name", ["_greedy_insertion", "_regret2_insertion", "_regret3_insertion"]
)
def test_repair_stops_when_the_internal_deadline_expires(repair_name: str) -> None:
    destroy_repair = _candidate_module("baseline_modules.destroy_repair")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    solution = state._Solution(
        instance,
        [
            state._Route(instance, [1]),
            state._Route(instance, [3]),
        ],
    )
    repair = getattr(destroy_repair, repair_name)

    with pytest.raises(TimeoutError, match="deadline exhausted"):
        repair(
            solution,
            [2, 4],
            random.Random(1703),
            context=_ExpiringContext(live_checks=1),
            reserve=0.1,
        )


@pytest.mark.parametrize(
    "destroy_name",
    ["_random_removal", "_worst_removal", "_shaw_removal", "_route_removal"],
)
def test_destroy_deadline_polling_preserves_live_path(destroy_name: str) -> None:
    destroy_repair = _candidate_module("baseline_modules.destroy_repair")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    control = state._Solution(
        instance,
        [
            state._Route(instance, [1, 2]),
            state._Route(instance, [3, 4]),
        ],
    )
    observed = control.copy()
    destroy = getattr(destroy_repair, destroy_name)

    control_removed = destroy(
        control,
        2,
        random.Random(1703),
        context=None,
        reserve=0.0,
    )
    observed_removed = destroy(
        observed,
        2,
        random.Random(1703),
        context=_RecordingContext(),
        reserve=0.1,
    )

    assert observed_removed == control_removed
    assert observed.routes_as_tuples() == control.routes_as_tuples()
    assert observed.total_cost == control.total_cost


@pytest.mark.parametrize(
    ("destroy_name", "live_checks"),
    [
        ("_random_removal", 1),
        ("_worst_removal", 2),
        ("_shaw_removal", 2),
        ("_route_removal", 1),
    ],
)
def test_destroy_stops_when_its_internal_deadline_expires(
    destroy_name: str,
    live_checks: int,
) -> None:
    destroy_repair = _candidate_module("baseline_modules.destroy_repair")
    state = _candidate_module("baseline_modules.state")
    instance = _instance()
    solution = state._Solution(
        instance,
        [
            state._Route(instance, [1, 2]),
            state._Route(instance, [3, 4]),
        ],
    )
    destroy = getattr(destroy_repair, destroy_name)

    with pytest.raises(TimeoutError, match="deadline exhausted"):
        destroy(
            solution,
            4,
            random.Random(1703),
            context=_ExpiringContext(live_checks=live_checks),
            reserve=0.1,
        )


@pytest.mark.parametrize(
    ("scenario", "expected_reason", "expects_repair"),
    [
        pytest.param(
            "destroy_deadline",
            "deadline_exhausted",
            False,
            id="destroy-deadline",
        ),
        pytest.param(
            "repair_value_error",
            "repair_error",
            True,
            id="repair-value-error",
        ),
        pytest.param(
            "candidate_infeasible",
            "infeasible",
            True,
            id="candidate-infeasible",
        ),
        pytest.param("route_limit", "route_limit", True, id="route-limit"),
    ],
)
def test_scheduler_recovery_retains_valid_incumbent(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_reason: str,
    expects_repair: bool,
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

    destroy_calls = []

    def destroy(_candidate, _count, _rng, *, context, reserve):
        destroy_calls.append((context, reserve))
        if scenario == "destroy_deadline":
            raise scheduler._OperatorDeadlineExpired(
                "destroy/repair deadline exhausted"
            )
        return [1]

    repair_calls = []

    def repair(candidate, _removed, _rng, *, context, reserve) -> None:
        repair_calls.append((context, reserve))
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
    assert destroy_calls == [(context, pytest.approx(0.05))]
    assert repair_calls == (
        [(context, pytest.approx(0.05))] if expects_repair else []
    )
