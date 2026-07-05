from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *
from scion.core.models import HypothesisProposal, MechanismChange
from scion.core.proposal_pipeline.problem_quality import (
    validate_problem_hypothesis_quality,
    validate_problem_patch_quality,
)


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
    assert "Runtime evidence for problem-level hypotheses:" in rendered
    assert "`instance.customer_ids`" in rendered
    assert "`instance.allowed_routes`" in rendered
    assert "`instance.bks_routes`" in rendered
    assert "`instance.route_distance(route)`" in rendered
    assert "`CvrpSolution(routes=...)`" in rendered
    assert "fleet_violation first, then total_distance" in rendered
    assert "Capacity overload" in rendered
    assert "policies/baseline_algorithm.py" in rendered
    assert "policies/baseline_modules/*.py" in rendered
    assert "Legacy operator/component-policy" in rendered


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


def test_cvrp_solver_design_surface_interface_renders_safe_instance_api(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface("solver_design")

    assert "`instance.customer_ids`" in rendered
    assert "`instance.customer_count`" in rendered
    assert "`instance.demands[customer_id]`" in rendered
    assert "`instance.capacity`" in rendered
    assert "`instance.allowed_routes`" in rendered
    assert "`instance.bks_routes`" in rendered
    assert "`instance.distance(i, j)`" in rendered
    assert "fleet_violation = max(0, len(routes) - route_limit)" in rendered
    assert "context.record_phase(name, elapsed_ms)" in rendered
    assert "context.record_iteration(phase='search', count=1)" in rendered
    assert "Never use `instance.customers`" in rendered
    assert "context.record_move" in rendered
    assert "policies/baseline_modules/*.py" in rendered


def test_cvrp_adapter_patch_quality_blocks_construction_seed_activation_only(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a construction seed selection portfolio that chooses a "
            "Clarke-Wright savings seed before ALNS."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        novelty_signature={"mechanism_family": "construction_seed_portfolio"},
        mechanism_changes=(
            MechanismChange(id="savings_seed_selection_probe", change_type="add"),
        ),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content=(
            "def _savings_seed_selection_probe(instance, rng, context=None):\n"
            "    if context:\n"
            "        context.record_iteration('savings_seed_selection_probe', 1)\n"
            "        context.record_phase('savings_seed_selection_probe', 1)\n"
            "    return _construct_initial_solution(instance, rng)\n"
        ),
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
        patch,
    )

    assert check.allowed is False
    assert "cvrp_construction_seed_direct_effect_missing" in check.detail
    assert "agent_quality_blocked" in check.detail
    assert check.structured_rejection["gate_name"] == "cvrp_solver_design_static_quality"
    assert (
        check.structured_rejection["failure_code"]
        == "agent_quality_blocked:cvrp_construction_seed_direct_effect_missing"
    )
    assert check.structured_rejection["agent_block_reason"] == "agent_quality_blocked"
    assert "construction_seed_direct_effect_record_move" in (
        check.structured_rejection["missing_code_elements"]
    )


def test_cvrp_adapter_hypothesis_quality_blocks_successor32_mechanism_drift(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a bounded pair-failure cooldown selector before ALNS chooses "
            "a destroy and repair pair."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        novelty_signature={"mechanism_family": "acceptance_or_adaptive_weighting"},
        mechanism_changes=(
            MechanismChange(id="pair_failure_cooldown_selection", change_type="add"),
        ),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
    )

    assert check.allowed is False
    assert "cvrp_successor32_focus_mismatch" in check.detail
    assert check.structured_rejection["gate_name"] == "cvrp_successor32_focus"
    assert (
        check.structured_rejection["required_mechanism_id"]
        == "post_repair_effect_credit_weighting"
    )
    assert check.structured_rejection["selected_mechanism_ids"] == [
        "pair_failure_cooldown_selection"
    ]
    assert check.structured_rejection["agent_block_reason"] == (
        "agent_quality_blocked"
    )


def test_cvrp_adapter_hypothesis_quality_allows_successor32_focus(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Test post_repair_effect_credit_weighting by crediting ALNS "
            "destroy/repair weights from post-repair pre-polish objective "
            "effect."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        novelty_signature={"mechanism_family": "acceptance_or_adaptive_weighting"},
        mechanism_changes=(
            MechanismChange(
                id="post_repair_effect_credit_weighting",
                change_type="add",
            ),
        ),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
    )

    assert check.allowed is True


@pytest.mark.parametrize(
    ("mechanism_id", "target_file"),
    [
        ("route_angle_aware_2opt_star", "policies/baseline_modules/local_search.py"),
        ("edge_frequency_penalty_repair", "policies/baseline_modules/destroy_repair.py"),
    ],
)
def test_cvrp_adapter_hypothesis_quality_blocks_successor37_default_avoid(
    cvrp_adapter: ProblemAdapter,
    mechanism_id: str,
    target_file: str,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            f"Repeat {mechanism_id} as a CVRP solver-design mechanism after "
            "successor37."
        ),
        change_locus="solver_design",
        action="modify",
        target_file=target_file,
        novelty_signature={"mechanism_family": "clean_cvrp_solver_fork"},
        mechanism_changes=(MechanismChange(id=mechanism_id, change_type="add"),),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
    )

    assert check.allowed is False
    assert "cvrp_successor37_default_avoid" in check.detail
    assert check.structured_rejection["gate_name"] == (
        "cvrp_successor37_default_avoid"
    )
    assert check.structured_rejection["blocked_mechanism_id"] == mechanism_id
    assert check.structured_rejection["agent_block_reason"] == (
        "agent_quality_blocked"
    )
    assert "CMT2/CMT4 protection plan" in check.structured_rejection[
        "retry_constraint"
    ]


