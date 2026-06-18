from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import (
    EvalStats,
    ExperimentStage,
    MechanismChange,
    ProtocolResult,
)
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    telemetry_effect_zero_detected,
    telemetry_decision_details,
)
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
    assert summary["warnings"][0]["diagnostic_kind"] == "evaluated_no_effect"
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
    assert diagnostic["diagnostic_signals"] == [
        "runtime_budget_zero_or_subms",
        "evaluated_no_effect",
    ]
    assert diagnostic["activation"]["candidate_positive"] == 1
    assert diagnostic["runtime"]["candidate_zero"] == 1
    assert diagnostic["effect"]["candidate_zero"] == 2


def test_mechanism_diagnostics_report_move_only_as_evaluated_no_effect() -> None:
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

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert {
        warning["diagnostic_kind"] for warning in summary["warnings"]
    } == {"evaluated_no_effect"}
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["passed"] is True
    assert diagnostic["activation_status"] == "missing"
    assert diagnostic["runtime_status"] == "missing"
    assert diagnostic["effect_status"] == "zero"
    assert diagnostic["diagnostic_kind"] == "evaluated_no_effect"
    assert diagnostic["telemetry_outcome"] == "no_effect"
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


def test_declared_field_zero_with_alternate_positive_effect_is_not_effect_zero() -> None:
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
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_EFFECT_NOT_OBSERVED"
    ]
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["effect_status"] == "positive"
    assert diagnostic["passed"] is True
    assert diagnostic["diagnostic_type"] is None
    assert diagnostic["telemetry_outcome"] is None
    assert diagnostic["effect_observed"] is True
    assert diagnostic["effect"]["status"] == "positive"
    assert diagnostic["effect"]["declared_field_warning_status"] == (
        "declared_field_warning"
    )
    assert diagnostic["declared_field_warnings"] == [
        {
            "category": "effect",
            "field": "mechanism_best_delta.target_probe",
            "code": "TELEMETRY_EFFECT_NOT_OBSERVED",
            "severity": "warn",
        }
    ]
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=1,
            wins=0,
            losses=0,
            ties=1,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(),
        exposed_summary="screening telemetry",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_surface_runtime_summary={"telemetry_guard": summary},
    )
    assert telemetry_effect_zero_detected(protocol) is False


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
    assert diagnostic["diagnostic_kind"] == "activated_no_positive_effect"
    assert diagnostic["telemetry_outcome"] == "effect_attribution_missing"
    assert "Activation was observed" in diagnostic["repair_guidance"][-1]


def test_activation_missing_with_evaluation_is_advisory_when_effect_is_advisory() -> None:
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

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]
    assert {
        warning["diagnostic_kind"] for warning in summary["warnings"]
    } == {"evaluated_no_effect"}


def test_zero_ms_runtime_with_positive_evaluation_is_runtime_budget_warning() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_context.{mechanism}_iterations",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": ["mechanism_evaluations.{mechanism}"]
                    },
                    mechanism_budget_runtime_fields={
                        "{mechanism}": ["mechanism_phase_runtime_ms.{mechanism}"]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_context": {"target_probe_iterations": 1},
                "mechanism_phase_runtime_ms": {"target_probe": 0},
                "mechanism_evaluations": {"target_probe": 1},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        expected_telemetry={
            "activation": ["mechanism_phase_runtime_ms.target_probe"],
            "budget": ["mechanism_phase_runtime_ms.target_probe"],
        },
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert {
        warning["diagnostic_kind"] for warning in summary["warnings"]
    } == {"runtime_budget_zero_or_subms"}
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["activation_status"] == "observed"
    assert diagnostic["runtime_status"] == "zero"
    assert diagnostic["effect_status"] == "positive"
    assert diagnostic["diagnostic_kind"] == "runtime_budget_zero_or_subms"
    assert "zero/sub-ms timer granularity" in " ".join(
        diagnostic["repair_guidance"]
    )


def test_conditional_not_triggered_is_advisory_without_evaluation_requirement() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{}],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="rare_probe", change_type="modify")
        ],
        effect_observation_required=False,
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert {
        warning["diagnostic_kind"] for warning in summary["warnings"]
    } == {"not_evaluated/not_triggered"}
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["diagnostic_kind"] == "not_evaluated/not_triggered"
    assert "Do not fake activation" in " ".join(diagnostic["repair_guidance"])


def test_missing_context_record_with_zero_runtime_is_wiring_suspect() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_context.{mechanism}_iterations",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": ["mechanism_evaluations.{mechanism}"]
                    },
                    mechanism_budget_runtime_fields={
                        "{mechanism}": ["mechanism_phase_runtime_ms.{mechanism}"]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {"mechanism_phase_runtime_ms": {"target_probe": 0}}
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["diagnostic_kind"] == "wiring_suspect"
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["diagnostic_kind"] == "wiring_suspect"
    assert "No mechanism-local context/evaluation evidence" in " ".join(
        diagnostic["repair_guidance"]
    )


def test_wiring_suspect_flows_into_formal_decision_details() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{}],
        problem_spec=_mechanism_probe_spec(),
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=1,
            wins=0,
            losses=0,
            ties=1,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("TELEMETRY_GUARD_FAILED",),
        exposed_summary="telemetry failed",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_surface_runtime_summary={"telemetry_guard": summary},
    )

    assert formal_telemetry_guard_failed(protocol) is True
    details = telemetry_decision_details(protocol)
    assert details
    assert {detail["diagnostic_kind"] for detail in details} == {"wiring_suspect"}
    assert {detail["branch_repair_signal"] for detail in details} == {
        "wiring_suspect"
    }
