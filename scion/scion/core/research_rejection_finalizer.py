"""Problem-neutral cleanup for pre-Protocol research rejection."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from scion.core.execution_outcome import (
    AttemptDisposition,
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    ResearchRejectionDisposition,
    record_execution_outcome_event,
)
from scion.core.models import Branch, HypothesisRecord, PatchProposal


@dataclass(frozen=True)
class ResearchRejectionFinalization:
    marker: ResearchRejectionDisposition
    archive_ref: str | None = None


@dataclass
class ResearchRejectionFinalizer:
    """Restore the clean research base and append one rejection fact."""

    campaign_id: str
    registry: Any
    branch_store: Any
    hypothesis_store: Any
    workspace_lifecycle: Any
    branch_hypotheses: MutableMapping[str, Any]
    branch_patches: MutableMapping[str, Any]
    branch_current_hypothesis: MutableMapping[str, Any]
    discard_approved_hypothesis_binding: Any

    def finalize(
        self,
        *,
        branch: Branch,
        hypothesis_record: HypothesisRecord,
        proposal_attempt_ref: Mapping[str, Any],
        rejection_phase: str,
        outcome: ExecutionOutcomeRecord,
        checks: tuple[Mapping[str, Any], ...],
        rejected_candidate_workspace: str | None = None,
        patch: PatchProposal | None = None,
    ) -> ResearchRejectionFinalization:
        if rejection_phase not in {
            "hypothesis_contract",
            "proposal_code",
            "patch_contract",
            "verification",
        }:
            raise ValueError("unsupported research rejection phase")
        if outcome.outcome is not ExecutionOutcome.RESEARCH_REJECTED:
            raise ValueError("research rejection requires RESEARCH_REJECTED outcome")
        if hypothesis_record.branch_id != branch.branch_id:
            raise ValueError("rejected hypothesis belongs to another branch")

        cleanup_payload = None
        if rejection_phase == "verification":
            if rejected_candidate_workspace is None or patch is None:
                raise ValueError("verification rejection requires candidate and patch")
            cleanup = self.workspace_lifecycle.reject_candidate(
                branch,
                rejected_candidate_workspace,
            )
            cleanup_payload = {
                "workspace": cleanup.workspace,
                "cleaned": cleanup.cleaned,
                "cleanup_error": cleanup.cleanup_error,
            }
        elif rejected_candidate_workspace is not None:
            raise ValueError("only verification rejection owns candidate cleanup")
        elif rejection_phase in {"hypothesis_contract", "proposal_code"} and (
            patch is not None
        ):
            raise ValueError(f"{rejection_phase} rejection cannot own a patch")
        elif rejection_phase == "patch_contract" and patch is None:
            raise ValueError("patch Contract rejection requires a patch")

        self.hypothesis_store.mark_status(
            hypothesis_record.hypothesis_id,
            "research_rejected",
        )
        branch.screening_expand_count = 0
        branch.validation_expand_count = 0
        self.branch_store.save(branch)
        self.branch_hypotheses.pop(branch.branch_id, None)
        self.branch_patches.pop(branch.branch_id, None)
        self.branch_current_hypothesis.pop(branch.branch_id, None)
        self.discard_approved_hypothesis_binding(branch.branch_id)

        failed = next(
            (dict(item) for item in checks if item.get("passed") is False),
            None,
        )
        audit = {
            "schema_version": "research-rejection.v1",
            "rejection_phase": rejection_phase,
            "reason_code": outcome.reason_code,
            "detail": outcome.detail,
            "failed_check": failed,
            "checks": [dict(item) for item in checks],
            "hypothesis": {
                "hypothesis_id": hypothesis_record.hypothesis_id,
                "text": hypothesis_record.hypothesis_text or "",
                "action": hypothesis_record.action,
                "target_file": hypothesis_record.target_file,
            },
            "patch": (
                {
                    "action": patch.action,
                    "files": [
                        change.file_path for change in patch.iter_file_changes()
                    ],
                }
                if patch is not None
                else None
            ),
            "proposal_call_ref": dict(proposal_attempt_ref or {}),
            "candidate_cleanup": cleanup_payload,
        }
        event_id = self.registry.record_event(
            {
                "campaign_id": self.campaign_id,
                "branch_id": branch.branch_id,
                "hypothesis_id": hypothesis_record.hypothesis_id,
                "event_kind": "research_rejection",
                "stage": rejection_phase,
                "audit_payload_json": json.dumps(
                    audit,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            }
        )
        record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=outcome,
            hypothesis_id=hypothesis_record.hypothesis_id,
            event_kind="research_rejection_execution_outcome",
        )
        marker = ResearchRejectionDisposition(
            disposition=AttemptDisposition.ATTEMPT_REJECT_TO_BASE,
            rejection_phase=rejection_phase,
            lineage_event_id=str(event_id),
        )
        return ResearchRejectionFinalization(marker=marker)


__all__ = ["ResearchRejectionFinalization", "ResearchRejectionFinalizer"]
