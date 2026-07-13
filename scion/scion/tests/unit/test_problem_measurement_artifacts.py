from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scion.measurement.readiness import measurement_readiness_status
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.proposal.context_manager.manager import _problem_measurement_diagnostics


_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    (
        "problem_path",
        "expected_problem_id",
        "expected_metric",
        "expected_unit",
        "expected_pairs",
        "expected_mde",
    ),
    [
        (
            _REPO_ROOT / "scion" / "scion" / "problems" / "cvrp" / "problem-v1.yaml",
            "cvrp",
            "total_distance",
            "raw_delta",
            96,
            9.9,
        ),
        (
            _REPO_ROOT / "scion" / "problems" / "warehouse_delivery" / "problem-v1.yaml",
            "warehouse_delivery",
            "total_cost",
            "raw_delta",
            36,
            577.5,
        ),
    ],
)
def test_checked_in_problem_measurement_artifacts_are_ready(
    problem_path: Path,
    expected_problem_id: str,
    expected_metric: str,
    expected_unit: str,
    expected_pairs: int,
    expected_mde: float,
) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(problem_path)
    legacy = legacy_problem_spec_from_v1(spec_v1)

    readiness = measurement_readiness_status(legacy, as_of=date(2026, 6, 19))
    status_payload = readiness.to_status_payload()
    diagnostic_payload = readiness.to_diagnostic_payload()

    assert spec_v1.id == expected_problem_id
    assert spec_v1.measurement.effect_scale.metric == expected_metric
    assert spec_v1.measurement.effect_scale.unit == expected_unit
    assert readiness.status == "ready"
    assert readiness.reason_code == "ok"
    assert readiness.n_pairs == expected_pairs
    assert readiness.mde_at_power_80 == expected_mde
    assert readiness.signal_to_noise_tier == "low_power"
    assert readiness.decision_features_excluded is True
    assert "calibration_ref" not in status_payload
    assert "pair_evidence" not in status_payload
    assert diagnostic_payload["calibration_ref"] == spec_v1.measurement.calibration_ref


@pytest.mark.parametrize(
    "problem_path",
    [
        _REPO_ROOT / "scion" / "scion" / "problems" / "cvrp" / "problem-v1.yaml",
        _REPO_ROOT / "scion" / "problems" / "warehouse_delivery" / "problem-v1.yaml",
    ],
)
def test_checked_in_problem_measurement_diagnostics_stay_reduced(
    problem_path: Path,
) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(problem_path)
    legacy = legacy_problem_spec_from_v1(spec_v1)

    diagnostics = _problem_measurement_diagnostics(
        legacy,
        adapter=load_problem_adapter(spec_v1),
    )
    rendered = json.dumps(diagnostics, sort_keys=True, default=str)
    problem_owned = diagnostics["problem_owned_diagnostics"]

    assert diagnostics["runtime_model"]
    assert diagnostics["pairing_validity"]
    assert diagnostics["effect_scale"]["metric"] == (
        spec_v1.measurement.effect_scale.metric
    )
    assert diagnostics["measurement_readiness"]["status"] == "ready"
    assert diagnostics["measurement_readiness"]["decision_features_excluded"] is True
    assert problem_owned["schema_version"]
    assert problem_owned["proposal_visibility_only"] is True
    assert problem_owned["decision_features_excluded"] is True
    _assert_forbidden_raw_measurement_fields_absent(diagnostics)
    assert "calibration_ref" not in rendered
    assert "pair_evidence" not in rendered
    assert "raw_calibration" not in rendered


def _assert_forbidden_raw_measurement_fields_absent(value: Any) -> None:
    forbidden = {
        "pair_evidence",
        "raw_pair_rows",
        "raw_calibration_pair_rows",
        "bks_gap_details",
        "validation_case_details",
        "frozen_case_details",
        "llm_text",
        "prompt_ratios",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for item in value.values():
            _assert_forbidden_raw_measurement_fields_absent(item)
    elif isinstance(value, list):
        for item in value:
            _assert_forbidden_raw_measurement_fields_absent(item)
