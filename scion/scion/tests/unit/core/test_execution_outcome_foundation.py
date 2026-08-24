from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from scion.core.campaign_loop import CampaignRunResult
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.models import (
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    ProtocolResult,
    StepRecord,
)
from scion.core.step_result import StepResult
from scion.core.evidence_recording.status import project_last_result
from scion.lineage.registry import LineageRegistry


def _run_projection(outcome: ExecutionOutcome) -> dict[str, object]:
    result = CampaignRunResult.empty(1)
    counts = dict(result.execution_outcome_counts)
    counts[outcome.value] = 1
    return replace(
        result,
        scheduled_calls=1,
        stop_reason=f"execution_{outcome.value}",
        execution_outcome_counts=counts,
        last_execution_outcome={
            "outcome": outcome.value,
            "reason_code": f"TEST_{outcome.value.upper()}",
        },
    ).to_projection()


def _operator_state() -> dict[str, object]:
    return {
        "campaign_id": "campaign-1",
        "proposal_runtime_mode": "direct_v3",
        "champion_version": 1,
        "branches": [],
    }


def _hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="test an explicit execution outcome",
        change_locus="solver.py:search",
        action="modify",
        target_file="solver.py",
    )


def _protocol() -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=1,
            wins=1,
            losses=0,
            ties=0,
            win_rate=1.0,
            median_delta=1.0,
            ci_low=0.1,
            ci_high=1.9,
        ),
        gate_outcome="pass",
        reason_codes=("SCREENING_PASS",),
        exposed_summary="positive",
        raw_metrics_ref="metrics.json",
    )


def _step(
    outcome: ExecutionOutcome,
    *,
    decision: Decision | None = None,
    protocol_result: ProtocolResult | None = None,
    execution_outcome: ExecutionOutcomeRecord | None = None,
) -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id=f"branch-{outcome.value}",
        hypothesis=_hypothesis(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=None,
        failure_detail=None,
        execution_outcome=(
            execution_outcome
            or ExecutionOutcomeRecord(
                outcome=outcome,
                reason_code=f"TEST_{outcome.value.upper()}",
                detail="typed outcome fixture",
                provenance={"source": "unit", "nested": [1, True]},
            )
        ),
    )


def _hypothesis_free_step(**overrides: object) -> StepRecord:
    values: dict[str, object] = {
        "round_num": 1,
        "branch_id": "branch-no-hypothesis",
        "hypothesis": None,
        "patch": None,
        "contract_passed": None,
        "verification_passed": None,
        "protocol_result": None,
        "decision": None,
        "failure_stage": "proposal_hypothesis",
        "failure_detail": "HYPOTHESIS_RESEARCH_ABSTAINED",
        "execution_outcome": ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
            provenance={"stage": "proposal_hypothesis"},
        ),
    }
    values.update(overrides)
    return StepRecord(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("outcome", list(ExecutionOutcome))
def test_six_state_roundtrip_event_query_step_result_and_step_record(
    tmp_path: Path,
    outcome: ExecutionOutcome,
) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    record = ExecutionOutcomeRecord(
        outcome=outcome,
        reason_code=f"TEST_{outcome.value.upper()}",
        detail="typed outcome fixture",
        provenance={"source": "unit", "nested": [1, True]},
    )
    branch_id = f"branch-{outcome.value}"

    registry.record_execution_outcome(
        campaign_id="campaign-1",
        branch_id=branch_id,
        record=record,
        stage="screening",
    )
    query_results = registry.query_execution_outcomes(
        campaign_id="campaign-1",
        branch_id=branch_id,
    )
    queried = query_results[0]

    assert query_results == [queried]
    assert {
        key: queried[key]
        for key in ("outcome", "reason_code", "detail", "provenance")
    } == record.to_primitive()

    projected_outcome = ExecutionOutcomeRecord.from_primitive(queried)
    decision = Decision.CONTINUE_EXPLORE if outcome is ExecutionOutcome.EVALUATED else None
    protocol = _protocol() if outcome is ExecutionOutcome.EVALUATED else None
    step_result = StepResult(
        action="explore",
        branch_id=branch_id,
        decision=decision,
        protocol_result=protocol,
        execution_outcome=projected_outcome,
    )
    step_record = _step(
        outcome,
        decision=decision,
        protocol_result=protocol,
        execution_outcome=projected_outcome,
    )

    assert step_result.execution_outcome == record
    assert step_record.execution_outcome == record
    assert step_result.execution_outcome is step_record.execution_outcome
    assert step_record.execution_outcome.provenance == record.provenance


def test_non_evaluated_outcome_rejects_decision_and_protocol() -> None:
    with pytest.raises(ValueError, match="cannot carry a Decision"):
        StepResult(
            action="explore",
            decision=Decision.ABANDON,
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="CONTRACT_REJECTED",
            ),
        )

    with pytest.raises(ValueError, match="cannot carry a ProtocolResult"):
        _step(
            ExecutionOutcome.NOT_EVALUATED,
            protocol_result=_protocol(),
        )


