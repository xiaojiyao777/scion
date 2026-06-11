from __future__ import annotations

from scion.measurement.aa_calibration import (
    AAPairRecord,
    build_aa_noise_floor_payload,
    estimate_protocol_power,
    summarize_aa_records,
)


def test_aa_calibration_summarizes_per_case_noise() -> None:
    records = [
        AAPairRecord("case-a", 1, 0, "tie", 0.0, 0.0),
        AAPairRecord("case-a", 2, 0, "win", 0.2, 0.2),
        AAPairRecord("case-a", 3, 0, "loss", -0.1, -0.1),
    ]

    rows = summarize_aa_records(records)

    assert rows == [
        {
            "case": "case-a",
            "n_pairs": 3,
            "seed_var": 0.02333333,
            "pair_tie_rate": 0.3333,
            "false_win_rate": 0.3333,
            "false_loss_rate": 0.3333,
            "delta_p50_abs": 0.1,
            "delta_p90_abs": 0.18,
            "delta_max_abs": 0.2,
        }
    ]


def test_aa_calibration_estimates_mde_above_practical_delta_when_noise_large() -> None:
    records = [
        AAPairRecord("case-a", idx, 0, "win" if idx % 2 else "loss", value, value)
        for idx, value in enumerate((-0.6, 0.4, -0.2, 0.3, -0.5, 0.5), start=1)
    ]

    power = estimate_protocol_power(
        records,
        win_rate_min=0.667,
        practical_delta=0.1,
        n_boot=80,
        seed=7,
    )

    assert power["false_pass_rate_at_current_gate"] < 0.5
    assert power["mde_at_power_80"] is not None
    assert power["mde_at_power_80"] > 0.1


def test_aa_calibration_payload_is_problem_owned_diagnostic() -> None:
    records = [AAPairRecord("case-a", 1, 0, "tie", 0.0, 0.0)]

    payload = build_aa_noise_floor_payload(
        records=records,
        problem_id="toy",
        stage="screening",
        metric="cost",
        unit="relative_pct",
        win_rate_min=0.667,
        practical_delta=0.1,
        calibrated_at="2026-06-11T00:00:00+00:00",
        champion_version="v1",
        protocol_version="p1",
        n_boot=10,
    )

    assert payload["schema"] == "scion.aa_noise_floor.v1"
    assert payload["decision_features_excluded"] is True
    assert payload["policy"] == "problem_owned_measurement_diagnostic"
    assert payload["protocol_power"]["recommended_min_effect"] is not None
