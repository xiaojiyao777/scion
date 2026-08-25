"""Explore-step pipeline facade class."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Optional, Sequence

from scion.contract.result_payload import diagnostic_checks
from scion.core.evaluation_orchestrator import (
    EvaluationExecutionResult,
)
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    block_branch_after_execution,
    record_execution_outcome_event,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.step_result import StepResult
from scion.core.verification_call import run_verification_gate
from scion.core.workspace_service import CandidateWorkspace

from .events import ExploreStepEventMixin
from .verification import VerificationMixin

logger = logging.getLogger(__name__)


def _no_op_event() -> None:
    return None


def _no_op_attempt_scope(_round_num: int) -> AbstractContextManager[None]:
    return nullcontext()


__all__ = [
    "ExploreStepPipeline",
]


@dataclass
class ExploreStepPipeline(VerificationMixin, ExploreStepEventMixin):
    """Own the proposal -> contract -> verification -> screening path."""

    branch_controller: Any
    contract_gate: Any
    verification_gate: Any
    registry: Any
    campaign_id: str
    get_champion: Callable[[], Optional[ChampionState]]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_workspaces: MutableMapping[str, str]
    increment_round: Callable[[], int]
    generate_hypothesis: Callable[[Branch], ProposalAttempt[HypothesisProposal]]
    generate_code: Callable[..., ProposalAttempt[PatchProposal]]
    record_step: Callable[[StepRecord], None]
    setup_workspace: Callable[[Branch], Optional[str]]
    apply_patch: Callable[..., Any]
    verify_candidate: Callable[[CandidateWorkspace], CandidateWorkspace]
    reject_candidate: Callable[[CandidateWorkspace], None]
    finalize_research_rejection: Callable[..., Any]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        EvaluationExecutionResult,
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    reserve_proposal_attempt: Callable[[], None] = lambda: None
    proposal_attempt_scope: Callable[[int], AbstractContextManager[None]] = (
        _no_op_attempt_scope
    )
    record_hypothesis_exported: Callable[[], None] = _no_op_event
    record_patch_completed: Callable[[], None] = _no_op_event
    record_code_candidate_ready: Callable[[], None] = _no_op_event
    update_status_progress: Callable[[dict[str, Any] | None], None] = lambda _payload: (
        None
    )
    step_history: Sequence[StepRecord] = ()

    def run(self, branch: Branch) -> StepResult:
        """Run the full EXPLORE/EXPLORE_EXPAND branch step."""
        rnum = self.increment_round()
        branch.screening_expand_count = 0
        branch.validation_expand_count = 0

        self._emit_status_progress(
            branch,
            phase="proposal_hypothesis",
            round_num=rnum,
        )
        self.reserve_proposal_attempt()
        with self.proposal_attempt_scope(rnum):
            return self._run_reserved_attempt(branch, rnum)

    def _run_reserved_attempt(self, branch: Branch, rnum: int) -> StepResult:
        """Run one admitted H/C attempt inside its single telemetry scope."""

        bid = branch.branch_id
        h_contract_diagnostics: tuple[dict[str, Any], ...] = ()
        hypothesis_attempt = self.generate_hypothesis(branch)
        hypothesis = hypothesis_attempt.proposal
        if hypothesis is None:
            proposal_outcome = hypothesis_attempt.execution_outcome
            if proposal_outcome is None:
                raise RuntimeError(
                    "hypothesis attempt missing proposal and execution outcome"
                )
            failure_detail = proposal_outcome.detail or "hypothesis generation failed"
            self._record_execution_outcome(
                branch,
                proposal_outcome,
                event_kind="proposal_execution_outcome",
            )
            durable_outcome = ExecutionOutcomeRecord(
                outcome=proposal_outcome.outcome,
                reason_code=proposal_outcome.reason_code,
                provenance={"stage": "proposal_hypothesis"},
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=None,
                    patch=None,
                    contract_passed=None,
                    verification_passed=None,
                    protocol_result=None,
                    decision=None,
                    failure_stage="proposal_hypothesis",
                    failure_detail=durable_outcome.reason_code,
                    execution_outcome=durable_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=failure_detail,
                    failure_stage="proposal_hypothesis",
                    failure_detail=failure_detail,
                    failure_category=proposal_outcome.outcome.value,
                    execution_outcome=proposal_outcome,
                )
            )
        self.record_hypothesis_exported()
        logger.info(
            "Branch %s R1 hypothesis: locus=%s action=%s target=%s text='%s'",
            bid,
            hypothesis.change_locus,
            hypothesis.action,
            hypothesis.target_file,
            hypothesis.hypothesis_text or "",
        )

        self._emit_status_progress(
            branch,
            phase="hypothesis_contract",
            round_num=rnum,
            hypothesis=hypothesis,
        )
        c_result = self._validate_hypothesis(branch, hypothesis)
        h_contract_diagnostics = diagnostic_checks(c_result)
        if not c_result.passed:
            logger.info(
                "Branch %s: hypothesis contract failed: %s",
                bid,
                c_result.failure_reason,
            )
            failure_stage = "hypothesis_contract"
            failure_detail = c_result.failure_reason
            contract_outcome = self._record_contract_failure(
                c_result,
                stage=failure_stage,
            )
            self.finalize_research_rejection(
                branch=branch,
                rejection_phase=failure_stage,
                outcome=contract_outcome,
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
                    contract_diagnostics=h_contract_diagnostics,
                    execution_outcome=contract_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="hypothesis contract rejected",
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                    execution_outcome=contract_outcome,
                )
            )

        self._emit_status_progress(
            branch,
            phase="proposal_code",
            round_num=rnum,
            hypothesis=hypothesis,
        )
        code_attempt = self.generate_code(
            branch,
            hypothesis,
        )
        patch = code_attempt.proposal
        if patch is not None:
            self.record_patch_completed()
            logger.info(
                "Branch %s R2 code: file=%s action=%s code_len=%d",
                bid,
                patch.file_path,
                patch.action,
                len(patch.code_content or ""),
            )

        if patch is None:
            proposal_outcome = code_attempt.execution_outcome
            if proposal_outcome is None:
                raise RuntimeError(
                    "code attempt missing proposal and execution outcome"
                )
            detailed_failure = proposal_outcome.detail or "code generation failed"
            if proposal_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED:
                self.finalize_research_rejection(
                    branch=branch,
                    rejection_phase="proposal_code",
                    outcome=proposal_outcome,
                )
            else:
                self._record_execution_outcome(
                    branch,
                    proposal_outcome,
                    event_kind="proposal_execution_outcome",
                )
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
                    failure_stage="proposal_code",
                    failure_detail=detailed_failure,
                    execution_outcome=proposal_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=detailed_failure or proposal_outcome.reason_code,
                    failure_stage="proposal_code",
                    failure_detail=detailed_failure,
                    failure_category=proposal_outcome.outcome.value,
                    execution_outcome=proposal_outcome,
                )
            )

        self._emit_status_progress(
            branch,
            phase="patch_contract",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
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
            contract_outcome = self._record_contract_failure(
                p_result,
                stage="patch_contract",
                patch=patch,
            )
            self.finalize_research_rejection(
                branch=branch,
                rejection_phase="patch_contract",
                outcome=contract_outcome,
                patch=patch,
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
                    failure_stage="patch_contract",
                    failure_detail=p_result.failure_reason,
                    contract_diagnostics=(
                        *h_contract_diagnostics,
                        *diagnostic_checks(p_result),
                    ),
                    execution_outcome=contract_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="patch contract rejected",
                    failure_stage="patch_contract",
                    failure_detail=p_result.failure_reason,
                    failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                    execution_outcome=contract_outcome,
                )
            )

        self._emit_status_progress(
            branch,
            phase="workspace_setup",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        workspace = self.setup_workspace(branch)
        if workspace is None:
            workspace_outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="WORKSPACE_SETUP_FAILED",
                detail="workspace setup failed",
                provenance={"stage": "workspace_setup"},
            )
            self._record_execution_outcome(
                branch,
                workspace_outcome,
                event_kind="workspace_execution_outcome",
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
                    execution_outcome=workspace_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="workspace setup failed",
                    failure_stage="workspace",
                    failure_detail="workspace setup failed",
                    failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
                    execution_outcome=workspace_outcome,
                )
            )

        candidate_parent_scope = (
            "retained_branch_head"
            if self.branch_controller.get_code_base(bid) == "branch_workspace"
            else "declared_champion"
        )
        try:
            self._emit_status_progress(
                branch,
                phase="apply_patch",
                round_num=rnum,
                hypothesis=hypothesis,
                patch=patch,
            )
            candidate = self.apply_patch(
                workspace,
                patch,
                hypothesis=hypothesis,
                sync_registry=True,
            )
            workspace = candidate.workspace
            self.record_code_candidate_ready()
        except Exception as exc:
            logger.warning("Branch %s: apply_patch failed: %s", bid, exc)
            failure_detail = f"apply_patch: {exc}"
            workspace_outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="PATCH_MATERIALIZATION_FAILED",
                detail=failure_detail,
                provenance={
                    "stage": "patch_materialization",
                    "error_type": type(exc).__name__,
                },
            )
            self._record_execution_outcome(
                branch,
                workspace_outcome,
                event_kind="workspace_execution_outcome",
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
                    failure_detail=failure_detail,
                    execution_outcome=workspace_outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="apply_patch failed",
                    failure_stage="workspace",
                    failure_detail=failure_detail,
                    failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
                    execution_outcome=workspace_outcome,
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
        )
        try:
            vresult = run_verification_gate(
                self.verification_gate,
                workspace,
                champ_ws,
                patch,
                hypothesis=hypothesis,
            )
        except Exception:
            self._discard_candidate_after_exception(branch, candidate)
            raise
        if not vresult.passed:
            return self._finish_status_progress(
                self._handle_verification_failure(
                    branch=branch,
                    rnum=rnum,
                    patch=patch,
                    hypothesis=hypothesis,
                    vresult=vresult,
                    candidate=candidate,
                )
            )

        try:
            candidate = self.verify_candidate(candidate)
        except Exception as exc:
            try:
                self.reject_candidate(candidate)
            except Exception:
                logger.exception("Branch %s: failed to discard invalid candidate", bid)
            outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="CANDIDATE_VERIFICATION_FAILED",
                detail=str(exc),
                provenance={
                    "stage": "candidate_verification",
                    "exception_type": type(exc).__name__,
                },
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="workspace_execution_outcome",
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=True,
                    protocol_result=None,
                    decision=None,
                    failure_stage="workspace",
                    failure_detail=str(exc),
                    execution_outcome=outcome,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=str(exc),
                    failure_stage="workspace",
                    failure_detail=str(exc),
                    failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
                    execution_outcome=outcome,
                )
            )
        workspace = candidate.workspace

        # Keep the verified candidate in staging until Protocol produces a
        # typed Decision. Verification establishes evaluability; it does not
        # yet make the candidate the branch's clean source.
        branch.hypothesis = hypothesis

        fresh = self.branch_controller.get_branch(bid)
        if fresh and fresh.state in (
            BranchState.STALE,
            BranchState.STALE_WEIGHT_UPDATE,
        ):
            # The candidate has not reached Protocol. Discard its staging tree
            # and close this attempt as not evaluated.
            self.reject_candidate(candidate)
            branch.hypothesis = None
            self.branch_patches.pop(bid, None)
            self.branch_controller.reconcile_stale(
                bid,
                success=False,
                new_champion=self.get_champion(),
            )
            logger.info(
                "Branch %s: marked stale by async weight-opt during explore - closed",
                bid,
            )
            stale_outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="BRANCH_STALE_DURING_EXPLORE",
                detail="stale_during_explore",
                provenance={"stage": "verification"},
            )
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=stale_outcome,
                event_kind="explore_not_evaluated_outcome",
            )
            return self._finish_status_progress(
                StepResult(
                    action="skip",
                    branch_id=bid,
                    reason="stale_during_explore",
                    verification_passed=True,
                    execution_outcome=stale_outcome,
                )
            )

        self.branch_controller.next_stage(bid)
        self._emit_status_progress(
            branch,
            phase="evaluation_dispatch",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        try:
            evaluation = self.evaluate(
                branch,
                workspace,
                hypothesis,
            )
        except BaseException:
            self._discard_candidate_after_exception(branch, candidate)
            raise
        if not isinstance(evaluation, EvaluationExecutionResult):
            raise TypeError("evaluate callback must return EvaluationExecutionResult")
        decision = evaluation.decision
        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        execution_outcome = evaluation.execution_outcome
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            self.reject_candidate(candidate)
            self._record_execution_outcome(
                branch,
                execution_outcome,
                event_kind="explore_evaluation_outcome",
            )
            result = StepResult(
                action="explore",
                branch_id=bid,
                reason=execution_outcome.detail or execution_outcome.reason_code,
                failure_stage="evaluation",
                failure_detail=(
                    execution_outcome.detail or execution_outcome.reason_code
                ),
                verification_passed=True,
                canary_result=canary_result,
                execution_outcome=execution_outcome,
            )
            provenance = _evaluation_reason_provenance(evaluation)
            for key, value in provenance.items():
                setattr(result, key, value)
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=self.branch_patches.get(bid, patch),
                    contract_passed=True,
                    verification_passed=True,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation",
                    failure_detail=(
                        execution_outcome.detail or execution_outcome.reason_code
                    ),
                    contract_diagnostics=(
                        *h_contract_diagnostics,
                        *diagnostic_checks(p_result),
                    ),
                    decision_reason_codes=None,
                    **provenance,
                    canary_result=canary_result,
                    execution_outcome=execution_outcome,
                )
            )
            return self._finish_status_progress(result)
        if decision is None:
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label="explore",
            decision_reason_codes=evaluation.decision_reason_codes,
            patch=patch,
            candidate=candidate,
        )
        result.verification_passed = True
        if result.execution_outcome is None:
            result.protocol_result = protocol_result
            result.canary_result = canary_result
            result.execution_outcome = execution_outcome
        failure_stage, failure_detail = (
            (result.failure_stage, result.failure_detail)
            if result.execution_outcome.outcome is not ExecutionOutcome.EVALUATED
            else _evaluation_failure_detail(
                result.protocol_result,
                canary_result=result.canary_result,
            )
        )
        provenance = _evaluation_reason_provenance(evaluation)
        for key, value in provenance.items():
            setattr(result, key, value)
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
                protocol_result=result.protocol_result,
                decision=result.decision,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                contract_diagnostics=(
                    *h_contract_diagnostics,
                    *diagnostic_checks(p_result),
                ),
                decision_reason_codes=(
                    evaluation.decision_reason_codes
                    if result.decision is not None
                    else None
                ),
                **provenance,
                canary_result=result.canary_result,
                candidate_parent_scope=candidate_parent_scope,
                execution_outcome=result.execution_outcome,
            )
        )
        return self._finish_status_progress(result)

    def _discard_candidate_after_exception(
        self,
        branch: Branch,
        candidate: CandidateWorkspace,
    ) -> None:
        """Discard isolated staging without masking the triggering exception."""

        try:
            self.reject_candidate(candidate)
        except Exception:
            logger.exception(
                "Branch %s: candidate cleanup failed after exception",
                branch.branch_id,
            )

    def _record_execution_outcome(
        self,
        branch: Branch,
        record: ExecutionOutcomeRecord,
        *,
        event_kind: str,
    ) -> str | None:
        event_id = record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=record,
            event_kind=event_kind,
        )
        block_branch_after_execution(branch, record)
        return event_id

    def _emit_status_progress(
        self,
        branch: Branch,
        *,
        phase: str,
        round_num: int,
        hypothesis: HypothesisProposal | None = None,
        patch: PatchProposal | None = None,
    ) -> None:
        """Best-effort heartbeat for long pre-protocol steps."""
        payload: dict[str, Any] = {
            "branch_id": branch.branch_id,
            "stage": "proposal",
            "phase": phase,
            "round_num": round_num,
            "base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "step_started_at": datetime.now().isoformat(),
            "complete": False,
        }
        if hypothesis is not None:
            payload.update(
                {
                    "target_file": hypothesis.target_file,
                    "hypothesis_action": hypothesis.action,
                    "hypothesis_text": hypothesis.hypothesis_text,
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
        if canary_result is not None and not canary_result.passed:
            canary_reason_codes = tuple(canary_result.reason_codes or ())
            return (
                "canary",
                canary_reason_codes[0] if canary_reason_codes else "CANARY_FAILED",
            )
        return None, None
    reason_codes = {
        str(code).lower() for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" not in reason_codes:
        return None, None
    detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
    return "evaluation", detail


def _evaluation_reason_provenance(
    evaluation: EvaluationExecutionResult,
) -> dict[str, tuple[str, ...]]:
    return {
        "decision_engine_reason_codes": evaluation.decision_engine_reason_codes,
        "diagnostic_reason_codes": evaluation.diagnostic_reason_codes,
        "bypass_reason_codes": evaluation.bypass_reason_codes,
    }
