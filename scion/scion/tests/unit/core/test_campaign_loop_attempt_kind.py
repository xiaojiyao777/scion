from __future__ import annotations

from inspect import Parameter, signature
from types import SimpleNamespace
from typing import Any

import pytest

from scion.core.campaign_loop import CampaignLoop, _attempt_kind
from scion.core.campaign import CampaignManager
from scion.core.execution_outcome import (
    AttemptDisposition,
    ExecutionOutcome,
    ResearchRejectionDisposition,
)
from scion.core.models import Decision
from scion.core.step_result import StepResult


def _evaluated(stage: str = "screening", *, branch_id: str = "b1") -> StepResult:
    return StepResult(
        action="explore",
        branch_id=branch_id,
        reason="formal result",
        execution_outcome=ExecutionOutcome.EVALUATED,
        execution_outcome_reason_code="PROTOCOL_EVALUATED",
        protocol_stage=stage,
        formal_protocol_evaluated=True,
        screened_experiment_effective=stage == "screening",
    )


def _non_evaluated(outcome: ExecutionOutcome) -> StepResult:
    return StepResult(
        action="stopped",
        branch_id="b1",
        reason="typed terminal outcome",
        attempt_kind="other",
        execution_outcome=outcome,
        execution_outcome_reason_code="CURRENT_CALL_NOT_EVALUATED",
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
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs["stopped_reason"])

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        run_one_step=run_one_step,
        write_campaign_summary=lambda: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )
    loop.run(requested_rounds=rounds)
    return SimpleNamespace(calls=calls, statuses=statuses, stopped=stopped_reasons)


def _rejected(*, lineage_event_id: str | None = None) -> StepResult:
    marker = ResearchRejectionDisposition(
        disposition=AttemptDisposition.ATTEMPT_REJECT_TO_BASE,
        rejection_phase="verification",
        lineage_event_id=lineage_event_id,
    )
    return StepResult(
        action="explore",
        branch_id="b1",
        reason="candidate rejected",
        execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
        execution_outcome_reason_code="VERIFICATION_LIGHT_REJECTED",
        attempt_disposition=marker,
    )


def test_attempt_kind_is_explicit_and_never_inferred_from_reason_text() -> None:
    result = StepResult(
        action="explore",
        reason="same family retry schema quality telemetry repair",
        attempt_kind="other",
    )

    assert _attempt_kind(result) == "other"


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
    assert run.statuses[-1]["effective_rounds_completed"] == 0
    assert run.statuses[-1]["scheduled_calls"] == 1


def test_requested_rounds_count_only_formal_evaluated_results() -> None:
    run = _run(
        [_evaluated("screening", branch_id="b1"), _evaluated("validation", branch_id="b2")],
        rounds=2,
    )

    assert run.calls == 2
    status = run.statuses[-1]
    assert status["requested_rounds"] == 2
    assert status["effective_rounds_completed"] == 2
    assert status["completed_requested_rounds"] is True
    assert status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 1,
        "frozen": 0,
    }
    assert status["formal_screened_candidates"] == 1
    assert "requested_rounds_completed" in run.stopped


def test_evaluated_without_formal_protocol_projection_stops_without_counting() -> None:
    result = StepResult(
        action="explore",
        execution_outcome=ExecutionOutcome.EVALUATED,
        execution_outcome_reason_code="RESULT_PRESENT_BUT_NOT_FORMAL",
    )
    run = _run([result, _evaluated()], rounds=1)

    assert run.calls == 1
    assert "evaluated_without_formal_protocol_result" in run.stopped
    assert run.statuses[-1]["effective_rounds_completed"] == 0


def test_missing_outcome_stops_without_implicit_retry() -> None:
    run = _run([StepResult(action="skip"), _evaluated()], rounds=1)

    assert run.calls == 1
    assert "execution_outcome_missing" in run.stopped
    assert run.statuses[-1]["effective_rounds_completed"] == 0


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
    rejected = [
        _rejected(lineage_event_id=f"event-{index + 1}")
        for index in range(rejection_count)
    ]
    run = _run([*rejected, _evaluated()], rounds=1)

    assert run.calls == rejection_count + 1
    assert run.statuses[-1]["effective_rounds_completed"] == 1
    assert run.statuses[-1]["scheduled_calls"] == rejection_count + 1
    assert run.statuses[-1]["research_rejection_audit"]["committed"] == (
        rejection_count
    )
    assert run.statuses[-1]["research_rejection_audit"]["by_phase"] == {
        "verification": rejection_count
    }
    assert run.statuses[-1]["research_rejection_audit"]["by_reason"] == {
        "VERIFICATION_LIGHT_REJECTED": rejection_count
    }
    assert "requested_rounds_completed" in run.stopped


