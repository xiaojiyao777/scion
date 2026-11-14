from __future__ import annotations

import pytest

from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.policies import baseline_algorithm
from scion.problems.cvrp.policies.baseline_modules import local_search
from scion.problems.cvrp.policies.baseline_modules.state import _Route, _Solution


class _FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now


class _OuterContext:
    def __init__(self, remaining: float) -> None:
        self.remaining = float(remaining)

    def remaining_time(self) -> float:
        return self.remaining


def test_baseline_fraction_is_an_absolute_local_deadline() -> None:
    clock = _FakeClock(100.0)
    outer = _OuterContext(100.0)
    local_limit = baseline_algorithm._algorithm_time_limit(10.0)
    context = baseline_algorithm._DeadlineContext(
        outer,
        local_limit,
        clock=clock,
    )

    assert local_limit == pytest.approx(8.0)
    assert context.remaining_time() == pytest.approx(8.0)

    clock.now += 3.0
    assert context.remaining_time() == pytest.approx(5.0)

    outer.remaining = 2.0
    assert context.remaining_time() == pytest.approx(2.0)
    assert context.remaining_time_ms() == 2000

    clock.now += 10.0
    assert context.remaining_time() == 0.0


class _TickingClock(_FakeClock):
    def __call__(self) -> float:
        current = self.now
        self.now += 1.0
        return current


def _flat_solution() -> _Solution:
    instance = CvrpInstance(
        name="flat_deadline_fixture",
        capacity=12,
        depot=0,
        nodes=tuple(
            CvrpNode(id=node_id, x=0.0, y=0.0, demand=0 if node_id == 0 else 1)
            for node_id in range(13)
        ),
        allowed_routes=2,
        use_integer_cost=True,
    )
    return _Solution(
        instance,
        [
            _Route(instance, range(1, 7)),
            _Route(instance, range(7, 13)),
        ],
    )


@pytest.mark.parametrize(
    "operator",
    [
        lambda solution, context: local_search._two_opt_intra(solution, context, 0.0),
        lambda solution, context: local_search._two_opt_intra_polish(
            solution,
            context,
            0.0,
            "deadline_test",
        ),
        lambda solution, context: local_search._relocate(solution, context, 0.0),
        lambda solution, context: local_search._swap(solution, context, 0.0),
        lambda solution, context: local_search._or_opt(solution, 2, context, 0.0),
        lambda solution, context: local_search._two_opt_star(solution, context, 0.0),
    ],
    ids=[
        "two_opt_intra",
        "two_opt_intra_polish",
        "relocate",
        "swap",
        "or_opt",
        "two_opt_star",
    ],
)
def test_expensive_neighborhood_inner_loops_cooperate_with_deadline(operator) -> None:
    solution = _flat_solution()
    original_routes = solution.routes_as_tuples()
    clock = _TickingClock()
    context = baseline_algorithm._DeadlineContext(
        _OuterContext(100.0),
        3.0,
        clock=clock,
    )
    context.record_move = lambda *args, **kwargs: None

    operator(solution, context)

    assert clock.now == pytest.approx(4.0)
    assert solution.routes_as_tuples() == original_routes
    assert solution.is_feasible()
