"""CVRP solver registry-operator runtime tests."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from scion.problem.bridge import load_problem_spec_v1_from_yaml, legacy_problem_spec_from_v1
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.runtime.audit import runtime_audit_failure_from_raw, runtime_audit_failure_from_result
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"


class _Spec:
    pass


def _runner() -> LocalSubprocessRunner:
    return LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))


def _workspace(tmp_path: Path) -> Path:
    target = tmp_path / "cvrp_ws"
    shutil.copytree(CVRP_DIR, target)
    return target


def _write_operator_case(workspace: Path) -> Path:
    data_dir = workspace / "data"
    data_dir.mkdir(exist_ok=True)
    case_path = data_dir / "operator_case.json"
    case_path.write_text(
        json.dumps(
            {
                "name": "operator_case",
                "capacity": 99,
                "depot": 0,
                "allowed_routes": 1,
                "use_integer_cost": True,
                "nodes": [
                    {"id": 0, "x": 0, "y": 0, "demand": 0},
                    {"id": 1, "x": 0, "y": 1, "demand": 1},
                    {"id": 2, "x": 0, "y": 2, "demand": 1},
                    {"id": 3, "x": 0, "y": 3, "demand": 1},
                    {"id": 4, "x": 1, "y": 0, "demand": 1},
                    {"id": 5, "x": 2, "y": 5, "demand": 1},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return case_path


def _write_synthetic_vrp(tmp_path: Path) -> Path:
    path = tmp_path / "operator_runtime_smoke.vrp"
    path.write_text(
        "\n".join(
            [
                "NAME : operator_runtime_smoke",
                "TYPE : CVRP",
                "DIMENSION : 4",
                "EDGE_WEIGHT_TYPE : EUC_2D",
                "CAPACITY : 10",
                "NODE_COORD_SECTION",
                "1 0 0",
                "2 10 0",
                "3 10 10",
                "4 0 10",
                "DEMAND_SECTION",
                "1 0",
                "2 4",
                "3 3",
                "4 2",
                "DEPOT_SECTION",
                "1",
                "-1",
                "EOF",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.with_suffix(".sol").write_text(
        "Route #1: 2 3 4\nCost : 40\n",
        encoding="utf-8",
    )
    return path


def _run_solver(
    workspace: Path,
    instance_path: str,
    *,
    seed: int = 14,
    registry_path: str | None = None,
) -> dict[str, Any]:
    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path=instance_path,
        seed=seed,
        time_limit_sec=2,
        registry_path="" if registry_path is None else registry_path,
    )
    assert result.success is True, result.stderr
    assert result.output is not None
    assert result.output.feasible is True
    assert result.output_path is not None

    output_path = Path(result.output_path)
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)


def _artifact(raw: dict[str, Any], workspace: Path, instance_path: str):
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / instance_path))
    artifact = adapter.deserialize_solver_output(raw, instance)
    return adapter, instance, artifact


def test_empty_registry_keeps_json_nearest_neighbor_behavior(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 16.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_attempts"] == 0

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_missing_registry_keeps_vrp_nearest_neighbor_behavior(
    tmp_path: Path,
) -> None:
    vrp_path = _write_synthetic_vrp(tmp_path)

    raw = _run_solver(CVRP_DIR, str(vrp_path), seed=11, registry_path=None)

    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 40.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_attempts"] == 0


def test_registry_operator_can_improve_route_and_is_audited(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "better_route.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class BetterRoute:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: better_route",
                "    file_path: operators/better_route.py",
                "    class_name: BetterRoute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 12.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 1
    assert raw["runtime"]["operator_accepted"] == 1
    assert raw["runtime"]["operator_attempts"] == 2
    assert raw["runtime"]["operator_rounds"] == 2
    assert raw["runtime"]["operator_rounds_with_acceptance"] == 1
    assert raw["runtime"]["operator_no_improvement_rounds"] == 1
    assert raw["runtime"]["operator_stop_reason"] == "no_improvement_round"
    assert {
        (event["operator"], event["status"])
        for event in raw["runtime"]["operator_events"]
    } >= {("better_route", "accepted")}

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_noop_registry_operator_stops_after_one_no_improvement_round(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "noop.py").write_text(
        "\n".join(
            [
                "class NoopOperator:",
                "    def execute(self, solution, instance, rng):",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: noop_operator",
                "    file_path: operators/noop.py",
                "    class_name: NoopOperator",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 1
    assert raw["runtime"]["operator_attempts"] == 1
    assert raw["runtime"]["operator_accepted"] == 0
    assert raw["runtime"]["operator_rounds"] == 1
    assert raw["runtime"]["operator_rounds_with_acceptance"] == 0
    assert raw["runtime"]["operator_no_improvement_rounds"] == 1
    assert raw["runtime"]["operator_stop_reason"] == "no_improvement_round"
    assert runtime_audit_failure_from_raw(raw) is None


def test_workspace_local_cvrp_solution_is_coerced_and_can_improve(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "local_model_better_route.py").write_text(
        "\n".join(
            [
                "from models import CvrpSolution",
                "",
                "class LocalModelBetterRoute:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: local_model_better_route",
                "    file_path: operators/local_model_better_route.py",
                "    class_name: LocalModelBetterRoute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"]["total_distance"] == 12.0
    assert raw["runtime"]["operator_accepted"] == 1
    assert raw["runtime"]["operator_errors"] == 0


def test_search_policy_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "search_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "policy_loaded",
        "policy_errors",
        "baseline_time_fraction",
        "operator_round_limit",
        "post_baseline_operators_enabled",
    )
    assert set(required_fields).issubset(raw["runtime"])
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="search_policy",
    ) is None


def test_construction_policy_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "construction_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "construction_surface_loaded",
        "construction_errors",
        "construction_mode",
        "construction_elapsed_ms",
        "construction_routes",
        "construction_distance",
        "construction_feasible",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["construction_surface_loaded"] is True
    assert runtime["construction_errors"] == 0
    assert runtime["construction_mode"] == "nearest_neighbor"
    assert runtime["construction_routes"] == len(raw["routes"])
    assert runtime["construction_distance"] == raw["objective"]["total_distance"]
    assert runtime["construction_feasible"] is True
    assert runtime["baseline_required"] is False
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="construction_policy",
    ) is None


def test_neighborhood_portfolio_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "neighborhood_portfolio"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "portfolio_surface_loaded",
        "portfolio_errors",
        "enabled_components",
        "component_weights",
        "candidate_limits",
        "component_attempts",
        "component_accepted",
        "component_runtime_ms",
        "portfolio_stop_reason",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["portfolio_surface_loaded"] is True
    assert runtime["portfolio_errors"] == 0
    assert "route_local" in runtime["enabled_components"]
    assert runtime["component_weights"]["route_local"] == 1.0
    assert runtime["candidate_limits"]["max_rounds"] == 3
    assert runtime["candidate_limits"]["top_k"] == 16
    assert runtime["component_attempts"]["route_local"] == 0
    assert runtime["component_accepted"]["route_local"] == 0
    assert runtime["component_runtime_ms"]["route_local"] == 0
    assert runtime["portfolio_stop_reason"] == "no_registry_operators"
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="neighborhood_portfolio",
    ) is None


def test_modified_construction_policy_changes_mode_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    return 'demand_descending'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    return 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["runtime"]["construction_surface_loaded"] is True
    assert raw["runtime"]["construction_errors"] == 0
    assert raw["runtime"]["construction_mode"] == "demand_descending"
    assert runtime_audit_failure_from_raw(raw) is None


def test_invalid_construction_policy_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    return 'benchmark_answer_mode'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    return 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["runtime"]["construction_errors"] == 1
    assert raw["runtime"]["construction_mode"] == "nearest_neighbor"
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "construction_runtime_error"
    assert "construction_errors=1" in issue["detail"]
    assert "benchmark_answer_mode" in issue["construction_events"][0]["detail"]


def test_modified_neighborhood_portfolio_changes_component_schedule_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "operators" / "route_local_noop.py").write_text(
        "\n".join(
            [
                "class RouteLocalNoop:",
                "    category = 'route_local'",
                "    def execute(self, solution, instance, rng):",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "operators" / "route_pair_better.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class RoutePairBetter:",
                "    category = 'route_pair'",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: route_pair_better",
                "    file_path: operators/route_pair_better.py",
                "    category: route_pair",
                "    class_name: RoutePairBetter",
                "    weight: 2.0",
                "  - name: route_local_noop",
                "    file_path: operators/route_local_noop.py",
                "    category: route_local",
                "    class_name: RouteLocalNoop",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['route_local']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    return {'route_local': 1.0}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    return {'max_rounds': 20, 'top_k': 1}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert runtime["portfolio_surface_loaded"] is True
    assert runtime["portfolio_errors"] == 0
    assert runtime["enabled_components"] == ["route_local"]
    assert runtime["operator_loaded"] == 1
    assert runtime["operator_attempts"] == 1
    assert runtime["component_attempts"]["route_local"] == 1
    assert runtime["component_attempts"].get("route_pair", 0) == 0
    assert runtime["portfolio_stop_reason"] == "no_improvement_round"
    assert runtime_audit_failure_from_raw(raw) is None


def test_invalid_neighborhood_portfolio_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['unknown_component']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    return {'route_local': -1.0}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    return {'top_k': -1}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["runtime"]["portfolio_surface_loaded"] is True
    assert raw["runtime"]["portfolio_errors"] >= 3
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "portfolio_runtime_error"
    assert "portfolio_errors=" in issue["detail"]
    assert "unknown_component" in issue["portfolio_events"][0]["detail"]


def test_invalid_operator_outputs_do_not_pollute_solution(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_type.py").write_text(
        "\n".join(
            [
                "class BadType:",
                "    def execute(self, solution, instance, rng):",
                "        return []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "operators" / "missing_customers.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class MissingCustomers:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_type",
                "    file_path: operators/bad_type.py",
                "    class_name: BadType",
                "    weight: 2.0",
                "  - name: missing_customers",
                "    file_path: operators/missing_customers.py",
                "    class_name: MissingCustomers",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 2
    assert raw["runtime"]["operator_accepted"] == 0
    assert raw["runtime"]["operator_skipped"] >= 2
    assert raw["runtime"]["operator_errors"] >= 2
    assert raw["runtime"]["operator_invalid_outputs"] >= 2
    assert {
        (event["operator"], event["status"])
        for event in raw["runtime"]["operator_events"]
    } >= {
        ("bad_type", "error"),
        ("missing_customers", "error"),
    }
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True


def test_operator_exception_is_reported_in_run_result_runtime_audit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_attribute.py").write_text(
        "\n".join(
            [
                "class BadAttribute:",
                "    def execute(self, solution, instance, rng):",
                "        _ = instance.vehicle_capacity",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_attribute",
                "    file_path: operators/bad_attribute.py",
                "    class_name: BadAttribute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path="data/operator_case.json",
        seed=14,
        time_limit_sec=2,
        registry_path=str(workspace / "registry.yaml"),
    )

    assert result.success is True
    assert result.output is not None
    assert result.output.runtime["operator_errors"] == 1
    issue = runtime_audit_failure_from_result(result)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"
    assert "vehicle_capacity" in issue["operator_events"][0]["detail"]


def test_registry_path_escape_entry_is_not_loaded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    escaped = tmp_path / "escaped_operator.py"
    escaped.write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class EscapedOperator:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: escaped_operator",
                "    file_path: ../escaped_operator.py",
                "    class_name: EscapedOperator",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_skipped"] == 1
    assert raw["runtime"]["operator_events"] == [
        {
            "operator": "escaped_operator",
            "status": "skipped",
            "detail": "operator path escapes workspace",
        }
    ]
