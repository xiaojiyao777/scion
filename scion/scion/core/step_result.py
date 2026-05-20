"""Step result value object for campaign execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

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
        "proposal_retry",
        "telemetry_repairable",
        "same_family_retry",
        "other",
    ] = "screening"
