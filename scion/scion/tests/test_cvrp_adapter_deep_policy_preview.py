from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

@pytest.mark.parametrize(
    ("surface_name", "file_path", "code_content"),
    [
        (
            "alns_vns_policy",
            "policies/alns_vns_policy.py",
            (
                "def alns_vns_plan(instance, time_limit_sec):\n"
                "    return {\n"
                "        'enabled': True,\n"
                "        'components': ['alns', 'vns'],\n"
                "        'component_weights': {'alns': 1.0, 'vns': 0.5},\n"
                "        'params': {'destroy_ratio': (0.05, 0.2), 'segment_length': 50},\n"
                "    }\n"
            ),
        ),
        (
            "destroy_repair_policy",
            "policies/destroy_repair_policy.py",
            (
                "def destroy_repair_plan(instance, time_limit_sec):\n"
                "    return {\n"
                "        'enabled': True,\n"
                "        'destroy_selectors': ['worst_removal'],\n"
                "        'repair_selectors': ['regret_2'],\n"
                "        'subset_strategy': 'route_diverse',\n"
                "        'max_destroy_customers': 3,\n"
                "        'repair_budget_per_customer': 6,\n"
                "        'fallback_to_smaller_subsets': True,\n"
                "        'phase_best_preference': True,\n"
                "    }\n"
            ),
        ),
        (
            "route_pair_candidate_policy",
            "policies/route_pair_candidate_policy.py",
            (
                "def route_pair_plan(instance, time_limit_sec):\n"
                "    return {\n"
                "        'enabled': True,\n"
                "        'scoring_terms': ['route_distance', 'distance_saving'],\n"
                "        'move_families': ['customer_swap'],\n"
                "        'candidate_limits': {'pair_cap': 4, 'position_cap': 3},\n"
                "    }\n"
            ),
        ),
        (
            "acceptance_restart_policy",
            "policies/acceptance_restart_policy.py",
            (
                "def acceptance_restart_plan(instance, time_limit_sec):\n"
                "    return {\n"
                "        'enabled': True,\n"
                "        'min_distance_improvement': 0.0,\n"
                "        'recovery_only_policy': 'reject_recovery_only',\n"
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
                "        'perturbation': {'enabled': True, 'schedule': 'before_first_round', 'strength': 2, 'max_perturbations': 1},\n"
                "    }\n"
            ),
        ),
    ],
)

def test_cvrp_deep_mechanism_policy_previews_accept_valid_plans(
    cvrp_adapter: ProblemAdapter,
    surface_name: str,
    file_path: str,
    code_content: str,
) -> None:
    patch = PatchProposal(
        file_path=file_path,
        action="modify",
        code_content=code_content,
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name=surface_name),
    )

    assert preview["passed"] is True
    assert preview["surface"] == surface_name
    assert preview["issues"] == []
    assert preview.get("skipped") is not True


def test_cvrp_deep_mechanism_policy_preview_rejects_bad_values(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/route_pair_candidate_policy.py",
        action="modify",
        code_content=(
            "def route_pair_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'scoring_terms': ['made_up_score'],\n"
            "        'move_families': ['customer_swap'],\n"
            "        'candidate_limits': {'pair_cap': 999, 'unknown': 1},\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="route_pair_candidate_policy"),
    )

    assert preview["passed"] is False
    issues = json.dumps(preview["issues"])
    assert "made_up_score" in issues
    assert "pair_cap" in issues
    assert "unknown" in issues


def test_cvrp_destroy_repair_policy_preview_rejects_subset_values_as_destroy_selectors(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/destroy_repair_policy.py",
        action="modify",
        code_content=(
            "def destroy_repair_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'destroy_selectors': ['route_diverse', 'single_worst'],\n"
            "        'repair_selectors': ['cheapest'],\n"
            "        'subset_strategy': 'route_diverse',\n"
            "        'max_destroy_customers': 4,\n"
            "        'repair_budget_per_customer': 16,\n"
            "        'fallback_to_smaller_subsets': True,\n"
            "        'phase_best_preference': True,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="destroy_repair_policy"),
    )

    assert preview["passed"] is False
    issues = json.dumps(preview["issues"])
    assert "destroy_selectors returned unknown values" in issues
    assert "route_diverse" in issues
    assert "single_worst" in issues
