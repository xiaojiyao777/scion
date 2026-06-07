"""Generic visibility helpers for screening diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_EPS = 1e-12
_RUNTIME_CONFIDENCE_MIN_PAIRS = 4
_RUNTIME_SEVERE_SLOW_RATIO = 1.50
_RUNTIME_SEVERE_SLOW_DELTA_MS = 100.0
_RUNTIME_REGRESSION_RATE = 0.90
_FRESH_RUNTIME_STATUSES = {"fresh_champion_required", "fresh_required"}
_LOW_RUNTIME_STATUSES = {
    "fresh_champion_required",
    "fresh_required",
    "incomplete",
    "insufficient",
    "missing",
    "none",
    "unknown_low",
}
_LOW_RUNTIME_CONFIDENCES = {
    "incomplete",
    "insufficient",
    "low",
    "low_cached_champion",
    "missing",
    "none",
    "unknown_low",
}
_CANDIDATE_INTENT_COUNT_KEYS = (
    "quality_candidate",
    "observability_candidate",
    "diagnostic_candidate",
    "unknown",
)
_OBSERVABILITY_VALUE_COUNT_KEYS = (
    "observability_value_observed",
    "observability_value_partial",
    "observability_value_missing",
    "observability_value_not_applicable",
)
_OBSERVABILITY_INTENT_TERMS = {
    "observability",
    "instrument",
    "instrumentation",
    "visibility",
    "telemetry_bridge",
    "telemetry_probe",
    "coverage",
    "coverage_probe",
    "probe",
}
_DIAGNOSTIC_INTENT_TERMS = {
    "audit",
    "cached_champion",
    "diagnostic",
    "fresh_champion",
    "fresh_champion_required",
    "low_cached_champion",
    "low_sample_diagnostic",
    "not_evaluated",
    "not_triggered",
    "runtime_aggregate_excluded",
    "runtime_budget",
    "tool_budget",
    "tool_loop",
}
_STRUCTURED_TEXT_EXCLUDE_KEYS = {
    "detail",
    "detail_summary",
    "expected_effect",
    "exposed_summary",
    "hypothesis_text",
    "prompt",
    "proposal_guidance",
    "rationale",
    "raw_text",
    "summary",
    "text",
    "transcript",
}


def runtime_confidence_for_protocol(
    protocol: Any,
    *,
    runtime_ratio: float | None,
    runtime_delta: float | None,
    runtime_regression_rate: float | None,
    runtime_pairs: int,
) -> str:
    """Return prompt/audit-visible confidence for aggregate runtime fields."""

    declared = str(getattr(protocol, "runtime_confidence", "") or "").strip()
    if declared and declared not in {"unknown", "high"}:
        return declared
    if runtime_pairs <= 0:
        return "missing"
    if runtime_pairs >= _RUNTIME_CONFIDENCE_MIN_PAIRS:
        return "sufficient"
    severe_ratio = (
        runtime_ratio is not None and runtime_ratio >= _RUNTIME_SEVERE_SLOW_RATIO
    )
    severe_delta = (
        runtime_delta is not None and runtime_delta >= _RUNTIME_SEVERE_SLOW_DELTA_MS
    )
    severe_rate = (
        runtime_regression_rate is not None
        and runtime_regression_rate >= _RUNTIME_REGRESSION_RATE
    )
    if severe_ratio and severe_delta and severe_rate:
        return "sufficient"
    return "low_sample_diagnostic"


def runtime_aggregate_exclusion_for_protocol(protocol: Any) -> dict[str, Any]:
    """Explain why aggregate runtime stats are absent while evidence exists."""

    stats = getattr(protocol, "stats", None)
    if protocol is None or stats is None:
        return {}
    runtime_pairs = _safe_int(getattr(stats, "runtime_pairs", 0))
    if runtime_pairs > 0:
        return {}
    confidence = str(getattr(protocol, "runtime_confidence", "") or "").strip()
    cached_pairs = _safe_int(getattr(protocol, "champion_cached_runtime_pairs", 0))
    candidate_summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    candidate_pair_count = _candidate_runtime_pair_count(candidate_summary)
    if not confidence or confidence in {"high", "unknown"}:
        return {}
    if cached_pairs <= 0 and candidate_pair_count <= 0:
        return {}
    return {
        "schema_version": "runtime_aggregate_exclusion.v1",
        "excluded": True,
        "reason": confidence,
        "runtime_confidence": confidence,
        "runtime_pairs": runtime_pairs,
        "champion_cached_runtime_pairs": cached_pairs,
        "candidate_runtime_pair_evidence_count": candidate_pair_count,
        "summary": (
            "Aggregate runtime stats are excluded because champion runtime "
            "evidence is low confidence, while per-pair candidate/runtime "
            "evidence remains available for audit and proposal feedback."
        ),
    }


def runtime_evidence_policy_summary(
    *,
    runtime_confidence: Any = "",
    runtime_evidence_status: Any = "",
    runtime_pairs: Any = 0,
    champion_cached_runtime_pairs: Any = 0,
    runtime_aggregate_excluded: Any = False,
    candidate_runtime_pair_evidence_count: Any = 0,
) -> dict[str, Any]:
    """Return generic policy metadata for interpreting runtime evidence.

    The payload is proposal/audit visibility only. It does not change formal
    gate semantics and must not be copied into DecisionFeatures.
    """

    confidence = str(runtime_confidence or "").strip().lower() or "unknown"
    status = str(runtime_evidence_status or "").strip().lower() or "unknown"
    runtime_pair_count = _safe_int(runtime_pairs)
    cached_pair_count = _safe_int(champion_cached_runtime_pairs)
    candidate_pair_count = _safe_int(candidate_runtime_pair_evidence_count)
    aggregate_excluded = bool(runtime_aggregate_excluded)
    fresh_required = status in _FRESH_RUNTIME_STATUSES
    low_confidence = (
        confidence in _LOW_RUNTIME_CONFIDENCES
        or confidence.startswith("low")
        or "cached" in confidence
    )
    incomplete_status = (
        status in _LOW_RUNTIME_STATUSES
        or "incomplete" in status
        or "insufficient" in status
    )
    low_or_incomplete = bool(
        fresh_required
        or low_confidence
        or incomplete_status
        or aggregate_excluded
    )
    reason_codes: list[str] = []
    if low_confidence:
        reason_codes.append("RUNTIME_EVIDENCE_LOW_OR_CACHED_CONFIDENCE")
    if fresh_required:
        reason_codes.append("RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED")
    elif incomplete_status:
        reason_codes.append("RUNTIME_EVIDENCE_INCOMPLETE")
    if aggregate_excluded:
        reason_codes.append("RUNTIME_AGGREGATE_EXCLUDED")
    if not reason_codes:
        reason_codes.append("RUNTIME_EVIDENCE_SUPPORTING_SIGNAL_ONLY")
    return _drop_empty(
        {
            "schema_version": "runtime_evidence_policy.v1",
            "runtime_evidence_confidence": confidence,
            "runtime_evidence_status": status,
            "runtime_pairs": runtime_pair_count,
            "champion_cached_runtime_pairs": cached_pair_count,
            "candidate_runtime_pair_evidence_count": candidate_pair_count,
            "fresh_champion_required": fresh_required,
            "runtime_aggregate_excluded": aggregate_excluded,
            "standalone_optimization_signal": False,
            "runtime_signal_role": (
                "audit_or_proposal_guidance_only"
                if low_or_incomplete
                else "tie_break_supporting_signal"
            ),
            "policy_reason_codes": reason_codes,
            "proposal_guidance": (
                "Do not use runtime evidence as a standalone optimization "
                "signal; require fresh or non-runtime objective evidence before "
                "planning from this runtime signal."
                if low_or_incomplete
                else "Runtime evidence is supporting tie-break evidence, not a "
                "standalone optimization signal."
            ),
            "proposal_guidance_only": True,
            "decision_features_excluded": True,
        }
    )


def runtime_gate_visibility_summary(
    *,
    stage: Any = "",
    gate_outcome: Any = "",
    reason_codes: Any = (),
    runtime_confidence: Any = "",
    runtime_evidence_status: Any = "",
    runtime_pairs: Any = 0,
    champion_cached_runtime_pairs: Any = 0,
    failed_pairs: Any = 0,
    candidate_failed_pairs: Any = 0,
    champion_failed_pairs: Any = 0,
    runtime_budget_diagnostic: Any = None,
) -> dict[str, Any]:
    """Separate runtime/objective audit reasons without changing decisions."""

    stage_value = _status_value(stage)
    outcome = _status_value(gate_outcome)
    codes = tuple(
        str(code).strip()
        for code in (reason_codes or ())
        if str(code).strip()
    )
    runtime_status = _status_value(runtime_evidence_status) or "unknown"
    runtime_conf = _status_value(runtime_confidence) or "unknown"
    runtime_pair_count = _safe_int(runtime_pairs)
    cached_pair_count = _safe_int(champion_cached_runtime_pairs)
    failed_pair_count = _safe_int(failed_pairs)
    candidate_failed_count = _safe_int(candidate_failed_pairs)
    champion_failed_count = _safe_int(champion_failed_pairs)
    budget_diagnostic = (
        dict(runtime_budget_diagnostic)
        if isinstance(runtime_budget_diagnostic, Mapping)
        else {}
    )
    budget_code = str(budget_diagnostic.get("code") or "").strip()
    fresh_required = (
        runtime_status in _FRESH_RUNTIME_STATUSES
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in codes
    )
    runtime_incomplete = (
        runtime_status in _LOW_RUNTIME_STATUSES
        or "INCOMPLETE_EVIDENCE" in codes
        or "INCOMPLETE_RUNTIME_EVIDENCE" in codes
        or (
            cached_pair_count > 0
            and runtime_pair_count <= 0
            and not fresh_required
        )
    )
    objective_codes = tuple(
        code
        for code in codes
        if not _runtime_visibility_code(code)
        and not _runtime_budget_code(code, budget_code)
    )
    reason_semantics: list[str] = []
    visibility_reason_codes: list[str] = []
    if objective_codes:
        reason_semantics.append("objective_fail")
        visibility_reason_codes.append("OBJECTIVE_GATE_REASON_PRESENT")
    if fresh_required:
        reason_semantics.append("runtime_fresh_champion_required")
        visibility_reason_codes.append("RUNTIME_FRESH_CHAMPION_REEVALUATION_REQUIRED")
    elif runtime_incomplete:
        reason_semantics.append("runtime_incomplete_advisory")
        visibility_reason_codes.append("RUNTIME_INCOMPLETE_ADVISORY")
    if budget_code:
        reason_semantics.append("runtime_budget_saturation")
        visibility_reason_codes.append("RUNTIME_BUDGET_SATURATION_VISIBLE")
    if not reason_semantics:
        reason_semantics.append("formal_gate_only")
        visibility_reason_codes.append("FORMAL_GATE_REASON_ONLY")
    recommendation = "none"
    if fresh_required:
        recommendation = "fresh_champion_re_evaluation_required"
    elif budget_code:
        recommendation = "inspect_runtime_budget_saturation"
    elif runtime_incomplete:
        recommendation = "runtime_evidence_advisory_only"
    elif objective_codes and stage_value == "screening":
        recommendation = "continue_objective_research"
    return _drop_empty(
        {
            "schema_version": "runtime_gate_visibility.v1",
            "stage": stage_value or None,
            "gate_outcome": outcome or None,
            "reason_semantics": reason_semantics,
            "reason_codes": list(visibility_reason_codes),
            "objective_reason_codes": list(objective_codes),
            "runtime_reason_codes": [
                code for code in codes if _runtime_visibility_code(code)
            ],
            "runtime_budget_diagnostic_code": budget_code or None,
            "runtime_confidence": runtime_conf,
            "runtime_evidence_status": runtime_status,
            "runtime_pairs": runtime_pair_count,
            "champion_cached_runtime_pairs": cached_pair_count,
            "failed_pairs": failed_pair_count,
            "candidate_failed_pairs": candidate_failed_count,
            "champion_failed_pairs": champion_failed_count,
            "fresh_champion_required": fresh_required,
            "rerun_recommendation": recommendation,
            "fresh_champion_requirement": (
                "fresh_champion_re_evaluation_required_before_runtime_tie_advances"
                if fresh_required
                else None
            ),
            "formal_rerun_scheduled": False,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )


def runtime_gate_visibility_for_protocol(protocol: Any) -> dict[str, Any]:
    """Return runtime gate reason visibility for a completed protocol result."""

    stats = getattr(protocol, "stats", None)
    if protocol is None or stats is None:
        return {}
    return runtime_gate_visibility_summary(
        stage=getattr(getattr(protocol, "stage", None), "value", None)
        or getattr(protocol, "stage", ""),
        gate_outcome=getattr(protocol, "gate_outcome", ""),
        reason_codes=getattr(protocol, "reason_codes", ()),
        runtime_confidence=getattr(protocol, "runtime_confidence", ""),
        runtime_evidence_status=getattr(
            protocol,
            "runtime_evidence_status",
            getattr(stats, "runtime_evidence_status", ""),
        ),
        runtime_pairs=getattr(stats, "runtime_pairs", 0),
        champion_cached_runtime_pairs=getattr(
            protocol,
            "champion_cached_runtime_pairs",
            getattr(stats, "champion_cached_runtime_pairs", 0),
        ),
        failed_pairs=getattr(stats, "failed_pairs", 0),
        candidate_failed_pairs=getattr(stats, "candidate_failed_pairs", 0),
        champion_failed_pairs=getattr(stats, "champion_failed_pairs", 0),
        runtime_budget_diagnostic=_runtime_budget_diagnostic_from_protocol(protocol),
    )


def runtime_evidence_policy_for_protocol(protocol: Any) -> dict[str, Any]:
    """Return generic runtime evidence policy metadata for a protocol result."""

    stats = getattr(protocol, "stats", None)
    if protocol is None or stats is None:
        return {}
    exclusion = runtime_aggregate_exclusion_for_protocol(protocol)
    return runtime_evidence_policy_summary(
        runtime_confidence=getattr(protocol, "runtime_confidence", ""),
        runtime_evidence_status=getattr(
            protocol,
            "runtime_evidence_status",
            getattr(stats, "runtime_evidence_status", ""),
        ),
        runtime_pairs=getattr(stats, "runtime_pairs", 0),
        champion_cached_runtime_pairs=getattr(
            protocol,
            "champion_cached_runtime_pairs",
            getattr(stats, "champion_cached_runtime_pairs", 0),
        ),
        runtime_aggregate_excluded=bool(exclusion.get("excluded")),
        candidate_runtime_pair_evidence_count=exclusion.get(
            "candidate_runtime_pair_evidence_count",
            0,
        ),
    )


def _runtime_visibility_code(code: str) -> bool:
    upper = code.upper()
    return (
        upper.startswith("RUNTIME_")
        or "RUNTIME" in upper
        or "INCOMPLETE_EVIDENCE" in upper
        or upper in {"CANDIDATE_RUNTIME_FAILURE", "CHAMPION_RUNTIME_FAILURE"}
    )


def _runtime_budget_code(code: str, budget_code: str) -> bool:
    upper = code.upper()
    return bool(
        (budget_code and code == budget_code)
        or "RUNTIME_BUDGET" in upper
        or upper.endswith("_RUNTIME_BUDGET_SATURATION")
    )


def candidate_intent_counts_for_steps(steps: Any) -> dict[str, int]:
    """Return compact campaign counters for generic candidate intent labels."""

    counts = {key: 0 for key in _CANDIDATE_INTENT_COUNT_KEYS}
    for step in steps or ():
        intent = candidate_intent_visibility_for_step(step).get(
            "candidate_intent",
            "unknown",
        )
        key = str(intent or "unknown")
        if key not in counts:
            key = "unknown"
        counts[key] += 1
    return counts


def observability_value_counts_for_steps(steps: Any) -> dict[str, Any]:
    """Return campaign counters for proposal/report-only observability value."""

    counts = {key: 0 for key in _OBSERVABILITY_VALUE_COUNT_KEYS}
    reason_counts: dict[str, int] = {}
    applicable = 0
    total = 0
    decision_excluded_count = 0
    for step in steps or ():
        visibility = observability_value_visibility_for_step(step)
        if not visibility:
            continue
        total += 1
        status = str(
            visibility.get("observability_value_status")
            or "observability_value_missing"
        )
        if status not in counts:
            status = "observability_value_missing"
        counts[status] += 1
        if status != "observability_value_not_applicable":
            applicable += 1
        for code in visibility.get("reason_codes") or ():
            key = str(code)
            reason_counts[key] = reason_counts.get(key, 0) + 1
        if visibility.get("decision_features_excluded") is True:
            decision_excluded_count += 1
    return {
        "schema_version": "observability_value_counts.v1",
        "observability_value_total": total,
        "observability_value_applicable_count": applicable,
        **counts,
        "reason_code_counts": reason_counts,
        "decision_features_excluded_count": decision_excluded_count,
    }


def observability_value_visibility_for_step(step: Any) -> dict[str, Any]:
    """Return report/proposal-only value visibility for diagnostic candidates.

    This visibility records whether an observability/diagnostic candidate made
    structured protocol evidence easier to inspect. It is intentionally not a
    DecisionFeatures source and does not alter formal gates.
    """

    intent_visibility = candidate_intent_visibility_for_step(step)
    intent = str(intent_visibility.get("candidate_intent") or "unknown")
    protocol = getattr(step, "protocol_result", None)
    if intent not in {"observability_candidate", "diagnostic_candidate"}:
        return _observability_value_payload(
            candidate_intent=intent,
            status="observability_value_not_applicable",
            reason_codes=("OBSERVABILITY_VALUE_NOT_APPLICABLE_TO_QUALITY_SEARCH",),
            details={},
        )
    if protocol is None:
        return _observability_value_payload(
            candidate_intent=intent,
            status="observability_value_missing",
            reason_codes=("OBSERVABILITY_VALUE_MISSING_PROTOCOL_EVIDENCE",),
            details={},
        )
    evidence = _observability_value_evidence_for_protocol(protocol)
    return _observability_value_payload(
        candidate_intent=intent,
        status=evidence["status"],
        reason_codes=tuple(evidence["reason_codes"]),
        details=evidence["details"],
    )


def observability_value_visibility_from_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize a status/progress observability value payload.

    ``record_protocol_progress`` does not have a full StepRecord, so this helper
    accepts already-structured progress fields and uses the same output schema.
    """

    existing = payload.get("observability_value_visibility")
    if isinstance(existing, Mapping):
        base = dict(existing)
        base.setdefault("schema_version", "observability_value_visibility.v1")
        base.setdefault("proposal_visibility_only", True)
        base.setdefault("decision_features_excluded", True)
        return base
    intent = str(payload.get("candidate_intent") or "").strip()
    if not intent:
        kind = str(payload.get("attempt_kind") or "").strip().lower()
        intent = (
            "diagnostic_candidate"
            if "diagnostic" in kind
            else "observability_candidate"
            if "observability" in kind
            else "unknown"
        )
    if intent not in {"observability_candidate", "diagnostic_candidate"}:
        return {}
    evidence = _observability_value_evidence_from_sources(
        mechanism_evidence=payload.get("mechanism_evidence"),
        surface_summary=payload.get("candidate_surface_runtime_summary"),
        phase_summary=payload.get("candidate_phase_telemetry_summary"),
        runtime_confidence=payload.get("runtime_confidence"),
        runtime_evidence_status=payload.get("runtime_evidence_status"),
        runtime_pairs=payload.get("runtime_pairs"),
        champion_cached_runtime_pairs=payload.get("champion_cached_runtime_pairs"),
        runtime_budget_diagnostic=payload.get("runtime_budget_diagnostic"),
        telemetry_failure_details=payload.get("telemetry_failure_details"),
        candidate_runtime_failure_categories=payload.get(
            "candidate_runtime_failure_categories"
        ),
        candidate_first_runtime_failure=payload.get("candidate_first_runtime_failure"),
    )
    return _observability_value_payload(
        candidate_intent=intent,
        status=evidence["status"],
        reason_codes=tuple(evidence["reason_codes"]),
        details=evidence["details"],
    )


