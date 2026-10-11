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


def test_public_multishape_example_runs_without_disabling_real_paths(tmp_path):
    result = _run(tmp_path, _example("test_real_entry_across_public_route_shapes"))
    assert result.outcome == "passed", result


@pytest.mark.parametrize(
    "test_name",
    ["test_real_entry_and_construction", "test_real_entry_across_public_route_shapes"],
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
