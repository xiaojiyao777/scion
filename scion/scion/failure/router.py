"""Typed failure classification without proposal retry policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Branch, FailureEvent


@dataclass(frozen=True)
class FailureAction:
    """One terminal classification for the current scheduled call."""

    action: Literal["block_infra", "reject_response"]
    execution_outcome: ExecutionOutcome
    reason_code: str


class FailureRouter:
    """Separate environment blocks from rejected non-evaluated responses."""

    def route(
        self,
        failure: FailureEvent,
        branch: Branch,
    ) -> FailureAction:
        del branch
        category = str(failure.category or "").strip().lower()
        if category == "infra":
            return FailureAction(
                action="block_infra",
                execution_outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="INFRA_BLOCKED",
            )
        return FailureAction(
            action="reject_response",
            execution_outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="RESPONSE_REJECTED",
        )
