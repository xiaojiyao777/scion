"""Reduced measurement declaration view for generic Scion consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Literal, Mapping

from scion.measurement.readiness import (
    CalibrationEvidenceLevel,
    MeasurementReadinessReason,
    MeasurementReadinessStatus,
    SignalToNoiseTier,
    measurement_readiness_status,
)


RuntimeModel = Literal["comparative", "budget_exhausting"]
PairingValidity = Literal["trajectory_stable", "trajectory_divergent"]
CalibrationFreshness = Literal[
    "fresh",
    "stale",
    "missing",
    "incomplete",
    "unavailable",
]


@dataclass(frozen=True)
class MeasurementConsumerView:
    """Problem-owned measurement facts reduced for generic framework use."""

    problem_family: str
    measurement_declared: bool
    readiness_status: MeasurementReadinessStatus
    readiness_reason_code: MeasurementReadinessReason
    runtime_model: RuntimeModel = "comparative"
    pairing_validity: PairingValidity = "trajectory_stable"
    effect_metric: str = ""
    effect_unit: str = ""
    practical_delta_screen: float | None = None
    practical_delta_validate: float | None = None
    mde_at_power_80: float | None = None
    noise_band_p90_abs: float | None = None
    effect_to_mde_ratio: float | None = None
    signal_to_noise_tier: SignalToNoiseTier = "unknown"
    calibration_age_days: int | None = None
    calibration_max_age_days: int = 0
    n_pairs: int = 0
    calibration_freshness: CalibrationFreshness = "missing"
    evidence_depth: CalibrationEvidenceLevel = "none"
    decision_features_excluded: bool = True

    def to_status_payload(self) -> dict[str, Any]:
        """Return a compact consumer payload with no raw calibration material."""

        return {
            "schema_version": "scion.measurement_consumer_view.v1",
            "problem_family": self.problem_family,
            "measurement_declared": self.measurement_declared,
            "readiness_status": self.readiness_status,
            "readiness_reason_code": self.readiness_reason_code,
            "runtime_model": self.runtime_model,
            "pairing_validity": self.pairing_validity,
            "effect_metric": self.effect_metric,
            "effect_unit": self.effect_unit,
            "practical_delta_screen": self.practical_delta_screen,
            "practical_delta_validate": self.practical_delta_validate,
            "mde_at_power_80": self.mde_at_power_80,
            "noise_band_p90_abs": self.noise_band_p90_abs,
            "effect_to_mde_ratio": self.effect_to_mde_ratio,
            "signal_to_noise_tier": self.signal_to_noise_tier,
            "calibration_age_days": self.calibration_age_days,
            "calibration_max_age_days": self.calibration_max_age_days,
            "n_pairs": self.n_pairs,
            "calibration_freshness": self.calibration_freshness,
            "evidence_depth": self.evidence_depth,
            "decision_features_excluded": self.decision_features_excluded,
        }

    def to_readiness_status_payload(self) -> dict[str, Any]:
        """Return the legacy readiness shape expected by current config users."""

        return {
            "status": self.readiness_status,
            "reason_code": self.readiness_reason_code,
            "calibration_age_days": self.calibration_age_days,
            "calibration_max_age_days": self.calibration_max_age_days,
            "n_pairs": self.n_pairs,
            "mde_at_power_80": self.mde_at_power_80,
            "noise_band_p90_abs": self.noise_band_p90_abs,
            "effect_to_mde_ratio": self.effect_to_mde_ratio,
            "signal_to_noise_tier": self.signal_to_noise_tier,
            "calibration_evidence_level": self.evidence_depth,
            "decision_features_excluded": self.decision_features_excluded,
        }


def measurement_consumer_view(
    problem_spec: Any | None,
    *,
    as_of: date | datetime | None = None,
) -> MeasurementConsumerView:
    """Build the normalized measurement view consumed by generic core."""

    measurement = _problem_measurement(problem_spec)
    readiness = measurement_readiness_status(problem_spec, as_of=as_of)
    if measurement is None:
        return MeasurementConsumerView(
            problem_family=_problem_family(problem_spec),
            measurement_declared=False,
            readiness_status=readiness.status,
            readiness_reason_code=readiness.reason_code,
            mde_at_power_80=readiness.mde_at_power_80,
            noise_band_p90_abs=readiness.noise_band_p90_abs,
            effect_to_mde_ratio=readiness.effect_to_mde_ratio,
            signal_to_noise_tier=readiness.signal_to_noise_tier,
            calibration_age_days=readiness.calibration_age_days,
            calibration_max_age_days=readiness.calibration_max_age_days,
            n_pairs=readiness.n_pairs,
            calibration_freshness=_calibration_freshness(readiness.reason_code),
            evidence_depth=readiness.calibration_evidence_level,
        )

    effect_scale = getattr(measurement, "effect_scale", None)
    return MeasurementConsumerView(
        problem_family=_problem_family(problem_spec),
        measurement_declared=True,
        readiness_status=readiness.status,
        readiness_reason_code=readiness.reason_code,
        runtime_model=_runtime_model(getattr(measurement, "runtime_model", None)),
        pairing_validity=_pairing_validity(
            getattr(measurement, "pairing_validity", None)
        ),
        effect_metric=_text(getattr(effect_scale, "metric", "")),
        effect_unit=_text(getattr(effect_scale, "unit", "")),
        practical_delta_screen=_optional_nonnegative_float(
            "measurement.effect_scale.practical_delta_screen",
            getattr(effect_scale, "practical_delta_screen", None),
        ),
        practical_delta_validate=_optional_nonnegative_float(
            "measurement.effect_scale.practical_delta_validate",
            getattr(effect_scale, "practical_delta_validate", None),
        ),
        mde_at_power_80=readiness.mde_at_power_80,
        noise_band_p90_abs=readiness.noise_band_p90_abs,
        effect_to_mde_ratio=readiness.effect_to_mde_ratio,
        signal_to_noise_tier=readiness.signal_to_noise_tier,
        calibration_age_days=readiness.calibration_age_days,
        calibration_max_age_days=readiness.calibration_max_age_days,
        n_pairs=readiness.n_pairs,
        calibration_freshness=_calibration_freshness(readiness.reason_code),
        evidence_depth=readiness.calibration_evidence_level,
    )


def measurement_consumer_view_from_mapping(
    problem: Mapping[str, Any],
    *,
    root_dir: str,
    calibration_ref_override: str | None = None,
    as_of: date | datetime | None = None,
) -> MeasurementConsumerView:
    """Build the consumer view from a parsed problem-v1 mapping."""

    measurement = problem.get("measurement")
    adapted_measurement = (
        _measurement_namespace(
            measurement,
            calibration_ref_override=calibration_ref_override,
        )
        if isinstance(measurement, Mapping)
        else None
    )
    spec = SimpleNamespace(
        id=_text(problem.get("id")),
        name=_text(problem.get("name")),
        problem_family=_text(problem.get("problem_family")),
        family=_text(problem.get("family")),
        root_dir=root_dir,
        measurement=adapted_measurement,
    )
    return measurement_consumer_view(spec, as_of=as_of)


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


def _problem_family(problem_spec: Any | None) -> str:
    for source in (problem_spec, getattr(problem_spec, "spec_v1", None)):
        if source is None:
            continue
        for name in ("problem_family", "family", "id", "name"):
            value = _text(getattr(source, name, ""))
            if value:
                return value
    return ""


def _runtime_model(value: Any) -> RuntimeModel:
    text = _text(value) or "comparative"
    if text in {"comparative", "budget_exhausting"}:
        return text  # type: ignore[return-value]
    raise ValueError("measurement.runtime_model must be comparative or budget_exhausting")


def _pairing_validity(value: Any) -> PairingValidity:
    text = _text(value) or "trajectory_stable"
    if text in {"trajectory_stable", "trajectory_divergent"}:
        return text  # type: ignore[return-value]
    raise ValueError(
        "measurement.pairing_validity must be trajectory_stable or trajectory_divergent"
    )


def _optional_nonnegative_float(name: str, value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative number") from exc
    if number < 0.0:
        raise ValueError(f"{name} must be a non-negative number")
    return number


def _measurement_namespace(
    value: Mapping[str, Any],
    *,
    calibration_ref_override: str | None,
) -> SimpleNamespace:
    effect_scale = _mapping_value(value.get("effect_scale"))
    readiness_summary = value.get("readiness_summary")
    return SimpleNamespace(
        runtime_model=value.get("runtime_model", "comparative"),
        pairing_validity=value.get("pairing_validity", "trajectory_stable"),
        effect_scale=SimpleNamespace(
            metric=_text(effect_scale.get("metric")),
            unit=_text(effect_scale.get("unit")),
            practical_delta_screen=effect_scale.get("practical_delta_screen"),
            practical_delta_validate=effect_scale.get("practical_delta_validate"),
        ),
        calibration_ref=(
            calibration_ref_override
            if calibration_ref_override is not None
            else value.get("calibration_ref", "")
        ),
        calibration_max_age_days=value.get("calibration_max_age_days", 0),
        readiness_summary=(
            SimpleNamespace(**dict(readiness_summary))
            if isinstance(readiness_summary, Mapping)
            else None
        ),
    )


def _mapping_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _calibration_freshness(
    reason_code: MeasurementReadinessReason,
) -> CalibrationFreshness:
    if reason_code == "ok":
        return "fresh"
    if reason_code == "calibration_stale":
        return "stale"
    if reason_code == "calibration_incomplete":
        return "incomplete"
    if reason_code in {
        "missing_measurement",
        "missing_calibration_ref",
        "calibration_not_found",
    }:
        return "missing"
    return "unavailable"


def _text(value: Any) -> str:
    return str(value or "").strip()
