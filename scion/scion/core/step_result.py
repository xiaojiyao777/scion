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
        "replay",
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
        "fresh_runtime_replay",
        "reconcile_lifecycle",
        "scheduler_active_slot_blocked",
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
    decision_layer_source: Optional[str] = None
    decision_engine_reason_codes: Tuple[str, ...] = ()
    diagnostic_reason_codes: Tuple[str, ...] = ()
    bypass_reason_codes: Tuple[str, ...] = ()
    lifecycle_reason_codes: Tuple[str, ...] = ()
    lifecycle_bookkeeping: Dict[str, Any] | None = None
    scheduler_slot: str = ""
    scheduler_reason: str = ""
    scheduler_audit_metadata: Dict[str, Any] | None = None
    proposal_session_ref: Dict[str, Any] | None = None
    canary_result: Any | None = None
