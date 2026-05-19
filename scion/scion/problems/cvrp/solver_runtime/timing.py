"""Time-budget helpers for CVRP solver runtime."""
from __future__ import annotations

import time


_MAIN_SEARCH_EXIT_RESERVE_SEC = 0.75
_ROUTE_POOL_EXIT_RESERVE_SEC = 2.50
_MAX_EXIT_RESERVE_FRACTION = 0.15


def _time_exhausted(start_time: float, time_limit_sec: float) -> bool:
    if time_limit_sec <= 0:
        return False
    return time.perf_counter() - start_time >= time_limit_sec


def _remaining_time_sec(
    start_time: float | None,
    time_limit_sec: float | None,
) -> float:
    if start_time is None or time_limit_sec is None or time_limit_sec <= 0:
        return 0.0
    return max(0.0, float(time_limit_sec) - (time.perf_counter() - start_time))


def _bounded_exit_reserve_sec(
    time_limit_sec: float | None,
    requested_reserve_sec: float,
) -> float:
    requested = max(0.0, float(requested_reserve_sec))
    if time_limit_sec is None or time_limit_sec <= 0:
        return requested
    scaled_cap = max(0.05, float(time_limit_sec) * _MAX_EXIT_RESERVE_FRACTION)
    return min(requested, scaled_cap)


def _main_search_time_exhausted(start_time: float, time_limit_sec: float) -> bool:
    if time_limit_sec <= 0:
        return False
    return _remaining_time_sec(
        start_time,
        time_limit_sec,
    ) <= _bounded_exit_reserve_sec(time_limit_sec, _MAIN_SEARCH_EXIT_RESERVE_SEC)


def _route_pool_time_exhausted(
    start_time: float | None,
    time_limit_sec: float | None,
    *,
    exit_reserve_sec: float = _ROUTE_POOL_EXIT_RESERVE_SEC,
) -> bool:
    if start_time is None or time_limit_sec is None or time_limit_sec <= 0:
        return False
    return _remaining_time_sec(start_time, time_limit_sec) <= max(
        0.0,
        _bounded_exit_reserve_sec(time_limit_sec, exit_reserve_sec),
    )
