from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problem.providers import (
    resolve_solver_design_prompt_provider,
    resolve_solver_design_smoke_provider,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    validate_expected_telemetry_contract,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_cvrp_adapter_registers_solver_design_providers() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    legacy = legacy_problem_spec_from_v1(spec)

    prompt_provider = resolve_solver_design_prompt_provider(
        problem_spec=legacy,
        adapter=adapter,
    )
    smoke_provider = resolve_solver_design_smoke_provider(
        problem_spec=legacy,
        adapter=adapter,
    )

    assert prompt_provider is not None
    assert smoke_provider is not None
    assert smoke_provider.is_runtime_patch_path("policies/baseline_algorithm.py")
    assert smoke_provider.is_runtime_patch_path("policies/baseline_modules/config.py")
    assert not smoke_provider.is_runtime_patch_path("operators/local_search.py")


def test_cvrp_prompt_provider_owns_solver_design_specific_terms() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_prompt_provider()

    rendered = "\n".join(
        [
            *provider.solver_design_code_rules({}),
            *provider.solver_design_scope_guidance(
                {"agentic_code_scope_control": {"failure_detail": "timeout"}},
                mode="compact_timeout_retry",
                broad_terms=["alns", "destroy"],
            ),
            *provider.solver_design_user_constraints({}),
        ]
    )

    assert "_ALNSVNSSolver" in rendered
    assert "_Solution" in rendered
    assert "solver_algorithm_search_iterations=0" in rendered
    assert "policies/baseline_modules/" in rendered


def test_cvrp_prompt_provider_demotes_legacy_surfaces() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_prompt_provider()

    rendered = "\n".join(
        [
            *provider.solver_design_hypothesis_guidance({}),
            *provider.solver_design_code_rules({}),
            *provider.solver_design_scope_guidance(
                {},
                mode="",
                broad_terms=(),
            ),
            *provider.solver_design_user_constraints({}),
        ]
    )

    assert "policies/baseline_algorithm.py" in rendered
    assert "policies/baseline_modules/*.py" in rendered
    assert "policies/solver_algorithm.py" not in rendered
    assert "deleted" in rendered
    assert "not optimization directions" in rendered
    assert "initial construction is route-limit guarded" in rendered
    assert "positive fleet_violation or route-limit excess" in rendered
    assert "explicitly repairs that compatibility hook" not in rendered


def test_cvrp_problem_spec_declares_solver_algorithm_telemetry_roles() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")

    activation_errors = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="solver_design",
        expected_telemetry={
            "activation": ["solver_algorithm_fleet_violation"],
            "effect": ["solver_algorithm_fleet_violation"],
        },
    )
    activation_ok = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="solver_design",
        expected_telemetry={
            "activation": ["solver_algorithm_phase_runtime_ms.route_merge_seed"],
        },
        declared_mechanisms=["route_merge_seed"],
    )
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"solver_algorithm_fleet_violation": 0}],
        problem_spec=spec,
        selected_surface="solver_design",
        expected_telemetry={"effect": ["solver_algorithm_fleet_violation"]},
        protected_objectives=("fleet_violation",),
    )

    assert activation_errors[0] == (
        "expected_telemetry.activation references declared outcome field "
        "solver_algorithm_fleet_violation (role(s): protected_outcome); "
        "activation must use mechanism-specific activity evidence declared by "
        "the selected research surface."
    )
    assert "Legal expected_telemetry template" in activation_errors[1]
    assert "mechanism_id='<mechanism_id>'" in activation_errors[1]
    assert "solver_algorithm_phase_runtime_ms.<mechanism_id>" in activation_errors[1]
    assert activation_ok == ()
    assert summary["passed"] is True
    assert summary["fields"]["solver_algorithm_fleet_violation"][
        "candidate_positive"
    ] == 0


def test_cvrp_smoke_provider_owns_low_effort_interpretation() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def seed_pool(instance):\n    return []\n",
        additional_changes=(
            SimpleNamespace(
                file_path="policies/baseline_modules/scheduler.py",
                action="modify",
                code_content="class _ALNSVNSSolver:\n    pass\n",
            ),
        ),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve ALNS/VNS search by changing construction seeds.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
    )

    issue = provider.low_effort_issue(
        patch=patch,
        hypothesis=hypothesis,
        runs=[
            {
                "case": "cvrplib/A/A-n32-k5.vrp",
                "seed": 11,
                "passed": True,
                "runtime": {
                    "solver_algorithm_search_iterations": 1,
                    "solver_algorithm_move_attempts": 6,
                    "solver_algorithm_stop_reason": "no_improvement",
                    "solver_algorithm_elapsed_ms": 90,
                },
                "run": {"elapsed_ms": 100},
            },
            {
                "case": "cvrplib/B/B-n31-k5.vrp",
                "seed": 11,
                "passed": True,
                "runtime": {
                    "solver_algorithm_search_iterations": 2,
                    "solver_algorithm_move_attempts": 12,
                    "solver_algorithm_stop_reason": "no_improvement",
                    "solver_algorithm_elapsed_ms": 100,
                },
                "run": {"elapsed_ms": 110},
            },
        ],
        micro_results=[
            {
                "case": "cvrplib/A/A-n32-k5.vrp",
                "seed": 11,
                "comparison": "tie",
                "champion_elapsed_ms": 3000,
            },
            {
                "case": "cvrplib/B/B-n31-k5.vrp",
                "seed": 11,
                "comparison": "loss",
                "champion_elapsed_ms": 3000,
            },
        ],
    )

    assert issue is not None
    assert "low active search effort" in issue
    assert "policies/baseline_modules/scheduler.py" in issue


def test_cvrp_smoke_provider_rejects_double_bridge_semantic_drift() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a cross-route double-bridge perturbation across up to 4 routes."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        mechanism_changes=(SimpleNamespace(id="double_bridge_perturbation"),),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content=(
            "def _double_bridge_perturbation(solution, rng, context=None):\n"
            "    for route in solution.routes:\n"
            "        customers = route.customers\n"
            "        if len(customers) >= 8:\n"
            "            route.customers = customers[:2] + customers[4:6] + customers[2:4] + customers[6:]\n"
            "            context.record_move('double_bridge_perturbation', attempted=1, accepted=1, delta=1, best_improved=1)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is not None
    assert "semantic drift" in issue
    assert "single route" in issue


def test_cvrp_smoke_provider_rejects_destroy_helper_effect_telemetry() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    hypothesis = HypothesisProposal(
        hypothesis_text="Add spatial_cluster_removal destroy.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        mechanism_changes=(SimpleNamespace(id="spatial_cluster_removal"),),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/destroy_repair.py",
        action="modify",
        code_content=(
            "def _spatial_cluster_removal(solution, q, rng, context=None):\n"
            "    if context:\n"
            "        context.record_move('spatial_cluster_removal', attempted=1, accepted=1, delta=5, best_improved=1)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is not None
    assert "non-causal destroy telemetry" in issue
