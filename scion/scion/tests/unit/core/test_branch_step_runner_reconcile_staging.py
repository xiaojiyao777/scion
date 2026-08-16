"""Stale-reconcile staging ownership tests."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    BranchState,
    ChampionState,
    CheckResult,
    ContractResult,
    HypothesisProposal,
    PatchProposal,
    VerificationResult,
)
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.core.workspace_service import CandidateWorkspace


def _champion(version: int) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={},
        code_snapshot_path=f"/tmp/champion-{version}",
    )


def _runner(*, verification_passed: bool, evaluate):
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
    workspaces = {branch.branch_id: "/tmp/old-branch"}
    applied: list[str] = []
    rejected: list[str] = []

    class _VerificationGate:
        def run(self, *_args, **_kwargs):
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

    def apply_candidate(base_workspace, _patch, **_kwargs):
        applied.append(base_workspace)
        return CandidateWorkspace(
            workspace="/tmp/reconcile-staging",
            source_digest="candidate",
        )

    def verify_candidate(candidate):
        return candidate

    def reject_candidate(candidate):
        rejected.append(candidate.workspace)

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
        apply_reconcile_candidate=apply_candidate,
        verify_reconcile_candidate=verify_candidate,
        reject_reconcile_candidate=reject_candidate,
    )
    return runner, controller, branch, workspaces, applied, rejected


def test_reconcile_verification_failure_rejects_staging_before_abandoning() -> None:
    runner, controller, branch, _workspaces, applied, rejected = _runner(
        verification_passed=False,
        evaluate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("Protocol must not run after failed verification")
        ),
    )

    result = runner.run_reconcile_step(branch)

    assert applied == ["/tmp/champion-2"]
    assert rejected == ["/tmp/reconcile-staging"]
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

    runner, controller, branch, workspaces, applied, rejected = _runner(
        verification_passed=True,
        evaluate=not_evaluated,
    )

    result = runner.run_reconcile_step(branch)

    current = controller.get_branch(branch.branch_id)
    assert applied == ["/tmp/champion-2"]
    assert rejected == ["/tmp/reconcile-staging"]
    assert observed == [("explore", "/tmp/reconcile-staging")]
    assert workspaces[branch.branch_id] == "/tmp/old-branch"
    assert current.state is BranchState.BLOCKED_INFRA
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
