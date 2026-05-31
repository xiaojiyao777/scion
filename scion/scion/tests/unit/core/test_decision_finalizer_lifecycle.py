from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    SCREENING_MARGINAL_SIGNAL_CONTINUE,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
    SCREENING_WEAK_SIGNAL_CONTINUE,
)
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.models import (
    BranchState,
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
from scion.core.runtime_budget_diagnostics import SCREENING_RUNTIME_BUDGET_SATURATION
from scion.core.scheduler import Scheduler
from scion.core.telemetry_validation import (
    TELEMETRY_VALIDATION_REPAIRABLE,
    VALIDATION_TELEMETRY_REPAIRABLE,
)


class _HypothesisStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str]] = []

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        self.statuses.append((hypothesis_id, status))


def test_continue_explore_preserves_non_regressive_neutral_screening_workspace() -> None:
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
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-1",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    zero_win_streaks: dict[str, int] = {}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
        branch_zero_win_streaks=zero_win_streaks,
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
    )

    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            valid_pairs=8,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="all ties",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_surface_runtime_summary={
            "runtime_budget_diagnostic": {
                "schema": "scion.runtime_budget_diagnostic.v1",
                "code": SCREENING_RUNTIME_BUDGET_SATURATION,
                "stage": "screening",
                "severity": "warn",
                "repairable": True,
            },
        },
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
            SCREENING_RUNTIME_BUDGET_SATURATION,
            SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        ),
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.counts_toward_max_rounds is True
    assert result.attempt_kind == "screening"
    assert "weak screening signal" in result.reason
    assert "runtime_budget_diagnostic=SCREENING_RUNTIME_BUDGET_SATURATION" in (
        result.reason
    )
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert patches[branch.branch_id] is patch
    assert discarded == []
    assert zero_win_streaks[branch.branch_id] == 1
    assert controller.get_branch(branch.branch_id).direction is not None
    assert controller.get_branch(branch.branch_id).branch_code_status == (
        "active_no_effect"
    )
    assert controller.get_branch(branch.branch_id).last_screening_feedback_tier == (
        "no_effect"
    )
    assert controller.get_branch(branch.branch_id).last_telemetry_outcome == (
        "no_objective_effect"
    )
    assert hyp_store.statuses == [("h-1", "screening_no_effect")]


def test_balanced_mixed_screening_workspace_is_marginal_not_weak_exploit() -> None:
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
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-marginal",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    zero_win_streaks: dict[str, int] = {}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
        branch_zero_win_streaks=zero_win_streaks,
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
    )

    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=3,
            losses=3,
            ties=6,
            win_rate=0.25,
            median_delta=0.0,
            ci_low=-0.5,
            ci_high=0.5,
            candidate_failed_pairs=0,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="balanced mixed follow-up",
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
            SCREENING_MARGINAL_SIGNAL_CONTINUE,
        ),
    )

    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "marginal mixed screening signal" in result.reason
    assert stored.branch_code_status == "active_marginal"
    assert stored.last_screening_feedback_tier == "marginal"
    assert discarded == []
    assert action.slot == "refine_active"
    assert hyp_store.statuses == [
        ("h-marginal", "screening_marginal_retained")
    ]


def test_continue_explore_discards_candidate_failed_screening_workspace() -> None:
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
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-2",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    zero_win_streaks: dict[str, int] = {}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
        branch_zero_win_streaks=zero_win_streaks,
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
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=10,
            wins=4,
            losses=0,
            ties=6,
            win_rate=0.4,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            valid_pairs=10,
            candidate_failed_pairs=1,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="candidate runtime failure",
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
            SCREENING_WEAK_SIGNAL_CONTINUE,
        ),
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.attempt_kind == "screening"
    assert discarded == [branch.branch_id]
    assert controller.get_branch(branch.branch_id).branch_code_status == "discarded"
    assert controller.get_branch(branch.branch_id).branch_mechanism_ids == (
        "repair_ordering",
    )
    assert branch.branch_id not in patches
    assert branch.branch_id in workspaces
    assert hyp_store.statuses == [("h-2", "rejected")]


def test_validation_telemetry_repairable_marks_wiring_suspect_without_reusing_workspace() -> None:
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
    branch.state = BranchState.VALIDATING
    hypothesis = HypothesisProposal(
        hypothesis_text="Add missing activation telemetry.",
        change_locus="solver_design",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="activation_probe", change_type="add"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-3",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
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
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.VALIDATION,
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
        reason_codes=(
            VALIDATION_TELEMETRY_REPAIRABLE,
            TELEMETRY_VALIDATION_REPAIRABLE,
            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        ),
        exposed_summary="validation telemetry repairable",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.VALIDATION_REPAIR_REQUIRED,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=(
            VALIDATION_TELEMETRY_REPAIRABLE,
            TELEMETRY_VALIDATION_REPAIRABLE,
        ),
    )

    assert result.decision == Decision.VALIDATION_REPAIR_REQUIRED
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "validation_repair_required"
    assert result.reason.startswith("VALIDATION_TELEMETRY_REPAIRABLE")
    assert "repair_policy=repair_first_same_mechanism_or_clean_fork" in result.reason
    assert "repair_mechanism_ids=activation_probe" in result.reason
    assert result.repair_mechanism_ids == ("activation_probe",)
    assert discarded == [branch.branch_id]
    assert branch.branch_id not in patches
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert controller.get_branch(branch.branch_id).branch_code_status == (
        "telemetry_wiring_suspect"
    )
    assert controller.get_branch(branch.branch_id).last_telemetry_outcome == (
        "activation_missing_or_wiring_suspect"
    )
    assert controller.get_branch(branch.branch_id).telemetry_repair_mechanism_ids == (
        "activation_probe",
    )
    assert controller.get_branch(branch.branch_id).telemetry_repair_attempts == {
        "activation_probe": 1
    }
    assert hyp_store.statuses == [("h-3", "validation_telemetry_failed")]
    assert controller.get_branch(branch.branch_id).state == BranchState.EXPLORE


def test_screening_telemetry_repairable_marks_telemetry_failed_not_code_failed() -> None:
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
    hypothesis = HypothesisProposal(
        hypothesis_text="Add missing activation telemetry.",
        change_locus="solver_design",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="activation_probe", change_type="add"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-4",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
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
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(TELEMETRY_VALIDATION_REPAIRABLE,),
        exposed_summary="screening telemetry repairable",
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
        decision_reason_codes=(TELEMETRY_VALIDATION_REPAIRABLE,),
    )

    assert result.attempt_kind == "telemetry_repairable"
    assert result.counts_toward_max_rounds is False
    assert hyp_store.statuses == [("h-4", "screening_telemetry_failed")]
    assert discarded == [branch.branch_id]


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
            SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
            SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
        ),
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
    assert patches[branch.branch_id] is previous_patch
    assert discarded == []
    assert action.slot == "exploit_weak_positive"
