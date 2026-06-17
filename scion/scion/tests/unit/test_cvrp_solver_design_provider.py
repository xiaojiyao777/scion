from __future__ import annotations

import json
from types import SimpleNamespace

from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problem.providers import (
    active_subject_code_constraints_payload,
    resolve_solver_design_prompt_provider,
    resolve_solver_design_smoke_provider,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.solver_design_smoke.benchmark import (
    _compare_solver_design_raw_outputs,
)
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    validate_expected_telemetry_contract,
)
from scion.proposal.tools.previews.schema import _hypothesis_schema_preview
from scion.proposal.engine.code_prompts import _split_code_context
from scion.tests.unit.test_agentic_proposal_tools_helpers import _cvrp_context
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


def test_cvrp_smoke_provider_owns_solver_design_objective_comparison() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()

    comparison = _compare_solver_design_raw_outputs(
        {
            "objective": {
                "fleet_violation": 0,
                "total_distance": 150.0,
            }
        },
        {
            "objective": {
                "fleet_violation": 1,
                "total_distance": 100.0,
            }
        },
        provider=provider,
    )

    assert comparison == {
        "comparison": "win",
        "delta": 1.0,
        "decisive_metric": "fleet_violation",
        "candidate_objective": {
            "fleet_violation": 0,
            "total_distance": 150.0,
        },
        "champion_objective": {
            "fleet_violation": 1,
            "total_distance": 100.0,
        },
    }


def test_cvrp_smoke_provider_compares_distance_after_fleet_tie() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()

    comparison = provider.solver_design_smoke_comparison(
        candidate_raw={
            "objective": {
                "fleet_violation": 0,
                "total_distance": 103.5,
            }
        },
        champion_raw={
            "objective": {
                "fleet_violation": 0,
                "total_distance": 100.0,
            }
        },
    )

    assert comparison["comparison"] == "loss"
    assert comparison["delta"] == -3.5
    assert comparison["decisive_metric"] == "total_distance"


def test_generic_smoke_comparison_without_problem_provider_is_incomparable() -> None:
    comparison = _compare_solver_design_raw_outputs(
        {"objective": {"fleet_violation": 0, "total_distance": 10.0}},
        {"objective": {"fleet_violation": 1, "total_distance": 20.0}},
    )

    assert comparison == {"comparison": "incomparable"}


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
    assert "context.record_iteration" in rendered
    assert "context.record_context('<mechanism>" not in rendered
    assert "no `context.record_context` API" in rendered


def test_cvrp_active_subject_code_constraints_are_provider_owned() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    payload = active_subject_code_constraints_payload(
        problem_spec=legacy_problem_spec_from_v1(spec),
        adapter=adapter,
        surface="solver_design",
    )
    rendered_payload = json.dumps(payload, sort_keys=True)

    assert payload["surface"] == "solver_design"
    assert "ObjectiveValue" in rendered_payload
    assert "context.objective_key" in rendered_payload
    assert "_Solution" in rendered_payload
    assert "__slots__" in rendered_payload
    system_blocks, user_prompt = _split_code_context(
        {
            "problem_summary": "CVRP",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "target_file": "policies/baseline_modules/local_search.py",
            "target_file_code": "VALUE = 1\n",
            "active_subject_code_constraints": payload,
        }
    )
    rendered_prompt = (
        "\n".join(str(block["text"]) for block in system_blocks) + user_prompt
    )
    assert "Active Subject Code Constraints" in rendered_prompt
    assert "ObjectiveValue" in rendered_prompt


def test_code_prompt_renders_provider_active_subject_code_constraints() -> None:
    constraints = {
        "surface": "opaque_surface",
        "subject_id": "opaque.subject",
        "constraints": [
            {
                "id": "opaque_value_contract",
                "constraint": (
                    "WidgetValue cannot be subtracted; use provider.compare."
                ),
            }
        ],
    }

    system_blocks, user_prompt = _split_code_context(
        {
            "problem_summary": "Opaque problem",
            "research_surface_name": "opaque_surface",
            "research_surface_kind": "solver_design",
            "target_file": "policies/example.py",
            "target_file_code": "VALUE = 1\n",
            "active_subject_code_constraints": constraints,
        }
    )
    rendered = "\n".join(str(block["text"]) for block in system_blocks) + user_prompt

    assert "Active Subject Code Constraints" in rendered
    assert "WidgetValue cannot be subtracted" in rendered
    assert "ObjectiveValue" not in rendered


def test_cvrp_hypothesis_guidance_defaults_policy_telemetry_to_indirect_evidence() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_prompt_provider()

    rendered = "\n".join(provider.solver_design_hypothesis_guidance({}))

    assert "by default: activation includes" in rendered
    assert "Declare effect fields" in rendered
    assert "only when `m` directly records" in rendered
    assert "do not claim ordinary ALNS best-improvement bookkeeping" in rendered


