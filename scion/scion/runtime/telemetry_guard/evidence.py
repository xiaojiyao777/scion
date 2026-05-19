"""Runtime telemetry value checks."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _positive_evidence(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0.0
    if isinstance(value, str):
        text = value.strip().lower()
        return bool(text) and text not in {
            "0",
            "false",
            "none",
            "null",
            "disabled",
            "off",
            "no",
            "unknown",
        }
    if isinstance(value, Mapping):
        return any(_positive_evidence(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return any(_positive_evidence(item) for item in value)
    return bool(value)


def _empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (Mapping, Sequence)) and not isinstance(
        value,
        (bytes, bytearray, str),
    ):
        return len(value) == 0
    return False


def _bounded_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _bounded_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_bounded_value(item) for item in list(value)[:8]]
    return str(value)[:160]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)
