from __future__ import annotations

import json

from scion.proposal.tools.previews.algorithm_smoke_feedback import (
    _algorithm_smoke_agent_payload,
)
from scion.proposal.agentic_preview import (
    _algorithm_smoke_failure_detail,
    _preview_observation_passed,
)
from scion.proposal.agentic_code_context import (
    _preview_repair_feedback_prompt_payload,
)
from scion.proposal.tools import ProposalObservation
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


def test_algorithm_smoke_preview_repair_feedback_is_short_and_actionable() -> None:
    smoke_payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "telemetry_static_preview": {
                "passed": False,
                "issue_codes": ["DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING"],
                "checked_fields": [
                    "solver_algorithm_phase_best_delta.sa_reheat_on_stagnation"
                ],
                "required_calls": {
                    "sa_reheat_on_stagnation": [
                        "context.record_move('sa_reheat_on_stagnation', attempted=1, accepted=1, delta=<positive_improvement_delta>, best_improved=True)"
                    ]
                },
                "actionable_telemetry_feedback": [
                    {
                        "failure_code": "DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING",
                        "mechanism_id": "sa_reheat_on_stagnation",
                        "category": "effect",
                        "delta_valued_fields": [
                            "solver_algorithm_phase_best_delta.sa_reheat_on_stagnation"
                        ],
                        "declaration_alternative": (
                            "If this mechanism is intended to prove only "
                            "activity or activation, repair expected_telemetry."
                        ),
                    }
                ],
                "issues": [
                    "algorithm_smoke_failure:algorithm_smoke_failure should not be repeated"
                ],
            },
            "primary_issue": "telemetry_static_preview rejected effect telemetry",
        }
    )
    observation = ProposalObservation(
        observation_id="obs-smoke",
        session_id="session",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="call",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload=smoke_payload,
    )

    feedback = _preview_repair_feedback_prompt_payload(observation)
    structured = feedback["structured_payload"]
    rendered = json.dumps(structured, sort_keys=True)

    assert structured["failure_code"] == "DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING"
    assert structured["mechanism_id"] == "sa_reheat_on_stagnation"
    assert "offending_fields" in structured
    assert "allowed_repair_shape" in structured
    assert "forbidden_repair_shape" in structured
    assert "guarantee-positive fallback" in structured["forbidden_repair_shape"]
    assert "algorithm_smoke_failure:algorithm_smoke_failure" not in rendered
    assert len(rendered) < 2600


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

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    assert payload["failure_class"] == "activation_not_observed_diagnostic"
    assert payload["diagnostic_passed"] is True
    assert diagnostic["code"] == "proposal_activation_diagnostic"
    assert diagnostic["category"] == "proposal_activation_diagnostic"
    assert diagnostic["activation_diagnostic_kind"] == "not_connected"
    assert diagnostic["diagnostic_type"] == "activation_unobserved_wiring_suspect"
    assert diagnostic["lifecycle_signal"] == "inactive_or_wiring_suspect"
    assert payload["smoke_telemetry_diagnostic_kind"] == (
        "activation_unobserved_wiring_suspect"
    )
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


def test_algorithm_smoke_effect_failure_is_proposal_diagnostic() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "runtime": {
                    "solver_algorithm_search_iterations": 10,
                    "solver_algorithm_move_attempts": 4,
                },
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "expected_telemetry_present": True,
                    "effect_observation_required": True,
                    "declared_mechanisms": ["probe"],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "probe",
                            "category": "effect",
                            "field": "mechanism_best_delta.probe",
                            "candidate_positive": 0,
                            "candidate_present": 2,
                        }
                    ],
                },
            },
        }
    )

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    assert payload["failure_class"] == "telemetry_not_observed_diagnostic"
    assert payload["diagnostic_passed"] is True


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

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    assert payload["failure_class"] == "activation_not_observed_diagnostic"
    assert payload["diagnostic_passed"] is True
    assert diagnostic["activation_diagnostic_kind"] == "path_not_reached"
    assert diagnostic["failure_code"] == "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    assert diagnostic["mechanism_id"] == "late_probe"
    hints = " ".join(payload["repair_hints"])
    assert "canary-scoped threshold" in hints
    assert "Do not unconditionally trigger" in hints
    assert "no-op activation" not in hints

    observation = ProposalObservation(
        observation_id="obs-diagnostic",
        session_id="session",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="call",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke diagnostic.",
        structured_payload=payload,
    )
    assert _preview_observation_passed(observation) is True
    assert _algorithm_smoke_failure_detail([observation]) is None