@pytest.mark.parametrize(
    "override",
    (
        {"execution_outcome": None},
        {
            "execution_outcome": ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="EVALUATED",
                provenance={"stage": "proposal_hypothesis"},
            )
        },
        {"failure_stage": "proposal_code"},
        {"patch": object()},
        {"contract_passed": False},
        {"verification_passed": False},
        {"protocol_result": _protocol()},
        {"decision": Decision.CONTINUE_EXPLORE},
        {"canary_result": object()},
        {"candidate_parent_scope": "declared_champion"},
        {"decision_reason_codes": ()},
        {"decision_engine_reason_codes": ("SENTINEL",)},
        {"diagnostic_reason_codes": ("SENTINEL",)},
        {"bypass_reason_codes": ("SENTINEL",)},
        {"contract_diagnostics": ({"name": "SENTINEL"},)},
        {"failure_detail": "RAW_SENTINEL"},
        {
            "execution_outcome": ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                detail="RAW_SENTINEL",
                provenance={"stage": "proposal_hypothesis"},
            )
        },
        {
            "execution_outcome": ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                provenance={
                    "stage": "proposal_hypothesis",
                    "phase": "hypothesis",
                },
            )
        },
    ),
)
def test_hypothesis_free_step_rejects_noncanonical_payloads(
    override: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="hypothesis-free"):
        _hypothesis_free_step(**override)


def test_step_values_reject_a_bare_outcome_enum() -> None:
    with pytest.raises(TypeError, match="ExecutionOutcomeRecord"):
        StepResult(
            action="explore",
            execution_outcome=ExecutionOutcome.NOT_EVALUATED,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="ExecutionOutcomeRecord"):
        StepRecord(
            round_num=1,
            branch_id="branch-1",
            hypothesis=_hypothesis(),
            patch=None,
            contract_passed=False,
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage=None,
            failure_detail=None,
            execution_outcome=ExecutionOutcome.NOT_EVALUATED,  # type: ignore[arg-type]
        )


def test_evaluation_execution_result_is_not_a_tuple_api() -> None:
    result = EvaluationExecutionResult(
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="EVALUATION_EXCEPTION",
        )
    )

    with pytest.raises(TypeError):
        tuple(result)


def test_historical_row_without_outcome_remains_readable_and_unknown(
    tmp_path: Path,
) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    registry.record_event(
        {
            "campaign_id": "campaign-old",
            "branch_id": "branch-old",
            "hypothesis_text": "historical",
        }
    )

    events = registry.query_by_branch("branch-old")
    assert len(events) == 1
    assert events[0]["execution_outcome"] is None
    assert registry.query_execution_outcomes(branch_id="branch-old") == []

    historical_step = StepRecord(
        round_num=1,
        branch_id="branch-old",
        hypothesis=_hypothesis(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=_protocol(),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )
    assert historical_step.execution_outcome is None


def test_generic_event_writer_cannot_bypass_typed_outcome_owner(
    tmp_path: Path,
) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))

    with pytest.raises(ValueError, match="record_execution_outcome"):
        registry.record_event(
            {
                "campaign_id": "campaign-1",
                "branch_id": "branch-1",
                "execution_outcome": "not_evaluated",
            }
        )


def test_summary_and_status_project_explicit_non_evaluated_without_screening(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)
    step = _step(ExecutionOutcome.NOT_EVALUATED)

    last_result = StepResult(
        action="explore",
        branch_id=step.branch_id,
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="TEST_NOT_EVALUATED",
            detail="typed outcome fixture",
            provenance={"source": "unit"},
        ),
    )
    state = _operator_state()
    state["last_result"] = project_last_result(last_result)
    run_projection = _run_projection(ExecutionOutcome.NOT_EVALUATED)
    status = recorder.write_status(state=state, run_result=run_projection)
    summary = recorder.write_campaign_summary(
        state=state,
        run_result=run_projection,
        step_history=[step],
    )

    assert status["run_result"]["last_execution_outcome"]["outcome"] == (
        "not_evaluated"
    )
    assert status["last_result"]["execution_outcome"]["reason_code"] == (
        "TEST_NOT_EVALUATED"
    )
    assert summary["run_result"]["execution_outcome_counts"] == {
        "evaluated": 0,
        "research_rejected": 0,
        "not_evaluated": 1,
        "blocked_infra": 0,
        "resource_exhausted": 0,
        "interrupted": 0,
    }
    assert summary["run_result"]["last_execution_outcome"]["outcome"] == (
        "not_evaluated"
    )
    assert summary["steps"][0]["execution_outcome"]["outcome"] == "not_evaluated"
    assert summary["steps"][0]["execution_outcome"]["reason_code"] == (
        "TEST_NOT_EVALUATED"
    )
    assert "screened_experiment" not in summary["steps"][0]
    assert "screened_experiment_effective" not in summary["steps"][0]
    assert step.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED


