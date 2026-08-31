"""Protocol-independent typed outcomes for research execution attempts."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from scion.core.selected_hypothesis_basis import (
    canonical_selected_hypothesis_research_basis_json,
)


class ExecutionOutcome(Enum):
    EVALUATED = "evaluated"
    RESEARCH_REJECTED = "research_rejected"
    NOT_EVALUATED = "not_evaluated"
    BLOCKED_INFRA = "blocked_infra"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERRUPTED = "interrupted"


_EXECUTION_HOLD_OUTCOMES = frozenset(
    {
        ExecutionOutcome.BLOCKED_INFRA,
        ExecutionOutcome.NOT_EVALUATED,
        ExecutionOutcome.RESOURCE_EXHAUSTED,
        ExecutionOutcome.INTERRUPTED,
    }
)


@dataclass(frozen=True)
class ExecutionOutcomeRecord:
    """Typed, JSON-primitive projection of an execution outcome."""

    outcome: ExecutionOutcome
    reason_code: str
    detail: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

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

    def to_primitive(self) -> dict[str, Any]:
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
    def from_primitive(cls, payload: Mapping[str, Any]) -> ExecutionOutcomeRecord:
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
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"non-string execution outcome key at {path}: {key!r}")
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


def execution_outcome_requires_hold(record: ExecutionOutcomeRecord) -> bool:
    """Return whether automatic scheduling must stop for this branch."""

    return record.outcome in _EXECUTION_HOLD_OUTCOMES


def disposition_failure_record(
    *,
    reason_code: str,
    error: Exception,
    operation: str,
    interrupted_outcome: ExecutionOutcomeRecord | None = None,
    completed_protocol: Any | None = None,
    unapplied_decision: Any | None = None,
    decision_reason_codes: tuple[str, ...] | None = None,
) -> ExecutionOutcomeRecord:
    """Describe one failed cleanup/bind without erasing the preceding fact.

    Disposition happens after an earlier typed evaluation fact or after Protocol
    has completed, but before the host can safely close the attempt.  The
    terminal outcome is therefore infrastructure-blocked.  The preceding fact
    remains ordinary provenance; no Decision is claimed as applied.
    """

    if interrupted_outcome is not None and completed_protocol is not None:
        raise ValueError(
            "disposition failure accepts interrupted_outcome or "
            "completed_protocol, not both"
        )
    provenance: dict[str, Any] = {
        "stage": "candidate_disposition",
        "operation": operation,
        "exception_type": type(error).__name__,
    }
    if interrupted_outcome is not None:
        provenance["interrupted_outcome"] = interrupted_outcome.to_primitive()
    if completed_protocol is not None:
        protocol_stage = getattr(completed_protocol, "stage", "")
        protocol_stage_value = str(
            getattr(protocol_stage, "value", protocol_stage) or ""
        )
        stats = getattr(completed_protocol, "stats", None)
        provenance["protocol_stage"] = protocol_stage_value
        provenance["completed_protocol"] = {
            "stage": protocol_stage_value,
            "gate_outcome": str(
                getattr(completed_protocol, "gate_outcome", "") or ""
            ),
            "reason_codes": list(
                getattr(completed_protocol, "reason_codes", ()) or ()
            ),
            "raw_metrics_ref": str(
                getattr(completed_protocol, "raw_metrics_ref", "") or ""
            ),
            "stats": asdict(stats) if is_dataclass(stats) else None,
        }
    if unapplied_decision is not None:
        provenance["unapplied_decision"] = str(
            getattr(unapplied_decision, "value", unapplied_decision) or ""
        )
    if decision_reason_codes:
        provenance["decision_reason_codes"] = list(decision_reason_codes)
    return ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.BLOCKED_INFRA,
        reason_code=reason_code,
        detail=str(error),
        provenance=provenance,
    )


def block_branch_after_execution(
    branch: Any,
    record: ExecutionOutcomeRecord,
) -> bool:
    """Stop automatic scheduling with one ordinary branch state and reason."""

    if not execution_outcome_requires_hold(record):
        return False
    from scion.core.models import BranchState

    branch.state = BranchState.BLOCKED_INFRA
    failure_codes = getattr(branch, "failure_codes", None)
    if not isinstance(failure_codes, list):
        failure_codes = []
        branch.failure_codes = failure_codes
    if record.reason_code not in failure_codes:
        failure_codes.append(record.reason_code)
    return True


def record_execution_outcome_event(
    *,
    registry: Any,
    campaign_id: str,
    branch_id: str,
    record: ExecutionOutcomeRecord,
    event_kind: str,
    extra_fields: Mapping[str, Any] | None = None,
    selected_hypothesis_research_basis: Mapping[str, Any] | None = None,
) -> str | None:
    writer = getattr(registry, "record_execution_outcome", None)
    if not callable(writer):
        return None
    values = {
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "record": record,
        "event_kind": event_kind,
        "stage": str(record.provenance.get("stage") or ""),
    }
    extras = dict(extra_fields or {})
    basis_field = "selected_hypothesis_research_basis_json"
    if basis_field in extras:
        raise ValueError(
            f"{basis_field} must be supplied through the dedicated argument"
        )
    if selected_hypothesis_research_basis is not None:
        extras[basis_field] = canonical_selected_hypothesis_research_basis_json(
            selected_hypothesis_research_basis
        )
    if extras:
        values["extra_fields"] = extras
    return writer(
        **values,
    )