def test_cvrp_hypothesis_guidance_exposes_adaptive_vns_opportunity() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_prompt_provider()

    rendered = "\n".join(provider.solver_design_hypothesis_guidance({}))

    assert "adaptive embedded-VNS share-70 cadence-2" in rendered
    assert "proposal-only" in rendered
    assert "excluded from DecisionFeatures/promotion gates" in rendered
    assert "current exception is the adaptive embedded-VNS share-70 cadence-2 opportunity" in rendered
    assert "raw adaptive embedded-VNS cadence-2 lowered embedded-VNS runtime pressure" in rendered
    assert "64-row focused WSL matrix" in rendered
    assert "mean paired delta -0.12" in rendered
    assert "not as a default solver change" in rendered
    assert "cumulative embedded-VNS runtime-share, objective, remaining-budget" in rendered
    assert "record direct effect telemetry with `context.record_move`" in rendered
    assert "activation/runtime counters alone leave effect attribution missing" in rendered
    assert "Do not hardcode case ids, BKS values, seeds, or split membership" in rendered
    assert "do not remove VNS broadly" in rendered


def test_cvrp_schema_preview_warns_reheat_broad_loop_effect_before_code(
    tmp_path,
) -> None:
    context = _cvrp_context(tmp_path)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a stagnation-triggered simulated annealing reheat policy in "
            "the scheduler."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        mechanism_changes=(
            SimpleNamespace(id="sa_reheat_on_stagnation", change_type="add"),
        ),
        novelty_signature={
            "algorithm_family": "ALNS+VNS",
            "construction_strategy": "unchanged",
            "improvement_strategy": "stagnation-triggered acceptance reheat",
            "acceptance_strategy": "simulated annealing reheating",
            "runtime_budget_strategy": "bounded reheat checks inside ALNS",
        },
        expected_telemetry={
            "activation": [
                "solver_algorithm_context_records.sa_reheat_on_stagnation_iterations",
                "solver_algorithm_phase_runtime_ms.sa_reheat_on_stagnation",
            ],
            "effect": [
                "solver_algorithm_phase_best_delta.sa_reheat_on_stagnation",
                "solver_algorithm_phase_improvement_counts.sa_reheat_on_stagnation",
            ],
        },
    )

    preview = _hypothesis_schema_preview(context, hypothesis)

    problem_preview = preview["problem_expected_telemetry_preview"]
    assert preview["passed"] is True
    assert problem_preview["status"] == "advisory"
    assert problem_preview["advisory_code"] == "C11_expected_telemetry_advisory"
    assert problem_preview["mechanism_id"] == "sa_reheat_on_stagnation"
    assert "solver_algorithm_phase_best_delta.sa_reheat_on_stagnation" in (
        problem_preview["offending_fields"]
    )
    assert "decision/context" in problem_preview["allowed_repair_shape"]


def test_cvrp_schema_preview_blocks_no_effect_effect_telemetry_contradiction(
    tmp_path,
) -> None:
    context = _cvrp_context(tmp_path)
    mechanism_id = "incumbent_preserve_gate"
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add an early return gate that keeps the incumbent unchanged when "
            "the candidate path has no objective-changing move."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        expected_effect=(
            "Preserve incumbent solution and avoid objective-changing work when "
            "the gate fires."
        ),
        mechanism_changes=(SimpleNamespace(id=mechanism_id, change_type="add"),),
        expected_telemetry={
            "activation": [
                f"solver_algorithm_context_records.{mechanism_id}_iterations"
            ],
            "effect": [
                f"solver_algorithm_phase_best_delta.{mechanism_id}",
                f"solver_algorithm_phase_improvement_counts.{mechanism_id}",
            ],
        },
    )

    preview = _hypothesis_schema_preview(context, hypothesis)
    problem_preview = preview["problem_expected_telemetry_preview"]

    assert preview["passed"] is False
    assert problem_preview["failure_code"] == "C11_expected_telemetry"
    assert "Telemetry contract contradiction" in problem_preview["reason"]
    assert "Activation/budget telemetry" in (
        problem_preview["telemetry_category_guidance"]
    )
    assert "unchanged incumbent" in problem_preview["forbidden_repair_shape"]


def test_cvrp_schema_preview_allows_direct_effect_for_operator_mechanism(
    tmp_path,
) -> None:
    context = _cvrp_context(tmp_path)
    hypothesis = HypothesisProposal(
        hypothesis_text="Add a nearest-neighbor limited relocate operator.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        mechanism_changes=(
            SimpleNamespace(id="nn_relocate_operator", change_type="add"),
        ),
        expected_telemetry={
            "activation": [
                "solver_algorithm_context_records.nn_relocate_operator_iterations",
                "solver_algorithm_phase_runtime_ms.nn_relocate_operator",
            ],
            "effect": [
                "solver_algorithm_phase_best_delta.nn_relocate_operator",
                "solver_algorithm_phase_improvement_counts.nn_relocate_operator",
            ],
        },
    )

    preview = _hypothesis_schema_preview(context, hypothesis)

    assert preview["problem_expected_telemetry_preview"] is None


