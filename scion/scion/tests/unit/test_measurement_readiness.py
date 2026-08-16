from __future__ import annotations

import json
from dataclasses import fields
from datetime import date

from scion.core.models import DecisionFeatures
from scion.measurement.readiness import measurement_readiness_status


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
    root,
    *,
    calibrated_at: str = "2026-06-10T00:00:00Z",
    metric: str = "total_cost",
    unit: str = "raw_delta",
    mde: float | None = 4.0,
) -> None:
    path = root / "formal" / "calibration" / "aa_noise_floor.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "scion.aa_noise_floor.v1",
                "problem_id": "demo",
                "stage": "screening",
                "measurement_metric": metric,
                "measurement_unit": unit,
                "calibrated_at": calibrated_at,
                "n_pairs": 12,
                "protocol_power": {"mde_at_power_80": mde},
                "per_case": [
                    {"case": "a", "delta_p90_abs": 0.75},
                    {"case": "b", "delta_p90_abs": 1.25},
                ],
                "pair_evidence": [{"case_id": "raw-row-not-for-status"}],
                "policy": "problem_owned_measurement_diagnostic",
            }
        ),
        encoding="utf-8",
    )


def test_missing_calibration_ref_is_not_ready(tmp_path) -> None:
    readiness = measurement_readiness_status(_Problem(str(tmp_path)))

    assert readiness.status == "not_ready"
    assert readiness.reason_code == "missing_calibration_ref"


def test_missing_calibration_file_is_not_ready(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "not_ready"
    assert readiness.reason_code == "calibration_not_found"


def test_unreadable_calibration_json_is_not_ready(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    path = tmp_path / measurement.calibration_ref
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "not_ready"
    assert readiness.reason_code == "calibration_unreadable"


def test_stale_calibration_is_visible(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    measurement.calibration_max_age_days = 30
    _write_artifact(tmp_path, calibrated_at="2026-01-01T00:00:00Z")

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "degraded"
    assert readiness.reason_code == "calibration_stale"
    assert readiness.calibration_age_days == 161


def test_compatible_calibration_reduces_to_deterministic_readiness_fields(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path, mde=4.0)

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "ready"
    assert readiness.reason_code == "ok"
    assert readiness.calibration_age_days == 1
    assert readiness.n_pairs == 12
    assert readiness.mde_at_power_80 == 4.0
    assert readiness.noise_band_p90_abs == 1.25
    assert readiness.effect_to_mde_ratio == 0.5
    assert readiness.signal_to_noise_tier == "marginal"
    assert readiness.calibration_evidence_level == "pair_evidence"
    assert readiness.to_status_payload()["calibration_evidence_level"] == (
        "pair_evidence"
    )
    assert "pair_evidence" not in readiness.to_status_payload()
    assert "calibration_ref" not in readiness.to_status_payload()


def test_summary_only_calibration_evidence_level_is_visible(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path, mde=4.0)
    path = tmp_path / measurement.calibration_ref
    artifact = json.loads(path.read_text(encoding="utf-8"))
    artifact.pop("pair_evidence")
    path.write_text(json.dumps(artifact), encoding="utf-8")

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "ready"
    assert readiness.calibration_evidence_level == "summary_only"
    assert readiness.to_status_payload()["calibration_evidence_level"] == (
        "summary_only"
    )


def test_full_replay_calibration_evidence_level_requires_replay_metadata(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path, mde=4.0)
    path = tmp_path / measurement.calibration_ref
    artifact = json.loads(path.read_text(encoding="utf-8"))
    artifact["selected_cases"] = ["case-a.vrp"]
    artifact["selected_seeds"] = [11]
    artifact["replicate_count"] = 1
    artifact["runtime_policy"] = {"selected_policy": "protocol_time_limits"}
    artifact["pair_evidence"] = [
        {
            "case": "case-a",
            "ledger_seed": 11,
            "candidate_seed": 1000011,
            "resolved_case_path": "/data/case-a.vrp",
        }
        for _ in range(artifact["n_pairs"])
    ]
    path.write_text(json.dumps(artifact), encoding="utf-8")

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "ready"
    assert readiness.calibration_evidence_level == "full_replay"
    payload = readiness.to_status_payload()
    assert payload["calibration_evidence_level"] == "full_replay"
    assert "selected_cases" not in payload
    assert "pair_evidence" not in payload


def test_incomplete_calibration_is_degraded(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path, mde=None)

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "degraded"
    assert readiness.reason_code == "calibration_incomplete"
    assert readiness.signal_to_noise_tier == "unknown"


def test_incompatible_calibration_is_not_ready(tmp_path) -> None:
    measurement = _Measurement()
    measurement.calibration_ref = "formal/calibration/aa_noise_floor.json"
    _write_artifact(tmp_path, metric="other_metric")

    readiness = measurement_readiness_status(
        _Problem(str(tmp_path), measurement),
        as_of=date(2026, 6, 11),
    )

    assert readiness.status == "not_ready"
    assert readiness.reason_code == "calibration_incompatible"


def test_decision_features_exclude_raw_calibration_diagnostics() -> None:
    field_names = {field.name for field in fields(DecisionFeatures)}

    assert "raw_calibration_pair_rows" not in field_names
    assert "pair_evidence" not in field_names
    assert "calibration_ref" not in field_names
    assert "calibration_explanation" not in field_names
