from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.core.evidence_recording import EvidenceRecorder
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import (
    AttemptDisposition,
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    ResearchRejectionDisposition,
)
from scion.core.models import (
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    ProtocolResult,
    StepRecord,
)
from scion.core.step_result import StepResult
from scion.lineage.registry import LineageRegistry


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
        execution_outcome=outcome,
        execution_outcome_reason_code=f"TEST_{outcome.value.upper()}",
        execution_outcome_detail="typed outcome fixture",
        execution_outcome_provenance={"source": "unit", "nested": [1, True]},
    )


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
    queried = registry.get_latest_execution_outcome(
        campaign_id="campaign-1",
        branch_id=branch_id,
    )
    query_results = registry.query_execution_outcomes(
        campaign_id="campaign-1",
        branch_id=branch_id,
    )

    assert queried is not None
    assert query_results == [queried]
    assert {
        key: queried[key]
        for key in ("outcome", "reason_code", "detail", "provenance")
    } == record.to_primitive()

    projected_outcome = ExecutionOutcome(queried["outcome"])
    decision = Decision.CONTINUE_EXPLORE if outcome is ExecutionOutcome.EVALUATED else None
    protocol = _protocol() if outcome is ExecutionOutcome.EVALUATED else None
    step_result = StepResult(
        action="explore",
        branch_id=branch_id,
        decision=decision,
        execution_outcome=projected_outcome,
        execution_outcome_reason_code=queried["reason_code"],
        execution_outcome_detail=queried["detail"],
        execution_outcome_provenance=queried["provenance"],
    )
    step_record = _step(outcome, decision=decision, protocol_result=protocol)

    assert step_result.execution_outcome is outcome
    assert step_record.execution_outcome is outcome
    assert step_record.execution_outcome_provenance == record.provenance


def test_non_evaluated_outcome_rejects_decision_and_protocol() -> None:
    with pytest.raises(ValueError, match="cannot carry a Decision"):
        StepResult(
            action="explore",
            decision=Decision.ABANDON,
            execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
            execution_outcome_reason_code="CONTRACT_REJECTED",
        )

    with pytest.raises(ValueError, match="cannot carry a ProtocolResult"):
        _step(
            ExecutionOutcome.NOT_EVALUATED,
            protocol_result=_protocol(),
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


def test_contract_failure_is_research_rejected_without_decision(tmp_path: Path) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    hypothesis_text = "invalid hypothesis " * 40 + "complete-tail"

    registry.record_contract_failure(
        campaign_id="campaign-1",
        branch_id="branch-1",
        hypothesis_text=hypothesis_text,
        change_locus="solver.py:search",
        action="modify",
        target_file="solver.py",
        failure_reason="missing clean-fork claim",
    )

    events = registry.query_by_branch("branch-1")
    assert len(events) == 1
    event = events[0]
    assert event["event_kind"] == "contract_fail"
    assert event["hypothesis_text"] == hypothesis_text
    assert event["decision"] is None
    assert event["execution_outcome"] == "research_rejected"
    assert event["execution_outcome_reason_code"] == "CONTRACT_REJECTED"
    audit_payload = json.loads(event["audit_payload_json"])
    assert audit_payload["schema"] == "execution-outcome-event.v1"
    assert audit_payload["execution_outcome"]["outcome"] == "research_rejected"
    latest = registry.get_latest_execution_outcome(branch_id="branch-1")
    assert latest is not None
    assert latest["detail"] == "missing clean-fork claim"
    assert latest["provenance"]["owner"] == "outer_contract"


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
    assert registry.get_latest_execution_outcome(branch_id="branch-old") is None
    assert registry.rebuild_latest_execution_outcomes(
        campaign_id="campaign-old"
    ) == {}

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


def test_rebuild_uses_latest_append_only_outcome_per_branch(tmp_path: Path) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    for outcome in (
        ExecutionOutcome.NOT_EVALUATED,
        ExecutionOutcome.INTERRUPTED,
    ):
        registry.record_execution_outcome(
            campaign_id="campaign-1",
            branch_id="branch-1",
            record=ExecutionOutcomeRecord(
                outcome=outcome,
                reason_code=outcome.value.upper(),
            ),
        )

    rebuilt = registry.rebuild_latest_execution_outcomes(campaign_id="campaign-1")
    assert rebuilt["branch-1"]["outcome"] == "interrupted"


def test_summary_and_status_project_explicit_non_evaluated_without_screening(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)
    step = _step(ExecutionOutcome.NOT_EVALUATED)

    status = recorder.write_status(
        last_result=StepResult(
            action="explore",
            branch_id=step.branch_id,
            execution_outcome=ExecutionOutcome.NOT_EVALUATED,
            execution_outcome_reason_code="TEST_NOT_EVALUATED",
            execution_outcome_detail="typed outcome fixture",
            execution_outcome_provenance={"source": "unit"},
        )
    )
    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="config",
            code_snapshot_path="snapshot",
            code_snapshot_hash="hash",
        ),
    )

    assert status["last_execution_outcome"]["outcome"] == "not_evaluated"
    assert status["last_result"]["execution_outcome_reason_code"] == (
        "TEST_NOT_EVALUATED"
    )
    assert summary["execution_outcome_counts"] == {
        "evaluated": 0,
        "research_rejected": 0,
        "not_evaluated": 1,
        "blocked_infra": 0,
        "resource_exhausted": 0,
        "interrupted": 0,
    }
    assert summary["last_execution_outcome"]["outcome"] == "not_evaluated"
    assert summary["steps"][0]["execution_outcome"] == "not_evaluated"
    assert summary["steps"][0]["execution_outcome_reason_code"] == (
        "TEST_NOT_EVALUATED"
    )
    assert summary["steps"][0]["screened_experiment"] is False
    assert summary["steps"][0]["screened_experiment_effective"] is False
    assert step.execution_outcome is ExecutionOutcome.NOT_EVALUATED


def test_status_and_summary_project_typed_research_rejection_disposition(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="campaign-1", campaign_dir=tmp_path)
    marker = ResearchRejectionDisposition(
        disposition=AttemptDisposition.ATTEMPT_REJECT_TO_BASE,
        rejection_phase="verification",
        lineage_event_id="event-1",
    )
    result = StepResult(
        action="explore",
        branch_id="branch-1",
        execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
        execution_outcome_reason_code="VERIFICATION_LIGHT_REJECTED",
        attempt_disposition=marker,
    )
    step = _step(ExecutionOutcome.RESEARCH_REJECTED)
    step.attempt_disposition = marker

    status = recorder.write_status(last_result=result)
    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="config",
            code_snapshot_path="snapshot",
            code_snapshot_hash="hash",
        ),
    )

    assert status["last_result"]["attempt_disposition"] == marker.to_primitive()
    assert summary["steps"][0]["attempt_disposition"] == marker.to_primitive()
