"""Verification and retry helpers for explore-step execution."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from scion.core.models import Branch, FailureEvent, HypothesisProposal, HypothesisRecord, PatchProposal, StepRecord, VerificationResult
from scion.core.step_result import StepResult
from scion.core.verification_call import run_verification_gate

from .common import (
    _AGENT_QUALITY_BLOCKED,
    _PROPOSAL_ACTIVATION_DIAGNOSTIC,
    _PROPOSAL_PREMISE_CONTRADICTED,
    _VerificationOutcome,
    _is_candidate_scoped_heavy_failure,
    _proposal_session_ref_failure_code,
)

logger = logging.getLogger(__name__)


class VerificationMixin:
    def _mark_code_generation_recovered(
        self,
        branch: Branch,
        h_record: HypothesisRecord,
    ) -> None:
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        branch.updated_at = datetime.now()
        try:
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "active")
            h_record.status = "active"
        except Exception as exc:
            logger.debug(
                "HypothesisStore.mark_status(%s, active) failed after code retry: %s",
                h_record.hypothesis_id,
                exc,
            )
        try:
            self.persist_branch_state(branch.branch_id)
        except Exception as exc:
            logger.debug(
                "BranchStore.save(%s) failed after code retry recovery: %s",
                branch.branch_id,
                exc,
            )

    def _validate_hypothesis(self, hypothesis: HypothesisProposal) -> Any:
        champion = self.get_champion()
        return self.contract_gate.validate_hypothesis(
            hypothesis,
            self.hypothesis_store.get_by_status("active"),
            self.hypothesis_store.get_by_status("blacklisted"),
            rejected_hypotheses=self.hypothesis_store.get_by_status("rejected"),
            current_champion_version=champion.version if champion else 0,
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
        retry_attempt: bool = False,
        prior_failure: Optional[str] = None,
    ) -> "_VerificationOutcome":
        bid = branch.branch_id
        severity = vresult.failure_severity or "light"
        logger.info(
            "Branch %s: verification failed (%s): %s",
            bid,
            severity,
            vresult.first_failure,
        )
        category = "verification_light" if severity == "light" else "verification_heavy"
        failure = FailureEvent(category=category, detail=vresult.first_failure or "")

        if severity == "light":
            fixed = self.attempt_fix(branch, patch, vresult)
            if fixed is not None:
                fixed_contract = self.contract_gate.validate_patch(
                    fixed,
                    approved_hypothesis=hypothesis,
                    base_snapshot_path=workspace,
                )
                if not fixed_contract.passed:
                    logger.info(
                        "Branch %s: fix patch failed contract gate: %s",
                        bid,
                        fixed_contract.failure_reason,
                    )
                    fixed = None
                else:
                    try:
                        fixed_applied = self.apply_patch(
                            branch,
                            workspace,
                            fixed,
                            remember_patch=True,
                        )
                        code_hash = fixed_applied.code_hash
                        vresult = run_verification_gate(
                            self.verification_gate,
                            workspace,
                            champion_workspace,
                            fixed,
                            hypothesis=hypothesis,
                        )
                    except Exception:
                        pass
            if vresult.passed:
                return _VerificationOutcome(
                    step_result=None,
                    code_hash=code_hash,
                    verification_result=vresult,
                )
            self.handle_failure(branch, failure)
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            archive_ref = self.archive_failed_workspace(workspace, bid, rnum)
            self._record_verification_fail_event(
                bid=bid,
                h_record=h_record,
                hypothesis=hypothesis,
                patch=patch,
                vresult=vresult,
                decision_reason="light",
            )
            self.record_step(
                self._verification_failure_step(
                    rnum=rnum,
                    bid=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    h_record=h_record,
                    vresult=vresult,
                    archive_ref=archive_ref,
                    retry_attempt=retry_attempt,
                    prior_failure=prior_failure,
                )
            )
            return _VerificationOutcome(
                step_result=StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="verification failed (light)",
                    counts_toward_max_rounds=not retry_attempt,
                ),
                code_hash=code_hash,
                verification_result=vresult,
            )

        failed_status = (
            "rejected"
            if _is_candidate_scoped_heavy_failure(
                hypothesis,
                problem_spec=getattr(self.contract_gate, "_spec", None),
            )
            else "blacklisted"
        )
        self.hypothesis_store.mark_status(h_record.hypothesis_id, failed_status)
        self.handle_failure(branch, failure, hypothesis_already_recorded=True)
        archive_ref = self.archive_failed_workspace(workspace, bid, rnum)
        self._record_verification_fail_event(
            bid=bid,
            h_record=h_record,
            hypothesis=hypothesis,
            patch=patch,
            vresult=vresult,
            decision_reason="heavy",
        )
        self.record_step(
            self._verification_failure_step(
                rnum=rnum,
                bid=bid,
                hypothesis=hypothesis,
                patch=patch,
                h_record=h_record,
                vresult=vresult,
                archive_ref=archive_ref,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
        )
        return _VerificationOutcome(
            step_result=StepResult(
                action="explore",
                branch_id=bid,
                reason="verification failed (heavy)",
                counts_toward_max_rounds=not retry_attempt,
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
        retry_attempt: bool = False,
        prior_failure: Optional[str] = None,
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
            proposal_session_ref=self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            ),
        )

    def _proposal_session_ref(
        self,
        branch_id: str,
        *,
        retry_attempt: bool = False,
        prior_failure: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        ref = self.proposal_session_ref_for(branch_id)
        if not retry_attempt:
            return ref

        retry_ref: dict[str, Any] = {"retry_attempt": True}
        if prior_failure:
            retry_ref["retry_prior_failure"] = prior_failure
        if ref is None:
            return retry_ref
        return {**ref, **retry_ref}

    def _current_round_num(self) -> int:
        if self.get_current_round is not None:
            return self.get_current_round()
        owner = getattr(self.increment_round, "__self__", None)
        return int(getattr(owner, "_round_num", 0))



def build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    """Build a full verification failure detail string for LLM diagnosis."""
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
