"""CVRP adapter tests for v0.4 route-native verification."""
from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import PatchProposal, RunResult, SolverOutput
from scion.problem.contracts import ProblemAdapter
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solver import solve
from scion.verification.gate import VerificationGate


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
TINY_5 = CVRP_DIR / "data" / "tiny_5.json"


@pytest.fixture
def cvrp_spec() -> ProblemSpecV1:
    with open(CVRP_DIR / "problem-v1.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["root_dir"] = str(CVRP_DIR)
    data["canary_case_path"] = str(TINY_5)
    return ProblemSpecV1(**data)


@pytest.fixture
def cvrp_adapter(cvrp_spec: ProblemSpecV1) -> ProblemAdapter:
    return load_problem_adapter(cvrp_spec)


def _raw(routes: list[list[int]], *, distance: float = 8.0, fleet: int = 0) -> dict[str, Any]:
    return {
        "routes": routes,
        "objective": {
            "fleet_violation": fleet,
            "total_distance": distance,
            "routes": len(routes),
        },
        "feasible": True,
    }


def test_cvrp_problem_spec_loads(cvrp_spec: ProblemSpecV1, cvrp_adapter: ProblemAdapter) -> None:
    assert cvrp_spec.id == "cvrp"
    assert [o.name for o in cvrp_spec.objectives] == ["fleet_violation", "total_distance"]
    assert "fleet_violation" in cvrp_adapter.render_problem_summary()
    assert "implicit depot" in cvrp_adapter.render_operator_interface()


def test_cvrp_adapter_renders_problem_object_for_solver_level_research(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_problem_object()

    assert "Instance model:" in rendered
    assert "Solution model:" in rendered
    assert "Objective policy:" in rendered
    assert "Solver lifecycle:" in rendered
    assert "Move/design grammar:" in rendered
    assert "Runtime evidence for problem-level hypotheses:" in rendered
    assert "`instance.customer_ids`" in rendered
    assert "`instance.route_distance(route)`" in rendered
    assert "`CvrpSolution(routes=...)`" in rendered
    assert "fleet_violation first, then total_distance" in rendered
    assert "Component policies are implementation hooks" in rendered
    assert "Do not claim success from active flags" in rendered


def test_cvrp_instance_exposes_safe_policy_api_without_customers_alias() -> None:
    inst = CvrpInstance(
        name="api_smoke",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=3),
            CvrpNode(id=2, x=0.0, y=1.0, demand=4),
        ),
    )

    assert inst.customer_ids == (1, 2)
    assert inst.customer_count == len(inst.customer_ids) == 2
    assert inst.demands == {0: 0, 1: 3, 2: 4}
    assert inst.demands[1] == inst.demand(1)
    assert not hasattr(inst, "customers")
    with pytest.raises(AttributeError):
        getattr(inst, "customers")


