import json
from datetime import date
from pathlib import Path

import pytest
import os
import yaml
from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest
from scion.problem.bridge import load_problem_spec_v1_from_yaml


SCION_DIR = Path(__file__).resolve().parents[2]
PACKAGE_PROBLEMS_DIR = SCION_DIR / "scion" / "problems"
LEGACY_PROBLEMS_DIR = SCION_DIR / "problems"

def test_problem_spec_loader(tmp_path):
    d = tmp_path / "problem"
    d.mkdir()
    p_file = d / "problem.yaml"
    content = {
        "name": "WarehouseDelivery",
        "operator_categories": ["order_level", "vehicle_level"],
        "operators_dir": "operators",
        "search_space": {
            "editable": ["operators/*.py"],
            "frozen": ["operators/base.py"],
            "import_whitelist": ["math", "random"]
        }
    }
    p_file.write_text(yaml.dump(content))

    spec = ProblemSpec.from_yaml(str(p_file))
    assert spec.name == "WarehouseDelivery"
    assert spec.search_space.import_whitelist == ["math", "random"]
    assert "order_level" in spec.operator_categories

def test_split_manifest_disjoint(tmp_path):
    s_file = tmp_path / "split.yaml"

    # Valid: frozen disjoint from all
    valid_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(valid_content))
    manifest = SplitManifest.from_yaml(str(s_file))
    assert manifest.screening == ["case1", "case2"]

    # Screening/validation overlap is allowed (different seeds test stability)
    overlap_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case1", "case2", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(overlap_content))
    manifest2 = SplitManifest.from_yaml(str(s_file))
    assert manifest2.validation == ["case1", "case2", "case4"]

    # Frozen overlap is NOT allowed
    invalid_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case2"]
    }
    s_file.write_text(yaml.dump(invalid_content))
    with pytest.raises(ValueError, match="overlap"):
        SplitManifest.from_yaml(str(s_file))

def test_protocol_config_defaults():
    """Authoritative ProtocolConfig uses nested sub-configs with sensible defaults."""
    config = ProtocolConfig()
    # Screening defaults
    assert config.screening.n_cases_modify > 0
    assert config.screening.n_cases_create > 0
    assert config.screening.n_seeds > 0
    # Validation defaults
    assert config.validation.n_cases > 0
    assert config.validation.n_seeds > 0
    # Frozen defaults
    assert config.frozen.n_cases > 0
    assert config.frozen.max_uses_per_campaign > 0
    # Backward-compat properties
    assert 0.0 < config.screening_win_rate_threshold <= 1.0
    assert 0.0 < config.validation_win_rate_threshold <= 1.0
    assert config.min_practical_delta > 0.0
    assert config.measurement_governance == "on"
    borderline = config.gates.screening.expanded_borderline_advance
    assert borderline.enabled is False
    assert borderline.win_rate_window == pytest.approx(0.05)


def test_protocol_config_resolves_problem_measurement_practical_delta():
    """Problem-owned measurement thresholds replace the legacy dead default."""
    measurement = type(
        "Measurement",
        (),
        {
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "effect_scale": type(
                "EffectScale",
                (),
                {
                    "practical_delta_screen": 2.5,
                    "practical_delta_validate": 1.25,
                },
            )()
        },
    )()
    problem_spec = type("ProblemSpec", (), {"measurement": measurement})()

    config = ProtocolConfig().with_problem_measurement(problem_spec)

    assert config.min_practical_delta == 2.5
    assert config.screening_min_practical_delta == 2.5
    assert config.validation_min_practical_delta == 1.25
    assert config.runtime.runtime_model == "budget_exhausting"
    assert config.pairing_validity == "trajectory_divergent"
    assert config.measurement_governance == "on"
    assert config.measurement_readiness.status == "not_ready"
    assert config.measurement_readiness.reason_code == "missing_calibration_ref"


