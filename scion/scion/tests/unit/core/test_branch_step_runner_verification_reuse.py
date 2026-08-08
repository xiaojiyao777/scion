from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
)
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.lineage.registry import LineageRegistry


def _branch(state: BranchState = BranchState.VALIDATING) -> Branch:
    return Branch(
        branch_id="branch-1",
        state=state,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        current_code_hash="verified-code-hash",
        last_clean_code_hash="verified-code-hash",
    )


def _hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Improve generic local search.",
        change_locus="solver_design",
        action="modify",
        target_file="solver.py",
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="def solve(*args, **kwargs):\n    return None\n",
    )


def _protocol_result(
    stage: ExperimentStage = ExperimentStage.VALIDATION,
) -> ProtocolResult:
    return ProtocolResult(
        stage=stage,
        stats=EvalStats(
            n_cases=3,
            wins=2,
            losses=1,
            ties=0,
            win_rate=0.67,
            median_delta=0.1,
            ci_low=0.01,
            ci_high=0.2,
        ),
        gate_outcome="pass",
        reason_codes=("validation_pass",),
        exposed_summary="validation aggregate",
        raw_metrics_ref="/tmp/validation-metrics.json",
    )


def _evaluated(
    decision: Decision,
    protocol_result: ProtocolResult,
) -> EvaluationExecutionResult:
    return EvaluationExecutionResult(
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.EVALUATED,
            reason_code="EVALUATION_COMPLETED",
        ),
        decision=decision,
        protocol_result=protocol_result,
        canary_result=CanaryResult(passed=True),
    )


def _runner_for_outcome_test(
    *,
    branch: Branch,
    evaluate,
    recorded_steps,
    finalized,
    registry,
) -> BranchStepRunner:
    hypothesis = _hypothesis()
    h_record = HypothesisRecord(
        hypothesis_id="hyp-outcome",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
    )
    branch_controller = BranchController()
    branch_controller.restore_branch(branch)
    return BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(code_snapshot_path="/tmp/champion"),
        branch_store=SimpleNamespace(save=lambda branch: None),
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: _patch()},
        branch_current_hypothesis={branch.branch_id: h_record},
        experiment_protocol_provider=lambda: object(),
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        persist_branch_state=lambda branch_id: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        evaluate=evaluate,
        apply_decision_and_finalize=lambda **kwargs: finalized.append(kwargs),
        record_step=recorded_steps.append,
        decision_reason_codes_for=lambda *args: None,
        run_explore_step=lambda branch: StepResult(action="explore"),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 2,
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
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
    assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
    assert result.decision is None
    assert steps[-1].protocol_result is None
    assert steps[-1].decision is None
    assert steps[-1].decision_reason_codes is None
    assert branch.state is BranchState.VALIDATING
    assert branch.branch_id in runner.branch_workspaces
    assert branch.branch_id in runner.branch_current_hypothesis
    durable = registry.get_latest_execution_outcome(branch_id=branch.branch_id)
    assert durable is not None
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
    assert result.execution_outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.decision is None
    assert steps[-1].protocol_result is None
    assert steps[-1].decision is None
    assert branch.state is BranchState.BLOCKED_INFRA
    assert branch.branch_evidence_summary["infra_resume_state"] == {
        "schema_version": "infra-resume-state.v1",
        "state": "frozen_testing",
    }
    assert branch.branch_id in runner.branch_workspaces
    assert branch.branch_id in runner.branch_current_hypothesis
    assert branch.branch_id in runner.branch_patches
    durable = registry.get_latest_execution_outcome(branch_id=branch.branch_id)
    assert durable is not None
    assert durable["reason_code"] == "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
    assert durable["provenance"]["raw_metrics_ref"] == ("/tmp/frozen-partial.json")