def test_repeated_research_rejections_are_audited_and_schedule_forward() -> None:
    rejected = _rejected(lineage_event_id="same-lineage-event")
    run = _run([rejected, rejected, _evaluated()], rounds=1)

    assert run.calls == 3
    assert run.statuses[-1]["effective_rounds_completed"] == 1
    assert run.statuses[-1]["scheduled_calls"] == 3
    assert run.statuses[-1]["research_rejection_audit"]["committed"] == 2
    assert "requested_rounds_completed" in run.stopped


def test_post_promotion_stale_lifecycle_schedules_forward_through_36_stages() -> None:
    stale_lifecycle = StepResult(
        action="reconcile",
        branch_id="old-promoted-peer",
        reason="no patch to reconcile",
        attempt_kind="reconcile_lifecycle",
    )
    stages = ("screening", "validation", "frozen")
    formal_results = [
        _evaluated(stages[index % len(stages)], branch_id=f"forward-{index}")
        for index in range(36)
    ]

    run = _run([stale_lifecycle, *formal_results], rounds=36)

    assert run.calls == 37
    status = run.statuses[-1]
    assert status["effective_rounds_completed"] == 36
    assert status["scheduled_calls"] == 37
    assert status["protocol_stage_counts"] == {
        "screening": 12,
        "validation": 12,
        "frozen": 12,
    }
    assert status["research_rejection_audit"]["committed"] == 0
    assert "research_rejection_disposition_missing" not in run.stopped
    assert "requested_rounds_completed" in run.stopped


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("decision", Decision.ABANDON),
        ("protocol_stage", "screening"),
        ("formal_protocol_evaluated", True),
        ("screened_experiment_effective", True),
        ("execution_outcome_reason_code", "UNBOUND_REASON"),
        ("execution_outcome_detail", "unbound detail"),
        ("execution_outcome_provenance", {"unbound": True}),
        ("attempt_disposition", _rejected().attempt_disposition),
        ("failure_stage", "verification"),
        ("failure_detail", "unbound failure"),
        ("failure_category", "research_rejected"),
    ),
)
def test_reconcile_lifecycle_with_attempt_evidence_does_not_scheduler_forward(
    field: str,
    value: object,
) -> None:
    lifecycle = StepResult(
        action="reconcile",
        branch_id="stale-branch",
        attempt_kind="reconcile_lifecycle",
    )
    setattr(lifecycle, field, value)

    run = _run([lifecycle, _evaluated()], rounds=1)

    assert run.calls == 1
    assert run.statuses[-1]["effective_rounds_completed"] == 0
    assert "execution_outcome_missing" in run.stopped


@pytest.mark.parametrize("failure_stage", ("patch_contract", "verification"))
def test_markerless_typed_rejection_schedules_forward_and_audits_failure_stage(
    failure_stage: str,
) -> None:
    reason_code = f"{failure_stage.upper()}_REJECTED"
    rejected = StepResult(
        action="reconcile",
        branch_id="stale-branch",
        reason="reconcile candidate rejected",
        attempt_kind="reconcile_lifecycle",
        failure_stage=failure_stage,
        failure_detail="candidate rejected before Protocol",
        failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
        execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
        execution_outcome_reason_code=reason_code,
    )

    run = _run([rejected, _evaluated()], rounds=1)

    assert run.calls == 2
    status = run.statuses[-1]
    assert status["effective_rounds_completed"] == 1
    assert status["research_rejection_audit"] == {
        "committed": 1,
        "by_phase": {failure_stage: 1},
        "by_reason": {reason_code: 1},
        "last": {
            "rejection_phase": failure_stage,
            "reason_code": reason_code,
        },
    }
    assert "requested_rounds_completed" in run.stopped