def test_status_and_summary_use_the_single_research_rejection_outcome(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)
    result = StepResult(
        action="explore",
        branch_id="branch-1",
        failure_stage="verification",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="VERIFICATION_LIGHT_REJECTED",
        ),
    )
    step = _step(ExecutionOutcome.RESEARCH_REJECTED)

    state = _operator_state()
    state["last_result"] = project_last_result(result)
    run_projection = _run_projection(ExecutionOutcome.RESEARCH_REJECTED)
    status = recorder.write_status(state=state, run_result=run_projection)
    summary = recorder.write_campaign_summary(
        state=state,
        run_result=run_projection,
        step_history=[step],
    )

    assert status["last_result"]["execution_outcome"]["outcome"] == (
        "research_rejected"
    )
    assert summary["steps"][0]["execution_outcome"]["outcome"] == (
        "research_rejected"
    )
    assert "attempt_disposition" not in status["last_result"]
    assert "attempt_disposition" not in summary["steps"][0]


@pytest.mark.parametrize(
    "stage",
    ("proposal_hypothesis", "proposal_code"),
)
def test_public_proposal_failure_status_and_summary_drop_provider_detail(
    tmp_path: Path,
    stage: str,
) -> None:
    sentinel = (
        "RAW_SENTINEL H_BASIS_SENTINEL PROBE_SENTINEL RESERVED_SENTINEL"
    )
    original_outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code=(
            "HYPOTHESIS_RESEARCH_ABSTAINED"
            if stage == "proposal_hypothesis"
            else "PATCH_PROPOSAL_INVALID"
        ),
        detail=sentinel,
        provenance={
            "stage": stage,
            "phase": stage,
            "exception_type": sentinel,
        },
    )
    result = StepResult(
        action="explore",
        branch_id="branch-1",
        reason=sentinel,
        failure_stage=stage,
        failure_detail=sentinel,
        execution_outcome=original_outcome,
    )

    projected = project_last_result(result)

    assert projected["reason"] == original_outcome.reason_code
    assert projected["execution_outcome"] == {
        "outcome": "research_rejected",
        "reason_code": original_outcome.reason_code,
        "stage": stage,
    }
    assert sentinel not in str(projected)

    durable_outcome = (
        ExecutionOutcomeRecord(
            outcome=original_outcome.outcome,
            reason_code=original_outcome.reason_code,
            provenance={"stage": stage},
        )
        if stage == "proposal_hypothesis"
        else original_outcome
    )
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=None if stage == "proposal_hypothesis" else _hypothesis(),
        patch=None,
        contract_passed=None if stage == "proposal_hypothesis" else True,
        verification_passed=None if stage == "proposal_hypothesis" else False,
        protocol_result=None,
        decision=None,
        failure_stage=stage,
        failure_detail=(
            original_outcome.reason_code
            if stage == "proposal_hypothesis"
            else sentinel
        ),
        execution_outcome=durable_outcome,
    )
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)
    summary = recorder.write_campaign_summary(
        state=_operator_state(),
        run_result=_run_projection(ExecutionOutcome.RESEARCH_REJECTED),
        step_history=[step],
    )

    assert summary["steps"][0]["failure_detail"] == original_outcome.reason_code
    assert summary["steps"][0]["execution_outcome"] == {
        "outcome": "research_rejected",
        "reason_code": original_outcome.reason_code,
        "detail": "",
        "provenance": {"stage": stage},
    }
    assert sentinel not in str(summary)


@pytest.mark.parametrize(
    ("failure_stage", "provenance_stage"),
    (
        ("proposal_code", "workspace"),
        ("workspace", "proposal_code"),
    ),
)
def test_summary_sanitizes_proposal_failure_from_either_stage_fact(
    tmp_path: Path,
    failure_stage: str,
    provenance_stage: str,
) -> None:
    sentinel = "RAW_PROVIDER_DETAIL_SENTINEL"
    outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code="PATCH_PROPOSAL_INVALID",
        detail=sentinel,
        provenance={
            "stage": provenance_stage,
            "exception_type": sentinel,
        },
    )
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=_hypothesis(),
        patch=None,
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage=failure_stage,
        failure_detail=sentinel,
        execution_outcome=outcome,
    )
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)

    summary = recorder.write_campaign_summary(
        state=_operator_state(),
        run_result=_run_projection(ExecutionOutcome.RESEARCH_REJECTED),
        step_history=[step],
    )

    assert summary["steps"][0]["failure_detail"] == "PATCH_PROPOSAL_INVALID"
    assert summary["steps"][0]["failure_stage"] == "proposal_code"
    assert summary["steps"][0]["execution_outcome"] == {
        "outcome": "research_rejected",
        "reason_code": "PATCH_PROPOSAL_INVALID",
        "detail": "",
        "provenance": {"stage": "proposal_code"},
    }
    assert sentinel not in str(summary)
