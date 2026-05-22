"""Common helpers for campaign evidence recording."""
from __future__ import annotations

from typing import Any, Callable, Mapping


StateProvider = Callable[[], Mapping[str, Any]]

_NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS = {"max_rounds_exhausted"}
_DEFAULT_NON_FORMAL_FINAL_EVIDENCE_REASON = (
    "campaign ended normally without an attached formal final evidence package; "
    "recording a non-formal final evidence closure"
)
_DEFAULT_PENDING_FINAL_EVIDENCE_REASON = (
    "final evidence package was not attached; post-campaign final evaluation "
    "is still required for formal readiness"
)


def _drop_none(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")



def _drop_empty_summary_items(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }

