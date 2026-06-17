from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.config.problem import ProblemSpec
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    MechanismChange,
    PatchProposal,
)
from scion.core.proposal_pipeline.agentic_validation import AgenticValidationMixin
from scion.core.proposal_pipeline.problem_quality import (
    validate_problem_hypothesis_quality,
    validate_problem_patch_quality,
)
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
from scion.problem.providers import (
    active_subject_code_constraints_payload,
    active_subject_taxonomy_payload,
)
from scion.problems.warehouse_delivery.adapter import WarehouseDeliveryAdapter
from scion.proposal.engine.hypothesis_context_profiles import (
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.agentic_session import (
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalStatus,
    AgenticTerminationReason,
)
from scion.proposal.context.problem_adapter import _build_operator_interface_spec
from scion.runtime.surface_telemetry import declared_surface_telemetry_fields
from scion.runtime.telemetry_guard import build_telemetry_guard_summary
from scion.proposal.tools import (
    ContextExposurePolicy,
    ProposalToolContext,
    ProposalToolRegistry,
)


_WAREHOUSE_PROBLEM = (
    Path(__file__).resolve().parents[3]
    / "problems"
    / "warehouse_delivery"
    / "problem.yaml"
)
_WAREHOUSE_PROBLEM_V1 = _WAREHOUSE_PROBLEM.with_name("problem-v1.yaml")
_PACKAGED_WAREHOUSE_PROBLEM_V1 = (
    Path(__file__).resolve().parents[2]
    / "problems"
    / "warehouse_delivery"
    / "problem-v1.yaml"
)


def test_warehouse_vehicle_level_surface_passes_target_preview() -> None:
    spec = ProblemSpec.from_yaml(str(_WAREHOUSE_PROBLEM))
    _assert_vehicle_level_preview_passes(spec)


def test_warehouse_v1_bridge_preserves_surfaces_for_target_preview() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    bridge = bridge_problem_spec_v1(spec_v1)

    assert [surface.name for surface in bridge.problem_spec.research_surfaces] == [
        "order_level",
        "vehicle_level",
    ]
    _assert_vehicle_level_preview_passes(bridge.problem_spec)


def test_warehouse_operator_interfaces_render_problem_owned_guidance() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    order_interface = _build_operator_interface_spec(
        bridge.problem_spec,
        adapter=adapter,
        surface_name="order_level",
    )
    vehicle_interface = _build_operator_interface_spec(
        bridge.problem_spec,
        adapter=adapter,
        surface_name="vehicle_level",
    )

    assert "Active Surface Prompt Guidance: order_level" in order_interface
    assert "top-k, sampling, or early-exit cap" in order_interface
    assert "Avoid repeated full-solution feasibility/objective recomputation" in (
        order_interface
    )
    assert "O(n^2) trial evaluation" in order_interface
    assert "Active Surface Prompt Guidance: vehicle_level" in vehicle_interface
    assert "Removing, disabling, or replacing split/merge operators" in (
        vehicle_interface
    )
    assert "operators/split_vehicle.py" in vehicle_interface
    assert "assignment-completeness check" in vehicle_interface
    assert "keeps every order assigned exactly once" in vehicle_interface
    assert "Solution.assignment synchronized with Vehicle.order_ids" in (
        vehicle_interface
    )
    assert "O(n^2) trial evaluation" not in vehicle_interface
    assert "screening-to-validation transfer risk" in order_interface
    assert "operator activation counters" in order_interface
    assert "effect counters" in vehicle_interface
    assert "VALIDATION_FAIL_NO_HIERARCHICAL_GAIN" in vehicle_interface
    assert "self.validation_transfer_diagnostics" in order_interface
    assert "operator_diagnostics.{mechanism}.*" in order_interface
    assert "undeclared expected_telemetry fields" in (
        vehicle_interface
    )


def test_warehouse_problem_context_surfaces_validation_transfer_diagnostic() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    summary = adapter.render_problem_summary()
    diagnostic = filter_hypothesis_context_for_prompt(
        {
            "problem_summary": summary,
            "research_surfaces": "Research surfaces: vehicle_level",
            "operator_categories": "vehicle_level",
            "available_actions": "modify, create_new",
            "targetable_files": "operators/*.py",
            "champion_operators_code": "class MergeVehicles:\n    pass\n",
            "champion_stats": "champion_v1",
            "problem_measurement_diagnostics": {
                "schema_version": "problem_measurement_proposal_diagnostic.v1",
                "taint": "problem_owned_proposal_diagnostic",
                "decision_features_excluded": True,
                "adapter_diagnostics": (
                    adapter.render_problem_measurement_diagnostics()
                ),
            },
        }
    )["problem_measurement_diagnostics"]

    assert "screening-to-validation transfer" in summary
    assert "same_subcategory_consolidate-style operator" in summary
    assert "formal aggregate 2/3/0" in diagnostic
    assert "paired 6/9/0" in diagnostic
    assert "VALIDATION_FAIL_NO_HIERARCHICAL_GAIN" in diagnostic
    assert "operator_invocations" in diagnostic
    assert "split_delta_sum" in diagnostic
    assert "excluded_from_decision_features" in diagnostic


def test_warehouse_adapter_declares_structural_activation_refs() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    taxonomy = active_subject_taxonomy_payload(
        problem_spec=spec_v1,
        adapter=adapter,
        surface="vehicle_level",
    )

    assert "operator_invocations" in taxonomy["telemetry_activation_refs"]
    assert "eligible_vehicle_or_order_groups_seen" in taxonomy[
        "telemetry_activation_refs"
    ]
    assert "accepted_moves" in taxonomy["telemetry_activation_refs"]


def test_warehouse_adapter_exposes_active_subject_code_constraints() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    constraints = active_subject_code_constraints_payload(
        problem_spec=spec_v1,
        adapter=adapter,
        surface="vehicle_level",
    )

    rendered = str(constraints)
    assert constraints["version"] == (
        "warehouse_operator_validation_transfer_code_constraints.v1"
    )
    assert "self.validation_transfer_diagnostics" in rendered
    assert "self._new_diagnostics()" in rendered
    assert "new_diagnostics()" in rendered
    assert "operator_invocations" in rendered
    assert "eligible_vehicle_or_order_groups_seen" in rendered
    assert "accepted_moves" in rendered
    assert "split_delta_sum" in rendered
    assert "cost_delta_sum" in rendered
    assert "improving_move_count" in rendered
    assert "activation" in rendered
    assert "effect counters" in rendered
    assert "split-preserving cost-only compression" in rendered
    assert "unbounded full vehicle-pair scans" in rendered
    assert "top_k" in rendered
    assert "lexicographic" in rendered
    assert "Comments or string mentions" in rendered


def test_warehouse_problem_spec_declares_operator_diagnostics_telemetry() -> None:
    for path in (_WAREHOUSE_PROBLEM_V1, _PACKAGED_WAREHOUSE_PROBLEM_V1):
        spec_v1 = load_problem_spec_v1_from_yaml(path)
        rendered = path.read_text(encoding="utf-8")
        assert "screening-to-validation transfer risk" in rendered
        assert "operator_diagnostics.{mechanism}.operator_invocations" in rendered

        for surface_name in ("order_level", "vehicle_level"):
            surface = _surface(spec_v1, surface_name)
            fields = declared_surface_telemetry_fields(
                surface,
                problem_spec=spec_v1,
                declared_mechanisms=("fill_and_downsize",),
            )
            assert (
                "operator_diagnostics.fill_and_downsize.operator_invocations"
                in fields
            )
            assert "operator_diagnostics.fill_and_downsize.accepted_moves" in fields
            assert (
                "operator_diagnostics.fill_and_downsize.split_delta_sum" in fields
            )

            summary = build_telemetry_guard_summary(
                candidate_runtimes=[
                    {
                        "operator_diagnostics": {
                            "fill_and_downsize": {
                                "operator_invocations": 4,
                                "eligible_vehicle_or_order_groups_seen": 2,
                                "accepted_moves": 1,
                                "split_delta_sum": 1,
                                "cost_delta_sum": 575,
                                "improving_move_count": 1,
                            }
                        }
                    }
                ],
                problem_spec=spec_v1,
                selected_surface=surface_name,
                declared_mechanisms=(
                    MechanismChange(id="fill_and_downsize", change_type="add"),
                ),
            )

            diagnostic = summary["mechanism_diagnostics"][0]
            assert summary["passed"] is True
            assert diagnostic["mechanism"] == "fill_and_downsize"
            assert diagnostic["activation_status"] == "observed"
            assert diagnostic["effect_status"] == "positive"


def test_warehouse_preview_rejects_existing_operator_module_delete() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    surface = _surface(spec_v1, "order_level")

    preview = adapter.preview_research_surface_patch(
        patch=PatchProposal(
            file_path="operators/swap_orders.py",
            action="delete",
            code_content="",
        ),
        surface=surface,
    )

    assert preview["passed"] is False
    assert preview["verification_run"] is False
    assert any("warehouse_operator_module_delete" in issue for issue in preview["issues"])
    assert preview["checks"][0]["name"] == "warehouse_operator_module_delete"


def test_warehouse_preview_rejects_existing_operator_module_remove() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    surface = _surface(spec_v1, "order_level")

    preview = adapter.preview_research_surface_patch(
        patch=PatchProposal(
            file_path="operators/move_order.py",
            action="remove",
            code_content="",
        ),
        surface=surface,
    )

    assert preview["passed"] is False
    assert any("warehouse_operator_module_delete" in issue for issue in preview["issues"])


def test_warehouse_preview_rejects_undeclared_internal_state_key() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    surface = _surface(spec_v1, "order_level")
    code = """
from operators.base import Operator


class MoveOrder(Operator):
    def __init__(self, instance, phase=1):
        self.instance = instance
        self.phase = phase

    def execute(self, solution, rng):
        work = {
            vid: {"pallets": 0, "hazard": 0}
            for vid in sorted(solution.vehicles)
        }
        return work["v1"]["capacity"]
"""

    preview = adapter.preview_research_surface_patch(
        patch=PatchProposal(
            file_path="operators/move_order.py",
            action="modify",
            code_content=code,
        ),
        surface=surface,
    )

    assert preview["passed"] is False
    assert any(
        "warehouse_operator_internal_state_key" in issue
        for issue in preview["issues"]
    )


def test_warehouse_quality_check_blocks_missing_validation_transfer_claims() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = Branch(
        branch_id="warehouse-weak-positive",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    weak_hypothesis = HypothesisProposal(
        hypothesis_text="Merge same-subcategory vehicles more aggressively.",
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        target_weakness="Some subcategories are split across vehicles.",
        expected_effect="Screening should improve subcategory_splits.",
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        weak_hypothesis,
    )

    assert check.allowed is False
    assert "warehouse_validation_transfer_quality_missing" in check.detail
    assert "agent_quality_blocked" in check.detail
    assert "validation_transfer_risk" in check.detail
    assert "activation_effect_diagnostics" in check.detail
    assert "screening_only_guard" in check.detail
    assert "effect_scope_or_split_cost_risk" in check.detail
    assert "runtime_bounded_acceptance" in check.detail
    assert (
        check.structured_rejection["gate_name"]
        == "warehouse_validation_transfer_quality"
    )
    template = check.structured_rejection["repair_template"]
    assert template["repair_type"] == (
        "warehouse_validation_transfer_hypothesis_quality"
    )
    assert "validation_transfer_risk" in template["missing_items"]
    assert "expected_effect" in template["hypothesis_field_hints"]


def test_agentic_validation_blocks_warehouse_hypothesis_before_code() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = Branch(
        branch_id="warehouse-agentic",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Merge same-subcategory vehicles more aggressively.",
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-warehouse-agentic",
        campaign_id="camp-warehouse",
        branch_id=branch.branch_id,
        champion_version=champion.version,
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path="operators/merge_vehicles.py",
            action="modify",
            code_content="class MergeVehicles:\n    pass\n",
        ),
        termination_reason=AgenticTerminationReason.COMPLETED,
    )

    sanitized = _AgenticValidationHarness(adapter)._validate_and_sanitize_agentic_output(
        branch=branch,
        champion=champion,
        output=output,
    )

    assert sanitized.status == AgenticProposalStatus.FAILED
    assert sanitized.patch is None
    assert sanitized.hypothesis is None
    assert sanitized.failure_category == AgenticFailureCategory.PREMISE_CONTRADICTED
    assert (
        sanitized.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED
    )
    assert "warehouse_validation_transfer_quality_missing" in (
        sanitized.failure_detail or ""
    )
    assert sanitized.structured_rejection is not None
    assert (
        sanitized.structured_rejection["gate_name"]
        == "warehouse_validation_transfer_quality"
    )


def test_warehouse_quality_check_allows_transfer_and_diagnostics_claims() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = Branch(
        branch_id="warehouse-weak-positive",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine the merge trigger for screening-to-validation transfer: "
            "the mechanism should generalize because it only acts on "
            "case-general same-subcategory groups with spare capacity."
        ),
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        target_weakness=(
            "The prior screening positive can fail formal validation when "
            "activation occurs without a hierarchical gain."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show accepted_moves and "
            "split_delta_sum positive, not merely screening wins. The intended "
            "effect scope is true split-positive improvement, with cost_delta "
            "as a secondary tie-breaker."
        ),
        no_op_condition=(
            "Guard and return the original solution when the move would be "
            "screening-only or lacks a formal-cases general condition."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is a median delta 0 no hierarchical gain."
        ),
        runtime_budget_strategy=(
            "Use a top_k candidate cap and early exit after one accepted merge "
            "to keep runtime comparable to the champion."
        ),
        expected_telemetry={
            "activation": ["accepted_moves"],
            "effect": ["split_delta_sum"],
        },
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        hypothesis,
    )

    assert check.allowed is True


