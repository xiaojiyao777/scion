"""Stale-reconcile staging ownership tests."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.candidate_evaluation import candidate_evaluation
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    BranchState,
    ChampionState,
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    VerificationResult,
)
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult


def _champion(version: int) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=f"/tmp/champion-{version}",
        code_snapshot_hash=f"champion-{version}",
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
    record = HypothesisRecord(
        hypothesis_id="reconcile-hypothesis",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
    )
    workspaces = {branch.branch_id: "/tmp/old-branch"}
    applied: list[tuple[str, bool]] = []
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

    def apply_candidate(_branch, base_workspace, _patch, **kwargs):
        applied.append((base_workspace, kwargs["remember_patch"]))
        workspaces[branch.branch_id] = "/tmp/reconcile-staging"
        return SimpleNamespace(
            workspace="/tmp/reconcile-staging", code_hash="candidate"
        )

    def reject_candidate(_branch, workspace):
        rejected.append(workspace)
        workspaces[branch.branch_id] = "/tmp/reconcile-base"

    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: new_champion,
        branch_store=SimpleNamespace(save=lambda _branch: None),
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
        branch_current_hypothesis={branch.branch_id: record},
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
        persist_branch_state=lambda _branch_id: None,
        setup_workspace=lambda *_args, **_kwargs: "/tmp/reconcile-base",
        apply_patch=lambda *_args, **_kwargs: None,
        evaluate=evaluate,
        apply_decision_and_finalize=lambda **_kwargs: StepResult(action="reconcile"),
        record_step=lambda _step: None,
        decision_reason_codes_for=lambda *_args: None,
        run_explore_step=lambda _branch: StepResult(action="explore"),
        run_eval_step_callback=lambda _branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda _branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        hypothesis_store=SimpleNamespace(mark_status=lambda *_args: None),
        apply_reconcile_candidate=apply_candidate,
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

    assert applied == [("/tmp/reconcile-base", False)]
    assert rejected == ["/tmp/reconcile-staging"]
    assert result.failure_stage == "verification"
    assert controller.get_branch(branch.branch_id).state is BranchState.ABANDONED


def test_reconcile_success_enters_protocol_with_pending_staging_candidate() -> None:
    observed: list[tuple[str, str]] = []

    def not_evaluated(branch, workspace, _hypothesis):
        observed.append((branch.state.value, workspace))
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="TEMPORARY_PROTOCOL_FAILURE",
                detail="retry this staging candidate",
            )
        )

    runner, controller, branch, workspaces, applied, rejected = _runner(
        verification_passed=True,
        evaluate=not_evaluated,
    )

    result = runner.run_reconcile_step(branch)

    restored = controller.get_branch(branch.branch_id)
    assert applied == [("/tmp/reconcile-base", False)]
    assert rejected == []
    assert observed == [("explore", "/tmp/reconcile-staging")]
    assert workspaces[branch.branch_id] == "/tmp/reconcile-staging"
    assert restored.state is BranchState.EXPLORE
    assert candidate_evaluation(restored) == {
        "status": "pending",
        "hypothesis_id": "reconcile-hypothesis",
        "kind": "reconcile",
    }
    assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
