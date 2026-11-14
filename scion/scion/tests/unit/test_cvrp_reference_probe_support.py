"""Optional public examples remain executable and detect their stated faults.

These are framework regressions for research support, not candidate gates.
Only ordinary synthetic/public fixtures and isolated source copies are used.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    write_development_probe_source,
)


_ROOT = Path(__file__).resolve().parents[2] / "problems/cvrp"


def _example(*tests: str) -> str:
    tree = ast.parse((_ROOT / "tests/test_solver.py").read_text())
    source = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "PUBLIC_PROBE_EXAMPLE"
            for target in node.targets
        )
    )
    example = ast.parse(source)
    example.body = [
        node
        for node in example.body
        if not (
            isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
            and node.name not in tests
        )
    ]
    return ast.unparse(example)


def _run(tmp_path: Path, source: str):
    for path in (_ROOT / "policies").rglob("*.py"):
        destination = tmp_path / path.relative_to(_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    runtime = tmp_path / "problem-runtime/cvrp"
    runtime.mkdir(parents=True)
    for name in ("__init__.py", "models.py"):
        (runtime / name).write_bytes((_ROOT / name).read_bytes())
    probe = write_development_probe_source(
        source, tmp_path, max_chars=64000, max_bytes=100000
    )
    return BubblewrapDevelopmentSandbox().run_probe(
        workspace=str(tmp_path),
        probe_path=probe,
        timeout_sec=10,
        problem_runtime_root=str(runtime.parent),
    )


@pytest.mark.parametrize(
    "test_name,mutation",
    [
        (
            "test_tiny_fixed_start_reference",
            'monkeypatch.setattr(local_search, "_two_opt_intra", lambda *a: False)',
        ),
        (
            "test_real_entry_and_construction",
            'monkeypatch.setattr(scheduler, "_vns", lambda *a, **k: False)',
        ),
        (
            "test_real_entry_and_construction",
            'monkeypatch.setattr(scheduler, "_default_vns_operators", lambda: [])',
        ),
        (
            "test_real_operator_collaborators",
            'monkeypatch.setattr(CvrpInstance, "distance", lambda *a: 0.)',
        ),
        (
            "test_real_entry_across_public_route_shapes",
            'monkeypatch.setattr(scheduler, "_default_vns_operators", lambda: [])',
        ),
        (
            "test_real_entry_across_public_route_shapes",
            'monkeypatch.setattr(baseline_algorithm, "solve", lambda *a: CvrpSolution(()))',
        ),
        (
            "test_reference_known_transition",
            "monkeypatch.setitem(globals(), 'reference_two_opt', "
            "lambda instance, start: (tuple(start), []))",
        ),
    ],
    ids=[
        "skipped-improvements",
        "mock-only-vns",
        "empty-registry",
        "wrong-cost",
        "shape-empty-registry",
        "shape-entry-bypass",
        "reference-skips-known-move",
    ],
)
def test_public_example_falsifies_concrete_mutations(tmp_path, test_name, mutation):
    source = _example(test_name) + (
        "\nimport pytest\n"
        "@pytest.fixture(autouse=True)\n"
        "def inject_fault(monkeypatch):\n"
        f"    {mutation}\n"
    )
    result = _run(tmp_path, source)

    assert result.outcome == "failed", result
    assert result.diagnostic["phase"] == "call"
    assert result.diagnostic["exception_kind"] == "assertion_error"


def test_reference_worksheet_rejects_wrong_expected_arithmetic(tmp_path):
    source = _example("test_reference_arithmetic_before_candidate_assertions")
    source = source.replace("Fraction(67, 200)", "Fraction(321, 1000)")
    assert "Fraction(321, 1000)" in source
    result = _run(tmp_path, source)
    assert result.outcome == "failed"
    assert result.diagnostic["exception_kind"] == "assertion_error"


def test_comparative_reference_distinguishes_additions_from_extra_gain(tmp_path):
    result = _run(tmp_path, _example("test_reference_trial_comparison"))
    assert result.outcome == "passed", result


@pytest.mark.parametrize(
    "replacement",
    [
        "start_cost - proposed_best",
        "float(len(proposed_trials) > len(inherited_trials))",
        "max(0., inherited_best - proposed_best)",
    ],
    ids=["own-gain-is-not-extra-gain", "more-trials-is-not-extra-gain", "keep-losses"],
)
def test_comparative_reference_falsifies_weakened_claims(tmp_path, replacement):
    source = _example("test_reference_trial_comparison")
    assert source.count("inherited_best - proposed_best") == 1
    source = source.replace("inherited_best - proposed_best", replacement)
    result = _run(tmp_path, source)
    assert result.outcome == "failed", result
    assert result.diagnostic["exception_kind"] == "assertion_error"


def test_comparative_reference_rejects_incomplete_solution(tmp_path):
    source = _example() + """
