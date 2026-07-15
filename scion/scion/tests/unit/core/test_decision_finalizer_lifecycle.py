"""Formal Decision side-effect tests for DecisionFinalizer."""

from __future__ import annotations

import pytest

from scion.core.branch import BranchController
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary,
)
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


class _HypothesisStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str]] = []

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        self.statuses.append((hypothesis_id, status))


def _fixture():
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
        hypothesis_text="Change the selected algorithm surface.",
        change_locus="algorithm",
        action="modify",
        target_file="solver.py",
    )
    record = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus="algorithm",
        action="modify",
        status="running",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    hypotheses = {branch.branch_id: hypothesis}
    patches = {
        branch.branch_id: PatchProposal(
            file_path="solver.py",
            action="modify",
            code_content="# candidate\n",
        )
    }
    current = {branch.branch_id: record}
    store = _HypothesisStore()
    persisted: list[str] = []
    lineage: list[Decision] = []

    def discard(branch_id: str) -> None:
        workspaces.pop(branch_id, None)

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current,
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step_lineage=lambda *args, **_kwargs: lineage.append(args[7]),
        decision_reason_codes_for=lambda *_args: ("FORMAL_REASON",),
        discard_branch_workspace=discard,
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=persisted.append,
    )
    return (
        finalizer,
        controller,
        branch,
        hypothesis,
        record,
        store,
        workspaces,
        hypotheses,
        patches,
        lineage,
    )


def _apply(finalizer, branch, hypothesis, record, decision: Decision):
    return finalizer.apply(
        branch=branch,
        decision=decision,
        hypothesis=hypothesis,
        h_record=record,
        protocol_result=None,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("FORMAL_REASON",),
    )


def test_queue_validate_applies_formal_transition_without_advisory_override() -> None:
    finalizer, controller, branch, hypothesis, record, store, *_rest = _fixture()
    result = _apply(finalizer, branch, hypothesis, record, Decision.QUEUE_VALIDATE)
    assert result.decision is Decision.QUEUE_VALIDATE
    assert controller.get_branch(branch.branch_id).state is BranchState.READY_VALIDATE
    assert "FORMAL_REASON" in result.reason
    assert store.statuses == []


def test_continue_explore_retains_verified_codebase_and_clears_attempt() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis, record, store = fixture[:6]
    workspaces, hypotheses, patches = fixture[6:9]
    result = _apply(finalizer, branch, hypothesis, record, Decision.CONTINUE_EXPLORE)
    assert result.decision is Decision.CONTINUE_EXPLORE
    assert controller.get_branch(branch.branch_id).state is BranchState.EXPLORE
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert branch.branch_id not in hypotheses
    assert branch.branch_id not in patches
    assert store.statuses == [(record.hypothesis_id, "rejected")]


def test_abandon_is_terminal_and_records_only_formal_decision() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis, record, store = fixture[:6]
    lineage = fixture[9]
    result = _apply(finalizer, branch, hypothesis, record, Decision.ABANDON)
    assert result.decision is Decision.ABANDON
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED
    assert lineage == [Decision.ABANDON]
    assert store.statuses == [(record.hypothesis_id, "rejected")]


def test_screening_summary_retains_statistical_status_metric_and_ci() -> None:
    _finalizer, _controller, branch, *_rest = _fixture()
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=3,
            ties=5,
            win_rate=0.0,
            median_delta=-4.0,
            ci_low=-10.25,
            ci_high=-0.5,
            statistical_status="negative",
            statistical_metric="total_distance",
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="private/metrics.json",
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )

    summary = branch.branch_evidence_summary
    assert summary["statistical_status"] == "negative"
    assert summary["statistical_metric"] == "total_distance"
    assert (summary["ci_low"], summary["ci_high"]) == (-10.25, -0.5)
    assert summary["decision_reason_codes"] == ["SCREENING_FAIL_WIN_RATE"]


