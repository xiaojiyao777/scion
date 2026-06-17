from __future__ import annotations

import json
from pathlib import Path

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
    SCREENING_WEAK_SIGNAL_CONTINUE,
)
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evidence_recording.replay_identity import (
    FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS,
    FORMAL_REPLAY_IDENTITY_SCHEMA,
    formal_replay_identity_payload,
)
from scion.core.formal_candidate_artifacts import (
    FormalCandidatePatchArtifactRecorder,
)
from scion.core.models import (
    Branch,
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
    PairwiseCaseFeedback,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.proposal.screening_feedback import screening_feedback_summary
from scion.core.telemetry_validation import (
    TELEMETRY_EFFECT_ZERO_OUTCOME,
    TELEMETRY_VALIDATION_REPAIRABLE,
    VALIDATION_TELEMETRY_REPAIRABLE,
)
from scion.tests.unit.core.decision_finalizer_lifecycle_test_support import (
    _HypothesisStore,
)


def test_reconcile_continue_is_not_rewritten_to_abandon() -> None:
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
        hypothesis_text="Try a bounded same-branch refinement.",
        change_locus="repair",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-reconcile-continue",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    hyp_store = _HypothesisStore()
    hard_abandons: list[tuple[str, str]] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *args: hard_abandons.append(args),  # type: ignore[arg-type]
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: workspaces.pop(branch_id, None),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="reconcile continue",
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
        action_label="reconcile",
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.action == "reconcile"
    assert result.decision == Decision.CONTINUE_EXPLORE
    assert stored.state == BranchState.EXPLORE
    assert hard_abandons == []


def test_win_skewed_weak_positive_screening_workspace_reason_is_positive() -> None:
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
        hypothesis_id="h-weak-positive",
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
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

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
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=4,
            losses=1,
            ties=7,
            win_rate=1 / 3,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=4.0,
            candidate_failed_pairs=0,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="win-skewed weak-positive follow-up",
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
        lifecycle_action="retain_head",
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "weak-positive screening signal" in result.reason
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert discarded == []
    assert hyp_store.statuses == [
        ("h-weak-positive", "screening_weak_positive_retained")
    ]


def test_pair_level_weak_positive_screening_workspace_is_retained() -> None:
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
        hypothesis_text="Tune a bounded decision lever.",
        change_locus="decision",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="bounded_decision_lever", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-pair-weak-positive",
        branch_id=branch.branch_id,
        change_locus="decision",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
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
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            candidate_failed_pairs=0,
            runtime_pairs=4,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="pair-level weak-positive follow-up",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=(
            PairwiseCaseFeedback(case_id="case-a", seed=1, comparison="win", delta=1.0),
            PairwiseCaseFeedback(case_id="case-b", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-c", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-d", seed=1, comparison="tie", delta=0.0),
        ),
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
            SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        ),
        lifecycle_action="retain_head",
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "weak-positive screening signal" in result.reason
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert stored.branch_evidence_summary["runtime_evidence_pressure_count"] == 0
    assert discarded == []
    assert hyp_store.statuses == [
        ("h-pair-weak-positive", "screening_weak_positive_retained")
    ]


def test_pair_level_weak_positive_fresh_required_marks_runtime_replay() -> None:
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
        hypothesis_text="Tune a bounded decision lever.",
        change_locus="decision",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="bounded_decision_lever", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-pair-fresh-runtime",
        branch_id=branch.branch_id,
        change_locus="decision",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    hypotheses = {branch.branch_id: hypothesis}
    patches = {branch.branch_id: patch}
    current_hypothesis = {branch.branch_id: h_record}
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

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
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_pairs=0,
            champion_cached_runtime_pairs=4,
            runtime_evidence_status="fresh_champion_required",
        ),
        gate_outcome="unclear",
        reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        exposed_summary="pair-level weak-positive follow-up needs fresh runtime",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=(
            PairwiseCaseFeedback(case_id="case-a", seed=1, comparison="win", delta=1.0),
            PairwiseCaseFeedback(case_id="case-b", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-c", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-d", seed=1, comparison="tie", delta=0.0),
        ),
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="fresh_champion_required",
        champion_cached_runtime_pairs=4,
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
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        ),
        lifecycle_action="retain_head",
    )

    stored = controller.get_branch(branch.branch_id)
    marker = stored.branch_evidence_summary["fresh_runtime_followup"]

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert stored.branch_evidence_summary["evidence_retention_status"] == "retained"
    assert stored.branch_evidence_summary["fresh_runtime_pending"] is True
    assert marker["queue_intent"] == "fresh_champion_runtime_replay"
    assert marker["scheduler_marker"] == "fresh_champion_runtime_replay_pending"
    assert marker["trigger"] == "pair_level_win_no_loss"
    assert marker["fresh_runtime_required"] is True
    assert marker["promotion_boundary"] == "not_a_promotion_or_validation_decision"
    assert marker["decision_features_excluded"] is True
    assert discarded == []
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert hypotheses[branch.branch_id] is hypothesis
    assert patches[branch.branch_id] is patch
    assert current_hypothesis[branch.branch_id] is h_record
    assert hyp_store.statuses == [
        ("h-pair-fresh-runtime", "screening_fresh_runtime_replay_pending")
    ]


