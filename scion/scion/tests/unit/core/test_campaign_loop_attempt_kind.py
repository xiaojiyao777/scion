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
    verify_research_rejection=lambda _marker: False,
    get_research_rejection_counts=lambda: {
        "total": 0,
        "by_phase": {},
        "by_reason": {},
        "completion_ids": [],
    },
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
        verify_research_rejection=verify_research_rejection,
        get_research_rejection_counts=get_research_rejection_counts,
    )
    loop.run(requested_rounds=rounds)
    return SimpleNamespace(calls=calls, statuses=statuses, stopped=stopped_reasons)


def _rejected(completion_digit: str, *, attempt_id: str) -> StepResult:
    marker = ResearchRejectionDisposition(
        disposition=AttemptDisposition.ATTEMPT_REJECT_TO_BASE,
        completion_id=completion_digit * 64,
        campaign_id="campaign-1",
        provider_attempt_id=attempt_id,
        rejection_phase="verification",
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
        ExecutionOutcome.RESEARCH_REJECTED,
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
        _rejected(str(index + 1), attempt_id=f"attempt-{index + 1}")
        for index in range(rejection_count)
    ]
    committed: list[ResearchRejectionDisposition] = []

    def verify(marker: ResearchRejectionDisposition) -> bool:
        if marker not in {item.attempt_disposition for item in rejected}:
            return False
        committed.append(marker)
        return True

    run = _run(
        [*rejected, _evaluated()],
        rounds=1,
        verify_research_rejection=verify,
        get_research_rejection_counts=lambda: {
            "total": len(committed),
            "by_phase": {"verification": len(committed)},
            "by_reason": {"VERIFICATION_LIGHT_REJECTED": len(committed)},
            "completion_ids": [item.completion_id for item in committed],
        },
    )

    assert run.calls == rejection_count + 1
    assert run.statuses[-1]["effective_rounds_completed"] == 1
    assert run.statuses[-1]["scheduled_calls"] == rejection_count + 1
    assert run.statuses[-1]["research_rejection_audit"]["committed"] == (
        rejection_count
    )
    assert "requested_rounds_completed" in run.stopped


def test_repeated_committed_completion_is_non_progress() -> None:
    rejected = _rejected("a", attempt_id="attempt-a")
    run = _run(
        [rejected, rejected, _evaluated()],
        rounds=1,
        verify_research_rejection=lambda marker: marker
        == rejected.attempt_disposition,
    )

    assert run.calls == 2
    assert "research_rejection_non_progress_identity_conflict" in run.stopped
    assert run.statuses[-1]["effective_rounds_completed"] == 0