def test_warehouse_hypothesis_quality_rejects_missing_split_cost_effect_scope() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine merge_vehicles for screening-to-validation transfer using "
            "case-general same-subcategory groups."
        ),
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        target_weakness=(
            "A screening-positive merge can fail formal validation with no "
            "hierarchical gain."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show operator_invocations, "
            "accepted_moves, and improving_move_count positive."
        ),
        no_op_condition=(
            "Return the original solution when the move is screening-only or "
            "lexicographically dominated on formal cases."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is median delta 0 on formal cases."
        ),
        runtime_budget_strategy=(
            "Use a top_k candidate cap and early exit after one accepted merge."
        ),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
    )

    assert check.allowed is False
    assert "effect_scope_or_split_cost_risk" in check.detail
    assert "runtime_bounded_acceptance" not in check.detail


def test_warehouse_hypothesis_quality_rejects_missing_runtime_bound() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine merge_vehicles for screening-to-validation transfer using "
            "case-general same-subcategory groups."
        ),
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        target_weakness=(
            "A screening-positive merge can fail formal validation with no "
            "hierarchical gain."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show operator_invocations, "
            "accepted_moves, split_delta_sum, and cost_delta_sum. The intended "
            "effect scope is true split-positive improvement, with cost_delta "
            "as a secondary tie-breaker."
        ),
        no_op_condition=(
            "Return the original solution when the move is screening-only or "
            "lexicographically dominated on formal cases."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is median delta 0 on formal cases."
        ),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
    )

    assert check.allowed is False
    assert "runtime_bounded_acceptance" in check.detail
    assert "effect_scope_or_split_cost_risk" not in check.detail


