"""Protocol-independent typed outcomes for research execution attempts."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional


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


def execution_outcome_requires_hold(record: ExecutionOutcomeRecord) -> bool:
    """Return whether automatic scheduling must stop for this branch."""

    return record.outcome in _EXECUTION_HOLD_OUTCOMES


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
) -> Optional[str]:
    writer = getattr(registry, "record_execution_outcome", None)
    if not callable(writer):
        return None
    return writer(
        campaign_id=campaign_id,
        branch_id=branch_id,
        record=record,
        event_kind=event_kind,
        stage=str(record.provenance.get("stage") or ""),
    )
