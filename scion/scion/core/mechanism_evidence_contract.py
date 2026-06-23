"""Generic lifecycle contract for declared mechanism telemetry evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scion.runtime.telemetry_guard.summary_signals import (
    ACTIVATED_NO_POSITIVE_EFFECT,
    EVALUATED_NO_EFFECT,
    NOT_EVALUATED_OR_TRIGGERED,
    RUNTIME_BUDGET_ZERO_OR_SUBMS,
    WIRING_SUSPECT,
)


SCHEMA_VERSION = "scion.mechanism_evidence_contract.v1"

DECLARED_NOT_TRIGGERED = "declared_not_triggered"
DECLARED_WIRING_SUSPECT = "declared_wiring_suspect"
OBSERVED_NO_EFFECT = "observed_no_effect"
OBSERVED_POSITIVE_EFFECT = "observed_positive_effect"
EFFECT_ATTRIBUTION_MISSING = "effect_attribution_missing"
UNKNOWN = "unknown"

_FOLLOWUP_DIAGNOSTIC_KINDS = frozenset(
    {
        NOT_EVALUATED_OR_TRIGGERED,
        WIRING_SUSPECT,
        RUNTIME_BUDGET_ZERO_OR_SUBMS,
        ACTIVATED_NO_POSITIVE_EFFECT,
    }
)
_NO_REPAIR_DIAGNOSTIC_KINDS = frozenset({EVALUATED_NO_EFFECT})
_POSITIVE_EFFECT_STATUSES = frozenset(
    {
        "positive",
        "observed",
        "observed_positive",
        "case_level_positive_signal",
        "objective_positive",
        "positive_objective_effect",
    }
)


@dataclass(frozen=True)
class MechanismEvidenceContract:
    """Proposal/lifecycle visibility for mechanism evidence, never Decision input."""

    schema_version: str
    declared_mechanism_ids: tuple[str, ...]
    primary_mechanism_id: str
    primary_status: str
    activation_status: str
    runtime_status: str
    effect_status: str
    diagnostic_kind: str
    repairable: bool
    followup_required: bool
    repair_mechanism_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "declared_mechanism_ids": list(self.declared_mechanism_ids),
            "primary_mechanism_id": self.primary_mechanism_id,
            "primary_status": self.primary_status,
            "activation_status": self.activation_status,
            "runtime_status": self.runtime_status,
            "effect_status": self.effect_status,
            "diagnostic_kind": self.diagnostic_kind,
            "repairable": self.repairable,
            "followup_required": self.followup_required,
            "repair_mechanism_ids": list(self.repair_mechanism_ids),
            "reason_codes": list(self.reason_codes),
            "proposal_visibility_only": self.proposal_visibility_only,
            "decision_features_excluded": self.decision_features_excluded,
        }


def mechanism_evidence_contract_for_protocol(protocol: Any) -> dict[str, Any]:
    """Build a deterministic contract payload from a ProtocolResult-like object."""

    surface_summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    telemetry_guard = (
        surface_summary.get("telemetry_guard")
        if isinstance(surface_summary, Mapping)
        else None
    )
    contract = mechanism_evidence_contract_from_sources(
        telemetry_guard_summary=telemetry_guard,
        mechanism_evidence=getattr(protocol, "mechanism_evidence", None),
    )
    return contract.as_dict() if contract is not None else {}


def mechanism_evidence_contract_from_sources(
    *,
    telemetry_guard_summary: Any = None,
    mechanism_evidence: Any = None,
) -> MechanismEvidenceContract | None:
    """Normalize telemetry guard diagnostics into a problem-neutral lifecycle payload."""

    guard = telemetry_guard_summary if isinstance(telemetry_guard_summary, Mapping) else {}
    evidence = mechanism_evidence if isinstance(mechanism_evidence, Mapping) else {}
    diagnostics = _mechanism_diagnostics(guard)
    declared_ids = _declared_mechanism_ids(guard, evidence, diagnostics)
    primary_id = _primary_mechanism_id(evidence, declared_ids, diagnostics)
    primary_diagnostic = _primary_diagnostic(
        diagnostics,
        primary_mechanism_id=primary_id,
    )

    activation_status = _status(
        primary_diagnostic.get("activation_status")
        or evidence.get("primary_activation_status")
        or evidence.get("activation_status")
        or evidence.get("activation_evidence_status")
    )
    runtime_status = _status(
        primary_diagnostic.get("runtime_status")
        or evidence.get("primary_runtime_status")
        or evidence.get("runtime_status")
    )
    effect_status = _status(
        primary_diagnostic.get("effect_status")
        or evidence.get("primary_effect_status")
        or evidence.get("effect_status")
        or evidence.get("objective_effect_status")
    )
    diagnostic_kind = _status(
        primary_diagnostic.get("diagnostic_kind")
        or evidence.get("primary_diagnostic_kind")
        or evidence.get("diagnostic_kind")
    )

    if not (
        declared_ids
        or primary_id
        or activation_status
        or runtime_status
        or effect_status
        or diagnostic_kind
    ):
        return None

    repair_mechanism_ids = _repair_mechanism_ids(
        diagnostics,
        primary_mechanism_id=primary_id,
    )
    followup_required = bool(repair_mechanism_ids)
    primary_status = _primary_status(
        diagnostic_kind=diagnostic_kind,
        effect_status=effect_status,
    )
    repairable = _repairable_for_kind(diagnostic_kind, followup_required)
    reason_codes = _reason_codes(
        primary_status=primary_status,
        diagnostic_kind=diagnostic_kind,
        followup_required=followup_required,
    )
    return MechanismEvidenceContract(
        schema_version=SCHEMA_VERSION,
        declared_mechanism_ids=declared_ids,
        primary_mechanism_id=primary_id,
        primary_status=primary_status,
        activation_status=activation_status or UNKNOWN,
        runtime_status=runtime_status or UNKNOWN,
        effect_status=effect_status or UNKNOWN,
        diagnostic_kind=diagnostic_kind or "",
        repairable=repairable,
        followup_required=followup_required,
        repair_mechanism_ids=repair_mechanism_ids,
        reason_codes=reason_codes,
    )


def mechanism_contract_followup_required(payload: Any) -> bool:
    """Return true only for proposal/lifecycle-only mechanism follow-up payloads."""

    if not isinstance(payload, Mapping):
        return False
    return bool(
        payload.get("followup_required") is True
        and payload.get("decision_features_excluded") is True
    )


def _mechanism_diagnostics(guard: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    diagnostics = guard.get("mechanism_diagnostics")
    if not isinstance(diagnostics, (list, tuple)):
        return ()
    return tuple(item for item in diagnostics if isinstance(item, Mapping))


def _declared_mechanism_ids(
    guard: Mapping[str, Any],
    evidence: Mapping[str, Any],
    diagnostics: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    ids: list[str] = []
    ids.extend(_clean_strings(guard.get("declared_mechanisms")))
    ids.extend(_clean_strings(evidence.get("declared_mechanism_ids")))
    for item in evidence.get("mechanisms") or ():
        if isinstance(item, Mapping):
            ids.extend(_clean_strings((item.get("mechanism"),)))
    for item in diagnostics:
        ids.extend(_clean_strings((item.get("mechanism"),)))
    return tuple(dict.fromkeys(ids))


def _primary_mechanism_id(
    evidence: Mapping[str, Any],
    declared_ids: tuple[str, ...],
    diagnostics: tuple[Mapping[str, Any], ...],
) -> str:
    for key in ("primary_mechanism_id", "primary_mechanism"):
        value = _clean_string(evidence.get(key))
        if value:
            return value
    for item in diagnostics:
        value = _clean_string(item.get("mechanism"))
        if value:
            return value
    return declared_ids[0] if declared_ids else ""


def _primary_diagnostic(
    diagnostics: tuple[Mapping[str, Any], ...],
    *,
    primary_mechanism_id: str,
) -> Mapping[str, Any]:
    if primary_mechanism_id:
        for item in diagnostics:
            if _clean_string(item.get("mechanism")) == primary_mechanism_id:
                return item
    return diagnostics[0] if diagnostics else {}


def _repair_mechanism_ids(
    diagnostics: tuple[Mapping[str, Any], ...],
    *,
    primary_mechanism_id: str,
) -> tuple[str, ...]:
    repair_ids = [
        _clean_string(item.get("mechanism"))
        for item in diagnostics
        if _diagnostic_followup_required(item)
    ]
    repair_ids = [item for item in repair_ids if item]
    if repair_ids:
        return tuple(dict.fromkeys(repair_ids))
    if primary_mechanism_id and any(
        _diagnostic_followup_required(item) for item in diagnostics
    ):
        return (primary_mechanism_id,)
    return ()


def _diagnostic_followup_required(item: Mapping[str, Any]) -> bool:
    kind = _status(item.get("diagnostic_kind"))
    if kind in _FOLLOWUP_DIAGNOSTIC_KINDS:
        return True
    if kind in _NO_REPAIR_DIAGNOSTIC_KINDS:
        return False
    if item.get("repairable") is False:
        return False
    if item.get("repairable") is True:
        return True
    return False


def _primary_status(*, diagnostic_kind: str, effect_status: str) -> str:
    if diagnostic_kind == NOT_EVALUATED_OR_TRIGGERED:
        return DECLARED_NOT_TRIGGERED
    if diagnostic_kind in {WIRING_SUSPECT, RUNTIME_BUDGET_ZERO_OR_SUBMS}:
        return DECLARED_WIRING_SUSPECT
    if diagnostic_kind == ACTIVATED_NO_POSITIVE_EFFECT:
        return EFFECT_ATTRIBUTION_MISSING
    if diagnostic_kind == EVALUATED_NO_EFFECT:
        return OBSERVED_NO_EFFECT
    if effect_status in _POSITIVE_EFFECT_STATUSES:
        return OBSERVED_POSITIVE_EFFECT
    return UNKNOWN


def _repairable_for_kind(diagnostic_kind: str, followup_required: bool) -> bool:
    if diagnostic_kind in _NO_REPAIR_DIAGNOSTIC_KINDS:
        return False
    if diagnostic_kind in _FOLLOWUP_DIAGNOSTIC_KINDS:
        return True
    return bool(followup_required)


def _reason_codes(
    *,
    primary_status: str,
    diagnostic_kind: str,
    followup_required: bool,
) -> tuple[str, ...]:
    codes: list[str] = []
    if primary_status == DECLARED_NOT_TRIGGERED:
        codes.append("MECHANISM_CONTRACT_DECLARED_NOT_TRIGGERED")
    elif diagnostic_kind == RUNTIME_BUDGET_ZERO_OR_SUBMS:
        codes.append("MECHANISM_CONTRACT_RUNTIME_BUDGET_ZERO_OR_SUBMS")
    elif primary_status == DECLARED_WIRING_SUSPECT:
        codes.append("MECHANISM_CONTRACT_WIRING_SUSPECT")
    elif primary_status == EFFECT_ATTRIBUTION_MISSING:
        codes.append("MECHANISM_CONTRACT_EFFECT_ATTRIBUTION_MISSING")
    elif primary_status == OBSERVED_NO_EFFECT:
        codes.append("MECHANISM_CONTRACT_EVALUATED_NO_EFFECT")
    elif primary_status == OBSERVED_POSITIVE_EFFECT:
        codes.append("MECHANISM_CONTRACT_POSITIVE_EFFECT")
    else:
        codes.append("MECHANISM_CONTRACT_UNKNOWN")
    codes.append(
        "MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REQUIRED"
        if followup_required
        else "MECHANISM_CONTRACT_NO_REPAIR_FOLLOWUP"
    )
    return tuple(dict.fromkeys(codes))


def _clean_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_clean_string(value)] if _clean_string(value) else []
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return [
        text
        for text in (_clean_string(item) for item in value)
        if text
    ]


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _status(value: Any) -> str:
    return _clean_string(value).lower()


__all__ = [
    "DECLARED_NOT_TRIGGERED",
    "DECLARED_WIRING_SUSPECT",
    "EFFECT_ATTRIBUTION_MISSING",
    "MechanismEvidenceContract",
    "OBSERVED_NO_EFFECT",
    "OBSERVED_POSITIVE_EFFECT",
    "SCHEMA_VERSION",
    "UNKNOWN",
    "mechanism_contract_followup_required",
    "mechanism_evidence_contract_for_protocol",
    "mechanism_evidence_contract_from_sources",
]
