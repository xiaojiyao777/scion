"""Common helpers for campaign evidence recording."""
from __future__ import annotations

from typing import Any, Callable, Mapping


StateProvider = Callable[[], Mapping[str, Any]]

_MEASUREMENT_READINESS_STATUS_FIELDS = (
    "status",
    "reason_code",
    "calibration_age_days",
    "calibration_max_age_days",
    "n_pairs",
    "mde_at_power_80",
    "noise_band_p90_abs",
    "effect_to_mde_ratio",
    "signal_to_noise_tier",
    "calibration_evidence_level",
    "decision_features_excluded",
)

_NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS = {
    "max_rounds_exhausted",  # historical artifact compatibility
    "requested_rounds_completed",
}
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


def reduced_measurement_readiness_payload(value: Any) -> dict[str, Any] | None:
    """Return only deterministic measurement readiness status fields."""

    if value is None:
        return None
    if hasattr(value, "to_readiness_status_payload"):
        raw = value.to_readiness_status_payload()
    elif hasattr(value, "to_status_payload"):
        raw = value.to_status_payload()
    elif hasattr(value, "model_dump"):
        try:
            raw = value.model_dump(mode="json")
        except TypeError:
            raw = value.model_dump()
    elif isinstance(value, Mapping):
        raw = value
    else:
        return None
    if not isinstance(raw, Mapping):
        return None
    payload = {
        key: raw[key]
        for key in _MEASUREMENT_READINESS_STATUS_FIELDS
        if key in raw
    }
    return payload or None
