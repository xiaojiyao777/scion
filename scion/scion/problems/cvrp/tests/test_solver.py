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
import itertools
import math
import random
import sys
import time
from contextlib import contextmanager
from fractions import Fraction
from policies import baseline_algorithm
from policies.baseline_modules import local_search, scheduler
from policies.baseline_modules.state import _Route, _Solution
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution

# Assertions belong in collected test_* functions, not just module-level code.
# An arithmetic worksheet, not a proposed scheduling policy. Derive the formula
# for YOUR claim independently before testing a candidate. Exact decimal inputs
# and rational sanity checks avoid accidental handwritten float expectations.
def reference_reserved_seconds(total, minimum, exit_fraction, retained_fraction):
    total, minimum, exit_fraction, retained_fraction = (
        Fraction(str(value))
        for value in (total, minimum, exit_fraction, retained_fraction)
    )
    reserve = max(minimum, total * exit_fraction)
    return float(reserve + max(Fraction(0), total - reserve) * retained_fraction)

def test_reference_arithmetic_before_candidate_assertions():
    assert reference_reserved_seconds(1, .05, .03, .30) == float(Fraction(67, 200))
    assert reference_reserved_seconds(10, .05, .03, .30) == float(Fraction(321, 100))
    for total in (.2, 1, 10):
        reserve = max(.05, total * .03)
        assert math.isclose(reference_reserved_seconds(total, .05, .03, 0), reserve)
        assert math.isclose(reference_reserved_seconds(total, .05, .03, 1), total)
# For an observed float, compare to an independently derived reference using
# math.isclose; never fix a failing probe by copying the candidate's output.

# Independent of candidate _Route.cost, _Solution.total_cost, and cost helpers.
# This is the declared CVRP objective, NOT a claimed optimum for a solver.
def exact_route_cost(instance, route):
    nodes = {node.id: node for node in instance.nodes}
    def edge(left, right):
        if instance.edge_weights is not None:
            return instance.edge_weights[left][right]
        a, b = nodes[left], nodes[right]
        distance = math.hypot(a.x - b.x, a.y - b.y)
        return math.floor(distance + .5) if instance.use_integer_cost else distance
    path = (instance.depot, *route, instance.depot)
    return math.fsum(edge(left, right) for left, right in zip(path, path[1:]))

def exact_solution_cost(instance, routes):
    return math.fsum(exact_route_cost(instance, route) for route in routes)

def assert_feasible(instance, routes):
    demands = {node.id: node.demand for node in instance.nodes}
    customers = [customer for route in routes for customer in route]
    expected = sorted(node.id for node in instance.nodes if node.id != instance.depot)
    assert sorted(customers) == expected  # Detect duplicates as well as omissions.
    assert all(sum(demands[c] for c in route) <= instance.capacity for route in routes)
    if instance.allowed_routes is not None:
        assert sum(bool(route) for route in routes) <= instance.allowed_routes

def assert_internal_consistent(solution):
    instance = solution.instance
    routes = solution.routes_as_tuples()
    assert_feasible(instance, routes)
    for route in solution.routes:
        assert math.isclose(route.cost, exact_route_cost(instance, route.customers),
                            rel_tol=1e-12, abs_tol=1e-6)
        assert route.load == sum(instance.demand(c) for c in route.customers)
    assert math.isclose(solution.total_cost, exact_solution_cost(instance, routes),
                        rel_tol=1e-12, abs_tol=1e-6)

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

@contextmanager
def observe_python_calls(functions):
    # Observe ordinary Python calls without replacing the registry or functions.
    # Wrapping an operator changes `operator is _swap` / `_two_opt_intra` and can
    # silently bypass identity-sensitive cache/argument dispatch in real VNS.
    # Counts prove ENTRY only, not completion, acceptance or retained benefit.
    # Profiling has overhead: never use this diagnostic to claim timed speedup.
    counts = {operation.__code__: 0 for operation in functions}
    previous = sys.getprofile()
    def observe(frame, event, arg):
        if event == 'call' and frame.f_code in counts:
            counts[frame.f_code] += 1
        if previous is not None:
            previous(frame, event, arg)
    sys.setprofile(observe)
    try:
        yield counts
    finally:
        sys.setprofile(previous)

