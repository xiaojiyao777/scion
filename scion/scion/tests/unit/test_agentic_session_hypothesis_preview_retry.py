from __future__ import annotations

from dataclasses import fields

import scion.proposal.agentic_session_hypothesis as hypothesis_facade
from scion.core.models import (
    Decision,
    DecisionFeatures,
    EvalStats,
    ExperimentStage,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.agentic_session_hypothesis import (
    _hypothesis_preview_retry_feedback,
)
from scion.proposal.hypothesis_telemetry_retry import (
    expected_telemetry_retry_feedback,
)
from scion.proposal import agentic_session_hypothesis_schema_retry as schema_retry
from scion.proposal.engine import (
    _split_hypothesis_context,
    _split_hypothesis_target_intent_context,
)
from scion.proposal.target_intent_binding import (
    target_intent_binding_retry_feedback,
)
from scion.proposal.agentic_utils import _json_ready
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.tests.unit.agentic_session_test_support import *


class SequentialHypothesisCreative(FakeCreative):
    def __init__(self, hypotheses: list[HypothesisProposal]) -> None:
        super().__init__(hypothesis=hypotheses[-1])
        self.hypotheses = list(hypotheses)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.hypotheses:
            return self.hypothesis
        return self.hypotheses.pop(0)


class SequentialHypothesisToolClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.tool_names: list[str] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        del prompt, model, system_blocks, request_kind
        self.tool_names.append(tool["name"])
        if tool["name"] == "plan_proposal_tool_call":
            return {"intent": "stop"}
        if tool["name"] == "generate_hypothesis":
            if not self.payloads:
                raise AssertionError("generate_hypothesis called too many times")
            return self.payloads.pop(0)
        raise AssertionError(f"unexpected tool request: {tool['name']}")


def test_schema_retry_helpers_remain_importable_from_hypothesis_facade() -> None:
    helper_names = (
        "_schema_retry_preservation_drift",
        "_schema_retry_corrective_retry_already_used",
        "_same_mechanism_preview_retry_pending",
        "_schema_retry_drift_feedback",
        "_schema_retry_drift_failure_detail",
        "_schema_retry_protected_identity",
        "_hypothesis_retry_anchor",
        "_mechanism_ref_token",
        "_mechanism_ref_matches",
        "_mechanism_id_schema_retry_pending",
        "_launch_focus_required_mechanism_retry_pending",
    )

    for helper_name in helper_names:
        assert getattr(hypothesis_facade, helper_name) is getattr(
            schema_retry,
            helper_name,
        )


def test_schema_retry_identity_helpers_keep_existing_behavior() -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            target_file="policies/baseline_modules/local_search.py",
            expected_telemetry={
                "activation": [
                    "solver_algorithm_context_records.other_probe_iterations"
                ],
            },
        ),
        mechanism_changes=(
            MechanismChange(
                id="adaptive_vns_operator_weights",
                change_type="add",
            ),
        ),
    )
    preserve_hypothesis = {
        "action": "modify",
        "target_file": "policies/baseline_modules/local_search.py",
        "mechanism_changes": [
            {"id": "adaptive_vns_operator_weights", "change_type": "add"}
        ],
    }
    preview_rejections = [
        {
            "attempt": 1,
            "failure_code": "C11_expected_telemetry",
            "preserve_hypothesis": preserve_hypothesis,
        }
    ]

    assert hypothesis_facade._same_mechanism_preview_retry_pending(
        [{"failure_code": "same_mechanism_only_violation"}]
    )
    assert hypothesis_facade._mechanism_id_schema_retry_pending(
        [{"failure_code": "invalid_mechanism_id"}]
    )
    assert hypothesis_facade._mechanism_ref_token(
        "Adaptive-VNS-Operator-Weights_iterations"
    ) == "adaptive_vns_operator_weights"

    drift = hypothesis_facade._schema_retry_preservation_drift(
        hypothesis,
        preview_rejections,
        attempt=2,
    )

    assert drift is not None
    assert drift["failure_code"] == "schema_retry_drift"
    assert drift["drift_fields"] == ["expected_telemetry.activation"]
    feedback = hypothesis_facade._schema_retry_drift_feedback(
        drift,
        hypothesis,
        attempt=2,
    )
    assert feedback["corrective_retry"] is True
    assert "Do not explore" in feedback["retry_constraint"]


def test_schema_retry_ignores_structural_activation_counter_leaf_names() -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            target_file="operators/upgrade_pack.py",
            expected_telemetry={
                "activation": [
                    "operator_invocations",
                    "eligible_vehicle_or_order_groups_seen",
                    "accepted_moves",
                ],
            },
        ),
        mechanism_changes=(
            MechanismChange(
                id="same_subcategory_upgrade_merge",
                change_type="add",
            ),
        ),
    )
    preserve_hypothesis = {
        "action": "modify",
        "target_file": "operators/upgrade_pack.py",
        "mechanism_changes": [
            {"id": "same_subcategory_upgrade_merge", "change_type": "add"}
        ],
    }

    drift = hypothesis_facade._schema_retry_preservation_drift(
        hypothesis,
        [
            {
                "attempt": 1,
                "failure_code": "C11_expected_telemetry",
                "preserve_hypothesis": preserve_hypothesis,
            }
        ],
        attempt=2,
        structural_activation_refs={
            "operator_invocations",
            "eligible_vehicle_or_order_groups_seen",
            "accepted_moves",
        },
    )

    assert drift is None


