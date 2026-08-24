"""Decision finalization boundary for campaign branch steps."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
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
    ContractResult,
    Decision,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.step_result import StepResult
from scion.core.workspace_service import CandidateWorkspace

logger = logging.getLogger(__name__)


class LineageRecorder(Protocol):
    def __call__(
        self,
        branch: Branch,
        code_hash: str,
        hypothesis: HypothesisProposal,
        patch: Optional[PatchProposal],
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        canary_result: CanaryResult,
        protocol_result: Optional[ProtocolResult],
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]] = None,
        strict: bool = False,
    ) -> None: ...


@dataclass
class DecisionFinalizer:
    """Apply deterministic decision side effects after feature extraction."""

    branch_controller: BranchController
    branch_patches: MutableMapping[str, PatchProposal]
    require_promotable_branch: Callable[[Branch], None]
    promote_branch: Callable[[Branch], None]
    record_step_lineage: LineageRecorder
    discard_branch_workspace: Callable[[str], None]
    accept_candidate: Callable[[Branch, CandidateWorkspace], str] | None = None
    reject_candidate: Callable[[CandidateWorkspace], Any] | None = None
    registry: Any = None
    campaign_id: str = ""

    def apply(
        self,
        *,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]] = None,
        patch: PatchProposal | None = None,
        candidate: CandidateWorkspace | None = None,
        reanchor_champion: ChampionState | None = None,
    ) -> StepResult:
        bid = branch.branch_id
        logger.info("Branch %s: decision=%s", bid, decision.value)
        effective_reason_codes = decision_reason_codes or (
            tuple(protocol_result.reason_codes) if protocol_result else None
        )
        candidate_values = (patch, candidate)
        has_candidate = all(value is not None for value in candidate_values)
        if any(value is not None for value in candidate_values) and not has_candidate:
            raise ValueError("candidate finalization requires patch and workspace")
        canary_abandonment = (
            decision is Decision.ABANDON and not canary_result.passed
        )
        if protocol_result is None and not canary_abandonment:
            raise ValueError(
                "Decision without Protocol requires failed-canary ABANDON"
            )
        if decision is not Decision.PROMOTE and has_candidate:
            if protocol_result is not None or canary_abandonment:
                assert patch is not None
                assert candidate is not None
                return self._apply_nonpromotion(
                    branch=branch,
                    decision=decision,
                    hypothesis=hypothesis,
                    protocol_result=protocol_result,
                    canary_result=canary_result,
                    contract_result=contract_result,
                    verification_result=verification_result,
                    action_label=action_label,
                    decision_reason_codes=effective_reason_codes,
                    patch=patch,
                    candidate=candidate,
                    reanchor_champion=reanchor_champion,
                )
            raise ValueError(
                "candidate Decision without Protocol requires failed-canary ABANDON"
            )
        if decision == Decision.PROMOTE:
            _consume_completed_protocol_expansion(branch, protocol_result)
            return self._promote(
                branch=branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision_reason_codes=effective_reason_codes,
            )
        return self._apply_without_candidate(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
            decision_reason_codes=effective_reason_codes,
            patch=patch,
        )

    def _apply_without_candidate(
        self,
        *,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]],
        patch: PatchProposal | None,
    ) -> StepResult:
        """Apply an evaluation-only Decision before its sole scientific event."""

        bid = branch.branch_id
        _consume_completed_protocol_expansion(branch, protocol_result)
        if decision is Decision.ABANDON:
            _mark_branch_abandoned(
                branch,
                decision_reason_codes=decision_reason_codes,
            )
        elif decision is not Decision.CONTINUE_EXPLORE:
            _set_branch_direction(
                branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
            )

        _apply_decision_transition(self.branch_controller, branch, decision)

        if decision is Decision.CONTINUE_EXPLORE:
            branch.hypothesis = None
            branch.direction = None
        elif decision is Decision.ABANDON:
            self.discard_branch_workspace(bid)
            branch.hypothesis = None
            self.branch_patches.pop(bid, None)
        else:
            branch.hypothesis = hypothesis

        try:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
                patch=patch,
                code_hash=branch.current_code_hash or "",
                strict=True,
            )
        except Exception as exc:
            return self._scientific_event_failure(
                branch=branch,
                action_label=action_label,
                error=exc,
            )

        reason_codes = tuple(decision_reason_codes or ())
        reason = f"decision={decision.value}"
        if reason_codes:
            reason = f"{reason}; reasons={','.join(reason_codes)}"
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=reason,
            protocol_result=protocol_result,
        )

    def _apply_nonpromotion(
        self,
        *,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]],
        patch: PatchProposal,
        candidate: CandidateWorkspace,
        reanchor_champion: ChampionState | None,
    ) -> StepResult:
        """Apply one completed Protocol decision directly and synchronously.

        Candidate disposition and the ordinary Branch update happen before the
        single scientific event.  A failed event write becomes a typed infra
        terminal; it never leaves an event that claims an unapplied Decision.
        """
        bid = branch.branch_id
        accepted_candidate = self._apply_candidate_decision(
            branch=branch,
            decision=decision,
            patch=patch,
            candidate=candidate,
        )
        if reanchor_champion is not None and decision is not Decision.ABANDON:
            branch.state = BranchState.EXPLORE
            branch.base_champion_id = reanchor_champion.version
            branch.weight_revision = reanchor_champion.weight_revision
        _consume_completed_protocol_expansion(branch, protocol_result)
        if decision is Decision.ABANDON:
            _mark_branch_abandoned(
                branch,
                decision_reason_codes=decision_reason_codes,
            )
        elif decision is not Decision.CONTINUE_EXPLORE:
            _set_branch_direction(
                branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
            )

        _apply_decision_transition(self.branch_controller, branch, decision)

        if accepted_candidate and branch.direction is None:
            branch.direction = (
                f"{hypothesis.change_locus}: {hypothesis.hypothesis_text or ''}"
            )
        branch.hypothesis = (
            hypothesis
            if decision is not Decision.CONTINUE_EXPLORE and accepted_candidate
            else None
        )

        if not accepted_candidate:
            self.discard_branch_workspace(bid)

        if decision == Decision.ABANDON:
            self.branch_patches.pop(bid, None)

        try:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
                patch=patch,
                code_hash=candidate.source_digest,
                strict=True,
            )
        except Exception as exc:
            return self._scientific_event_failure(
                branch=branch,
                action_label=action_label,
                error=exc,
            )
        reason_codes = tuple(decision_reason_codes or ())
        reason = f"decision={decision.value}"
        if reason_codes:
            reason = f"{reason}; reasons={','.join(reason_codes)}"
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=reason,
            protocol_result=protocol_result,
        )

    def _apply_candidate_decision(
        self,
        *,
        branch: Branch,
        decision: Decision,
        patch: PatchProposal,
        candidate: CandidateWorkspace,
    ) -> bool:
        if decision in {
            Decision.CONTINUE_EXPLORE,
            Decision.EXPAND_SCREENING,
            Decision.QUEUE_VALIDATE,
            Decision.EXPAND_VALIDATION,
            Decision.QUEUE_FROZEN,
        }:
            if self.accept_candidate is None:
                raise RuntimeError("candidate acceptance callback is unavailable")
            self.accept_candidate(branch, candidate)
            self.branch_patches[branch.branch_id] = patch
            return True
        if decision is Decision.ABANDON:
            if self.reject_candidate is None:
                raise RuntimeError("candidate rejection callback is unavailable")
            self.reject_candidate(candidate)
            return False
        raise RuntimeError(
            f"unsupported nonpromotion candidate Decision: {decision.value}"
        )

    def _scientific_event_failure(
        self,
        *,
        branch: Branch,
        action_label: str,
        error: Exception,
    ) -> StepResult:
        """Fail closed when the sole completed-experiment event cannot persist."""

        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code="EXPERIMENT_EVENT_WRITE_FAILED",
            detail=str(error),
            provenance={
                "stage": "decision_event",
                "exception_type": type(error).__name__,
            },
        )
        logger.error(
            "Branch %s: completed experiment event could not be persisted: %s",
            branch.branch_id,
            error,
        )
        block_branch_after_execution(branch, record)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=branch.branch_id,
            decision=None,
            reason=f"decision_event_failed: {error}",
            failure_stage="decision_event",
            failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
            failure_detail=str(error),
            protocol_result=None,
            execution_outcome=record,
        )

    def _record_lineage(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        patch: PatchProposal | None = None,
        code_hash: str = "",
        strict: bool = False,
    ) -> None:
        self.record_step_lineage(
            branch,
            code_hash,
            hypothesis,
            patch if patch is not None else self.branch_patches.get(branch.branch_id),
            contract_result,
            verification_result,
            canary_result,
            protocol_result,
            decision,
            decision_reason_codes,
            strict=strict,
        )

    def _promote(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> StepResult:
        bid = branch.branch_id
        try:
            self.require_promotable_branch(branch)
        except StateTransitionError as exc:
            logger.error("Branch %s: promote precondition failed: %s", bid, exc)
            return self._promotion_failure(
                branch=branch,
                action_label=action_label,
                stage="promotion_precondition",
                reason_code="PROMOTION_PRECONDITION_FAILED",
                error=exc,
            )
        try:
            self.promote_branch(branch)
        except Exception as exc:
            logger.error("Branch %s: promotion failed: %s", bid, exc)
            return self._promotion_failure(
                branch=branch,
                action_label=action_label,
                stage="promotion",
                reason_code="PROMOTION_FAILED",
                error=exc,
            )
        try:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=Decision.PROMOTE,
                decision_reason_codes=decision_reason_codes,
                code_hash=branch.current_code_hash or "",
                strict=True,
            )
        except Exception as exc:
            return self._scientific_event_failure(
                branch=branch,
                action_label=action_label,
                error=exc,
            )
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=Decision.PROMOTE,
            reason="decision=promote",
            protocol_result=protocol_result,
        )

    def _promotion_failure(
        self,
        *,
        branch: Branch,
        action_label: str,
        stage: str,
        reason_code: str,
        error: Exception,
    ) -> StepResult:
        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code=reason_code,
            detail=str(error),
            provenance={
                "stage": stage,
                "exception_type": type(error).__name__,
            },
        )
        record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=record,
            event_kind="promotion_execution_outcome",
        )
        block_branch_after_execution(branch, record)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=branch.branch_id,
            decision=None,
            reason=f"{stage}_failed: {error}",
            failure_stage=stage,
            failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
            failure_detail=str(error),
            protocol_result=None,
            execution_outcome=record,
        )


def _apply_decision_transition(
    controller: BranchController,
    branch: Branch,
    decision: Decision,
) -> None:
    if decision is Decision.CONTINUE_EXPLORE and branch.state in (
        BranchState.EXPLORE,
        BranchState.STALE_WEIGHT_UPDATE,
    ):
        return
    controller.apply_decision(branch.branch_id, decision)


def _consume_completed_protocol_expansion(
    branch: Branch,
    protocol_result: ProtocolResult | None,
) -> None:
    """Consume an expansion round only in the completed decision target."""

    if protocol_result is None:
        return
    if branch.state is BranchState.EXPLORE_EXPAND:
        branch.screening_expand_count += 1
    elif branch.state is BranchState.VALIDATING_EXPAND:
        branch.validation_expand_count += 1


def _mark_branch_abandoned(
    branch: Branch,
    *,
    decision_reason_codes: Iterable[str] | None,
) -> None:
    """Keep the ordinary terminal state and reason on the branch."""

    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (decision_reason_codes or ())
            if str(code).strip()
        )
    )
    if reason_codes:
        branch.failure_codes = list(
            dict.fromkeys(
                [
                    *list(getattr(branch, "failure_codes", None) or ()),
                    *reason_codes,
                ]
            )
        )


def _set_branch_direction(
    branch: Branch,
    *,
    hypothesis: HypothesisProposal,
    protocol_result: Optional[ProtocolResult],
) -> None:
    """Label an evaluated branch with its ordinary research direction."""

    if protocol_result is None or getattr(protocol_result, "stats", None) is None:
        return
    if branch.direction is None:
        branch.direction = (
            f"{hypothesis.change_locus}: {hypothesis.hypothesis_text or ''}"
        )
