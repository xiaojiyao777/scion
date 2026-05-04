"""LLM circuit breaker used by campaign proposal generation."""
from __future__ import annotations

MAX_CONSECUTIVE_LLM_FAILURES = 3


class CircuitBreaker:
    """Trips after N consecutive LLM failures to prevent budget burn."""

    def __init__(self, threshold: int = MAX_CONSECUTIVE_LLM_FAILURES) -> None:
        self._threshold = threshold
        self._consecutive_failures = 0
        self._last_failure_detail = ""

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self, detail: str) -> bool:
        """Record a failure. Returns True if the circuit has just tripped."""
        self._consecutive_failures += 1
        self._last_failure_detail = detail
        return self._consecutive_failures >= self._threshold

    @property
    def is_tripped(self) -> bool:
        return self._consecutive_failures >= self._threshold

    @property
    def last_failure_detail(self) -> str:
        return self._last_failure_detail
