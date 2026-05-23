from __future__ import annotations

from scion.proposal.tools.previews.algorithm_smoke_feedback import (
    _algorithm_smoke_agent_payload,
)
from scion.tests.unit.agentic_solver_design_test_support import *


def test_algorithm_smoke_feedback_separates_mechanism_telemetry_statuses() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "issues": [
                    "telemetry guard observed no activation evidence for declared "
                    "mechanism vns_local_search"
                ],
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "champion_runs": 2,
                    "expected_telemetry_present": True,
                    "declared_mechanisms": ["vns_local_search"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "vns_local_search",
                            "activation_status": "missing",
                            "runtime_status": "missing",
                            "effect_status": "zero",
                            "activation_observed": False,
                            "runtime_observed": False,
                            "effect_observed": False,
                            "declared_field_failures": [
                                {
                                    "category": "effect",
                                    "field": (
                                        "solver_algorithm_phase_best_delta."
                                        "vns_local_search"
                                    ),
                                    "code": "TELEMETRY_EFFECT_NOT_OBSERVED",
                                    "severity": "fail",
                                }
                            ],
                            "activation": {
                                "status": "missing",
                                "fields": [
                                    "solver_algorithm_context_records."
                                    "vns_local_search_iterations",
                                    "solver_algorithm_phase_runtime_ms."
                                    "vns_local_search",
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_zero": 0,
                                "candidate_missing": 4,
                            },
                            "runtime": {
                                "status": "missing",
                                "fields": [
                                    "solver_algorithm_phase_runtime_ms."
                                    "vns_local_search"
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_zero": 0,
                                "candidate_missing": 2,
                            },
                            "effect": {
                                "status": "zero",
                                "fields": [
                                    "solver_algorithm_phase_improvement_counts."
                                    "vns_local_search",
                                    "solver_algorithm_phase_best_delta."
                                    "vns_local_search",
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 4,
                                "candidate_zero": 4,
                                "candidate_missing": 0,
                            },
                            "repair_guidance": [
                                "Add direct activation telemetry for declared "
                                "mechanism vns_local_search."
                            ],
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "vns_local_search",
                            "category": "activation",
                            "field": (
                                "solver_algorithm_context_records."
                                "vns_local_search_iterations,"
                                "solver_algorithm_phase_runtime_ms.vns_local_search"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_zero": 0,
                            "candidate_missing": 4,
                            "champion_positive": 0,
                        }
                    ],
                    "warnings": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "warn",
                            "mechanism": "vns_local_search",
                            "category": "effect",
                            "field": (
                                "solver_algorithm_phase_improvement_counts."
                                "vns_local_search,"
                                "solver_algorithm_phase_best_delta.vns_local_search"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 4,
                            "candidate_zero": 4,
                            "candidate_missing": 0,
                            "champion_positive": 0,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["telemetry_guard"]["mechanism_diagnostics"][0]
    assert diagnostic["mechanism"] == "vns_local_search"
    assert diagnostic["activation_status"] == "missing"
    assert diagnostic["runtime_status"] == "missing"
    assert diagnostic["effect_status"] == "zero"
    assert diagnostic["declared_field_failures"][0]["field"] == (
        "solver_algorithm_phase_best_delta.vns_local_search"
    )
    assert diagnostic["effect"]["counters"]["candidate_zero"] == 4
    assert "Add direct activation telemetry" in payload["repair_hints"][0]


def test_algorithm_smoke_activation_missing_emits_proposal_diagnostic() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "issues": ["telemetry guard observed no activation evidence"],
                "runtime": {
                    "solver_algorithm_search_iterations": 0,
                    "solver_algorithm_move_attempts": 0,
                },
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "champion_runs": 2,
                    "expected_telemetry_present": True,
                    "declared_mechanisms": ["new_probe"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "new_probe",
                            "activation_status": "missing",
                            "runtime_status": "missing",
                            "effect_status": "not_declared",
                            "activation": {
                                "status": "missing",
                                "fields": [
                                    "solver_algorithm_context_records."
                                    "new_probe_iterations"
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_missing": 2,
                            },
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "new_probe",
                            "category": "activation",
                            "field": (
                                "solver_algorithm_context_records."
                                "new_probe_iterations"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_missing": 2,
                            "champion_positive": 0,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["activation_diagnostic"]

    assert payload["failure_class"] == "proposal_activation_diagnostic"
    assert diagnostic["code"] == "proposal_activation_diagnostic"
    assert diagnostic["category"] == "proposal_activation_diagnostic"
    assert diagnostic["activation_diagnostic_kind"] == "not_connected"
    assert diagnostic["telemetry_failure_code"] == (
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    )
    assert diagnostic["telemetry_failure_mechanism"] == "new_probe"
    assert diagnostic["telemetry_failure_category"] == "activation"
    assert diagnostic["telemetry_failure_field"] == (
        "solver_algorithm_context_records.new_probe_iterations"
    )
    assert any("Wire new_probe" in hint for hint in payload["repair_hints"])


def test_algorithm_smoke_activation_diagnostic_uses_declared_non_cvrp_activity_fields() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "dispatch_policy",
                "case_count": 2,
                "issues": ["telemetry guard observed no activation evidence"],
                "runtime": {
                    "dispatch_search_iterations": 4,
                    "dispatch_move_attempts": 6,
                },
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "dispatch_policy",
                    "candidate_runs": 2,
                    "champion_runs": 2,
                    "expected_telemetry_present": True,
                    "declared_mechanisms": ["new_probe"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "new_probe",
                            "activation_status": "missing",
                            "runtime_status": "missing",
                            "effect_status": "not_declared",
                            "activation": {
                                "status": "missing",
                                "fields": [
                                    "dispatch_context_records.new_probe_iterations"
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_missing": 2,
                            },
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "new_probe",
                            "category": "activation",
                            "field": (
                                "dispatch_context_records.new_probe_iterations"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_missing": 2,
                            "champion_positive": 0,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["activation_diagnostic"]

    assert payload["selected_surface"] == "dispatch_policy"
    assert diagnostic["activation_diagnostic_kind"] == "instrumentation_missing"
    assert diagnostic["telemetry_failure_field"] == (
        "dispatch_context_records.new_probe_iterations"
    )
    assert any("record_iteration" in hint for hint in payload["repair_hints"])


def test_algorithm_smoke_primary_issue_uses_declared_non_cvrp_runtime_events() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "dispatch_policy",
                "case_count": 1,
                "runtime": {
                    "dispatch_errors": 1,
                    "dispatch_events": [
                        {"detail": "dispatch runtime failed in policy step"}
                    ],
                },
                "runtime_audit_failure": {
                    "error_category": "dispatch_runtime_error",
                    "detail": "",
                    "runtime_error_field": "dispatch_errors",
                    "runtime_error_count": 1,
                    "runtime_events": [
                        {"detail": "dispatch runtime failed in policy step"}
                    ],
                },
            },
        }
    )

    assert payload["failure_class"] == "runtime_audit_failure"
    assert payload["primary_issue"] == "dispatch runtime failed in policy step"
    assert payload["runtime_smoke"]["runtime_audit_failure"][
        "runtime_error_field"
    ] == "dispatch_errors"


def test_algorithm_smoke_activation_diagnostic_flags_effect_counter_mismatch() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "issues": ["telemetry guard observed no activation evidence"],
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "champion_runs": 2,
                    "expected_telemetry_present": True,
                    "declared_mechanisms": ["move_probe"],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "move_probe",
                            "category": "activation",
                            "field": "solver_algorithm_improving_moves",
                            "candidate_positive": 0,
                            "candidate_present": 2,
                            "candidate_missing": 0,
                            "champion_positive": 1,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["activation_diagnostic"]

    assert diagnostic["activation_diagnostic_kind"] == (
        "expected_telemetry_mismatch"
    )
    assert "record_move alone" in " ".join(payload["repair_hints"]) or (
        "effect counters" in diagnostic["diagnosis"]
    )


def test_algorithm_smoke_effect_warning_is_advisory_not_failure() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": True,
            "runtime_smoke": {
                "passed": True,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "issues": [],
                "telemetry_guard": {
                    "passed": True,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "expected_telemetry_present": True,
                    "effect_observation_required": False,
                    "declared_mechanisms": ["probe"],
                    "failures": [],
                    "warnings": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "warn",
                            "mechanism": "probe",
                            "category": "effect",
                            "field": "mechanism_effect",
                            "candidate_positive": 0,
                            "candidate_present": 2,
                        }
                    ],
                },
            },
        }
    )

    assert payload["passed"] is True
    assert payload["failure_class"] == "passed"
    assert payload["telemetry_guard"]["triggered"] is False
    assert payload["telemetry_guard"]["advisory_code"] == (
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
    )


def test_algorithm_smoke_feedback_guides_unreached_activation_helper() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "telemetry_static_preview": {
                "passed": True,
                "declared_mechanisms": ["late_probe"],
                "checked_fields": ["mechanism_activation.late_probe"],
                "helper_evidence": {
                    "late_probe": {
                        "record_iteration": True,
                        "record_phase": False,
                    }
                },
            },
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "runtime": {
                    "solver_algorithm_search_iterations": 10,
                    "solver_algorithm_move_attempts": 2,
                },
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "declared_mechanisms": ["late_probe"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "late_probe",
                            "activation_status": "missing",
                            "runtime_status": "missing",
                            "effect_status": "not_declared",
                            "activation": {
                                "status": "missing",
                                "fields": ["mechanism_activation.late_probe"],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_missing": 2,
                            },
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "late_probe",
                            "category": "activation",
                            "field": "mechanism_activation.late_probe",
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_missing": 2,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["activation_diagnostic"]

    assert diagnostic["activation_diagnostic_kind"] == "path_not_reached"
    hints = " ".join(payload["repair_hints"])
    assert "trigger conditions" in hints
    assert "smoke-observable activation path" in hints
