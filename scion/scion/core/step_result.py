"""Step result value object for campaign execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import Decision, ProtocolResult


@dataclass
class StepResult:
    action: Literal[
        "explore",
        "validate",
        "frozen",
        "create_branch",
        "reconcile",
        "skip",
        "stopped",
    ]
    branch_id: Optional[str] = None
    decision: Optional[Decision] = None
    stopped: bool = False
    reason: str = ""
    failure_stage: Optional[str] = None
    failure_detail: Optional[str] = None
    failure_category: Optional[str] = None
    verification_passed: Optional[bool] = None
    protocol_result: ProtocolResult | None = None
    decision_engine_reason_codes: Tuple[str, ...] = ()
    diagnostic_reason_codes: Tuple[str, ...] = ()
    bypass_reason_codes: Tuple[str, ...] = ()
    canary_result: Any | None = None
    execution_outcome: ExecutionOutcomeRecord | None = None

    def __post_init__(self) -> None:
        record = self.execution_outcome
        if record is not None and not isinstance(record, ExecutionOutcomeRecord):
            raise TypeError("execution_outcome must be an ExecutionOutcomeRecord")
        if record is not None and record.outcome is not ExecutionOutcome.EVALUATED:
            if self.decision is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a Decision"
                )
            if self.protocol_result is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a ProtocolResult"
                )
