"""Decision finalization boundary for campaign branch steps."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import Callable, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.branch_lifecycle_policy import (
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_WEAK_SIGNAL_CONTINUE,
    SCREENING_ZERO_WIN_STREAK_CONTINUE,
)
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
from scion.core.telemetry_validation import (
    TELEMETRY_VALIDATION_REPAIRABLE,
    screened_experiment_effective,
)

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
            if action_label == "reconcile":
                self._abandon(branch=branch, h_record=h_record)
                try:
                    self.branch_controller.apply_decision(bid, Decision.ABANDON)
                except StateTransitionError as exc:
                    logger.error(
                        "Branch %s: reconcile abandon failed: %s",
                        bid,
                        exc,
                    )
                self._persist_current_branch(bid)
                return StepResult(
                    action="reconcile",
                    branch_id=bid,
                    decision=Decision.ABANDON,
                    reason="reconcile screening failed",
                )
            return self._continue_explore(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                verification_result=verification_result,
                action_label=action_label,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
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
                primary_reason = (
                    effective_reason_codes[0]
                    if effective_reason_codes
                    else "soft_lifecycle"
                )
                return StepResult(
                    action="soft_abandon",
                    branch_id=bid,
                    decision=decision,
                    reason=f"soft_abandon: {primary_reason}",
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
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> StepResult:
        bid = branch.branch_id
        telemetry_repairable = TELEMETRY_VALIDATION_REPAIRABLE in set(
            decision_reason_codes or ()
        )
        verification_passed = verification_result.passed
        has_positive_signal = (
            protocol_result is not None
            and protocol_result.stats is not None
            and protocol_result.stats.win_rate > 0
        )
        preserve_low_signal_branch = _preserve_low_signal_screening_workspace(
            protocol_result,
            decision_reason_codes,
        )
        preserve_workspace = verification_passed and (
            has_positive_signal
            or telemetry_repairable
            or preserve_low_signal_branch
        )

        if not preserve_workspace:
            self.discard_branch_workspace(bid)
            self.branch_patches.pop(bid, None)

        if preserve_workspace and branch.direction is None:
            branch.direction = (
                f"{hypothesis.change_locus}: "
                f"{(hypothesis.hypothesis_text or '')[:100]}"
            )
            logger.debug("Branch %s: direction set to %r", bid, branch.direction)

        if has_positive_signal:
            self.branch_zero_win_streaks[bid] = 0
        elif telemetry_repairable:
            self.branch_zero_win_streaks.setdefault(bid, 0)
        else:
            streak = self.branch_zero_win_streaks.get(bid, 0) + 1
            self.branch_zero_win_streaks[bid] = streak

        if not telemetry_repairable:
            self.branch_hypotheses.pop(bid, None)
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        else:
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "code_failed")
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
        reason = (
            "TELEMETRY_VALIDATION_REPAIRABLE: repair declared mechanism telemetry "
            "on the same branch"
            if telemetry_repairable
            else (
                "CONTINUE_EXPLORE: weak screening signal; improve the same branch"
                if preserve_low_signal_branch
                else "CONTINUE_EXPLORE: re-propose next step"
            )
        )
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=reason,
            counts_toward_max_rounds=not telemetry_repairable,
            attempt_kind="telemetry_repairable" if telemetry_repairable else "screening",
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


def _preserve_low_signal_screening_workspace(
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Optional[tuple[str, ...]],
) -> bool:
    if protocol_result is None or not screened_experiment_effective(protocol_result):
        return False
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return False
    stats = protocol_result.stats
    if stats is None:
        return False
    if stats.median_delta is not None and stats.median_delta < 0:
        return False
    if stats.candidate_failed_pairs > 0:
        return False
    if stats.runtime_ratio_median is not None and stats.runtime_ratio_median > 1.10:
        return False
    if (
        stats.runtime_regression_rate is not None
        and stats.runtime_regression_rate >= 0.90
    ):
        return False
    lifecycle_codes = {
        SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        SCREENING_WEAK_SIGNAL_CONTINUE,
        SCREENING_ZERO_WIN_STREAK_CONTINUE,
    }
    reason_set = set(decision_reason_codes or ())
    if lifecycle_codes & reason_set:
        return True
    return bool(stats.win_rate > 0 or stats.losses == 0)