def test_protocol_config_record_only_measurement_keeps_status_not_behavior():
    """Record-only is measurement governance off, not all governance off."""
    measurement = type(
        "Measurement",
        (),
        {
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "effect_scale": type(
                "EffectScale",
                (),
                {
                    "practical_delta_screen": 2.5,
                    "practical_delta_validate": 1.25,
                },
            )(),
        },
    )()
    problem_spec = type("ProblemSpec", (), {"measurement": measurement})()
    base = ProtocolConfig(
        practical_delta_screen=0.4,
        practical_delta_validate=0.8,
        runtime={"runtime_model": "comparative"},
        pairing_validity="trajectory_stable",
    )

    config = base.with_problem_measurement(
        problem_spec,
        governance_mode="record_only",
    )
    on_config = base.with_problem_measurement(
        problem_spec,
        governance_mode="on",
    )

    assert on_config.measurement_governance == "on"
    assert on_config.screening_min_practical_delta == 2.5
    assert on_config.validation_min_practical_delta == 1.25
    assert on_config.runtime.runtime_model == "budget_exhausting"
    assert on_config.pairing_validity == "trajectory_divergent"
    assert config.measurement_governance == "record_only"
    assert config.measurement_readiness.status == "not_ready"
    assert config.measurement_readiness.reason_code == "missing_calibration_ref"
    assert config.screening_min_practical_delta == 0.4
    assert config.validation_min_practical_delta == 0.8
    assert config.runtime.runtime_model == "comparative"
    assert config.pairing_validity == "trajectory_stable"


def test_cvrp_formal_protocol_consumes_problem_measurement_declaration():
    problem = load_problem_spec_v1_from_yaml(
        PACKAGE_PROBLEMS_DIR / "cvrp" / "problem-v1.yaml"
    )
    base = ProtocolConfig.from_yaml(
        PACKAGE_PROBLEMS_DIR / "cvrp" / "formal" / "protocol.yaml"
    )

    config = base.with_problem_measurement(
        problem,
        measurement_readiness_as_of=date(2026, 6, 11),
    )

    assert config.measurement_governance == "on"
    assert config.screening_min_practical_delta == pytest.approx(2.0)
    assert config.validation_min_practical_delta == pytest.approx(1.0)
    assert config.runtime.runtime_model == "budget_exhausting"
    assert config.pairing_validity == "trajectory_divergent"
    assert config.measurement_readiness.status == "ready"
    assert config.measurement_readiness.reason_code == "ok"
    assert config.measurement_readiness.mde_at_power_80 == pytest.approx(9.9)
    assert config.measurement_readiness.calibration_evidence_level == "summary_only"
    status_payload = config.measurement_readiness.model_dump()
    assert "calibration_ref" not in status_payload
    assert "pair_evidence" not in status_payload
    assert "raw_calibration_pair_rows" not in status_payload


def test_warehouse_prod_protocol_consumes_problem_measurement_declaration():
    problem = load_problem_spec_v1_from_yaml(
        LEGACY_PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )
    base = ProtocolConfig.from_yaml(
        LEGACY_PROBLEMS_DIR / "warehouse_delivery" / "protocol_prod.yaml"
    )

    config = base.with_problem_measurement(
        problem,
        measurement_readiness_as_of=date(2026, 6, 11),
    )

    assert config.measurement_governance == "on"
    assert config.screening_min_practical_delta == pytest.approx(0.001)
    assert config.validation_min_practical_delta == pytest.approx(0.001)
    assert config.runtime.runtime_model == "comparative"
    assert config.pairing_validity == "trajectory_divergent"
    assert config.measurement_readiness.status == "ready"
    assert config.measurement_readiness.reason_code == "ok"
    assert config.measurement_readiness.mde_at_power_80 == pytest.approx(577.5)
    assert config.measurement_readiness.calibration_evidence_level == "summary_only"
    status_payload = config.measurement_readiness.model_dump()
    assert "calibration_ref" not in status_payload
    assert "pair_evidence" not in status_payload
    assert "raw_calibration_pair_rows" not in status_payload


def test_protocol_config_normalizes_measurement_governance_alias():
    config = ProtocolConfig.model_validate({"measurement_governance": "record-only"})

    assert config.measurement_governance == "record_only"


