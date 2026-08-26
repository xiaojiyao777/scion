"""Strict public-projection schemas for the private M32 study adapter."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from .models import _as_mapping, _fail
from .study_root_progress import _validate_last_result_shape

_SUMMARY_ONLY_FIELDS = frozenset(
    {
        "verification_failure_breakdown",
        "action_locus_coverage",
        "family_coverage",
        "diagnostics",
        "steps",
    }
)
_RUN_RESULT_FIELDS = frozenset(
    {
        "status",
        "requested_rounds",
        "evaluated_rounds",
        "scheduled_calls",
        "formal_screened_candidates",
        "protocol_stage_counts",
        "failure_categories",
        "execution_outcome_counts",
        "unknown_outcome_count",
        "last_execution_outcome",
        "run_validity",
        "qualification",
        "stop_reason",
    }
)
_QUALIFICATION_FIELDS = frozenset(
    {
        "mode",
        "development_boundary_mode",
        "limits",
        "proposal_attempts",
        "verified_candidate_chains",
        "formal_screening_stages",
        "initial_screening_stages",
        "expanded_screening_stages",
        "disposition",
    }
)
_STATUS_REQUIRED_FIELDS = frozenset(
    {
        "updated_at",
        "campaign_id",
        "campaign_mode",
        "proposal_runtime_mode",
        "proposal_runtime",
        "run_result",
        "n_steps",
        "total_rounds",
        "n_experiments",
        "screened_experiments",
        "n_active_branches",
        "active_slots",
        "champion_version",
        "champion_weight_revision",
        "balance_exhausted",
        "branches",
        "measurement_readiness",
    }
)
_STATUS_OPTIONAL_FIELDS = frozenset({"last_result", "current_progress"})
_MEASUREMENT_READINESS_FIELDS = frozenset(
    {
        "status",
        "reason_code",
        "calibration_age_days",
        "calibration_max_age_days",
        "n_pairs",
        "mde_at_power_80",
        "noise_band_p90_abs",
        "effect_to_mde_ratio",
        "signal_to_noise_tier",
        "calibration_evidence_level",
    }
)
_MEASUREMENT_REASON_CODES = frozenset(
    {
        "ok",
        "missing_measurement",
        "missing_calibration_ref",
        "calibration_not_found",
        "calibration_unreadable",
        "calibration_incompatible",
        "calibration_incomplete",
        "calibration_stale",
    }
)
_STEP_REQUIRED_FIELDS = frozenset(
    {
        "round",
        "branch_id",
        "decision",
        "decision_reason_codes",
        "diagnostic_reason_codes",
        "bypass_reason_codes",
        "contract_passed",
        "contract_diagnostics",
        "verification_passed",
        "failure_stage",
        "failure_detail",
        "hypothesis",
        "execution_outcome",
    }
)
_STEP_OPTIONAL_FIELDS = frozenset(
    {"canary_result", "protocol_result", "case_feedback_summary"}
)
_CANARY_REQUIRED_FIELDS = frozenset({"passed", "reason"})
_CANARY_OPTIONAL_FIELDS = frozenset(
    {
        "failure_category",
        "reason_codes",
        "candidate_attributable_infeasible_pairs",
        "raw_metrics_ref",
    }
)
_PROTOCOL_REQUIRED_FIELDS = frozenset(
    {
        "stage",
        "median_delta",
        "ci_low",
        "ci_high",
        "statistical_status",
        "statistical_metric",
        "metric_stats",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "runtime_pairs",
        "runtime_confidence",
        "runtime_model",
        "runtime_evidence_status",
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
        "shared_failed_pairs",
        "bilateral_failed_pairs",
        "gate_outcome",
        "reason_codes",
        "decision_reason_codes",
        "diagnostic_reason_codes",
        "bypass_reason_codes",
        "raw_metrics_ref",
        "case_ids",
        "seed_set",
        "case_aggregation",
        "selected_surface",
        "opportunity_status",
        "opportunity_diagnostics",
        "mechanism_evidence",
        "candidate_surface_runtime_summary",
        "candidate_phase_telemetry_summary",
        "runtime_budget_diagnostic",
        "candidate_runtime_failure_categories",
        "candidate_first_runtime_failure",
        "candidate_operator_attempts",
        "candidate_operator_accepted",
        "candidate_operator_errors",
        "candidate_operator_invalid_outputs",
        "candidate_policy_errors",
        "candidate_construction_errors",
        "candidate_portfolio_errors",
        "candidate_runtime_stop_reasons",
        "screening_case_wins",
        "screening_case_losses",
        "screening_case_ties",
        "screening_case_total",
        "screening_case_win_rate",
        "screening_pair_wins",
        "screening_pair_losses",
        "screening_pair_ties",
        "screening_pair_total",
        "screening_pair_win_rate",
    }
)
_PROTOCOL_OPTIONAL_FIELDS = frozenset(
    {"candidate_attributable_infeasible_pairs", "paired_effect_cells"}
)


def _validate_status_summary_snapshot(
    status: Mapping[str, Any], summary: Mapping[str, Any]
) -> None:
    _validate_status_shape(status, summary)
    _validate_status_summary_mirror(status, summary)
    _validate_summary_only_fields(summary, status.get("n_steps"))
    _validate_step_shapes(summary.get("steps"))


def _validate_status_shape(
    status: Mapping[str, Any], summary: Mapping[str, Any]
) -> None:
    if "final_evidence_refs" in status or "final_evidence_refs" in summary:
        _fail("STUDY_FINAL_EVIDENCE_FORBIDDEN")
    updated_at = status.get("updated_at")
    if type(updated_at) is not str or not updated_at.strip():
        _fail("STUDY_STATUS_TIMESTAMP_INVALID")
    status_fields = set(status)
    if not _STATUS_REQUIRED_FIELDS <= status_fields or (
        status_fields - _STATUS_REQUIRED_FIELDS - _STATUS_OPTIONAL_FIELDS
    ):
        _fail("STUDY_STATUS_SHAPE_INVALID")
    if type(status.get("balance_exhausted")) is not bool:
        _fail("STUDY_BALANCE_PROJECTION_INVALID")
    if status.get("campaign_mode") != "qualification_only":
        _fail("STUDY_CAMPAIGN_MODE_INVALID")
    if "current_progress" in status and not isinstance(
        status["current_progress"], Mapping
    ):
        _fail("STUDY_CURRENT_PROGRESS_INVALID")
    if "last_result" in status:
        _validate_last_result_shape(status["last_result"])
    _validate_measurement_readiness(status.get("measurement_readiness"))


def _validate_status_summary_mirror(
    status: Mapping[str, Any], summary: Mapping[str, Any]
) -> None:
    for key, value in status.items():
        if key == "updated_at":
            continue
        if key not in summary or summary[key] != value:
            _fail("STUDY_STATUS_SUMMARY_MISMATCH")
    state_fields = set(status) - {"updated_at"}
    summary_only = set(summary) - state_fields
    if summary_only != _SUMMARY_ONLY_FIELDS:
        _fail("STUDY_STATUS_SUMMARY_SHAPE_INVALID")


def _validate_summary_only_fields(summary: Mapping[str, Any], n_steps: Any) -> None:
    if type(n_steps) is not int or n_steps < 0 or summary.get("diagnostics") != []:
        _fail("STUDY_SUMMARY_DIAGNOSTICS_INVALID")
    for name in (
        "verification_failure_breakdown",
        "action_locus_coverage",
        "family_coverage",
    ):
        counts = _as_mapping(summary.get(name), "STUDY_SUMMARY_COUNT_MAP_INVALID")
        if (
            any(
                type(key) is not str or type(value) is not int or value < 0
                for key, value in counts.items()
            )
            or sum(counts.values()) > n_steps
        ):
            _fail("STUDY_SUMMARY_COUNT_MAP_INVALID")


def _validate_step_shapes(value: Any) -> None:
    if not isinstance(value, list):
        _fail("STUDY_SUMMARY_STEPS_INVALID")
    for raw_step in value:
        step = _as_mapping(raw_step, "STUDY_SUMMARY_STEP_SHAPE_INVALID")
        fields = frozenset(step)
        if not _STEP_REQUIRED_FIELDS <= fields or fields - (
            _STEP_REQUIRED_FIELDS | _STEP_OPTIONAL_FIELDS
        ):
            _fail("STUDY_SUMMARY_STEP_SHAPE_INVALID")
        _validate_canary_shape(step)
        _validate_protocol_shape(step)
        _validate_case_feedback_shape(step)


def _validate_canary_shape(step: Mapping[str, Any]) -> None:
    if "canary_result" not in step:
        return
    canary = _as_mapping(step["canary_result"], "STUDY_CANARY_SHAPE_INVALID")
    fields = frozenset(canary)
    if not _CANARY_REQUIRED_FIELDS <= fields or fields - (
        _CANARY_REQUIRED_FIELDS | _CANARY_OPTIONAL_FIELDS
    ):
        _fail("STUDY_CANARY_SHAPE_INVALID")


def _validate_protocol_shape(step: Mapping[str, Any]) -> None:
    if "protocol_result" not in step:
        return
    protocol = _as_mapping(step["protocol_result"], "STUDY_PROTOCOL_SHAPE_INVALID")
    fields = frozenset(protocol)
    if not _PROTOCOL_REQUIRED_FIELDS <= fields or fields - (
        _PROTOCOL_REQUIRED_FIELDS | _PROTOCOL_OPTIONAL_FIELDS
    ):
        _fail("STUDY_PROTOCOL_SHAPE_INVALID")


def _validate_case_feedback_shape(step: Mapping[str, Any]) -> None:
    if "case_feedback_summary" not in step:
        return
    protocol = _as_mapping(
        step.get("protocol_result"), "STUDY_CASE_FEEDBACK_SHAPE_INVALID"
    )
    case_ids = protocol.get("case_ids")
    rows = step["case_feedback_summary"]
    if (
        not isinstance(case_ids, list)
        or any(type(case_id) is not str for case_id in case_ids)
        or not isinstance(rows, list)
        or not rows
    ):
        _fail("STUDY_CASE_FEEDBACK_SHAPE_INVALID")
    basenames = [PurePosixPath(case_id).name for case_id in case_ids]
    observed: set[str] = set()
    previous_index = -1
    for raw in rows:
        row = _as_mapping(raw, "STUDY_CASE_FEEDBACK_SHAPE_INVALID")
        case_id = row.get("case_id")
        medians = row.get("median_deltas")
        if set(row) != {
            "case_id",
            "dominant_result",
            "seed_pattern",
            "decisive",
            "median_deltas",
        } or (
            type(case_id) is not str
            or case_id not in basenames
            or case_id in observed
            or row.get("dominant_result") not in {"win", "loss", "tie", "mixed"}
            or row.get("seed_pattern") not in {"uniform", "heterogeneous"}
            or type(row.get("decisive")) is not str
            or not isinstance(medians, Mapping)
            or any(
                type(name) is not str or not name or not _finite_number(value)
                for name, value in medians.items()
            )
        ):
            _fail("STUDY_CASE_FEEDBACK_SHAPE_INVALID")
        index = basenames.index(case_id)
        if index <= previous_index:
            _fail("STUDY_CASE_FEEDBACK_SHAPE_INVALID")
        previous_index = index
        observed.add(case_id)


def _finite_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _validate_measurement_readiness(value: Any) -> None:
    item = _as_mapping(value, "STUDY_MEASUREMENT_READINESS_INVALID")
    if set(item) != _MEASUREMENT_READINESS_FIELDS or (
        item.get("status") not in {"ready", "degraded", "not_ready"}
        or item.get("reason_code") not in _MEASUREMENT_REASON_CODES
        or not _optional_nonnegative_int(item.get("calibration_age_days"))
        or not _nonnegative_int_value(item.get("calibration_max_age_days"))
        or not _nonnegative_int_value(item.get("n_pairs"))
        or any(
            not _optional_nonnegative_float(item.get(field))
            for field in (
                "mde_at_power_80",
                "noise_band_p90_abs",
                "effect_to_mde_ratio",
            )
        )
        or item.get("signal_to_noise_tier")
        not in {"ready", "marginal", "low_power", "unknown"}
        or item.get("calibration_evidence_level")
        not in {"none", "summary_only", "pair_evidence", "full_replay"}
    ):
        _fail("STUDY_MEASUREMENT_READINESS_INVALID")


def _optional_nonnegative_int(value: Any) -> bool:
    return value is None or _nonnegative_int_value(value)


def _nonnegative_int_value(value: Any) -> bool:
    return type(value) is int and value >= 0


def _optional_nonnegative_float(value: Any) -> bool:
    return value is None or (
        type(value) is float and math.isfinite(value) and value >= 0.0
    )


def _validate_study_run_schema(status: Mapping[str, Any]) -> None:
    run = _as_mapping(status.get("run_result"), "RUN_RESULT_INVALID")
    fields = frozenset(run)
    if fields not in {_RUN_RESULT_FIELDS, _RUN_RESULT_FIELDS | {"terminal_exception"}}:
        _fail("STUDY_RUN_RESULT_SHAPE_INVALID")
    qualification = _as_mapping(
        run.get("qualification"), "QUALIFICATION_PROJECTION_INVALID"
    )
    if set(qualification) != _QUALIFICATION_FIELDS:
        _fail("STUDY_QUALIFICATION_SHAPE_INVALID")
    if "terminal_exception" not in run:
        return
    exception = _as_mapping(
        run["terminal_exception"], "STUDY_TERMINAL_EXCEPTION_INVALID"
    )
    if set(exception) != {"reason", "type", "message"} or (
        any(type(exception.get(key)) is not str for key in exception)
        or not exception["reason"]
        or not exception["type"]
        or exception["reason"] != run.get("stop_reason")
    ):
        _fail("STUDY_TERMINAL_EXCEPTION_INVALID")
