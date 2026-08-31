from __future__ import annotations

from inspect import Parameter, signature
from types import SimpleNamespace
from typing import Any

import pytest

from scion.core.campaign import CampaignManager
from scion.core.campaign_loop import CampaignLoop
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import Decision, EvalStats, ExperimentStage, ProtocolResult
from scion.core.step_result import StepResult


def _protocol(stage: str) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage(stage),
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
        reason_codes=(f"{stage.upper()}_PASS",),
        exposed_summary="positive",
        raw_metrics_ref=f"metrics/{stage}.json",
    )


def _evaluated(stage: str = "screening", *, branch_id: str = "b1") -> StepResult:
    return StepResult(
        action="explore",
        branch_id=branch_id,
        reason="formal result",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.EVALUATED,
            reason_code="PROTOCOL_EVALUATED",
        ),
        protocol_result=_protocol(stage),
    )


def _non_evaluated(outcome: ExecutionOutcome) -> StepResult:
    return StepResult(
        action="stopped",
        branch_id="b1",
        reason="typed terminal outcome",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=outcome,
            reason_code="CURRENT_CALL_NOT_EVALUATED",
        ),
    )


def _run(
    results: list[StepResult],
    *,
    rounds: int,
) -> SimpleNamespace:
    calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "run_result" in kwargs:
            statuses.append(kwargs["run_result"].to_projection())

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        run_one_step=run_one_step,
        write_terminal_artifacts=lambda _result: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )
    result = loop.run(requested_rounds=rounds)
    return SimpleNamespace(
        calls=calls,
        statuses=statuses,
        stopped=stopped_reasons,
        result=result,
    )


def _rejected() -> StepResult:
    return StepResult(
        action="explore",
        branch_id="b1",
        reason="candidate rejected",
        failure_stage="verification",
        failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="VERIFICATION_LIGHT_REJECTED",
        ),
    )


def test_round_target_is_required_and_named_requested_rounds() -> None:
    for run_method in (CampaignLoop.run, CampaignManager.run):
        parameters = signature(run_method).parameters
        assert "max_rounds" not in parameters
        assert parameters["requested_rounds"].default is Parameter.empty


@pytest.mark.parametrize(
    "outcome",
    [
        ExecutionOutcome.NOT_EVALUATED,
        ExecutionOutcome.BLOCKED_INFRA,
        ExecutionOutcome.RESOURCE_EXHAUSTED,
        ExecutionOutcome.INTERRUPTED,
    ],
)
def test_typed_non_evaluated_outcome_stops_current_invocation(
    outcome: ExecutionOutcome,
) -> None:
    run = _run([_non_evaluated(outcome), _evaluated()], rounds=1)

    assert run.calls == 1
    assert f"execution_{outcome.value}" in run.stopped
    assert run.statuses[-1]["evaluated_rounds"] == 0
    assert run.statuses[-1]["scheduled_calls"] == 1
    assert run.statuses[-1]["execution_outcome_counts"][outcome.value] == 1


def test_requested_rounds_count_only_formal_evaluated_results() -> None:
    run = _run(
        [
            _evaluated("screening", branch_id="b1"),
            _evaluated("validation", branch_id="b2"),
        ],
        rounds=2,
    )

    assert run.calls == 2
    status = run.statuses[-1]
    assert status["requested_rounds"] == 2
    assert status["evaluated_rounds"] == 2
    assert run.result.completed is True
    assert status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 1,
        "frozen": 0,
    }
    assert status["formal_screened_candidates"] == 1
    assert status["execution_outcome_counts"]["evaluated"] == 2
    assert status["unknown_outcome_count"] == 0
    assert "requested_rounds_completed" in run.stopped


def test_evaluated_without_formal_protocol_projection_stops_without_counting() -> None:
    result = StepResult(
        action="explore",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.EVALUATED,
            reason_code="RESULT_PRESENT_BUT_NOT_FORMAL",
        ),
    )
    run = _run([result, _evaluated()], rounds=1)

    assert run.calls == 1
    assert "evaluated_without_formal_protocol_result" in run.stopped
    assert run.statuses[-1]["evaluated_rounds"] == 0


def test_result_without_outcome_is_not_counted_as_an_attempt() -> None:
    run = _run([StepResult(action="skip"), _evaluated()], rounds=1)

    assert run.calls == 2
    assert "requested_rounds_completed" in run.stopped
    assert run.statuses[-1]["evaluated_rounds"] == 1
    assert run.statuses[-1]["scheduled_calls"] == 1
    assert run.statuses[-1]["unknown_outcome_count"] == 0


