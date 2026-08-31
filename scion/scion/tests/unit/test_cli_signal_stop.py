from __future__ import annotations

import inspect
import json
import os
import signal
from pathlib import Path

import pytest

from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignOuterHardwall,
    _CampaignSignalStop,
    _run_campaign_with_signal_finalization,
    register_run_command,
)
from scion.core.campaign_composition import compose_campaign_services
from scion.core.campaign_loop import CampaignRunResult
from scion.core.production_boundary import validate_fresh_campaign_output
from scion.proposal.engine.provider_call import _write_terminal_trace_best_effort


class _Manager:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    def request_stop(self, reason: str) -> None:
        self.reasons.append(reason)


def test_cli_signal_handler_records_stop_before_exit() -> None:
    manager = _Manager()

    with _campaign_signal_handlers(manager):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        with pytest.raises(_CampaignSignalStop) as raised:
            handler(signal.SIGTERM, None)

    assert manager.reasons == ["signal:SIGTERM"]
    assert raised.value.reason == "signal:SIGTERM"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP unavailable")
def test_cli_sighup_records_typed_stop_before_terminal_exit() -> None:
    manager = _Manager()

    with _campaign_signal_handlers(manager):
        handler = signal.getsignal(signal.SIGHUP)
        assert callable(handler)
        with pytest.raises(_CampaignSignalStop) as raised:
            handler(signal.SIGHUP, None)

    assert manager.reasons == ["signal:SIGHUP"]
    assert raised.value.reason == "signal:SIGHUP"
    assert raised.value.exit_status == 128 + int(signal.SIGHUP)


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP unavailable")
def test_cli_keeps_signal_handlers_until_terminal_artifact_is_written(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "status.json"

    class _FinalizingManager(_Manager):
        def run(self, *, requested_rounds: int) -> CampaignRunResult:
            assert requested_rounds == 1
            os.kill(os.getpid(), signal.SIGHUP)
            raise AssertionError("SIGHUP must interrupt the active campaign")

        def finalize_requested_stop(
            self,
            reason: str,
            *,
            interrupted_override: bool | None = None,
        ) -> None:
            assert interrupted_override is None
            os.kill(os.getpid(), signal.SIGTERM)
            terminal = CampaignRunResult.empty(1).terminalized(
                reason,
                interrupted=True,
            )
            status_path.write_text(
                json.dumps({"run_result": terminal.to_projection()}),
                encoding="utf-8",
            )

    manager = _FinalizingManager()
    with pytest.raises(_CampaignSignalStop) as raised:
        _run_campaign_with_signal_finalization(
            manager,
            requested_rounds=1,
            hardwall=_CampaignOuterHardwall(None),
        )

    assert raised.value.reason == "signal:SIGHUP"
    assert manager.reasons == ["signal:SIGHUP"]
    run_result = json.loads(status_path.read_text(encoding="utf-8"))["run_result"]
    assert run_result["status"] == "stopped"
    assert run_result["stop_reason"] == "signal:SIGHUP"
    assert run_result["execution_outcome_counts"]["interrupted"] == 1
    assert run_result["last_execution_outcome"] == {
        "outcome": "interrupted",
        "reason_code": "EXTERNAL_STOP_REQUESTED",
        "stage": "campaign",
    }


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP unavailable")
def test_provider_trace_does_not_swallow_real_terminal_signal() -> None:
    class _SignalTrace:
        def write_terminal(self, **_kwargs) -> None:
            os.kill(os.getpid(), signal.SIGHUP)

    class _TraceInterruptedManager(_Manager):
        def __init__(self) -> None:
            super().__init__()
            self.finalized: list[tuple[str, bool | None]] = []

        def run(self, *, requested_rounds: int) -> CampaignRunResult:
            assert requested_rounds == 1
            _write_terminal_trace_best_effort(
                _SignalTrace(),
                request_kind="hypothesis",
                model="test-model",
                tool={},
                prompt="test prompt",
                system_blocks=[],
                context={},
                started_at="2026-08-30T00:00:00",
                client=object(),
                ok=True,
                provider_response_diagnostics=None,
                attempt_index=0,
            )
            raise AssertionError("SIGHUP must escape best-effort trace writing")

        def finalize_requested_stop(
            self,
            reason: str,
            *,
            interrupted_override: bool | None = None,
        ) -> None:
            self.finalized.append((reason, interrupted_override))
            os.kill(os.getpid(), signal.SIGTERM)

    manager = _TraceInterruptedManager()
    with pytest.raises(_CampaignSignalStop) as raised:
        _run_campaign_with_signal_finalization(
            manager,
            requested_rounds=1,
            hardwall=_CampaignOuterHardwall(None),
        )

    assert raised.value.reason == "signal:SIGHUP"
    assert raised.value.exit_status == 128 + int(signal.SIGHUP)
    assert manager.reasons == ["signal:SIGHUP"]
    assert manager.finalized == [("signal:SIGHUP", None)]


def test_composition_owns_the_production_boundary_check() -> None:
    cli_source = inspect.getsource(register_run_command)
    composition_source = inspect.getsource(compose_campaign_services)

    assert "validate_production_campaign_boundary" not in cli_source
    assert composition_source.count("validate_production_campaign_boundary(") == 1


def test_run_output_accepts_only_absent_or_empty_directory(tmp_path) -> None:
    absent = tmp_path / "new-run"
    validate_fresh_campaign_output(absent)

    empty = tmp_path / "empty"
    empty.mkdir()
    validate_fresh_campaign_output(empty)

    (empty / "status.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="campaign output must be fresh"):
        validate_fresh_campaign_output(empty)