def test_schema_retry_still_blocks_nested_activation_mechanism_drift() -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            target_file="operators/upgrade_pack.py",
            expected_telemetry={
                "activation": [
                    "operator_diagnostics.unrelated_repack.operator_invocations",
                    "operator_diagnostics.unrelated_repack.accepted_moves",
                ],
            },
        ),
        mechanism_changes=(
            MechanismChange(
                id="same_subcategory_upgrade_merge",
                change_type="add",
            ),
        ),
    )
    preserve_hypothesis = {
        "action": "modify",
        "target_file": "operators/upgrade_pack.py",
        "mechanism_changes": [
            {"id": "same_subcategory_upgrade_merge", "change_type": "add"}
        ],
    }

    drift = hypothesis_facade._schema_retry_preservation_drift(
        hypothesis,
        [
            {
                "attempt": 1,
                "failure_code": "C11_expected_telemetry",
                "preserve_hypothesis": preserve_hypothesis,
            }
        ],
        attempt=2,
        structural_activation_refs={
            "operator_diagnostics",
            "operator_invocations",
            "accepted_moves",
        },
    )

    assert drift is not None
    assert drift["drift_fields"] == ["expected_telemetry.activation"]
    assert drift["observed"]["expected_telemetry.activation"][
        "activation_mechanism_refs"
    ] == ["unrelated_repack"]


def test_target_intent_binding_retry_feedback_names_allowed_repair_paths() -> None:
    selected = {
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_modules/local_search.py",
        "mechanism_id": "adaptive_vns_operator_weights",
        "mechanism_family": "adaptive_vns_operator_weights",
    }
    drifted = replace(
        _vns_hypothesis(_good_vns_mechanism_telemetry()),
        action="create_new",
        target_file="policies/baseline_modules/destroy_repair.py",
        mechanism_changes=(
            MechanismChange(
                id="unrelated_search_gate",
                change_type="add",
            ),
        ),
    )

    feedback = target_intent_binding_retry_feedback(
        selected,
        drifted,
        attempt=1,
        manifest=None,
    )

    assert feedback is not None
    assert feedback["failure_code"] == "target_intent_binding_mismatch"
    assert feedback["allowed_repair_paths"] == [
        "preserve_selected_target_intent",
        "request_fresh_target_intent_reselection",
    ]
    assert "preserve selected_target_intent exactly" in feedback[
        "retry_constraint"
    ]
    assert "fresh target-intent selection" in feedback["retry_constraint"]
    assert "not drift mechanism, action, or target_file" in feedback[
        "retry_constraint"
    ]


def test_schema_retry_preserves_selected_target_intent_binding() -> None:
    selected = {
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_modules/local_search.py",
        "mechanism_id": "adaptive_vns_operator_weights",
        "mechanism_family": "adaptive_vns_operator_weights",
    }
    bound = _vns_hypothesis(_good_vns_mechanism_telemetry())
    drifted = replace(
        bound,
        action="create_new",
        target_file="policies/baseline_modules/destroy_repair.py",
        mechanism_changes=(
            MechanismChange(
                id="clustered_worst_removal",
                change_type="add",
            ),
        ),
    )
    binding_feedback = target_intent_binding_retry_feedback(
        selected,
        drifted,
        attempt=1,
        manifest=None,
    )
    assert binding_feedback is not None

    assert (
        hypothesis_facade._schema_retry_preservation_drift(
            bound,
            [binding_feedback],
            attempt=2,
        )
        is None
    )
    drift = hypothesis_facade._schema_retry_preservation_drift(
        drifted,
        [binding_feedback],
        attempt=2,
    )

    assert drift is not None
    assert drift["failure_code"] == "schema_retry_drift"
    assert drift["retry_failure_code"] == "target_intent_binding_mismatch"
    assert drift["drift_fields"] == ["action", "target_file", "mechanism_id"]
    assert drift["expected"]["target_file"] == selected["target_file"]
    assert drift["observed"]["target_file"] == drifted.target_file


def test_material_difference_requirement_is_first_class_in_manifest() -> None:
    requirement = {
        "schema_version": "proposal_material_difference_requirement.v1",
        "required": True,
        "record_type": "material_difference_requirement",
        "record_id": "material_difference_requirement:test123",
        "record_digest": "sha256:test123",
        "requirement_source": "low_value_clean_fork_pressure",
        "reason_codes": [
            "LOW_VALUE_CLEAN_FORK_PRESSURE",
            "CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE",
        ],
        "required_for": "clean_fork_new_branch",
        "candidate_branch_ids": ["retained-no-effect"],
        "candidate_release_reasons": [
            "retained_checkpoint_no_effect_current_head"
        ],
        "candidate_summaries": [
            {
                "branch_id": "retained-no-effect",
                "release_reason": (
                    "retained_checkpoint_no_effect_current_head"
                ),
            }
        ],
        "required_output_contract": (
            "The next hypothesis must include non-boilerplate material_difference."
        ),
        "decision_features_excluded": True,
    }
    context = {
        "problem_summary": "Generic combinatorial optimization problem.",
        "research_surfaces": "solver_design",
        "champion_operators_code": "def solve(): pass",
        "champion_stats": "champion v1",
        "active_problem_boundary_surfaces": "solver_design",
        "material_difference_requirement": requirement,
    }

    target_blocks, target_user = _split_hypothesis_target_intent_context(context)
    hypothesis_blocks, hypothesis_user = _split_hypothesis_context(context)
    target_text = "\n\n".join(
        str(block.get("text") or "") for block in target_blocks
    ) + target_user
    hypothesis_text = "\n\n".join(
        str(block.get("text") or "") for block in hypothesis_blocks
    ) + hypothesis_user

    assert "## Material Difference Requirement" in target_text
    assert "## Material Difference Requirement" in hypothesis_text
    assert "retained_checkpoint_no_effect_current_head" in target_text
    assert "retained_checkpoint_no_effect_current_head" in hypothesis_text
    assert "non-empty `material_difference` object" in hypothesis_user

    manifest = build_api_visible_prompt_manifest(
        session_id="session-material-difference",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=context,
        observations=[],
        call_index=1,
        system_blocks=hypothesis_blocks,
        user_prompt=hypothesis_user,
    )

    assert manifest["material_difference_requirement_visible"] is True
    assert manifest["material_difference_requirement_visible_count"] == 1
    assert (
        manifest["material_difference_requirement_source"]
        == "low_value_clean_fork_pressure"
    )
    requirement_ledger = manifest[
        "material_difference_requirement_visibility_ledger"
    ]
    assert requirement_ledger["record_id"] == (
        "material_difference_requirement:test123"
    )
    assert requirement_ledger["candidate_release_reason_count"] == 1
    assert any(
        entry.get("entry_kind") == "material_difference_requirement"
        and entry.get("visibility_status") == "full"
        for entry in manifest["visibility_ledger"]["entries"]
    )
    decision_fields = {field.name for field in fields(DecisionFeatures)}
    assert "material_difference_requirement" not in decision_fields
    assert "material_difference_requirement_visible" not in decision_fields