import pytest
def test_missing_customer_cannot_supply_a_comparative_gain():
    instance = public_instance()
    start = (tuple(range(1, 7)), tuple(range(7, 13)))
    incomplete = (tuple(range(1, 7)), tuple(range(7, 12)))
    for inherited, proposed in (([incomplete], []), ([], [incomplete])):
        with pytest.raises(AssertionError):
            reference_trial_comparison(instance, start, inherited, proposed)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "passed", result


def test_reference_frontier_keeps_full_empty_and_partial_scope_distinct(tmp_path):
    result = _run(tmp_path, _example("test_reference_matches_eligible_frontier"))
    assert result.outcome == "passed", result


@pytest.mark.parametrize(
    "replacement",
    ["True", "not active or bool(touched & active)"],
    ids=["ignore-frontier", "empty-frontier-is-not-full"],
)
def test_reference_frontier_falsifies_mismatched_eligibility(tmp_path, replacement):
    source = _example("test_reference_matches_eligible_frontier")
    original = "active is None or bool(touched & active)"
    assert source.count(original) == 1
    result = _run(tmp_path, source.replace(original, replacement))
    assert result.outcome == "failed", result
    assert result.diagnostic["exception_kind"] == "assertion_error"


def test_public_multishape_example_runs_without_disabling_real_paths(tmp_path):
    result = _run(tmp_path, _example("test_real_entry_across_public_route_shapes"))
    assert result.outcome == "passed", result


@pytest.mark.parametrize(
    "test_name",
    [
        "test_real_entry_and_construction",
        "test_real_entry_across_public_route_shapes",
        "test_completed_improvement_survives_real_return",
    ],
)
def test_entry_observer_preserves_identity_sensitive_dispatch(tmp_path, test_name):
    source = _example(test_name) + """
import pytest
@pytest.fixture(autouse=True)
def check_identity(monkeypatch):
    original = scheduler._vns
    expected = tuple(local_search._default_vns_operators())
    def check(solution, operators, *args, **kwargs):
        assert len(operators) == len(expected)
        assert all(actual is real for actual, real in zip(operators, expected))
        return original(solution, operators, *args, **kwargs)
    monkeypatch.setattr(scheduler, '_vns', check)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "passed", result


def test_call_observer_restores_hook_and_preserves_optional_arguments(tmp_path):
    source = _example() + """
def test_observer_lifecycle():
    token = object()
    observed = []
    def operation(*, certificate=None):
        assert certificate is token
        return certificate
    def previous(frame, event, arg):
        if event == 'call' and frame.f_code is operation.__code__:
            observed.append(event)
    def dispatch(candidate):
        assert candidate is operation
        return candidate(certificate=token)
    old = sys.getprofile()
    try:
        sys.setprofile(previous)
        try:
            with observe_python_calls([operation]) as calls:
                assert dispatch(operation) is token
                raise ValueError('exercise cleanup')
        except ValueError:
            pass
        assert sys.getprofile() is previous
        assert calls == {operation.__code__: 1}
        assert observed == ['call']
        assert dispatch(operation) is token
        assert calls == {operation.__code__: 1}  # No leaked observer.
    finally:
        sys.setprofile(old)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "passed", result


