from __future__ import annotations

import signal

import pytest

from scion.cli.commands.init_run import (
    _CampaignSignalStop,
    _campaign_signal_handlers,
)


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
