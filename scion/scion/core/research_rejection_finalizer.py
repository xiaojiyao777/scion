"""Problem-neutral cleanup for pre-Protocol research rejection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    record_execution_outcome_event,
)
from scion.core.models import Branch, PatchProposal
from scion.core.workspace_service import CandidateWorkspace


@dataclass
class ResearchRejectionFinalizer:
    """Restore the clean research base and append one rejection fact."""

    campaign_id: str
    registry: Any
    workspace_service: Any
    branch_patches: MutableMapping[str, Any]

    def finalize(
        self,
        *,
        branch: Branch,
        rejection_phase: str,
        outcome: ExecutionOutcomeRecord,
        patch: PatchProposal | None = None,
        candidate: CandidateWorkspace | None = None,
    ) -> None:
        if rejection_phase not in {
            "hypothesis_contract",
            "proposal_code",
            "patch_contract",
            "verification",
        }:
            raise ValueError("unsupported research rejection phase")
        if outcome.outcome is not ExecutionOutcome.RESEARCH_REJECTED:
            raise ValueError("research rejection requires RESEARCH_REJECTED outcome")
        if rejection_phase == "verification":
            if patch is None or candidate is None:
                raise ValueError("verification rejection requires patch and candidate")
            self.workspace_service.reject_candidate(candidate)
        elif rejection_phase in {"hypothesis_contract", "proposal_code"} and (
            patch is not None
        ):
            raise ValueError(f"{rejection_phase} rejection cannot own a patch")
        elif rejection_phase == "patch_contract" and patch is None:
            raise ValueError("patch Contract rejection requires a patch")

        branch.screening_expand_count = 0
        branch.validation_expand_count = 0
        branch.hypothesis = None
        self.branch_patches.pop(branch.branch_id, None)

        record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=outcome,
            event_kind="research_rejection",
        )


__all__ = ["ResearchRejectionFinalizer"]