def _vns_hypothesis(expected_telemetry: dict) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "VNS local search uses fixed neighborhood ordering. Add a "
                "VNS-local adaptive neighborhood scheduler that learns from "
                "recent improvement success while preserving fleet_violation."
            ),
            target_weakness=(
                "The local-search phase does not adapt VNS neighborhood order "
                "from recent success."
            ),
            expected_effect=(
                "Improve total_distance by spending VNS effort on productive "
                "neighborhoods."
            ),
            no_op_condition=(
                "Fall back to fixed VNS ordering when the adaptive scheduler has "
                "no positive activation evidence."
            ),
            mechanism_changes=[
                {
                    "id": "adaptive_vns_operator_weights",
                    "change_type": "add",
                }
            ],
            novelty_signature={
                "algorithm_family": "adaptive_vns",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "adaptive_vns_neighborhood_ordering",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_vns_segments",
            },
            expected_telemetry=expected_telemetry,
        )
    )


def _local_search_mechanism_hypothesis(
    *,
    mechanism_id: str,
    text: str,
) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=text,
            target_weakness=(
                "Large CVRP cases need a targeted local-search mechanism with "
                "direct objective-effect telemetry."
            ),
            expected_effect=(
                "Improve total_distance on large cases while preserving fleet "
                "feasibility."
            ),
            no_op_condition="Skip when there is no remaining local-search budget.",
            mechanism_changes=[
                {
                    "id": mechanism_id,
                    "change_type": "modify",
                }
            ],
            novelty_signature={
                "algorithm_family": "bounded_local_search",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": mechanism_id,
                "acceptance_strategy": "strict_improvement_only",
                "runtime_budget_strategy": "deadline_aware_candidate_pool",
            },
            expected_telemetry={
                "activity": ["solver_algorithm_search_iterations"],
                "activation": [
                    f"solver_algorithm_context_records.{mechanism_id}_iterations",
                    f"solver_algorithm_phase_runtime_ms.{mechanism_id}",
                ],
                "effect": [
                    f"solver_algorithm_phase_improvement_counts.{mechanism_id}"
                ],
                "budget": [
                    f"solver_algorithm_phase_runtime_ms.{mechanism_id}"
                ],
            },
        )
    )


def _duplicate_or_opt_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "The active solver lacks inter-route Or-opt segment relocation; "
                "add an NN-filtered cross-route segment relocation neighborhood."
            ),
            target_weakness=(
                "The active solver lacks inter-route Or-opt segment relocation."
            ),
            expected_effect="Improve total_distance with a new cross-route Or-opt move.",
            mechanism_changes=[
                {"id": "cross_route_oropt", "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "vns_local_search",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "new_cross_route_oropt",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_neighbor_pairs",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )


def _targeted_multi_relocate_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "Add targeted_multi_relocate as a new local-search mechanism "
                "for high-cost customers."
            ),
            target_weakness="The active local search misses targeted multi relocate.",
            expected_effect="Improve total_distance with targeted relocations.",
            mechanism_changes=[
                {"id": "targeted_multi_relocate", "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "targeted_multi_relocate",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "targeted_multi_relocate",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_relocation_pairs",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )


def _failed_screening_step(hypothesis: HypothesisProposal) -> StepRecord:
    return StepRecord(
        round_num=4,
        branch_id="branch-cvrp",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=16,
                wins=0,
                losses=0,
                ties=16,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="/tmp/screening.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )


def _bad_vns_phase_telemetry() -> dict:
    return {
        "activity": ["solver_algorithm_search_iterations"],
        "activation": ["solver_algorithm_phase_runtime_ms.vns"],
        "effect": [
            "solver_algorithm_phase_improvement_counts."
            "adaptive_vns_operator_weights"
        ],
        "budget": [
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights"
        ],
    }


def _good_vns_mechanism_telemetry() -> dict:
    return {
        "activity": ["solver_algorithm_search_iterations"],
        "activation": [
            "solver_algorithm_context_records."
            "adaptive_vns_operator_weights_iterations",
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights",
        ],
        "effect": [
            "solver_algorithm_phase_improvement_counts."
            "adaptive_vns_operator_weights"
        ],
        "budget": [
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights"
        ],
    }


def _same_mechanism_context(tmp_path: Path) -> ProposalToolContext:
    context = _cvrp_context_with_champion(tmp_path)
    assert context.branch is not None
    context.branch.branch_code_status = "active_no_effect"
    context.branch.last_screening_feedback_tier = "no_effect"
    context.branch.last_telemetry_outcome = "no_objective_effect"
    context.branch.branch_mechanism_ids = ("adaptive_vns_operator_weights",)
    return context


def test_same_mechanism_schema_preview_retries_unrelated_mechanism_id(
    tmp_path: Path,
) -> None:
    context = _same_mechanism_context(tmp_path)
    bad = replace(
        _vns_hypothesis(_good_vns_mechanism_telemetry()),
        hypothesis_text=(
            "Add an unrelated restart mechanism on a same-mechanism follow-up "
            "branch."
        ),
        mechanism_changes=(
            MechanismChange(id="unrelated_restart", change_type="add"),
        ),
    )
    registry = ProposalToolRegistry.default_read_only()

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _json_ready(bad)},
        context,
    )
    feedback = _hypothesis_preview_retry_feedback(
        [preview],
        detail="schema or target preview did not pass",
        attempt=1,
        previous_hypothesis=bad,
    )

    payload = preview.structured_payload["hypothesis"]
    guard = payload["branch_continuation_guard"]
    assert preview.structured_payload["passed"] is False
    assert guard["failure_code"] == "same_mechanism_only_violation"
    assert guard["hypothesis_generation_mode"] == "same_mechanism_only"
    assert guard["protected_mechanism_ids"] == ["adaptive_vns_operator_weights"]
    assert guard["proposed_mechanism_ids"] == ["unrelated_restart"]
    assert feedback is not None
    assert feedback["failure_code"] == "same_mechanism_only_violation"
    assert feedback["protected_mechanism_ids"] == [
        "adaptive_vns_operator_weights"
    ]
    assert guard["candidate_routing"] == "new_mechanism_requires_clean_fork_signal"
    assert guard["clean_fork_signal"] is True
    assert "not_a_code_or_screening_failure" in guard["proposal_failure_accounting"]
    assert feedback["candidate_routing"] == "new_mechanism_requires_clean_fork_signal"
    assert feedback["clean_fork_signal"] is True
    assert "not_a_code_or_screening_failure" in feedback[
        "proposal_failure_accounting"
    ]
    assert "clean branch/fork" in feedback["retry_constraint"]
    assert "unrelated_restart" in feedback["reason"]


