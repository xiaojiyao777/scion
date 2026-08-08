"""Verification rejection handling for explore-step execution."""

from __future__ import annotations

import logging
from typing import Any, Optional

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    execution_outcome_projection_kwargs,
)
from scion.core.models import (
    Branch,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.step_result import StepResult
from scion.proposal.context_manager.code_context import branch_current_file_sources

from .common import (
    _VerificationOutcome,
)

logger = logging.getLogger(__name__)


class VerificationMixin:
    def _validate_hypothesis(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> Any:
        return self.contract_gate.validate_hypothesis(
            hypothesis,
            base_snapshot_path=self.branch_workspaces.get(branch.branch_id),
            base_file_overrides=branch_current_file_sources(
                branch,
                self.step_history,
            ),
        )

    def _handle_verification_failure(
        self,
        *,
        branch: Branch,
        rnum: int,
        workspace: str,
        patch: PatchProposal,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        vresult: VerificationResult,
        code_hash: str,
        champion_workspace: str,
    ) -> "_VerificationOutcome":
        bid = branch.branch_id
        del champion_workspace
        severity = vresult.failure_severity or "light"
        logger.info(
            "Branch %s: verification failed (%s): %s",
            bid,
            severity,
            vresult.first_failure,
        )
        reason_code = (
            "VERIFICATION_LIGHT_REJECTED"
            if severity == "light"
            else "VERIFICATION_HEAVY_REJECTED"
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
            for check in vresult.checks
        ]
        outcome = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=reason_code,
            detail=vresult.first_failure or "",
            provenance={
                "owner": "verification_gate",
                "stage": "verification",
                "severity": severity,
                "verification_checks": checks,
            },
        )
        finalization = self.finalize_research_rejection(
            branch=branch,
            hypothesis_record=h_record,
            proposal_attempt_ref=self._proposal_session_ref(bid),
            rejection_phase="verification",
            outcome=outcome,
            checks=tuple(checks),
            rejected_candidate_workspace=workspace,
            patch=patch,
        )
        self.record_step(
            self._verification_failure_step(
                rnum=rnum,
                bid=bid,
                hypothesis=hypothesis,
                patch=patch,
                h_record=h_record,
                vresult=vresult,
                archive_ref=finalization.archive_ref,
                outcome=outcome,
                attempt_disposition=finalization.marker,
            )
        )
        return _VerificationOutcome(
            step_result=StepResult(
                action="explore",
                branch_id=bid,
                reason=f"verification rejected ({severity})",
                failure_stage="verification",
                failure_detail=vresult.first_failure,
                failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                proposal_session_ref=self._proposal_session_ref(bid),
                attempt_disposition=finalization.marker,
                **execution_outcome_projection_kwargs(outcome),
            ),
            code_hash=code_hash,
            verification_result=vresult,
        )

    def _verification_failure_step(
        self,
        *,
        rnum: int,
        bid: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        h_record: HypothesisRecord,
        vresult: VerificationResult,
        archive_ref: Optional[str],
        outcome: ExecutionOutcomeRecord,
        attempt_disposition: Any,
    ) -> StepRecord:
        return StepRecord(
            round_num=rnum,
            branch_id=bid,
            hypothesis=hypothesis,
            patch=patch,
            contract_passed=True,
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage="verification",
            failure_detail=vresult.first_failure,
            verification_detail=build_verification_detail(vresult),
            code_archive_ref=archive_ref,
            hypothesis_id=h_record.hypothesis_id,
            proposal_session_ref=self._proposal_session_ref(bid),
            attempt_disposition=attempt_disposition,
            **execution_outcome_projection_kwargs(outcome),
        )

    def _proposal_session_ref(
        self,
        branch_id: str,
    ) -> Optional[dict[str, Any]]:
        return self.proposal_session_ref_for(branch_id)


def build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    """Build the complete verification failure evidence projection."""
    if not vresult or vresult.passed:
        return None
    failed = [c for c in vresult.checks if not c.passed]
    if not failed:
        return vresult.first_failure
    lines = [
        f"severity={vresult.failure_severity or 'unknown'}  "
        f"first_failure={vresult.first_failure or 'N/A'}"
    ]
    for check in failed:
        lines.append(f"  [{check.name}] ({check.severity}) {check.detail}")
    return "\n".join(lines)
