"""Verification rejection handling for explore-step execution."""

from __future__ import annotations

import logging
from typing import Any

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.models import (
    Branch,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.step_result import StepResult
from scion.core.workspace_service import CandidateWorkspace

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
        )

    def _handle_verification_failure(
        self,
        *,
        branch: Branch,
        rnum: int,
        patch: PatchProposal,
        hypothesis: HypothesisProposal,
        vresult: VerificationResult,
        candidate: CandidateWorkspace,
    ) -> StepResult:
        bid = branch.branch_id
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
                "stage": "verification",
                "severity": severity,
                "verification_checks": checks,
                "patch": {
                    "action": patch.action,
                    "files": [change.file_path for change in patch.iter_file_changes()],
                },
            },
        )
        self.finalize_research_rejection(
            branch=branch,
            rejection_phase="verification",
            outcome=outcome,
            patch=patch,
            candidate=candidate,
        )
        self.record_step(
            self._verification_failure_step(
                rnum=rnum,
                bid=bid,
                hypothesis=hypothesis,
                patch=patch,
                vresult=vresult,
                outcome=outcome,
            )
        )
        return StepResult(
            action="explore",
            branch_id=bid,
            reason=f"verification rejected ({severity})",
            failure_stage="verification",
            failure_detail=vresult.first_failure,
            failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
            execution_outcome=outcome,
        )

    def _verification_failure_step(
        self,
        *,
        rnum: int,
        bid: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        vresult: VerificationResult,
        outcome: ExecutionOutcomeRecord,
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
            execution_outcome=outcome,
        )
