"""Problem-neutral cleanup for pre-Protocol research rejection."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    block_branch_after_execution,
    disposition_failure_record,
    record_execution_outcome_event,
)
from scion.core.models import Branch, PatchProposal
from scion.core.workspace_service import CandidateWorkspace

logger = logging.getLogger(__name__)


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
        selected_hypothesis_research_basis: dict[str, Any] | None = None,
    ) -> ExecutionOutcomeRecord:
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
            try:
                self.workspace_service.reject_candidate(candidate)
            except Exception as exc:
                failed = disposition_failure_record(
                    reason_code="CANDIDATE_REJECT_FAILED",
                    error=exc,
                    operation="reject_candidate_after_research_rejection",
                    interrupted_outcome=outcome,
                )
                try:
                    record_execution_outcome_event(
                        registry=self.registry,
                        campaign_id=self.campaign_id,
                        branch_id=branch.branch_id,
                        record=failed,
                        event_kind="candidate_disposition_execution_outcome",
                        selected_hypothesis_research_basis=(
                            selected_hypothesis_research_basis
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Branch %s: research rejection cleanup outcome could not "
                        "persist",
                        branch.branch_id,
                    )
                block_branch_after_execution(branch, failed)
                return failed
        elif rejection_phase in {"hypothesis_contract", "proposal_code"} and (
            patch is not None
        ):
            raise ValueError(f"{rejection_phase} rejection cannot own a patch")
        elif rejection_phase == "patch_contract" and patch is None:
            raise ValueError("patch Contract rejection requires a patch")

        branch.screening_expand_count = 0
        branch.validation_expand_count = 0
        if branch.accepted_changes:
            accepted_head = branch.accepted_changes[-1]
            branch.hypothesis = accepted_head.hypothesis
            branch.selected_hypothesis_research_basis = deepcopy(
                accepted_head.selected_hypothesis_research_basis
            )
            self.branch_patches[branch.branch_id] = accepted_head.patch
        else:
            branch.hypothesis = None
            branch.selected_hypothesis_research_basis = None
            self.branch_patches.pop(branch.branch_id, None)

        record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=outcome,
            event_kind="research_rejection",
            selected_hypothesis_research_basis=selected_hypothesis_research_basis,
        )
        return outcome


__all__ = ["ResearchRejectionFinalizer"]
