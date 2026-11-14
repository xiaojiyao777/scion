"""Formal Decision side-effect tests for DecisionFinalizer."""

from __future__ import annotations

import pytest

from scion.core.branch import BranchController
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import (
    AcceptedFileBeforeSource,
    BranchState,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.workspace_service import CandidateWorkspace


def _fixture():
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path="/tmp/champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the selected algorithm surface.",
        change_locus="algorithm",
        action="modify",
        target_file="solver.py",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {}
    candidate_patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    lineage: list[Decision] = []

    def discard(branch_id: str) -> None:
        workspaces.pop(branch_id, None)

    def accept(branch, candidate) -> str:
        branch.current_code_hash = candidate.source_digest
        workspaces[branch.branch_id] = candidate.workspace
        return candidate.workspace

    def reject(candidate) -> None:
        del candidate

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_patches=patches,
        require_promotable_branch=lambda _branch: None,
        promote_branch=lambda _branch: None,
        record_step_lineage=lambda *args, **_kwargs: lineage.append(args[8]),
        discard_branch_workspace=discard,
        accept_candidate=accept,
        reject_candidate=reject,
    )
    return (
        finalizer,
        controller,
        branch,
        hypothesis,
        workspaces,
        patches,
        lineage,
        candidate_patch,
    )


def _apply(finalizer, branch, hypothesis, decision: Decision):
    return finalizer.apply(
        branch=branch,
        decision=decision,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("pass"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("FORMAL_REASON",),
    )


def test_queue_validate_applies_formal_transition_without_advisory_override() -> None:
    finalizer, controller, branch, hypothesis, *_rest = _fixture()
    result = _apply(finalizer, branch, hypothesis, Decision.QUEUE_VALIDATE)
    assert result.decision is Decision.QUEUE_VALIDATE
    assert controller.get_branch(branch.branch_id).state is BranchState.READY_VALIDATE
    assert "FORMAL_REASON" in result.reason


def test_protocol_without_candidate_workspace_uses_regular_transition() -> None:
    finalizer, controller, branch, hypothesis, *_rest = _fixture()
    result = finalizer.apply(
        branch=branch,
        decision=Decision.QUEUE_VALIDATE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("pass"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
    )

    assert result.decision is Decision.QUEUE_VALIDATE
    assert controller.get_branch(branch.branch_id).state is BranchState.READY_VALIDATE


@pytest.mark.parametrize(
    "decision",
    (Decision.QUEUE_VALIDATE, Decision.CONTINUE_EXPLORE),
)
def test_decision_without_candidate_or_protocol_fails_closed(
    decision: Decision,
) -> None:
    finalizer, _controller, branch, hypothesis, *_rest = _fixture()

    with pytest.raises(
        ValueError,
        match="Decision without Protocol requires failed-canary ABANDON",
    ):
        finalizer.apply(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=None,
            canary_result=CanaryResult(passed=True),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            action_label="explore",
            decision_reason_codes=("NO_PROTOCOL",),
        )

    assert branch.state is BranchState.EXPLORE
    assert branch.current_code_hash is None
    assert _rest[2] == []


@pytest.mark.parametrize(
    "decision",
    (Decision.QUEUE_VALIDATE, Decision.CONTINUE_EXPLORE),
)
def test_candidate_without_protocol_fails_before_accepting_staging(
    decision: Decision,
) -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis = fixture[:4]
    accepted: list[str] = []
    rejected: list[str] = []

    def accept(_branch, candidate) -> str:
        accepted.append(candidate.workspace)
        return candidate.workspace

    def reject(candidate) -> None:
        rejected.append(candidate.workspace)

    finalizer.accept_candidate = accept
    finalizer.reject_candidate = reject

    with pytest.raises(
        ValueError,
        match="Decision without Protocol requires failed-canary ABANDON",
    ):
        finalizer.apply(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=None,
            canary_result=CanaryResult(passed=True),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            action_label="explore",
            decision_reason_codes=("NO_PROTOCOL",),
            **_candidate_kwargs(fixture),
        )

    assert accepted == []
    assert rejected == []
    assert branch.current_code_hash is None
    assert fixture[5] == {}
    assert fixture[6] == []


def _screening_protocol(gate_outcome: str) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=2,
            wins=0,
            losses=2,
            ties=0,
            win_rate=0.0,
            median_delta=-1.0,
            ci_low=-2.0,
            ci_high=-0.5,
        ),
        gate_outcome=gate_outcome,
        reason_codes=("SCREENING_RESULT",),
        exposed_summary="screening result",
        raw_metrics_ref="metrics/screening.json",
    )