def test_warehouse_hypothesis_quality_allows_split_cost_scope_and_runtime_bound() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
    )

    assert check.allowed is True


def test_warehouse_patch_quality_blocks_transfer_hypothesis_without_code_diagnostics() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = _warehouse_weak_positive_branch()
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def execute(self, solution, rng):
        candidate = solution.deep_copy()
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "warehouse_validation_transfer_patch_quality_missing" in check.detail
    assert "agent_quality_blocked" in check.detail
    assert "activation_effect_diagnostic_code" in check.detail
    assert (
        check.structured_rejection["gate_name"]
        == "warehouse_validation_transfer_patch_quality"
    )
    assert check.structured_rejection["agent_block_reason"] == "agent_quality_blocked"
    template = check.structured_rejection["repair_template"]
    assert template["repair_type"] == "warehouse_validation_transfer_patch_quality"
    assert "activation_effect_diagnostic_code" in template["missing_items"]
    assert "operator_invocations" in template["required_code_signals"]["activation"]
    assert "screening_only_guard" in template["example_identifiers"]


def test_warehouse_patch_quality_allows_diagnostics_and_guard_code() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = _warehouse_weak_positive_branch()
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        eligible_vehicle_or_order_groups_seen = 1
        diagnostics["eligible_vehicle_or_order_groups_seen"] += (
            eligible_vehicle_or_order_groups_seen
        )
        split_delta = 1
        cost_delta = 10
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
            return solution
        validation_transfer_guard = split_delta > 0 or cost_delta > 0
        if not validation_transfer_guard:
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_rejects_unbounded_nested_vehicle_pair_scan() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content=_merge_vehicle_pair_scan_code(bounded=False),
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "bounded_candidate_policy" in check.detail
    template = check.structured_rejection["repair_template"]
    assert "bounded_candidate_policy" in template["missing_items"]


