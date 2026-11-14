"""Common helpers for campaign evidence recording."""

from __future__ import annotations

from typing import Any, Mapping

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
)


def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")


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
        key: raw[key] for key in _MEASUREMENT_READINESS_STATUS_FIELDS if key in raw
    }
    return payload or None