def test_actionable_loss_diagnostic_fresh_required_marks_followup_not_promotion() -> None:
    branch = Branch(
        branch_id="loss-diagnostic",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=1,
            ties=3,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=-1.0,
            ci_high=1.0,
            runtime_pairs=0,
            runtime_evidence_status="fresh_champion_required",
        ),
        gate_outcome="unclear",
        reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        exposed_summary="loss diagnostic needs fresh runtime",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=(
            PairwiseCaseFeedback(case_id="case-a", seed=1, comparison="loss", delta=-1.0),
            PairwiseCaseFeedback(case_id="case-b", seed=1, comparison="tie", delta=0.0),
        ),
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="fresh_champion_required",
        champion_cached_runtime_pairs=2,
        mechanism_evidence={
            "primary_activation_status": "observed",
            "primary_effect_status": "positive",
        },
    )
    feedback = screening_feedback_summary(
        protocol,
        decision_reason_codes=(
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
        ),
    )

    from scion.core.decision_lifecycle_actions import (
        update_branch_screening_evidence_summary,
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=(
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
        ),
    )

    marker = branch.branch_evidence_summary["fresh_runtime_followup"]

    assert feedback.tier == "quality_regression"
    assert marker["trigger"] == "actionable_loss_diagnostic"
    assert marker["followup_policy"] == (
        "fresh_champion_runtime_or_diagnostic_followup_required"
    )
    assert marker["fresh_runtime_required"] is True
    assert marker["promotion_boundary"] == "not_a_promotion_or_validation_decision"
    assert marker["decision_features_excluded"] is True


def test_no_effect_fresh_required_runtime_tie_does_not_mark_followup() -> None:
    branch = Branch(
        branch_id="no-effect-runtime-tie",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_pairs=0,
            runtime_evidence_status="fresh_champion_required",
        ),
        gate_outcome="unclear",
        reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        exposed_summary="no-effect runtime tie needs no replay followup",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=(
            PairwiseCaseFeedback(case_id="case-a", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-b", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-c", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-d", seed=1, comparison="tie", delta=0.0),
        ),
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="fresh_champion_required",
        champion_cached_runtime_pairs=4,
    )
    feedback = screening_feedback_summary(
        protocol,
        decision_reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
    )

    from scion.core.decision_lifecycle_actions import (
        update_branch_screening_evidence_summary,
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
    )

    summary = branch.branch_evidence_summary

    assert feedback.tier == "no_effect"
    assert summary["tier"] == "no_effect"
    assert summary.get("fresh_runtime_pending") is not True
    assert summary.get("fresh_runtime_required") is not True
    assert "fresh_runtime_followup" not in summary


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


