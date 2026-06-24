from __future__ import annotations

import json
from dataclasses import fields
from datetime import date
from typing import Any

from scion.core.models import DecisionFeatures
from scion.measurement.consumer_view import measurement_consumer_view


class _EffectScale:
    metric = "total_cost"
    unit = "raw_delta"
    practical_delta_screen = 2.0
    practical_delta_validate = 1.0


class _Measurement:
    runtime_model = "comparative"
    pairing_validity = "trajectory_stable"
    effect_scale = _EffectScale()
    calibration_ref = ""
    calibration_max_age_days = 90
    readiness_summary = None


class _Problem:
    id = "demo"

    def __init__(self, root_dir: str, measurement: object | None = None) -> None:
        self.root_dir = root_dir
        self.measurement = measurement if measurement is not None else _Measurement()


def _write_artifact(
    root: Any,
    *,
    calibrated_at: str = "2026-06-10T00:00:00Z",
    mde: float | None = 4.0,
) -> None:
    path = root / "formal" / "calibration" / "aa_noise_floor.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "scion.aa_noise_floor.v1",
                "problem_id": "demo",
                "measurement_metric": "total_cost",
                "measurement_unit": "raw_delta",
                "calibrated_at": calibrated_at,
                "n_pairs": 12,
                "protocol_power": {"mde_at_power_80": mde},
                "per_case": [
                    {"case": "a", "delta_p90_abs": 0.75},
                    {"case": "b", "delta_p90_abs": 1.25},
                ],
                "pair_evidence": [
                    {
                        "case_id": f"raw-row-{index}",
                        "candidate_seed": 1000 + index,
                        "resolved_case_path": f"/cases/case-{index}.vrp",
                    }
                    for index in range(12)
                ],
                "selected_cases": ["case-a.vrp"],
                "selected_seeds": [11],
                "replicate_count": 1,
                "runtime_policy": {"selected_policy": "protocol_time_limits"},
                "decision_features_excluded": True,
            }
        ),
        encoding="utf-8",
    )


def test_measurement_consumer_view_reduces_problem_declaration(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path)

    view = measurement_consumer_view(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert view.problem_family == "demo"
    assert view.measurement_declared is True
    assert view.readiness_status == "ready"
    assert view.readiness_reason_code == "ok"
    assert view.runtime_model == "comparative"
    assert view.pairing_validity == "trajectory_stable"
    assert view.effect_metric == "total_cost"
    assert view.effect_unit == "raw_delta"
    assert view.practical_delta_screen == 2.0
    assert view.practical_delta_validate == 1.0
    assert view.mde_at_power_80 == 4.0
    assert view.effect_to_mde_ratio == 0.5
    assert view.calibration_freshness == "fresh"
    assert view.evidence_depth == "full_replay"
    assert view.decision_features_excluded is True


def test_consumer_payload_excludes_raw_problem_and_calibration_fields(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path)

    payload = measurement_consumer_view(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    ).to_status_payload()
    readiness_payload = measurement_consumer_view(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    ).to_readiness_status_payload()

    forbidden = {
        "calibration_ref",
        "pair_evidence",
        "selected_cases",
        "selected_seeds",
        "bks",
        "case_gap",
        "mechanism_rankings",
        "raw_calibration_pair_rows",
    }
    assert not (forbidden & set(_all_keys(payload)))
    assert not (forbidden & set(_all_keys(readiness_payload)))


def test_missing_measurement_has_not_ready_default_view() -> None:
    problem = type("Problem", (), {"id": "demo", "measurement": None})()

    view = measurement_consumer_view(problem)

    assert view.problem_family == "demo"
    assert view.measurement_declared is False
    assert view.readiness_status == "not_ready"
    assert view.readiness_reason_code == "missing_measurement"
    assert view.runtime_model == "comparative"
    assert view.pairing_validity == "trajectory_stable"
    assert view.calibration_freshness == "missing"
    assert view.evidence_depth == "none"


def test_stale_calibration_is_reduced_to_freshness_tier(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    measurement.calibration_max_age_days = 30
    _write_artifact(tmp_path, calibrated_at="2026-01-01T00:00:00Z")

    view = measurement_consumer_view(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert view.readiness_status == "degraded"
    assert view.readiness_reason_code == "calibration_stale"
    assert view.calibration_freshness == "stale"
    assert view.calibration_age_days == 161


def test_decision_features_stay_free_of_measurement_consumer_raw_fields() -> None:
    field_names = {field.name for field in fields(DecisionFeatures)}

    assert "calibration_ref" not in field_names
    assert "pair_evidence" not in field_names
    assert "selected_cases" not in field_names
    assert "mechanism_rankings" not in field_names


def _all_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_all_keys(child))
        return keys
    if isinstance(value, list):
        keys = []
        for child in value:
            keys.extend(_all_keys(child))
        return keys
    return []
