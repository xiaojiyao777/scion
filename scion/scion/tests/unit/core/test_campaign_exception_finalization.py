from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.step_result import StepResult

from .campaign_control_boundaries_test_support import _campaign


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_campaign_run_preflight_exception_writes_terminal_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path)
    exception_message = "synthetic preflight failure " + "x" * 600 + " complete-tail"

    def raise_preflight() -> None:
        raise RuntimeError(exception_message)

    monkeypatch.setattr(cm, "_run_runtime_preflight", raise_preflight)

    with pytest.raises(RuntimeError, match="synthetic preflight failure"):
        cm.run(requested_rounds=2)

    campaign_dir = Path(cm._campaign_dir)
    status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")

    for payload in (status, summary):
        assert payload["stopped"] is True
        assert payload["stopped_reason"] == "preflight_exception"
        assert payload["run_validity"]["status"] == "invalid"
        assert payload["run_validity"]["reason"] == "invalid_no_experiments"
        assert payload["campaign_loop"]["requested_rounds"] == 2
        assert payload["campaign_loop"]["failure_categories"][
            "preflight_exception"
        ] == 1
        assert payload["campaign_loop"]["terminal_exception"]["type"] == (
            "RuntimeError"
        )
        assert payload["campaign_loop"]["terminal_exception"]["message"] == (
            exception_message
        )


def test_campaign_run_one_step_exception_writes_partial_terminal_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path)
    cm._runtime_preflight_checked = True
    calls = 0

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return StepResult(
                action="explore",
                branch_id="branch-1",
                reason="synthetic completed screening",
                protocol_stage="screening",
                formal_protocol_evaluated=True,
                screened_experiment_effective=True,
                execution_outcome=ExecutionOutcome.EVALUATED,
                execution_outcome_reason_code="EVALUATION_COMPLETED",
            )
        raise RuntimeError("synthetic step crash")

    monkeypatch.setattr(cm, "run_one_step", run_one_step)

    with pytest.raises(RuntimeError, match="synthetic step crash"):
        cm.run(requested_rounds=2)

    campaign_dir = Path(cm._campaign_dir)
    status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")

    for payload in (status, summary):
        assert payload["stopped"] is True
        assert payload["stopped_reason"] == "unhandled_exception"
        assert payload["campaign_loop"]["requested_rounds"] == 2
        assert payload["campaign_loop"]["effective_rounds_completed"] == 1
        assert payload["campaign_loop"]["failure_categories"][
            "unhandled_exception"
        ] == 1
        assert payload["campaign_loop"]["terminal_exception"]["type"] == (
            "RuntimeError"
        )
    assert status["run_validity"]["status"] == "valid"
    assert status["run_validity"]["reason"] == "valid_but_incomplete"
    assert summary["run_validity"]["status"] == "unknown"
    assert summary["run_validity"]["reason"] == "unknown_historical"
