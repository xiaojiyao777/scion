from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import MechanismChange
from scion.runtime.telemetry_guard import build_telemetry_guard_summary


def _mechanism_probe_spec() -> SimpleNamespace:
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": ["mechanism_activation"]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": ["mechanism_effect"]
                    },
                ),
            )
        ]
    )


def test_auto_declared_mechanism_effect_probe_warns_when_activation_present() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 1},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]
    assert summary["warnings"][0]["diagnostic_type"] == (
        "mechanism_executed_no_improvement"
    )
    assert summary["mechanism_diagnostics"][0]["telemetry_outcome"] == "no_effect"


def test_mechanism_diagnostics_separate_activation_runtime_and_zero_effect() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_iterations.{mechanism}",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": [
                            "mechanism_improvement_counts.{mechanism}",
                            "mechanism_best_delta.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_iterations": {"target_probe": 3},
                "mechanism_phase_runtime_ms": {"target_probe": 0},
                "mechanism_improvement_counts": {"target_probe": 0},
                "mechanism_best_delta": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["passed"] is True
    assert diagnostic["activation_status"] == "observed"
    assert diagnostic["runtime_status"] == "zero"
    assert diagnostic["effect_status"] == "zero"
    assert diagnostic["activation"]["candidate_positive"] == 1
    assert diagnostic["runtime"]["candidate_zero"] == 1
    assert diagnostic["effect"]["candidate_zero"] == 2


def test_mechanism_diagnostics_report_move_only_as_activation_missing() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_iterations.{mechanism}",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": [
                            "mechanism_improvement_counts.{mechanism}",
                            "mechanism_best_delta.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_improvement_counts": {"target_probe": 0},
                "mechanism_best_delta": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == (
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    )
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["passed"] is False
    assert diagnostic["activation_status"] == "missing"
    assert diagnostic["runtime_status"] == "missing"
    assert diagnostic["effect_status"] == "zero"
    assert "direct activation telemetry" in diagnostic["repair_guidance"][0]


def test_explicit_mechanism_effect_claim_is_no_effect_when_activation_observed() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 1},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": {"target_probe": ["mechanism_effect"]}},
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in [
        warning["code"] for warning in summary["warnings"]
    ]
    assert summary["mechanism_diagnostics"][0]["diagnostic_type"] == (
        "mechanism_executed_no_improvement"
    )
    assert summary["mechanism_diagnostics"][0]["telemetry_outcome"] == "no_effect"


def test_declared_field_zero_with_activation_is_visible_as_no_effect_warning() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_activation.{mechanism}",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": [
                            "mechanism_effect.{mechanism}",
                            "mechanism_best_delta.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 1},
                "mechanism_phase_runtime_ms": {"target_probe": 5},
                "mechanism_effect": {"target_probe": 3},
                "mechanism_best_delta": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        expected_telemetry={"effect": ["mechanism_best_delta.target_probe"]},
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["effect_status"] == "declared_field_warning"
    assert diagnostic["passed"] is True
    assert diagnostic["diagnostic_type"] == "mechanism_executed_no_improvement"
    assert diagnostic["telemetry_outcome"] == "no_effect"
    assert diagnostic["effect_observed"] is False
    assert diagnostic["effect"]["aggregate_status"] == "positive"
    assert diagnostic["declared_field_warnings"] == [
        {
            "category": "effect",
            "field": "mechanism_best_delta.target_probe",
            "code": "TELEMETRY_EFFECT_NOT_OBSERVED",
            "severity": "warn",
        }
    ]
    assert "Activation and runtime telemetry are observed" in (
        diagnostic["repair_guidance"][0]
    )
    assert "not activation missing" in diagnostic["repair_guidance"][0]
    assert "mechanism_best_delta.target_probe" in diagnostic["repair_guidance"][0]


def test_algorithm_smoke_can_treat_missing_effect_as_advisory() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 1},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": {"target_probe": ["mechanism_effect"]}},
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
        effect_observation_required=False,
    )

    assert summary["passed"] is True
    assert summary["effect_observation_required"] is False
    assert summary["failures"] == []
    warning_codes = [warning["code"] for warning in summary["warnings"]]
    assert "TELEMETRY_EFFECT_NOT_OBSERVED" in warning_codes
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in warning_codes


def test_missing_effect_attribution_with_activation_is_repairable_warning() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 1},
            }
        ],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": {"target_probe": ["mechanism_effect"]}},
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    warning_codes = [warning["code"] for warning in summary["warnings"]]
    assert "TELEMETRY_EFFECT_NOT_OBSERVED" in warning_codes
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in warning_codes
    assert {
        warning["diagnostic_type"]
        for warning in summary["warnings"]
        if warning["code"] == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
    } == {"effect_attribution_missing"}
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["activation_status"] == "observed"
    assert diagnostic["effect_status"] == "missing"
    assert diagnostic["diagnostic_type"] == "effect_attribution_missing"
    assert diagnostic["telemetry_outcome"] == "effect_attribution_missing"
    assert "Activation was observed" in diagnostic["repair_guidance"][-1]


def test_activation_missing_still_blocks_when_effect_is_advisory() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 0},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
        effect_observation_required=False,
    )

    assert summary["passed"] is False
    assert [failure["code"] for failure in summary["failures"]] == [
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    ]
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
    ]
