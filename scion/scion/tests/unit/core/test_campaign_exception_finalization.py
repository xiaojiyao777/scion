from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.step_result import StepResult

from .campaign_control_boundaries_test_support import _campaign
from .evidence_recorder_test_support import _protocol_result


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

    monkeypatch.setattr(cm, "_run_research_environment_preflight", raise_preflight)

    with pytest.raises(RuntimeError, match="synthetic preflight failure"):
        cm.run(requested_rounds=2)

    campaign_dir = Path(cm._campaign_dir)
    status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")

    assert status["run_result"] == summary["run_result"]
    run_result = status["run_result"]
    assert run_result["status"] == "stopped"
    assert run_result["stop_reason"] == "preflight_exception"
    assert run_result["requested_rounds"] == 2
    assert run_result["run_validity"] == {
        "status": "invalid",
        "reason": "invalid_no_evaluated_outcome",
        "valid": False,
    }
    assert run_result["terminal_exception"]["type"] == "RuntimeError"
    assert run_result["terminal_exception"]["message"] == exception_message


def test_campaign_run_one_step_exception_writes_partial_terminal_artifacts(
    tmp_path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path)
    cm._research_preflight_checked = True
    calls = 0

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return StepResult(
                action="explore",
                branch_id="branch-1",
                reason="synthetic completed screening",
                protocol_result=_protocol_result(),
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.EVALUATED,
                    reason_code="EVALUATION_COMPLETED",
                ),
            )
        raise RuntimeError("synthetic step crash")

    monkeypatch.setattr(cm, "run_one_step", run_one_step)

    with pytest.raises(RuntimeError, match="synthetic step crash"):
        cm.run(requested_rounds=2)

    campaign_dir = Path(cm._campaign_dir)
    status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")

    assert status["run_result"] == summary["run_result"]
    run_result = status["run_result"]
    assert run_result["status"] == "stopped"
    assert run_result["stop_reason"] == "unhandled_exception"
    assert run_result["requested_rounds"] == 2
    assert run_result["evaluated_rounds"] == 1
    assert run_result["terminal_exception"]["type"] == "RuntimeError"
    assert run_result["run_validity"] == {
        "status": "valid",
        "reason": "valid_incomplete",
        "valid": True,
    }
