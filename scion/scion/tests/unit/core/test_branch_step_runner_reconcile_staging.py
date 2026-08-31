"""Stale-reconcile staging ownership tests."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    AcceptedBranchChange,
    AcceptedFileBeforeSource,
    BranchState,
    CanaryResult,
    ChampionState,
    CheckResult,
    ContractResult,
    Decision,
    HypothesisProposal,
    PatchProposal,
    VerificationResult,
)
from scion.core.research_history import project_research_history_step
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.core.workspace_service import CandidateWorkspace
from scion.lineage.registry import LineageRegistry
from scion.proposal.context_manager.history_projection import (
    proposal_pre_protocol_observations,
)


def _champion(version: int) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={},
        code_snapshot_path=f"/tmp/champion-{version}",
    )


def _research_basis(ref: str) -> dict[str, object]:
    return {
        "read_refs": [ref],
        "nearest_prior_refs": [ref],
        "material_delta": f"Replay the mechanism supported by {ref}.",
        "alternatives_considered": ["Discard the accepted branch head."],
        "observable_prediction": "The public screen should improve after replay.",
        "falsification_condition": "Reject if the public screen does not improve.",
    }


def _runner(*, verification_passed: bool, evaluate, conflicts=()):
    controller = BranchController()
    old_champion = _champion(1)
    new_champion = _champion(2)
    branch = controller.create_branch(old_champion)
    controller.mark_all_stale(new_champion.version)
    hypothesis = HypothesisProposal(
        hypothesis_text="Reconcile the local-search candidate.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="class LocalSearch: pass\n",
    )
    branch.hypothesis = hypothesis
    branch.accepted_changes.append(
        AcceptedBranchChange(
            hypothesis=hypothesis,
            patch=patch,
            before_sources=(
                AcceptedFileBeforeSource(
                    file_path="operators/local_search.py",
                    source="class LocalSearch: old\n",
                ),
            ),
        )
    )
    workspaces = {branch.branch_id: "/tmp/old-branch"}
    applied: list[str] = []
    rejected: list[str] = []
    digest_calls: list[str] = []

    class _VerificationGate:
        def run(self, *_args, **_kwargs):
            digest_calls.append("verification")
            return VerificationResult(
                passed=verification_passed,
                checks=(
                    CheckResult(
                        name="verification",
                        passed=verification_passed,
                        severity="light",
                        detail="ok" if verification_passed else "failed",
                        elapsed_ms=0,
                    ),
                ),
                first_failure=None if verification_passed else "failed",
            )

    def create_workspace(_base_workspace):
        return "/tmp/reconcile-staging"

    def apply_change(workspace, patch, **_kwargs):
        applied.append(f"{workspace}:{patch.file_path}")

    def seal_candidate(workspace, **values):
        digest_calls.append("baseline")
        return CandidateWorkspace(
            workspace=workspace,
            source_digest="candidate",
            changed_files=tuple(values["changed_files"]),
        )

    def verify_candidate(candidate):
        digest_calls.append("recompute")
        return candidate

    def reject_workspace(workspace):
        rejected.append(workspace)

    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: new_champion,
        branch_workspaces=workspaces,
        branch_patches={branch.branch_id: patch},
        experiment_protocol_provider=lambda: object(),
        contract_gate=SimpleNamespace(
            validate_patch=lambda *_args, **_kwargs: ContractResult(
                passed=True,
                checks=(),
            )
        ),
        verification_gate=_VerificationGate(),
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        setup_workspace=lambda *_args, **_kwargs: "/tmp/reconcile-base",
        evaluate=evaluate,
        apply_decision_and_finalize=lambda **_kwargs: StepResult(action="reconcile"),
        record_step=lambda _step: None,
        run_explore_step=lambda _branch: StepResult(action="explore"),
        run_eval_step_callback=lambda _branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda _branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        create_reconcile_workspace=create_workspace,
        reconcile_source_conflicts=lambda *_args: tuple(conflicts),
        apply_reconcile_change=apply_change,
        seal_reconcile_candidate=seal_candidate,
        verify_reconcile_candidate=verify_candidate,
        discard_reconcile_workspace=reject_workspace,
    )
    return (
        runner,
        controller,
        branch,
        workspaces,
        applied,
        rejected,
        digest_calls,
    )


def test_reconcile_without_accepted_changes_records_one_unbased_terminal(
    tmp_path: Path,
) -> None:
    runner, controller, branch, _workspaces, _applied, _rejected, _digests = (
        _runner(
            verification_passed=True,
            evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("Protocol must not run without accepted changes")
            ),
        )
    )
    branch.accepted_changes.clear()
    branch.selected_hypothesis_research_basis = _research_basis("mutable-head")
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    recorded_steps = []
    runner.registry = registry
    runner.campaign_id = "campaign-1"
    runner.record_step = recorded_steps.append

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert result.execution_outcome.reason_code == (
        "RECONCILE_NO_ACCEPTED_CHANGES"
    )
    assert result.failure_category == ExecutionOutcome.NOT_EVALUATED.value
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED
    assert branch.selected_hypothesis_research_basis is None
    assert recorded_steps == []
    outcomes = registry.query_execution_outcomes(branch_id=branch.branch_id)
    assert len(outcomes) == 1
    assert outcomes[0]["event_kind"] == "reconcile_not_evaluated_outcome"
    rows = registry.query_by_branch(branch.branch_id)
    assert len(rows) == 1
    assert rows[0]["selected_hypothesis_research_basis_json"] is None
    assert rows[0]["hypothesis_text"] is None
    assert rows[0]["patch_file"] is None


def test_reconcile_verification_failure_rejects_staging_before_abandoning() -> None:
    runner, controller, branch, _workspaces, applied, rejected, digests = _runner(
        verification_passed=False,
        evaluate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Protocol must not run after failed verification")
        ),
    )

    result = runner.run_reconcile_step(branch)

    assert applied == [
        "/tmp/reconcile-staging:operators/local_search.py",
    ]
    assert rejected == ["/tmp/reconcile-staging"]
    assert digests == ["baseline", "verification"]
    assert result.failure_stage == "verification"
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED


def test_reconcile_protocol_failure_rejects_direct_staging_candidate() -> None:
    observed: list[tuple[str, str]] = []

    def not_evaluated(branch, workspace, _hypothesis, **stage_values):
        observed.append((stage_values["branch_state"].value, workspace))
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="TEMPORARY_PROTOCOL_FAILURE",
                detail="protocol did not evaluate the staging candidate",
            )
        )

    runner, controller, branch, workspaces, applied, rejected, digests = _runner(
        verification_passed=True,
        evaluate=not_evaluated,
    )

    result = runner.run_reconcile_step(branch)

    current = controller.get_branch(branch.branch_id)
    assert applied == [
        "/tmp/reconcile-staging:operators/local_search.py",
    ]
    assert rejected == ["/tmp/reconcile-staging"]
    assert digests == ["baseline", "verification", "recompute"]
    assert observed == [("explore", "/tmp/reconcile-staging")]
    assert workspaces[branch.branch_id] == "/tmp/old-branch"
    assert current.state is BranchState.BLOCKED_INFRA
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED


def test_reconcile_not_evaluated_persists_replay_head_basis(
    tmp_path: Path,
) -> None:
    replay_head_basis = _research_basis("accepted-head")
    mutable_branch_basis = _research_basis("mutable-branch-head")

    def not_evaluated(*_args, **_kwargs):
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="TEST_PROTOCOL_STOP",
                provenance={"stage": "screening"},
            )
        )

    runner, _controller, branch, *_rest = _runner(
        verification_passed=True,
        evaluate=not_evaluated,
    )
    branch.accepted_changes[0] = replace(
        branch.accepted_changes[0],
        selected_hypothesis_research_basis=replay_head_basis,
    )
    branch.selected_hypothesis_research_basis = mutable_branch_basis
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    recorded_steps = []
    runner.registry = registry
    runner.campaign_id = "campaign-1"
    runner.record_step = recorded_steps.append

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert len(recorded_steps) == 1
    assert recorded_steps[0].selected_hypothesis_research_basis == (
        replay_head_basis
    )
    outcomes = registry.query_execution_outcomes(branch_id=branch.branch_id)
    assert len(outcomes) == 1
    rows = registry.query_by_branch(branch.branch_id)
    assert len(rows) == 1
    assert json.loads(rows[0]["selected_hypothesis_research_basis_json"]) == (
        replay_head_basis
    )


def test_reconcile_preserve_stale_records_typed_replay_head_step(
    tmp_path: Path,
) -> None:
    replay_head_basis = _research_basis("accepted-head")
    mutable_branch_basis = _research_basis("mutable-branch-head")
    runner, _controller, branch, *_rest = _runner(
        verification_passed=True,
        evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Protocol must not run when it is unavailable")
        ),
    )
    branch.accepted_changes[0] = replace(
        branch.accepted_changes[0],
        selected_hypothesis_research_basis=replay_head_basis,
    )
    branch.selected_hypothesis_research_basis = mutable_branch_basis
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    recorded_steps = []
    runner.registry = registry
    runner.campaign_id = "campaign-1"
    runner.record_step = recorded_steps.append
    runner.experiment_protocol_provider = lambda: None

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert result.execution_outcome.reason_code == "RECONCILE_PROTOCOL_MISSING"
    assert result.decision is None
    assert len(recorded_steps) == 1
    step = recorded_steps[0]
    assert step.hypothesis is branch.accepted_changes[-1].hypothesis
    assert step.patch is branch.accepted_changes[-1].patch
    assert step.contract_passed is None
    assert step.verification_passed is None
    assert step.protocol_result is None
    assert step.decision is None
    assert step.execution_outcome is result.execution_outcome
    assert step.selected_hypothesis_research_basis == replay_head_basis
    assert step.base_champion_version == 2
    assert step.base_source_ref == "champion:v2"
    assert project_research_history_step(step, problem_id="generic_demo") is not None
    outcomes = registry.query_execution_outcomes(branch_id=branch.branch_id)
    assert len(outcomes) == 1
    rows = registry.query_by_branch(branch.branch_id)
    assert len(rows) == 1
    assert json.loads(rows[0]["selected_hypothesis_research_basis_json"]) == (
        replay_head_basis
    )


def test_reconcile_evaluated_lineage_uses_replay_head_basis(
    tmp_path: Path,
) -> None:
    replay_head_basis = _research_basis("accepted-head")
    mutable_branch_basis = _research_basis("mutable-branch-head")
    canary_result = CanaryResult(
        passed=False,
        reason="bounded canary rejection",
        reason_codes=("CANARY_REJECTED",),
    )

    def evaluated(*_args, **_kwargs):
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="PROTOCOL_EVALUATED",
                provenance={"stage": "canary"},
            ),
            decision=Decision.ABANDON,
            canary_result=canary_result,
            decision_reason_codes=("CANARY_REJECTED",),
        )

    runner, _controller, branch, *_rest = _runner(
        verification_passed=True,
        evaluate=evaluated,
    )
    branch.accepted_changes[0] = replace(
        branch.accepted_changes[0],
        selected_hypothesis_research_basis=replay_head_basis,
    )
    branch.selected_hypothesis_research_basis = mutable_branch_basis
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    recorder = EvidenceRecorder(
        campaign_id="campaign-1",
        campaign_dir=tmp_path,
        registry=registry,
    )
    recorded_steps = []
    observed_finalizer_basis = []
    runner.registry = registry
    runner.campaign_id = "campaign-1"
    runner.record_step = recorded_steps.append

    def finalize(**values):
        observed_finalizer_basis.append(
            values["branch"].selected_hypothesis_research_basis
        )
        candidate = values["candidate"]
        recorder.record_step_lineage(
            branch=values["branch"],
            code_hash=candidate.source_digest,
            hypothesis=values["hypothesis"],
            patch=values["patch"],
            contract_result=values["contract_result"],
            verification_result=values["verification_result"],
            canary_result=values["canary_result"],
            protocol_result=values["protocol_result"],
            decision=values["decision"],
            champion=_champion(2),
            decision_reason_codes=values["decision_reason_codes"],
            base_champion_version=2,
            base_source_ref="champion:v2",
            changed_files=candidate.changed_files,
        )
        return StepResult(
            action="reconcile",
            branch_id=branch.branch_id,
            decision=Decision.ABANDON,
        )

    runner.apply_decision_and_finalize = finalize

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.EVALUATED
    assert observed_finalizer_basis == [replay_head_basis]
    assert len(recorded_steps) == 1
    assert recorded_steps[0].selected_hypothesis_research_basis == (
        replay_head_basis
    )
    outcomes = registry.query_execution_outcomes(branch_id=branch.branch_id)
    assert len(outcomes) == 1
    rows = registry.query_by_branch(branch.branch_id)
    assert len(rows) == 1
    assert json.loads(rows[0]["selected_hypothesis_research_basis_json"]) == (
        replay_head_basis
    )


def test_reconcile_contract_interrupt_cleans_the_partially_replayed_chain() -> None:
    runner, controller, branch, _workspaces, applied, rejected, digests = _runner(
        verification_passed=True,
        evaluate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Protocol must not run after interrupted replay")
        ),
    )
    first_change = branch.accepted_changes[0]
    second_hypothesis = HypothesisProposal(
        hypothesis_text="Apply a second accepted increment.",
        change_locus="local_search",
        action="modify",
        target_file="operators/second.py",
    )
    second_patch = PatchProposal(
        file_path="operators/second.py",
        action="modify",
        code_content="class Second: pass\n",
    )
    branch.accepted_changes.append(
        AcceptedBranchChange(
            hypothesis=second_hypothesis,
            patch=second_patch,
            before_sources=(
                AcceptedFileBeforeSource(
                    file_path="operators/second.py",
                    source="class Second: old\n",
                ),
            ),
        )
    )
    contract_calls = 0

    def interrupt_second_contract(*_args, **_kwargs):
        nonlocal contract_calls
        contract_calls += 1
        if contract_calls == 2:
            raise KeyboardInterrupt("interrupt accepted-chain replay")
        return ContractResult(passed=True, checks=())

    runner.contract_gate = SimpleNamespace(validate_patch=interrupt_second_contract)

    with pytest.raises(KeyboardInterrupt, match="accepted-chain replay"):
        runner.run_reconcile_step(branch)

    assert branch.accepted_changes[0] is first_change
    assert applied == [
        "/tmp/reconcile-staging:operators/local_search.py",
    ]
    assert rejected == ["/tmp/reconcile-staging"]
    assert digests == []
    assert controller.get_branch(branch.branch_id).state is BranchState.STALE


def test_reconcile_finalization_interrupt_cleans_unclaimed_staging() -> None:
    runner, controller, branch, _workspaces, applied, rejected, digests = _runner(
        verification_passed=True,
        evaluate=lambda *_args, **_kwargs: EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="TEST_EVALUATED",
            ),
            decision=Decision.ABANDON,
        ),
    )
    runner.apply_decision_and_finalize = lambda **_kwargs: (_ for _ in ()).throw(
        KeyboardInterrupt("interrupt before Decision disposition")
    )

    with pytest.raises(KeyboardInterrupt, match="Decision disposition"):
        runner.run_reconcile_step(branch)

    assert applied == [
        "/tmp/reconcile-staging:operators/local_search.py",
    ]
    assert digests == ["baseline", "verification", "recompute"]
    assert rejected == ["/tmp/reconcile-staging"]
    assert controller.get_branch(branch.branch_id).state is BranchState.STALE


def test_reconcile_same_file_sibling_drift_fails_closed_without_overwrite() -> None:
    runner, controller, branch, workspaces, applied, rejected, digests = _runner(
        verification_passed=True,
        conflicts=("operators/local_search.py",),
        evaluate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Protocol must not run after a source conflict")
        ),
    )

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert result.execution_outcome.reason_code == "RECONCILE_SOURCE_CONFLICT"
    assert result.failure_stage == "reconcile_source"
    assert applied == []
    assert digests == []
    assert rejected == ["/tmp/reconcile-staging"]
    assert workspaces[branch.branch_id] == "/tmp/old-branch"
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED


def test_reconcile_source_conflict_is_complete_non_decision_science(
    tmp_path: Path,
) -> None:
    runner, _controller, branch, _workspaces, _applied, _rejected, _digests = (
        _runner(
            verification_passed=True,
            conflicts=("operators/local_search.py",),
            evaluate=lambda *_args: (_ for _ in ()).throw(
                AssertionError("Protocol must not run after a source conflict")
            ),
        )
    )
    basis = {
        "read_refs": ["history-0007"],
        "nearest_prior_refs": ["history-0007"],
        "material_delta": "Replay one materially distinct accepted mechanism.",
        "alternatives_considered": ["Discard the accepted branch head."],
        "observable_prediction": "The public screen should improve after replay.",
        "falsification_condition": "Reject if the public screen does not improve.",
    }
    branch.accepted_changes[0] = replace(
        branch.accepted_changes[0],
        changed_files=("operators/local_search.py", "registry.yaml"),
        selected_hypothesis_research_basis=basis,
    )
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    steps = []
    runner.registry = registry
    runner.campaign_id = "campaign-1"
    runner.record_step = steps.append

    result = runner.run_reconcile_step(branch)

    assert result.decision is None
    assert len(steps) == 1
    step = steps[0]
    assert step.decision is None
    assert step.hypothesis is branch.accepted_changes[0].hypothesis
    assert step.patch is branch.accepted_changes[0].patch
    assert step.base_champion_version == 2
    assert step.base_source_ref == "champion:v2"
    assert step.changed_files == (
        "operators/local_search.py",
        "registry.yaml",
    )
    assert step.selected_hypothesis_research_basis == basis
    assert step.execution_outcome.reason_code == "RECONCILE_SOURCE_CONFLICT"
    assert proposal_pre_protocol_observations([step])[0]["outcome"] == {
        "stage": "reconcile_source",
        "reason_code": "RECONCILE_SOURCE_CONFLICT",
        "checks": [],
    }
    history = project_research_history_step(step, problem_id="generic_demo")
    assert history is not None
    assert history["hypothesis"]["text"] == (
        branch.accepted_changes[0].hypothesis.hypothesis_text
    )
    assert history["patch"]["changes"][0]["file_path"] == (
        "operators/local_search.py"
    )
    summary = EvidenceRecorder(
        campaign_id="campaign-1",
        campaign_dir=tmp_path,
    )._build_summary_step(step)
    assert summary["decision"] is None
    assert summary["base_source_ref"] == "champion:v2"
    assert summary["changed_files"][-1] == "registry.yaml"
    row = next(
        event
        for event in registry.query_by_branch(branch.branch_id)
        if event["event_kind"] == "reconcile_research_rejection"
    )
    assert row["decision"] is None
    assert row["base_champion_version"] == 2
    assert row["base_source_ref"] == "champion:v2"
    assert json.loads(row["changed_files_json"])[-1] == "registry.yaml"
    assert json.loads(row["selected_hypothesis_research_basis_json"]) == basis


def test_reconcile_apply_failure_records_the_accepted_change() -> None:
    runner, _controller, branch, _workspaces, _applied, _rejected, _digests = (
        _runner(
            verification_passed=True,
            evaluate=lambda *_args: (_ for _ in ()).throw(
                AssertionError("Protocol must not run after apply failure")
            ),
        )
    )
    recorded = []
    runner.record_step = recorded.append
    runner.apply_reconcile_change = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        ValueError("accepted source cannot be applied")
    )

    result = runner.run_reconcile_step(branch)

    assert result.execution_outcome.reason_code == "RECONCILE_APPLY_FAILED"
    assert result.failure_stage == "reconcile_apply"
    assert len(recorded) == 1
    assert recorded[0].hypothesis is branch.accepted_changes[0].hypothesis
    assert recorded[0].patch is branch.accepted_changes[0].patch
    assert recorded[0].decision is None


def test_reconcile_two_change_chain_uses_one_staging_and_one_digest_pair() -> None:
    def not_evaluated(*_args, **_kwargs):
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="TEST_PROTOCOL_STOP",
            )
        )

    runner, controller, branch, _workspaces, applied, rejected, digests = _runner(
        verification_passed=True,
        evaluate=not_evaluated,
    )
    second_hypothesis = HypothesisProposal(
        hypothesis_text="Keep the second accepted file in the replay chain.",
        change_locus="local_search",
        action="modify",
        target_file="operators/second.py",
    )
    second_patch = PatchProposal(
        file_path="operators/second.py",
        action="modify",
        code_content="class Second: pass\n",
    )
    branch.accepted_changes.append(
        AcceptedBranchChange(
            hypothesis=second_hypothesis,
            patch=second_patch,
            before_sources=(
                AcceptedFileBeforeSource(
                    file_path="operators/second.py",
                    source="class Second: old\n",
                ),
            ),
        )
    )
    contract_bases: list[str] = []

    def validate_patch(*_args, **kwargs):
        contract_bases.append(kwargs["base_snapshot_path"])
        return ContractResult(passed=True, checks=())

    runner.contract_gate = SimpleNamespace(validate_patch=validate_patch)
    recorded_steps = []
    runner.record_step = recorded_steps.append

    runner.run_reconcile_step(branch)

    assert contract_bases == [
        "/tmp/reconcile-staging",
        "/tmp/reconcile-staging",
    ]
    assert applied == [
        "/tmp/reconcile-staging:operators/local_search.py",
        "/tmp/reconcile-staging:operators/second.py",
    ]
    assert digests == ["baseline", "verification", "recompute"]
    assert rejected == ["/tmp/reconcile-staging"]
    assert len(branch.accepted_changes) == 2
    assert recorded_steps[-1].patch is second_patch
    assert controller.get_branch(branch.branch_id).state is BranchState.BLOCKED_INFRA
