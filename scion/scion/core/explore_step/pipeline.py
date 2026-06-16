"""Explore-step pipeline facade class."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Optional, Sequence, Tuple

from scion.core.branch_hygiene import (
    branch_hygiene_context,
    branch_requires_repair_focus,
    record_branch_lifecycle_policy_block,
)
from scion.core.branch_repair_policy import (
    REPAIR_FIRST_POLICY_VIOLATION,
    branch_continuation_mechanism_ids,
    branch_repair_mechanism_ids,
    is_branch_lifecycle_policy_block_detail,
    validate_repair_focused_patch,
)
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
from scion.core.repeated_contract_failures import (
    REPEATED_CONTRACT_REROUTE_REASON,
    RepeatedContractRecord,
    record_contract_failure_attempt,
)
from scion.core.run_validity import failure_category_for_run_validity
from scion.core.step_result import StepResult
from scion.core.telemetry_validation import screened_experiment_effective
from scion.core.verification_call import run_verification_gate
from scion.contract.result_payload import diagnostic_checks
from scion.proposal.context.branch_followup import branch_current_file_sources

from .common import (
    _AGENTIC_BUDGET_CONTROL,
    _AGENTIC_SESSION_TIMEOUT,
    _AGENT_QUALITY_BLOCKED,
    _agent_quality_failure_detail,
    _is_algorithm_smoke_failure_detail,
    _is_agent_quality_blocked_detail,
    _is_agentic_control_timeout_detail,
    _is_schema_quality_block_detail,
    _proposal_failure_hypothesis,
    _proposal_failure_reason,
    _proposal_failure_stage,
    _proposal_session_ref_is_agent_quality_blocked,
)
from .branch_lesson_usage import (
    branch_lesson_usage_pre_code_block_reason,
    branch_lesson_usage_requirement_metadata,
    canonical_branch_lesson_usage_repair,
)
from .events import ExploreStepEventMixin
from .material_difference import (
    material_difference_pre_code_block_reason,
    material_difference_requirement_metadata,
)
from .verification import VerificationMixin

logger = logging.getLogger(__name__)

__all__ = [
    "ExploreStepPipeline",
    "branch_lesson_usage_pre_code_block_reason",
    "branch_lesson_usage_requirement_metadata",
    "material_difference_pre_code_block_reason",
    "material_difference_requirement_metadata",
]


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
        Tuple[Optional[Decision], Optional[ProtocolResult], CanaryResult],
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
    step_history: Sequence[StepRecord] = ()
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}

    def _block_missing_material_difference(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        *,
        round_num: int,
        retry_attempt: bool,
        prior_failure: str | None,
    ) -> StepResult | None:
        bid = branch.branch_id
        session_ref = self._proposal_session_ref(
            bid,
            retry_attempt=retry_attempt,
            prior_failure=prior_failure,
        )
        detail = material_difference_pre_code_block_reason(
            hypothesis,
            branch,
            session_ref=session_ref,
        )
        if not detail:
            return None
        logger.info(
            "Branch %s: material_difference pre-code block: %s",
            bid,
            detail,
        )
        self.handle_failure(
            branch,
            FailureEvent(category="proposal", detail=detail),
        )
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=None,
                contract_passed=True,
                verification_passed=False,
                protocol_result=None,
                decision=None,
                failure_stage="proposal",
                failure_detail=detail,
                hypothesis_id=h_record.hypothesis_id,
                proposal_session_ref=session_ref,
                counts_toward_max_rounds=False,
                attempt_kind="proposal_block",
            )
        )
        return StepResult(
            action="explore",
            branch_id=bid,
            reason="material difference required before code generation",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
            failure_stage="proposal",
            failure_detail=detail,
            failure_category="proposal",
            proposal_session_ref=session_ref,
        )

    def _block_missing_branch_lesson_usage(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        *,
        round_num: int,
        retry_attempt: bool,
        prior_failure: str | None,
    ) -> StepResult | None:
        bid = branch.branch_id
        session_ref = self._proposal_session_ref(
            bid,
            retry_attempt=retry_attempt,
            prior_failure=prior_failure,
        )
        detail = branch_lesson_usage_pre_code_block_reason(
            hypothesis,
            branch,
            session_ref=session_ref,
        )
        if detail:
            repair = canonical_branch_lesson_usage_repair(
                getattr(hypothesis, "branch_lesson_usage", None),
                metadata=branch_lesson_usage_requirement_metadata(
                    branch,
                    session_ref=session_ref,
                ),
                hypothesis=hypothesis,
            )
            repaired_usage = repair.get("branch_lesson_usage") if repair else None
            if isinstance(repaired_usage, dict) and repaired_usage:
                hypothesis.branch_lesson_usage = repaired_usage
                attribution = repair.get("repair_attribution")
                if isinstance(attribution, dict) and attribution:
                    hypothesis.schema_repair_attribution = (
                        *tuple(hypothesis.schema_repair_attribution or ()),
                        attribution,
                    )
                detail = branch_lesson_usage_pre_code_block_reason(
                    hypothesis,
                    branch,
                    session_ref=session_ref,
                )
        if not detail:
            return None
        logger.info(
            "Branch %s: branch_lesson_usage pre-code block: %s",
            bid,
            detail,
        )
        self.handle_failure(
            branch,
            FailureEvent(category="proposal", detail=detail),
        )
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=None,
                contract_passed=True,
                verification_passed=False,
                protocol_result=None,
                decision=None,
                failure_stage="proposal",
                failure_detail=detail,
                hypothesis_id=h_record.hypothesis_id,
                proposal_session_ref=session_ref,
                counts_toward_max_rounds=False,
                attempt_kind="proposal_block",
            )
        )
        return StepResult(
            action="explore",
            branch_id=bid,
            reason="branch lesson usage required before code generation",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
            failure_stage="proposal",
            failure_detail=detail,
            failure_category="proposal",
            proposal_session_ref=session_ref,
        )

    def run(self, branch: Branch) -> StepResult:
        """Run the full EXPLORE/EXPLORE_EXPAND branch step."""
        bid = branch.branch_id
        self._proposal_session_ref_cache = {}
        pending = self.pending_hypotheses.pop(bid, None)
        retry_attempt = pending is not None
        if retry_attempt:
            rnum = self._current_round_num()
        else:
            rnum = self.increment_round()
            self.increment_rounds_since_last_promote()

        prior_failure: Optional[str] = None
        h_contract_diagnostics: tuple[dict[str, Any], ...] = ()

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
                repeated_contract = self._record_repeated_contract_failure(
                    branch,
                    failure_detail,
                    hypothesis,
                    session_ref,
                    failure_stage="hypothesis_contract",
                )
                self.hypothesis_store.mark_status(
                    h_record.hypothesis_id,
                    "rejected" if quality_blocked else "contract_failed",
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
                        contract_diagnostics=diagnostic_checks(c_result_pending),
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=session_ref,
                        attempt_kind=(
                            "branch_lifecycle_policy"
                            if repeated_contract.threshold_reached
                            else "screening"
                        ),
                        repair_policy_reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else None
                        ),
                    )
                )
                return self._finish_status_progress(
                    StepResult(
                        action="explore",
                        branch_id=bid,
                        reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else
                            _AGENT_QUALITY_BLOCKED
                            if quality_blocked
                            else "pending hypothesis re-failed contract gate"
                        ),
                        counts_toward_max_rounds=False,
                        attempt_kind=(
                            "branch_lifecycle_policy"
                            if repeated_contract.threshold_reached
                            else "screening"
                        ),
                        repair_policy_reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else ""
                        ),
                        proposal_session_ref=session_ref,
                    )
                )
            h_contract_diagnostics = diagnostic_checks(c_result_pending)
            blocked = self._block_missing_material_difference(
                branch,
                hypothesis,
                h_record,
                round_num=rnum,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            if blocked is not None:
                return self._finish_status_progress(blocked)
            blocked = self._block_missing_branch_lesson_usage(
                branch,
                hypothesis,
                h_record,
                round_num=rnum,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            if blocked is not None:
                return self._finish_status_progress(blocked)
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
                failure_category = failure_category_for_run_validity(
                    failure_detail,
                    failure_stage=failure_stage,
                    session_ref=session_ref,
                )
                if failure_stage == _AGENT_QUALITY_BLOCKED:
                    self._record_agent_quality_branch_signal(
                        branch,
                        failure_detail,
                        session_ref,
                    )
                self._record_proposal_fail_event(bid, failure_detail)
                attempt_kind, repair_ids, repair_policy_reason = (
                    self._repair_attempt_metadata(branch, failure_detail)
                )
                if attempt_kind == "branch_lifecycle_policy":
                    self._record_branch_lifecycle_policy_block(
                        branch,
                        failure_detail,
                    )
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
                        counts_toward_max_rounds=False,
                        attempt_kind=attempt_kind,
                        repair_policy_reason=repair_policy_reason,
                        repair_mechanism_ids=repair_ids,
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
                        attempt_kind=attempt_kind,  # type: ignore[arg-type]
                        repair_mechanism_ids=repair_ids,
                        repair_policy_reason=repair_policy_reason or "",
                        failure_stage=failure_stage,
                        failure_detail=failure_detail,
                        failure_category=failure_category,
                        proposal_session_ref=session_ref,
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
                    self.hypothesis_store.mark_status(
                        h_record.hypothesis_id,
                        "contract_failed",
                    )
                repeated_contract = self._record_repeated_contract_failure(
                    branch,
                    failure_detail,
                    hypothesis,
                    session_ref,
                    failure_stage="hypothesis_contract",
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
                        contract_diagnostics=diagnostic_checks(c_result),
                        hypothesis_id=h_record.hypothesis_id,
                        proposal_session_ref=session_ref,
                        attempt_kind=(
                            "branch_lifecycle_policy"
                            if repeated_contract.threshold_reached
                            else "screening"
                        ),
                        repair_policy_reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else None
                        ),
                    )
                )
                return self._finish_status_progress(
                    StepResult(
                        action="explore",
                        branch_id=bid,
                        reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else
                            _AGENT_QUALITY_BLOCKED
                            if quality_blocked
                            else "hypothesis contract failed"
                        ),
                        counts_toward_max_rounds=False,
                        attempt_kind=(
                            "branch_lifecycle_policy"
                            if repeated_contract.threshold_reached
                            else "screening"
                        ),
                        repair_policy_reason=(
                            REPEATED_CONTRACT_REROUTE_REASON
                            if repeated_contract.threshold_reached
                            else ""
                        ),
                        proposal_session_ref=session_ref,
                    )
                )
            h_contract_diagnostics = diagnostic_checks(c_result)

            champion = self.get_champion()
            h_record.base_champion_version = champion.version if champion else 0
            self.hypothesis_store.save(h_record)
            blocked = self._block_missing_material_difference(
                branch,
                hypothesis,
                h_record,
                round_num=rnum,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            if blocked is not None:
                return self._finish_status_progress(blocked)
            blocked = self._block_missing_branch_lesson_usage(
                branch,
                hypothesis,
                h_record,
                round_num=rnum,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            if blocked is not None:
                return self._finish_status_progress(blocked)
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
            cache = getattr(self, "_proposal_session_ref_cache", None)
            if isinstance(cache, dict):
                cache.pop(bid, None)
            session_timeout = _is_agentic_control_timeout_detail(detailed_failure)
            quality_blocked = _is_agent_quality_blocked_detail(detailed_failure)
            status = "code_failed"
            queue_pending_retry = False
            if session_timeout:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                failure_detail = detailed_failure or _AGENTIC_SESSION_TIMEOUT
            elif quality_blocked:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                status = (
                    "smoke_failed"
                    if _is_algorithm_smoke_failure_detail(detailed_failure)
                    else "rejected"
                )
                failure_detail = detailed_failure or _AGENT_QUALITY_BLOCKED
            elif prior_failure is not None:
                branch.pending_retry = False
                branch.consecutive_llm_retries = 0
                status = "rejected"
                failure_detail = (
                    f"{detailed_failure} (retry - hypothesis rejected)"
                    if detailed_failure
                    else "LLM code generation failed (retry - hypothesis rejected)"
                )
            else:
                failure_detail = detailed_failure or "LLM code generation failed"
                queue_pending_retry = True
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            failure_stage = _proposal_failure_stage(
                failure_detail,
                "code_generation",
            )
            failure_category = failure_category_for_run_validity(
                failure_detail,
                failure_stage=failure_stage,
                session_ref=session_ref,
            )
            if failure_stage == _AGENT_QUALITY_BLOCKED:
                self._record_agent_quality_branch_signal(
                    branch,
                    failure_detail,
                    session_ref,
                )
            repeated_contract = self._record_repeated_contract_failure(
                branch,
                failure_detail,
                hypothesis,
                session_ref,
                failure_stage=failure_stage,
            )
            if repeated_contract.threshold_reached:
                queue_pending_retry = False
                self.pending_hypotheses.pop(bid, None)
                if status == "code_failed":
                    status = "rejected"
            if queue_pending_retry:
                self.pending_hypotheses[bid] = (
                    hypothesis,
                    h_record,
                    failure_detail,
                )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, status)
            attempt_kind, repair_ids, repair_policy_reason = (
                self._repair_attempt_metadata(branch, failure_detail)
            )
            if repeated_contract.threshold_reached:
                attempt_kind = "branch_lifecycle_policy"
                repair_policy_reason = REPEATED_CONTRACT_REROUTE_REASON
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
                    counts_toward_max_rounds=False,
                    attempt_kind=attempt_kind,
                    repair_policy_reason=repair_policy_reason,
                    repair_mechanism_ids=repair_ids,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=_proposal_failure_reason(
                        failure_detail,
                        "code generation failed",
                    )
                    if not repeated_contract.threshold_reached
                    else REPEATED_CONTRACT_REROUTE_REASON,
                    counts_toward_max_rounds=False,
                    attempt_kind=attempt_kind,  # type: ignore[arg-type]
                    repair_mechanism_ids=repair_ids,
                    repair_policy_reason=repair_policy_reason or "",
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    failure_category=failure_category,
                    proposal_session_ref=session_ref,
                ),
            )

        repair_patch_check = validate_repair_focused_patch(
            branch,
            hypothesis,
            patch,
            step_history=self.step_history,
        )
        if not repair_patch_check.allowed:
            detail = repair_patch_check.detail
            logger.info(
                "Branch %s: branch continuation patch policy failed: %s",
                bid,
                detail,
            )
            if not is_branch_lifecycle_policy_block_detail(detail):
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=detail),
                )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            attempt_kind, repair_ids, repair_policy_reason = (
                self._repair_attempt_metadata(branch, detail)
            )
            if attempt_kind == "branch_lifecycle_policy":
                self._record_branch_lifecycle_policy_block(branch, detail)
            if not repair_ids:
                repair_ids = (
                    repair_patch_check.protected_mechanism_ids
                    or repair_patch_check.proposed_mechanism_ids
                )
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
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
                    failure_stage="repair_policy",
                    failure_detail=detail,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    counts_toward_max_rounds=False,
                    attempt_kind=attempt_kind,
                    repair_policy_reason=(
                        repair_policy_reason or repair_patch_check.reason
                    ),
                    repair_mechanism_ids=repair_ids,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=detail,
                    counts_toward_max_rounds=False,
                    attempt_kind=attempt_kind,  # type: ignore[arg-type]
                    repair_mechanism_ids=repair_ids,
                    repair_policy_reason=(
                        repair_policy_reason or repair_patch_check.reason
                    ),
                    proposal_session_ref=session_ref,
                )
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
            base_file_overrides=branch_current_file_sources(
                branch,
                self.step_history,
            ),
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
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
            repeated_contract = self._record_repeated_contract_failure(
                branch,
                p_result.failure_reason,
                hypothesis,
                session_ref,
                failure_stage="patch_contract",
            )
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "contract_failed")
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
                    contract_diagnostics=(
                        *h_contract_diagnostics,
                        *diagnostic_checks(p_result),
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    attempt_kind=(
                        "branch_lifecycle_policy"
                        if repeated_contract.threshold_reached
                        else "screening"
                    ),
                    repair_policy_reason=(
                        REPEATED_CONTRACT_REROUTE_REASON
                        if repeated_contract.threshold_reached
                        else None
                    ),
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=(
                        REPEATED_CONTRACT_REROUTE_REASON
                        if repeated_contract.threshold_reached
                        else "patch contract failed"
                    ),
                    counts_toward_max_rounds=not retry_attempt,
                    attempt_kind=(
                        "branch_lifecycle_policy"
                        if repeated_contract.threshold_reached
                        else "screening"
                    ),
                    repair_policy_reason=(
                        REPEATED_CONTRACT_REROUTE_REASON
                        if repeated_contract.threshold_reached
                        else ""
                    ),
                    proposal_session_ref=session_ref,
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
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
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
                    proposal_session_ref=session_ref,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="workspace setup failed",
                    counts_toward_max_rounds=not retry_attempt,
                    proposal_session_ref=session_ref,
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
            session_ref = self._proposal_session_ref(
                bid,
                retry_attempt=retry_attempt,
                prior_failure=prior_failure,
            )
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
                    proposal_session_ref=session_ref,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="apply_patch failed",
                    counts_toward_max_rounds=not retry_attempt,
                    proposal_session_ref=session_ref,
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
        finalizer_decision = decision or Decision.ABANDON
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=finalizer_decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label="explore",
        )
        _annotate_protocol_accounting(result, protocol_result)
        result.canary_result = canary_result
        failure_stage, failure_detail = _evaluation_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        if decision is None:
            result.decision = None
            result.failure_stage = failure_stage or "evaluation"
            result.failure_detail = failure_detail or "evaluation failed"
        provenance = self.decision_provenance_for(bid)
        for key, value in provenance.items():
            setattr(result, key, value)
        session_ref = self._proposal_session_ref(
            bid,
            retry_attempt=retry_attempt,
            prior_failure=prior_failure,
        )
        result.proposal_session_ref = session_ref
        logger.debug(
            "_run_explore_step done bid=%s decision=%s workspaces=%s",
            bid,
            finalizer_decision.value,
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
                decision=result.decision if decision is not None else None,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                contract_diagnostics=(
                    *h_contract_diagnostics,
                    *diagnostic_checks(p_result),
                ),
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                **provenance,
                proposal_session_ref=session_ref,
                canary_result=canary_result,
                counts_toward_max_rounds=result.counts_toward_max_rounds,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
            )
        )
        if retry_attempt:
            result.counts_toward_max_rounds = False
        return self._finish_status_progress(result)

    def _repair_attempt_metadata(
        self,
        branch: Branch,
        failure_detail: str | None,
    ) -> tuple[str, tuple[str, ...], str | None]:
        if (
            failure_category_for_run_validity(
                failure_detail,
                failure_stage="proposal",
            )
            == "infra"
        ):
            return "proposal_retry", (), str(failure_detail or "")
        if _is_schema_quality_block_detail(failure_detail):
            return "schema_quality_block", (), str(failure_detail or "")
        if "stale_source" in str(failure_detail or "").lower():
            return "proposal_retry", (), "stale_source_refresh"
        if is_branch_lifecycle_policy_block_detail(failure_detail):
            ids = branch_continuation_mechanism_ids(
                branch,
                self.step_history,
            )
            if not ids:
                ids = branch_repair_mechanism_ids(branch)
            return "branch_lifecycle_policy", ids, str(failure_detail or "")
        if not branch_requires_repair_focus(branch):
            return "proposal_block", (), None
        repair_ids = branch_repair_mechanism_ids(branch)
        reason = None
        if REPAIR_FIRST_POLICY_VIOLATION in str(failure_detail or ""):
            reason = str(failure_detail or "")
        return "telemetry_repair", repair_ids, reason

    def _record_branch_lifecycle_policy_block(
        self,
        branch: Branch,
        detail: str | None,
    ) -> None:
        if not is_branch_lifecycle_policy_block_detail(detail):
            return
        record_branch_lifecycle_policy_block(branch, detail)
        try:
            self.persist_branch_state(branch.branch_id)
        except Exception:  # pragma: no cover - reroute persistence is best effort
            logger.debug(
                "Failed to persist branch lifecycle reroute marker for %s",
                branch.branch_id,
                exc_info=True,
            )

    def _record_repeated_contract_failure(
        self,
        branch: Branch,
        failure_detail: str | None,
        hypothesis: HypothesisProposal | None,
        session_ref: dict[str, Any] | None,
        *,
        failure_stage: str | None,
    ) -> RepeatedContractRecord:
        record = record_contract_failure_attempt(
            branch,
            failure_detail,
            hypothesis,
            session_ref,
            failure_stage=failure_stage,
        )
        if record.signature is None:
            return record
        try:
            self.persist_branch_state(branch.branch_id)
        except Exception:  # pragma: no cover - diagnostic persistence is best effort
            logger.debug(
                "Failed to persist repeated-contract diagnostic marker for %s",
                branch.branch_id,
                exc_info=True,
            )
        return record

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


def _evaluation_failure_detail(
    protocol_result: ProtocolResult | None,
    *,
    canary_result: CanaryResult | None = None,
) -> tuple[str | None, str | None]:
    if protocol_result is None:
        return None, None
    reason_codes = {
        str(code).lower()
        for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" not in reason_codes:
        return None, None
    detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
    return "evaluation", detail


def _annotate_protocol_accounting(
    result: StepResult,
    protocol_result: ProtocolResult | None,
) -> None:
    if protocol_result is None:
        return
    stage_obj = getattr(protocol_result, "stage", "")
    stage = str(getattr(stage_obj, "value", stage_obj) or "")
    if stage not in {"screening", "validation", "frozen"}:
        return
    formal_evaluated = (
        getattr(protocol_result, "stats", None) is not None
        and screened_experiment_effective(protocol_result)
    )
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated
