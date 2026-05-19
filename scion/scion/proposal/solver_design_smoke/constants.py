"""Shared constants for solver-design runtime smoke."""

from __future__ import annotations

_ALGORITHM_SMOKE_TIME_LIMIT_SEC = 3
_ALGORITHM_SMOKE_TIMEOUT_SEC = 15
_ALGORITHM_SMOKE_DEFAULT_SEED = 77
_ALGORITHM_SMOKE_MAX_SCREENING_CASES = 4
_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES = 2
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS = 5
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS = 30
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO = 0.35
_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS = frozenset(
    {
        "no_improvement",
        "early_exit",
        "construction_only",
        "no_search",
    }
)
