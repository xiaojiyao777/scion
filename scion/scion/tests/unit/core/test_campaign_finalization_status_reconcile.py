from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.campaign import CampaignManager
from scion.core.campaign_loop import CampaignLoop, CampaignRunResult
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.step_result import StepResult


def test_campaign_loop_emits_one_typed_terminal_value() -> None:
    statuses: list[dict[str, Any]] = []
    terminals: list[CampaignRunResult] = []
    attempts = 0
    result = StepResult(
        action="explore",
        branch_id="branch-1",
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="CONTRACT_REJECTED",
        ),
    )

    def run_one_step() -> StepResult:
        nonlocal attempts
        attempts += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(kwargs),
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: attempts >= 1,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda _reason: None,
        run_one_step=run_one_step,
        write_terminal_artifacts=terminals.append,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda _timeout: None,
    )

    terminal = loop.run(1)

    assert terminals == [terminal]
    assert terminal is loop.current_result
    assert terminal.stop_reason == "termination condition met"
    assert terminal.execution_outcome_counts["research_rejected"] == 1
    assert all(isinstance(call["run_result"], CampaignRunResult) for call in statuses)
    assert not any("loop_status" in call for call in statuses)


def test_terminal_status_and_summary_receive_identical_snapshots() -> None:
    manager = CampaignManager.__new__(CampaignManager)
    terminal = CampaignRunResult.empty(1).terminalized("external_stop_requested")
    state = {"campaign_id": "camp-1", "run_result": terminal.to_projection()}
    calls: list[tuple[str, Any, Any]] = []
    manager._step_history = []
    manager.get_state = lambda *, run_result=None: state
    manager._evidence_recorder = SimpleNamespace(
        write_status=lambda **kwargs: calls.append(
            ("status", kwargs["state"], kwargs["run_result"])
        ),
        write_campaign_summary=lambda **kwargs: calls.append(
            ("summary", kwargs["state"], kwargs["run_result"])
        ),
    )

    CampaignManager._write_terminal_artifacts(manager, terminal)

    assert [kind for kind, _, _ in calls] == ["status", "summary"]
    assert calls[0][1] is calls[1][1]
    assert calls[0][2] is calls[1][2]


def test_summary_is_still_attempted_when_terminal_status_writer_fails() -> None:
    manager = CampaignManager.__new__(CampaignManager)
    terminal = CampaignRunResult.empty(1).terminalized("unhandled_exception")
    state = {"campaign_id": "camp-1", "run_result": terminal.to_projection()}
    summaries: list[dict[str, Any]] = []
    manager._step_history = []
    manager.get_state = lambda *, run_result=None: state

    def fail_status(**_kwargs: Any) -> None:
        raise RuntimeError("status unavailable")

    manager._evidence_recorder = SimpleNamespace(
        write_status=fail_status,
        write_campaign_summary=lambda **kwargs: summaries.append(kwargs),
    )

    CampaignManager._write_terminal_artifacts(manager, terminal)

    assert len(summaries) == 1
    assert summaries[0]["state"] is state
    assert summaries[0]["run_result"] is state["run_result"]
