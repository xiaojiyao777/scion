"""CVRP large two-opt postrun evidence classifiers."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from scion.problems.cvrp.research_guidance import (
    PROTECTED_CASES,
    REQUIRED_MECHANISM_ID,
)


CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS = (
    "cvrp_large_twoopt_seed_handoff",
    "cvrp_large_twoopt_unbounded_default_avoid_handoff",
    "cvrp_large_twoopt_bounded_constraints_handoff",
    "cvrp_cmt_case_protection_handoff",
    "cvrp_resume_continuity_handoff",
    "cvrp_measurement_mde_handoff",
    "cvrp_low_snr_reason_handoff",
    "cvrp_decision_boundary_handoff",
)

CVRP_LARGE_TWOOPT_REVIEW_AXES = (
    "confirm_deadline_or_remaining_time_guard_in_solver_code",
    "confirm_no_unbounded_two_opt_intra_or_vns_fallback_above_large_threshold",
    "inspect_pair_level_total_distance_feasibility_route_count_and_wall_clock_evidence",
    "interpret_effect_against_aa_mde_and_case_level_variance",
    "reject_activation_only_or_seed_selection_only_claims",
)
CVRP_LARGE_TWOOPT_PROTECTED_CASES = tuple(PROTECTED_CASES)


def cvrp_large_twoopt_handoff_requirements(
    *,
    phase4: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    problem_specific = _mapping_or_empty(phase4.get("problem_specific_requirements"))
    checks = _mapping_or_empty(contract.get("checks"))
    requirements: dict[str, Any] = {}
    for key in CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS:
        coverage = _mapping_or_empty(problem_specific.get(key))
        check = _mapping_or_empty(checks.get(key))
        requirements[key] = {
            "available": coverage.get("available") is True
            or check.get("passed") is True,
            "count": _int_or_zero(coverage.get("count")),
            "source": coverage.get("source") or check.get("detail") or "",
            "contract_check_passed": check.get("passed"),
            "contract_detail": check.get("detail"),
        }
    return requirements


def cvrp_large_twoopt_mechanism_signal(
    *,
    measurement_effect_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    protocol_families: set[str] = set()
    continuity_families: set[str] = set()
    rejected_protocol_families: set[str] = set()
    rejected_continuity_families: set[str] = set()
    rejection_reason_counts: dict[str, int] = {}
    protocol_rows = 0
    top_row_signal_count = 0
    direct_evidence = _empty_cvrp_large_twoopt_direct_evidence()
    measurement = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    family_effects = _mapping_or_empty(measurement.get("mechanism_family_effects"))
    for family, payload in sorted(family_effects.items()):
        match = _cvrp_large_twoopt_family_match(str(family))
        if not match["matches"]:
            if match["twoopt_candidate"]:
                rejected_protocol_families.add(str(family))
                _increment_count(rejection_reason_counts, str(match["reason"]))
            continue
        protocol_families.add(str(family))
        protocol_rows += _int_or_zero(
            _mapping_or_empty(payload).get("protocol_row_count")
        )
    entries = measurement_effect_summary.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            effect = _mapping_or_empty(entry.get("protocol_effects_vs_mde"))
            top_rows = effect.get("top_rows_by_effect_to_mde")
            if not isinstance(top_rows, list):
                continue
            for row in top_rows:
                if not isinstance(row, Mapping):
                    continue
                family = str(row.get("mechanism_family") or "")
                match = _cvrp_large_twoopt_family_match(family)
                if match["matches"]:
                    protocol_families.add(family)
                    top_row_signal_count += 1
                    _merge_cvrp_large_twoopt_direct_evidence(
                        direct_evidence,
                        row,
                    )
                elif match["twoopt_candidate"]:
                    rejected_protocol_families.add(family)
                    _increment_count(rejection_reason_counts, str(match["reason"]))
    continuity = _mapping_or_empty(research_continuity_summary.get("aggregate"))
    family_counts = _mapping_or_empty(continuity.get("mechanism_family_counts"))
    for family in family_counts:
        match = _cvrp_large_twoopt_family_match(str(family))
        if match["matches"]:
            continuity_families.add(str(family))
        elif match["twoopt_candidate"]:
            rejected_continuity_families.add(str(family))
            _increment_count(rejection_reason_counts, str(match["reason"]))
    families = sorted(protocol_families | continuity_families)
    protocol_signal_rows = max(protocol_rows, top_row_signal_count)
    direct_evidence["ready"] = _cvrp_large_twoopt_direct_evidence_ready(
        direct_evidence
    )
    direct_evidence["missing"] = _cvrp_large_twoopt_direct_evidence_missing(
        direct_evidence
    )
    mechanism_family_available = bool(protocol_families) and protocol_signal_rows > 0
    return {
        "available": mechanism_family_available and direct_evidence["ready"],
        "mechanism_family_available": mechanism_family_available,
        "direct_evidence_ready": direct_evidence["ready"],
        "direct_evidence": direct_evidence,
        "families": families,
        "protocol_families": sorted(protocol_families),
        "continuity_families": sorted(continuity_families),
        "rejected_protocol_families": sorted(rejected_protocol_families),
        "rejected_continuity_families": sorted(rejected_continuity_families),
        "rejection_reason_counts": rejection_reason_counts,
        "protocol_row_count": protocol_signal_rows,
        "top_row_signal_count": top_row_signal_count,
        "source": (
            "measurement_effect_summary.mechanism_family_effects for protocol "
            "effect evidence; matching top_rows_by_effect_to_mde must also "
            "carry direct activation/effect/phase telemetry; "
            "research_continuity_summary.mechanism_family_counts is context only"
        ),
    }


def cvrp_large_twoopt_evidence_requirement_statuses(
    large_twoopt_mechanism: Mapping[str, Any],
) -> dict[str, Any]:
    """Return CVRP-owned requirement proof status for opportunity usage.

    These statuses answer whether the required evidence checklist was observed.
    They deliberately do not require a positive at-MDE effect; outcome quality
    remains owned by the measurement effect and large-twoopt review summaries.
    """

    mechanism = _mapping_or_empty(large_twoopt_mechanism)
    direct = _mapping_or_empty(mechanism.get("direct_evidence"))
    mechanism_family_available = (
        mechanism.get("mechanism_family_available") is True
    )
    objective_runtime_missing: list[str] = []
    if not mechanism_family_available:
        objective_runtime_missing.append("missing_large_twoopt_mechanism_family")
    if _int_or_zero(direct.get("activation_observed_count")) <= 0:
        objective_runtime_missing.append("missing_activation_observed")
    if _int_or_zero(direct.get("objective_effect_observed_count")) <= 0:
        objective_runtime_missing.append("missing_objective_effect_telemetry")
    if _int_or_zero(direct.get("phase_telemetry_observed_count")) <= 0:
        objective_runtime_missing.append("missing_phase_telemetry")

    observed_cases = sorted(
        set(_string_items(direct.get("protected_cases_observed")))
    )
    missing_cases = [
        case
        for case in CVRP_LARGE_TWOOPT_PROTECTED_CASES
        if case not in observed_cases
    ]
    protected_missing = (
        ["missing_cmt_case_protection_evidence"] if missing_cases else []
    )

    statuses = {
        "large_instance_two_opt_objective_runtime_requirement": (
            _requirement_status(
                missing=objective_runtime_missing,
                observed_fields={
                    "activation_observed_count": _int_or_zero(
                        direct.get("activation_observed_count")
                    ),
                    "objective_effect_observed_count": _int_or_zero(
                        direct.get("objective_effect_observed_count")
                    ),
                    "phase_telemetry_observed_count": _int_or_zero(
                        direct.get("phase_telemetry_observed_count")
                    ),
                    "protocol_row_count": _int_or_zero(
                        mechanism.get("protocol_row_count")
                    ),
                },
                outcome_status=_large_twoopt_outcome_status(direct),
            )
        ),
        "cmt2_cmt4_case_protection": _requirement_status(
            missing=protected_missing,
            observed_fields={
                "protected_case_complete_row_count": _int_or_zero(
                    direct.get("protected_case_complete_row_count")
                ),
            },
            protected_cases_observed=observed_cases,
            required_protected_cases=list(CVRP_LARGE_TWOOPT_PROTECTED_CASES),
            outcome_status="not_outcome_requirement",
        ),
    }
    complete = all(
        _mapping_or_empty(item).get("status") == "observed"
        for item in statuses.values()
    )
    missing = sorted(
        {
            reason
            for item in statuses.values()
            for reason in _string_items(_mapping_or_empty(item).get("missing_fields"))
        }
    )
    return {
        "schema_version": "scion.postrun_cvrp_large_twoopt_evidence_requirement_statuses.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "missing": missing,
        "requirements": statuses,
    }


def _requirement_status(
    *,
    missing: list[str],
    observed_fields: Mapping[str, Any],
    outcome_status: str,
    protected_cases_observed: list[str] | None = None,
    required_protected_cases: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "observed" if not missing else "missing",
        "observed_fields": dict(observed_fields),
        "missing_fields": list(missing),
        "protected_cases_observed": list(protected_cases_observed or []),
        "required_protected_cases": list(required_protected_cases or []),
        "outcome_status": outcome_status,
    }


def _large_twoopt_outcome_status(direct_evidence: Mapping[str, Any]) -> str:
    if _int_or_zero(direct_evidence.get("positive_effect_row_count")) > 0:
        return "positive_effect_observed"
    if _int_or_zero(direct_evidence.get("objective_effect_observed_count")) > 0:
        return "measured_no_positive_at_mde"
    return "not_measured"


def _empty_cvrp_large_twoopt_direct_evidence() -> dict[str, Any]:
    return {
        "ready": False,
        "missing": [],
        "required_protected_cases": list(CVRP_LARGE_TWOOPT_PROTECTED_CASES),
        "protected_cases_observed": [],
        "top_rows_checked": 0,
        "complete_direct_evidence_row_count": 0,
        "positive_effect_row_count": 0,
        "activation_observed_count": 0,
        "objective_effect_observed_count": 0,
        "phase_telemetry_observed_count": 0,
        "protected_case_evidence_row_count": 0,
        "protected_case_complete_row_count": 0,
    }


def _merge_cvrp_large_twoopt_direct_evidence(
    direct_evidence: dict[str, Any],
    row: Mapping[str, Any],
) -> None:
    direct_evidence["top_rows_checked"] += 1
    positive_effect = row.get("positive_effect_at_or_above_mde") is True
    row_family = str(row.get("mechanism_family") or "")
    activation_observed = _mechanism_activation_observed(
        row,
        family_match=_cvrp_large_twoopt_family_match,
        expected_family=row_family,
    )
    objective_effect_observed = _mechanism_objective_effect_observed(
        row,
        family_match=_cvrp_large_twoopt_family_match,
        expected_family=row_family,
    )
    phase_telemetry_observed = _cvrp_large_twoopt_phase_telemetry_observed(row)
    protected_cases_observed = _cvrp_protected_cases_observed(row)
    protected_case_complete = all(
        case in protected_cases_observed for case in CVRP_LARGE_TWOOPT_PROTECTED_CASES
    )
    if positive_effect:
        direct_evidence["positive_effect_row_count"] += 1
    if activation_observed:
        direct_evidence["activation_observed_count"] += 1
    if objective_effect_observed:
        direct_evidence["objective_effect_observed_count"] += 1
    if phase_telemetry_observed:
        direct_evidence["phase_telemetry_observed_count"] += 1
    if protected_cases_observed:
        direct_evidence["protected_case_evidence_row_count"] += 1
        direct_evidence["protected_cases_observed"] = sorted(
            set(_string_items(direct_evidence.get("protected_cases_observed")))
            | protected_cases_observed
        )
    if protected_case_complete:
        direct_evidence["protected_case_complete_row_count"] += 1
    if (
        positive_effect
        and activation_observed
        and objective_effect_observed
        and phase_telemetry_observed
        and protected_case_complete
    ):
        direct_evidence["complete_direct_evidence_row_count"] += 1


def _cvrp_large_twoopt_direct_evidence_ready(
    direct_evidence: Mapping[str, Any],
) -> bool:
    return (
        _int_or_zero(direct_evidence.get("complete_direct_evidence_row_count")) > 0
    )


def _cvrp_large_twoopt_direct_evidence_missing(
    direct_evidence: Mapping[str, Any],
) -> list[str]:
    missing = []
    if _int_or_zero(direct_evidence.get("positive_effect_row_count")) <= 0:
        missing.append("missing_positive_effect_at_or_above_mde")
    if _int_or_zero(direct_evidence.get("activation_observed_count")) <= 0:
        missing.append("missing_activation_observed")
    if _int_or_zero(direct_evidence.get("objective_effect_observed_count")) <= 0:
        missing.append("missing_objective_effect_telemetry")
    if _int_or_zero(direct_evidence.get("phase_telemetry_observed_count")) <= 0:
        missing.append("missing_phase_telemetry")
    observed = set(_string_items(direct_evidence.get("protected_cases_observed")))
    missing_cases = [
        case
        for case in CVRP_LARGE_TWOOPT_PROTECTED_CASES
        if case not in observed
    ]
    if missing_cases:
        missing.append("missing_cmt_case_protection_evidence")
    if (
        not missing
        and _int_or_zero(direct_evidence.get("complete_direct_evidence_row_count"))
        <= 0
    ):
        missing.append("missing_complete_direct_evidence_row")
    return missing


def _mechanism_activation_observed(
    row: Mapping[str, Any],
    *,
    family_match: Callable[[str], Mapping[str, Any]] | None = None,
    expected_family: str = "",
) -> bool:
    evidence = _mapping_or_empty(row.get("mechanism_evidence"))
    statuses: list[Any] = []
    if _mechanism_evidence_family_matches(
        evidence.get("primary_mechanism"),
        family_match=family_match,
        expected_family=expected_family,
    ):
        statuses.extend(
            [
                evidence.get("primary_activation_status"),
                evidence.get("activation_evidence_status"),
            ]
        )
    mechanisms = evidence.get("mechanisms")
    if isinstance(mechanisms, list):
        for item in mechanisms:
            if isinstance(item, Mapping) and _mechanism_evidence_family_matches(
                item.get("mechanism"),
                family_match=family_match,
                expected_family=expected_family,
            ):
                statuses.append(item.get("activation_status"))
    return any(
        _status_observed(status, ("activation_observed",))
        for status in statuses
    )


def _mechanism_objective_effect_observed(
    row: Mapping[str, Any],
    *,
    family_match: Callable[[str], Mapping[str, Any]] | None = None,
    expected_family: str = "",
) -> bool:
    evidence = _mapping_or_empty(row.get("mechanism_evidence"))
    statuses: list[Any] = []
    if _mechanism_evidence_family_matches(
        evidence.get("primary_mechanism"),
        family_match=family_match,
        expected_family=expected_family,
    ):
        statuses.extend(
            [
                evidence.get("primary_effect_status"),
                evidence.get("objective_effect_status"),
            ]
        )
    mechanisms = evidence.get("mechanisms")
    if isinstance(mechanisms, list):
        for item in mechanisms:
            if isinstance(item, Mapping) and _mechanism_evidence_family_matches(
                item.get("mechanism"),
                family_match=family_match,
                expected_family=expected_family,
            ):
                statuses.append(item.get("effect_status"))
    return any(
        _status_observed(
            status,
            (
                "objective_effect_observed",
                "mixed_objective_effect",
                "mixed_positive",
                "positive",
                "zero_objective_effect",
            ),
        )
        for status in statuses
    )


def _mechanism_evidence_family_matches(
    value: Any,
    *,
    family_match: Callable[[str], Mapping[str, Any]] | None,
    expected_family: str,
) -> bool:
    text = str(value or "").strip()
    if not text:
        return family_match is None and not str(expected_family or "").strip()
    if family_match is None:
        expected = str(expected_family or "").strip()
        return not expected or text == expected
    return family_match(text).get("matches") is True


def _cvrp_protected_cases_observed(row: Mapping[str, Any]) -> set[str]:
    observed: set[str] = set()
    for key in (
        "case_protection_evidence",
        "protected_case_evidence",
        "case_level_total_distance_deltas",
        "case_level_deltas",
        "case_metrics",
        "case_results",
        "case_level_results",
        "per_case_results",
        "per_case",
    ):
        observed.update(_protected_cases_from_case_payload(row.get(key)))
    mechanism_evidence = _mapping_or_empty(row.get("mechanism_evidence"))
    for key in (
        "case_protection_evidence",
        "protected_case_evidence",
        "case_level_total_distance_deltas",
        "case_level_deltas",
        "case_results",
    ):
        observed.update(_protected_cases_from_case_payload(mechanism_evidence.get(key)))
    return observed


def _protected_cases_from_case_payload(value: Any) -> set[str]:
    observed: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            case = _protected_case_name(key)
            if case and _case_payload_has_objective_delta_evidence(item):
                observed.add(case)
            if isinstance(item, Mapping):
                embedded_case = _protected_case_from_mapping(item)
                if (
                    embedded_case
                    and _case_payload_has_objective_delta_evidence(item)
                ):
                    observed.add(embedded_case)
                observed.update(_protected_cases_from_case_payload(item))
            elif isinstance(item, list):
                observed.update(_protected_cases_from_case_payload(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                case = _protected_case_from_mapping(item)
                if case and _case_payload_has_objective_delta_evidence(item):
                    observed.add(case)
                observed.update(_protected_cases_from_case_payload(item))
            elif isinstance(item, list):
                observed.update(_protected_cases_from_case_payload(item))
    return observed


def _protected_case_from_mapping(value: Mapping[str, Any]) -> str | None:
    for key in (
        "case",
        "case_id",
        "case_name",
        "instance",
        "instance_id",
        "problem_case",
        "protected_case",
        "name",
    ):
        case = _protected_case_name(value.get(key))
        if case:
            return case
    return None


def _protected_case_name(value: Any) -> str | None:
    text = str(value or "").upper().replace("-", "_")
    for case in CVRP_LARGE_TWOOPT_PROTECTED_CASES:
        if case in text:
            return case
    return None


def _case_payload_has_objective_delta_evidence(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return _float_or_none(value) is not None
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(
                marker in key_text
                for marker in (
                    "candidate_minus_champion",
                    "champion_minus_candidate",
                    "candidate_minus_baseline",
                    "baseline_minus_candidate",
                    "delta",
                    "distance",
                    "objective",
                    "cost",
                    "improvement",
                )
            ) and _payload_has_numeric_evidence(item):
                return True
            if (
                isinstance(item, (Mapping, list))
                and _case_payload_has_objective_delta_evidence(item)
            ):
                return True
        return False
    if isinstance(value, list):
        return any(_case_payload_has_objective_delta_evidence(item) for item in value)
    return False


def _payload_has_numeric_evidence(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return _float_or_none(value) is not None
    if isinstance(value, Mapping):
        return any(_payload_has_numeric_evidence(item) for item in value.values())
    if isinstance(value, list):
        return any(_payload_has_numeric_evidence(item) for item in value)
    return False


def _cvrp_large_twoopt_phase_telemetry_observed(row: Mapping[str, Any]) -> bool:
    summary = _mapping_or_empty(row.get("candidate_phase_telemetry_summary"))
    buckets = _mapping_or_empty(summary.get("buckets"))
    for name, payload in buckets.items():
        if not isinstance(payload, Mapping):
            continue
        if not _is_cvrp_large_twoopt_phase_name(str(name)):
            continue
        if _float_or_none(payload.get("weighted_sum_ms")) not in (None, 0.0):
            return True
        if _float_or_none(payload.get("max_ms")) not in (None, 0.0):
            return True
    for key in (
        "solver_algorithm_phase_improvement_counts",
        "phase_improvement_counts",
    ):
        counts = _mapping_or_empty(summary.get(key))
        if _nested_positive_count_for_phase(
            counts,
            phase_match=_is_cvrp_large_twoopt_phase_name,
        ) > 0:
            return True
    return False


def _is_cvrp_large_twoopt_phase_name(value: str) -> bool:
    normalized = (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )
    compact = normalized.replace("_", "")
    excluded_markers = (
        "cross_route",
        "crossroute",
        "two_opt_star",
        "twooptstar",
        "2optstar",
        "size70_two_opt",
        "size70twoopt",
        "unbounded",
        "vns",
        "fallback",
    )
    if any(marker in normalized or marker in compact for marker in excluded_markers):
        return False
    return (
        "two_opt" in normalized
        or "twoopt" in compact
        or "2opt" in compact
    )


def _status_observed(status: Any, accepted: tuple[str, ...]) -> bool:
    text = str(status or "").strip().lower()
    if text == "observed":
        return True
    return text in accepted


def _nested_positive_count(value: Mapping[str, Any]) -> int:
    total = 0
    for item in value.values():
        if isinstance(item, Mapping):
            total += _nested_positive_count(item)
        else:
            total += max(0, _int_or_zero(item))
    return total


def _nested_positive_count_for_phase(
    value: Mapping[str, Any],
    *,
    phase_match: Callable[[str], bool],
) -> int:
    total = 0
    for key, item in value.items():
        if isinstance(item, Mapping):
            total += _nested_positive_count_for_phase(
                item,
                phase_match=phase_match,
            )
        elif phase_match(str(key)):
            total += max(0, _int_or_zero(item))
    return total


def _is_cvrp_large_twoopt_family(value: str) -> bool:
    return _cvrp_large_twoopt_family_match(value)["matches"]


def _cvrp_large_twoopt_family_match(value: str) -> dict[str, Any]:
    normalized = (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )
    compact = normalized.replace("_", "")
    twoopt_candidate = (
        "two_opt" in normalized
        or "2opt" in compact
        or "twoopt" in compact
    )
    if not twoopt_candidate:
        return {
            "matches": False,
            "twoopt_candidate": False,
            "reason": "not_twoopt_family",
        }

    excluded_markers = (
        "cross_route",
        "crossroute",
        "two_opt_star",
        "twooptstar",
        "2optstar",
        "unbounded",
        "vns",
        "fallback",
    )
    if any(marker in normalized or marker in compact for marker in excluded_markers):
        return {
            "matches": False,
            "twoopt_candidate": True,
            "reason": "excluded_default_avoid_twoopt_family",
        }

    seed_guidance = {
        REQUIRED_MECHANISM_ID,
    }
    if normalized in seed_guidance:
        return {
            "matches": True,
            "twoopt_candidate": True,
            "reason": "matched_prepared_large_twoopt_seed_family",
        }

    canonical = {
        "bounded_large_twoopt",
    }
    if normalized in canonical:
        return {
            "matches": True,
            "twoopt_candidate": True,
            "reason": "matched_canonical_large_twoopt_family",
        }

    large_scope = (
        "large" in normalized
        or "xl" in normalized
        or "size70" in compact
    )
    bounded_or_deadline_scope = (
        "bounded" in normalized
        or "deadline" in normalized
        or "time_guard" in normalized
        or "time_bounded" in normalized
        or "guarded" in normalized
        or "capped" in normalized
    )
    if large_scope and bounded_or_deadline_scope:
        return {
            "matches": True,
            "twoopt_candidate": True,
            "reason": "matched_scoped_large_twoopt_family",
        }
    if large_scope and (
        "intra" in normalized
        or "route_internal" in normalized
    ):
        return {
            "matches": False,
            "twoopt_candidate": True,
            "reason": "missing_bounded_deadline_twoopt_scope",
        }
    return {
        "matches": False,
        "twoopt_candidate": True,
        "reason": "missing_large_bounded_intra_twoopt_scope",
    }


def cvrp_large_twoopt_interpretation(
    *,
    current_run_evidence: bool,
    invalid_infra_only: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    formal_screened_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
    large_twoopt_available: bool,
    large_twoopt_family_available: bool,
    large_twoopt_direct_evidence_ready: bool,
) -> str:
    if invalid_infra_only:
        return "invalid_infra_only_no_research_conclusion"
    if not current_run_evidence:
        return "prepared_only_launch_required"
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            return "quality_blocked_no_protocol_twoopt_conclusion"
        if formal_screened_candidates > 0:
            return "screened_without_protocol_evaluation"
        return "insufficient_current_run_evidence"
    if not handoff_complete:
        return "protocol_evaluated_handoff_incomplete"
    if not (
        measurement_available
        and runtime_available
        and continuity_available
    ):
        return "protocol_evaluated_review_inputs_incomplete"
    if not large_twoopt_family_available:
        return "protocol_evaluated_without_large_twoopt_signal"
    if not large_twoopt_direct_evidence_ready:
        return "protocol_evaluated_without_large_twoopt_direct_evidence"
    if not large_twoopt_available:
        return "protocol_evaluated_without_large_twoopt_signal"
    return "bounded_twoopt_review_ready"


def cvrp_large_twoopt_evidence_gaps(
    *,
    current_run_evidence: bool,
    invalid_infra_only: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    runtime_available: bool,
    continuity_available: bool,
    large_twoopt_available: bool,
    large_twoopt_family_available: bool,
    large_twoopt_direct_evidence_ready: bool,
) -> list[str]:
    gaps: list[str] = []
    if not handoff_complete:
        gaps.append("cvrp_large_twoopt_handoff_requirements_incomplete")
    if invalid_infra_only:
        gaps.append("invalid_infra_only_no_research_conclusion")
        return gaps
    if not current_run_evidence:
        gaps.append("launch_required_before_bounded_twoopt_conclusion")
        return gaps
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            gaps.append("quality_blocked_before_protocol_evaluation")
        else:
            gaps.append("no_protocol_evaluated_candidates")
    if not measurement_available:
        gaps.append("missing_measurement_effect_summary")
    if not runtime_available:
        gaps.append("missing_runtime_feedback_summary")
    if not continuity_available:
        gaps.append("missing_research_continuity_summary")
    if protocol_evaluated_candidates > 0 and not large_twoopt_family_available:
        gaps.append("missing_large_twoopt_mechanism_signal")
    elif (
        protocol_evaluated_candidates > 0
        and not large_twoopt_direct_evidence_ready
    ):
        gaps.append("missing_large_twoopt_direct_evidence")
    elif protocol_evaluated_candidates > 0 and not large_twoopt_available:
        gaps.append("missing_large_twoopt_mechanism_signal")
    return gaps


def _research_continuity_action_counts(entries: Any) -> dict[str, int]:
    counts = {
        "same_mechanism_selected": 0,
        "same_mechanism_observed": 0,
        "branch_lessons_satisfied": 0,
        "branch_lessons_required": 0,
        "branch_lesson_semantic_gap_count": 0,
        "weak_positive_accepted": 0,
        "weak_positive_observed": 0,
    }
    if not isinstance(entries, list):
        return counts
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        same_mechanism = _mapping_or_empty(entry.get("same_mechanism_followup"))
        lessons = _mapping_or_empty(entry.get("branch_lesson_usage"))
        transfer = _mapping_or_empty(entry.get("weak_positive_transfer"))
        counts["same_mechanism_selected"] += _int_or_zero(
            same_mechanism.get("selected_same_branch_refinement_count")
        )
        counts["same_mechanism_observed"] += _int_or_zero(
            same_mechanism.get("observed_opportunity_count")
        )
        counts["branch_lessons_satisfied"] += _int_or_zero(
            lessons.get("satisfied_count")
        )
        counts["branch_lessons_required"] += _int_or_zero(
            lessons.get("requirement_count")
        )
        counts["branch_lesson_semantic_gap_count"] += _int_or_zero(
            lessons.get("semantic_gap_count")
        )
        counts["weak_positive_accepted"] += _int_or_zero(
            transfer.get("accepted_count")
        )
        counts["weak_positive_observed"] += _int_or_zero(
            transfer.get("observed_opportunity_count")
        )
    return counts


def problem_research_continuity_signal(
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = _mapping_or_empty(research_continuity_summary.get("aggregate"))
    counts = _research_continuity_action_counts(
        research_continuity_summary.get("entries")
    )
    max_branch_depth = _int_or_zero(aggregate.get("max_branch_depth"))
    mechanism_family_counts = _int_mapping(aggregate.get("mechanism_family_counts"))
    active_shape_counts = _int_mapping(aggregate.get("active_shape_counts"))
    same_mechanism_observed = counts["same_mechanism_observed"]
    same_mechanism_selected = counts["same_mechanism_selected"]
    same_mechanism_missed = max(
        0,
        same_mechanism_observed - same_mechanism_selected,
    )
    missed_all_same_mechanism_opportunities = (
        same_mechanism_observed > 0 and same_mechanism_selected <= 0
    )
    substantive = (
        (
            max_branch_depth >= 2
            or same_mechanism_selected > 0
            or counts["branch_lessons_satisfied"] > 0
            or counts["weak_positive_accepted"] > 0
        )
        and not missed_all_same_mechanism_opportunities
    )
    return {
        "substantive": substantive,
        "max_branch_depth": max_branch_depth,
        "same_mechanism_observed": same_mechanism_observed,
        "same_mechanism_selected": same_mechanism_selected,
        "same_mechanism_missed": same_mechanism_missed,
        "branch_lessons_required": counts["branch_lessons_required"],
        "branch_lessons_satisfied": counts["branch_lessons_satisfied"],
        "weak_positive_observed": counts["weak_positive_observed"],
        "weak_positive_accepted": counts["weak_positive_accepted"],
        "mechanism_family_counts": mechanism_family_counts,
        "active_shape_counts": active_shape_counts,
    }


def _increment_count(
    counts: dict[str, int],
    key: str,
    amount: int = 1,
) -> None:
    if not key:
        return
    counts[key] = counts.get(key, 0) + amount


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(item) for key, item in sorted(value.items())}


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "CVRP_LARGE_TWOOPT_PROTECTED_CASES",
    "CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS",
    "CVRP_LARGE_TWOOPT_REVIEW_AXES",
    "cvrp_large_twoopt_evidence_gaps",
    "cvrp_large_twoopt_handoff_requirements",
    "cvrp_large_twoopt_interpretation",
    "cvrp_large_twoopt_mechanism_signal",
    "problem_research_continuity_signal",
]
