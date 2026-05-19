from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

def test_cvrp_policy_preview_rejects_instance_customers_alias(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.7 if instance.customers else 0.8\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 1\n\n"
            "def enable_post_baseline_operators(instance, time_limit_sec):\n"
            "    return True\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="search_policy"),
    )

    assert preview["passed"] is False
    assert "baseline_time_fraction raised during synthetic preview" in json.dumps(preview)
    assert "customers" in json.dumps(preview["issues"])
    assert preview["synthetic_instance"]["customer_count"] == 3
    assert "customers" not in preview["synthetic_instance"]


def test_cvrp_algorithm_blueprint_preview_rejects_bad_plan(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/algorithm_blueprint.py",
        action="modify",
        code_content=(
            "def algorithm_plan(instance, time_limit_sec):\n"
            "    return {\n"
            "        'enabled': True,\n"
            "        'construction_methods': ['nearest_neighbor'],\n"
            "        'construction_keep_top_k': 1,\n"
            "        'construction_bias': 0.0,\n"
            "        'baseline_time_fraction': 0.8,\n"
            "        'operator_round_limit': 20,\n"
            "        'post_baseline_operators_enabled': False,\n"
            "        'local_search': {\n"
            "            'enabled_components': ['made_up_move'],\n"
            "            'rounds': 9,\n"
            "            'top_k': 16,\n"
            "        },\n"
            "        'restart': {'enabled': False, 'stagnation_rounds': 0},\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="algorithm_blueprint"),
    )

    assert preview["passed"] is False
    assert "made_up_move" in json.dumps(preview["issues"])
    assert "local_search.rounds" in json.dumps(preview["issues"])


def test_cvrp_baseline_policy_preview_accepts_valid_params(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_policy.py",
        action="modify",
        code_content=(
            "def baseline_params(instance, time_limit_sec):\n"
            "    return {\n"
            "        'destroy_ratio': (0.05, 0.25),\n"
            "        'segment_length': 50,\n"
            "        'reaction_factor': 0.2,\n"
            "        'vns_max_no_improve': 250,\n"
            "        'use_vns': False,\n"
            "        'cw_threshold': 100,\n"
            "        'vns_threshold': 100,\n"
            "        'alns_threshold': 200,\n"
            "        'max_destroy_customers': min(20, instance.customer_count + 5),\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="baseline_policy"),
    )

    assert preview["passed"] is True
    assert preview["surface"] == "baseline_policy"
    assert preview["issues"] == []


def test_cvrp_baseline_policy_preview_rejects_invalid_params(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_policy.py",
        action="modify",
        code_content=(
            "def baseline_params(instance, time_limit_sec):\n"
            "    return {\n"
            "        'destroy_ratio': (0.7, 0.2),\n"
            "        'segment_length': 0,\n"
            "        'use_vns': 'yes',\n"
            "        'unknown': 1,\n"
            "    }\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="baseline_policy"),
    )

    assert preview["passed"] is False
    issues = json.dumps(preview["issues"])
    assert "destroy_ratio lower bound" in issues
    assert "segment_length" in issues
    assert "use_vns" in issues
    assert "unknown" in issues


def test_cvrp_algorithm_blueprint_preview_rejects_instance_customers_alias(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/algorithm_blueprint.py",
        action="modify",
        code_content=(
            "def algorithm_plan(instance, time_limit_sec):\n"
            "    return {'enabled': bool(instance.customers)}\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="algorithm_blueprint"),
    )

    assert preview["passed"] is False
    assert "algorithm_plan raised during synthetic preview" in json.dumps(preview)
    assert "customers" in json.dumps(preview["issues"])
