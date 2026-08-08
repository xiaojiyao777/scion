"""Lineage/event helpers for explore-step execution."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import Branch, ContractResult, HypothesisProposal, PatchProposal

from .common import (
    _AGENT_QUALITY_BLOCKED,
    _PROPOSAL_ACTIVATION_DIAGNOSTIC,
    _PROPOSAL_PREMISE_CONTRADICTED,
    _proposal_session_ref_failure_code,
)

logger = logging.getLogger(__name__)


class ExploreStepEventMixin:
    def _record_contract_failure(
        self,
        branch_id: str,
        hypothesis: HypothesisProposal,
        result: ContractResult,
        *,
        stage: str,
        hypothesis_id: str,
        patch: PatchProposal | None = None,
    ) -> ExecutionOutcomeRecord:
        reason_code = (
            "HYPOTHESIS_CONTRACT_REJECTED"
            if stage == "hypothesis_contract"
            else "PATCH_CONTRACT_REJECTED"
        )
        checks = [
            {
                "name": check.name,
                "passed": check.passed,
                "severity": check.severity,
                "detail": check.detail,
                "elapsed_ms": check.elapsed_ms,
                "metadata": dict(check.metadata or {}),
            }
            for check in result.checks
        ]
        detail = result.failure_reason or ""
        provenance = {
            "owner": "outer_contract",
            "stage": stage,
            "contract_checks": checks,
        }
        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=reason_code,
            detail=detail,
            provenance=provenance,
        )
        return record

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
                    "hypothesis_text": f"Proposal generation failed: {failure_detail}",
                    "contract_result": "skipped",
                    "verification_result": "skipped",
                    "canary_result": "skipped",
                    "stage": "proposal",
                    "decision_reason": failure_detail,
                }
            )
        except Exception:
            pass
