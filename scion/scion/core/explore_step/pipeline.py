"""Explore-step pipeline facade class."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.branch_hygiene import branch_hygiene_context
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

from .common import (
    _AGENTIC_BUDGET_CONTROL,
    _AGENTIC_SESSION_TIMEOUT,
    _AGENT_QUALITY_BLOCKED,
    _agent_quality_failure_detail,
    _is_agent_quality_blocked_detail,
    _is_agentic_control_timeout_detail,
    _proposal_failure_hypothesis,
    _proposal_failure_reason,
    _proposal_failure_stage,
    _proposal_session_ref_is_agent_quality_blocked,
)
from .events import ExploreStepEventMixin
from .verification import VerificationMixin

logger = logging.getLogger(__name__)


@dataclass
class ExploreStepPipeline(VerificationMixin, ExploreStepEventMixin):
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
    get_current_round: Optional[Callable[[], int]] = None
    persist_branch_state: Callable[[str], None] = lambda _branch_id: None
    update_status_progress: Callable[[dict[str, Any] | None], None] = (
        lambda _payload: None
    )

    def run(self, branch: Branch) -> StepResult:
        """Run the full EXPLORE/EXPLORE_EXPAND branch step."""
        bid = branch.branch_id
        pending = self.pending_hypotheses.pop(bid, None)
        retry_attempt = pending is not None
        if retry_attempt:
            rnum = self._current_round_num()
        else:
            rnum = self.increment_round()
            self.increment_rounds_since_last_promote()

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
            self._emit_status_progress(
                branch,
                phase="proposal_hypothesis_retry_contract",
                round_num=rnum,
                hypothesis=hypothesis,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            c_result_pending = self._validate_hypothesis(hypothesis)
            if not c_result_pending.passed:
                logger.info(
                    "Branch %s: pending hypothesis re-failed contract gate: %s",
                    bid,
                    c_result_pending.failure_reason,
                )
                reason = c_result_pending.failure_reason or ""
                session_ref = self._proposal_session_ref(
                    bid,
                    retry_attempt=retry_attempt,
                    prior_failure=prior_failure,
                )
                quality_blocked = (
                    _proposal_session_ref_is_agent_quality_blocked(session_ref)
                    or _is_agent_quality_blocked_detail(reason)
                )
                failure_stage = (
                    _AGENT_QUALITY_BLOCKED if quality_blocked else "hypothesis_contract"
                )
                failure_detail = (
                    _agent_quality_failure_detail(reason, session_ref)
                    if quality_blocked
                    else c_result_pending.failure_reason
                )
                if quality_blocked:
                    self._record_agent_quality_branch_signal(
                        branch,
                        failure_detail,
                        session_ref,
                    )
                else:
                    category = (
                        "search_guidance" if "C10_novelty" in reason else "contract"
                    )
                    self.handle_failure(
                        branch,
                        FailureEvent(category=category, detail=reason),
                    )
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
                        failure_stage=failure_stage,
                        failure_detail=failure_detail,
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=session_ref,
                    )
                )
                return self._finish_status_progress(
                    StepResult(
                        action="explore",
                        branch_id=bid,
                        reason=(
                            _AGENT_QUALITY_BLOCKED
                            if quality_blocked
                            else "pending hypothesis re-failed contract gate"
                        ),
                        counts_toward_max_rounds=False,
                    )
                )
            self.branch_hypotheses[bid] = hypothesis
        else:
            self._emit_status_progress(
                branch,
                phase="proposal_hypothesis",
                round_num=rnum,
                retry_attempt=retry_attempt,
            )
            hypothesis, h_record = self.generate_hypothesis(branch)
            if hypothesis is None:
                failure_detail = (
                    self.proposal_failure_detail_for(bid)
                    or "hypothesis generation failed"
                )
                session_ref = self._proposal_session_ref(bid)
                failure_stage = _proposal_failure_stage(
                    failure_detail,
                    "proposal",
                )
                if failure_stage == _AGENT_QUALITY_BLOCKED:
                    self._record_agent_quality_branch_signal(
                        branch,
                        failure_detail,
                        session_ref,
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
                        failure_stage=failure_stage,
                        failure_detail=failure_detail,
                        proposal_session_ref=session_ref,
                    )
                )
                return self._finish_status_progress(
                    StepResult(
                        action="explore",
                        branch_id=bid,
                        reason=_proposal_failure_reason(
                            failure_detail,
                            "hypothesis generation failed",
                        ),
                        counts_toward_max_rounds=False,
                    ),
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

            self._emit_status_progress(
                branch,
                phase="hypothesis_contract",
                round_num=rnum,
                hypothesis=hypothesis,
                retry_attempt=retry_attempt,
            )
            c_result = self._validate_hypothesis(hypothesis)
            if not c_result.passed:
                logger.info(
                    "Branch %s: hypothesis contract failed: %s",
                    bid,
                    c_result.failure_reason,
                )
                reason = c_result.failure_reason or ""
                session_ref = self._proposal_session_ref(bid)
                quality_blocked = (
                    _proposal_session_ref_is_agent_quality_blocked(session_ref)
                    or _is_agent_quality_blocked_detail(reason)
                )
                failure_stage = (
                    _AGENT_QUALITY_BLOCKED if quality_blocked else "hypothesis_contract"
                )
                failure_detail = (
                    _agent_quality_failure_detail(reason, session_ref)
                    if quality_blocked
                    else c_result.failure_reason
                )
                if quality_blocked:
                    self._record_agent_quality_branch_signal(
                        branch,
                        failure_detail,
                        session_ref,
                    )
                else:
                    category = (
                        "search_guidance" if "C10_novelty" in reason else "contract"
                    )
                    self.handle_failure(
                        branch,
                        FailureEvent(category=category, detail=reason),
                    )
                    self._record_contract_failure(
                        bid,
                        hypothesis,
                        c_result.failure_reason or "",
                    )
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
                        failure_stage=failure_stage,
                        failure_detail=failure_detail,
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=session_ref,
                    )
                )
                return self._finish_status_progress(
                    StepResult(
                        action="explore",
                        branch_id=bid,
                        reason=(
                            _AGENT_QUALITY_BLOCKED
                            if quality_blocked
                            else "hypothesis contract failed"
                        ),
                        counts_toward_max_rounds=False,
                    )
                )

            champion = self.get_champion()
            h_record.base_champion_version = champion.version if champion else 0
            self.hypothesis_store.save(h_record)
            self.branch_hypotheses[bid] = hypothesis

        self._emit_status_progress(
            branch,
            phase="proposal_code",
            round_num=rnum,
            hypothesis=hypothesis,
            retry_attempt=retry_attempt,
            prior_failure=prior_failure,
        )
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
                self._mark_code_generation_recovered(branch, h_record)

        if patch is None:
            detailed_failure = self.proposal_failure_detail_for(bid)
            session_timeout = _is_agentic_control_timeout_detail(detailed_failure)
            quality_blocked = _is_agent_quality_blocked_detail(detailed_failure)
            if session_timeout:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                failure_detail = detailed_failure or _AGENTIC_SESSION_TIMEOUT
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "code_failed")
            elif quality_blocked:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
                failure_detail = detailed_failure or _AGENT_QUALITY_BLOCKED
            elif prior_failure is not None:
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
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            failure_stage = _proposal_failure_stage(
                failure_detail,
                "code_generation",
            )
            if failure_stage == _AGENT_QUALITY_BLOCKED:
                self._record_agent_quality_branch_signal(
                    branch,
                    failure_detail,
                    session_ref,
                )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=None,
                    contract_passed=not quality_blocked,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=_proposal_failure_reason(
                        failure_detail,
                        "code generation failed",
                    ),
                    counts_toward_max_rounds=False,
                ),
            )

        self._emit_status_progress(
            branch,
            phase="patch_contract",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
            retry_attempt=retry_attempt,
        )
        p_result = self.contract_gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
            base_snapshot_path=self.branch_workspaces.get(bid),
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
                    proposal_session_ref=self._proposal_session_ref(
                        bid,
                        retry_attempt=retry_attempt,
                        prior_failure=prior_failure,
                    ),
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="patch contract failed",
                    counts_toward_max_rounds=not retry_attempt,
                )
            )

        self._emit_status_progress(
            branch,
            phase="workspace_setup",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
            retry_attempt=retry_attempt,
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
                    proposal_session_ref=self._proposal_session_ref(
                        bid,
                        retry_attempt=retry_attempt,
                        prior_failure=prior_failure,
                    ),
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="workspace setup failed",
                    counts_toward_max_rounds=not retry_attempt,
                )
            )

        try:
            self._emit_status_progress(
                branch,
                phase="apply_patch",
                round_num=rnum,
                hypothesis=hypothesis,
                patch=patch,
                retry_attempt=retry_attempt,
            )
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
                    proposal_session_ref=self._proposal_session_ref(
                        bid,
                        retry_attempt=retry_attempt,
                        prior_failure=prior_failure,
                    ),
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="apply_patch failed",
                    counts_toward_max_rounds=not retry_attempt,
                )
            )

        champion = self.get_champion()
        champ_ws = champion.code_snapshot_path if champion else ""
        self._emit_status_progress(
            branch,
            phase="verification",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
            retry_attempt=retry_attempt,
        )
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
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            if verification_outcome.step_result is not None:
                return self._finish_status_progress(
                    verification_outcome.step_result
                )
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
            return self._finish_status_progress(
                StepResult(
                    action="skip",
                    branch_id=bid,
                    reason="stale_during_explore",
                    counts_toward_max_rounds=not retry_attempt,
                )
            )

        self.branch_controller.next_stage(bid)
        self._emit_status_progress(
            branch,
            phase="evaluation_dispatch",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
            retry_attempt=retry_attempt,
        )
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
                proposal_session_ref=self._proposal_session_ref(
                    bid,
                    retry_attempt=retry_attempt,
                    prior_failure=prior_failure,
                ),
            )
        )
        if retry_attempt:
            result.counts_toward_max_rounds = False
        return self._finish_status_progress(result)

    def _emit_status_progress(
        self,
        branch: Branch,
        *,
        phase: str,
        round_num: int,
        hypothesis: HypothesisProposal | None = None,
        patch: PatchProposal | None = None,
        retry_attempt: bool = False,
        prior_failure: str | None = None,
    ) -> None:
        """Best-effort heartbeat for long pre-protocol steps."""
        payload: dict[str, Any] = {
            "branch_id": branch.branch_id,
            "stage": "proposal",
            "phase": phase,
            "round_num": round_num,
            "base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "retry_attempt": retry_attempt,
            "step_started_at": datetime.now().isoformat(),
            "complete": False,
        }
        payload.update(branch_hygiene_context(branch))
        if prior_failure:
            payload["retry_prior_failure"] = prior_failure
        if hypothesis is not None:
            payload.update(
                {
                    "target_file": hypothesis.target_file,
                    "hypothesis_action": hypothesis.action,
                    "hypothesis_text": hypothesis.hypothesis_text,
                    "mechanism_changes": [
                        {
                            "id": str(getattr(change, "id", "") or ""),
                            "change_type": str(
                                getattr(change, "change_type", "") or ""
                            ),
                        }
                        for change in tuple(
                            getattr(hypothesis, "mechanism_changes", ()) or ()
                        )
                        if str(getattr(change, "id", "") or "")
                    ],
                }
            )
        if patch is not None:
            payload.update(
                {
                    "patch_action": patch.action,
                    "patch_file": patch.file_path,
                }
            )
        try:
            self.update_status_progress(payload)
        except Exception:  # pragma: no cover - heartbeat must never break research
            logger.debug("Failed to emit explore status progress", exc_info=True)

    def _finish_status_progress(self, result: StepResult) -> StepResult:
        try:
            self.update_status_progress(None)
        except Exception:  # pragma: no cover - status cleanup must not affect result
            logger.debug("Failed to clear explore status progress", exc_info=True)
        return result
