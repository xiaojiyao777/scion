"""Runtime evidence visibility helpers for screening diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


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


def _runtime_budget_diagnostic_from_protocol(protocol: Any) -> Mapping[str, Any]:
    surface = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(surface, Mapping):
        return {}
    diagnostic = surface.get("runtime_budget_diagnostic")
    return diagnostic if isinstance(diagnostic, Mapping) else {}


def _status_value(value: Any) -> str:
    return str(value or "").strip().lower()


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