def test_quality_regression_discarded_candidate_records_patch_artifact(
    tmp_path: Path,
) -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path=str(tmp_path / "champion"),
            code_snapshot_hash="champion-hash",
        )
    )
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "clean-hash"
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded repair scoring change.",
        change_locus="repair",
        action="modify",
        target_file="solver.py",
        mechanism_changes=(
            MechanismChange(id="repair_scoring", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-quality-regression",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
        target_file="solver.py",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="def score():\n    return 2\n",
    )
    base_workspace = tmp_path / "champion"
    workspace = tmp_path / "workspace"
    base_workspace.mkdir()
    workspace.mkdir()
    (base_workspace / "solver.py").write_text(
        "def score():\n    return 1\n",
        encoding="utf-8",
    )
    (workspace / "solver.py").write_text(patch.code_content, encoding="utf-8")
    recorder = FormalCandidatePatchArtifactRecorder(
        tmp_path,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    workspaces = {branch.branch_id: str(workspace)}
    patches = {branch.branch_id: patch}
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
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
        record_formal_candidate_artifact=lambda **kwargs: recorder.record(
            **kwargs,
            base_workspace=str(base_workspace),
        ),
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=6,
            wins=0,
            losses=2,
            ties=4,
            win_rate=0.0,
            median_delta=-1.0,
            ci_low=-2.0,
            ci_high=0.0,
            runtime_pairs=6,
            runtime_ratio_median=1.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="quality regression",
        raw_metrics_ref=str(tmp_path / "metrics" / "screening.json"),
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
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )

    metadata_paths = list(
        (tmp_path / "artifacts" / "formal_candidates").glob(
            "**/candidate.patch.json"
        )
    )
    assert result.decision == Decision.CONTINUE_EXPLORE
    assert discarded == [branch.branch_id]
    assert branch.branch_id not in patches
    assert len(metadata_paths) == 1
    metadata = json.loads(metadata_paths[0].read_text(encoding="utf-8"))
    assert metadata["branch_id"] == branch.branch_id
    assert metadata["hypothesis_id"] == "h-quality-regression"
    assert metadata["stage"] == "screening"
    assert metadata["branch_code_status"] == "discarded"
    assert metadata["target_files"] == ["solver.py"]
    assert metadata["base"]["base_champion_hash"] == "champion-hash"
    assert metadata["base"]["last_clean_code_hash"] == "clean-hash"
    assert metadata["current"]["current_code_hash"] == "candidate-hash"
    assert metadata["patch"]["files"][0]["code_content"] == patch.code_content
    replay_identity = metadata["replay_identity"]
    expected_identity = formal_replay_identity_payload(
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
        patch_digest=metadata["patch"]["patch_digest"],
        selected_surface="repair",
        protocol_version="protocol-v3",
        raw_metrics_ref="metrics/screening.json",
        code_hash="candidate-hash",
    )
    assert replay_identity["schema"] == FORMAL_REPLAY_IDENTITY_SCHEMA
    assert set(FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS).issubset(replay_identity)
    for key in FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS:
        assert replay_identity[key] == expected_identity[key]
    assert replay_identity["identity_status"] == "complete"
    assert replay_identity["status"] == "complete"
    assert replay_identity["missing_identity_keys"] == []
    assert replay_identity["missing_keys"] == []
    assert metadata["replay_metadata"]["replay_identity_ref"] == (
        "candidate.patch.json#/replay_identity"
    )
    assert metadata["replay_metadata"]["replay_identity_status"] == "complete"
    summary = branch.branch_evidence_summary
    assert summary["formal_candidate_artifact_status"] == "recorded"
    assert summary["formal_candidate_artifact_report"]["artifact_status"] == "recorded"
    assert summary["replay_identity"]["identity_status"] == "complete"
    assert summary["formal_replay_identity_ref"].endswith("#/replay_identity")
    diff_text = (metadata_paths[0].parent / "candidate.diff").read_text(
        encoding="utf-8"
    )
    assert "--- a/solver.py" in diff_text
    assert "+++ b/solver.py" in diff_text
    assert "-    return 1" in diff_text
    assert "+    return 2" in diff_text
    index_text = (
        tmp_path / "artifacts" / "formal_candidates" / "index.jsonl"
    ).read_text(encoding="utf-8")
    assert "h-quality-regression" in index_text


def test_formal_candidate_artifact_captures_registry_activation_file(
    tmp_path: Path,
) -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion-hash",
        )
    )
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "clean-hash"
    hypothesis = HypothesisProposal(
        hypothesis_text="Add a registered operator.",
        change_locus="vehicle_level",
        action="create_new",
        target_file="operators/new_operator.py",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-create-operator",
        branch_id=branch.branch_id,
        change_locus="vehicle_level",
        action="create_new",
        status="running",
        target_file="operators/new_operator.py",
    )
    operator_code = "class NewOperator:\n    pass\n"
    patch = PatchProposal(
        file_path="operators/new_operator.py",
        action="create",
        code_content=operator_code,
    )
    base_workspace = tmp_path / "champion"
    workspace = tmp_path / "workspace"
    (base_workspace / "operators").mkdir(parents=True)
    (workspace / "operators").mkdir(parents=True)
    base_registry = "operators: []\n"
    candidate_registry = (
        "operators:\n"
        "- name: new_operator\n"
        "  file_path: operators/new_operator.py\n"
        "  class_name: NewOperator\n"
        "  weight: 0.1\n"
    )
    (base_workspace / "registry.yaml").write_text(base_registry, encoding="utf-8")
    (workspace / "registry.yaml").write_text(
        candidate_registry,
        encoding="utf-8",
    )
    (workspace / "operators" / "new_operator.py").write_text(
        operator_code,
        encoding="utf-8",
    )
    recorder = FormalCandidatePatchArtifactRecorder(
        tmp_path,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=2,
            wins=1,
            losses=0,
            ties=1,
            win_rate=0.5,
            median_delta=1.0,
            ci_low=0.0,
            ci_high=2.0,
        ),
        gate_outcome="expand",
        reason_codes=("SCREENING_EXPAND",),
        exposed_summary="registered operator screening expand",
        raw_metrics_ref=str(tmp_path / "metrics" / "screening.json"),
    )

    artifact_ref = recorder.record(
        branch=branch,
        hypothesis=hypothesis,
        h_record=h_record,
        patch=patch,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        decision=Decision.EXPAND_SCREENING,
        decision_reason_codes=("SCREENING_EXPAND",),
        workspace=str(workspace),
        base_workspace=str(base_workspace),
    )

    metadata_paths = list(
        (tmp_path / "artifacts" / "formal_candidates").glob(
            "**/candidate.patch.json"
        )
    )
    assert artifact_ref
    assert len(metadata_paths) == 1
    metadata = json.loads(metadata_paths[0].read_text(encoding="utf-8"))
    assert metadata["proposal_target_files"] == ["operators/new_operator.py"]
    assert metadata["activation_files"] == ["registry.yaml"]
    assert metadata["target_files"] == [
        "operators/new_operator.py",
        "registry.yaml",
    ]
    files = {item["file_path"]: item for item in metadata["patch"]["files"]}
    assert files["operators/new_operator.py"]["action"] == "create"
    assert files["operators/new_operator.py"]["code_content"] == operator_code
    assert files["registry.yaml"]["action"] == "modify"
    assert files["registry.yaml"]["code_content"] == candidate_registry
    assert files["registry.yaml"]["base_sha256"]
    assert files["registry.yaml"]["workspace_current_sha256"]
    assert metadata["patch"]["patch_digest"] == metadata["replay_identity"][
        "patch_digest"
    ]
    diff_text = (metadata_paths[0].parent / "candidate.diff").read_text(
        encoding="utf-8"
    )
    assert "+++ b/operators/new_operator.py" in diff_text
    assert "+++ b/registry.yaml" in diff_text