def test_same_mechanism_schema_preview_allows_protected_tune_or_repair(
    tmp_path: Path,
) -> None:
    context = _same_mechanism_context(tmp_path)
    protected = replace(
        _vns_hypothesis(_good_vns_mechanism_telemetry()),
        hypothesis_text=(
            "Tune and repair adaptive_vns_operator_weights without adding a "
            "new mechanism."
        ),
        mechanism_changes=(
            MechanismChange(
                id="adaptive_vns_operator_weights",
                change_type="modify",
            ),
        ),
    )
    registry = ProposalToolRegistry.default_read_only()

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _json_ready(protected)},
        context,
    )

    guard = preview.structured_payload["hypothesis"]["branch_continuation_guard"]
    assert preview.structured_payload["passed"] is True
    assert guard["passed"] is True
    assert guard["protected_mechanism_ids"] == ["adaptive_vns_operator_weights"]


def test_same_mechanism_preview_retry_happens_inside_proposal_session(
    tmp_path: Path,
) -> None:
    bad = HypothesisProposal(
        **_valid_hypothesis_payload(
            hypothesis_text=(
                "Add an unrelated restart mechanism on a non-clean follow-up "
                "branch."
            ),
            target_weakness="The budget policy needs a different mechanism.",
            expected_effect="Improve distance through unrelated restart logic.",
        ),
        mechanism_changes=(
            MechanismChange(id="unrelated_restart", change_type="add"),
        ),
    )
    good = HypothesisProposal(
        **_valid_hypothesis_payload(
            hypothesis_text=(
                "Tune protected_budget_policy on the same non-clean branch."
            ),
            target_weakness="The protected budget policy needs parameter tuning.",
            expected_effect=(
                "Improve runtime tradeoff by tuning the same protected policy."
            ),
        ),
        mechanism_changes=(
            MechanismChange(id="protected_budget_policy", change_type="modify"),
        ),
    )
    creative = SequentialHypothesisCreative([bad, good])
    context = _context(tmp_path, policy=_tool_enabled_policy())
    assert context.branch is not None
    context.branch.branch_code_status = "active_no_effect"
    context.branch.last_screening_feedback_tier = "no_effect"
    context.branch.last_telemetry_outcome = "no_objective_effect"
    context.branch.branch_mechanism_ids = ("protected_budget_policy",)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-same-mechanism-preview-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "same-mechanism-preview-retry"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == good
    assert len(creative.hypothesis_contexts) == 2
    retry_feedback = creative.hypothesis_contexts[1][
        "agentic_hypothesis_preview_rejections"
    ][0]
    assert retry_feedback["failure_code"] == "same_mechanism_only_violation"
    assert retry_feedback["hypothesis_generation_mode"] == "same_mechanism_only"
    assert retry_feedback["protected_mechanism_ids"] == [
        "protected_budget_policy"
    ]
    assert "SAME-MECHANISM BRANCH RETRY" in creative.hypothesis_contexts[1][
        "agentic_hypothesis_preview_retry_rule"
    ]
    assert not any(
        event.metadata.get("failure_code") == "new_mechanism_requires_clean_fork"
        for event in output.transcript
    )


def test_launch_focus_required_mechanism_preview_retries_to_required_id(
    tmp_path: Path,
) -> None:
    required_id = "large_instance_intra_route_two_opt_seed"
    bad = _local_search_mechanism_hypothesis(
        mechanism_id="bounded_two_opt_probe",
        text="Add a bounded two-opt probe that is not the prepared launch focus.",
    )
    good = _local_search_mechanism_hypothesis(
        mechanism_id=required_id,
        text=(
            "Implement the prepared large-instance intra-route two-opt seed "
            "inside local_search.py."
        ),
    )
    creative = SequentialHypothesisCreative([bad, good])
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
        launch_research_focus={
            "research_focus": {
                "required_mechanism_ids": [required_id],
            },
        },
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-launch-focus-required-mechanism-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "launch-focus-required-mechanism"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == good
    assert len(creative.hypothesis_contexts) == 2
    retry_context = creative.hypothesis_contexts[1]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert (
        retry_feedback["failure_code"]
        == "launch_research_focus_required_mechanism"
    )
    assert retry_feedback["required_mechanism_ids"] == [required_id]
    assert retry_feedback["candidate_mechanism_ids"] == ["bounded_two_opt_probe"]
    assert retry_feedback["allowed_repair_shape"]["mechanism_changes"] == [
        {"id": required_id, "change_type": "modify"}
    ]
    assert "LAUNCH-FOCUS REQUIRED-MECHANISM RETRY" in retry_context[
        "agentic_hypothesis_preview_retry_rule"
    ]


