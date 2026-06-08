"""Generic visibility helpers for screening diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.core.screening_visibility_runtime import (
    runtime_aggregate_exclusion_for_protocol,
    runtime_confidence_for_protocol,
    runtime_evidence_policy_counts_for_steps,
    runtime_evidence_policy_for_protocol,
    runtime_evidence_policy_summary,
    runtime_gate_visibility_for_protocol,
    runtime_gate_visibility_summary,
)

_EPS = 1e-12
_ALGORITHM_QUALITY_CANDIDATE = "algorithm_quality_candidate"
_OBSERVABILITY_CANDIDATE = "observability_candidate"
_REPAIR_OR_INFRA_CANDIDATE = "repair_or_infra_candidate"
_UNKNOWN_CANDIDATE = "unknown"
_CANDIDATE_INTENT_COUNT_KEYS = (
    _ALGORITHM_QUALITY_CANDIDATE,
    _OBSERVABILITY_CANDIDATE,
    _REPAIR_OR_INFRA_CANDIDATE,
    _UNKNOWN_CANDIDATE,
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
_REPAIR_OR_INFRA_INTENT_TERMS = {
    "contract",
    "failure_repair",
    "infra",
    "infrastructure",
    "interface_repair",
    "repair",
    "schema_repair",
    "telemetry_wiring",
    "verification_repair",
}
_REPAIR_OR_INFRA_DECLARED_INTENT_TERMS = (
    _REPAIR_OR_INFRA_INTENT_TERMS - {"repair"}
)
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


def candidate_intent_counts_for_steps(steps: Any) -> dict[str, int]:
    """Return compact campaign counters for generic candidate intent labels."""

    counts = {key: 0 for key in _CANDIDATE_INTENT_COUNT_KEYS}
    for step in steps or ():
        intent = candidate_intent_visibility_for_step(step).get(
            "candidate_intent",
            _UNKNOWN_CANDIDATE,
        )
        key = _canonical_candidate_intent(intent)
        if key not in counts:
            key = _UNKNOWN_CANDIDATE
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
    intent = _canonical_candidate_intent(
        intent_visibility.get("candidate_intent") or _UNKNOWN_CANDIDATE
    )
    protocol = getattr(step, "protocol_result", None)
    if intent not in {_OBSERVABILITY_CANDIDATE, _REPAIR_OR_INFRA_CANDIDATE}:
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
        base["candidate_intent"] = (
            _canonical_candidate_intent(base.get("candidate_intent"))
            or _UNKNOWN_CANDIDATE
        )
        base.setdefault("proposal_visibility_only", True)
        base.setdefault("decision_features_excluded", True)
        return base
    intent = _canonical_candidate_intent(payload.get("candidate_intent"))
    if not intent:
        kind = str(payload.get("attempt_kind") or "").strip().lower()
        intent = (
            _REPAIR_OR_INFRA_CANDIDATE
            if "diagnostic" in kind or "repair" in kind or "infra" in kind
            else _OBSERVABILITY_CANDIDATE
            if "observability" in kind
            else _UNKNOWN_CANDIDATE
        )
    if intent not in {_OBSERVABILITY_CANDIDATE, _REPAIR_OR_INFRA_CANDIDATE}:
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
    intent_tokens = list(_candidate_declared_intent_tokens_for_step(step))
    diagnostic_tokens = list(_candidate_diagnostic_tokens_for_step(step))
    intent_token_text = " ".join(intent_tokens).lower()
    diagnostic_token_text = " ".join(diagnostic_tokens).lower()
    quality_hits = _quality_intent_hits_for_step(step)
    observability_hits = sorted(
        term for term in _OBSERVABILITY_INTENT_TERMS if term in intent_token_text
    )
    diagnostic_hits = sorted(
        {
            term
            for term in _DIAGNOSTIC_INTENT_TERMS | _REPAIR_OR_INFRA_INTENT_TERMS
            if term in diagnostic_token_text
        }
        | {
            term
            for term in _REPAIR_OR_INFRA_DECLARED_INTENT_TERMS
            if term in intent_token_text
        }
    )
    no_effect = False
    if protocol is not None:
        try:
            no_effect = no_objective_effect_for_protocol(protocol)
        except Exception:  # pragma: no cover - defensive visibility only
            no_effect = False
    if quality_hits:
        intent = _ALGORITHM_QUALITY_CANDIDATE
        reason_codes = [
            f"CANDIDATE_INTENT_ALGORITHM_QUALITY_{_reason_suffix(hit)}"
            for hit in quality_hits[:4]
        ]
    elif observability_hits:
        intent = _OBSERVABILITY_CANDIDATE
        reason_codes = [
            f"CANDIDATE_INTENT_OBSERVABILITY_{_reason_suffix(hit)}"
            for hit in observability_hits[:4]
        ]
    elif diagnostic_hits:
        intent = _REPAIR_OR_INFRA_CANDIDATE
        reason_codes = [
            f"CANDIDATE_INTENT_REPAIR_OR_INFRA_{_reason_suffix(hit)}"
            for hit in diagnostic_hits[:4]
        ]
    elif protocol is not None:
        intent = _ALGORITHM_QUALITY_CANDIDATE
        reason_codes = ["CANDIDATE_INTENT_ALGORITHM_QUALITY_FORMAL_PROTOCOL"]
    else:
        intent = _UNKNOWN_CANDIDATE
        reason_codes = ["CANDIDATE_INTENT_UNKNOWN"]
    interpretation = None
    if (
        intent in {_OBSERVABILITY_CANDIDATE, _REPAIR_OR_INFRA_CANDIDATE}
        and no_effect
    ):
        interpretation = "diagnostic_not_quality_failure"
    elif intent == _ALGORITHM_QUALITY_CANDIDATE:
        interpretation = "algorithm_quality_candidate_evidence"
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
            "candidate_intent": _canonical_candidate_intent(candidate_intent)
            or _UNKNOWN_CANDIDATE,
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


def _candidate_declared_intent_tokens_for_step(step: Any) -> tuple[str, ...]:
    tokens: list[str] = []
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
                    "target_file": getattr(hypothesis, "target_file", ""),
                }
            )
        )
    patch = getattr(step, "patch", None)
    if patch is not None:
        tokens.extend(
            _structured_tokens(
                {
                    "patch_action": getattr(patch, "action", ""),
                    "patch_file_path": getattr(patch, "file_path", ""),
                    "patch_mechanism_changes": getattr(
                        patch,
                        "mechanism_changes",
                        (),
                    ),
                }
            )
        )
    return tuple(dict.fromkeys(token for token in tokens if token))


def _candidate_diagnostic_tokens_for_step(step: Any) -> tuple[str, ...]:
    tokens: list[str] = []
    protocol = getattr(step, "protocol_result", None)
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
    if predicted_direction in {"improve", "tradeoff"}:
        hits.append("predicted_direction_quality")
    if tuple(getattr(hypothesis, "target_objectives", ()) or ()):
        hits.append("target_objectives")
    non_observability_mechanism_changes = [
        change
        for change in getattr(hypothesis, "mechanism_changes", ()) or ()
        if not _mechanism_change_is_observability_or_repair(change)
    ]
    if non_observability_mechanism_changes:
        hits.append("mechanism_changes")
    return list(dict.fromkeys(hits))


def _mechanism_change_is_observability_or_repair(change: Any) -> bool:
    tokens = " ".join(_structured_tokens(change)).lower()
    if not tokens:
        return False
    return any(term in tokens for term in _OBSERVABILITY_INTENT_TERMS) or any(
        term in tokens for term in _REPAIR_OR_INFRA_DECLARED_INTENT_TERMS
    )


def _canonical_candidate_intent(value: Any) -> str:
    intent = str(value or "").strip()
    if not intent:
        return ""
    aliases = {
        "quality_candidate": _ALGORITHM_QUALITY_CANDIDATE,
        "algorithm_quality_candidate": _ALGORITHM_QUALITY_CANDIDATE,
        "observability_candidate": _OBSERVABILITY_CANDIDATE,
        "diagnostic_candidate": _REPAIR_OR_INFRA_CANDIDATE,
        "repair_or_infra_candidate": _REPAIR_OR_INFRA_CANDIDATE,
        "unknown": _UNKNOWN_CANDIDATE,
    }
    return aliases.get(intent, intent)


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
