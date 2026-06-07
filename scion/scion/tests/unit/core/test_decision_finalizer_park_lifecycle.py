from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    SCREENING_MARGINAL_SIGNAL_CONTINUE,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT,
    SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    SCREENING_ZERO_WIN_STREAK_EXHAUSTED,
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
from scion.tests.unit.core.decision_finalizer_lifecycle_test_support import (
    _HypothesisStore,
)


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
        lifecycle_action="retain_head",
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.counts_toward_max_rounds is True
    assert result.attempt_kind == "screening"
    assert "neutral no-effect screening signal" in result.reason
    assert "weak screening signal" not in result.reason
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
    assert controller.get_branch(
        branch.branch_id
    ).lifecycle_no_effect_diagnostic_followups == 1
    assert controller.get_branch(branch.branch_id).lifecycle_signal_repeat_count == 1
    assert controller.get_branch(
        branch.branch_id
    ).lifecycle_last_signal_signature
    assert hyp_store.statuses == [("h-1", "screening_no_effect")]


def test_no_effect_after_weak_checkpoint_parks_current_head_and_opens_slot() -> None:
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
    branch.direction = "repair: retained weak checkpoint"
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.last_telemetry_outcome = "objective_positive"
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.last_valid_checkpoint_id = "checkpoint-best"
    branch.branch_mechanism_ids = ("repair_ordering",)
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a same-mechanism follow-up.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-retain",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# no-effect follow-up\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    archived: list[str] = []
    cleaned: list[str] = []
    discarded: list[str] = []
    hyp_store = _HypothesisStore()
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
        archive_workspace=lambda workspace, _branch_id: archived.append(workspace),
        cleanup_workspace=lambda workspace: cleaned.append(workspace),
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=0,
            losses=0,
            ties=12,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
            runtime_pairs=12,
            valid_pairs=12,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="all ties after retained checkpoint",
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
            BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
            SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT,
        ),
        lifecycle_action="retain_checkpoint",
    )
    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "retain_checkpoint" in result.reason
    assert stored.state == BranchState.PARKED_LINEAGE
    assert stored.branch_code_status == "parked_lineage"
    assert stored.last_telemetry_outcome == "checkpoint_retained"
    assert stored.best_quality_checkpoint_id == "checkpoint-best"
    assert stored.last_valid_checkpoint_id == "checkpoint-best"
    assert workspaces == {}
    assert patches == {}
    assert archived == ["/tmp/workspace"]
    assert cleaned == ["/tmp/workspace"]
    assert discarded == []
    assert hyp_store.statuses == [("h-retain", "rejected")]
    assert action.action == "create_new"


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
        lifecycle_action="retain_head",
    )

    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "marginal mixed screening signal" in result.reason
    assert stored.branch_code_status == "active_marginal"
    assert stored.last_screening_feedback_tier == "marginal"
    assert stored.lifecycle_marginal_no_effect_streak == 1
    assert stored.lifecycle_signal_repeat_count == 1
    assert stored.lifecycle_last_signal_signature
    assert discarded == []
    assert action.slot == "refine_active"
    assert hyp_store.statuses == [
        ("h-marginal", "screening_marginal_retained")
    ]

def test_marginal_failed_followup_parks_lineage_without_archiving_branch() -> None:
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
    branch.branch_code_status = "active_marginal"
    branch.last_screening_feedback_tier = "marginal"
    branch.best_quality_checkpoint_id = "checkpoint-best"
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune existing marginal mechanism.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-park",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# failed marginal followup\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    archived: list[str] = []
    cleaned: list[str] = []
    discarded: list[str] = []
    hyp_store = _HypothesisStore()
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
        archive_workspace=lambda workspace, _branch_id: archived.append(workspace),
        cleanup_workspace=lambda workspace: cleaned.append(workspace),
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
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
        exposed_summary="loss-heavy marginal follow-up",
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
        ),
        lifecycle_action="park_lineage",
    )

    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "park_lineage" in result.reason
    assert stored.state == BranchState.PARKED_LINEAGE
    assert stored.branch_code_status == "parked_lineage"
    assert stored.branch_lifecycle_new_mechanism_ineligible is True
    assert stored.branch_lifecycle_reroute_reason == (
        "clean_fork_after_branch_lifecycle_policy_block"
    )
    assert stored.last_branch_lifecycle_policy_block[
        "lifecycle_marginal_no_effect_streak"
    ] == 0
    assert branch.branch_id not in workspaces
    assert branch.branch_id not in patches
    assert archived == ["/tmp/workspace"]
    assert cleaned == ["/tmp/workspace"]
    assert discarded == []
    assert controller.get_active_branches() == []
    assert controller.get_reportable_branches() == [stored]
    assert action.action == "create_new"
    assert hyp_store.statuses == [("h-park", "rejected")]

def test_no_effect_exhausted_parks_lineage_and_opens_capacity() -> None:
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
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    hypothesis = HypothesisProposal(
        hypothesis_text="Repair a no-effect branch trigger.",
        change_locus="repair",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-no-effect-park",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=_HypothesisStore(),
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={
            branch.branch_id: PatchProposal("solver.py", "modify", "# no effect\n")
        },
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={branch.branch_id: 2},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda _branch_id: None,
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
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="no-effect exhausted",
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
            BRANCH_LIFECYCLE_PARK_LINEAGE,
            SCREENING_ZERO_WIN_STREAK_EXHAUSTED,
        ),
        lifecycle_action="park_lineage",
    )

    stored = controller.get_branch(branch.branch_id)
    action = Scheduler(max_active_branches=1).select_next([stored])

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert stored.branch_code_status == "parked_lineage"
    assert stored.state == BranchState.PARKED_LINEAGE
    assert stored.lifecycle_no_effect_diagnostic_followups == 2
    assert controller.get_active_branches() == []
    assert controller.get_reportable_branches() == [stored]
    assert action.action == "create_new"


def test_legacy_lifecycle_reason_code_without_explicit_action_does_not_park() -> None:
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
        hypothesis_text="Retry a weak branch without explicit lifecycle action.",
        change_locus="repair",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-legacy-no-action",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {
        branch.branch_id: PatchProposal("solver.py", "modify", "# no effect\n")
    }
    discarded: list[str] = []
    archived: list[str] = []
    cleaned: list[str] = []
    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=_HypothesisStore(),
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches=patches,
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={branch.branch_id: 2},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda workspace, _reason: archived.append(workspace),
        cleanup_workspace=lambda workspace: cleaned.append(workspace),
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
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="legacy lifecycle-like reason code",
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
            BRANCH_LIFECYCLE_PARK_LINEAGE,
            SCREENING_ZERO_WIN_STREAK_EXHAUSTED,
        ),
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "park_lineage" not in result.reason
    assert stored.state == BranchState.EXPLORE
    assert stored.branch_code_status == "discarded"
    assert discarded == [branch.branch_id]
    assert archived == []
    assert cleaned == []
    assert branch.branch_id not in patches
