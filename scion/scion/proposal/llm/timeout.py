"""Hard timeout context for provider SDK calls."""
from __future__ import annotations

import os
import signal
import threading
from contextlib import contextmanager
from typing import Any

from .errors import LLMTimeoutError


@contextmanager
def _llm_hard_timeout(timeout_sec: float):
    """Enforce a wall-clock timeout around provider SDK calls on POSIX.

    SDK timeout knobs are not consistently total-request deadlines across
    OpenAI-compatible providers. In the campaign main thread, SIGALRM gives
    Scion a final process-safety deadline for the one provider call. It never
    schedules a retry. Non-main threads fall back to SDK timeout behavior
    because Python signals can only be installed in the main thread.
    """
    if (
        timeout_sec <= 0
        or os.name != "posix"
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def _raise_timeout(signum: int, frame: Any) -> None:
        raise LLMTimeoutError(
            f"LLM provider call exceeded hard timeout {timeout_sec:.1f}s"
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0.0)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_sec)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(
                signal.ITIMER_REAL,
                previous_timer[0],
                previous_timer[1],
            )