def test_warehouse_patch_quality_allows_bounded_top_k_vehicle_pair_scan() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content=_merge_vehicle_pair_scan_code(bounded=True),
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_quality_blocks_existing_operator_invented_telemetry_key() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine move_order for screening-to-validation transfer using a "
            "case-general guard rather than a screening-only move."
        ),
        change_locus="order_level",
        action="modify",
        target_file="operators/move_order.py",
        target_weakness=(
            "Formal validation can fail when screening activation has no "
            "hierarchical gain."
        ),
        expected_effect=(
            "Activation and effect diagnostics should show operator_invocations "
            "and split_delta_sum under an exportable runtime key."
        ),
        no_op_condition=(
            "Return the original solution when the move is not case-general or "
            "would worsen lexicographic split/cost objectives."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is a screening-positive no hierarchical "
            "gain on formal cases."
        ),
        expected_telemetry={
            "activation": [
                (
                    "operator_diagnostics."
                    "split_preserving_vehicle_elimination.operator_invocations"
                )
            ],
            "effect": [
                (
                    "operator_diagnostics."
                    "split_preserving_vehicle_elimination.split_delta_sum"
                )
            ],
        },
        mechanism_changes=(
            MechanismChange(
                id="split_preserving_vehicle_elimination",
                change_type="modify",
            ),
        ),
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
    )

    assert check.allowed is False
    rejection = check.structured_rejection
    assert (
        rejection["failure_code"]
        == "agent_quality_blocked:warehouse_operator_telemetry_identity_mismatch"
    )
    assert rejection["gate_name"] == "warehouse_operator_telemetry_identity"
    assert rejection["expected_runtime_key"] == "move_order"
    assert rejection["offending_mechanism_ids"] == [
        "split_preserving_vehicle_elimination"
    ]
    assert "operator_diagnostics.move_order.operator_invocations" in str(
        rejection["repair_template"]
    )


