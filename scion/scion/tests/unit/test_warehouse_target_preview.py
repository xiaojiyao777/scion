from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.config.problem import ProblemSpec
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
)
from scion.core.proposal_pipeline.agentic_validation import AgenticValidationMixin
from scion.core.proposal_pipeline.problem_quality import (
    validate_problem_hypothesis_quality,
)
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
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
    assert "proposal-level diagnostic plan" in order_interface
    assert "do not invent undeclared expected_telemetry fields" in (
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
    assert (
        check.structured_rejection["gate_name"]
        == "warehouse_validation_transfer_quality"
    )


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
            "split_delta_sum positive, not merely screening wins."
        ),
        no_op_condition=(
            "Guard and return the original solution when the move would be "
            "screening-only or lacks a formal-cases general condition."
        ),
        risk_to_higher_priority=(
            "Validation transfer risk is a median delta 0 no hierarchical gain."
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
