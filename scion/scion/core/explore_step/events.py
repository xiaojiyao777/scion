"""Lineage/event helpers for explore-step execution."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from scion.core.models import Branch, HypothesisProposal, HypothesisRecord, PatchProposal, VerificationResult

from .common import (
    _AGENT_QUALITY_BLOCKED,
    _PROPOSAL_ACTIVATION_DIAGNOSTIC,
    _PROPOSAL_PREMISE_CONTRADICTED,
    _proposal_session_ref_failure_code,
)


class ExploreStepEventMixin:
    def _record_contract_failure(
        self,
        branch_id: str,
        hypothesis: HypothesisProposal,
        failure_reason: str,
    ) -> None:
        try:
            self.registry.record_contract_failure(
                campaign_id=self.campaign_id,
                branch_id=branch_id,
                hypothesis_text=hypothesis.hypothesis_text or "",
                change_locus=hypothesis.change_locus,
                action=hypothesis.action,
                target_file=hypothesis.target_file,
                failure_reason=failure_reason,
            )
        except Exception:
            pass

    def _record_agent_quality_branch_signal(
        self,
        branch: Branch,
        failure_detail: str | None,
        session_ref: Mapping[str, Any] | None,
    ) -> None:
        code = _proposal_session_ref_failure_code(session_ref)
        if not code:
            if _PROPOSAL_ACTIVATION_DIAGNOSTIC in str(failure_detail or ""):
                code = _PROPOSAL_ACTIVATION_DIAGNOSTIC
            elif _PROPOSAL_PREMISE_CONTRADICTED in str(failure_detail or ""):
                code = _PROPOSAL_PREMISE_CONTRADICTED
            else:
                code = _AGENT_QUALITY_BLOCKED
        normalized = code.upper()
        branch.failure_codes.append(normalized)
        branch.updated_at = datetime.now()
        try:
            self.persist_branch_state(branch.branch_id)
        except Exception:
            logger.debug(
                "BranchStore.save(%s) failed after agent-quality block",
                branch.branch_id,
                exc_info=True,
            )

    def _record_proposal_fail_event(self, branch_id: str, failure_detail: str) -> None:
        try:
            self.registry.record_event(
                {
                    "campaign_id": self.campaign_id,
                    "branch_id": branch_id,
                    "timestamp": datetime.now().isoformat(),
                    "event_kind": "proposal_fail",
                    "hypothesis_text": f"Proposal generation failed: {failure_detail}"[:500],
                    "contract_result": "skipped",
                    "verification_result": "skipped",
                    "canary_result": "skipped",
                    "stage": "proposal",
                    "decision_reason": failure_detail[:500],
                }
            )
        except Exception:
            pass

    def _record_verification_fail_event(
        self,
        *,
        bid: str,
        h_record: HypothesisRecord,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        vresult: VerificationResult,
        decision_reason: str,
    ) -> None:
        try:
            self.registry.record_event(
                {
                    "campaign_id": self.campaign_id,
                    "branch_id": bid,
                    "hypothesis_id": h_record.hypothesis_id,
                    "timestamp": datetime.now().isoformat(),
                    "event_kind": "verification_fail",
                    "contract_passed": True,
                    "verification_passed": False,
                    "verification_result": vresult.first_failure,
                    "patch_file": patch.file_path if patch else None,
                    "hypothesis_text": (hypothesis.hypothesis_text or "")[:200],
                    "stage": "verification",
                    "decision_reason": decision_reason,
                }
            )
        except Exception:
            pass

