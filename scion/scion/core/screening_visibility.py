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