def test_warehouse_quality_allows_existing_operator_runtime_key_shape() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine move_order for screening-to-validation transfer with a "
            "case-general order relocation guard."
        ),
        change_locus="order_level",
        action="modify",
        target_file="operators/move_order.py",
        target_weakness=(
            "Prior screening-positive activation can fail formal validation "
            "with no hierarchical gain."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show "
            "operator_diagnostics.move_order.operator_invocations and "
            "operator_diagnostics.move_order.split_delta_sum positive. The "
            "intended effect scope is true split-positive improvement, with "
            "cost_delta as a secondary tie-breaker."
        ),
        no_op_condition=(
            "Return the original solution when the move is screening-only, "
            "not case-general, or lexicographically dominated."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is no hierarchical gain on formal cases."
        ),
        runtime_budget_strategy=(
            "Use a top_k order-pair cap and early exit after one accepted move."
        ),
        expected_telemetry={
            "activation": [
                "operator_diagnostics.move_order.operator_invocations",
                (
                    "operator_diagnostics.move_order."
                    "eligible_vehicle_or_order_groups_seen"
                ),
                "operator_diagnostics.move_order.accepted_moves",
            ],
            "effect": [
                "operator_diagnostics.move_order.split_delta_sum",
                "operator_diagnostics.move_order.cost_delta_sum",
            ],
        },
        mechanism_changes=(MechanismChange(id="move_order", change_type="modify"),),
    )
    patch = PatchProposal(
        file_path="operators/move_order.py",
        action="modify",
        code_content=_valid_validation_transfer_operator_code("MoveOrder"),
        mechanism_changes=(MechanismChange(id="move_order", change_type="modify"),),
    )

    hypothesis_check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
    )
    patch_check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
        patch,
    )

    assert hypothesis_check.allowed is True
    assert patch_check.allowed is True


def test_warehouse_quality_allows_create_new_operator_runtime_key_shape() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    runtime_key = "same_subcategory_residual_merge"
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Create a same-subcategory residual merge operator for "
            "screening-to-validation transfer with a case-general merge guard."
        ),
        change_locus="vehicle_level",
        action="create_new",
        target_file=f"operators/{runtime_key}.py",
        target_weakness=(
            "Subcategory residuals can look positive in screening but fail "
            "formal validation if they do not transfer."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show "
            f"operator_diagnostics.{runtime_key}.operator_invocations and "
            f"operator_diagnostics.{runtime_key}.split_delta_sum positive. "
            "The intended effect scope is true split-positive improvement, "
            "with cost_delta as a secondary tie-breaker."
        ),
        no_op_condition=(
            "Return the original solution when a merge is screening-only, not "
            "case-general, or lexicographically dominated."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is no hierarchical gain on formal cases."
        ),
        runtime_budget_strategy=(
            "Use a max_candidates cap and early exit after one accepted merge."
        ),
        expected_telemetry={
            "activation": [
                f"operator_diagnostics.{runtime_key}.operator_invocations",
                f"operator_diagnostics.{runtime_key}.accepted_moves",
            ],
            "effect": [
                f"operator_diagnostics.{runtime_key}.split_delta_sum",
                f"operator_diagnostics.{runtime_key}.cost_delta_sum",
            ],
        },
        mechanism_changes=(MechanismChange(id=runtime_key, change_type="add"),),
    )
    patch = PatchProposal(
        file_path=f"operators/{runtime_key}.py",
        action="create",
        code_content=_valid_validation_transfer_operator_code(
            "SameSubcategoryResidualMerge"
        ),
        mechanism_changes=(MechanismChange(id=runtime_key, change_type="add"),),
    )

    hypothesis_check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
    )
    patch_check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        hypothesis,
        patch,
    )

    assert hypothesis_check.allowed is True
    assert patch_check.allowed is True


