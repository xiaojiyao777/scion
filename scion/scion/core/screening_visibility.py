"""Direct screening evidence projections.

This module exposes measured protocol facts.  It does not infer candidate
intent, observability value, research novelty, or proposal quality from those
facts.
"""

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


def mechanism_evidence_for_protocol(protocol: Any) -> dict[str, Any]:
    """Return measured mechanism activation/effect facts from telemetry."""

    existing = getattr(protocol, "mechanism_evidence", None)
    if isinstance(existing, Mapping) and existing:
        from scion.protocol.experiment.proposal_evidence import (
            is_proposal_mechanism_evidence_envelope,
        )

        # Problem-owned proposal evidence has its own typed scope.  Treating it
        # as the legacy per-mechanism diagnostic shape manufactures
        # ``unknown`` activation/effect fields that the provider never
        # asserted and can mis-bind unrelated telemetry to the active
        # hypothesis.
        if is_proposal_mechanism_evidence_envelope(existing):
            return dict(existing)
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
        (hook_ids if entry["role"] == "wrapper_hook" else primary_ids).append(
            mechanism
        )
    primary = (
        primary_ids[0]
        if primary_ids
        else mechanisms[0]["mechanism"] if mechanisms else ""
    )
    primary_entry = next(
        (item for item in mechanisms if item.get("mechanism") == primary),
        {},
    )
    return {
        "declared_mechanism_count": len(mechanisms),
        "primary_mechanism": primary,
        "wrapper_hook_mechanisms": hook_ids,
        "hook_activation_observed": any(
            item.get("role") == "wrapper_hook"
            and str(item.get("activation_status") or "") == "observed"
            for item in mechanisms
        ),
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
    """Return problem/telemetry-owned diagnostics without host search advice."""

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
    activation = str(
        mechanism_evidence.get("primary_activation_status") or ""
    ).strip()
    diagnostic_kind = str(
        mechanism_evidence.get("primary_diagnostic_kind") or ""
    ).strip()
    if (
        primary
        and mechanism_evidence.get("hook_activation_observed")
        and activation in {"missing", "zero", ""}
    ):
        diagnostics.append(
            "wrapper hook activated, but primary mechanism had no local "
            "activation evidence in this screening result"
        )
    if diagnostic_kind == "not_evaluated/not_triggered":
        diagnostics.append(
            "primary mechanism was not evaluated or its trigger did not fire"
        )
    stats = getattr(protocol, "stats", None)
    case_total = _safe_int(getattr(stats, "n_cases", 0))
    if (
        no_objective_effect
        and case_total > 0
        and _safe_int(getattr(stats, "ties", 0)) == case_total
        and _safe_int(getattr(stats, "wins", 0)) == 0
        and _safe_int(getattr(stats, "losses", 0)) == 0
    ):
        diagnostics.append("all evaluated screening cases tied")
    return tuple(dict.fromkeys(diagnostics))


def opportunity_status_for_diagnostics(
    diagnostics: tuple[str, ...],
    *,
    existing: str = "",
) -> str:
    if existing and existing != "unknown":
        return existing
    return "observed" if diagnostics else "unknown"


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


def _activation_evidence_status(entry: Mapping[str, Any]) -> str:
    status = str(entry.get("activation_status") or "").strip()
    return status or "unknown"


def _objective_effect_status(
    protocol: Any,
    entry: Mapping[str, Any],
) -> str:
    status = str(entry.get("effect_status") or "").strip()
    if status:
        return status
    return "no_effect" if no_objective_effect_for_protocol(protocol) else "unknown"


def _looks_like_wrapper_hook(mechanism: str) -> bool:
    text = mechanism.lower()
    return any(marker in text for marker in ("hook", "wrapper", "bridge"))


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "mechanism_evidence_for_protocol",
    "no_objective_effect_for_protocol",
    "opportunity_diagnostics_for_protocol",
    "opportunity_status_for_diagnostics",
    "runtime_aggregate_exclusion_for_protocol",
    "runtime_confidence_for_protocol",
    "runtime_evidence_policy_counts_for_steps",
    "runtime_evidence_policy_for_protocol",
    "runtime_evidence_policy_summary",
    "runtime_gate_visibility_for_protocol",
    "runtime_gate_visibility_summary",
    "telemetry_guard_for_protocol",
]
