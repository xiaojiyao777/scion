"""Decision finalization boundary for campaign branch steps."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import Callable, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    Decision,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.promotion_service import PromotionPlan
from scion.core.step_result import StepResult

logger = logging.getLogger(__name__)


class HypothesisStoreLike(Protocol):
    def mark_status(self, hypothesis_id: str, status: str) -> None:
        ...


class BranchStoreLike(Protocol):
    def save(self, branch: Branch) -> None:
        ...


LineageRecorder = Callable[
    [
        Branch,
        HypothesisProposal,
        Optional[PatchProposal],
        ContractResult,
        VerificationResult,
        CanaryResult,
        Optional[ProtocolResult],
        Decision,
        str,
        Optional[tuple[str, ...]],
        Optional[str],
    ],
    None,
]


@dataclass
class DecisionFinalizer:
    """Apply deterministic decision side effects after feature extraction."""

    branch_controller: BranchController
    branch_store: BranchStoreLike | None
    hypothesis_store: HypothesisStoreLike
    branch_workspaces: MutableMapping[str, str]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    branch_zero_win_streaks: MutableMapping[str, int]
    prepare_promoted_champion: Callable[[Branch], PromotionPlan]
    require_promotable_branch: Callable[[Branch], None]
    commit_promote_plan: Callable[[PromotionPlan], None]
    handle_failure: Callable[..., None]
    record_hard_abandon: Callable[[str, str], None]
    record_step_lineage: LineageRecorder
    decision_reason_codes_for: Callable[
        [str, Optional[ProtocolResult]],
        Optional[tuple[str, ...]],
    ]
    discard_branch_workspace: Callable[[str], None]
    archive_workspace: Callable[[str, str], None]
    cleanup_workspace: Callable[[str], None]
    persist_branch_state: Callable[[str], None]
    reset_recent_abandoned_count: Callable[[], None]

    def apply(
        self,
        *,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]] = None,
    ) -> StepResult:
        bid = branch.branch_id
        logger.info("Branch %s: decision=%s", bid, decision.value)
        effective_reason_codes = decision_reason_codes or self.decision_reason_codes_for(
            bid,
            protocol_result,
        )

        promote_plan: PromotionPlan | None = None
        if decision == Decision.PROMOTE:
            promote_plan = self._prepare_promotion(
                branch=branch,
                action_label=action_label,
            )
            if isinstance(promote_plan, StepResult):
                return promote_plan

        if decision != Decision.PROMOTE:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
            )

        if decision == Decision.CONTINUE_EXPLORE:
            return self._continue_explore(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                verification_result=verification_result,
                action_label=action_label,
                decision=decision,
            )

        if decision == Decision.PROMOTE:
            assert promote_plan is not None
            return self._promote(
                branch=branch,
                promote_plan=promote_plan,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision_reason_codes=effective_reason_codes,
            )

        if decision == Decision.ABANDON:
            updated_branch = self.branch_controller.get_branch(bid)
            if updated_branch and updated_branch.state == BranchState.ABANDONED:
                self.branch_patches.pop(bid, None)
                return StepResult(
                    action="soft_abandon",
                    branch_id=bid,
                    decision=decision,
                    reason="T4: win_rate < 0.3",
                )
            self._abandon(branch=branch, h_record=h_record)
        else:
            self.reset_recent_abandoned_count()

        try:
            self.branch_controller.apply_decision(bid, decision)
        except StateTransitionError as exc:
            logger.error(
                "Branch %s: apply_decision(%s) failed: %s",
                bid,
                decision.value,
                exc,
            )

        self._persist_current_branch(bid)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=f"decision={decision.value}",
        )

    def _prepare_promotion(
        self,
        *,
        branch: Branch,
        action_label: str,
    ) -> PromotionPlan | StepResult:
        bid = branch.branch_id
        try:
            self.require_promotable_branch(branch)
        except StateTransitionError as exc:
            logger.error("Branch %s: promote precondition failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_precondition: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_precondition_failed: {exc}",
            )
        try:
            return self.prepare_promoted_champion(branch)
        except Exception as exc:
            logger.error("Branch %s: promote prepare failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_prepare: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_prepare_failed: {exc}",
            )

    def _record_lineage(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        event_id: Optional[str] = None,
    ) -> None:
        self.record_step_lineage(
            branch,
            hypothesis,
            self.branch_patches.get(branch.branch_id),
            contract_result,
            verification_result,
            canary_result,
            protocol_result,
            decision,
            h_record.hypothesis_id,
            decision_reason_codes,
            event_id,
        )

    def _continue_explore(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        verification_result: VerificationResult,
        action_label: str,
        decision: Decision,
    ) -> StepResult:
        bid = branch.branch_id
        verification_passed = verification_result.passed
        has_positive_signal = (
            protocol_result is not None
            and protocol_result.stats is not None
            and protocol_result.stats.win_rate > 0
        )
        preserve_workspace = verification_passed and has_positive_signal

        if not preserve_workspace:
            self.discard_branch_workspace(bid)
            self.branch_patches.pop(bid, None)

        if has_positive_signal:
            self.branch_zero_win_streaks[bid] = 0
            if branch.direction is None:
                branch.direction = (
                    f"{hypothesis.change_locus}: "
                    f"{(hypothesis.hypothesis_text or '')[:100]}"
                )
                logger.debug("Branch %s: direction set to %r", bid, branch.direction)
        else:
            streak = self.branch_zero_win_streaks.get(bid, 0) + 1
            self.branch_zero_win_streaks[bid] = streak
            if streak >= 3 and branch.direction is not None:
                logger.debug(
                    "Branch %s: %d consecutive 0-win-rate rounds - clearing direction",
                    bid,
                    streak,
                )
                branch.direction = None

        self.branch_hypotheses.pop(bid, None)
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        if branch.state not in (BranchState.EXPLORE, BranchState.STALE_WEIGHT_UPDATE):
            try:
                self.branch_controller.apply_decision(bid, decision)
            except StateTransitionError as exc:
                logger.error(
                    "Branch %s: apply_decision(CONTINUE_EXPLORE) from %s failed: %s",
                    bid,
                    branch.state.value,
                    exc,
                )
        self.reset_recent_abandoned_count()
        self.persist_branch_state(bid)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason="CONTINUE_EXPLORE: re-propose next step",
        )

    def _promote(
        self,
        *,
        branch: Branch,
        promote_plan: PromotionPlan,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> StepResult:
        bid = branch.branch_id
        promotion_event_id = str(uuid.uuid4())
        promoted_champion = replace(
            promote_plan.champion,
            promotion_experiment_id=promotion_event_id,
        )
        promote_plan = replace(promote_plan, champion=promoted_champion)
        try:
            self.commit_promote_plan(promote_plan)
        except Exception as exc:
            logger.error("Branch %s: promote commit failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_commit: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_commit_failed: {exc}",
            )
        self._record_lineage(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=Decision.PROMOTE,
            decision_reason_codes=decision_reason_codes,
            event_id=promotion_event_id,
        )
        self.persist_branch_state(bid)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=Decision.PROMOTE,
            reason="decision=promote",
        )

    def _abandon(self, *, branch: Branch, h_record: HypothesisRecord) -> None:
        bid = branch.branch_id
        self.record_hard_abandon(bid, "decision_abandon")
        workspace = self.branch_workspaces.pop(bid, None)
        if workspace:
            try:
                self.archive_workspace(workspace, bid)
            except Exception as exc:
                logger.debug("Branch %s: archive failed: %s", bid, exc)
            try:
                self.cleanup_workspace(workspace)
            except Exception:
                pass
        self.branch_hypotheses.pop(bid, None)
        self.branch_patches.pop(bid, None)
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        self.branch_current_hypothesis.pop(bid, None)

    def _persist_current_branch(self, branch_id: str) -> None:
        try:
            branch = self.branch_controller.get_branch(branch_id)
            if branch:
                if self.branch_store is not None:
                    self.branch_store.save(branch)
        except Exception as exc:
            logger.debug("BranchStore.save (decision) failed: %s", exc)