def test_validation_atomically_replaces_screening_projection_and_retains_history() -> (
    None
):
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis, record = fixture[:5]
    branch.branch_evidence_summary = {
        "canonical_screening_history": [{"round": 1}, {"round": 2}],
    }
    screening = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=5,
            losses=1,
            ties=2,
            win_rate=0.625,
            median_delta=3.5,
            ci_low=-11.0,
            ci_high=12.0,
            statistical_status="uncertain",
            statistical_metric="total_distance",
            runtime_pairs=0,
            total_pairs=32,
            valid_pairs=32,
            pair_wins=20,
            pair_losses=11,
            pair_ties=1,
            runtime_evidence_status="insufficient",
        ),
        gate_outcome="pass",
        reason_codes=("SCREENING_PASS",),
        exposed_summary="screening passed",
        raw_metrics_ref="metrics/screening.json",
        case_ids=("cases/screening.vrp",),
        seed_set=(11, 29, 43, 59),
        champion_cache_hits=32,
        champion_cached_runtime_pairs=32,
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="insufficient",
    )
    update_branch_screening_evidence_summary(
        branch,
        protocol_result=screening,
        decision_reason_codes=("SCREENING_PASS",),
    )
    branch.branch_evidence_summary.update(
        {
            "formal_candidate_patch_artifact_ref": "artifacts/candidate.json",
            "formal_replay_identity_ref": "artifacts/candidate.json#/replay_identity",
            "formal_candidate_artifact_report": {"artifact_status": "recorded"},
            "formal_replay_identity": {"identity_status": "complete"},
            "replay_identity": {"identity_status": "complete"},
            "replay_metadata": {"replay_identity_status": "complete"},
            "candidate_code_hash": "candidate-hash",
            "code_hash": "candidate-hash",
            "current_code_hash": "candidate-hash",
            "patch_digest": "patch-digest",
            "patch_hash": "patch-digest",
        }
    )
    branch.state = BranchState.VALIDATING

    validation = ProtocolResult(
        stage=ExperimentStage.VALIDATION,
        stats=EvalStats(
            n_cases=8,
            wins=6,
            losses=1,
            ties=1,
            win_rate=0.75,
            median_delta=7.75,
            ci_low=0.0,
            ci_high=77.0,
            statistical_status="uncertain",
            statistical_metric="total_distance",
            runtime_ratio_median=1.0111,
            runtime_delta_median_ms=287.5,
            runtime_regression_rate=0.6875,
            runtime_pairs=32,
            total_pairs=32,
            valid_pairs=32,
            pair_wins=25,
            pair_losses=5,
            pair_ties=2,
            runtime_evidence_status="sufficient",
        ),
        gate_outcome="expand",
        reason_codes=("VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",),
        exposed_summary="validation expands",
        raw_metrics_ref="metrics/validation.json",
        case_ids=("cases/validation.vrp",),
        seed_set=(47, 53, 71, 83),
        champion_cache_misses=32,
        runtime_confidence="high",
        runtime_evidence_status="sufficient",
    )
    result = finalizer.apply(
        branch=branch,
        decision=Decision.EXPAND_VALIDATION,
        hypothesis=hypothesis,
        h_record=record,
        protocol_result=validation,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=("VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",),
    )

    assert result.decision is Decision.EXPAND_VALIDATION
    assert branch.state is BranchState.VALIDATING_EXPAND
    summary = branch.branch_evidence_summary
    assert summary["stage"] == summary["protocol_stage"] == "validation"
    assert summary["gate_outcome"] == "expand"
    assert (summary["wins"], summary["losses"], summary["ties"]) == (6, 1, 1)
    assert (summary["pair_wins"], summary["pair_losses"], summary["pair_ties"]) == (
        25,
        5,
        2,
    )
    assert summary["median_delta"] == 7.75
    assert (summary["ci_low"], summary["ci_high"]) == (0.0, 77.0)
    assert summary["raw_metrics_ref"] == "metrics/validation.json"
    assert summary["runtime_pairs"] == 32
    assert summary["runtime_evidence_status"] == "sufficient"
    assert summary["runtime_cache"]["champion_cache_misses"] == 32
    assert summary["reason_codes"] == ["VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN"]
    assert summary["why_not_promoted_reason_codes"] == [
        "VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN"
    ]
    assert summary["canonical_screening_history"] == [
        {"round": 1},
        {"round": 2},
    ]
    assert summary["formal_candidate_patch_artifact_ref"] == (
        "artifacts/candidate.json"
    )
    assert summary["formal_replay_identity"] == {"identity_status": "complete"}
    assert summary["formal_replay_identity_ref"] == (
        "artifacts/candidate.json#/replay_identity"
    )
    assert summary["formal_candidate_artifact_report"] == {
        "artifact_status": "recorded"
    }
    assert summary["replay_identity"] == {"identity_status": "complete"}
    assert summary["replay_metadata"] == {"replay_identity_status": "complete"}
    assert summary["candidate_code_hash"] == "candidate-hash"
    assert summary["code_hash"] == summary["current_code_hash"] == "candidate-hash"
    assert summary["patch_digest"] == summary["patch_hash"] == "patch-digest"
    assert set(summary["protocol_evidence_by_stage"]) == {
        "screening",
        "validation",
    }
    assert summary["protocol_evidence_by_stage"]["screening"]["raw_metrics_ref"] == (
        "metrics/screening.json"
    )
    assert (
        summary["protocol_evidence_by_stage"]["validation"]["raw_metrics_ref"]
        == "metrics/validation.json"
    )
    assert summary["latest_protocol_evidence"]["raw_metrics_ref"] == (
        "metrics/validation.json"
    )