def test_warehouse_patch_quality_accepts_helper_returned_diagnostics_dict() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = self._new_diagnostics()

    def _new_diagnostics(self):
        return {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        split_delta = 1
        cost_delta = 0
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_rejects_helper_diagnostics_missing_keys() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
def new_diagnostics():
    return {
        "operator_invocations": 0,
        "eligible_vehicle_or_order_groups_seen": 0,
        "accepted_moves": 0,
        "split_delta_sum": 0,
        "cost_delta_sum": 0,
    }


class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = new_diagnostics()

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        split_delta = 1
        cost_delta = 0
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "activation_effect_diagnostic_code" in check.detail


def test_warehouse_patch_quality_accepts_split_and_cost_delta_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        split_delta = 0
        cost_delta = 1200
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_accepts_candidate_base_split_cost_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        base_splits = 3
        candidate_splits = 2
        base_cost = 7200
        candidate_cost = 5100
        diagnostics["split_delta_sum"] += base_splits - candidate_splits
        diagnostics["cost_delta_sum"] += base_cost - candidate_cost
        lexicographic_guard = (
            candidate_splits < base_splits
            or candidate_splits == base_splits
            and candidate_cost < base_cost
        )
        if not lexicographic_guard:
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_accepts_helper_based_split_cost_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidates = self._rank_candidates(solution)[:16]
        diagnostics["eligible_vehicle_or_order_groups_seen"] += len(candidates)
        for candidate in candidates:
            evaluated = self._evaluate_candidate(candidate)
            if evaluated is None:
                continue
            split_delta, cost_delta, new_solution = evaluated
            diagnostics["split_delta_sum"] += split_delta
            diagnostics["cost_delta_sum"] += cost_delta
            diagnostics["accepted_moves"] += 1
            diagnostics["improving_move_count"] += 1
            return new_solution
        return solution

    def _evaluate_candidate(self, candidate):
        split_delta = candidate.split_delta
        cost_delta = candidate.cost_delta
        if split_delta > 0 or (split_delta == 0 and cost_delta > 0):
            return split_delta, cost_delta, candidate.solution
        return None

    def _rank_candidates(self, solution):
        max_candidates = 16
        return sorted(solution.candidates)[:max_candidates]
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_accepts_loop_continue_helper_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidates = self._rank_candidates(solution, sorted(solution.vehicles))[:16]
        diagnostics["eligible_vehicle_or_order_groups_seen"] += len(candidates)
        best_cost_move = None
        for _score, v1_id, v2_id in candidates:
            candidate = self._evaluate_merge(solution, v1_id, v2_id)
            if candidate is None:
                continue
            split_delta, cost_delta, new_vtype = candidate
            if split_delta > 0:
                return self._apply_merge(solution, v1_id, v2_id, new_vtype, split_delta, cost_delta)
            if split_delta == 0 and cost_delta > 0:
                best_cost_move = (v1_id, v2_id, cost_delta, new_vtype)
        if best_cost_move is None:
            return solution
        dst_vid, src_vid, cost_delta, new_vtype = best_cost_move
        return self._apply_merge(solution, dst_vid, src_vid, new_vtype, 0, cost_delta)

    def _evaluate_merge(self, solution, dst_vid, src_vid):
        split_delta = solution.base_splits - solution.candidate_splits
        cost_delta = solution.base_cost - solution.candidate_cost
        if split_delta > 0 or (split_delta == 0 and cost_delta > 0):
            return split_delta, cost_delta, solution.new_vtype
        return None

    def _apply_merge(self, solution, dst_vid, src_vid, new_vtype, split_delta, cost_delta):
        new_sol = solution.deep_copy()
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["accepted_moves"] += 1
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        diagnostics["improving_move_count"] += 1
        return new_sol

    def _rank_candidates(self, solution, vehicle_ids):
        max_candidates = 16
        return sorted(solution.candidates)[:max_candidates]
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_accepts_direct_candidate_continue_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidates = self._rank_candidates(solution)[:16]
        diagnostics["eligible_vehicle_or_order_groups_seen"] += len(candidates)
        base_splits = self._subcategory_splits(solution)
        base_cost = self._total_cost(solution)
        for candidate in candidates:
            new_sol = self._apply_candidate(solution, candidate)
            candidate_splits = self._subcategory_splits(new_sol)
            candidate_cost = self._total_cost(new_sol)
            split_delta = base_splits - candidate_splits
            cost_delta = base_cost - candidate_cost
            if split_delta < 0:
                continue
            if split_delta == 0 and cost_delta <= 0:
                continue
            diagnostics["split_delta_sum"] += split_delta
            diagnostics["cost_delta_sum"] += cost_delta
            diagnostics["accepted_moves"] += 1
            diagnostics["improving_move_count"] += 1
            return new_sol
        return solution

    def _rank_candidates(self, solution):
        max_candidates = 16
        return sorted(solution.candidates)[:max_candidates]
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_accepts_direct_split_preserving_cost_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidates = self._rank_candidates(solution)[:16]
        diagnostics["eligible_vehicle_or_order_groups_seen"] += len(candidates)
        base_split = self._subcategory_splits(solution)
        base_cost = self._total_cost(solution)
        for candidate in candidates:
            new_sol = self._apply_candidate(solution, candidate)
            split_delta = base_split - self._subcategory_splits(new_sol)
            cost_delta = base_cost - self._total_cost(new_sol)
            if split_delta != 0 or cost_delta <= 0:
                continue
            diagnostics["split_delta_sum"] += split_delta
            diagnostics["cost_delta_sum"] += cost_delta
            diagnostics["accepted_moves"] += 1
            diagnostics["improving_move_count"] += 1
            return new_sol
        return solution

    def _rank_candidates(self, solution):
        max_candidates = 16
        return sorted(solution.candidates)[:max_candidates]
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is True


def test_warehouse_patch_quality_rejects_split_only_candidate_continue_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidates = self._rank_candidates(solution)[:16]
        diagnostics["eligible_vehicle_or_order_groups_seen"] += len(candidates)
        for candidate in candidates:
            split_delta = candidate.split_delta
            diagnostics["split_delta_sum"] += split_delta
            diagnostics["cost_delta_sum"] += candidate.cost_delta
            if split_delta < 0:
                continue
            diagnostics["accepted_moves"] += 1
            diagnostics["improving_move_count"] += 1
            return candidate.solution
        return solution

    def _rank_candidates(self, solution):
        max_candidates = 16
        return sorted(solution.candidates)[:max_candidates]
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "screening_or_lexicographic_guard" in check.detail


def test_warehouse_patch_quality_rejects_helper_with_string_only_guard() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        diagnostics["split_delta_sum"] += 1
        diagnostics["cost_delta_sum"] += 1
        if self._evaluate_candidate() is None:
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return solution.deep_copy()

    def _evaluate_candidate(self):
        if "split_delta and cost_delta are checked":
            return object()
        return None
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "screening_or_lexicographic_guard" in check.detail


def test_warehouse_patch_quality_rejects_string_only_guard_with_diagnostics() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        diagnostics["split_delta_sum"] += 1
        diagnostics["cost_delta_sum"] += 1
        if "lexicographic guard with split_delta and cost_delta":
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return solution.deep_copy()
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "screening_or_lexicographic_guard" in check.detail


def test_warehouse_patch_quality_rejects_comment_only_guard_with_diagnostics() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        diagnostics["split_delta_sum"] += 1
        diagnostics["cost_delta_sum"] += 1
        # lexicographic guard: split_delta and cost_delta checked elsewhere
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return solution.deep_copy()
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "screening_or_lexicographic_guard" in check.detail


def test_warehouse_patch_quality_rejects_local_only_diagnostics_dict() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = _warehouse_weak_positive_branch()
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def execute(self, solution, rng):
        validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }
        validation_transfer_diagnostics["operator_invocations"] += 1
        validation_transfer_diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        validation_transfer_diagnostics["split_delta_sum"] += 1
        validation_transfer_diagnostics["cost_delta_sum"] += 1
        candidate = solution.deep_copy()
        validation_transfer_guard = True
        if not validation_transfer_guard:
            return solution
        validation_transfer_diagnostics["accepted_moves"] += 1
        validation_transfer_diagnostics["improving_move_count"] += 1
        return candidate
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "activation_effect_diagnostic_code" in check.detail
    template = check.structured_rejection["repair_template"]
    assert "self.validation_transfer_diagnostics" in " ".join(
        template["minimal_shape"]
    )


