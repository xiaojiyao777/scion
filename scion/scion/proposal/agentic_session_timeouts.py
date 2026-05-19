
"""Timeout helpers for deterministic APS preview calls."""
from __future__ import annotations

import signal
import sys
import threading
from typing import Any

_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC = 12.0
_ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC = 36.0
_FINAL_PREVIEW_WALL_TIME_RESERVE_SEC = (
    _CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC + _ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC + 5.0
)


class _ProposalToolTimeout(BaseException):
    pass


def _facade_value(name: str, fallback: float) -> float:
    module = sys.modules.get("scion.proposal.agentic_session")
    value = getattr(module, name, fallback) if module is not None else fallback
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _can_use_signal_timeout() -> bool:
    return threading.current_thread() is threading.main_thread() and hasattr(signal, "SIGALRM")


def _preview_tool_timeout_sec(name: str) -> float:
    if name == "proposal.algorithm_smoke":
        return _facade_value(
            "_ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC",
            _ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC,
        )
    return _facade_value(
        "_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC",
        _CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC,
    )