def test_real_entry_and_construction(monkeypatch):
    instance = public_instance()
    original = scheduler._ALNSVNSSolver._initial_solution
    real_vns = scheduler._vns
    observations = []
    vns_observations = []
    def observe(self, instance, reserve):
        result = original(self, instance, reserve)
        assert_internal_consistent(result)
        observations.append((instance.customer_count, result.is_feasible()))
        return result
    def observe_vns(solution, operators, *args, **kwargs):
        # Preserve the actual scheduler, registry, state and collaborators.
        # An empty/mocked registry cannot establish this integration claim.
        before = exact_solution_cost(solution.instance, solution.routes_as_tuples())
        result = real_vns(solution, operators, *args, **kwargs)
        assert_internal_consistent(solution)
        after = exact_solution_cost(solution.instance, solution.routes_as_tuples())
        assert after <= before + 1e-6
        vns_observations.append((len(operators), before, after))
        return result
    monkeypatch.setattr(scheduler._ALNSVNSSolver, "_initial_solution", observe)
    monkeypatch.setattr(scheduler, "_vns", observe_vns)
    with observe_python_calls(scheduler._default_vns_operators()) as calls:
        result = baseline_algorithm.solve(
            instance, random.Random(1703), .3, PublicContext(.3)
        )
    assert observations == [(12, True)]
    assert vns_observations and all(count > 0 for count, _, _ in vns_observations)
    assert sum(calls.values()) > 0
    assert_feasible(instance, result.routes)
    # This proves real entry-to-VNS wiring, not that YOUR new search path is.
    # For your claim, observe its actual transition without changing dispatch
    # identity, and assert the functional consequence rather than just a call.
    # Do not turn off guards just to make an inactive path appear exercised.
    # If the current design intentionally no longer uses VNS, adapt this optional
    # example to its actual collaborators instead of reinstalling a mechanism.

def test_real_operator_collaborators():
    instance = public_instance()
    solution = _Solution(instance, [
        _Route(instance, range(1, 7)), _Route(instance, range(7, 13))
    ])
    for operation in local_search._default_vns_operators():
        current = solution.copy()
        operation(current, PublicContext(.3), 0.)
        assert_internal_consistent(current)
    # If adding a new collaborator/oracle, instantiate its REAL class here.
    # A fake class with invented methods cannot establish integration correctness.
    # For poll-cutoff/atomicity tests, count the unrestricted control and replay
    # EACH cutoff with identical start state, active frontier and instrumentation.
    # Changing eligible routes changes the work/poll count: a completed accepted
    # move is then not evidence of an interrupted commit. Poll clocks establish
    # only that isolated boundary property, not real wall-clock responsiveness.

