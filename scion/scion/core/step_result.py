"""Step result value object for campaign execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Tuple

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ResearchRejectionDisposition,
    validate_research_rejection_disposition,
    validate_execution_outcome_projection,
)
from scion.core.models import Decision


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
    attempt_kind: Literal[
        "screening",
        "reconcile_lifecycle",
        "other",
    ] = "screening"
    repair_mechanism_ids: Tuple[str, ...] = ()
    repair_policy_reason: str = ""
    failure_stage: Optional[str] = None
    failure_detail: Optional[str] = None
    failure_category: Optional[str] = None
    protocol_stage: Optional[Literal["screening", "validation", "frozen"]] = None
    formal_protocol_evaluated: bool = False
    screened_experiment_effective: bool = False
    decision_engine_reason_codes: Tuple[str, ...] = ()
    diagnostic_reason_codes: Tuple[str, ...] = ()
    bypass_reason_codes: Tuple[str, ...] = ()
    scheduler_slot: str = ""
    scheduler_reason: str = ""
    scheduler_audit_metadata: Dict[str, Any] | None = None
    proposal_session_ref: Dict[str, Any] | None = None
    canary_result: Any | None = None
    execution_outcome: ExecutionOutcome | None = None
    execution_outcome_reason_code: str = ""
    execution_outcome_detail: str = ""
    execution_outcome_provenance: Dict[str, Any] = field(default_factory=dict)
    attempt_disposition: ResearchRejectionDisposition | None = None

    def __post_init__(self) -> None:
        validate_execution_outcome_projection(
            execution_outcome=self.execution_outcome,
            reason_code=self.execution_outcome_reason_code,
            detail=self.execution_outcome_detail,
            provenance=self.execution_outcome_provenance,
            decision=self.decision,
        )
        validate_research_rejection_disposition(
            self.attempt_disposition,
            execution_outcome=self.execution_outcome,
        )
