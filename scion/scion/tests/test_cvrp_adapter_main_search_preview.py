from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

def test_cvrp_main_search_strategy_preview_accepts_valid_plan(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'problem_adaptation': {'strategy_family': 'route_structure_repair', 'instance_profile': {'scale': 'small'}, 'phase_objective': 'phase_best_distance', 'component_roles': {'intra_route_2opt': 'support', 'inter_route_relocate': 'support', 'route_pair_swap': 'primary', 'bounded_destroy_repair': 'support', 'route_pool_recombination': 'support'}, 'fallback_order': ['route_pair_swap', 'inter_route_relocate', 'bounded_destroy_repair', 'route_pool_recombination', 'intra_route_2opt'], 'evidence_targets': ['main_search_component_phase_delta_sum', 'main_search_objective_delta_by_phase']},\n"
            "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 2, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},\n"
            "        'construction': {'methods': ['nearest_neighbor', 'sequential'], 'keep_top_k': 2, 'bias': 0.1},\n"
            "        'baseline': {'time_fraction': 0.6, 'params': {'destroy_ratio': (0.05, 0.25)}},\n"
            "        'improvement': {'enabled_components': ['intra_route_2opt', 'inter_route_relocate', 'route_pair_swap', 'bounded_destroy_repair', 'route_pool_recombination'], 'rounds': 2, 'top_k': 24},\n"
            "        'acceptance': {'min_distance_improvement': 0.0, 'component_min_distance_improvement': {'bounded_destroy_repair': 0.0}, 'bounded_destroy_repair_accept_limit': 2, 'recovery_only_policy': 'phase_best_preferred'},\n"
            "        'restart': {'enabled': True, 'stagnation_rounds': 1, 'max_restarts': 1},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is True
    assert preview["surface"] == "main_search_strategy"
    assert preview["issues"] == []
    coverage_check = next(
        check
        for check in preview["checks"]
        if check["name"] == "main_search_problem_object_evidence_alignment"
    )
    assert coverage_check["passed"] is True
    assert coverage_check["missing_components"] == []
    assert "solver-level CVRP designs" in coverage_check["guidance"]
    assert "diagnostic only" in coverage_check["guidance"]


def test_cvrp_main_search_strategy_preview_accepts_lifecycle_roles_and_runtime_targets(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'problem_adaptation': {\n"
            "            'strategy_family': 'baseline_intensification',\n"
            "            'instance_profile': {'customer_count': instance.customer_count, 'scale': 'medium'},\n"
            "            'phase_objective': 'phase_best_distance',\n"
            "            'component_roles': {\n"
            "                'nearest_neighbor': 'primary',\n"
            "                'demand_descending': 'support',\n"
            "                'repo_local_baseline': 'primary',\n"
            "                'route_pair_swap': 'primary',\n"
            "                'bounded_destroy_repair': 'support',\n"
            "                'intra_route_2opt': 'support',\n"
            "                'strict_improvement_acceptance': 'primary',\n"
            "                'restart_stagnation': 'support',\n"
            "                'bounded_perturbation': 'support',\n"
            "                'pre_improvement_perturbation': 'probe',\n"
            "            },\n"
            "            'fallback_order': ['route_pair_swap', 'bounded_destroy_repair', 'intra_route_2opt'],\n"
            "            'evidence_targets': ['main_search_component_accepted', 'main_search_component_phase_improvement_counts', 'main_search_route_pool_sample_count', 'main_search_route_pool_size', 'main_search_route_pool_recombined_routes', 'main_search_perturbation_count', 'main_search_restart_count', 'main_search_objective_delta_by_phase'],\n"
            "        },\n"
            "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'route_structure_repair', 'local_cleanup', 'perturbation', 'restart'], 'route_pool_activation': 'medium_large_only', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 1, 'local_cleanup_after_recombination': True, 'adaptive_component_budget': True},\n"
            "        'construction': {'methods': ['nearest_neighbor', 'demand_descending'], 'keep_top_k': 2, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.78, 'params': {'destroy_ratio': (0.10, 0.30), 'segment_length': 150, 'max_destroy_customers': 8}},\n"
            "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair', 'intra_route_2opt'], 'rounds': 5, 'top_k': 20},\n"
            "        'acceptance': {'min_distance_improvement': 0.0, 'component_min_distance_improvement': {'bounded_destroy_repair': 1.0}, 'bounded_destroy_repair_accept_limit': 1, 'recovery_only_policy': 'allow'},\n"
            "        'restart': {'enabled': True, 'stagnation_rounds': 5, 'max_restarts': 2},\n"
            "        'perturbation': {'enabled': True, 'strength': 2, 'max_perturbations': 2, 'schedule': 'before_first_round'},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is True
    assert preview["issues"] == []


def test_cvrp_main_search_strategy_preview_rejects_novelty_signature_in_plan(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': False,\n"
            "        'problem_adaptation': {'strategy_family': 'balanced_lifecycle', 'instance_profile': {}, 'phase_objective': 'phase_best_distance', 'component_roles': {}, 'fallback_order': [], 'evidence_targets': ['main_search_component_phase_delta_sum']},\n"
            "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.8, 'params': {}},\n"
            "        'improvement': {'enabled_components': [], 'rounds': 0, 'top_k': 16},\n"
            "        'acceptance': {'min_distance_improvement': 0.0},\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "        'novelty_signature': {'selected_components': ['route_pair_swap']},\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is False
    assert "main_search_plan returned unknown keys ['novelty_signature']" in json.dumps(
        preview["issues"]
    )


def test_cvrp_main_search_strategy_preview_warns_when_forced_diagnostic_deep_components_missing(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'route_structure_repair'], 'route_pool_activation': 'disabled', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 0, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},\n"
            "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.8, 'params': {}},\n"
            "        'improvement': {'enabled_components': ['intra_route_2opt', 'inter_route_relocate'], 'rounds': 5, 'top_k': 24},\n"
            "        'acceptance': {'min_distance_improvement': 0.0},\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is True
    assert preview["issues"] == []
    coverage_check = next(
        check
        for check in preview["checks"]
        if check["name"] == "main_search_problem_object_evidence_alignment"
    )
    assert coverage_check["passed"] is True
    assert coverage_check["severity"] == "diagnostic_warning"
    assert coverage_check["missing_components"] == [
        "bounded_destroy_repair",
        "route_pair_swap",
        "route_pool_recombination",
    ]


def test_cvrp_main_search_strategy_preview_rejects_missing_algorithm_body(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.8, 'params': {}},\n"
            "        'improvement': {'enabled_components': ['route_pool_recombination'], 'rounds': 1, 'top_k': 24},\n"
            "        'acceptance': {'min_distance_improvement': 0.0},\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is False
    assert "missing required keys ['algorithm_body']" in json.dumps(preview["issues"])
    assert "missing required algorithm_body section" in json.dumps(preview["issues"])


def test_cvrp_main_search_strategy_preview_rejects_bad_algorithm_body(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'algorithm_body': {'phase_sequence': [], 'baseline_budget_policy': 'legacy_floor', 'route_pool_activation': 'tiny_only', 'route_pool_min_customers': -1, 'route_pool_max_rounds': 99, 'local_cleanup_after_recombination': 'yes'},\n"
            "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.8, 'params': {}},\n"
            "        'improvement': {'enabled_components': ['route_pool_recombination'], 'rounds': 1, 'top_k': 24},\n"
            "        'acceptance': {'min_distance_improvement': 0.0},\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is False
    assert "algorithm_body.phase_sequence" in json.dumps(preview["issues"])
    assert "baseline_budget_policy" in json.dumps(preview["issues"])
    assert "tiny_only" in json.dumps(preview["issues"])
    assert "algorithm_body.route_pool_min_customers" in json.dumps(preview["issues"])
    assert "algorithm_body.route_pool_max_rounds" in json.dumps(preview["issues"])
    assert "local_cleanup_after_recombination" in json.dumps(preview["issues"])


def test_cvrp_main_search_strategy_preview_rejects_bad_plan(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
            "        'baseline': {'time_fraction': 0.8, 'params': {'unknown': 1}},\n"
            "        'improvement': {'enabled_components': ['made_up_move'], 'rounds': 0, 'top_k': 0},\n"
            "        'acceptance': {'min_distance_improvement': 0.0},\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0, 'extra': 1},\n"
            "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'operator_round_limit': 0,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is False
    assert "made_up_move" in json.dumps(preview["issues"])
    assert "baseline.params" in json.dumps(preview["issues"])
    assert "restart returned unknown keys" in json.dumps(preview["issues"])


def test_cvrp_main_search_strategy_preview_rejects_instance_customers_alias(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/main_search_strategy.py",
        action="modify",
        code_content=(
            "def main_search_plan(instance, time_limit_sec):\n"
            "    return {'enabled': bool(instance.customers)}\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="main_search_strategy"),
    )

    assert preview["passed"] is False
    assert "main_search_plan raised during synthetic preview" in json.dumps(preview)
    assert "customers" in json.dumps(preview["issues"])
