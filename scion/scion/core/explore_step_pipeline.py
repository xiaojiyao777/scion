"""Explore-step execution pipeline for branch candidates."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)
from scion.core.step_result import StepResult
from scion.core.verification_call import run_verification_gate

logger = logging.getLogger(__name__)


def _proposal_failure_hypothesis(detail: str) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=f"Proposal generation failed: {detail}",
        change_locus="proposal",
        action="create_new",
        target_file=None,
        predicted_direction="exploratory",
        target_weakness="proposal_generation",
        expected_effect="no candidate generated",
    )


def _is_candidate_scoped_heavy_failure(
    hypothesis: HypothesisProposal,
    *,
    problem_spec: Any | None,
) -> bool:
    """Return whether a heavy failure should retire only this candidate.

    Top-level solver-design surfaces are problem-object boundaries, not narrow
    mechanisms. A single invalid implementation should not globally blacklist
    the boundary and push later proposal rounds back to component surfaces.
    """
    surface = _surface_for_hypothesis(problem_spec, hypothesis)
    if surface is None:
        return False
    kind = str(getattr(surface, "kind", "") or "").strip().lower()
    role = str(getattr(getattr(surface, "algorithm", None), "role", "") or "").lower()
    return (
        kind in {"solver_design", "solver_algorithm"}
        or "solver_design" in role
        or "solver_algorithm" in role
    )


def _surface_for_hypothesis(
    problem_spec: Any | None,
    hypothesis: HypothesisProposal,
) -> Any | None:
    if problem_spec is None:
        return None
    target_name = str(getattr(hypothesis, "change_locus", "") or "").strip()
    if not target_name:
        return None
    for surface in getattr(problem_spec, "research_surfaces", []) or []:
        if str(getattr(surface, "name", "") or "").strip() == target_name:
            return surface
    return None


@dataclass(frozen=True)
class _VerificationOutcome:
    step_result: Optional[StepResult]
    code_hash: str
    verification_result: VerificationResult


@dataclass
class ExploreStepPipeline:
    """Own the proposal -> contract -> verification -> screening path."""

    branch_controller: Any
    contract_gate: Any
    verification_gate: Any
    hypothesis_store: Any
    registry: Any
    campaign_id: str
    get_champion: Callable[[], Optional[ChampionState]]
    pending_hypotheses: MutableMapping[str, Tuple[HypothesisProposal, HypothesisRecord, str]]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    branch_workspaces: MutableMapping[str, str]
    failure_streak: MutableMapping[str, int]
    increment_round: Callable[[], int]
    increment_rounds_since_last_promote: Callable[[], None]
    generate_hypothesis: Callable[
        [Branch],
        Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]],
    ]
    generate_code: Callable[..., Optional[PatchProposal]]
    attempt_fix: Callable[
        [Branch, PatchProposal, VerificationResult],
        Optional[PatchProposal],
    ]
    handle_failure: Callable[..., None]
    record_step: Callable[[StepRecord], None]
    setup_workspace: Callable[[Branch], Optional[str]]
    apply_patch: Callable[..., Any]
    record_verification_pass: Callable[[Branch, str], None]
    archive_failed_workspace: Callable[[str, str, int], Optional[str]]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        Tuple[Decision, Optional[ProtocolResult], CanaryResult],
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    decision_reason_codes_for: Callable[[str, Optional[ProtocolResult]], Optional[Tuple[str, ...]]]
    proposal_failure_detail_for: Callable[[str], Optional[str]] = lambda _branch_id: None
    proposal_session_ref_for: Callable[[str], Optional[dict[str, Any]]] = lambda _branch_id: None

    def run(self, branch: Branch) -> StepResult:
        """Run the full EXPLORE/EXPLORE_EXPAND branch step."""
        bid = branch.branch_id
        rnum = self.increment_round()
        self.increment_rounds_since_last_promote()

        pending = self.pending_hypotheses.pop(bid, None)
        prior_failure: Optional[str] = None

        if pending is None:
            # Expand budgets are per candidate, not per branch.
            branch.screening_expand_count = 0
            branch.validation_expand_count = 0

        if pending is not None:
            hypothesis, h_record, prior_failure = pending
            logger.info(
                "Branch %s: retrying code gen for pending hypothesis (prior failure: %s)",
                bid,
                prior_failure[:80],
            )
            c_result_pending = self._validate_hypothesis(hypothesis)
            if not c_result_pending.passed:
                logger.info(
                    "Branch %s: pending hypothesis re-failed contract gate: %s",
                    bid,
                    c_result_pending.failure_reason,
                )
                reason = c_result_pending.failure_reason or ""
                category = "search_guidance" if "C10_novelty" in reason else "contract"
                self.handle_failure(branch, FailureEvent(category=category, detail=reason))
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
                self.record_step(
                    StepRecord(
                        round_num=rnum,
                        branch_id=bid,
                        hypothesis=hypothesis,
                        patch=None,
                        contract_passed=False,
                        verification_passed=False,
                        protocol_result=None,
                        decision=None,
                        failure_stage="hypothesis_contract",
                        failure_detail=c_result_pending.failure_reason,
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=self.proposal_session_ref_for(bid),
                    )
                )
                return StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="pending hypothesis re-failed contract gate",
                )
            self.branch_hypotheses[bid] = hypothesis
        else:
            hypothesis, h_record = self.generate_hypothesis(branch)
            if hypothesis is None:
                failure_detail = (
                    self.proposal_failure_detail_for(bid)
                    or "hypothesis generation failed"
                )
                self._record_proposal_fail_event(bid, failure_detail)
                self.record_step(
                    StepRecord(
                        round_num=rnum,
                        branch_id=bid,
                        hypothesis=_proposal_failure_hypothesis(failure_detail),
                        patch=None,
                        contract_passed=False,
                        verification_passed=False,
                        protocol_result=None,
                        decision=None,
                        failure_stage="proposal",
                        failure_detail=failure_detail,
                        proposal_session_ref=self.proposal_session_ref_for(bid),
                    )
                )
                return StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="hypothesis generation failed",
                )
            if h_record is None:
                raise RuntimeError(
                    f"Branch {bid}: hypothesis generated without canonical record"
                )
            logger.info(
                "Branch %s R1 hypothesis: locus=%s action=%s target=%s text='%s'",
                bid,
                hypothesis.change_locus,
                hypothesis.action,
                hypothesis.target_file,
                (hypothesis.hypothesis_text or "")[:200],
            )

            c_result = self._validate_hypothesis(hypothesis)
            if not c_result.passed:
                logger.info(
                    "Branch %s: hypothesis contract failed: %s",
                    bid,
                    c_result.failure_reason,
                )
                reason = c_result.failure_reason or ""
                category = "search_guidance" if "C10_novelty" in reason else "contract"
                self.handle_failure(branch, FailureEvent(category=category, detail=reason))
                self._record_contract_failure(bid, hypothesis, c_result.failure_reason or "")
                self.record_step(
                    StepRecord(
                        round_num=rnum,
                        branch_id=bid,
                        hypothesis=hypothesis,
                        patch=None,
                        contract_passed=False,
                        verification_passed=False,
                        protocol_result=None,
                        decision=None,
                        failure_stage="hypothesis_contract",
                        failure_detail=c_result.failure_reason,
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=self.proposal_session_ref_for(bid),
                    )
                )
                return StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="hypothesis contract failed",
                )

            champion = self.get_champion()
            h_record.base_champion_version = champion.version if champion else 0
            self.hypothesis_store.save(h_record)
            self.branch_hypotheses[bid] = hypothesis

        patch = self.generate_code(branch, hypothesis, prior_failure=prior_failure)
        if patch is not None:
            logger.info(
                "Branch %s R2 code: file=%s action=%s code_len=%d",
                bid,
                patch.file_path,
                patch.action,
                len(patch.code_content or ""),
            )
            if prior_failure is not None:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0

        if patch is None:
            detailed_failure = self.proposal_failure_detail_for(bid)
            if prior_failure is not None:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
                failure_detail = (
                    f"{detailed_failure} (retry - hypothesis rejected)"
                    if detailed_failure
                    else "LLM code generation failed (retry - hypothesis rejected)"
                )
            else:
                failure_detail = detailed_failure or "LLM code generation failed"
                self.pending_hypotheses[bid] = (
                    hypothesis,
                    h_record,
                    failure_detail,
                )
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "code_failed")
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=None,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="code_generation",
                    failure_detail=failure_detail,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=self.proposal_session_ref_for(bid),
                )
            )
            return StepResult(
                action="explore",
                branch_id=bid,
                reason="code generation failed",
            )

        p_result = self.contract_gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
        )
        if not p_result.passed:
            logger.info(
                "Branch %s: patch contract failed: %s",
                bid,
                p_result.failure_reason,
            )
            self.handle_failure(
                branch,
                FailureEvent(category="contract", detail=p_result.failure_reason or ""),
            )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=False,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="patch_contract",
                    failure_detail=p_result.failure_reason,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=self.proposal_session_ref_for(bid),
                )
            )
            return StepResult(
                action="explore",
                branch_id=bid,
                reason="patch contract failed",
            )

        workspace = self.setup_workspace(branch)
        if workspace is None:
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail="workspace setup failed"),
                hypothesis_already_recorded=True,
            )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="workspace",
                    failure_detail="workspace setup failed",
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=self.proposal_session_ref_for(bid),
                )
            )
            return StepResult(
                action="explore",
                branch_id=bid,
                reason="workspace setup failed",
            )

        try:
            applied = self.apply_patch(
                branch,
                workspace,
                patch,
                hypothesis=hypothesis,
                remember_patch=True,
                sync_registry=True,
            )
            code_hash = applied.code_hash
        except Exception as exc:
            logger.warning("Branch %s: apply_patch failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="contract", detail=f"apply_patch: {exc}"),
            )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="workspace",
                    failure_detail=f"apply_patch: {exc}",
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=self.proposal_session_ref_for(bid),
                )
            )
            return StepResult(
                action="explore",
                branch_id=bid,
                reason="apply_patch failed",
            )

        champion = self.get_champion()
        champ_ws = champion.code_snapshot_path if champion else ""
        vresult = run_verification_gate(
            self.verification_gate,
            workspace,
            champ_ws,
            patch,
            hypothesis=hypothesis,
        )
        if not vresult.passed:
            verification_outcome = self._handle_verification_failure(
                branch=branch,
                rnum=rnum,
                workspace=workspace,
                patch=patch,
                hypothesis=hypothesis,
                h_record=h_record,
                vresult=vresult,
                code_hash=code_hash,
                champion_workspace=champ_ws,
            )
            if verification_outcome.step_result is not None:
                return verification_outcome.step_result
            code_hash = verification_outcome.code_hash
            vresult = verification_outcome.verification_result

        self.record_verification_pass(branch, code_hash)
        self.failure_streak.clear()
        self.branch_current_hypothesis[bid] = h_record

        fresh = self.branch_controller.get_branch(bid)
        if fresh and fresh.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            logger.info(
                "Branch %s: marked stale by async weight-opt during explore - deferring",
                bid,
            )
            return StepResult(
                action="skip",
                branch_id=bid,
                reason="stale_during_explore",
            )

        self.branch_controller.next_stage(bid)
        decision, protocol_result, canary_result = self.evaluate(
            branch,
            workspace,
            hypothesis,
        )
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label="explore",
        )
        logger.debug(
            "_run_explore_step done bid=%s decision=%s workspaces=%s",
            bid,
            decision.value,
            list(self.branch_workspaces.keys()),
        )
        self.record_step(
            StepRecord(
                round_num=rnum,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=self.branch_patches.get(bid, patch),
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision or Decision.ABANDON,
                failure_stage=None,
                failure_detail=None,
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                proposal_session_ref=self.proposal_session_ref_for(bid),
            )
        )
        return result

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
                )
            )
            return _VerificationOutcome(
                step_result=StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="verification failed (light)",
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
            )
        )
        return _VerificationOutcome(
            step_result=StepResult(
                action="explore",
                branch_id=bid,
                reason="verification failed (heavy)",
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
            proposal_session_ref=self.proposal_session_ref_for(bid),
        )

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
