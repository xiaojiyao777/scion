"""Decision finalization boundary for campaign branch steps."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    block_branch_after_execution,
    disposition_failure_record,
    record_execution_outcome_event,
)
from scion.core.models import (
    AcceptedBranchChange,
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
    branch_base_source_ref,
    branch_changed_files,
)
from scion.core.promotion_service import PromotionCommittedError
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
        *,
        base_champion_version: int,
        base_source_ref: str,
        changed_files: tuple[str, ...],
        strict: bool = False,
    ) -> None: ...


@dataclass(frozen=True)
class _LineageSource:
    base_champion_version: int
    base_source_ref: str
    changed_files: tuple[str, ...]


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
        lineage_source = _lineage_source_before_decision(
            branch,
            patch=patch,
            candidate=candidate,
            reanchor_champion=reanchor_champion,
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
                    lineage_source=lineage_source,
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
                lineage_source=lineage_source,
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
            lineage_source=lineage_source,
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
        lineage_source: _LineageSource,
    ) -> StepResult:
        """Apply an evaluation-only Decision before its sole scientific event."""

        bid = branch.branch_id
        if decision is Decision.ABANDON:
            try:
                self.discard_branch_workspace(bid)
            except Exception as exc:
                return self._candidate_disposition_failure(
                    branch=branch,
                    action_label=action_label,
                    reason_code="BRANCH_WORKSPACE_DISCARD_FAILED",
                    operation="discard_branch_workspace",
                    error=exc,
                    protocol_result=protocol_result,
                    decision=decision,
                    decision_reason_codes=decision_reason_codes,
                )
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
            branch.hypothesis = hypothesis
        elif decision is Decision.ABANDON:
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
                lineage_source=lineage_source,
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

    def _promotion_event_failure(
        self,
        *,
        branch: Branch,
        action_label: str,
        error: Exception,
        protocol_result: ProtocolResult | None,
        canary_result: CanaryResult,
    ) -> StepResult:
        """Keep a committed promotion true when its lineage write fails."""

        return self._committed_promotion_failure(
            branch=branch,
            action_label=action_label,
            error=error,
            protocol_result=protocol_result,
            canary_result=canary_result,
            reason_code="PROMOTION_EVENT_WRITE_FAILED",
            stage="decision_event",
            operation="record_promotion_event",
        )

    def _committed_promotion_failure(
        self,
        *,
        branch: Branch,
        action_label: str,
        error: Exception,
        protocol_result: ProtocolResult | None,
        canary_result: CanaryResult,
        reason_code: str,
        stage: str,
        operation: str,
    ) -> StepResult:
        """Report post-commit infrastructure without reversing promotion."""

        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code=reason_code,
            detail=str(error),
            provenance={
                "stage": stage,
                "applied_decision": Decision.PROMOTE.value,
                "operation": operation,
                "exception_type": type(error).__name__,
                **(
                    {"champion_version": error.champion_version}
                    if isinstance(error, PromotionCommittedError)
                    else {}
                ),
            },
        )
        logger.error(
            "Branch %s: promotion committed but %s failed: %s",
            branch.branch_id,
            operation,
            error,
        )
        try:
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=branch.branch_id,
                record=record,
                event_kind="promotion_committed_execution_outcome",
                selected_hypothesis_research_basis=(
                    branch.selected_hypothesis_research_basis
                ),
            )
        except Exception:
            logger.exception(
                "Branch %s: committed-promotion outcome could not persist",
                branch.branch_id,
            )
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=branch.branch_id,
            decision=Decision.PROMOTE,
            reason=f"promotion_committed_infra_failed: {error}",
            failure_stage=stage,
            failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
            failure_detail=str(error),
            protocol_result=protocol_result,
            canary_result=canary_result,
            execution_outcome=record,
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
        lineage_source: _LineageSource,
    ) -> StepResult:
        """Apply one completed Protocol decision directly and synchronously.

        Candidate disposition and the ordinary Branch update happen before the
        single scientific event.  A failed event write becomes a typed infra
        terminal; it never leaves an event that claims an unapplied Decision.
        """
        bid = branch.branch_id
        effective_state = (
            BranchState.EXPLORE
            if reanchor_champion is not None and decision is not Decision.ABANDON
            else branch.state
        )
        try:
            if not (
                decision is Decision.CONTINUE_EXPLORE
                and effective_state
                in (BranchState.EXPLORE, BranchState.STALE_WEIGHT_UPDATE)
            ):
                self.branch_controller.require_decision_transition(
                    bid,
                    decision,
                    state=effective_state,
                )
        except StateTransitionError as exc:
            if self.reject_candidate is not None:
                try:
                    self.reject_candidate(candidate)
                except Exception as cleanup_exc:
                    return self._candidate_disposition_failure(
                        branch=branch,
                        action_label=action_label,
                        reason_code="CANDIDATE_REJECT_FAILED",
                        operation="reject_candidate_after_decision_precondition",
                        error=cleanup_exc,
                        protocol_result=protocol_result,
                        decision=decision,
                        decision_reason_codes=decision_reason_codes,
                    )
            return self._candidate_disposition_failure(
                branch=branch,
                action_label=action_label,
                reason_code="DECISION_TRANSITION_PRECONDITION_FAILED",
                operation="preflight_decision_transition",
                error=exc,
                protocol_result=protocol_result,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
            )
        try:
            accepted_candidate = self._apply_candidate_decision(
                branch=branch,
                decision=decision,
                hypothesis=hypothesis,
                patch=patch,
                candidate=candidate,
                append_accepted_change=reanchor_champion is None,
            )
        except Exception as exc:
            accepting = decision is not Decision.ABANDON
            return self._candidate_disposition_failure(
                branch=branch,
                action_label=action_label,
                reason_code=(
                    "CANDIDATE_ACCEPT_FAILED"
                    if accepting
                    else "CANDIDATE_REJECT_FAILED"
                ),
                operation="accept_candidate" if accepting else "reject_candidate",
                error=exc,
                protocol_result=protocol_result,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
            )
        if not accepted_candidate:
            try:
                self.discard_branch_workspace(bid)
            except Exception as exc:
                return self._candidate_disposition_failure(
                    branch=branch,
                    action_label=action_label,
                    reason_code="BRANCH_WORKSPACE_DISCARD_FAILED",
                    operation="discard_branch_workspace",
                    error=exc,
                    protocol_result=protocol_result,
                    decision=decision,
                    decision_reason_codes=decision_reason_codes,
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
        branch.hypothesis = hypothesis if accepted_candidate else None

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
                lineage_source=lineage_source,
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
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        candidate: CandidateWorkspace,
        append_accepted_change: bool,
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
            if append_accepted_change:
                branch.accepted_changes.append(
                    AcceptedBranchChange(
                        hypothesis=hypothesis,
                        patch=patch,
                        before_sources=candidate.before_sources,
                        changed_files=candidate.changed_files,
                        selected_hypothesis_research_basis=deepcopy(
                            branch.selected_hypothesis_research_basis
                        ),
                    )
                )
            return True
        if decision is Decision.ABANDON:
            if self.reject_candidate is None:
                raise RuntimeError("candidate rejection callback is unavailable")
            self.reject_candidate(candidate)
            return False
        raise RuntimeError(
            f"unsupported nonpromotion candidate Decision: {decision.value}"
        )

    def _candidate_disposition_failure(
        self,
        *,
        branch: Branch,
        action_label: str,
        reason_code: str,
        operation: str,
        error: Exception,
        protocol_result: ProtocolResult | None,
        decision: Decision,
        decision_reason_codes: tuple[str, ...] | None,
    ) -> StepResult:
        """Persist a typed terminal without claiming an unapplied Decision."""

        record = disposition_failure_record(
            reason_code=reason_code,
            error=error,
            operation=operation,
            completed_protocol=protocol_result,
            unapplied_decision=decision,
            decision_reason_codes=decision_reason_codes,
        )
        logger.error(
            "Branch %s: candidate disposition failed during %s: %s",
            branch.branch_id,
            operation,
            error,
        )
        try:
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=branch.branch_id,
                record=record,
                event_kind="candidate_disposition_execution_outcome",
                selected_hypothesis_research_basis=(
                    branch.selected_hypothesis_research_basis
                ),
            )
        except Exception:
            logger.exception(
                "Branch %s: candidate disposition outcome could not persist",
                branch.branch_id,
            )
        block_branch_after_execution(branch, record)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=branch.branch_id,
            decision=None,
            reason=f"candidate_disposition_failed: {error}",
            failure_stage="candidate_disposition",
            failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
            failure_detail=str(error),
            protocol_result=None,
            execution_outcome=record,
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
        lineage_source: _LineageSource,
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
            base_champion_version=lineage_source.base_champion_version,
            base_source_ref=lineage_source.base_source_ref,
            changed_files=lineage_source.changed_files,
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
        lineage_source: _LineageSource,
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
        except PromotionCommittedError as exc:
            logger.error(
                "Branch %s: promotion committed but bookkeeping failed: %s",
                bid,
                exc,
            )
            return self._committed_promotion_failure(
                branch=branch,
                action_label=action_label,
                error=exc,
                protocol_result=protocol_result,
                canary_result=canary_result,
                reason_code="PROMOTION_COMMITTED_BOOKKEEPING_FAILED",
                stage="promotion_post_commit",
                operation=exc.operation,
            )
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
                lineage_source=lineage_source,
                strict=True,
            )
        except Exception as exc:
            return self._promotion_event_failure(
                branch=branch,
                action_label=action_label,
                error=exc,
                protocol_result=protocol_result,
                canary_result=canary_result,
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
        try:
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=branch.branch_id,
                record=record,
                event_kind="promotion_execution_outcome",
                selected_hypothesis_research_basis=(
                    branch.selected_hypothesis_research_basis
                ),
            )
        except Exception:
            logger.exception(
                "Branch %s: promotion failure outcome could not persist",
                branch.branch_id,
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


def _lineage_source_before_decision(
    branch: Branch,
    *,
    patch: PatchProposal | None,
    candidate: CandidateWorkspace | None,
    reanchor_champion: ChampionState | None,
) -> _LineageSource:
    if reanchor_champion is not None:
        base_champion_version = reanchor_champion.version
        base_source_ref = f"champion:v{reanchor_champion.version}"
    else:
        base_champion_version = branch.base_champion_id
        base_source_ref = branch_base_source_ref(branch)
    if reanchor_champion is not None and candidate is not None:
        changed_files = candidate.changed_files
    else:
        changed_files = tuple(
            dict.fromkeys(
                (
                    *branch_changed_files(branch, patch),
                    *(candidate.changed_files if candidate is not None else ()),
                )
            )
        )
    return _LineageSource(
        base_champion_version=base_champion_version,
        base_source_ref=base_source_ref,
        changed_files=changed_files,
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
