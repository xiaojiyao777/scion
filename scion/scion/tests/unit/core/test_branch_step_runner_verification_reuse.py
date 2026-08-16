from __future__ import annotations

from contextlib import nullcontext

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
)
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.lineage.registry import LineageRegistry


def _branch(state: BranchState = BranchState.VALIDATING) -> Branch:
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve generic local search.",
        change_locus="solver_design",
        action="modify",
        target_file="solver.py",
    )
    return Branch(
        branch_id="branch-1",
        state=state,
        base_champion_id=1,
        current_code_hash="verified-code-hash",
        hypothesis=hypothesis,
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="def solve(*args, **kwargs):\n    return None\n",
    )


def _runner_for_outcome_test(
    *,
    branch: Branch,
    evaluate,
    recorded_steps,
    finalized,
    registry,
) -> BranchStepRunner:
    assert branch.hypothesis is not None
    branch_controller = BranchController()
    branch_controller._branches[branch.branch_id] = branch
    return BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path="/tmp/champion",
        ),
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_patches={branch.branch_id: _patch()},
        experiment_protocol_provider=lambda: object(),
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        setup_workspace=lambda *args, **kwargs: None,
        evaluate=evaluate,
        apply_decision_and_finalize=lambda **kwargs: finalized.append(kwargs),
        record_step=recorded_steps.append,
        run_explore_step=lambda branch: StepResult(action="explore"),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 2,
        registry=registry,
        campaign_id="campaign-1",
    )


def test_eval_step_not_evaluated_skips_finalizer_and_preserves_candidate(
    tmp_path,
) -> None:
    branch = _branch()
    steps = []
    finalized = []
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    runner = _runner_for_outcome_test(
        branch=branch,
        evaluate=lambda *args: EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="EVALUATION_EXCEPTION",
                detail="protocol boom",
                provenance={"stage": "validation"},
            )
        ),
        recorded_steps=steps,
        finalized=finalized,
        registry=registry,
    )

    result = runner.run_eval_step(branch)

    assert finalized == []
    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert result.decision is None
    assert steps[-1].protocol_result is None
    assert steps[-1].decision is None
    assert steps[-1].decision_reason_codes is None
    assert branch.state is BranchState.BLOCKED_INFRA
    assert branch.branch_id in runner.branch_workspaces
    assert branch.hypothesis is not None
    durable = registry.query_execution_outcomes(branch_id=branch.branch_id)[0]
    assert durable["reason_code"] == "EVALUATION_EXCEPTION"


def test_eval_step_champion_evidence_block_preserves_candidate_and_stage(
    tmp_path,
) -> None:
    branch = _branch(BranchState.FROZEN_TESTING)
    steps = []
    finalized = []
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    runner = _runner_for_outcome_test(
        branch=branch,
        evaluate=lambda *args: EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="EVALUATION_CHAMPION_EVIDENCE_BLOCKED",
                detail="champion evidence timeout",
                provenance={
                    "stage": "frozen",
                    "raw_metrics_ref": "/tmp/frozen-partial.json",
                },
            )
        ),
        recorded_steps=steps,
        finalized=finalized,
        registry=registry,
    )

    result = runner.run_eval_step(branch)

    assert finalized == []
    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.decision is None
    assert steps[-1].protocol_result is None
    assert steps[-1].decision is None
    assert branch.state is BranchState.BLOCKED_INFRA
    assert branch.branch_id in runner.branch_workspaces
    assert branch.hypothesis is not None
    assert branch.branch_id in runner.branch_patches
    durable = registry.query_execution_outcomes(branch_id=branch.branch_id)[0]
    assert durable["reason_code"] == "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
    assert durable["provenance"]["raw_metrics_ref"] == "/tmp/frozen-partial.json"
