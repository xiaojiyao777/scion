"""Generic formal telemetry validation classification helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.core.models import ExperimentStage, ProtocolResult

TELEMETRY_VALIDATION_REPAIRABLE = "TELEMETRY_VALIDATION_REPAIRABLE"

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


def telemetry_validation_failure_codes(
    protocol_result: ProtocolResult | None,
) -> tuple[str, ...]:
    """Return stable reason codes for a repairable telemetry validation failure."""
    if not is_repairable_telemetry_validation_failure(protocol_result):
        return ()
    guard = telemetry_guard_summary(protocol_result)
    codes = [
        str(item.get("code") or "").strip()
        for item in _failure_items(guard)
        if _is_repairable_failure(item)
    ]
    return tuple(dict.fromkeys([TELEMETRY_VALIDATION_REPAIRABLE, *codes]))


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
    parts = [
        "telemetry_validation_repairable",
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
    "TELEMETRY_VALIDATION_REPAIRABLE",
    "is_repairable_telemetry_validation_failure",
    "screened_experiment_effective",
    "telemetry_guard_summary",
    "telemetry_validation_failure_codes",
    "telemetry_validation_feedback",
]