def test_warehouse_patch_quality_rejects_nonstandard_counters_and_text_signals() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    patch = PatchProposal(
        file_path="operators/merge_vehicles.py",
        action="modify",
        code_content="""
class MergeVehicles:
    def execute(self, solution, rng):
        diagnostic_counter_metric = {
            "operator_invocation_count": 1,
            "effect_delta_sum": 0,
        }
        screening_only_guard = "mentioned but not executable"
        return solution.deep_copy()
""",
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=adapter),
        _warehouse_weak_positive_branch(),
        _warehouse_transfer_quality_hypothesis(),
        patch,
    )

    assert check.allowed is False
    assert "activation_effect_diagnostic_code" in check.detail
    assert "screening_or_lexicographic_guard" in check.detail


def test_agentic_validation_blocks_warehouse_patch_without_transfer_diagnostics() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = _warehouse_weak_positive_branch(branch_id="warehouse-agentic-code")
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-warehouse-agentic-code",
        campaign_id="camp-warehouse",
        branch_id=branch.branch_id,
        champion_version=champion.version,
        hypothesis=_warehouse_transfer_quality_hypothesis(),
        patch=PatchProposal(
            file_path="operators/merge_vehicles.py",
            action="modify",
            code_content="""
class MergeVehicles:
    def execute(self, solution, rng):
        return solution.deep_copy()
""",
        ),
        termination_reason=AgenticTerminationReason.COMPLETED,
    )

    sanitized = _AgenticValidationHarness(adapter)._validate_and_sanitize_agentic_output(
        branch=branch,
        champion=champion,
        output=output,
    )

    assert sanitized.status == AgenticProposalStatus.FAILED
    assert sanitized.patch is None
    assert sanitized.termination_reason == AgenticTerminationReason.CODE_GENERATION_FAILED
    assert sanitized.failure_category == "agent_grounding_failure"
    assert "warehouse_validation_transfer_patch_quality_missing" in (
        sanitized.failure_detail or ""
    )
    assert sanitized.structured_rejection is not None
    assert (
        sanitized.structured_rejection["failure_code"]
        == "agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing"
    )
    assert (
        sanitized.structured_rejection["gate_name"]
        == "warehouse_validation_transfer_patch_quality"
    )
    assert sanitized.structured_rejection["repair_template"]["repair_type"] == (
        "warehouse_validation_transfer_patch_quality"
    )


def test_warehouse_quality_check_does_not_accept_undeclared_telemetry_only() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    adapter = WarehouseDeliveryAdapter(spec_v1)
    branch = Branch(
        branch_id="warehouse-weak-positive",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine this operator for screening-to-validation transfer and "
            "formal cases."
        ),
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        no_op_condition="Guard against screening-only no-op gains.",
        expected_telemetry={
            "activation": ["accepted_moves"],
            "effect": ["split_delta_sum"],
        },
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=adapter),
        branch,
        hypothesis,
    )

    assert check.allowed is False
    assert "activation_effect_diagnostics" in check.detail