def test_formal_candidate_artifact_omission_reports_missing_replay_identity(
    tmp_path: Path,
) -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion-hash",
        )
    )
    branch.current_code_hash = "candidate-hash"
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded repair scoring change.",
        change_locus="repair",
        action="modify",
        target_file="solver.py",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-missing-identity",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
        target_file="solver.py",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="def score():\n    return 2\n",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solver.py").write_text(patch.code_content, encoding="utf-8")
    recorder = FormalCandidatePatchArtifactRecorder(tmp_path)
    workspaces = {branch.branch_id: str(workspace)}
    patches = {branch.branch_id: patch}
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
        discard_branch_workspace=lambda branch_id: workspaces.pop(branch_id, None),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
        record_formal_candidate_artifact=lambda **kwargs: recorder.record(**kwargs),
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        exposed_summary="weak signal",
        raw_metrics_ref=str(tmp_path / "metrics" / "screening.json"),
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
        decision_reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
    )

    metadata_paths = list(
        (tmp_path / "artifacts" / "formal_candidates").glob(
            "**/candidate.patch.json"
        )
    )
    index_rows = [
        json.loads(line)
        for line in (
            tmp_path / "artifacts" / "formal_candidates" / "index.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = branch.branch_evidence_summary
    report = summary["formal_candidate_artifact_report"]

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert metadata_paths == []
    assert len(index_rows) == 1
    assert index_rows[0]["artifact_status"] == "omitted"
    assert index_rows[0]["artifact_omitted_reason"] == "missing_replay_identity"
    assert "problem_spec_hash" in index_rows[0]["missing_replay_identity_keys"]
    assert summary["formal_candidate_artifact_status"] == "omitted"
    assert summary["artifact_omitted_reason"] == "missing_replay_identity"
    assert summary["non_replayable_reason"] == (
        "formal_candidate_artifact_omitted:missing_replay_identity"
    )
    assert report["artifact_status"] == "omitted"
    assert report["artifact_omitted_reason"] == "missing_replay_identity"
    assert "seed_ledger_hash" in report["missing_replay_identity_keys"]
    assert summary["replay_identity"]["identity_status"] == "degraded"


def test_abandon_syncs_terminal_branch_evidence_before_lineage_and_persist() -> None:
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
        hypothesis_text="Try a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-abandon",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
        mechanism_changes=(
            MechanismChange(id="candidate_filter_probe", change_type="modify"),
        ),
    )
    hyp_store = _HypothesisStore()
    hard_abandons: list[tuple[str, str]] = []
    persisted: list[dict] = []
    lineage_snapshots: list[tuple[str, dict]] = []

    class BranchStore:
        def save(self, saved_branch) -> None:
            persisted.append(dict(saved_branch.branch_evidence_summary))

    def record_lineage(*args, **_kwargs) -> None:
        recorded_branch = args[0]
        lineage_snapshots.append(
            (
                recorded_branch.branch_code_status,
                dict(recorded_branch.branch_evidence_summary),
            )
        )

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=BranchStore(),
        hypothesis_store=hyp_store,
        branch_workspaces={},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *args: hard_abandons.append(args),  # type: ignore[arg-type]
        record_step_lineage=record_lineage,
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
            n_cases=10,
            wins=0,
            losses=4,
            ties=6,
            win_rate=0.0,
            median_delta=-1.5,
            ci_low=-3.0,
            ci_high=-0.5,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )

    stored = controller.get_branch(branch.branch_id)
    assert result.decision == Decision.ABANDON
    assert result.action == "screening"
    assert stored.state == BranchState.ABANDONED
    assert hard_abandons == [(branch.branch_id, "decision_abandon")]
    assert stored.branch_code_status != "clean"
    assert stored.branch_mechanism_ids == (
        "repair_ordering",
        "candidate_filter_probe",
    )
    assert lineage_snapshots
    assert lineage_snapshots[0][0] == stored.branch_code_status
    assert lineage_snapshots[0][1]["terminal_reason"] == "SCREENING_FAIL_WIN_RATE"
    assert persisted[-1]["terminal_reason"] == "SCREENING_FAIL_WIN_RATE"
    assert persisted[-1]["losses"] == 4
    assert persisted[-1]["abandon_accounting"]["kind"] == "hard_terminal_abandon"
    assert persisted[-1]["abandon_accounting"]["counts_toward_hard_abandon"] is True