@pytest.mark.parametrize(
    "surface_name",
    [
        "construction_policy",
        "search_policy",
        "baseline_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ],
)
def test_cvrp_policy_surface_interfaces_render_safe_instance_api(
    cvrp_adapter: ProblemAdapter,
    surface_name: str,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface(surface_name)

    assert "`instance.customer_ids`" in rendered
    assert "`instance.customer_count`" in rendered
    assert "`instance.demands[customer_id]`" in rendered
    assert "`instance.capacity`" in rendered
    assert "`instance.distance(i, j)`" in rendered
    assert "Never use `instance.customers`" in rendered


def test_cvrp_destroy_repair_policy_interface_lists_disjoint_selector_enums(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface("destroy_repair_policy")

    assert (
        "destroy_selectors: non-empty sequence containing only 'worst_removal', "
        "'route_diverse_worst'"
    ) in rendered
    assert (
        "repair_selectors: non-empty sequence containing only 'regret_2', "
        "'cheapest'"
    ) in rendered
    assert (
        "subset_strategy: one of 'prefix_shifted_route_diverse', 'single_worst', "
        "'route_diverse'"
    ) in rendered
    assert (
        "Do not put subset strategies such as 'single_worst' or 'route_diverse' "
        "in destroy_selectors"
    ) in rendered


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
            "        'problem_adaptation': {'strategy_family': 'route_structure_repair', 'instance_profile': {'scale': 'small'}, 'phase_objective': 'phase_best_distance', 'component_roles': {'intra_route_2opt': 'support', 'inter_route_relocate': 'support', 'route_pair_swap': 'primary', 'bounded_destroy_repair': 'support'}, 'fallback_order': ['route_pair_swap', 'inter_route_relocate', 'bounded_destroy_repair', 'intra_route_2opt'], 'evidence_targets': ['main_search_component_phase_delta_sum', 'main_search_objective_delta_by_phase']},\n"
            "        'construction': {'methods': ['nearest_neighbor', 'sequential'], 'keep_top_k': 2, 'bias': 0.1},\n"
            "        'baseline': {'time_fraction': 0.6, 'params': {'destroy_ratio': (0.05, 0.25)}},\n"
            "        'improvement': {'enabled_components': ['intra_route_2opt', 'inter_route_relocate', 'route_pair_swap', 'bounded_destroy_repair'], 'rounds': 2, 'top_k': 24},\n"
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
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is True
    assert preview["surface"] == "solver_design"
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
        surface=SimpleNamespace(name="solver_design"),
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
    ]


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
        surface=SimpleNamespace(name="solver_design"),
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
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    assert "main_search_plan raised during synthetic preview" in json.dumps(preview)
    assert "customers" in json.dumps(preview["issues"])


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


def test_valid_route_solution_passes_all_adapter_checks(
    cvrp_adapter: ProblemAdapter,
) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    artifact = cvrp_adapter.deserialize_solver_output(_raw([[1, 2], [3, 4]]), inst)

    assert artifact.feasible is True
    assert cvrp_adapter.check_solution_consistency(artifact, inst).passed is True
    assert cvrp_adapter.check_feasibility(artifact, inst).passed is True
    assert cvrp_adapter.recompute_objective(artifact, inst) == {
        "fleet_violation": 0,
        "total_distance": 8.0,
        "routes": 2,
    }


def test_explicit_depot_route_boundaries_are_normalized(cvrp_adapter: ProblemAdapter) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    artifact = cvrp_adapter.deserialize_solver_output(_raw([[0, 1, 2, 0], [0, 3, 4, 0]]), inst)

    assert artifact.normalized_solution == CvrpSolution(routes=((1, 2), (3, 4)))
    assert cvrp_adapter.check_solution_consistency(artifact, inst).passed is True


@pytest.mark.parametrize(
    ("routes", "expected"),
    [
        ([[1, 2], [2, 3, 4]], "appears in multiple routes"),
        ([[1, 2], [3]], "missing customers"),
        ([[1, 2], [3, 99]], "unknown customer 99"),
        ([[1, 0, 2], [3, 4]], "contains depot inside customer route"),
        ([[1, 2], [3, 4]], "objective field total_distance missing"),
    ],
)
def test_consistency_rejects_bad_route_shapes(
    cvrp_adapter: ProblemAdapter,
    routes: list[list[int]],
    expected: str,
) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    raw = _raw(routes)
    if expected.startswith("objective field"):
        raw["objective"].pop("total_distance")
    artifact = cvrp_adapter.deserialize_solver_output(raw, inst)

    report = cvrp_adapter.check_solution_consistency(artifact, inst)

    assert report.passed is False
    assert expected in "; ".join(report.reasons)


def test_feasibility_rejects_over_capacity_route(cvrp_adapter: ProblemAdapter) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    artifact = cvrp_adapter.deserialize_solver_output(_raw([[1, 2, 3], [4]], distance=10.0), inst)

    consistency = cvrp_adapter.check_solution_consistency(artifact, inst)
    feasibility = cvrp_adapter.check_feasibility(artifact, inst)

    assert consistency.passed is True
    assert feasibility.passed is False
    assert "exceeds capacity" in "; ".join(feasibility.reasons)


def test_recompute_objective_catches_reported_cost_mismatch(cvrp_adapter: ProblemAdapter) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    artifact = cvrp_adapter.deserialize_solver_output(_raw([[1, 2], [3, 4]], distance=999.0), inst)

    recomputed = cvrp_adapter.recompute_objective(artifact, inst)

    assert artifact.objective["total_distance"] == 999.0
    assert recomputed["total_distance"] == 8.0


def test_fleet_violation_uses_allowed_routes(cvrp_adapter: ProblemAdapter) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    artifact = cvrp_adapter.deserialize_solver_output(
        _raw([[1], [2], [3], [4]], distance=8.0, fleet=2),
        inst,
    )

    recomputed = cvrp_adapter.recompute_objective(artifact, inst)

    assert recomputed["fleet_violation"] == 2
    assert recomputed["routes"] == 4


def test_tiny_solver_output_is_adapter_valid(cvrp_adapter: ProblemAdapter) -> None:
    inst: CvrpInstance = cvrp_adapter.load_instance(str(TINY_5))
    sol = solve(inst, random.Random(42))
    raw = {"routes": [list(route) for route in sol.routes], "feasible": True}
    artifact = cvrp_adapter.deserialize_solver_output(raw, inst)
    raw["objective"] = dict(cvrp_adapter.recompute_objective(artifact, inst))
    artifact = cvrp_adapter.deserialize_solver_output(raw, inst)

    assert cvrp_adapter.check_solution_consistency(artifact, inst).passed is True
    assert cvrp_adapter.check_feasibility(artifact, inst).passed is True


def test_strict_adapter_backed_verification_gate_passes_cvrp_tiny(
    cvrp_adapter: ProblemAdapter,
) -> None:
    canary = str(TINY_5)
    raw = _raw([[1, 2], [3, 4]])

    class StaticRunner:
        def run_solver(self, workdir, instance_path, seed, time_limit_sec, registry_path):
            fd, output_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            return RunResult(
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
                output=SolverOutput(
                    vehicles={},
                    assignment={},
                    objective=raw["objective"],
                    feasible=True,
                ),
                output_path=output_path,
                error_category=None,
            )

    spec = ProblemSpec(
        name="cvrp",
        root_dir=str(CVRP_DIR),
        canary_case_path=canary,
        operator_categories=["route_local", "route_pair", "ruin_recreate"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py", "models.py", "adapter.py", "operators/base.py"],
            import_whitelist=["__future__", "math", "random", "typing"],
        ),
    )
    gate = VerificationGate(
        problem_spec=spec,
        runner=StaticRunner(),
        adapter=cvrp_adapter,
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
        operator_execute_signature="execute(self, solution, instance, rng) -> CvrpSolution",
    )
    patch = PatchProposal(
        file_path="operators/noop.py",
        action="create",
        code_content=(
            "class NoOp:\n"
            "    def execute(self, solution, instance, rng):\n"
            "        return solution\n"
        ),
    )

    result = gate.run(str(CVRP_DIR), str(CVRP_DIR), patch)

    assert result.passed is True
    assert [check.name for check in result.checks][-5:] == [
        "V5_solution_consistency",
        "V6_feasibility",
        "V7_objective",
        "V8_nondeterminism",
        "V9_perf_guard",
    ]