def test_problem_quality_check_without_adapter_does_not_affect_non_warehouse() -> None:
    branch = Branch(
        branch_id="generic-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic operator refinement.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local.py",
    )

    check = validate_problem_hypothesis_quality(
        SimpleNamespace(adapter=None),
        branch,
        hypothesis,
    )

    assert check.allowed is True


def _assert_vehicle_level_preview_passes(spec: ProblemSpec) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = ProposalToolContext(
        session_id="warehouse-preview-test",
        campaign_id="warehouse-preview-test",
        problem_spec=spec,
        policy=ContextExposurePolicy(allow_contract_preview=True),
    )

    observation = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "vehicle_level",
            "action": "modify",
            "target_file": "operators/merge_vehicles.py",
        },
        context,
    )

    assert observation.is_error is False
    assert observation.structured_payload["passed"] is True
    assert observation.structured_payload["issues"] == []
    assert observation.structured_payload["surface"]["name"] == "vehicle_level"
    assert observation.structured_payload["declared_targets"] == ["operators/*.py"]


def _surface(spec, name: str):
    return next(surface for surface in spec.research_surfaces if surface.name == name)


def _warehouse_weak_positive_branch(
    *,
    branch_id: str = "warehouse-weak-positive",
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )


def _warehouse_transfer_quality_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=(
            "Refine the merge trigger for screening-to-validation transfer: "
            "the mechanism should generalize because it only acts on "
            "case-general same-subcategory groups with spare capacity."
        ),
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/merge_vehicles.py",
        target_weakness=(
            "The prior screening positive can fail formal validation when "
            "activation occurs without a hierarchical gain."
        ),
        expected_effect=(
            "Activation/effect diagnostics should show operator_invocations, "
            "eligible_vehicle_or_order_groups_seen, accepted_moves, "
            "split_delta_sum, cost_delta_sum, and improving_move_count "
            "positive, not merely screening wins. The intended effect scope is "
            "true split-positive improvement, with cost_delta as a secondary "
            "tie-breaker rather than split-preserving cost-only compression."
        ),
        no_op_condition=(
            "Guard and return the original solution when the move would be "
            "screening-only or lexicographically dominated on formal cases."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is a median delta 0 no hierarchical gain; "
            "if a candidate only compresses cost while preserving splits, it "
            "may overfit screening/validation and regress frozen/runtime."
        ),
        runtime_budget_strategy=(
            "Use a top_k candidate-pair cap and early exit after one accepted "
            "merge to bound runtime."
        ),
    )


def _merge_vehicle_pair_scan_code(*, bounded: bool) -> str:
    candidate_policy = ""
    iter_source = "candidate_pairs"
    if bounded:
        candidate_policy = """
        top_k = 8
        candidate_pairs = sorted(candidate_pairs, key=lambda item: item[0])[:top_k]
"""
    return f"""
class MergeVehicles:
    def __init__(self):
        self.validation_transfer_diagnostics = {{
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }}

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate_pairs = []
        for source_id, source_vehicle in solution.vehicles.items():
            for target_id, target_vehicle in solution.vehicles.items():
                if source_id == target_id:
                    continue
                candidate_pairs.append((0, source_id, target_id))
{candidate_policy}
        for _score, source_id, target_id in {iter_source}:
            diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
            candidate = solution.deep_copy()
            split_delta = 1
            cost_delta = 10
            diagnostics["split_delta_sum"] += split_delta
            diagnostics["cost_delta_sum"] += cost_delta
            if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
                return solution
            diagnostics["accepted_moves"] += 1
            diagnostics["improving_move_count"] += 1
            return candidate
        return solution
"""


def _valid_validation_transfer_operator_code(class_name: str) -> str:
    return f"""
class {class_name}:
    def __init__(self):
        self.validation_transfer_diagnostics = {{
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }}

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        candidate = solution.deep_copy()
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        split_delta = 1
        cost_delta = 10
        diagnostics["split_delta_sum"] += split_delta
        diagnostics["cost_delta_sum"] += cost_delta
        if split_delta < 0 or (split_delta == 0 and cost_delta <= 0):
            return solution
        diagnostics["accepted_moves"] += 1
        diagnostics["improving_move_count"] += 1
        return candidate
"""


class _AgenticValidationHarness(AgenticValidationMixin):
    require_agentic_problem_anchors = False
    problem_id = None
    problem_spec_hash = None
    split_manifest_hash = None
    seed_ledger_hash = None
    campaign_id = "camp-warehouse"
    step_history = []

    def __init__(self, adapter):
        self.problem_runtime = SimpleNamespace(adapter=adapter)

    def _forced_hypothesis_violation(self, *_args, **_kwargs):
        return None

    def _active_problem_boundary_violation(self, *_args, **_kwargs):
        return None