def test_lifecycle_archive_abandon_does_not_increment_hard_counter() -> None:
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
        hypothesis_text="Archive a low-signal lineage.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="low_signal_repair", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-soft-archive",
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
    hyp_store = _HypothesisStore()
    hard_abandons: list[tuple[str, str]] = []
    archived: list[tuple[str, str]] = []
    cleaned: list[str] = []
    lineage_summaries: list[dict] = []

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
        record_hard_abandon=lambda *args: hard_abandons.append(args),  # type: ignore[arg-type]
        record_step_lineage=lambda *args, **_kwargs: lineage_summaries.append(
            dict(args[0].branch_evidence_summary)
        ),
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda _branch_id: None,
        archive_workspace=lambda workspace, branch_id: archived.append(
            (workspace, branch_id)
        ),
        cleanup_workspace=lambda workspace: cleaned.append(workspace),
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=3,
            ties=5,
            win_rate=0.0,
            median_delta=-1.0,
            ci_low=-2.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",),
        exposed_summary="soft archive",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=("SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",),
        lifecycle_action="archive_lineage",
    )

    stored = controller.get_branch(branch.branch_id)
    accounting = stored.branch_evidence_summary["abandon_accounting"]

    assert branch.state == BranchState.ABANDONED
    assert result.action == "soft_abandon"
    assert result.decision == Decision.ABANDON
    assert result.attempt_kind == "screening"
    assert result.lifecycle_bookkeeping == {
        "schema": "scion.lifecycle_bookkeeping.v1",
        "role": "screening_result_lifecycle_annotation",
        "attached_to_attempt_kind": "screening",
        "legacy_attempt_kind": "branch_lifecycle_policy",
        "legacy_decision_layer_source": "lifecycle_policy",
        "decision_layer_source": "stage_decision",
        "lifecycle_action": "archive_lineage",
        "reason_codes": ["SCREENING_SOFT_ABANDON_NEGATIVE_DELTA"],
    }
    assert hard_abandons == []
    assert archived == [("/tmp/workspace", branch.branch_id)]
    assert cleaned == ["/tmp/workspace"]
    assert workspaces == {}
    assert patches == {}
    assert hyp_store.statuses == [("h-soft-archive", "rejected")]
    assert accounting["kind"] == "soft_lifecycle_archive"
    assert accounting["counts_toward_hard_abandon"] is False
    assert accounting["lifecycle_action"] == "archive_lineage"
    assert stored.branch_evidence_summary["counts_toward_hard_abandon"] is False
    assert lineage_summaries[0]["abandon_accounting"]["kind"] == (
        "soft_lifecycle_archive"
    )
    assert lineage_summaries[0]["abandon_accounting"][
        "counts_toward_hard_abandon"
    ] is False


