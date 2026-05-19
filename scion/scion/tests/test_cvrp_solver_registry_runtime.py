from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

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
    assert raw["runtime"]["algorithm_blueprint_loaded"] is True
    assert raw["runtime"]["algorithm_blueprint_active"] is False
    assert raw["runtime"]["algorithm_blueprint_errors"] == 0
    assert raw["runtime"]["algorithm_stop_reason"] == "inactive"

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


