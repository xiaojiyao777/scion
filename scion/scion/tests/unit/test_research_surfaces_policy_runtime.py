from __future__ import annotations

import random
from pathlib import Path

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpSolution
from scion.problems.cvrp.solver import (
    _baseline_time_budget,
    _load_construction_policy,
    _load_main_search_strategy,
    _load_neighborhood_portfolio,
    _load_search_policy,
    improve_with_registry_operators,
)
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_runtime,
)
from scion.tests.unit.research_surface_helpers import _tiny_instance


def test_cvrp_solver_loads_workspace_search_policy_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.5\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 3\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return False\n",
        encoding="utf-8",
    )

    policy = _load_search_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )
    assert policy["policy_loaded"] is True
    assert policy["policy_errors"] == 0
    assert policy["baseline_time_fraction"] == 0.5
    assert policy["operator_round_limit"] == 3
    assert policy["post_baseline_operators_enabled"] is False
    assert _baseline_time_budget(10.0, policy["baseline_time_fraction"]) == 5.0

    solution, audit = improve_with_registry_operators(
        CvrpSolution(routes=((1,),)),
        _tiny_instance(),
        adapter=CvrpAdapter(object()),  # type: ignore[arg-type]
        rng=random.Random(0),
        registry_path="",
        workspace_root=tmp_path,
        time_limit_sec=10.0,
        start_time=0.0,
        max_operator_rounds=policy["operator_round_limit"],
        post_baseline_operators_enabled=policy[
            "post_baseline_operators_enabled"
        ],
    )
    assert solution.routes == ((1,),)
    assert audit["operator_stop_reason"] == "disabled_by_policy"


def test_invalid_cvrp_search_policy_counts_policy_errors(tmp_path: Path) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 2.0\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 'many'\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    policy = _load_search_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["policy_loaded"] is True
    assert policy["policy_errors"] == 3
    assert policy["baseline_time_fraction"] == 0.95
    assert policy["operator_round_limit"] == 20
    assert policy["post_baseline_operators_enabled"] is True


def test_cvrp_solver_loads_workspace_construction_policy_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    return 'nearest_neighbor_demand_bias'\n\n"
        "def construction_bias(instance, time_limit_sec):\n"
        "    return 0.4\n",
        encoding="utf-8",
    )

    policy = _load_construction_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["construction_surface_loaded"] is True
    assert policy["construction_errors"] == 0
    assert policy["construction_mode"] == "nearest_neighbor_demand_bias"
    assert policy["construction_bias"] == 0.4


def test_invalid_cvrp_construction_policy_counts_construction_errors(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    return 'not_allowed'\n\n"
        "def construction_bias(instance, time_limit_sec):\n"
        "    return 2.0\n",
        encoding="utf-8",
    )

    policy = _load_construction_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["construction_surface_loaded"] is True
    assert policy["construction_errors"] == 2
    assert policy["construction_mode"] == "nearest_neighbor"
    assert policy["construction_bias"] == 1.0