def test_legacy_soft_abandon_lifecycle_action_maps_to_soft_archive_accounting() -> None:
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
        hypothesis_text="Soft-abandon a low-signal lineage.",
        change_locus="repair",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-legacy-soft",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    hyp_store = _HypothesisStore()
    hard_abandons: list[tuple[str, str]] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces={},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *args: hard_abandons.append(args),  # type: ignore[arg-type]
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda _branch_id: None,
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=None,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=("BRANCH_LIFECYCLE_ARCHIVE_LINEAGE",),
        lifecycle_action="soft_abandon",  # type: ignore[arg-type]
    )

    accounting = branch.branch_evidence_summary["abandon_accounting"]

    assert result.action == "soft_abandon"
    assert branch.state == BranchState.ABANDONED
    assert hard_abandons == []
    assert accounting["kind"] == "soft_lifecycle_archive"
    assert accounting["lifecycle_action"] == "archive_lineage"
    assert accounting["counts_toward_hard_abandon"] is False


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


def test_effect_zero_diagnostic_with_observed_activation_is_not_wiring_suspect() -> None:
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
    branch.branch_code_status = "telemetry_wiring_suspect"
    branch.last_telemetry_outcome = "activation_missing_or_wiring_suspect"
    hypothesis = HypothesisProposal(
        hypothesis_text="Refine merge_vehicles on the same branch.",
        change_locus="solver_design",
        action="modify",
        mechanism_changes=(MechanismChange(id="merge_vehicles", change_type="modify"),),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-effect-zero",
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
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

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
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=14,
            wins=7,
            losses=1,
            ties=6,
            win_rate=0.5,
            median_delta=775.0,
            ci_low=1.0,
            ci_high=900.0,
            runtime_ratio_median=0.49,
            runtime_pairs=14,
        ),
        gate_outcome="fail",
        reason_codes=("TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        exposed_summary="weak signal; telemetry_effect_zero=diagnostic",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_operator_attempts=28,
        mechanism_evidence={
            "primary_activation_status": "observed",
            "primary_effect_status": "zero",
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
        decision_reason_codes=(SCREENING_WEAK_SIGNAL_CONTINUE,),
        lifecycle_action="retain_head",
    )

    stored = controller.get_branch(branch.branch_id)
    phase = stored.branch_evidence_summary["phase_activation_summary"]
    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.attempt_kind == "screening"
    assert result.counts_toward_max_rounds is True
    assert discarded == []
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_telemetry_outcome == TELEMETRY_EFFECT_ZERO_OUTCOME
    assert stored.telemetry_repair_mechanism_ids == ()
    assert phase["activation_status"] == "observed"
    assert phase["telemetry_outcome"] == TELEMETRY_EFFECT_ZERO_OUTCOME
    assert phase["telemetry_outcome"] != "activation_missing_or_wiring_suspect"
    assert "TELEMETRY_VALIDATION_REPAIRABLE" not in stored.branch_evidence_summary[
        "decision_reason_codes"
    ]
    assert branch.branch_id in patches
    assert workspaces[branch.branch_id] == "/tmp/workspace"


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