def test_protocol_config_surfaces_stale_measurement_calibration(tmp_path):
    artifact = tmp_path / "formal" / "calibration" / "aa_noise_floor.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "schema": "scion.aa_noise_floor.v1",
                "problem_id": "demo",
                "measurement_metric": "total_cost",
                "measurement_unit": "raw_delta",
                "calibrated_at": "2026-01-01T00:00:00Z",
                "n_pairs": 6,
                "protocol_power": {"mde_at_power_80": 4.0},
                "per_case": [{"delta_p90_abs": 1.0}],
                "decision_features_excluded": True,
            }
        ),
        encoding="utf-8",
    )
    effect_scale = type(
        "EffectScale",
        (),
        {
            "metric": "total_cost",
            "unit": "raw_delta",
            "practical_delta_screen": 2.0,
            "practical_delta_validate": 1.0,
        },
    )()
    measurement = type(
        "Measurement",
        (),
        {
            "runtime_model": "comparative",
            "pairing_validity": "trajectory_stable",
            "effect_scale": effect_scale,
            "calibration_ref": "formal/calibration/aa_noise_floor.json",
            "calibration_max_age_days": 30,
            "readiness_summary": None,
        },
    )()
    problem_spec = type(
        "ProblemSpec",
        (),
        {"id": "demo", "root_dir": str(tmp_path), "measurement": measurement},
    )()

    config = ProtocolConfig().with_problem_measurement(
        problem_spec,
        measurement_readiness_as_of=date(2026, 6, 11),
    )

    assert config.measurement_readiness.status == "degraded"
    assert config.measurement_readiness.reason_code == "calibration_stale"
    assert config.measurement_readiness.calibration_age_days == 161
    assert config.measurement_readiness.mde_at_power_80 == 4.0
    assert config.measurement_readiness.effect_to_mde_ratio == 0.5
    assert config.measurement_readiness.signal_to_noise_tier == "marginal"


def test_protocol_config_rejects_unknown_delta_reference():
    """Gate practical-delta refs must be numeric or declared symbolic names."""
    with pytest.raises(ValueError, match="median_delta_min"):
        ProtocolConfig(gates={"screening": {"median_delta_min": "missing_delta"}})

def test_protocol_config_from_yaml(tmp_path):
    """ProtocolConfig.from_yaml() loads the new nested format correctly."""
    p_file = tmp_path / "protocol.yaml"
    p_file.write_text(yaml.dump({
        "version": "test",
        "screening": {
            "n_cases_modify": 4,
            "n_cases_create": 8,
            "n_seeds": 2,
            "expand_to_modify": 8,
            "expand_to_create": 12,
        },
        "validation": {"n_cases": 5, "n_seeds": 3, "expand_to": 9},
        "frozen": {"n_cases": 3, "n_seeds": 3, "max_uses_per_campaign": 2},
        "gates": {
            "screening": {
                "win_rate_min": 0.6,
                "expanded_borderline_advance": {
                    "enabled": True,
                    "win_rate_window": 0.04,
                    "require_median_delta_nonnegative": True,
                    "require_ci_low_nonnegative": True,
                    "allow_pair_level_signal": True,
                    "pair_win_rate_min": 0.50,
                    "min_pair_total": 8,
                    "min_pair_wins": 4,
                    "min_pair_win_loss_margin": 2,
                    "pair_non_tie_win_rate_min": 0.60,
                    "max_pair_loss_rate": 0.40,
                },
            },
            "validation": {"win_rate_min": 0.7},
        }
    }))

    config = ProtocolConfig.from_yaml(str(p_file))
    assert config.screening.n_cases_modify == 4
    assert config.screening.n_cases_create == 8
    assert config.validation.n_cases == 5
    assert config.frozen.n_cases == 3
    assert config.frozen.max_uses_per_campaign == 2
    assert config.screening_win_rate_threshold == pytest.approx(0.6)
    borderline = config.gates.screening.expanded_borderline_advance
    assert borderline.enabled is True
    assert borderline.win_rate_window == pytest.approx(0.04)
    assert borderline.require_median_delta_nonnegative is True
    assert borderline.require_ci_low_nonnegative is True
    assert borderline.allow_pair_level_signal is True
    assert borderline.pair_win_rate_min == pytest.approx(0.50)
    assert borderline.min_pair_total == 8
    assert borderline.min_pair_wins == 4
    assert borderline.min_pair_win_loss_margin == 2
    assert borderline.pair_non_tie_win_rate_min == pytest.approx(0.60)
    assert borderline.max_pair_loss_rate == pytest.approx(0.40)
    assert config.validation_win_rate_threshold == pytest.approx(0.7)