def test_eval_step_records_screening_verification_reuse_marker() -> None:
    branch = _branch()
    recorded_steps = []
    finalized = {}
    hypothesis = _hypothesis()
    h_record = HypothesisRecord(
        hypothesis_id="hyp-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
        hypothesis_text=hypothesis.hypothesis_text,
    )

    def apply_decision_and_finalize(**kwargs):
        finalized.update(kwargs)
        return StepResult(
            action="validate",
            branch_id=branch.branch_id,
            decision=Decision.QUEUE_FROZEN,
            reason="decision=queue_frozen",
        )

    runner = BranchStepRunner(
        branch_controller=SimpleNamespace(
            apply_decision=lambda branch_id, decision: None,
        ),
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion-hash",
        ),
        branch_store=SimpleNamespace(save=lambda branch: None),
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: _patch()},
        branch_current_hypothesis={branch.branch_id: h_record},
        experiment_protocol_provider=lambda: object(),
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        persist_branch_state=lambda branch_id: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        evaluate=lambda branch, workspace, hypothesis: _evaluated(
            Decision.QUEUE_FROZEN,
            _protocol_result(),
        ),
        apply_decision_and_finalize=apply_decision_and_finalize,
        record_step=recorded_steps.append,
        decision_reason_codes_for=lambda branch_id, protocol_result: (
            "validation_pass",
        ),
        decision_provenance_for=lambda branch_id: {},
        run_explore_step=lambda branch: StepResult(action="explore"),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 2,
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
    )

    result = runner.run_eval_step(branch)

    verification = finalized["verification_result"]
    check = verification.checks[0]
    step = recorded_steps[0]

    assert result.decision == Decision.QUEUE_FROZEN
    assert verification.passed is True
    assert check.name == "V0_screening_verification_reuse"
    assert check.metadata["verification_reused_from_screening"] is True
    assert check.metadata["strict_checks_rerun"] is False
    assert check.metadata["original_verification_audit_hash"]
    assert (
        "code_hash=verified-code-hash"
        in check.metadata["original_verification_audit_detail"]
    )
    assert "V1-V8 were not rerun" in check.detail
    assert step.verification_passed is True
    assert step.verification_detail is not None
    assert "V0_screening_verification_reuse" in step.verification_detail
    assert "original_verification_audit_hash=" in step.verification_detail


def test_eval_step_blocks_reuse_when_current_hash_drifted(tmp_path) -> None:
    branch = _branch()
    branch.current_code_hash = "drifted-code-hash"
    recorded_steps = []
    hypothesis = _hypothesis()
    h_record = HypothesisRecord(
        hypothesis_id="hyp-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
        hypothesis_text=hypothesis.hypothesis_text,
    )

    runner = BranchStepRunner(
        branch_controller=SimpleNamespace(
            apply_decision=lambda branch_id, decision: None,
        ),
        scheduler=Scheduler(),
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(code_snapshot_path="/tmp/champion"),
        branch_store=SimpleNamespace(save=lambda branch: None),
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: _patch()},
        branch_current_hypothesis={branch.branch_id: h_record},
        experiment_protocol_provider=lambda: object(),
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        persist_branch_state=lambda branch_id: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        evaluate=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("protocol should not run after verification drift")
        ),
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="validate"),
        record_step=recorded_steps.append,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        decision_provenance_for=lambda branch_id: {},
        run_explore_step=lambda branch: StepResult(action="explore"),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 2,
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        registry=LineageRegistry(str(tmp_path / "lineage.db")),
        campaign_id="campaign-1",
    )

    result = runner.run_eval_step(branch)

    assert result.failure_stage == "verification"
    assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
    assert branch.branch_id in runner.branch_current_hypothesis
    durable = runner.registry.get_latest_execution_outcome(branch_id=branch.branch_id)
    assert durable is not None
    assert durable["outcome"] == "not_evaluated"
    assert durable["reason_code"] == "EVAL_VERIFICATION_REUSE_INVALID"
    assert recorded_steps[0].verification_passed is False
    assert "current code hash/status does not match" in (
        recorded_steps[0].verification_detail or ""
    )