def test_independent_known_transition_anchor(tmp_path):
    result = _run(tmp_path, _example("test_reference_known_transition"))
    assert result.outcome == "passed", result


def test_retention_example_runs_real_entry_and_independent_final_scoring(tmp_path):
    result = _run(tmp_path, _example("test_completed_improvement_survives_real_return"))
    assert result.outcome == "passed", result


def test_retention_example_rejects_other_kernel_gain_as_target_coverage(tmp_path):
    source = _example("test_completed_improvement_survives_real_return") + """
import pytest
@pytest.fixture(autouse=True)
def bypass_observed_kernel(monkeypatch):
    original = scheduler._default_vns_operators
    def operators():
        return [op for op in original() if op is not local_search._two_opt_intra]
    monkeypatch.setattr(scheduler, '_default_vns_operators', operators)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "failed", result
    assert result.diagnostic["phase"] == "call"
    assert result.diagnostic["exception_kind"] == "assertion_error"
    expected_line = next(
        index for index, line in enumerate(source.splitlines(), 1)
        if line.strip() == "assert kernel_gains"
    )
    assert result.diagnostic["probe_line"] == expected_line, result


@pytest.mark.parametrize("mode", ["gain", "claim_only", "expired", "exception"])
def test_kernel_observer_distinguishes_return_from_live_gain_and_restores_hook(
    tmp_path, mode
):
    source = _example() + f"""
def test_kernel_observer():
    matrix = ((0., 1., 10., 1.), (1., 0., 1., 10.),
              (10., 1., 0., 1.), (1., 10., 1., 0.))
    instance = CvrpInstance(name='public_observer_control', capacity=3, depot=0,
        allowed_routes=1,
        nodes=tuple(CvrpNode(i, 0., 0., int(i > 0)) for i in range(4)),
        edge_weights=matrix)
    solution = _Solution(instance, [_Route(instance, (1, 3, 2))])
    context = PublicContext(2.)
    token = object()
    # Isolated observer control only, not evidence of real algorithm coverage.
    def operation(solution, context, reserve, *, certificate=None):
        assert certificate is token
        if {mode!r} == 'exception':
            raise ValueError('not a normal return')
        if {mode!r} != 'claim_only':
            solution.routes[0].customers = [1, 2, 3]
            solution.routes[0].recalculate()
            solution.rebuild_index()
        if {mode!r} == 'expired':
            context.start -= 10.
        return True
    def dispatch(candidate):
        assert candidate is operation
        return candidate(solution, context, 0., certificate=token)
    seen = []
    def previous(frame, event, arg):
        if frame.f_code is operation.__code__:
            seen.append(event)
    old = sys.getprofile()
    try:
        sys.setprofile(previous)
        try:
            with observe_boolean_kernel_returns([operation]) as rows:
                dispatch(operation)
        except ValueError:
            assert {mode!r} == 'exception'
        assert sys.getprofile() is previous
        assert seen == ['call', 'return']
        if {mode!r} == 'exception':
            assert rows == []
        else:
            assert len(rows) == 1
            assert rows[0]['before'] == 22.
            assert rows[0]['after'] == (22. if {mode!r} == 'claim_only' else 4.)
            assert rows[0]['live_return'] == ({mode!r} != 'expired')
            gains = [r for r in rows if r['live_return'] and r['changed']
                     and r['after'] < r['before'] - 1e-6]
            assert bool(gains) == ({mode!r} == 'gain')
            dispatch(operation)
            assert len(rows) == 1  # Observer must not leak beyond the context.
    finally:
        sys.setprofile(old)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "passed", result


