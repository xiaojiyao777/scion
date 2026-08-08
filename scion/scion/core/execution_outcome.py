"""Protocol-independent typed outcomes for research execution attempts."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional


class ExecutionOutcome(Enum):
    EVALUATED = "evaluated"
    RESEARCH_REJECTED = "research_rejected"
    NOT_EVALUATED = "not_evaluated"
    BLOCKED_INFRA = "blocked_infra"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERRUPTED = "interrupted"


class AttemptDisposition(Enum):
    """Typed post-attempt state change independent of Protocol/Decision."""

    ATTEMPT_REJECT_TO_BASE = "attempt_reject_to_base"


@dataclass(frozen=True)
class ResearchRejectionDisposition:
    """Plain branch disposition after a rejected pre-Protocol candidate."""

    disposition: AttemptDisposition
    rejection_phase: str
    lineage_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.disposition is not AttemptDisposition.ATTEMPT_REJECT_TO_BASE:
            raise ValueError("unsupported research rejection disposition")
        if self.rejection_phase not in {
            "hypothesis_contract",
            "patch_contract",
            "verification",
        }:
            raise ValueError("research rejection phase is invalid")

    def to_primitive(self) -> Dict[str, str | None]:
        return {
            "disposition": self.disposition.value,
            "rejection_phase": self.rejection_phase,
            "lineage_event_id": self.lineage_event_id,
        }


def validate_research_rejection_disposition(
    marker: ResearchRejectionDisposition | None,
    *,
    execution_outcome: ExecutionOutcome | None,
) -> None:
    if marker is None:
        return
    if not isinstance(marker, ResearchRejectionDisposition):
        raise TypeError("attempt disposition must be a typed immutable marker")
    if execution_outcome is not ExecutionOutcome.RESEARCH_REJECTED:
        raise ValueError(
            "research rejection disposition requires RESEARCH_REJECTED outcome"
        )


_EXECUTION_HOLD_OUTCOMES = frozenset(
    {
        ExecutionOutcome.NOT_EVALUATED,
        ExecutionOutcome.RESOURCE_EXHAUSTED,
        ExecutionOutcome.INTERRUPTED,
    }
)
_EXECUTION_HOLD_KEY = "execution_hold"


@dataclass(frozen=True)
class ExecutionOutcomeRecord:
    """Typed, JSON-primitive projection of an execution outcome."""

    outcome: ExecutionOutcome
    reason_code: str
    detail: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ExecutionOutcome):
            raise TypeError("execution outcome must be an ExecutionOutcome")
        if not isinstance(self.reason_code, str):
            raise TypeError("execution outcome reason_code must be a string")
        reason_code = self.reason_code.strip()
        if not reason_code:
            raise ValueError("execution outcome reason_code is required")
        if not isinstance(self.detail, str):
            raise TypeError("execution outcome detail must be a string")
        provenance = _execution_outcome_primitive(
            self.provenance,
            path="$.provenance",
        )
        if not isinstance(provenance, dict):
            raise TypeError("execution outcome provenance must be a mapping")
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "provenance", provenance)

    def to_primitive(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "provenance": _execution_outcome_primitive(
                self.provenance,
                path="$.provenance",
            ),
        }

    @classmethod
    def from_primitive(cls, payload: Mapping[str, Any]) -> "ExecutionOutcomeRecord":
        if not isinstance(payload, Mapping):
            raise TypeError("execution outcome payload must be a mapping")
        provenance = payload.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise TypeError("execution outcome provenance must be a mapping")
        return cls(
            outcome=ExecutionOutcome(str(payload.get("outcome") or "")),
            reason_code=payload.get("reason_code", ""),
            detail=payload.get("detail", ""),
            provenance=dict(provenance),
        )


def _execution_outcome_primitive(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite execution outcome value at {path}")
        return value
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"non-string execution outcome key at {path}: {key!r}"
                )
            result[key] = _execution_outcome_primitive(
                child,
                path=f"{path}.{key}",
            )
        return result
    if isinstance(value, (list, tuple)):
        return [
            _execution_outcome_primitive(child, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    raise TypeError(
        f"non-primitive execution outcome value at {path}: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def validate_execution_outcome_projection(
    *,
    execution_outcome: ExecutionOutcome | None,
    reason_code: str = "",
    detail: str = "",
    provenance: Mapping[str, Any] | None = None,
    decision: Any | None = None,
    protocol_result: Any | None = None,
) -> ExecutionOutcomeRecord | None:
    """Validate an explicit projection without guessing historical outcomes."""

    if execution_outcome is None:
        if reason_code or detail or provenance:
            raise ValueError(
                "execution outcome metadata requires an explicit outcome"
            )
        return None
    record = ExecutionOutcomeRecord(
        outcome=execution_outcome,
        reason_code=reason_code,
        detail=detail,
        provenance=dict(provenance or {}),
    )
    if execution_outcome is not ExecutionOutcome.EVALUATED:
        if decision is not None:
            raise ValueError(
                "non-evaluated execution outcome cannot carry a Decision"
            )
        if protocol_result is not None:
            raise ValueError(
                "non-evaluated execution outcome cannot carry a ProtocolResult"
            )
    return record


def execution_outcome_projection_kwargs(
    record: ExecutionOutcomeRecord,
) -> dict[str, Any]:
    return {
        "execution_outcome": record.outcome,
        "execution_outcome_reason_code": record.reason_code,
        "execution_outcome_detail": record.detail,
        "execution_outcome_provenance": dict(record.provenance),
    }


def execution_outcome_requires_hold(record: ExecutionOutcomeRecord) -> bool:
    """Return whether automatic scheduling must stop for this branch."""

    return record.outcome in _EXECUTION_HOLD_OUTCOMES


def install_branch_execution_hold(
    branch: Any,
    record: ExecutionOutcomeRecord,
) -> bool:
    """Persistable branch marker preventing implicit re-execution.

    BLOCKED_INFRA is represented by BranchState and therefore is not duplicated
    here. Research rejection and evaluated results remain scheduler-owned.
    """

    if not execution_outcome_requires_hold(record):
        return False
    summary = getattr(branch, "branch_evidence_summary", None)
    if not isinstance(summary, dict):
        summary = {}
        setattr(branch, "branch_evidence_summary", summary)
    summary[_EXECUTION_HOLD_KEY] = {
        "schema_version": "execution-hold.v1",
        "active": True,
        **record.to_primitive(),
    }
    return True


def branch_execution_hold(branch: Any) -> Optional[Dict[str, Any]]:
    summary = getattr(branch, "branch_evidence_summary", None)
    if not isinstance(summary, Mapping):
        return None
    marker = summary.get(_EXECUTION_HOLD_KEY)
    if not isinstance(marker, Mapping) or marker.get("active") is not True:
        return None
    outcome = str(marker.get("outcome") or "")
    if outcome not in {item.value for item in _EXECUTION_HOLD_OUTCOMES}:
        return None
    return dict(marker)


def branch_has_execution_hold(branch: Any) -> bool:
    return branch_execution_hold(branch) is not None


def clear_branch_execution_hold(branch: Any) -> Optional[Dict[str, Any]]:
    summary = getattr(branch, "branch_evidence_summary", None)
    if not isinstance(summary, dict):
        return None
    marker = summary.pop(_EXECUTION_HOLD_KEY, None)
    return dict(marker) if isinstance(marker, Mapping) else None


def record_execution_outcome_event(
    *,
    registry: Any,
    campaign_id: str,
    branch_id: str,
    record: ExecutionOutcomeRecord,
    hypothesis_id: Optional[str],
    event_kind: str,
) -> Optional[str]:
    writer = getattr(registry, "record_execution_outcome", None)
    if not callable(writer):
        return None
    return writer(
        campaign_id=campaign_id,
        branch_id=branch_id,
        hypothesis_id=hypothesis_id,
        record=record,
        event_kind=event_kind,
        stage=str(record.provenance.get("stage") or ""),
    )


def execution_outcome_evidence(items: Iterable[Any]) -> dict[str, Any]:
    """Summarize explicit outcomes while preserving missing historical values."""
    counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    unknown_count = 0
    last: dict[str, Any] | None = None
    total = 0
    for item in items:
        total += 1
        projection = _execution_outcome_projection(item)
        if projection is None:
            unknown_count += 1
            continue
        counts[projection["outcome"]] += 1
        last = projection
    return execution_outcome_evidence_from_counts(
        counts,
        last_execution_outcome=last,
        unknown_count=unknown_count,
        total_count=total,
    )


def execution_outcome_evidence_from_counts(
    counts: Mapping[str, Any] | None,
    *,
    last_execution_outcome: Mapping[str, Any] | None = None,
    unknown_count: int = 0,
    total_count: int | None = None,
) -> dict[str, Any]:
    normalized = {outcome.value: 0 for outcome in ExecutionOutcome}
    for key, value in (counts or {}).items():
        outcome = str(key or "")
        if outcome not in normalized:
            continue
        try:
            normalized[outcome] = max(0, int(value or 0))
        except (TypeError, ValueError):
            continue
    evaluated_count = normalized[ExecutionOutcome.EVALUATED.value]
    non_evaluated_count = sum(normalized.values()) - evaluated_count
    unknown = max(0, int(unknown_count or 0))
    total = (
        max(0, int(total_count))
        if total_count is not None
        else evaluated_count + non_evaluated_count + unknown
    )
    if evaluated_count > 0:
        eligibility_status = (
            "partial_evaluated"
            if non_evaluated_count > 0 or unknown > 0
            else "eligible"
        )
        eligible = True
    elif non_evaluated_count > 0:
        eligibility_status = "ineligible_zero_evaluated"
        eligible = False
    else:
        eligibility_status = "unknown_historical"
        eligible = None
    last = (
        _safe_last_execution_outcome(last_execution_outcome)
        if isinstance(last_execution_outcome, Mapping)
        else None
    )
    return {
        "schema_version": "execution-outcome-evidence.v1",
        "execution_outcome_counts": normalized,
        "evaluated_count": evaluated_count,
        "non_evaluated_count": non_evaluated_count,
        "unknown_outcome_count": unknown,
        "total_outcome_subject_count": total,
        "last_execution_outcome": last,
        "research_conclusion_eligibility": {
            "status": eligibility_status,
            "eligible": eligible,
            "algorithm_conclusions_allowed": eligible is True,
            "partial": eligibility_status == "partial_evaluated",
            "excluded_outcome_counts": {
                key: value
                for key, value in normalized.items()
                if key != ExecutionOutcome.EVALUATED.value and value > 0
            },
            "unknown_excluded_count": unknown,
        },
    }


def _execution_outcome_projection(item: Any) -> dict[str, Any] | None:
    if isinstance(item, Mapping):
        raw_outcome = item.get("execution_outcome", item.get("outcome"))
        nested = raw_outcome if isinstance(raw_outcome, Mapping) else {}
        raw_value = nested.get("outcome") if nested else raw_outcome
        reason_code = (
            nested.get("reason_code")
            or item.get("execution_outcome_reason_code")
            or item.get("reason_code")
        )
        provenance = nested.get("provenance") or item.get(
            "execution_outcome_provenance"
        ) or item.get("provenance_refs") or item.get("provenance")
    else:
        raw_value = getattr(item, "execution_outcome", None)
        reason_code = getattr(item, "execution_outcome_reason_code", "")
        provenance = getattr(item, "execution_outcome_provenance", {})
    value = str(getattr(raw_value, "value", raw_value) or "")
    if value not in {outcome.value for outcome in ExecutionOutcome}:
        return None
    return {
        "outcome": value,
        "reason_code": str(reason_code or ""),
        "provenance_refs": _safe_provenance_refs(provenance),
    }


def _safe_last_execution_outcome(
    value: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw_outcome = value.get("outcome") or value.get("execution_outcome")
    outcome = str(getattr(raw_outcome, "value", raw_outcome) or "")
    if outcome not in {member.value for member in ExecutionOutcome}:
        return None
    return {
        "outcome": outcome,
        "reason_code": str(
            value.get("reason_code")
            or value.get("execution_outcome_reason_code")
            or ""
        ),
        "provenance_refs": _safe_provenance_refs(
            value.get("provenance_refs")
            or value.get("provenance")
            or value.get("execution_outcome_provenance")
        ),
    }


def _safe_provenance_refs(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key or "")
        if not (
            normalized_key in {"owner", "source", "stage", "exception_type"}
            or normalized_key.endswith(("_ref", "_id", "_hash"))
        ):
            continue
        if item is None or isinstance(item, (str, int, float, bool)):
            safe[normalized_key] = item
    return safe