def test_same_branch_target_intent_and_formal_prompts_route_new_mechanisms_to_clean_fork(
) -> None:
    branch_hygiene = (
        "branch_followup_policy=same_mechanism_followup_only; "
        "hypothesis_generation_mode=same_mechanism_only; "
        "protected_mechanism_ids=protected_budget_policy; "
        "same_mechanism_allowed_actions=tune, integrate, repair, parameterize, telemetry_wiring; "
        "forbidden_mechanism_policy=no_unrelated_mechanism_ids; "
        "clean_fork_policy=clean_fork_required_for_new_mechanism"
    )
    context = {
        "problem_summary": "CVRP.",
        "research_surfaces": "solver_design",
        "champion_operators_code": "# code",
        "champion_stats": "stats",
        "active_problem_boundary_surfaces": "solver_design",
        "targetable_files": "policies/baseline_modules/destroy_repair.py",
        "branch_hygiene_guidance": branch_hygiene,
        "branch_followup_policy": "same_mechanism_followup_only",
        "agentic_hypothesis_target_intent": {
            "intent": {
                "change_locus": "solver_design",
                "action": "modify",
                "target_file": "policies/baseline_modules/destroy_repair.py",
                "mechanism_id": "protected_budget_policy",
                "mechanism_family": "protected_budget_policy",
            }
        },
    }

    target_blocks, target_user = _split_hypothesis_target_intent_context(context)
    formal_blocks, formal_user = _split_hypothesis_context(context)
    target_rendered = "\n".join(block["text"] for block in target_blocks) + target_user
    formal_rendered = "\n".join(block["text"] for block in formal_blocks) + formal_user

    for rendered in (target_rendered, formal_rendered):
        assert "Same-Mechanism Follow-up Constraints" in rendered
        assert "protected_mechanism_ids=protected_budget_policy" in rendered
        assert "clean_fork_required_for_new_mechanism" in rendered
        assert "A new or unrelated mechanism requires a clean branch or clean fork" in rendered
    assert "same-mechanism only" in target_user
    assert "clean branch/fork signal" in target_user
    assert "Selected target-intent binding" in formal_user
    assert "Set `target_file` to selected intent value" in formal_user


def test_hypothesis_preview_c11_feedback_retries_to_corrected_hypothesis(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([bad, bad, good])
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-preview-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.hypothesis == good
    assert output.self_check.schema_valid is True
    assert len(creative.hypothesis_contexts) == 3
    assert "agentic_hypothesis_grounding_rejections" in creative.hypothesis_contexts[1]
    retry_context = creative.hypothesis_contexts[2]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert retry_feedback["failure_code"] == "C11_expected_telemetry"
    assert retry_feedback["attempt_kind"] == "schema_accounting_repair"
    assert (
        retry_feedback["repair_classification"]
        == "telemetry_schema_accounting_repair"
    )
    assert "solver_algorithm_phase_runtime_ms.vns" in json.dumps(retry_feedback)
    assert "Repair only expected_telemetry/schema fields" in retry_feedback[
        "retry_constraint"
    ]
    assert "schema/accounting repair" in retry_feedback["retry_constraint"]
    assert "switch mechanisms or targets" in retry_feedback["retry_constraint"]
    assert "declared_runtime_fields" not in retry_feedback
    assert "declared_mechanism_runtime_fields" not in retry_feedback
    assert retry_feedback["exact_allowed_top_level_categories"] == [
        "activation",
        "activity",
        "budget",
        "effect",
    ]
    assert retry_feedback["declared_mechanism_ids"] == [
        "adaptive_vns_operator_weights"
    ]
    assert retry_feedback["protected_mechanism_ids"] == [
        "adaptive_vns_operator_weights"
    ]
    assert (
        "broad aggregate phase"
        in retry_feedback["legal_mechanism_id_policy"]
    )
    assert retry_feedback["allowed_expected_telemetry_template"][
        "template_truncated"
    ] is False
    assert retry_feedback["allowed_expected_telemetry_template"][
        "mechanism_ids"
    ] == ["adaptive_vns_operator_weights"]
    assert retry_feedback["allowed_expected_telemetry_template"][
        "expected_telemetry"
    ]["activation"] == [
        "solver_algorithm_context_records.adaptive_vns_operator_weights_iterations",
        "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights",
    ]
    assert retry_feedback["preserve_hypothesis"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert retry_feedback["preserve_hypothesis"]["mechanism_changes"] == [
        {"id": "adaptive_vns_operator_weights", "change_type": "add"}
    ]
    assert any(
        event.metadata.get("failure_code") == "C11_expected_telemetry"
        for event in output.transcript
    )
    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in ref
    ]
    retry_manifests = [
        manifest
        for manifest in manifests
        if manifest.get("call_kind") == "hypothesis_preview_retry"
    ]
    assert retry_manifests
    retry_manifest = retry_manifests[0]
    feedback_status = retry_manifest["section_statuses"][
        "hypothesis_schema_telemetry_retry_feedback"
    ]
    assert feedback_status["status"] == "included"
    assert "hypothesis_schema_telemetry_retry_feedback" not in retry_manifest[
        "truncated_sections"
    ]
    feedback_refs = [
        ref
        for ref in output.tainted_artifact_refs
        if "hypothesis_schema_retry_feedback" in ref
    ]
    assert feedback_refs
    feedback_artifact = json.loads(Path(feedback_refs[0]).read_text(encoding="utf-8"))
    assert feedback_artifact["feedback"]["allowed_expected_telemetry_template_full"][
        "expected_telemetry"
    ]["activation"] == retry_feedback["allowed_expected_telemetry_template_full"][
        "expected_telemetry"
    ]["activation"]
    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    assert artifact["schema_retry_feedback_artifact_refs"]
    assert artifact["schema_retry_feedback_artifact_refs"][0].endswith(
        "hypothesis_schema_retry_feedback_0002.json"
    )
    assert any(
        event.get("metadata", {}).get("schema_retry_feedback_ref")
        in feedback_refs
        for event in artifact["compact_transcript"]
    )


def test_hypothesis_preview_c11_feedback_can_clear_unsupported_telemetry() -> None:
    feedback = expected_telemetry_retry_feedback(
        {
            "branch_continuation_guard": {},
        },
        {
            "passed": False,
            "detail_full": (
                "research surface 'solver_design' does not declare telemetry "
                "fields in surface.evidence"
            ),
            "requested_fields": {
                "activation": ["solver_algorithm_phase_runtime_ms.vns"],
            },
            "exact_allowed_top_level_categories": [
                "activation",
                "activity",
                "budget",
                "effect",
            ],
            "declared_mechanism_ids": ["adaptive_vns_operator_weights"],
            "allowed_expected_telemetry_template": {
                "selected_surface": "solver_design",
                "expected_telemetry": {},
                "template_is_exact": True,
                "template_truncated": False,
            },
        },
        {},
        detail="schema or target preview did not pass: C11_expected_telemetry",
        attempt=1,
        c11_detail="C11_expected_telemetry",
        telemetry_detail=(
            "research surface 'solver_design' does not declare telemetry "
            "fields in surface.evidence"
        ),
        preserve_hypothesis={
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_changes": [
                {"id": "adaptive_vns_operator_weights", "change_type": "add"}
            ],
        },
        protected_identity={
            "target_file": "policies/baseline_modules/local_search.py",
            "protected_mechanism_ids": ["adaptive_vns_operator_weights"],
        },
    )

    assert feedback["failure_code"] == "C11_expected_telemetry"
    assert feedback["unsupported_expected_telemetry"] is True
    assert feedback["clear_expected_telemetry_allowed"] is True
    assert feedback["allowed_repair_shape"]["expected_telemetry"] == {}
    assert "set expected_telemetry to {}" in feedback["retry_constraint"]