def test_real_entry_across_public_route_shapes(monkeypatch):
    # Multiple synthetic sizes/capacities and seeds; none is a Protocol case.
    # Keep real construction, budget, registry and operator identities. The call
    # observer does not force a guard, route shape or optional cache argument.
    real_initial = scheduler._ALNSVNSSolver._initial_solution
    constructions = []
    def initial(self, instance, reserve):
        result = real_initial(self, instance, reserve)
        assert_internal_consistent(result)
        constructions.append(tuple(len(route.customers) for route in result.routes))
        return result
    monkeypatch.setattr(scheduler._ALNSVNSSolver, '_initial_solution', initial)
    for count, capacity in ((40, 10), (320, 10), (320, 40)):
        nodes = (CvrpNode(0, 0., 0., 0),) + tuple(
            CvrpNode(i, float(i // 8), float(i % 8), 1)
            for i in range(1, count + 1)
        )
        matrix = tuple(tuple(float(math.floor(math.hypot(a.x-b.x, a.y-b.y) + .5))
                             for b in nodes) for a in nodes)
        instance = CvrpInstance(name='public_entry_shapes', capacity=capacity,
                                depot=0, allowed_routes=count // capacity,
                                nodes=nodes, edge_weights=matrix)
        for seed in (1703, 1709):
            constructions.clear()
            # Allow actual construction time at the larger size. This is a
            # public fixture budget, not a patched clock/guard or Protocol limit.
            seconds = .35 if count == 40 else 1.4
            with observe_python_calls(scheduler._default_vns_operators()) as calls:
                result = baseline_algorithm.solve(
                    instance, random.Random(seed), seconds, PublicContext(seconds)
                )
            assert len(constructions) == 1
            assert sum(calls.values()) > 0  # Empty/bypassed registry is not coverage.
            assert_feasible(instance, result.routes)
            assert math.isfinite(exact_solution_cost(instance, result.routes))
    # This establishes only the observed real entry/construction/operator paths.
    # Add functional assertions at YOUR actual accepted transition to distinguish
    # entering a method, completing a trial, accepting it, and improving best.
    # Do not infer those events from method names or an iteration counter alone.
    # More public seeds/shapes do not prove timed improvement or generalization;
    # complete paired Protocol evidence remains the quality comparison.

def reference_two_opt(instance, start):
    # Tiny fixed-start first-improvement reference, deliberately rescoring every
    # full route. No candidate delta helpers, cached values or telemetry.
    # This is ONE example of checking an equivalence claim, not a requirement
    # that a new algorithm preserve this neighborhood or selection policy.
    route = tuple(start)
    transitions = []
    while True:
        before = exact_route_cost(instance, route)
        accepted = None
        for left in range(len(route) - 1):
            for right in range(left + 1, len(route)):
                trial = route[:left] + tuple(reversed(route[left:right + 1])) + route[right + 1:]
                if exact_route_cost(instance, trial) < before - 1e-9:
                    accepted = trial
                    break
            if accepted is not None:
                break
        if accepted is None:
            return route, transitions
        transitions.append(accepted)
        route = accepted

def test_reference_known_transition():
    # Independently solved sanity anchor BEFORE comparing a candidate. Every
    # off-diagonal arc is >=1; this four-arc tour attains the lower bound 4.
    # The known first move is derived from the matrix, not candidate output.
    matrix = ((0., 1., 10., 1.), (1., 0., 1., 10.),
              (10., 1., 0., 1.), (1., 10., 1., 0.))
    instance = CvrpInstance(
        name='public_known_transition', capacity=3, depot=0, allowed_routes=1,
        nodes=tuple(CvrpNode(i, 0., 0., int(i > 0)) for i in range(4)),
        edge_weights=matrix,
    )
    assert exact_route_cost(instance, (1, 3, 2)) == 22.
    assert exact_route_cost(instance, (1, 2, 3)) == 4.
    assert reference_two_opt(instance, (1, 3, 2)) == ((1, 2, 3), [(1, 2, 3)])
    assert reference_two_opt(instance, (1, 2, 3)) == ((1, 2, 3), [])

def test_tiny_fixed_start_reference(monkeypatch):
    # Public synthetic symmetric matrix, unrelated to any Protocol population.
    # CvrpInstance rejects asymmetric matrices; do not claim directed coverage.
    count = 5
    matrix = tuple(tuple(0. if i == j else float(1 + (i + j + 3*i*j) % 23)
                         for j in range(count + 1)) for i in range(count + 1))
    instance = CvrpInstance(
        name="public_exact_reference", capacity=count, depot=0, allowed_routes=1,
        nodes=tuple(CvrpNode(i, 0., 0., int(i > 0)) for i in range(count + 1)),
        edge_weights=matrix,
    )
    # Only 5! starts. Exhaustive tiny checks are bounded correctness diagnostics,
    # not a benchmark or evidence of throughput on a larger timed instance.
    real_rebuild = _Solution.rebuild_index
    observed_transitions = []
    def observe_rebuild(self):
        result = real_rebuild(self)
        observed_transitions.append(tuple(self.routes[0].customers))
        return result
    monkeypatch.setattr(_Solution, "rebuild_index", observe_rebuild)
    for start in itertools.permutations(range(1, count + 1)):
        expected, transitions = reference_two_opt(instance, start)
        solution = _Solution(instance, [_Route(instance, start)])
        observed_transitions.clear()
        context = PublicContext(2.)
        changed = local_search._two_opt_intra(solution, context, 0.)
        assert context.remaining_time() > 0.  # Expired probe is not equivalence.
        assert solution.routes_as_tuples() == (expected,)
        assert changed == bool(transitions)
        assert observed_transitions == transitions
        assert_internal_consistent(solution)
    # Rebuild observations fit this implementation only. If a changed design
    # batches index updates, instrument its real accepted-transition point instead;
    # do not claim move-sequence equality from final objective equality alone.
    # Extend independent references to EVERY kernel covered by your own claim.

def test_public_large_entry_deadline():
    count = 719
    nodes = (CvrpNode(0, 0., 0., 0),) + tuple(
        CvrpNode(i, float((i * 37) % 997), float((i * 101) % 991), 1)
        for i in range(1, count + 1)
    )
    # Same rounded geometric objective, explicitly materialized for this public
    # fixture. Raw CvrpInstance geometry performs linear node lookups that can
    # dominate a short probe. This matrix fixture does not establish geometric
    # lookup throughput or represent every production instance implementation.
    matrix = tuple(tuple(float(math.floor(math.hypot(a.x-b.x, a.y-b.y) + .5))
                         for b in nodes) for a in nodes)
    instance = CvrpInstance(
        name="public_probe_large_deadline", capacity=25, depot=0, allowed_routes=29,
        nodes=nodes, edge_weights=matrix,
    )
    context = PublicContext(.20)
    result = baseline_algorithm.solve(instance, random.Random(1709), .20, context)
    assert_feasible(instance, result.routes)
    assert math.isfinite(exact_solution_cost(instance, result.routes))
    # This asserts return/feasibility, NOT a .20-second elapsed-time bound.
    # The existing outer sandbox hardwall bounds this probe; no speed threshold
    # or throughput claim. This budget can expire before a new path is reached.
    # For that claim, also test the actual path with its real deadline context.
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