@pytest.mark.parametrize(
    ("branch_state", "protocol_stage", "decision"),
    (
        (
            BranchState.VALIDATING,
            ExperimentStage.VALIDATION,
            Decision.CONTINUE_EXPLORE,
        ),
        (
            BranchState.VALIDATING_EXPAND,
            ExperimentStage.VALIDATION,
            Decision.VALIDATION_REPAIR_REQUIRED,
        ),
        (
            BranchState.FROZEN_TESTING,
            ExperimentStage.FROZEN,
            Decision.CONTINUE_EXPLORE,
        ),
    ),
)
def test_later_stage_continue_projects_evidence_before_reentering_explore(
    branch_state: BranchState,
    protocol_stage: ExperimentStage,
    decision: Decision,
) -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis, record = fixture[:5]
    branch.state = branch_state
    branch.branch_evidence_summary = {
        "stage": "screening",
        "raw_metrics_ref": "metrics/screening.json",
        "formal_candidate_patch_artifact_ref": "artifacts/candidate.json",
    }
    protocol = ProtocolResult(
        stage=protocol_stage,
        stats=EvalStats(
            n_cases=8,
            wins=3,
            losses=3,
            ties=2,
            win_rate=0.375,
            median_delta=0.0,
            ci_low=-2.0,
            ci_high=2.0,
            statistical_status="uncertain",
            statistical_metric="total_distance",
        ),
        gate_outcome="continue",
        reason_codes=("PROTOCOL_CONTINUE",),
        exposed_summary="continue exploration",
        raw_metrics_ref=f"metrics/{protocol_stage.value}.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=decision,
        hypothesis=hypothesis,
        h_record=record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=("PROTOCOL_CONTINUE",),
    )

    assert result.decision is decision
    assert branch.state is BranchState.EXPLORE
    assert branch.branch_evidence_summary["stage"] == protocol_stage.value
    assert branch.branch_evidence_summary["raw_metrics_ref"] == (
        f"metrics/{protocol_stage.value}.json"
    )
    assert (
        branch.branch_evidence_summary["formal_candidate_patch_artifact_ref"]
        == "artifacts/candidate.json"
    )


def test_protocol_stage_projection_replaces_missing_ref_with_latest_evidence() -> None:
    from scion.core.decision_lifecycle_actions import (
        update_branch_protocol_evidence_summary,
    )

    _finalizer, _controller, branch, *_rest = _fixture()
    for median_delta in (1.0, 2.0):
        update_branch_protocol_evidence_summary(
            branch,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.VALIDATION,
                stats=EvalStats(
                    n_cases=1,
                    wins=1,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    median_delta=median_delta,
                    ci_low=0.0,
                    ci_high=median_delta,
                ),
                gate_outcome="pass",
                reason_codes=("VALIDATION_PASS",),
                exposed_summary="validation passed",
                raw_metrics_ref="",
            ),
            decision_reason_codes=("VALIDATION_PASS",),
        )

    by_stage = branch.branch_evidence_summary["protocol_evidence_by_stage"]
    assert set(by_stage) == {"validation"}
    assert by_stage["validation"]["median_delta"] == 2.0