def test_existing_file_create_new_preview_feedback_preempts_c11(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)
    bad = replace(
        _vns_hypothesis(_bad_vns_phase_telemetry()),
        action="create_new",
        target_file="policies/baseline_modules/local_search.py",
    )

    schema_preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _json_ready(bad)},
        context,
    )
    permission_preview = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": bad.change_locus,
            "action": bad.action,
            "target_file": bad.target_file,
        },
        context,
    )
    feedback = _hypothesis_preview_retry_feedback(
        [schema_preview, permission_preview],
        detail="schema or target preview did not pass: C11_expected_telemetry",
        attempt=1,
        previous_hypothesis=bad,
    )

    payload = schema_preview.structured_payload["hypothesis"]
    assert schema_preview.structured_payload["passed"] is False
    assert payload["target_action_guard"]["reason"] == (
        "existing_file_create_new_rejected"
    )
    assert payload["expected_telemetry_contract"]["passed"] is False
    assert any(
        check["name"] == "C11_expected_telemetry"
        and check["passed"] is False
        for check in payload["checks"]
    )
    assert feedback is not None
    assert feedback["failure_code"] == "existing_file_create_new_rejected"
    assert feedback["source"] == "hypothesis_preview_target_action_guard"
    assert feedback["attempt_kind"] == "target_action_permission_repair"
    assert feedback["requested_action"] == "create_new"
    assert feedback["required_action"] == "modify"
    assert feedback["allowed_file_action"]["action"] == "modify"
    assert feedback["allowed_file_action"]["edit_intent"] == "exact_replace"
    assert feedback["source_digest"]
    assert feedback["preserve_hypothesis"]["action"] == "modify"
    assert feedback["preserve_hypothesis"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert feedback["protected_identity"].get("action") != "create_new"
    assert "Do not preserve the invalid file-level action=create_new" in (
        feedback["retry_constraint"]
    )
    assert "Mechanism-level wording may say add or integrate" in (
        feedback["retry_constraint"]
    )

    repaired = replace(bad, action="modify")
    assert (
        hypothesis_facade._schema_retry_preservation_drift(
            repaired,
            [feedback],
            attempt=2,
        )
        is None
    )
    still_invalid = hypothesis_facade._schema_retry_preservation_drift(
        bad,
        [feedback],
        attempt=2,
    )
    assert still_invalid is not None
    assert still_invalid["drift_fields"] == ["action"]


def test_hypothesis_preview_c10_missing_fields_feedback_uses_repair_template(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)
    bad = _vns_hypothesis(_good_vns_mechanism_telemetry())
    bad = replace(
        bad,
        novelty_signature={
            "algorithm_family": "adaptive_vns",
            "improvement_strategy": "adaptive_vns_neighborhood_ordering",
        },
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _json_ready(bad)},
        context,
    )
    feedback = _hypothesis_preview_retry_feedback(
        [preview],
        detail="schema or target preview did not pass",
        attempt=2,
        previous_hypothesis=bad,
    )

    assert preview.structured_payload["passed"] is False
    assert feedback is not None
    assert feedback["failure_code"] == "novelty_signature_missing_fields"
    assert feedback["check"] == "C10_novelty"
    assert feedback["missing_fields"] == [
        "construction_strategy",
        "acceptance_strategy",
        "runtime_budget_strategy",
    ]
    assert feedback["repair_template"]["repair_type"] == (
        "novelty_signature_missing_fields"
    )
    assert feedback["required_template"]["novelty_signature"]["mechanism_id"] == (
        "adaptive_vns_operator_weights"
    )
    assert "active solver map" in feedback["retry_constraint"]
    assert feedback["protected_identity"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    rendered = json.dumps(feedback, sort_keys=True)
    assert "raw_metrics" not in rendered
    assert "validation" not in rendered.lower()
    assert "frozen" not in rendered.lower()


def test_hypothesis_preview_c11_retry_allows_runtime_free_text_rewrite(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    rewritten = replace(
        good,
        hypothesis_text=(
            good.hypothesis_text
            + " The schema retry restates the runtime expectation more compactly."
        ),
        expected_effect=(
            "Improve total_distance by using the same adaptive VNS mechanism "
            "with clearer telemetry declarations."
        ),
        target_runtime_effect=(
            "Shift VNS time toward recently productive existing neighborhoods "
            "within the same bounded local-search budget."
        ),
        novelty_signature={
            **dict(good.novelty_signature or {}),
            "algorithm_family": (
                "adaptive neighborhood policy for the same VNS operator set"
            ),
            "construction_strategy": (
                "leave construction unchanged while restating the schema repair"
            ),
            "improvement_strategy": (
                "sliding-window success-rate reordering of neighborhood "
                "operators per pass"
            ),
            "acceptance_strategy": (
                "keep the incumbent acceptance rule unchanged"
            ),
            "runtime_budget_strategy": (
                "bounded_existing_vns_operator_reordering_with_schema_valid_telemetry"
            ),
        },
    )
    creative = SequentialHypothesisCreative([bad, bad, rewritten])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-free-text-allowed",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-free-text"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == rewritten
    assert output.self_check.schema_valid is True
    assert not any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_blocks_mechanism_target_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/scheduler.py",
            hypothesis_text=(
                "After schema retry, switch to a scheduler restart mechanism "
                "instead of repairing the prior VNS telemetry declaration."
            ),
            target_weakness="Scheduler restart cadence is fixed.",
            expected_effect="Improve total_distance through restart perturbations.",
            no_op_condition="Keep the existing scheduler when no restart evidence appears.",
            mechanism_changes=[
                {
                    "id": "adaptive_scheduler_restart",
                    "change_type": "add",
                }
            ],
            novelty_signature={
                "algorithm_family": "adaptive_scheduler_restart",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "restart_after_stagnation",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_restart_checks",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )
    creative = SequentialHypothesisCreative([bad, bad, drifted])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-drift-block",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-drift"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert creative.code_contexts == []
    assert len(creative.hypothesis_contexts) == 4
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema_retry_drift" in output.failure_detail
    assert "target_file" in output.failure_detail
    assert "mechanism_changes" in output.failure_detail
    assert output.failure_ledger["entries"][-1]["failure_code"] == "schema_retry_drift"
    assert any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        and event.metadata.get("corrective_retry") is True
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_corrects_identity_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted = replace(
        _vns_hypothesis(_good_vns_mechanism_telemetry()),
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(
            MechanismChange(id="or_opt1_nn", change_type="add"),
        ),
    )
    restored = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([bad, bad, drifted, restored])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-drift-corrective-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-drift-corrective"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == restored
    assert len(creative.hypothesis_contexts) == 4
    corrective_context = creative.hypothesis_contexts[3]
    drift_feedback = corrective_context["agentic_hypothesis_preview_rejections"][-1]
    assert drift_feedback["failure_code"] == "schema_retry_drift"
    assert drift_feedback["corrective_retry"] is True
    assert drift_feedback["protected_identity"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert drift_feedback["protected_identity"]["protected_mechanism_ids"] == [
        "adaptive_vns_operator_weights"
    ]
    assert output.failure_detail == "hypothesis awaits ContractGate approval"
    assert any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        and event.metadata.get("corrective_retry") is True
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_blocks_activation_mechanism_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted_telemetry = _good_vns_mechanism_telemetry()
    drifted_telemetry["activation"] = [
        "solver_algorithm_context_records.nn_relocate_iterations",
        "solver_algorithm_phase_runtime_ms.nn_relocate",
    ]
    drifted = replace(
        _vns_hypothesis(drifted_telemetry),
        target_runtime_effect=(
            "Keep the same prose, but incorrectly point activation telemetry "
            "at a different mechanism."
        ),
    )
    creative = SequentialHypothesisCreative([bad, bad, drifted])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-activation-drift",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-activation-drift"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert creative.code_contexts == []
    assert len(creative.hypothesis_contexts) == 4
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema_retry_drift" in output.failure_detail
    assert "expected_telemetry.activation" in output.failure_detail
    assert output.failure_ledger["entries"][-1]["failure_code"] == "schema_retry_drift"


def test_hypothesis_text_survives_preview_failure_artifact_serialization(
    tmp_path: Path,
) -> None:
    hypothesis_text = (
        "The current simulated annealing acceptance cools monotonically, and "
        "the search can become trapped behind a frozen SA temperature after "
        "early improvements. Add a bounded stagnation-triggered reheat so the "
        "acceptance probability can recover without changing feasibility "
        "checks or the operator portfolio."
    )
    bad_payload = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/acceptance.py",
        hypothesis_text=hypothesis_text,
        target_weakness=(
            "The acceptance temperature can freeze before late search "
            "diversification is useful."
        ),
        expected_effect="Improve total_distance by escaping late local optima.",
        mechanism_changes=[{"id": "sa_reheat", "change_type": "add"}],
        novelty_signature={
            "algorithm_family": "alns_with_sa_reheat",
            "construction_strategy": "preserve_existing_construction",
            "improvement_strategy": "preserve_existing_vns_portfolio",
            "acceptance_strategy": "stagnation_triggered_sa_reheat",
            "runtime_budget_strategy": "bounded_reheat_checks",
        },
        expected_telemetry={
            "activity": ["solver_algorithm_search_iterations"],
            "activation": {
                "sa_reheat": [
                    "solver_algorithm_accepted_moves",
                    "solver_algorithm_neutral_accepted_moves",
                ]
            },
            "effect": ["solver_algorithm_best_delta"],
            "budget": ["solver_algorithm_elapsed_ms"],
        },
    )
    client = SequentialHypothesisToolClient(
        [bad_payload, dict(bad_payload), dict(bad_payload)]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-text-handoff",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "hypothesis-text-handoff"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    rendered_codes = json.dumps(output.self_check.schema_preview_codes)
    ledger_entry = artifact["failure_ledger"]["entries"][0]

    assert output.status == AgenticProposalStatus.FAILED
    assert output.hypothesis is not None
    assert output.hypothesis.hypothesis_text == hypothesis_text
    assert artifact["hypothesis"]["hypothesis_text"] == hypothesis_text
    assert "frozen SA temperature" in artifact["hypothesis"]["hypothesis_text"]
    assert "C11_expected_telemetry" in (output.failure_detail or "")
    assert "hypothesis_text" not in rendered_codes
    assert ledger_entry["category"] == "schema_output_failure"
    assert "C11_expected_telemetry" in ledger_entry["detail"]
    assert "hypothesis_text" not in ledger_entry["detail"]


def test_mechanism_premise_warning_then_c11_retry_drift_fails_closed(
    tmp_path: Path,
) -> None:
    duplicate = _duplicate_or_opt_hypothesis()
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([duplicate, duplicate, bad, good])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-semantic-then-c11-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "semantic-then-preview"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED
    )
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema_retry_drift" in output.failure_detail
    assert "agent_grounding_failure" not in output.failure_detail
    assert output.hypothesis is None
    assert output.self_check.schema_valid is False
    assert len(creative.hypothesis_contexts) == 4
    assert all(
        "agentic_hypothesis_semantic_rejections" not in context
        for context in creative.hypothesis_contexts
    )
    preview_feedback = creative.hypothesis_contexts[2][
        "agentic_hypothesis_preview_rejections"
    ][0]
    assert preview_feedback["failure_code"] == "C11_expected_telemetry"
    assert "cross_route_oropt" in json.dumps(preview_feedback)
    drift_feedback = creative.hypothesis_contexts[3][
        "agentic_hypothesis_preview_rejections"
    ][-1]
    assert drift_feedback["failure_code"] == "schema_retry_drift"

    transcript = output.transcript
    assert any(
        event.metadata.get("diagnostic_kind") == "mechanism_premise_warning"
        and event.metadata.get("diagnostic", {}).get("quality_block") is False
        and event.metadata.get("diagnostic", {}).get("blocking") is False
        for event in transcript
    )
    assert any(
        event.metadata.get("tool_name") == "proposal.schema_preview"
        and event.metadata.get("status") == "ok"
        and "C11_expected_telemetry" in event.metadata.get("result_summary", "")
        for event in transcript
    )
    assert any(
        "Hypothesis preview gate rejected hypothesis" in event.message
        and event.metadata.get("failure_code") == "C11_expected_telemetry"
        for event in transcript
    )
    assert any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        for event in transcript
    )


def test_repeated_mechanism_enters_transcript_as_duplicate_diagnostic(
    tmp_path: Path,
) -> None:
    repeat = _targeted_multi_relocate_hypothesis()
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([repeat, repeat, good])
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(
        context,
        policy=ContextExposurePolicy(),
        step_history=(_failed_screening_step(repeat),),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-repeated-mechanism-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "repeated-mechanism"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == repeat
    assert len(creative.hypothesis_contexts) == 2
    assert all(
        "agentic_hypothesis_semantic_rejections" not in context
        for context in creative.hypothesis_contexts
    )
    duplicate_events = [
        event
        for event in output.transcript
        if event.metadata.get("result_kind") == "duplicate_diagnostic"
    ]
    assert duplicate_events
    assert duplicate_events[-1].metadata["failure_category"] == "repeated_mechanism"
    assert duplicate_events[-1].metadata["mechanism"] == "targeted_multi_relocate"
    assert "SCREENING_FAIL_WIN_RATE" in duplicate_events[-1].metadata["reason"]


def test_hypothesis_preview_c11_retry_exhaustion_fails_with_clear_detail(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    creative = SequentialHypothesisCreative([bad, bad])
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        artifact_store=artifact_store,
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-preview-exhausted",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-exhausted"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert creative.code_contexts == []
    assert len(creative.hypothesis_contexts) == 3
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "C11_expected_telemetry" in output.failure_detail
    assert "solver_algorithm_phase_runtime_ms.vns" in output.failure_detail
    assert output.self_check.schema_valid is False
    assert output.failure_ledger["latest_failure"] == "schema_output_failure"
    ledger_entry = output.failure_ledger["entries"][-1]
    assert ledger_entry["failure_code"] == "C11_expected_telemetry"
    assert ledger_entry["diagnostic_ref"]
    diagnostic = ledger_entry["diagnostic_payload"]
    assert diagnostic["failure_code"] == "C11_expected_telemetry"
    assert diagnostic["reason_full"]
    assert diagnostic["offending_fields_full"]
    assert diagnostic["allowed_expected_telemetry_template_full"][
        "template_truncated"
    ] is False
    assert diagnostic["allowed_expected_telemetry_template_full"][
        "expected_telemetry"
    ]["activation"] == [
        "solver_algorithm_context_records.adaptive_vns_operator_weights_iterations",
        "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights",
    ]
    self_check_c11 = output.self_check.diagnostics["C11_expected_telemetry"]
    assert output.self_check.schema_preview_full_refs
    assert set(self_check_c11["preview_full_refs"]).issubset(
        set(output.self_check.schema_preview_full_refs)
    )
    assert self_check_c11["expected_telemetry_contract"][
        "allowed_expected_telemetry_template"
    ]["template_truncated"] is False
    full_ref = next(
        ref for ref in output.tainted_artifact_refs if "self_check_preview_full" in ref
    )
    full_payload = json.loads(Path(full_ref).read_text(encoding="utf-8"))
    assert full_payload["structured_payload_full"]["hypothesis"][
        "expected_telemetry_contract"
    ]["allowed_expected_telemetry_template"]["template_truncated"] is False
    retry_payload = json.loads(
        Path(ledger_entry["diagnostic_ref"]).read_text(encoding="utf-8")
    )
    assert retry_payload["feedback"]["offending_fields_full"]


def test_non_repairable_target_preview_failure_fails_closed(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            target_file="policies/not_declared.py",
        )
    )
    creative = SequentialHypothesisCreative([hypothesis])
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-fail-closed",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-fail-closed"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert creative.code_contexts == []
    assert len(creative.hypothesis_contexts) == 1
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema or target preview did not pass" in output.failure_detail
    assert "C11_expected_telemetry" not in output.failure_detail
