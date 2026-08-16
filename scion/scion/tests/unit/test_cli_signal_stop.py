from __future__ import annotations

import inspect
import signal

import pytest

from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignSignalStop,
    register_run_command,
)
from scion.core.campaign_composition import compose_campaign_services
from scion.core.production_boundary import validate_fresh_campaign_output


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