def test_cvrp_schema_preview_does_not_classify_local_search_text_as_policy(
    tmp_path,
) -> None:
    context = _cvrp_context(tmp_path)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "After stagnation, add a cross-route string exchange local-search "
            "operator. This is a VNS move operator, not an acceptance policy."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        mechanism_changes=(
            SimpleNamespace(id="string_exchange_intensification", change_type="add"),
        ),
        expected_telemetry={
            "activation": [
                "solver_algorithm_context_records.string_exchange_intensification_iterations",
                "solver_algorithm_phase_runtime_ms.string_exchange_intensification",
            ],
            "effect": [
                "solver_algorithm_phase_best_delta.string_exchange_intensification",
                "solver_algorithm_phase_improvement_counts.string_exchange_intensification",
            ],
        },
    )

    preview = _hypothesis_schema_preview(context, hypothesis)

    assert preview["problem_expected_telemetry_preview"] is None


def test_cvrp_schema_preview_does_not_treat_preserve_acceptance_as_policy(
    tmp_path,
) -> None:
    context = _cvrp_context(tmp_path)
    mechanism_id = "stagnation_repair_scheduler"
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a bounded stagnation repair-ordering scheduler while keeping "
            "the existing acceptance rule unchanged."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        target_weakness=(
            "The active scheduler keeps the same repair ordering during "
            "distance stagnation."
        ),
        mechanism_changes=(SimpleNamespace(id=mechanism_id, change_type="add"),),
        novelty_signature={
            "algorithm_family": "alns_vns_scheduler",
            "improvement_strategy": "stagnation_triggered_repair_ordering",
            "acceptance_strategy": "preserve_existing_acceptance",
            "runtime_budget_strategy": "bounded_scheduler_checks",
        },
        expected_telemetry={
            "activation": [
                f"solver_algorithm_context_records.{mechanism_id}_iterations",
                f"solver_algorithm_phase_runtime_ms.{mechanism_id}",
            ],
            "effect": [
                f"solver_algorithm_phase_improvement_counts.{mechanism_id}"
            ],
        },
    )

    preview = _hypothesis_schema_preview(context, hypothesis)

    assert preview["problem_expected_telemetry_preview"] is None


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
    assert "context.read_active_solver_map.research_lever_digest" in rendered
    assert "proposal-only advisory" in rendered
    assert "excluded from DecisionFeatures and promotion gates" in rendered
    assert "local route absorption, route compaction, or slack-preservation" in rendered
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


def test_cvrp_smoke_provider_rejects_destroy_effect_via_local_alias() -> None:
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
            "    mechanism = 'spatial_cluster_removal'\n"
            "    if context:\n"
            "        context.record_move(mechanism, attempted=1, accepted=1, "
            "delta=5, best_improved=1)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is not None
    assert "non-causal destroy telemetry" in issue


def test_cvrp_smoke_provider_allows_acceptance_decision_counters() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add sa_reheat acceptance-temperature policy with decision counters "
            "and phase-budget telemetry."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(SimpleNamespace(id="sa_reheat"),),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/scheduler.py",
        action="modify",
        code_content=(
            "def solve(self, instance, rng):\n"
            "    phase_start = self.context.elapsed_ms()\n"
            "    self.context.record_iteration('sa_reheat', 1)\n"
            "    self.context.record_phase('sa_reheat', self.context.elapsed_ms() - phase_start)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is None


def test_cvrp_smoke_provider_rejects_unknown_record_context_helper() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    hypothesis = HypothesisProposal(
        hypothesis_text="Add sa_reheat acceptance-temperature policy.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(SimpleNamespace(id="sa_reheat"),),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/scheduler.py",
        action="modify",
        code_content=(
            "def solve(self, instance, rng):\n"
            "    self.context.record_context('sa_reheat_iterations', 1)\n"
            "    self.context.record_phase('sa_reheat', 1)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is not None
    assert "unknown telemetry helper" in issue
    assert "record_iteration('sa_reheat'" in issue


def test_cvrp_smoke_provider_rejects_acceptance_broad_loop_effect() -> None:
    provider = CvrpAdapter(
        load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    ).solver_design_smoke_provider()
    hypothesis = HypothesisProposal(
        hypothesis_text="Add sa_reheat acceptance-temperature policy.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(SimpleNamespace(id="sa_reheat"),),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/scheduler.py",
        action="modify",
        code_content=(
            "def solve(self, instance, rng):\n"
            "    self.context.record_move('sa_reheat', attempted=1, accepted=1, delta=-1, best_improved=1)\n"
        ),
    )

    issue = provider.solver_design_static_smoke_issue(
        patch=patch,
        hypothesis=hypothesis,
    )

    assert issue is not None
    assert "broad-loop acceptance telemetry" in issue