def candidate_intent_visibility_for_step(step: Any) -> dict[str, Any]:
    """Classify candidate intent from structured audit/protocol fields only.

    This helper is reporting/proposal visibility. It deliberately avoids raw
    proposal text and has no path into DecisionFeatures.
    """

    protocol = getattr(step, "protocol_result", None)
    tokens = list(_candidate_intent_tokens_for_step(step))
    token_text = " ".join(tokens).lower()
    quality_hits = _quality_intent_hits_for_step(step)
    observability_hits = sorted(
        term for term in _OBSERVABILITY_INTENT_TERMS if term in token_text
    )
    diagnostic_hits = sorted(
        term for term in _DIAGNOSTIC_INTENT_TERMS if term in token_text
    )
    no_effect = False
    if protocol is not None:
        try:
            no_effect = no_objective_effect_for_protocol(protocol)
        except Exception:  # pragma: no cover - defensive visibility only
            no_effect = False
    if observability_hits:
        intent = "observability_candidate"
        reason_codes = [
            f"CANDIDATE_INTENT_OBSERVABILITY_{_reason_suffix(hit)}"
            for hit in observability_hits[:4]
        ]
    elif quality_hits:
        intent = "quality_candidate"
        reason_codes = [
            f"CANDIDATE_INTENT_QUALITY_{_reason_suffix(hit)}"
            for hit in quality_hits[:4]
        ]
    elif diagnostic_hits:
        intent = "diagnostic_candidate"
        reason_codes = [
            f"CANDIDATE_INTENT_DIAGNOSTIC_{_reason_suffix(hit)}"
            for hit in diagnostic_hits[:4]
        ]
    elif protocol is not None:
        intent = "quality_candidate"
        reason_codes = ["CANDIDATE_INTENT_QUALITY_FORMAL_PROTOCOL"]
    else:
        intent = "unknown"
        reason_codes = ["CANDIDATE_INTENT_UNKNOWN"]
    interpretation = None
    if intent in {"observability_candidate", "diagnostic_candidate"} and no_effect:
        interpretation = "diagnostic_not_quality_failure"
    elif intent == "quality_candidate":
        interpretation = "quality_candidate_evidence"
    return _drop_empty(
        {
            "schema_version": "candidate_intent_visibility.v1",
            "candidate_intent": intent,
            "candidate_intent_reason_codes": reason_codes,
            "quality_search_interpretation": interpretation,
            "formal_decision_unchanged": True,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )


def _observability_value_payload(
    *,
    candidate_intent: str,
    status: str,
    reason_codes: tuple[str, ...],
    details: Mapping[str, Any],
) -> dict[str, Any]:
    return _drop_empty(
        {
            "schema_version": "observability_value_visibility.v1",
            "candidate_intent": candidate_intent or "unknown",
            "observability_value_status": status,
            "reason_codes": list(reason_codes),
            "details": dict(details),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )


def _observability_value_evidence_for_protocol(protocol: Any) -> dict[str, Any]:
    return _observability_value_evidence_from_sources(
        mechanism_evidence=mechanism_evidence_for_protocol(protocol),
        surface_summary=getattr(protocol, "candidate_surface_runtime_summary", {}),
        phase_summary=getattr(protocol, "candidate_phase_telemetry_summary", {}),
        runtime_confidence=getattr(protocol, "runtime_confidence", ""),
        runtime_evidence_status=getattr(protocol, "runtime_evidence_status", ""),
        runtime_pairs=getattr(getattr(protocol, "stats", None), "runtime_pairs", 0),
        champion_cached_runtime_pairs=getattr(
            protocol,
            "champion_cached_runtime_pairs",
            getattr(
                getattr(protocol, "stats", None),
                "champion_cached_runtime_pairs",
                0,
            ),
        ),
        runtime_budget_diagnostic=_runtime_budget_diagnostic_from_protocol(protocol),
        telemetry_failure_details=(),
        candidate_runtime_failure_categories=getattr(
            protocol,
            "candidate_runtime_failure_categories",
            {},
        ),
        candidate_first_runtime_failure=getattr(
            protocol,
            "candidate_first_runtime_failure",
            None,
        ),
    )


def _observability_value_evidence_from_sources(
    *,
    mechanism_evidence: Any,
    surface_summary: Any,
    phase_summary: Any,
    runtime_confidence: Any,
    runtime_evidence_status: Any,
    runtime_pairs: Any,
    champion_cached_runtime_pairs: Any,
    runtime_budget_diagnostic: Any,
    telemetry_failure_details: Any,
    candidate_runtime_failure_categories: Any,
    candidate_first_runtime_failure: Any,
) -> dict[str, Any]:
    mechanism = mechanism_evidence if isinstance(mechanism_evidence, Mapping) else {}
    surface = surface_summary if isinstance(surface_summary, Mapping) else {}
    phase = phase_summary if isinstance(phase_summary, Mapping) else {}
    guard = surface.get("telemetry_guard") if isinstance(surface, Mapping) else None
    if not isinstance(guard, Mapping):
        guard = {}
    field_coverage = _telemetry_field_coverage(surface, guard, phase)
    telemetry_has_coverage = field_coverage["field_count"] > 0
    activation_status = _status_value(
        mechanism.get("primary_activation_status")
        or mechanism.get("activation_evidence_status")
    )
    effect_status = _status_value(
        mechanism.get("primary_effect_status")
        or mechanism.get("objective_effect_status")
    )
    telemetry_outcome = _status_value(mechanism.get("telemetry_outcome"))
    diagnostic_kind = _status_value(mechanism.get("primary_diagnostic_kind"))
    runtime_status = _mechanism_runtime_status(mechanism, guard)
    runtime_conf = _status_value(runtime_confidence)
    runtime_status_value = _status_value(runtime_evidence_status)
    runtime_pair_count = _safe_int(runtime_pairs)
    cached_pair_count = _safe_int(champion_cached_runtime_pairs)
    budget_diagnostic = (
        runtime_budget_diagnostic
        if isinstance(runtime_budget_diagnostic, Mapping)
        else surface.get("runtime_budget_diagnostic")
    )
    budget_observable = isinstance(budget_diagnostic, Mapping) and bool(
        budget_diagnostic
    )
    telemetry_detail_count = _telemetry_detail_count(telemetry_failure_details)
    runtime_failure_observable = bool(
        telemetry_detail_count
        or (
            isinstance(candidate_runtime_failure_categories, Mapping)
            and candidate_runtime_failure_categories
        )
        or isinstance(candidate_first_runtime_failure, Mapping)
        or _guard_failure_count(guard)
    )
    activation_or_effect_observed = any(
        status in {"observed", "zero", "no_effect", "telemetry_effect_zero"}
        for status in (activation_status, effect_status, telemetry_outcome)
    )
    activation_or_effect_diagnostic = any(
        status
        and status not in {"unknown", "none"}
        for status in (
            activation_status,
            effect_status,
            telemetry_outcome,
            diagnostic_kind,
        )
    )
    runtime_confidence_observable = bool(
        (
            runtime_conf
            and runtime_conf not in {"unknown", "none", "missing", "high"}
        )
        or (
            runtime_status_value
            and runtime_status_value
            not in {"unknown", "none", "missing", "sufficient"}
        )
        or runtime_pair_count > 0
        or cached_pair_count > 0
    )
    observed_categories: list[str] = []
    reason_codes: list[str] = []
    if telemetry_has_coverage:
        observed_categories.append("telemetry_coverage")
        reason_codes.append("OBSERVABILITY_VALUE_TELEMETRY_COVERAGE_OBSERVED")
    if activation_or_effect_observed:
        observed_categories.append("activation_effect")
        reason_codes.append("OBSERVABILITY_VALUE_ACTIVATION_OR_EFFECT_OBSERVABLE")
    elif activation_or_effect_diagnostic:
        reason_codes.append("OBSERVABILITY_VALUE_ACTIVATION_OR_EFFECT_DIAGNOSTIC")
    if budget_observable or runtime_status not in {"", "unknown", "none"}:
        observed_categories.append("budget")
        reason_codes.append("OBSERVABILITY_VALUE_BUDGET_FIELD_OBSERVABLE")
    if runtime_confidence_observable:
        observed_categories.append("runtime_confidence")
        reason_codes.append("OBSERVABILITY_VALUE_RUNTIME_CONFIDENCE_OBSERVABLE")
    if runtime_failure_observable or diagnostic_kind:
        observed_categories.append("failure_attribution")
        reason_codes.append("OBSERVABILITY_VALUE_FAILURE_ATTRIBUTION_OBSERVABLE")
    structured_signal_present = bool(
        observed_categories
        or activation_or_effect_diagnostic
        or field_coverage["field_count"]
        or guard
        or mechanism
        or phase
    )
    if telemetry_has_coverage and (
        activation_or_effect_observed
        or budget_observable
        or runtime_confidence_observable
        or runtime_failure_observable
        or diagnostic_kind
    ):
        status = "observability_value_observed"
    elif structured_signal_present:
        status = "observability_value_partial"
        if not reason_codes:
            reason_codes.append("OBSERVABILITY_VALUE_STRUCTURED_DIAGNOSTIC_PARTIAL")
    else:
        status = "observability_value_missing"
        reason_codes.append("OBSERVABILITY_VALUE_STRUCTURED_EVIDENCE_MISSING")
    return {
        "status": status,
        "reason_codes": tuple(dict.fromkeys(reason_codes)),
        "details": _drop_empty(
            {
                "observed_categories": sorted(set(observed_categories)),
                "telemetry_field_coverage": field_coverage,
                "activation_status": activation_status or None,
                "effect_status": effect_status or None,
                "runtime_status": runtime_status or None,
                "runtime_confidence": runtime_conf or None,
                "runtime_evidence_status": runtime_status_value or None,
                "runtime_pairs": runtime_pair_count,
                "champion_cached_runtime_pairs": cached_pair_count,
                "runtime_budget_diagnostic_code": (
                    str(budget_diagnostic.get("code") or "").strip()
                    if isinstance(budget_diagnostic, Mapping)
                    else None
                ),
                "diagnostic_kind": diagnostic_kind or None,
                "telemetry_outcome": telemetry_outcome or None,
                "telemetry_failure_detail_count": telemetry_detail_count,
                "guard_failure_count": _guard_failure_count(guard),
            }
        ),
    }


def _telemetry_field_coverage(
    surface_summary: Mapping[str, Any],
    guard: Mapping[str, Any],
    phase_summary: Mapping[str, Any],
) -> dict[str, Any]:
    field_count = 0
    present = 0
    missing = 0
    positive = 0
    zero = 0
    categories: set[str] = set()
    for category, category_payload in (
        ("surface", surface_summary.get("fields")),
        ("phase", phase_summary),
        ("guard", guard.get("fields")),
    ):
        if isinstance(category_payload, Mapping):
            for field_payload in category_payload.values():
                if not isinstance(field_payload, Mapping):
                    continue
                field_count += 1
                categories.add(category)
                present += _safe_int(
                    field_payload.get("present")
                    or field_payload.get("candidate_present")
                )
                missing += _safe_int(
                    field_payload.get("missing")
                    or field_payload.get("candidate_missing")
                )
                positive += _safe_int(field_payload.get("candidate_positive"))
                zero += _safe_int(field_payload.get("candidate_zero"))
    for item in guard.get("mechanism_diagnostics") or ():
        if not isinstance(item, Mapping):
            continue
        for category in ("activation", "effect", "runtime", "budget"):
            category_payload = item.get(category)
            if not isinstance(category_payload, Mapping):
                continue
            field_count += len(category_payload.get("fields") or ()) or 1
            categories.add(category)
            present += _safe_int(category_payload.get("candidate_present"))
            missing += _safe_int(category_payload.get("candidate_missing"))
            positive += _safe_int(category_payload.get("candidate_positive"))
            zero += _safe_int(category_payload.get("candidate_zero"))
    return {
        "field_count": field_count,
        "candidate_present": present,
        "candidate_missing": missing,
        "candidate_positive": positive,
        "candidate_zero": zero,
        "categories": sorted(categories),
    }


def _runtime_budget_diagnostic_from_protocol(protocol: Any) -> Mapping[str, Any]:
    surface = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(surface, Mapping):
        return {}
    diagnostic = surface.get("runtime_budget_diagnostic")
    return diagnostic if isinstance(diagnostic, Mapping) else {}


def _mechanism_runtime_status(
    mechanism: Mapping[str, Any],
    guard: Mapping[str, Any],
) -> str:
    for item in mechanism.get("mechanisms") or ():
        if not isinstance(item, Mapping):
            continue
        status = _status_value(item.get("runtime_status"))
        if status:
            return status
    for item in guard.get("mechanism_diagnostics") or ():
        if not isinstance(item, Mapping):
            continue
        status = _status_value(item.get("runtime_status"))
        if status:
            return status
    return ""


def _telemetry_detail_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1
    if isinstance(value, (list, tuple)):
        return sum(1 for item in value if isinstance(item, Mapping))
    return 0


def _guard_failure_count(guard: Mapping[str, Any]) -> int:
    total = 0
    for key in ("failures", "warnings"):
        items = guard.get(key)
        if isinstance(items, (list, tuple)):
            total += sum(1 for item in items if isinstance(item, Mapping))
    return total


def _status_value(value: Any) -> str:
    return str(value or "").strip().lower()


def runtime_evidence_policy_counts_for_steps(steps: Any) -> dict[str, Any]:
    """Return campaign-level counters for runtime evidence policy visibility."""

    role_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    total = 0
    fresh_required_count = 0
    aggregate_excluded_count = 0
    low_cached_count = 0
    standalone_false_count = 0
    decision_excluded_count = 0
    for step in steps or ():
        protocol = getattr(step, "protocol_result", None)
        if protocol is None:
            continue
        policy = runtime_evidence_policy_for_protocol(protocol)
        if not policy:
            continue
        total += 1
        role = str(policy.get("runtime_signal_role") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        for code in policy.get("policy_reason_codes") or ():
            key = str(code)
            reason_counts[key] = reason_counts.get(key, 0) + 1
        if policy.get("fresh_champion_required"):
            fresh_required_count += 1
        if policy.get("runtime_aggregate_excluded"):
            aggregate_excluded_count += 1
        confidence = str(policy.get("runtime_evidence_confidence") or "").lower()
        if "cached" in confidence:
            low_cached_count += 1
        if policy.get("standalone_optimization_signal") is False:
            standalone_false_count += 1
        if policy.get("decision_features_excluded") is True:
            decision_excluded_count += 1
    return {
        "schema_version": "runtime_evidence_policy_counts.v1",
        "runtime_evidence_policy_total": total,
        "runtime_signal_role_counts": role_counts,
        "policy_reason_code_counts": reason_counts,
        "fresh_champion_required_count": fresh_required_count,
        "runtime_aggregate_excluded_count": aggregate_excluded_count,
        "low_cached_champion_count": low_cached_count,
        "standalone_optimization_signal_false_count": standalone_false_count,
        "decision_features_excluded_count": decision_excluded_count,
    }


def mechanism_evidence_for_protocol(protocol: Any) -> dict[str, Any]:
    """Return compact, generic mechanism evidence from telemetry diagnostics."""

    existing = getattr(protocol, "mechanism_evidence", None)
    if isinstance(existing, Mapping) and existing:
        payload = dict(existing)
        primary_entry = {
            "activation_status": payload.get("primary_activation_status"),
            "effect_status": payload.get("primary_effect_status"),
        }
        payload.setdefault(
            "activation_evidence_status",
            _activation_evidence_status(primary_entry),
        )
        payload.setdefault(
            "objective_effect_status",
            _objective_effect_status(protocol, primary_entry),
        )
        return payload
    guard = telemetry_guard_for_protocol(protocol)
    diagnostics = guard.get("mechanism_diagnostics") if guard else None
    if not isinstance(diagnostics, list):
        return {}
    mechanisms: list[dict[str, Any]] = []
    hook_ids: list[str] = []
    primary_ids: list[str] = []
    for item in diagnostics:
        if not isinstance(item, Mapping):
            continue
        mechanism = str(item.get("mechanism") or "").strip()
        if not mechanism:
            continue
        entry = {
            "mechanism": mechanism,
            "role": "wrapper_hook" if _looks_like_wrapper_hook(mechanism) else "primary",
            "activation_status": item.get("activation_status"),
            "runtime_status": item.get("runtime_status"),
            "effect_status": item.get("effect_status"),
            "diagnostic_kind": item.get("diagnostic_kind"),
            "telemetry_outcome": item.get("telemetry_outcome"),
        }
        mechanisms.append(entry)
        if entry["role"] == "wrapper_hook":
            hook_ids.append(mechanism)
        else:
            primary_ids.append(mechanism)
    primary = (
        primary_ids[0]
        if primary_ids
        else mechanisms[0]["mechanism"] if mechanisms else ""
    )
    hook_activation_observed = any(
        item.get("role") == "wrapper_hook"
        and str(item.get("activation_status") or "") == "observed"
        for item in mechanisms
    )
    primary_entry = next(
        (item for item in mechanisms if item.get("mechanism") == primary),
        {},
    )
    return {
        "declared_mechanism_count": len(mechanisms),
        "primary_mechanism": primary,
        "wrapper_hook_mechanisms": hook_ids,
        "hook_activation_observed": hook_activation_observed,
        "primary_activation_status": primary_entry.get("activation_status"),
        "primary_effect_status": primary_entry.get("effect_status"),
        "activation_evidence_status": _activation_evidence_status(primary_entry),
        "objective_effect_status": _objective_effect_status(protocol, primary_entry),
        "primary_diagnostic_kind": primary_entry.get("diagnostic_kind"),
        "mechanisms": mechanisms,
    }


def opportunity_diagnostics_for_protocol(
    protocol: Any,
    *,
    mechanism_evidence: Mapping[str, Any],
    no_objective_effect: bool,
) -> tuple[str, ...]:
    """Return compact opportunity diagnostics for screening visibility."""

    existing = getattr(protocol, "opportunity_diagnostics", None)
    if existing:
        return tuple(str(item) for item in existing if str(item).strip())
    diagnostics: list[str] = []
    guard = telemetry_guard_for_protocol(protocol)
    if guard is not None:
        for key in ("mechanism_opportunity_diagnostics", "opportunity_diagnostics"):
            raw_items = guard.get(key)
            if not isinstance(raw_items, list):
                continue
            for raw in raw_items:
                text = str(raw.get("summary") if isinstance(raw, Mapping) else raw)
                text = text.strip()
                if text and text not in diagnostics:
                    diagnostics.append(text)
    primary = str(mechanism_evidence.get("primary_mechanism") or "").strip()
    primary_activation = str(
        mechanism_evidence.get("primary_activation_status") or ""
    ).strip()
    primary_kind = str(mechanism_evidence.get("primary_diagnostic_kind") or "").strip()
    if (
        primary
        and mechanism_evidence.get("hook_activation_observed")
        and primary_activation in {"missing", "zero", ""}
    ):
        diagnostics.append(
            "wrapper hook activated, but primary mechanism was not evaluated "
            "with mechanism-local evidence in this screening set"
        )
    if primary_kind == "not_evaluated/not_triggered":
        diagnostics.append(
            "primary mechanism not evaluated or trigger did not fire in current screening"
        )
    stats = protocol.stats
    case_total = _safe_int(getattr(stats, "n_cases", 0))
    all_case_ties = (
        case_total > 0
        and _safe_int(getattr(stats, "ties", 0)) == case_total
        and _safe_int(getattr(stats, "wins", 0)) == 0
        and _safe_int(getattr(stats, "losses", 0)) == 0
    )
    if no_objective_effect and all_case_ties and case_total <= 2:
        diagnostics.append(
            "all screening cases tied on a tiny sample; opportunity and runtime "
            "diagnostics are low confidence"
        )
    runtime_budget = (
        protocol.candidate_surface_runtime_summary or {}
        if isinstance(protocol.candidate_surface_runtime_summary, Mapping)
        else {}
    )
    budget_payload = runtime_budget.get("runtime_budget_diagnostic")
    if isinstance(budget_payload, Mapping):
        code = str(budget_payload.get("code") or "").lower()
        if no_objective_effect and all_case_ties and "saturation" in code:
            diagnostics.append(
                "all screening cases tied while runtime budget is saturated; "
                "current screening has low confidence for this mechanism class"
            )
    return tuple(dict.fromkeys(diagnostics))


def opportunity_status_for_diagnostics(
    diagnostics: tuple[str, ...],
    *,
    existing: str = "",
) -> str:
    """Return a compact status label for opportunity diagnostics."""

    if existing and existing != "unknown":
        return existing
    if diagnostics and any(
        "opportunity" in item or "not evaluated" in item for item in diagnostics
    ):
        return "opportunity_poor"
    if diagnostics:
        return "low_confidence"
    return "unknown"


def telemetry_guard_for_protocol(protocol: Any) -> Mapping[str, Any] | None:
    summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(summary, Mapping):
        return None
    guard = summary.get("telemetry_guard")
    return guard if isinstance(guard, Mapping) else None


def no_objective_effect_for_protocol(protocol: Any) -> bool:
    stats = protocol.stats
    median_delta = _optional_float(getattr(stats, "median_delta", None))
    return (
        _safe_int(getattr(stats, "wins", 0)) == 0
        and _safe_int(getattr(stats, "losses", 0)) == 0
        and median_delta is not None
        and abs(median_delta) <= _EPS
    )


def _candidate_intent_tokens_for_step(step: Any) -> tuple[str, ...]:
    tokens: list[str] = []
    protocol = getattr(step, "protocol_result", None)
    hypothesis = getattr(step, "hypothesis", None)
    if hypothesis is not None:
        tokens.extend(
            _structured_tokens(
                {
                    "action": getattr(hypothesis, "action", ""),
                    "change_locus": getattr(hypothesis, "change_locus", ""),
                    "predicted_direction": getattr(
                        hypothesis,
                        "predicted_direction",
                        "",
                    ),
                    "target_runtime_effect": getattr(
                        hypothesis,
                        "target_runtime_effect",
                        "",
                    ),
                    "runtime_budget_strategy": getattr(
                        hypothesis,
                        "runtime_budget_strategy",
                        "",
                    ),
                    "expected_telemetry": getattr(
                        hypothesis,
                        "expected_telemetry",
                        {},
                    ),
                    "novelty_signature": getattr(
                        hypothesis,
                        "novelty_signature",
                        {},
                    ),
                    "mechanism_changes": getattr(
                        hypothesis,
                        "mechanism_changes",
                        (),
                    ),
                }
            )
        )
    tokens.extend(_structured_tokens(getattr(step, "decision_reason_codes", ()) or ()))
    tokens.extend(
        _structured_tokens(
            {
                "attempt_kind": getattr(step, "attempt_kind", ""),
                "repair_policy_reason": getattr(step, "repair_policy_reason", ""),
                "repair_mechanism_ids": getattr(step, "repair_mechanism_ids", ()),
                "scheduler_slot": getattr(step, "scheduler_slot", ""),
                "scheduler_reason": getattr(step, "scheduler_reason", ""),
                "scheduler_audit_metadata": getattr(
                    step,
                    "scheduler_audit_metadata",
                    {},
                ),
                "proposal_session_ref": getattr(step, "proposal_session_ref", {}),
            }
        )
    )
    if protocol is not None:
        tokens.extend(
            _structured_tokens(
                {
                    "stage": getattr(protocol, "stage", ""),
                    "gate_outcome": getattr(protocol, "gate_outcome", ""),
                    "reason_codes": getattr(protocol, "reason_codes", ()),
                    "selected_surface": getattr(protocol, "selected_surface", ""),
                    "opportunity_status": getattr(
                        protocol,
                        "opportunity_status",
                        "",
                    ),
                    "mechanism_evidence": getattr(
                        protocol,
                        "mechanism_evidence",
                        {},
                    ),
                    "candidate_surface_runtime_summary": getattr(
                        protocol,
                        "candidate_surface_runtime_summary",
                        {},
                    ),
                    "candidate_phase_telemetry_summary": getattr(
                        protocol,
                        "candidate_phase_telemetry_summary",
                        {},
                    ),
                }
            )
        )
    return tuple(dict.fromkeys(token for token in tokens if token))


def _quality_intent_hits_for_step(step: Any) -> list[str]:
    hits: list[str] = []
    hypothesis = getattr(step, "hypothesis", None)
    if hypothesis is None:
        return hits
    predicted_direction = str(
        getattr(hypothesis, "predicted_direction", "") or ""
    ).strip()
    if predicted_direction == "improve":
        hits.append("predicted_direction_improve")
    if tuple(getattr(hypothesis, "target_objectives", ()) or ()):
        hits.append("target_objectives")
    return list(dict.fromkeys(hits))


def _structured_tokens(value: Any, *, key: str = "") -> tuple[str, ...]:
    key_lower = str(key or "").strip().lower()
    if key_lower in _STRUCTURED_TEXT_EXCLUDE_KEYS:
        return ()
    if any(marker in key_lower for marker in ("prompt", "transcript", "text")):
        return ()
    if isinstance(value, Mapping):
        tokens: list[str] = []
        for item_key, item_value in value.items():
            item_key_text = str(item_key or "").strip()
            tokens.extend(_structured_tokens(item_value, key=item_key_text))
        return tuple(tokens)
    if isinstance(value, (list, tuple, set, frozenset)):
        tokens = []
        for item in value:
            tokens.extend(_structured_tokens(item, key=key_lower))
        return tuple(tokens)
    for attr in ("id", "change_type"):
        if hasattr(value, attr):
            return tuple(
                token
                for token in (
                    str(getattr(value, "id", "") or "").strip(),
                    str(getattr(value, "change_type", "") or "").strip(),
                )
                if token
            )
    if isinstance(value, bool):
        return (f"{key_lower}_{str(value).lower()}",) if key_lower else ()
    if isinstance(value, (int, float)):
        return ()
    text = str(value or "").strip()
    if not text or len(text) > 120:
        return ()
    return (text,)


def _reason_suffix(value: str) -> str:
    suffix = "".join(ch if ch.isalnum() else "_" for ch in value.upper()).strip("_")
    return suffix or "UNKNOWN"


def _candidate_runtime_pair_count(summary: Any) -> int:
    if not isinstance(summary, Mapping):
        return 0
    fields = summary.get("fields")
    if not isinstance(fields, Mapping):
        return 0
    max_seen = 0
    for field_summary in fields.values():
        if not isinstance(field_summary, Mapping):
            continue
        present = _safe_int(field_summary.get("present"))
        missing = _safe_int(field_summary.get("missing"))
        empty = _safe_int(field_summary.get("empty"))
        failed = _safe_int(field_summary.get("failed"))
        max_seen = max(max_seen, present + missing + empty + failed)
    return max_seen


def _activation_evidence_status(entry: Mapping[str, Any]) -> str:
    status = str(entry.get("activation_status") or "").strip()
    if status == "observed":
        return "activation_observed"
    if status == "missing":
        return "missing_activation"
    if status == "zero":
        return "zero_activation"
    if status:
        return status
    return "missing_activation"


def _objective_effect_status(protocol: Any, entry: Mapping[str, Any]) -> str:
    effect_status = str(entry.get("effect_status") or "").strip()
    if no_objective_effect_for_protocol(protocol):
        return "zero_objective_effect"
    if effect_status in {"observed", "missing", "zero"}:
        return effect_status
    if effect_status:
        return effect_status
    return "unknown"


def _looks_like_wrapper_hook(mechanism: str) -> bool:
    text = mechanism.lower()
    return (
        "hook" in text
        or text.startswith("scheduler_")
        or text.startswith("wrapper_")
        or text.endswith("_wrapper")
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _drop_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != {} and value != []
    }