def test_cvrp_solver_loads_workspace_neighborhood_portfolio_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "neighborhood_portfolio.py").write_text(
        "def enabled_components(instance, time_limit_sec):\n"
        "    return ['route_pair']\n\n"
        "def component_weights(instance, time_limit_sec):\n"
        "    return {'route_pair': 2.0}\n\n"
        "def candidate_limits(instance, time_limit_sec):\n"
        "    return {'max_rounds': 2, 'top_k': 1, 'route_pair': 3}\n",
        encoding="utf-8",
    )

    policy = _load_neighborhood_portfolio(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["portfolio_surface_loaded"] is True
    assert policy["portfolio_errors"] == 0
    assert policy["enabled_components"] == ["route_pair"]
    assert policy["component_weights"]["route_pair"] == 2.0
    assert policy["candidate_limits"]["max_rounds"] == 2
    assert policy["candidate_limits"]["top_k"] == 1
    assert policy["candidate_limits"]["route_pair"] == 3


def test_invalid_cvrp_neighborhood_portfolio_counts_portfolio_errors(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "neighborhood_portfolio.py").write_text(
        "def enabled_components(instance, time_limit_sec):\n"
        "    return ['not_a_component']\n\n"
        "def component_weights(instance, time_limit_sec):\n"
        "    return {'route_local': -1.0, 'ghost': 1.0}\n\n"
        "def candidate_limits(instance, time_limit_sec):\n"
        "    return {'top_k': -1, 'bad_limit': 2}\n",
        encoding="utf-8",
    )

    policy = _load_neighborhood_portfolio(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["portfolio_surface_loaded"] is True
    assert policy["portfolio_errors"] >= 5
    assert "registry_operator" in policy["enabled_components"]
    assert policy["component_weights"]["route_local"] == 0.0
    assert policy["candidate_limits"]["top_k"] == 0


def test_cvrp_solver_loads_workspace_main_search_strategy_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor', 'sequential'], 'keep_top_k': 2, 'bias': 0.2},",
                "        'baseline': {'time_fraction': 0.6, 'params': {'destroy_ratio': (0.05, 0.25), 'use_vns': False}},",
                "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair'], 'rounds': 3, 'top_k': 40},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': True, 'stagnation_rounds': 1, 'max_restarts': 1},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    policy = _load_main_search_strategy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["main_search_strategy_loaded"] is True
    assert policy["main_search_strategy_active"] is True
    assert policy["main_search_strategy_errors"] == 0
    assert policy["main_search_construction_methods"] == [
        "nearest_neighbor",
        "sequential",
    ]
    assert policy["main_search_baseline_time_fraction"] == 0.6
    assert policy["main_search_baseline_params"]["destroy_ratio"] == (0.05, 0.25)
    assert policy["main_search_baseline_params"]["use_vns"] is False
    assert policy["main_search_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert policy["main_search_deep_components_selected"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert policy["main_search_component_coverage_status"]["status"] == (
        "selected_not_attempted"
    )
    assert policy["main_search_problem_adaptation_source"] == "defaulted_missing_section"
    assert policy["main_search_strategy_family"] == "balanced_lifecycle"
    assert policy["main_search_instance_profile"]["customer_count"] > 0
    assert policy["main_search_rounds"] == 3
    assert policy["main_search_top_k"] == 40
    assert policy["main_search_post_baseline_operators_enabled"] is False


def test_cvrp_main_search_strategy_problem_adaptation_drives_order_and_thresholds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'problem_adaptation': {",
                "            'strategy_family': 'destroy_repair_recovery',",
                "            'instance_profile': {'scale': 'small', 'route_pressure': 'medium'},",
                "            'phase_objective': 'recovery_to_phase_best',",
                "            'component_roles': {'nearest_neighbor': 'support', 'repo_local_baseline': 'support', 'bounded_destroy_repair': 'primary', 'route_pair_swap': 'support', 'route_pool_recombination': 'disabled', 'strict_improvement_acceptance': 'primary', 'bounded_perturbation': 'probe'},",
                "            'fallback_order': [],",
                "            'evidence_targets': ['main_search_component_phase_delta_sum', 'main_search_component_phase_improvement_counts', 'main_search_component_accepted', 'main_search_restart_count', 'main_search_objective_trace'],",
                "        },",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair'], 'rounds': 2, 'top_k': 32},",
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

    policy = _load_main_search_strategy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["main_search_strategy_active"] is True
    assert policy["main_search_problem_adaptation_source"] == "declared"
    assert policy["main_search_strategy_family"] == "destroy_repair_recovery"
    assert policy["main_search_phase_objective"] == "recovery_to_phase_best"
    assert policy["main_search_declared_instance_profile"] == {
        "scale": "small",
        "route_pressure": "medium",
    }
    assert policy["main_search_instance_profile"]["customer_count"] > 0
    assert policy["main_search_components"] == [
        "bounded_destroy_repair",
        "route_pair_swap",
    ]
    assert policy["main_search_component_order"] == [
        "bounded_destroy_repair",
        "route_pair_swap",
    ]
    assert policy["main_search_component_roles"]["nearest_neighbor"] == "support"
    assert policy["main_search_component_roles"]["strict_improvement_acceptance"] == (
        "primary"
    )
    assert "main_search_component_phase_improvement_counts" in policy[
        "main_search_evidence_targets"
    ]
    assert "main_search_restart_count" in policy["main_search_evidence_targets"]
    assert policy["main_search_strategy_errors"] == 0
    assert policy["main_search_component_min_distance_improvement"][
        "bounded_destroy_repair"
    ] == 0.0
    assert policy["main_search_bounded_destroy_repair_accept_limit"] == 2
    assert policy["recovery_only_policy"] == "allow"


def test_cvrp_main_search_strategy_clamps_aggressive_baseline_params(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {'destroy_ratio': (0.05, 0.50), 'segment_length': 400, 'reaction_factor': 0.05, 'vns_max_no_improve': 10000, 'max_destroy_customers': 200}},",
                "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair'], 'rounds': 5, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': True, 'strength': 3, 'max_perturbations': 2},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    policy = _load_main_search_strategy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["main_search_strategy_active"] is True
    assert policy["main_search_baseline_params_clamped"] is True
    assert policy["main_search_baseline_params"]["destroy_ratio"] == (0.05, 0.35)
    assert policy["main_search_baseline_params"]["segment_length"] == 200
    assert policy["main_search_baseline_params"]["reaction_factor"] == 0.08
    assert policy["main_search_baseline_params"]["vns_max_no_improve"] == 7000
    assert policy["main_search_baseline_params"]["max_destroy_customers"] == 16
    clamp_evidence = policy["main_search_baseline_param_clamps"]
    assert clamp_evidence["applied"] is True
    assert clamp_evidence["status"] == "clamped"
    assert clamp_evidence["count"] == 5
    assert set(clamp_evidence["fields"]) == {
        "destroy_ratio",
        "segment_length",
        "reaction_factor",
        "vns_max_no_improve",
        "max_destroy_customers",
    }
    assert clamp_evidence["clamps"]["destroy_ratio"] == {
        "requested": [0.05, 0.5],
        "effective": [0.05, 0.35],
    }
    assert clamp_evidence["clamps"]["max_destroy_customers"] == {
        "requested": 200,
        "effective": 16,
    }


def test_invalid_cvrp_main_search_strategy_counts_strategy_errors(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['bad_mode'], 'keep_top_k': 0, 'bias': 2.0},",
                "        'baseline': {'time_fraction': 2.0, 'params': {'unknown': 1}},",
                "        'improvement': {'enabled_components': ['unknown_move'], 'rounds': 0, 'top_k': 0},",
                "        'acceptance': {'min_distance_improvement': 20.0},",
                "        'restart': {'enabled': 'yes', 'stagnation_rounds': -1, 'max_restarts': 99},",
                "        'perturbation': {'enabled': False, 'strength': 0, 'max_perturbations': 99},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 99,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    policy = _load_main_search_strategy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["main_search_strategy_loaded"] is True
    assert policy["main_search_strategy_active"] is False
    assert policy["main_search_strategy_errors"] >= 10
    assert policy["main_search_stop_reason"] == "invalid_plan"
    assert "unknown_move" in str(policy["main_search_strategy_events"])


def test_runtime_audit_fails_when_policy_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "policy_path": "policies/search_policy.py",
            "policy_loaded": True,
            "policy_errors": 1,
            "policy_events": [
                {
                    "policy": "policies/search_policy.py",
                    "status": "error",
                    "detail": "bad return",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "policy_runtime_error"
    assert "policy_errors=1" in issue["detail"]
    assert "bad return" in format_runtime_audit_failure(issue)


def test_runtime_audit_fails_when_construction_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "construction_policy_path": "policies/construction_policy.py",
            "construction_surface_loaded": True,
            "construction_errors": 1,
            "construction_mode": "nearest_neighbor",
            "construction_events": [
                {
                    "policy": "policies/construction_policy.py",
                    "status": "error",
                    "detail": "bad construction mode",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "construction_runtime_error"
    assert "construction_errors=1" in issue["detail"]
    assert "bad construction mode" in format_runtime_audit_failure(issue)


def test_runtime_audit_fails_when_portfolio_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "portfolio_policy_path": "policies/neighborhood_portfolio.py",
            "portfolio_surface_loaded": True,
            "portfolio_errors": 1,
            "enabled_components": ["route_local"],
            "portfolio_events": [
                {
                    "policy": "policies/neighborhood_portfolio.py",
                    "status": "error",
                    "detail": "unknown component",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "portfolio_runtime_error"
    assert "portfolio_errors=1" in issue["detail"]
    assert "unknown component" in format_runtime_audit_failure(issue)
