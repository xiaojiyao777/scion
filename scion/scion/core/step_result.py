"""Step result value object for campaign execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

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
        "soft_abandon",
        "stopped",
    ]
    branch_id: Optional[str] = None
    decision: Optional[Decision] = None
    stopped: bool = False
    reason: str = ""
    counts_toward_max_rounds: bool = True
    attempt_kind: Literal[
        "screening",
        "proposal_block",
        "proposal_diagnostic",
        "proposal_retry",
        "schema_quality_block",
        "branch_lifecycle_policy",
        "telemetry_repair",
        "telemetry_repairable",
        "validation_repair_required",
        "same_family_retry",
        "reconcile_lifecycle",
        "scheduler_active_slot_blocked",
        "other",
    ] = "screening"
    repair_mechanism_ids: Tuple[str, ...] = ()
    repair_policy_reason: str = ""
    failure_stage: Optional[str] = None
    failure_detail: Optional[str] = None
    failure_category: Optional[str] = None
    scheduler_slot: str = ""
    scheduler_reason: str = ""
    scheduler_audit_metadata: Dict[str, Any] | None = None