def test_algorithm_smoke_activation_missing_without_static_instrumentation_is_diagnostic() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
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
                            "runtime_status": "observed",
                            "effect_status": "not_declared",
                            "runtime": {
                                "status": "observed",
                                "candidate_positive": 2,
                                "candidate_present": 2,
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

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    assert payload["failure_class"] == "activation_not_observed_diagnostic"
    assert payload["diagnostic_passed"] is True
    assert payload["activation_diagnostic"]["activation_diagnostic_kind"] == (
        "instrumentation_missing"
    )
    assert payload["activation_diagnostic"]["diagnostic_type"] == (
        "activation_unobserved_wiring_suspect"
    )
    assert payload["activation_diagnostic"]["lifecycle_signal"] == (
        "inactive_or_wiring_suspect"
    )


def test_algorithm_smoke_conditional_activation_diagnostic_is_not_hard_fail() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "telemetry_static_preview": {
                "passed": True,
                "declared_mechanisms": ["rare_probe"],
                "checked_fields": ["mechanism_activation.rare_probe"],
                "helper_evidence": {
                    "rare_probe": {"record_iteration": True}
                },
            },
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 1,
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 1,
                    "declared_mechanisms": ["rare_probe"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "rare_probe",
                            "activation_status": "missing",
                            "activation": {
                                "status": "missing",
                                "fields": ["mechanism_activation.rare_probe"],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_missing": 1,
                            },
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "rare_probe",
                            "category": "activation",
                            "field": "mechanism_activation.rare_probe",
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_missing": 1,
                        }
                    ],
                },
            },
        }
    )

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    assert payload["diagnostic_passed"] is True
    assert payload["activation_diagnostic"]["diagnostic_type"] == (
        "activation_unobserved_conditional"
    )
    assert payload["activation_diagnostic"]["lifecycle_signal"] == (
        "active_no_case_level_gate"
    )


def test_algorithm_smoke_observed_activation_missing_effect_is_weak_signal() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "expected_telemetry_present": True,
                    "effect_observation_required": True,
                    "declared_mechanisms": ["active_probe"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "active_probe",
                            "activation_status": "observed",
                            "effect_status": "zero",
                            "activation": {
                                "status": "observed",
                                "fields": ["mechanism_activation.active_probe"],
                                "candidate_positive": 2,
                                "candidate_present": 2,
                            },
                            "effect": {
                                "status": "zero",
                                "fields": ["mechanism_best_delta.active_probe"],
                                "candidate_positive": 0,
                                "candidate_present": 2,
                                "candidate_zero": 2,
                            },
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "active_probe",
                            "category": "effect",
                            "field": "mechanism_best_delta.active_probe",
                            "candidate_positive": 0,
                            "candidate_present": 2,
                            "candidate_zero": 2,
                        }
                    ],
                },
            },
        }
    )

    assert payload["passed"] is True
    assert payload["status"] == "diagnostic"
    kinds = {item["diagnostic_type"] for item in payload["telemetry_diagnostics"]}
    assert "effect_missing_observed_activation" in kinds
    effect_diag = next(
        item
        for item in payload["telemetry_diagnostics"]
        if item["diagnostic_type"] == "effect_missing_observed_activation"
    )
    assert effect_diag["mechanism_id"] == "active_probe"
    assert effect_diag["lifecycle_signal"] == "valid_active_weak_positive"
    assert "weak signal" in effect_diag["screening_policy"]