def _candidate_kwargs(
    fixture,
    *,
    changed_files: tuple[str, ...] = ("solver.py",),
) -> dict[str, object]:
    return {
        "patch": fixture[7],
        "candidate": CandidateWorkspace(
            workspace="/tmp/candidate",
            source_digest="candidate",
            before_sources=(
                AcceptedFileBeforeSource(
                    file_path="solver.py",
                    source="# parent\n",
                ),
            ),
            changed_files=changed_files,
        ),
    }


def test_screening_fail_retains_verified_candidate_for_iteration() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    branch.current_code_hash = "parent"
    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.decision is Decision.CONTINUE_EXPLORE
    assert controller.get_branch(branch.branch_id).state is BranchState.EXPLORE
    assert branch.current_code_hash == "candidate"
    assert branch.direction == "algorithm: Change the selected algorithm surface."
    assert fixture[5][branch.branch_id] is fixture[7]
    assert branch.hypothesis is hypothesis
    assert [change.patch for change in branch.accepted_changes] == [fixture[7]]
    assert branch.accepted_changes[0].before_sources == (
        AcceptedFileBeforeSource(file_path="solver.py", source="# parent\n"),
    )


def test_screening_pass_keeps_exact_candidate_for_validation() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]

    result = finalizer.apply(
        branch=branch,
        decision=Decision.QUEUE_VALIDATE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("pass"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.decision is Decision.QUEUE_VALIDATE
    assert controller.get_branch(branch.branch_id).state is BranchState.READY_VALIDATE
    assert branch.current_code_hash == "candidate"
    assert branch.direction == "algorithm: Change the selected algorithm surface."
    assert fixture[5][branch.branch_id] is fixture[7]
    assert branch.hypothesis == hypothesis


def test_accepted_change_retains_derived_registry_and_selected_h_basis() -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis = fixture[:4]
    basis = {
        "read_refs": ["history-0003"],
        "nearest_prior_refs": ["history-0003"],
        "material_delta": "Change the activation catalogue with the new code.",
        "alternatives_considered": ["Keep the current active implementation."],
        "observable_prediction": "The public screening metric should improve.",
        "falsification_condition": "Reject if screening does not improve.",
    }
    branch.selected_hypothesis_research_basis = basis

    finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(
            fixture,
            changed_files=("solver.py", "registry.yaml"),
        ),
    )

    accepted = branch.accepted_changes[-1]
    assert accepted.changed_files == ("solver.py", "registry.yaml")
    assert accepted.selected_hypothesis_research_basis == basis
    assert accepted.selected_hypothesis_research_basis is not basis


def test_screening_fail_lineage_and_branch_keep_candidate_hash() -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis = fixture[:4]
    candidate_patch = fixture[7]
    lineage_args: list[tuple[object, ...]] = []
    lineage_kwargs: list[dict[str, object]] = []

    def capture_lineage(*args, **kwargs):
        lineage_args.append(args)
        lineage_kwargs.append(kwargs)

    finalizer.record_step_lineage = capture_lineage
    branch.current_code_hash = "parent"
    finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert len(lineage_args) == 1
    assert lineage_args[0][0].current_code_hash == "candidate"
    assert lineage_args[0][1] == "candidate"
    assert lineage_args[0][3] is candidate_patch
    assert lineage_kwargs == [
        {
            "base_champion_version": 1,
            "base_source_ref": f"branch:{branch.branch_id}:accepted-head:0",
            "changed_files": ("solver.py",),
            "strict": True,
        }
    ]
    assert branch.current_code_hash == "candidate"


def test_lineage_failure_blocks_after_applied_candidate() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    branch.current_code_hash = "parent"

    def fail_lineage(*_args, **_kwargs):
        raise OSError("lineage unavailable")

    finalizer.record_step_lineage = fail_lineage

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.execution_outcome is not None
    assert result.decision is None
    assert result.protocol_result is None
    assert controller.get_branch(branch.branch_id).state is BranchState.BLOCKED_INFRA
    assert branch.current_code_hash == "candidate"
    assert fixture[5][branch.branch_id] is fixture[7]


def test_accept_failure_returns_typed_infra_without_applying_decision() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    basis = {
        "read_refs": ["source-0001"],
        "nearest_prior_refs": [],
        "material_delta": "Exercise the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
    }
    branch.selected_hypothesis_research_basis = basis

    def fail_accept(_branch, _candidate) -> str:
        raise OSError("candidate acceptance unavailable")

    finalizer.accept_candidate = fail_accept

    result = finalizer.apply(
        branch=branch,
        decision=Decision.QUEUE_VALIDATE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("pass"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == "CANDIDATE_ACCEPT_FAILED"
    assert result.execution_outcome.provenance["stage"] == "candidate_disposition"
    assert result.execution_outcome.provenance["unapplied_decision"] == (
        "queue_validate"
    )
    assert result.execution_outcome.provenance["completed_protocol"]["stage"] == (
        "screening"
    )
    assert result.decision is None
    assert result.protocol_result is None
    assert result.failure_stage == "candidate_disposition"
    assert controller.get_branch(branch.branch_id).state is BranchState.BLOCKED_INFRA
    assert fixture[6] == []
    assert branch.current_code_hash is None
    assert branch.selected_hypothesis_research_basis == basis


def test_reject_failure_returns_typed_infra_without_abandoning_branch() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    branch.current_code_hash = "parent"

    def fail_reject(_candidate) -> None:
        raise OSError("candidate rejection unavailable")

    finalizer.reject_candidate = fail_reject

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == "CANDIDATE_REJECT_FAILED"
    assert result.execution_outcome.provenance["operation"] == "reject_candidate"
    assert result.execution_outcome.provenance["unapplied_decision"] == "abandon"
    assert result.decision is None
    assert controller.get_branch(branch.branch_id).state is BranchState.BLOCKED_INFRA
    assert branch.current_code_hash == "parent"
    assert fixture[4][branch.branch_id] == "/tmp/workspace"
    assert fixture[6] == []


def test_eval_only_discard_failure_preserves_completed_protocol_fact() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    branch.state = BranchState.VALIDATING
    branch.current_code_hash = "accepted-head"

    def fail_discard(_branch_id: str) -> None:
        raise OSError("branch cleanup unavailable")

    finalizer.discard_branch_workspace = fail_discard
    validation = ProtocolResult(
        stage=ExperimentStage.VALIDATION,
        stats=_screening_protocol("fail").stats,
        gate_outcome="fail",
        reason_codes=("VALIDATION_FAIL",),
        exposed_summary="validation failed",
        raw_metrics_ref="metrics/validation.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        protocol_result=validation,
        canary_result=CanaryResult(passed=True),
        contract_result=None,
        verification_result=None,
        action_label="validate",
        decision_reason_codes=("VALIDATION_FAIL",),
    )

    assert result.execution_outcome is not None
    assert result.execution_outcome.reason_code == "BRANCH_WORKSPACE_DISCARD_FAILED"
    assert result.execution_outcome.provenance["completed_protocol"] == {
        "stage": "validation",
        "gate_outcome": "fail",
        "reason_codes": ["VALIDATION_FAIL"],
        "raw_metrics_ref": "metrics/validation.json",
        "stats": {
            "n_cases": 2,
            "wins": 0,
            "losses": 2,
            "ties": 0,
            "win_rate": 0.0,
            "median_delta": -1.0,
            "ci_low": -2.0,
            "ci_high": -0.5,
            "statistical_status": None,
            "statistical_metric": None,
            "metric_stats": [],
            "protected_objective_regressions": [],
            "runtime_ratio_median": None,
            "runtime_delta_median_ms": None,
            "runtime_regression_rate": None,
            "runtime_pairs": 0,
            "total_pairs": 0,
            "attempted_pairs": 0,
            "valid_pairs": 0,
            "failed_pairs": 0,
            "candidate_failed_pairs": 0,
            "champion_failed_pairs": 0,
            "shared_failed_pairs": 0,
            "bilateral_failed_pairs": 0,
            "pair_wins": 0,
            "pair_losses": 0,
            "pair_ties": 0,
            "runtime_evidence_status": "sufficient",
        },
    }
    assert result.execution_outcome.provenance["unapplied_decision"] == "abandon"
    assert result.protocol_result is None
    assert result.decision is None
    assert controller.get_branch(branch.branch_id).state is BranchState.BLOCKED_INFRA
    assert branch.current_code_hash == "accepted-head"
    assert fixture[4][branch.branch_id] == "/tmp/workspace"
    assert fixture[6] == []


def test_accept_callback_binds_the_direct_candidate_value() -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis = fixture[:4]

    def accept_direct_candidate(branch, candidate) -> str:
        branch.current_code_hash = candidate.source_digest
        return candidate.workspace

    finalizer.accept_candidate = accept_direct_candidate
    finalizer.apply(
        branch=branch,
        decision=Decision.QUEUE_VALIDATE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("pass"),
        canary_result=CanaryResult(passed=True),
        contract_result=None,
        verification_result=None,
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert branch.current_code_hash == "candidate"


def test_unclear_screening_keeps_the_candidate() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("unclear"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.decision is Decision.CONTINUE_EXPLORE
    assert controller.get_branch(branch.branch_id).state is BranchState.EXPLORE
    assert branch.current_code_hash == "candidate"
    assert branch.hypothesis is hypothesis
    assert [change.patch for change in branch.accepted_changes] == [fixture[7]]


def test_abandon_cleans_candidate_without_a_completion_intent() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    workspaces = fixture[4]

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        protocol_result=_screening_protocol("fail"),
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore",
        decision_reason_codes=("SCREENING_RESULT",),
        **_candidate_kwargs(fixture),
    )

    assert result.decision is Decision.ABANDON
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED
    assert branch.current_code_hash is None
    assert workspaces == {}
    assert branch.hypothesis is None


def test_continue_explore_retains_head_hypothesis_metadata() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    workspaces, patches = fixture[4:6]
    result = _apply(finalizer, branch, hypothesis, Decision.CONTINUE_EXPLORE)
    assert result.decision is Decision.CONTINUE_EXPLORE
    assert controller.get_branch(branch.branch_id).state is BranchState.EXPLORE
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert branch.branch_id not in patches
    assert branch.hypothesis is hypothesis


def test_abandon_is_terminal_and_records_only_formal_decision() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    lineage = fixture[6]
    result = _apply(finalizer, branch, hypothesis, Decision.ABANDON)
    assert result.decision is Decision.ABANDON
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED
    assert lineage == [Decision.ABANDON]
    assert branch.hypothesis is None


def test_validation_transition_does_not_require_branch_summary() -> None:
    fixture = _fixture()
    finalizer, controller, branch, hypothesis = fixture[:4]
    branch.state = BranchState.VALIDATING
    lineage_observations: list[tuple[BranchState, bool]] = []

    def record_after_state(*_args, **kwargs) -> None:
        lineage_observations.append(
            (
                controller.get_branch(branch.branch_id).state,
                kwargs.get("strict") is True,
            )
        )

    finalizer.record_step_lineage = record_after_state

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
        runtime_confidence="high",
    )
    result = finalizer.apply(
        branch=branch,
        decision=Decision.EXPAND_VALIDATION,
        hypothesis=hypothesis,
        protocol_result=validation,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=("VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",),
    )

    assert result.decision is Decision.EXPAND_VALIDATION
    assert branch.state is BranchState.VALIDATING_EXPAND
    assert lineage_observations == [(BranchState.VALIDATING_EXPAND, True)]


@pytest.mark.parametrize(
    ("branch_state", "protocol_stage", "decision"),
    (
        (
            BranchState.VALIDATING,
            ExperimentStage.VALIDATION,
            Decision.CONTINUE_EXPLORE,
        ),
        (
            BranchState.FROZEN_TESTING,
            ExperimentStage.FROZEN,
            Decision.CONTINUE_EXPLORE,
        ),
    ),
)
def test_later_stage_continue_does_not_copy_protocol_before_reentering_explore(
    branch_state: BranchState,
    protocol_stage: ExperimentStage,
    decision: Decision,
) -> None:
    fixture = _fixture()
    finalizer, _controller, branch, hypothesis = fixture[:4]
    branch.state = branch_state
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
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=("PROTOCOL_CONTINUE",),
    )

    assert result.decision is decision
    assert branch.state is BranchState.EXPLORE
