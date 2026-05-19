from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_invalid_main_search_strategy_output_is_selected_surface_runtime_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.8, 'params': {}},",
                "        'improvement': {'enabled_components': ['unknown_move'], 'rounds': 1, 'top_k': 8},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
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
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )

    assert raw["runtime"]["main_search_strategy_errors"] >= 1
    assert raw["runtime"]["main_search_strategy_active"] is False
    assert raw["runtime"]["main_search_stop_reason"] == "invalid_plan"
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_strategy_errors" in issue["detail"]
    assert "main_search_strategy_errors" in issue["failed_runtime_fields"]
    assert "unknown_move" in json.dumps(raw["runtime"]["main_search_strategy_events"])


def test_policy_surfaces_accept_safe_cvrp_instance_api_without_runtime_errors(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "search_policy.py").write_text(
        "\n".join(
            [
                "def baseline_time_fraction(instance, time_limit_sec):",
                "    return 0.5 if instance.customer_count == len(instance.customer_ids) else 0.6",
                "",
                "def max_operator_rounds(instance, time_limit_sec):",
                "    return min(3, max(1, instance.customer_count))",
                "",
                "def enable_post_baseline_operators(instance, time_limit_sec):",
                "    return len(instance.customer_ids) > 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    total_demand = sum(instance.demands[c] for c in instance.customer_ids)",
                "    return 'nearest_neighbor_demand_bias' if total_demand <= instance.capacity else 'nearest_neighbor'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    farthest = max((instance.distance(instance.depot, c) for c in instance.customer_ids), default=0.0)",
                "    return 0.2 if farthest >= 0.0 else 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['route_local', 'route_pair'] if instance.customer_count == len(instance.customer_ids) else ['registry_operator']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    avg_demand = sum(instance.demands[c] for c in instance.customer_ids) / max(1, instance.customer_count)",
                "    demand_ratio = avg_demand / max(1, instance.capacity)",
                "    return {'route_local': 1.0, 'route_pair': min(5.0, 1.0 + demand_ratio)}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    count = instance.customer_count",
                "    return {",
                "        'max_rounds': min(3, count),",
                "        'top_k': min(4, count),",
                "        'total_attempts': min(200, count * 4),",
                "        'per_component_attempts': min(80, max(1, count * 2)),",
                "    }",
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
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["policy_errors"] == 0
    assert runtime["baseline_time_fraction"] == 0.5
    assert runtime["operator_round_limit"] == 3
    assert runtime["post_baseline_operators_enabled"] is True
    assert runtime["construction_errors"] == 0
    assert runtime["construction_mode"] == "nearest_neighbor_demand_bias"
    assert runtime["construction_bias"] == 0.2
    assert runtime["portfolio_errors"] == 0
    assert runtime["enabled_components"] == ["route_local", "route_pair"]
    assert runtime["candidate_limits"]["top_k"] == 4
    for surface_name in (
        "search_policy",
        "construction_policy",
        "neighborhood_portfolio",
    ):
        assert (
            runtime_audit_failure_from_raw(
                raw,
                problem_spec=legacy_spec,
                selected_surface=surface_name,
            )
            is None
        )


def test_search_policy_using_instance_customers_fails_runtime_audit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "search_policy.py").write_text(
        "\n".join(
            [
                "def baseline_time_fraction(instance, time_limit_sec):",
                "    return 0.7 if instance.customers else 0.8",
                "",
                "def max_operator_rounds(instance, time_limit_sec):",
                "    return 1",
                "",
                "def enable_post_baseline_operators(instance, time_limit_sec):",
                "    return True",
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
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="search_policy",
    )

    assert raw["runtime"]["policy_errors"] == 1
    assert issue is not None
    assert issue["error_category"] == "policy_runtime_error"
    assert "customers" in json.dumps(raw["runtime"]["policy_events"])


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


