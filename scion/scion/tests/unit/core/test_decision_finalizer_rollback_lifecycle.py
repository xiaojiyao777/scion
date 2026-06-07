from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
    SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
)
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.models import (
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.scheduler import Scheduler
from scion.tests.unit.core.decision_finalizer_lifecycle_test_support import (
    _HypothesisStore,
)


def test_regressed_followup_does_not_remain_active_weak_positive() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    branch.direction = "repair: established weak-positive checkpoint"
    branch.current_code_hash = "regressed-head"
    branch.last_clean_code_hash = "regressed-head"
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.branch_mechanism_ids = ("repair_ordering",)
    hypothesis = HypothesisProposal(
        hypothesis_text="Follow up on the same generic mechanism.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-5",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="operators/followup.py",
        action="modify",
        code_content="# regressed candidate\n",
    )
    previous_patch = PatchProposal(
        file_path="operators/checkpoint.py",
        action="modify",
        code_content="# checkpoint\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hyp_store = _HypothesisStore()
    discarded: list[str] = []
    restored: list[str] = []

    def restore_checkpoint(restored_branch):
        restored.append(restored_branch.branch_id)
        restored_branch.current_code_hash = "best-screened-checkpoint"
        restored_branch.last_clean_code_hash = "best-screened-checkpoint"
        restored_branch.branch_code_status = "active_weak_positive"
        restored_branch.last_screening_feedback_tier = "weak_positive"
        restored_branch.last_telemetry_outcome = "case_level_positive_signal"
        patches[restored_branch.branch_id] = previous_patch
        return True

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches=patches,
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
        restore_branch_checkpoint=restore_checkpoint,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=1,
            losses=5,
            ties=6,
            win_rate=1 / 12,
            median_delta=0.0,
            ci_low=-4.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
            runtime_pairs=12,
            valid_pairs=12,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="loss-heavy follow-up",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
            SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
            SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
        ),
        lifecycle_action="rollback_to_checkpoint",
    )

    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert restored == [branch.branch_id]
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert stored.last_telemetry_outcome == "case_level_positive_signal"
    assert stored.current_code_hash == "best-screened-checkpoint"
    assert stored.last_clean_code_hash == "best-screened-checkpoint"
    assert stored.rollback_count == 1
    assert stored.last_rollback_reason == "rollback_to_checkpoint"
    assert patches[branch.branch_id] is previous_patch
    assert discarded == []
    assert action.slot == "exploit_weak_positive"
