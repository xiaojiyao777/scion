"""Measurement readiness status derived from problem-owned calibration refs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping


MeasurementReadinessStatus = Literal["ready", "degraded", "not_ready"]
MeasurementReadinessReason = Literal[
    "ok",
    "missing_measurement",
    "missing_calibration_ref",
    "calibration_not_found",
    "calibration_unreadable",
    "calibration_incompatible",
    "calibration_incomplete",
    "calibration_stale",
]
SignalToNoiseTier = Literal["ready", "marginal", "low_power", "unknown"]
CalibrationEvidenceLevel = Literal[
    "none",
    "summary_only",
    "pair_evidence",
    "full_replay",
]


@dataclass(frozen=True)
class MeasurementReadiness:
    """Reduced, deterministic readiness fields safe for status consumption."""

    status: MeasurementReadinessStatus
    reason_code: MeasurementReadinessReason
    calibration_age_days: int | None = None
    calibration_max_age_days: int = 0
    n_pairs: int = 0
    mde_at_power_80: float | None = None
    noise_band_p90_abs: float | None = None
    effect_to_mde_ratio: float | None = None
    signal_to_noise_tier: SignalToNoiseTier = "unknown"
    calibration_evidence_level: CalibrationEvidenceLevel = "none"
    calibration_ref: str = ""

    def to_status_payload(self) -> dict[str, Any]:
        """Return generic enum/numeric fields only; no refs or raw diagnostics."""

        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "calibration_age_days": self.calibration_age_days,
            "calibration_max_age_days": self.calibration_max_age_days,
            "n_pairs": self.n_pairs,
            "mde_at_power_80": self.mde_at_power_80,
            "noise_band_p90_abs": self.noise_band_p90_abs,
            "effect_to_mde_ratio": self.effect_to_mde_ratio,
            "signal_to_noise_tier": self.signal_to_noise_tier,
            "calibration_evidence_level": self.calibration_evidence_level,
        }

    def to_diagnostic_payload(self) -> dict[str, Any]:
        """Return proposal-visible status plus the problem-owned artifact ref."""

        payload = self.to_status_payload()
        if self.calibration_ref:
            payload["calibration_ref"] = self.calibration_ref
        return payload


def measurement_readiness_status(
    problem_spec: Any | None,
    *,
    as_of: date | datetime | None = None,
) -> MeasurementReadiness:
    """Evaluate calibration freshness and reduced readiness for a problem spec."""

    measurement = _problem_measurement(problem_spec)
    if measurement is None:
        return MeasurementReadiness(
            status="not_ready",
            reason_code="missing_measurement",
        )

    calibration_max_age_days = _nonnegative_int(
        getattr(measurement, "calibration_max_age_days", 0)
    )
    calibration_ref = str(getattr(measurement, "calibration_ref", "") or "").strip()
    summary = _summary_payload(getattr(measurement, "readiness_summary", None))
    if not calibration_ref:
        return _readiness(
            status="not_ready",
            reason_code="missing_calibration_ref",
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=summary,
        )

    path = _resolve_calibration_path(problem_spec, calibration_ref)
    if path is None or not path.exists():
        return _readiness(
            status="not_ready",
            reason_code="calibration_not_found",
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=summary,
        )

    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _readiness(
            status="not_ready",
            reason_code="calibration_unreadable",
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=summary,
        )

    if not _compatible(problem_spec, measurement, artifact):
        return _readiness(
            status="not_ready",
            reason_code="calibration_incompatible",
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=summary,
        )

    calibrated_at = _parse_calibrated_at(artifact.get("calibrated_at"))
    age_days = _age_days(calibrated_at, as_of=as_of)
    payload = _artifact_summary(artifact) | summary
    if age_days is None:
        return _readiness(
            status="degraded",
            reason_code="calibration_incomplete",
            calibration_age_days=None,
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=payload,
        )
    if age_days > calibration_max_age_days:
        return _readiness(
            status="degraded",
            reason_code="calibration_stale",
            calibration_age_days=age_days,
            calibration_max_age_days=calibration_max_age_days,
            calibration_ref=calibration_ref,
            practical_delta=_practical_delta(measurement),
            summary=payload,
        )

    reason: MeasurementReadinessReason = "ok"
    status: MeasurementReadinessStatus = "ready"
    if _float_or_none(payload.get("mde_at_power_80")) is None:
        reason = "calibration_incomplete"
        status = "degraded"
    return _readiness(
        status=status,
        reason_code=reason,
        calibration_age_days=age_days,
        calibration_max_age_days=calibration_max_age_days,
        calibration_ref=calibration_ref,
        practical_delta=_practical_delta(measurement),
        summary=payload,
    )


def _problem_measurement(problem_spec: Any | None) -> Any | None:
    if problem_spec is None:
        return None
    measurement = getattr(problem_spec, "measurement", None)
    if measurement is not None:
        return measurement
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    if spec_v1 is not None:
        return getattr(spec_v1, "measurement", None)
    return None


def _resolve_calibration_path(
    problem_spec: Any | None,
    calibration_ref: str,
) -> Path | None:
    ref_path = Path(calibration_ref)
    if ref_path.is_absolute():
        return ref_path
    root = str(getattr(problem_spec, "root_dir", "") or "").strip()
    if not root:
        spec_v1 = getattr(problem_spec, "spec_v1", None)
        root = str(getattr(spec_v1, "root_dir", "") or "").strip()
    if not root:
        return None
    return Path(root) / ref_path


def _compatible(
    problem_spec: Any | None,
    measurement: Any,
    artifact: Mapping[str, Any],
) -> bool:
    if artifact.get("schema") != "scion.aa_noise_floor.v1":
        return False
    problem_id = str(
        getattr(problem_spec, "id", "")
        or getattr(problem_spec, "name", "")
        or ""
    )
    artifact_problem_id = str(artifact.get("problem_id") or "")
    if problem_id and artifact_problem_id and artifact_problem_id != problem_id:
        return False
    effect_scale = getattr(measurement, "effect_scale", None)
    metric = str(getattr(effect_scale, "metric", "") or "")
    unit = str(getattr(effect_scale, "unit", "") or "")
    if metric and str(artifact.get("measurement_metric") or "") != metric:
        return False
    if unit and str(artifact.get("measurement_unit") or "") != unit:
        return False
    return True


def _artifact_summary(artifact: Mapping[str, Any]) -> dict[str, Any]:
    power = artifact.get("protocol_power")
    if not isinstance(power, Mapping):
        power = {}
    return {
        "n_pairs": _nonnegative_int(artifact.get("n_pairs", 0)),
        "mde_at_power_80": _float_or_none(power.get("mde_at_power_80")),
        "noise_band_p90_abs": _noise_band_p90_abs(artifact.get("per_case")),
        "calibration_evidence_level": _calibration_evidence_level(artifact),
    }


def _summary_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, Mapping):
        return {}
    payload: dict[str, Any] = {}
    for key in ("mde_at_power_80", "noise_band_p90_abs", "effect_to_mde_ratio"):
        parsed = _float_or_none(value.get(key))
        if parsed is not None:
            payload[key] = parsed
    tier = _tier(value.get("signal_to_noise_tier"))
    if tier != "unknown":
        payload["signal_to_noise_tier"] = tier
    evidence_level = _calibration_evidence_level_value(
        value.get("calibration_evidence_level")
    )
    if evidence_level != "none":
        payload["calibration_evidence_level"] = evidence_level
    n_pairs = _nonnegative_int(value.get("n_pairs", 0))
    if n_pairs > 0:
        payload["n_pairs"] = n_pairs
    return payload


def _readiness(
    *,
    status: MeasurementReadinessStatus,
    reason_code: MeasurementReadinessReason,
    calibration_max_age_days: int,
    calibration_ref: str,
    practical_delta: float | None,
    summary: Mapping[str, Any],
    calibration_age_days: int | None = None,
) -> MeasurementReadiness:
    mde = _float_or_none(summary.get("mde_at_power_80"))
    ratio = _float_or_none(summary.get("effect_to_mde_ratio"))
    if ratio is None and practical_delta is not None and mde and mde > 0:
        ratio = practical_delta / mde
    return MeasurementReadiness(
        status=status,
        reason_code=reason_code,
        calibration_age_days=calibration_age_days,
        calibration_max_age_days=calibration_max_age_days,
        n_pairs=_nonnegative_int(summary.get("n_pairs", 0)),
        mde_at_power_80=mde,
        noise_band_p90_abs=_float_or_none(summary.get("noise_band_p90_abs")),
        effect_to_mde_ratio=ratio,
        signal_to_noise_tier=_tier(
            summary.get("signal_to_noise_tier") or _tier_for_ratio(ratio)
        ),
        calibration_evidence_level=_calibration_evidence_level_value(
            summary.get("calibration_evidence_level")
        ),
        calibration_ref=calibration_ref,
    )


def _practical_delta(measurement: Any) -> float | None:
    effect_scale = getattr(measurement, "effect_scale", None)
    return _float_or_none(getattr(effect_scale, "practical_delta_screen", None))


def _noise_band_p90_abs(per_case: Any) -> float | None:
    if not isinstance(per_case, list):
        return None
    values = [
        parsed
        for row in per_case
        if isinstance(row, Mapping)
        for parsed in [_float_or_none(row.get("delta_p90_abs"))]
        if parsed is not None
    ]
    return max(values) if values else None


def _calibration_evidence_level(artifact: Mapping[str, Any]) -> CalibrationEvidenceLevel:
    n_pairs = _nonnegative_int(artifact.get("n_pairs", 0))
    pair_evidence = artifact.get("pair_evidence")
    pair_count = len(pair_evidence) if isinstance(pair_evidence, list) else 0
    if pair_count <= 0:
        return "summary_only" if n_pairs > 0 else "none"
    selected_cases = artifact.get("selected_cases")
    selected_seeds = artifact.get("selected_seeds")
    runtime_policy = artifact.get("runtime_policy")
    has_replay_metadata = (
        isinstance(selected_cases, list)
        and bool(selected_cases)
        and isinstance(selected_seeds, list)
        and bool(selected_seeds)
        and isinstance(runtime_policy, Mapping)
        and bool(runtime_policy)
        and artifact.get("replicate_count") is not None
    )
    pair_rows_resolve_cases = all(
        isinstance(row, Mapping)
        and bool(row.get("candidate_seed") is not None)
        and (
            bool(row.get("resolved_case_path"))
            or isinstance(row.get("case_resolution"), Mapping)
        )
        for row in pair_evidence
    )
    if (
        n_pairs > 0
        and pair_count >= n_pairs
        and has_replay_metadata
        and pair_rows_resolve_cases
    ):
        return "full_replay"
    return "pair_evidence"


def _calibration_evidence_level_value(value: Any) -> CalibrationEvidenceLevel:
    text = str(value or "").strip()
    if text == "summary_only":
        return "summary_only"
    if text == "pair_evidence":
        return "pair_evidence"
    if text == "full_replay":
        return "full_replay"
    return "none"


def _parse_calibrated_at(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(
    calibrated_at: datetime | None,
    *,
    as_of: date | datetime | None,
) -> int | None:
    if calibrated_at is None:
        return None
    if as_of is None:
        as_of_date = datetime.now(timezone.utc).date()
    elif isinstance(as_of, datetime):
        as_of_date = (
            as_of.astimezone(timezone.utc).date()
            if as_of.tzinfo
            else as_of.date()
        )
    else:
        as_of_date = as_of
    return max(0, (as_of_date - calibrated_at.date()).days)


def _tier_for_ratio(ratio: float | None) -> SignalToNoiseTier:
    if ratio is None:
        return "unknown"
    if ratio >= 1.0:
        return "ready"
    if ratio >= 1.0 / 3.0:
        return "marginal"
    return "low_power"


def _tier(value: Any) -> SignalToNoiseTier:
    text = str(value or "").strip()
    if text in {"ready", "marginal", "low_power", "unknown"}:
        return text  # type: ignore[return-value]
    return "unknown"


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
