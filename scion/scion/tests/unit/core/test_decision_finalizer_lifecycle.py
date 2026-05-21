from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
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
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
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
            SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        ),
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.counts_toward_max_rounds is True
    assert result.attempt_kind == "screening"
    assert "weak screening signal" in result.reason
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert patches[branch.branch_id] is patch
    assert discarded == []
    assert zero_win_streaks[branch.branch_id] == 1
    assert controller.get_branch(branch.branch_id).direction is not None
    assert hyp_store.statuses == [("h-1", "rejected")]


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
    assert branch.branch_id not in patches
    assert branch.branch_id in workspaces
    assert hyp_store.statuses == [("h-2", "rejected")]


def test_validation_telemetry_repairable_preserves_workspace_with_stage_attempt_kind() -> None:
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
    assert discarded == []
    assert patches[branch.branch_id] is patch
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert hyp_store.statuses == [("h-3", "code_failed")]
    assert controller.get_branch(branch.branch_id).state == BranchState.EXPLORE