def test_cvrp_formal_protocol_enables_pair_signal_diagnostic_validation():
    protocol_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "problems",
        "cvrp",
        "formal",
        "protocol.yaml",
    )

    config = ProtocolConfig.from_yaml(protocol_path)

    assert config.gates.screening.win_rate_min == pytest.approx(0.6)
    assert config.gates.validation.win_rate_min == pytest.approx(0.66)
    borderline = config.gates.screening.expanded_borderline_advance
    assert borderline.enabled is True
    assert borderline.win_rate_window == pytest.approx(0.10)
    assert borderline.allow_pair_level_signal is True
    assert borderline.pair_win_rate_min == pytest.approx(0.50)
    assert borderline.min_pair_total == 16
    assert borderline.min_pair_wins == 8
    assert borderline.min_pair_win_loss_margin == 1
    assert borderline.pair_non_tie_win_rate_min == pytest.approx(0.60)
    assert borderline.max_pair_loss_rate == pytest.approx(0.40)
    assert borderline.require_ci_low_nonnegative is True


def test_warehouse_prod_protocol_enables_conservative_pair_signal_diagnostic_validation():
    protocol_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "problems",
        "warehouse_delivery",
        "protocol_prod.yaml",
    )

    config = ProtocolConfig.from_yaml(protocol_path)

    assert config.gates.screening.win_rate_min == pytest.approx(0.55)
    assert config.gates.validation.win_rate_min == pytest.approx(0.55)
    borderline = config.gates.screening.expanded_borderline_advance
    assert borderline.enabled is True
    assert borderline.win_rate_window == pytest.approx(0.05)
    assert borderline.require_median_delta_nonnegative is True
    assert borderline.require_ci_low_nonnegative is False
    assert borderline.allow_pair_level_signal is True
    assert borderline.pair_win_rate_min == pytest.approx(0.46)
    assert borderline.min_pair_total == 12
    assert borderline.min_pair_wins == 6
    assert borderline.min_pair_win_loss_margin == 4
    assert borderline.pair_non_tie_win_rate_min == pytest.approx(0.68)
    assert borderline.max_pair_loss_rate == pytest.approx(0.25)


def test_protocol_config_runtime_governance_from_yaml(tmp_path):
    """Runtime governance is protocol-level, with a default and YAML override."""
    default_config = ProtocolConfig()
    assert default_config.max_runtime_ratio == pytest.approx(2.0)

    p_file = tmp_path / "protocol.yaml"
    p_file.write_text(yaml.dump({
        "version": "runtime-test",
        "runtime": {
            "max_runtime_ratio": 1.5,
        },
    }))

    config = ProtocolConfig.from_yaml(str(p_file))
    assert config.runtime.max_runtime_ratio == pytest.approx(1.5)
    assert config.max_runtime_ratio == pytest.approx(1.5)


def test_protocol_config_runtime_time_limits_from_yaml(tmp_path):
    p_file = tmp_path / "protocol.yaml"
    p_file.write_text(yaml.dump({
        "version": "runtime-time-limit-test",
        "runtime": {
            "time_limits": {
                "stage_defaults": {
                    "screening": 30,
                    "validation": 30,
                    "frozen": 60,
                    "canary": 10,
                },
                "rules": [
                    {
                        "stages": ["screening"],
                        "min_dimension": 300,
                        "time_limit_sec": 60,
                    }
                ],
            }
        },
    }))

    config = ProtocolConfig.from_yaml(str(p_file))

    time_limits = config.runtime.time_limits
    assert time_limits.resolve(
        stage="screening",
        case_path="cvrplib/E/E-n101-k8.vrp",
        fallback_time_limit_sec=10,
    ) == 30
    assert time_limits.resolve(
        stage="screening",
        case_path="cvrplib/X/X-n401-k29.vrp",
        fallback_time_limit_sec=10,
    ) == 60
    assert time_limits.resolve(
        stage="frozen",
        case_path="cvrplib/X/X-n401-k29.vrp",
        fallback_time_limit_sec=10,
    ) == 60
