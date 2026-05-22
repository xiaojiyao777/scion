"""Generic formal telemetry validation classification helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.core.models import ExperimentStage, ProtocolResult

TELEMETRY_VALIDATION_REPAIRABLE = "TELEMETRY_VALIDATION_REPAIRABLE"
SCREENING_TELEMETRY_REPAIRABLE = "SCREENING_TELEMETRY_REPAIRABLE"
VALIDATION_TELEMETRY_REPAIRABLE = "VALIDATION_TELEMETRY_REPAIRABLE"
SCREENING_TELEMETRY_FAILED = "SCREENING_TELEMETRY_FAILED"
VALIDATION_TELEMETRY_FAILED = "VALIDATION_TELEMETRY_FAILED"
FROZEN_TELEMETRY_FAILED = "FROZEN_TELEMETRY_FAILED"
TELEMETRY_DECISION_DETAIL_SCHEMA = "scion.telemetry_decision_detail.v1"

_REPAIRABLE_TELEMETRY_CODES = frozenset(
    {
        "TELEMETRY_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
    }
)


def telemetry_guard_summary(
    protocol_result: ProtocolResult | None,
) -> Mapping[str, Any] | None:
    """Return the candidate telemetry guard summary when present."""
    if protocol_result is None:
        return None
    surface_summary = protocol_result.candidate_surface_runtime_summary or {}
    if not isinstance(surface_summary, Mapping):
        return None
    guard = surface_summary.get("telemetry_guard")
    return guard if isinstance(guard, Mapping) else None


def formal_telemetry_guard_failed(
    protocol_result: ProtocolResult | None,
) -> bool:
    """True when a completed protocol result failed its telemetry guard.

    Proposal previews and code-phase smoke checks do not produce ProtocolResult
    objects, so this predicate is restricted to formal protocol evidence.
    """
    if protocol_result is None:
        return False
    if _stage_value(protocol_result.stage) not in {"screening", "validation", "frozen"}:
        return False
    guard = telemetry_guard_summary(protocol_result)
    return guard is not None and bool(guard.get("passed", True)) is False


def telemetry_failure_categories(
    protocol_result: ProtocolResult | None,
) -> tuple[str, ...]:
    """Return unique failed telemetry guard categories for one formal result."""
    if not formal_telemetry_guard_failed(protocol_result):
        return ()
    guard = telemetry_guard_summary(protocol_result)
    categories: list[str] = []
    for item in _failure_items(guard):
        if str(item.get("severity") or "").strip().lower() != "fail":
            continue
        category = _normal_failure_category(item)
        if category not in categories:
            categories.append(category)
    return tuple(categories)


def telemetry_decision_details(
    protocol_result: ProtocolResult | None,
) -> tuple[dict[str, Any], ...]:
    """Return stable structured telemetry failure details for formal decisions."""
    if not formal_telemetry_guard_failed(protocol_result):
        return ()
    guard = telemetry_guard_summary(protocol_result)
    stage = _stage_value(protocol_result.stage) if protocol_result is not None else ""
    source_digest = _declaration_source_digest(protocol_result, guard)
    details: list[dict[str, Any]] = []
    for item in _failure_items(guard):
        if str(item.get("severity") or "").strip().lower() != "fail":
            continue
        field_ids = _field_ids(
            item.get("surface_field_ids")
            or item.get("surface_field_id")
            or item.get("field")
            or item.get("fields")
        )
        counters = _issue_counters(item)
        missing_fields = _explicit_field_ids(
            item,
            "missing_fields",
            "missing_field",
        )
        if not missing_fields and counters.get("candidate_missing", 0) > 0:
            missing_fields = field_ids
        invalid_fields = _explicit_field_ids(
            item,
            "invalid_fields",
            "invalid_field",
        )
        code = str(item.get("code") or "TELEMETRY_GUARD_FAILED").strip()
        if not invalid_fields and _code_indicates_invalid_field(code):
            invalid_fields = field_ids
        detail: dict[str, Any] = {
            "schema": TELEMETRY_DECISION_DETAIL_SCHEMA,
            "stage": stage or None,
            "code": code,
            "category": _normal_failure_category(item),
            "mechanism_id": _clean_optional_str(
                item.get("mechanism_id") or item.get("mechanism")
            ),
            "surface_field_id": field_ids[0] if field_ids else None,
            "surface_field_ids": field_ids,
            "runtime_role": _clean_optional_str(
                item.get("runtime_role")
                or item.get("role")
                or item.get("category")
            ),
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
            "repairable": _is_repairable_failure(item),
            "declaration_source_digest": source_digest,
            "candidate_missing": counters.get("candidate_missing", 0),
            "candidate_present": counters.get("candidate_present", 0),
            "candidate_positive": counters.get("candidate_positive", 0),
            "champion_positive": counters.get("champion_positive", 0),
        }
        details.append(detail)
    return tuple(details)


def is_repairable_telemetry_validation_failure(
    protocol_result: ProtocolResult | None,
) -> bool:
    """True when formal telemetry failed because activation was not observed."""
    if protocol_result is None:
        return False
    if protocol_result.stage not in (
        ExperimentStage.SCREENING,
        ExperimentStage.VALIDATION,
    ):
        return False
    guard = telemetry_guard_summary(protocol_result)
    if guard is None or bool(guard.get("passed", True)):
        return False
    return any(_is_repairable_failure(item) for item in _failure_items(guard))


def telemetry_repairable_stage(protocol_result: ProtocolResult | None) -> str | None:
    """Return the protocol stage for repairable activation telemetry failures."""
    if not is_repairable_telemetry_validation_failure(protocol_result):
        return None
    if protocol_result is None:
        return None
    if protocol_result.stage == ExperimentStage.SCREENING:
        return "screening"
    if protocol_result.stage == ExperimentStage.VALIDATION:
        return "validation"
    return None


def telemetry_validation_failure_codes(
    protocol_result: ProtocolResult | None,
) -> tuple[str, ...]:
    """Return stable reason codes for a repairable telemetry validation failure."""
    if not is_repairable_telemetry_validation_failure(protocol_result):
        return ()
    stage = telemetry_repairable_stage(protocol_result)
    guard = telemetry_guard_summary(protocol_result)
    codes = [
        str(item.get("code") or "").strip()
        for item in _failure_items(guard)
        if _is_repairable_failure(item)
    ]
    stage_codes = (
        (VALIDATION_TELEMETRY_REPAIRABLE, TELEMETRY_VALIDATION_REPAIRABLE)
        if stage == "validation"
        else (TELEMETRY_VALIDATION_REPAIRABLE, SCREENING_TELEMETRY_REPAIRABLE)
    )
    return tuple(dict.fromkeys([*stage_codes, *codes]))


def screened_experiment_effective(
    protocol_result: ProtocolResult | None,
) -> bool:
    """Whether a protocol result counts as an effective screened round."""
    return protocol_result is not None and not is_repairable_telemetry_validation_failure(
        protocol_result
    )


def telemetry_validation_feedback(
    protocol_result: ProtocolResult | None,
) -> str:
    """Compact prompt-facing repair guidance for formal telemetry failures."""
    if not is_repairable_telemetry_validation_failure(protocol_result):
        return ""
    guard = telemetry_guard_summary(protocol_result)
    if guard is None:
        return ""
    failures = [item for item in _failure_items(guard) if _is_repairable_failure(item)]
    if not failures:
        return ""
    first = failures[0]
    stage = telemetry_repairable_stage(protocol_result)
    parts = [
        (
            "validation_telemetry_repairable"
            if stage == "validation"
            else "telemetry_validation_repairable"
        ),
        f"code={first.get('code') or 'TELEMETRY_GUARD_FAILED'}",
    ]
    for label, key in (
        ("mechanism", "mechanism"),
        ("category", "category"),
        ("fields", "field"),
    ):
        value = str(first.get(key) or "").strip()
        if value:
            parts.append(f"{label}={value}")
    counters = _issue_counters(first)
    if counters:
        parts.extend(f"{key}={counters[key]}" for key in sorted(counters))
    candidate_runs = guard.get("candidate_runs")
    if candidate_runs not in (None, ""):
        parts.append(f"candidate_runs={candidate_runs}")
    guidance = _repair_guidance_for_issue(guard, first)
    if guidance:
        parts.append("repair_guidance=" + " ".join(guidance)[:500])
    return "; ".join(parts)


def _failure_items(guard: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if guard is None:
        return ()
    failures = guard.get("failures")
    if not isinstance(failures, Sequence) or isinstance(
        failures,
        (str, bytes, bytearray),
    ):
        return ()
    return tuple(item for item in failures if isinstance(item, Mapping))


def _normal_failure_category(item: Mapping[str, Any]) -> str:
    category = str(item.get("category") or "").strip().lower()
    if category:
        return category
    code = str(item.get("code") or "").strip().upper()
    for candidate in ("ACTIVATION", "ACTIVITY", "EFFECT", "BUDGET"):
        if candidate in code:
            return candidate.lower()
    return "unknown"


def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")


def _is_repairable_failure(item: Mapping[str, Any]) -> bool:
    code = str(item.get("code") or "").strip()
    severity = str(item.get("severity") or "").strip().lower()
    return severity == "fail" and code in _REPAIRABLE_TELEMETRY_CODES


def _issue_counters(issue: Mapping[str, Any]) -> dict[str, int]:
    counters: dict[str, int] = {}
    for key in (
        "candidate_missing",
        "candidate_present",
        "candidate_positive",
        "champion_positive",
    ):
        try:
            counters[key] = int(issue.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return counters


def _clean_optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _field_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.replace(";", ",").split(",")
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raw_values = [str(item) for item in value]
    else:
        raw_values = [str(value)]
    field_ids: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if text and text not in field_ids:
            field_ids.append(text)
    return field_ids


def _explicit_field_ids(issue: Mapping[str, Any], *keys: str) -> list[str]:
    for key in keys:
        field_ids = _field_ids(issue.get(key))
        if field_ids:
            return field_ids
    return []


def _code_indicates_invalid_field(code: str) -> bool:
    upper = code.strip().upper()
    return "INVALID" in upper or "UNDECLARED" in upper or "MISMATCH" in upper


def _declaration_source_digest(
    protocol_result: ProtocolResult | None,
    guard: Mapping[str, Any] | None,
) -> str | None:
    for source in (
        guard,
        protocol_result.candidate_surface_runtime_summary if protocol_result else None,
    ):
        if not isinstance(source, Mapping):
            continue
        for key in (
            "declaration_source_digest",
            "declaration_digest",
            "source_digest",
            "surface_digest",
            "snapshot_digest",
        ):
            value = _clean_optional_str(source.get(key))
            if value:
                return value
        declaration = source.get("declaration_source")
        if isinstance(declaration, Mapping):
            for key in ("digest", "source_digest", "snapshot_digest"):
                value = _clean_optional_str(declaration.get(key))
                if value:
                    return value
    return None


def _repair_guidance_for_issue(
    guard: Mapping[str, Any],
    issue: Mapping[str, Any],
) -> list[str]:
    mechanism = str(issue.get("mechanism") or "").strip()
    diagnostics = guard.get("mechanism_diagnostics")
    if mechanism and isinstance(diagnostics, Sequence):
        for item in diagnostics:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("mechanism") or "").strip() != mechanism:
                continue
            guidance = item.get("repair_guidance")
            if isinstance(guidance, Sequence) and not isinstance(
                guidance,
                (str, bytes, bytearray),
            ):
                return [str(entry).strip() for entry in guidance if str(entry).strip()]
    return [
        "Add direct positive activation telemetry on the declared mechanism path "
        "before treating win-rate as validated."
    ]


__all__ = [
    "FROZEN_TELEMETRY_FAILED",
    "SCREENING_TELEMETRY_FAILED",
    "SCREENING_TELEMETRY_REPAIRABLE",
    "TELEMETRY_VALIDATION_REPAIRABLE",
    "TELEMETRY_DECISION_DETAIL_SCHEMA",
    "VALIDATION_TELEMETRY_FAILED",
    "VALIDATION_TELEMETRY_REPAIRABLE",
    "formal_telemetry_guard_failed",
    "is_repairable_telemetry_validation_failure",
    "screened_experiment_effective",
    "telemetry_decision_details",
    "telemetry_failure_categories",
    "telemetry_guard_summary",
    "telemetry_repairable_stage",
    "telemetry_validation_failure_codes",
    "telemetry_validation_feedback",
]