def test_loop_status_has_no_provider_attempt_or_quality_budget_fields() -> None:
    run = _run([_evaluated()], rounds=1)
    status = run.statuses[-1]

    forbidden = {
        "proposal_attempt_limit",
        "proposal_attempts",
        "proposal_quality_loop_limit",
        "fresh_runtime_replay_drain_limit",
        "stage_transition_drain_limit",
        "pending_retry",
    }
    assert forbidden.isdisjoint(status)


@pytest.mark.parametrize("rejection_count", [1, 2])
def test_committed_rejections_schedule_forward_until_formal_target(
    rejection_count: int,
) -> None:
    rejected = [_rejected() for _index in range(rejection_count)]
    run = _run([*rejected, _evaluated()], rounds=1)

    assert run.calls == rejection_count + 1
    assert run.statuses[-1]["evaluated_rounds"] == 1
    assert run.statuses[-1]["scheduled_calls"] == rejection_count + 1
    assert run.statuses[-1]["failure_categories"] == {
        "research_rejected": rejection_count
    }
    assert run.statuses[-1]["execution_outcome_counts"]["research_rejected"] == (
        rejection_count
    )
    assert run.statuses[-1]["execution_outcome_counts"]["evaluated"] == 1
    assert "research_rejection_audit" not in run.statuses[-1]
    assert "requested_rounds_completed" in run.stopped


def test_repeated_research_rejections_are_audited_and_schedule_forward() -> None:
    rejected = _rejected()
    run = _run([rejected, rejected, _evaluated()], rounds=1)

    assert run.calls == 3
    assert run.statuses[-1]["evaluated_rounds"] == 1
    assert run.statuses[-1]["scheduled_calls"] == 3
    assert run.statuses[-1]["failure_categories"] == {"research_rejected": 2}
    assert "requested_rounds_completed" in run.stopped


def test_typed_reconcile_housekeeping_schedules_forward_through_36_stages() -> None:
    state_only_result = StepResult(
        action="reconcile",
        branch_id="old-promoted-peer",
        reason="no patch to reconcile",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="RECONCILE_NO_ACCEPTED_CHANGES",
            provenance={"stage": "reconcile"},
        ),
    )
    stages = ("screening", "validation", "frozen")
    formal_results = [
        _evaluated(stages[index % len(stages)], branch_id=f"forward-{index}")
        for index in range(36)
    ]

    run = _run([state_only_result, *formal_results], rounds=36)

    assert run.calls == 37
    status = run.statuses[-1]
    assert status["evaluated_rounds"] == 36
    assert status["scheduled_calls"] == 36
    assert status["execution_outcome_counts"]["not_evaluated"] == 0
    assert status["protocol_stage_counts"] == {
        "screening": 12,
        "validation": 12,
        "frozen": 12,
    }
    assert "research_rejection_audit" not in status
    assert "research_rejection_disposition_missing" not in run.stopped
    assert "requested_rounds_completed" in run.stopped


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("decision", Decision.ABANDON),
        ("failure_stage", "verification"),
        ("failure_detail", "unbound failure"),
        ("failure_category", "research_rejected"),
        ("stopped", True),
    ),
)
def test_result_without_outcome_is_never_counted_from_other_fields(
    field: str,
    value: object,
) -> None:
    state_only_result = StepResult(
        action="reconcile",
        branch_id="stale-branch",
    )
    setattr(state_only_result, field, value)

    run = _run([state_only_result, _evaluated()], rounds=1)

    assert run.calls == 2
    assert run.statuses[-1]["evaluated_rounds"] == 1
    assert "requested_rounds_completed" in run.stopped


@pytest.mark.parametrize("failure_stage", ("patch_contract", "verification"))
def test_typed_rejection_schedules_forward_without_a_second_audit_marker(
    failure_stage: str,
) -> None:
    reason_code = f"{failure_stage.upper()}_REJECTED"
    rejected = StepResult(
        action="reconcile",
        branch_id="stale-branch",
        reason="reconcile candidate rejected",
        failure_stage=failure_stage,
        failure_detail="candidate rejected before Protocol",
        failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=reason_code,
        ),
    )

    run = _run([rejected, _evaluated()], rounds=1)

    assert run.calls == 2
    status = run.statuses[-1]
    assert status["evaluated_rounds"] == 1
    assert status["failure_categories"] == {"research_rejected": 1}
    assert "research_rejection_audit" not in status
    assert "requested_rounds_completed" in run.stopped