@pytest.mark.parametrize("fault", ["no_transition", "expired_return", "lost_gain"])
def test_retention_example_rejects_incomplete_or_lost_improvement(tmp_path, fault):
    source = _example("test_completed_improvement_survives_real_return") + f"""
import pytest
@pytest.fixture(autouse=True)
def inject_fault(monkeypatch):
    real_vns = scheduler._vns
    real_solve = baseline_algorithm.solve
    initial = []
    def vns(solution, operators, max_no_improve, context, reserve, *args, **kwargs):
        if not initial:
            initial.append(solution.routes_as_tuples())
        if {fault!r} == 'no_transition':
            context.record_move('vns', attempted=100, accepted=100, delta=100.)
            return True  # A claimed gain with no actual route transition.
        result = real_vns(solution, operators, max_no_improve, context, reserve,
                          *args, **kwargs)
        if {fault!r} == 'expired_return':
            # The entry passes its real nested deadline context, not PublicContext.
            monkeypatch.setattr(context, 'remaining_time', lambda: 0.)
        return result
    def solve(*args, **kwargs):
        initial.clear()
        result = real_solve(*args, **kwargs)
        if {fault!r} == 'lost_gain':
            assert initial
            return CvrpSolution(initial[0])  # Feasible, but discards observed gain.
        return result
    monkeypatch.setattr(scheduler, '_vns', vns)
    monkeypatch.setattr(baseline_algorithm, 'solve', solve)
"""
    result = _run(tmp_path, source)
    assert result.outcome == "failed", result
    assert result.diagnostic["phase"] == "call"
    assert result.diagnostic["exception_kind"] == "assertion_error"


def test_reference_is_independent_of_candidate_cache_and_cost_helpers(tmp_path):
    source = (
        _example()
        + """
def test_independent_reference(monkeypatch):
    def unavailable(*args, **kwargs):
        raise AssertionError('candidate helper must not be the reference')
    instance = public_instance()
    routes = (tuple(range(1, 7)), tuple(range(7, 13)))
    expected = exact_solution_cost(instance, routes)
    assert expected > 0
    # Cache equality would survive this common-mode fault; direct arcs do not.
    monkeypatch.setattr(CvrpInstance, 'distance', unavailable)
    monkeypatch.setattr(CvrpInstance, 'route_distance', unavailable)
    assert exact_solution_cost(instance, routes) == expected
    assert_feasible(instance, routes)
"""
    )
    result = _run(tmp_path, source)

    assert result.outcome == "passed", result


@pytest.mark.parametrize("integer_cost", [False, True])
def test_reference_preserves_declared_matrix_and_geometry_semantics(
    tmp_path, integer_cost
):
    source = (
        _example()
        + f"""
def test_reference_semantics():
    nodes = tuple(CvrpNode(i, i * .9, i * 1.3, int(i > 0)) for i in range(5))
    instance = CvrpInstance(name='public_reference_semantics', capacity=4,
                            depot=0, nodes=nodes, use_integer_cost={integer_cost!r})
    route = (3, 1, 4, 2)
    # Cross-check independent reference against the frozen public model on varied
    # arcs. Neither value comes from a candidate state cache or handwritten sum.
    assert math.isclose(exact_route_cost(instance, route),
                        instance.route_distance(route), abs_tol=1e-9)
    weights = tuple(tuple(float(0 if i == j else 1 + abs(i-j) * 3 + i*j)
                          for j in range(5)) for i in range(5))
    matrix_instance = CvrpInstance(name='public_matrix_reference', capacity=4,
                                   depot=0, nodes=nodes, edge_weights=weights)
    assert exact_route_cost(matrix_instance, route) == matrix_instance.route_distance(route)
    assert exact_route_cost(matrix_instance, ()) == 0
"""
    )
    result = _run(tmp_path, source)

    assert result.outcome == "passed", result


def test_reference_support_stays_optional_and_has_no_private_population():
    tree = ast.parse((_ROOT / "tests/test_solver.py").read_text())
    collected = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert collected == [
        "test_public_algorithm_entrypoint_returns_valid_solution",
        "test_public_large_shape_returns_before_development_hardwall",
    ]
    example = _example()
    assert "Protocol" not in example  # AST rendering drops explanatory comments.
    assert "validation" not in example
    assert "read_text" not in example
    assert "open(" not in example
