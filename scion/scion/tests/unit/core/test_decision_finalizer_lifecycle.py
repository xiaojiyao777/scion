"""Formal Decision side-effect tests for DecisionFinalizer."""
from __future__ import annotations

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
    return finalizer, controller, branch, hypothesis, record, store, workspaces, hypotheses, patches, lineage


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