def test_cvrp_adapter_hypothesis_quality_allows_new_successor37_distinct_path(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = _solver_design_hypothesis()

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
    )

    assert check.allowed is True


def test_cvrp_hypothesis_quality_accepts_prompt_schema_material_difference(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = _solver_design_hypothesis(
        material_difference={
            "changed_dimensions": ["repair_acceptance_rollback_scope"],
            "signature_digest": "cap-slack-rollback-v1",
            "evidence_status_delta": ["direct_effect_planned"],
        }
    )

    check = _validate_cvrp_hypothesis_quality(cvrp_adapter, hypothesis)

    assert check.allowed is True


def test_cvrp_hypothesis_quality_blocks_missing_mechanism_id(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = _solver_design_hypothesis(mechanism_id="")

    check = _validate_cvrp_hypothesis_quality(cvrp_adapter, hypothesis)

    assert check.allowed is False
    assert check.structured_rejection["gate_name"] == (
        "cvrp_solver_design_causal_path_contract"
    )
    assert "mechanism_changes.id" in check.structured_rejection["missing_fields"]
    assert check.structured_rejection["agent_block_reason"] == (
        "agent_quality_blocked"
    )
    assert check.structured_rejection["decision_features_excluded"] is True


def test_cvrp_hypothesis_quality_blocks_missing_material_difference(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = _solver_design_hypothesis(material_difference={})

    check = _validate_cvrp_hypothesis_quality(cvrp_adapter, hypothesis)

    assert check.allowed is False
    assert "material_difference" in check.structured_rejection["missing_fields"]
    assert "materially different CVRP-owned causal path" in (
        check.structured_rejection["retry_constraint"]
    )


@pytest.mark.parametrize(
    "expected_telemetry",
    [
        {},
        {"activity": ["capacity_slack_repair_rollback_activation"]},
        {"effect": ["direct_objective_delta_without_declared_id"]},
    ],
)
def test_cvrp_hypothesis_quality_blocks_missing_direct_effect_telemetry(
    cvrp_adapter: ProblemAdapter,
    expected_telemetry: dict[str, object],
) -> None:
    hypothesis = _solver_design_hypothesis(expected_telemetry=expected_telemetry)

    check = _validate_cvrp_hypothesis_quality(cvrp_adapter, hypothesis)

    assert check.allowed is False
    assert "expected_telemetry.effect" in (
        check.structured_rejection["missing_fields"]
    )
    assert "direct objective-effect telemetry" in (
        check.structured_rejection["retry_constraint"]
    )


def test_cvrp_hypothesis_quality_blocks_missing_cmt_protection(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = _solver_design_hypothesis(
        branch_lesson_usage={
            "clean_fork_diversity_claim": {
                "claim": "This is distinct and protects CMT2/CMT4 in prose only."
            }
        }
    )

    check = _validate_cvrp_hypothesis_quality(cvrp_adapter, hypothesis)

    assert check.allowed is False
    assert "branch_lesson_usage.clean_fork_diversity_claim" in (
        check.structured_rejection["missing_fields"]
    )
    assert "CMT2/CMT4 protected-case protection evidence" in (
        check.structured_rejection["retry_constraint"]
    )
    assert "clean_fork_diversity_claim.protected_cases" in (
        check.structured_rejection["retry_constraint"]
    )
    assert "clean_fork_diversity_claim.protection_plan" in (
        check.structured_rejection["retry_constraint"]
    )
    assert (
        check.structured_rejection["repair_template"]["example_branch_lesson_usage"][
            "clean_fork_diversity_claim"
        ]["protected_cases"]
        == ["CMT2", "CMT4"]
    )


@pytest.mark.parametrize(
    "surface_name",
    [
        "construction_policy",
        "search_policy",
        "baseline_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ],
)
def test_cvrp_legacy_policy_surface_interfaces_are_removed(
    cvrp_adapter: ProblemAdapter,
    surface_name: str,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface(surface_name)

    assert "not an active CVRP research surface" in rendered
    assert "Use solver_design" in rendered
    assert "policies/baseline_algorithm.py" in rendered


def _validate_cvrp_hypothesis_quality(
    cvrp_adapter: ProblemAdapter,
    hypothesis: HypothesisProposal,
) -> object:
    return validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
    )


def _solver_design_hypothesis(
    *,
    mechanism_id: str = "capacity_slack_repair_rollback",
    material_difference: dict[str, object] | None = None,
    expected_telemetry: dict[str, object] | None = None,
    branch_lesson_usage: dict[str, object] | None = None,
) -> HypothesisProposal:
    mechanism_changes = (
        (MechanismChange(id=mechanism_id, change_type="add"),) if mechanism_id else ()
    )
    return HypothesisProposal(
        hypothesis_text=(
            "Test a capacity_slack_repair_rollback mechanism with direct "
            "repair-before and repair-after objective telemetry plus CMT2/CMT4 "
            "guards."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        novelty_signature={"mechanism_family": "destroy_repair_selection"},
        material_difference=(
            material_difference
            if material_difference is not None
            else {
                "changed_dimensions": ["repair acceptance rollback scope"],
                "contrast": {
                    "nearest_reviewed_mechanism": "edge_frequency_penalty_repair",
                    "difference": "rollback on capacity slack harm, not edge memory",
                },
                "evidence": {
                    "source": "successor37 direct effect and CMT2/CMT4 losses"
                },
            }
        ),
        expected_telemetry=(
            expected_telemetry
            if expected_telemetry is not None
            else {
                "effect": [
                    "capacity_slack_repair_rollback.direct_objective_delta",
                ]
            }
        ),
        branch_lesson_usage=(
            branch_lesson_usage
            if branch_lesson_usage is not None
            else {
                "clean_fork_diversity_claim": {
                    "protected_cases": ["CMT2", "CMT4"],
                    "protection_plan": {
                        "CMT2": "track rollback accepted/rejected objective deltas",
                        "CMT4": "track rollback accepted/rejected objective deltas",
                    },
                }
            }
        ),
        mechanism_changes=mechanism_changes,
    )
