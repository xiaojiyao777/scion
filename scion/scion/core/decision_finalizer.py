"""Decision finalization boundary for campaign branch steps."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.branch_hygiene import (
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    WIRING_SUSPECT_REQUIRES_REPAIR,
)
from scion.core.branch_repair_policy import mechanism_ids_for_repair
from scion.core.branch_lifecycle_policy import (
    SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
    SCREENING_MARGINAL_SIGNAL_CONTINUE,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,
    SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
    SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    SCREENING_WEAK_SIGNAL_CONTINUE,
    SCREENING_ZERO_WIN_STREAK_CONTINUE,
)
from scion.core.decision_lifecycle_actions import (
    merge_branch_lifecycle_block as _merge_branch_lifecycle_block,
    park_lineage as _park_lineage,
    update_branch_screening_evidence_summary as _update_branch_screening_evidence_summary,
    update_branch_lifecycle_signal_state as _update_branch_lifecycle_signal_state,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    Decision,
    DecisionLifecycleAction,
    EvalStats,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.promotion_service import PromotionCommitError, PromotionPlan
from scion.core.step_result import StepResult
from scion.core.runtime_budget_diagnostics import runtime_budget_diagnostic_code
from scion.core.screening_visibility import runtime_aggregate_exclusion_for_protocol
from scion.core.telemetry_validation import (
    SCREENING_TELEMETRY_REPAIRABLE,
    TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,
    TELEMETRY_EFFECT_ZERO_OUTCOME,
    TELEMETRY_VALIDATION_REPAIRABLE,
    VALIDATION_TELEMETRY_REPAIRABLE,
    screened_experiment_effective,
)
from scion.proposal.screening_feedback import screening_feedback_summary

logger = logging.getLogger(__name__)


class HypothesisStoreLike(Protocol):
    def mark_status(self, hypothesis_id: str, status: str) -> None:
        ...


class BranchStoreLike(Protocol):
    def save(self, branch: Branch) -> None:
        ...


class LineageRecorder(Protocol):
    def __call__(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: Optional[PatchProposal],
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        protocol_result: Optional[ProtocolResult],
        decision: Decision,
        hypothesis_id: str = "",
        decision_reason_codes: Optional[tuple[str, ...]] = None,
        event_id: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        ...

FormalCandidateArtifactRecorder = Callable[..., Optional[str]]


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
    restore_branch_checkpoint: Callable[..., bool] | None = None
    capture_branch_checkpoint: Callable[[Branch], bool] | None = None
    record_formal_candidate_artifact: FormalCandidateArtifactRecorder | None = None
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}

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
        lifecycle_action: DecisionLifecycleAction = "",
        lifecycle_policy_evidence: dict[str, object] | None = None,
    ) -> StepResult:
        bid = branch.branch_id
        logger.info("Branch %s: decision=%s", bid, decision.value)
        effective_reason_codes = decision_reason_codes or self.decision_reason_codes_for(
            bid,
            protocol_result,
        )
        effective_lifecycle_action = _effective_lifecycle_action(
            lifecycle_action,
            effective_reason_codes,
        )
        patch = self.branch_patches.get(bid)
        if decision == Decision.ABANDON:
            _sync_terminal_branch_evidence(
                branch,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=effective_reason_codes,
                lifecycle_action=effective_lifecycle_action,
                lifecycle_policy_evidence=lifecycle_policy_evidence,
            )
            self._record_formal_candidate_artifact(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                patch=patch,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
            )

        promote_plan: PromotionPlan | None = None
        if decision == Decision.PROMOTE:
            promote_plan = self._prepare_promotion(
                branch=branch,
                action_label=action_label,
            )
            if isinstance(promote_plan, StepResult):
                return _with_protocol_accounting(promote_plan, protocol_result)

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

        if decision in (Decision.CONTINUE_EXPLORE, Decision.VALIDATION_REPAIR_REQUIRED):
            result = self._continue_explore(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
                lifecycle_action=effective_lifecycle_action,
                lifecycle_policy_evidence=lifecycle_policy_evidence,
            )
            return _with_protocol_accounting(result, protocol_result)

        if decision == Decision.PROMOTE:
            assert promote_plan is not None
            result = self._promote(
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
            return _with_protocol_accounting(result, protocol_result)

        counts_toward_hard_abandon = True
        if decision == Decision.ABANDON:
            updated_branch = self.branch_controller.get_branch(bid)
            if updated_branch and updated_branch.state == BranchState.ABANDONED:
                self.branch_patches.pop(bid, None)
                _record_abandon_accounting(
                    branch,
                    lifecycle_action=effective_lifecycle_action,
                    decision_reason_codes=effective_reason_codes,
                    counts_toward_hard_abandon=False,
                    accounting_kind="soft_lifecycle_archive",
                )
                _attach_lifecycle_policy_evidence(
                    branch,
                    lifecycle_policy_evidence,
                )
                self._persist_current_branch(bid)
                primary_reason = (
                    effective_reason_codes[0]
                    if effective_reason_codes
                    else "soft_lifecycle"
                )
                return _with_protocol_accounting(
                    StepResult(
                        action="soft_abandon",
                        branch_id=bid,
                        decision=decision,
                        reason=f"soft_abandon: {primary_reason}",
                        lifecycle_bookkeeping=_soft_lifecycle_bookkeeping(
                            lifecycle_action=effective_lifecycle_action,
                            decision_reason_codes=effective_reason_codes,
                        ),
                    ),
                    protocol_result,
                )
            counts_toward_hard_abandon = _counts_toward_hard_abandon(
                effective_lifecycle_action,
            )
            self._abandon(
                branch=branch,
                h_record=h_record,
                lifecycle_action=effective_lifecycle_action,
                decision_reason_codes=effective_reason_codes,
                counts_toward_hard_abandon=counts_toward_hard_abandon,
            )
            _attach_lifecycle_policy_evidence(branch, lifecycle_policy_evidence)
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

        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=patch,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=decision,
            decision_reason_codes=effective_reason_codes,
        )
        self._persist_current_branch(bid)
        if decision == Decision.ABANDON and not counts_toward_hard_abandon:
            primary_reason = (
                effective_reason_codes[0]
                if effective_reason_codes
                else effective_lifecycle_action
                or "soft_lifecycle"
            )
            return _with_protocol_accounting(
                StepResult(
                    action="soft_abandon",
                    branch_id=bid,
                    decision=decision,
                    reason=f"soft_abandon: {primary_reason}",
                    attempt_kind="screening",
                    lifecycle_bookkeeping=_soft_lifecycle_bookkeeping(
                        lifecycle_action=effective_lifecycle_action,
                        decision_reason_codes=effective_reason_codes,
                    ),
                ),
                protocol_result,
            )
        reason_suffix = (
            f"; reasons={','.join(effective_reason_codes)}"
            if effective_reason_codes
            else ""
        )
        return _with_protocol_accounting(
            StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason=f"decision={decision.value}{reason_suffix}",
            ),
            protocol_result,
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
        strict: bool = False,
    ) -> None:
        args = (
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
        if strict:
            self.record_step_lineage(*args, strict=True)
        else:
            self.record_step_lineage(*args)

    def _continue_explore(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        lifecycle_action: DecisionLifecycleAction,
        lifecycle_policy_evidence: dict[str, object] | None,
    ) -> StepResult:
        bid = branch.branch_id
        telemetry_repair_stage = _telemetry_repair_stage(
            protocol_result,
            decision_reason_codes,
        )
        telemetry_repairable = telemetry_repair_stage is not None
        telemetry_effect_zero = TELEMETRY_EFFECT_ZERO_DIAGNOSTIC in set(
            decision_reason_codes or ()
        )
        park_lineage = lifecycle_action == "park_lineage"
        rollback_to_checkpoint = lifecycle_action == "rollback_to_checkpoint"
        retain_checkpoint = lifecycle_action == "retain_checkpoint"
        positive_low_signal_continue = _positive_low_signal_continue(
            decision_reason_codes
        )
        verification_passed = verification_result.passed
        has_positive_signal = (
            protocol_result is not None
            and protocol_result.stats is not None
            and protocol_result.stats.win_rate > 0
            and (
                positive_low_signal_continue
                or not _screening_quality_regressed(protocol_result.stats)
            )
        )
        preserve_low_signal_branch = _preserve_low_signal_screening_workspace(
            protocol_result,
            decision_reason_codes,
        )
        if lifecycle_action != "retain_head":
            preserve_low_signal_branch = False
        regressed_followup = _is_regressed_weak_positive_followup(
            branch,
            protocol_result,
            decision_reason_codes,
        )
        screening_feedback = (
            screening_feedback_summary(
                protocol_result,
                decision_reason_codes=tuple(decision_reason_codes or ()),
            )
            if protocol_result is not None
            else None
        )
        if screening_feedback is not None and screening_feedback.case_total:
            _update_branch_screening_evidence_summary(
                branch,
                protocol_result=protocol_result,
                screening_feedback=screening_feedback,
                decision_reason_codes=decision_reason_codes,
            )
            _update_branch_lifecycle_signal_state(
                branch,
                protocol_result=protocol_result,
                screening_feedback=screening_feedback,
                telemetry_effect_zero=telemetry_effect_zero,
            )
            branch.last_screening_feedback_tier = screening_feedback.tier
        fresh_runtime_replay_required = _fresh_runtime_replay_required(
            branch,
            protocol_result=protocol_result,
            decision_reason_codes=decision_reason_codes,
        )
        if telemetry_repairable:
            repair_mechanism_ids = mechanism_ids_for_repair(hypothesis)
        restored_regressed_checkpoint = False
        if telemetry_repairable and (park_lineage or retain_checkpoint):
            _park_lineage(
                branch,
                reason_codes=tuple(decision_reason_codes or ()),
                checkpoint_retained=retain_checkpoint,
            )
            branch.telemetry_repair_mechanism_ids = ()
        elif telemetry_repairable:
            branch.branch_code_status = "telemetry_wiring_suspect"
            branch.last_telemetry_outcome = "activation_missing_or_wiring_suspect"
            branch.branch_mechanism_ids = _merge_mechanism_ids(
                getattr(branch, "branch_mechanism_ids", ()) or (),
                repair_mechanism_ids,
            )
            branch.telemetry_repair_mechanism_ids = repair_mechanism_ids
            attempts = dict(getattr(branch, "telemetry_repair_attempts", {}) or {})
            for mechanism_id in repair_mechanism_ids or ("unknown",):
                attempts[mechanism_id] = int(attempts.get(mechanism_id, 0)) + 1
            branch.telemetry_repair_attempts = attempts
        elif (
            (preserve_low_signal_branch or fresh_runtime_replay_required)
            and screening_feedback is not None
        ):
            branch.branch_code_status = f"active_{screening_feedback.tier}"
            branch.last_telemetry_outcome = (
                TELEMETRY_EFFECT_ZERO_OUTCOME
                if telemetry_effect_zero
                else screening_feedback.effect_status
            )
            branch.branch_mechanism_ids = _merge_mechanism_ids(
                getattr(branch, "branch_mechanism_ids", ()) or (),
                mechanism_ids_for_repair(hypothesis),
            )
            branch.telemetry_repair_mechanism_ids = ()
        elif not preserve_low_signal_branch:
            if (
                (rollback_to_checkpoint or regressed_followup)
                and self.restore_branch_checkpoint is not None
            ):
                restored_regressed_checkpoint = self._restore_checkpoint(
                    branch,
                    reason=(
                        "rollback_to_checkpoint"
                        if rollback_to_checkpoint
                        else "regressed_followup"
                    ),
                    reason_codes=tuple(decision_reason_codes or ()),
                    lifecycle_policy_evidence=lifecycle_policy_evidence,
                )
            if regressed_followup and not restored_regressed_checkpoint:
                branch.branch_code_status = "regressed_followup"
                branch.current_code_hash = branch.last_clean_code_hash
                branch.last_screening_feedback_tier = "quality_regression"
                branch.last_telemetry_outcome = "regressed_followup"
            elif park_lineage or retain_checkpoint:
                _park_lineage(
                    branch,
                    reason_codes=tuple(decision_reason_codes or ()),
                    checkpoint_retained=retain_checkpoint,
                )
            elif not regressed_followup:
                branch.branch_code_status = "discarded"
            branch.branch_mechanism_ids = _merge_mechanism_ids(
                getattr(branch, "branch_mechanism_ids", ()) or (),
                mechanism_ids_for_repair(hypothesis),
            )
            branch.telemetry_repair_mechanism_ids = ()
        preserve_workspace = verification_passed and (
            preserve_low_signal_branch
            or restored_regressed_checkpoint
            or fresh_runtime_replay_required
        )

        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=self.branch_patches.get(bid),
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=decision,
            decision_reason_codes=decision_reason_codes,
        )

        if not preserve_workspace:
            if park_lineage or retain_checkpoint:
                self._discard_current_workspace_preserve_checkpoints(bid)
            else:
                self.discard_branch_workspace(bid)
            self.branch_patches.pop(bid, None)

        if preserve_workspace and branch.direction is None:
            branch.direction = (
                f"{hypothesis.change_locus}: "
                f"{(hypothesis.hypothesis_text or '')[:100]}"
            )
            logger.debug("Branch %s: direction set to %r", bid, branch.direction)
        if preserve_workspace and self.capture_branch_checkpoint is not None:
            try:
                self.capture_branch_checkpoint(branch)
            except Exception as exc:  # pragma: no cover - checkpoint audit best effort
                logger.debug(
                    "Branch %s: retained checkpoint capture failed: %s",
                    bid,
                    exc,
                )

        if has_positive_signal:
            self.branch_zero_win_streaks[bid] = 0
        elif telemetry_repairable:
            self.branch_zero_win_streaks.setdefault(bid, 0)
        else:
            streak = self.branch_zero_win_streaks.get(bid, 0) + 1
            self.branch_zero_win_streaks[bid] = streak

        if not telemetry_repairable:
            if not fresh_runtime_replay_required:
                self.branch_hypotheses.pop(bid, None)
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                (
                    "screening_fresh_runtime_replay_pending"
                    if fresh_runtime_replay_required
                    else _retained_screening_status(
                        preserve_low_signal_branch=preserve_low_signal_branch,
                        tier=(
                            screening_feedback.tier
                            if screening_feedback is not None
                            else ""
                        ),
                    )
                ),
            )
        else:
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                (
                    "validation_telemetry_failed"
                    if telemetry_repair_stage == "validation"
                    else "screening_telemetry_failed"
                ),
            )
        if branch.state not in (
            BranchState.EXPLORE,
            BranchState.STALE_WEIGHT_UPDATE,
            BranchState.PARKED_LINEAGE,
        ):
            try:
                self.branch_controller.apply_decision(bid, decision)
            except StateTransitionError as exc:
                logger.error(
                    "Branch %s: apply_decision(%s) from %s failed: %s",
                    bid,
                    decision.value,
                    branch.state.value,
                    exc,
                )
        self.reset_recent_abandoned_count()
        self.persist_branch_state(bid)
        if telemetry_repairable:
            if park_lineage or retain_checkpoint:
                reason = (
                    "CONTINUE_EXPLORE: "
                    f"{'retain_checkpoint' if retain_checkpoint else 'park_lineage'}; "
                    "telemetry diagnostic budget exhausted without archiving "
                    "the lineage"
                )
                attempt_kind = "branch_lifecycle_policy"
            else:
                reason_code = (
                    VALIDATION_TELEMETRY_REPAIRABLE
                    if telemetry_repair_stage == "validation"
                    else TELEMETRY_VALIDATION_REPAIRABLE
                )
                reason = (
                    f"{reason_code}: repair declared mechanism telemetry on the "
                    f"same branch; repair_focus={WIRING_SUSPECT_REQUIRES_REPAIR}; "
                    f"repair_policy={REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK}; "
                    f"repair_mechanism_ids={','.join(repair_mechanism_ids) or 'unknown'}; "
                    f"branch_code_status={branch.branch_code_status}; "
                    f"telemetry_outcome={branch.last_telemetry_outcome}"
                )
                attempt_kind = (
                    "validation_repair_required"
                    if telemetry_repair_stage == "validation"
                    else "telemetry_repairable"
                )
        else:
            signal_label = _screening_signal_label(
                preserve_low_signal_branch=preserve_low_signal_branch,
                screening_feedback=screening_feedback,
                decision_reason_codes=decision_reason_codes,
            )
            if restored_regressed_checkpoint:
                reason = (
                    "CONTINUE_EXPLORE: rollback_to_checkpoint; "
                    "latest refinement was archived as negative evidence"
                )
            elif park_lineage:
                reason = (
                    "CONTINUE_EXPLORE: park_lineage; keep lineage evidence and "
                    "prefer clean fork or later checkpoint-aware follow-up"
                )
            elif retain_checkpoint:
                reason = (
                    "CONTINUE_EXPLORE: retain_checkpoint; preserve best "
                    "checkpoint and avoid treating failed head as active"
                )
            else:
                reason = (
                    f"CONTINUE_EXPLORE: {signal_label}; improve the same branch"
                    if preserve_low_signal_branch
                    else "CONTINUE_EXPLORE: re-propose next step"
                )
            runtime_budget_code = runtime_budget_diagnostic_code(protocol_result)
            if runtime_budget_code:
                reason = (
                    f"{reason}; runtime_budget_diagnostic={runtime_budget_code}"
                )
            runtime_confidence = str(
                getattr(protocol_result, "runtime_confidence", "") or ""
            )
            if runtime_confidence and runtime_confidence not in {
                "high",
                "sufficient",
            }:
                reason = (
                    f"{reason}; runtime_evidence_confidence={runtime_confidence}"
                )
            attempt_kind = "screening"
            repair_mechanism_ids = ()
        _attach_lifecycle_policy_evidence(branch, lifecycle_policy_evidence)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=reason,
            counts_toward_max_rounds=not telemetry_repairable,
            attempt_kind=attempt_kind,  # type: ignore[arg-type]
            repair_mechanism_ids=repair_mechanism_ids,
            repair_policy_reason=(
                WIRING_SUSPECT_REQUIRES_REPAIR if telemetry_repairable else ""
            ),
        )

    def _restore_checkpoint(
        self,
        branch: Branch,
        *,
        reason: str,
        reason_codes: tuple[str, ...],
        lifecycle_policy_evidence: dict[str, object] | None = None,
    ) -> bool:
        if self.restore_branch_checkpoint is None:
            return False
        previous_count = int(getattr(branch, "rollback_count", 0) or 0)
        try:
            restored = self.restore_branch_checkpoint(
                branch,
                reason=reason,
                reason_codes=reason_codes,
            )
        except TypeError:
            restored = self.restore_branch_checkpoint(branch)
        if not restored:
            return False
        if int(getattr(branch, "rollback_count", 0) or 0) <= previous_count:
            branch.rollback_count = previous_count + 1
        branch.last_rollback_reason = reason
        _merge_branch_lifecycle_block(
            branch,
            action="rollback_to_checkpoint",
            reason_codes=reason_codes,
        )
        _attach_lifecycle_policy_evidence(branch, lifecycle_policy_evidence)
        return True

    def _record_formal_candidate_artifact(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        patch: PatchProposal | None,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> None:
        if self.record_formal_candidate_artifact is None:
            return
        if not _should_reconcile_formal_candidate_artifact(
            protocol_result=protocol_result,
        ):
            return
        try:
            artifact_ref = self.record_formal_candidate_artifact(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                patch=patch,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=tuple(decision_reason_codes or ()),
                workspace=self.branch_workspaces.get(branch.branch_id),
            )
        except Exception as exc:  # pragma: no cover - audit artifact is best effort
            logger.debug(
                "Branch %s: formal candidate patch artifact write failed: %s",
                branch.branch_id,
                exc,
            )
            return
        if artifact_ref:
            summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
            summary["formal_candidate_patch_artifact_ref"] = artifact_ref
            branch.branch_evidence_summary = summary

    def _discard_current_workspace_preserve_checkpoints(self, branch_id: str) -> None:
        workspace = self.branch_workspaces.pop(branch_id, None)
        if not workspace:
            return
        try:
            self.archive_workspace(workspace, branch_id)
        except Exception as exc:
            logger.debug(
                "Branch %s: parked workspace archive failed: %s",
                branch_id,
                exc,
            )
        try:
            self.cleanup_workspace(workspace)
        except Exception:
            pass

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
        except PromotionCommitError as exc:
            if not exc.champion_persisted:
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
                    failure_stage="promotion_commit",
                    failure_category="infra",
                    failure_detail=str(exc),
                )
            logger.error(
                "Branch %s: promote commit failed after durable champion write at %s: %s",
                bid,
                exc.phase,
                exc.original,
            )
            lineage_status = "not_attempted"
            lineage_error = ""
            try:
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
                    strict=True,
                )
                lineage_status = "recorded"
            except Exception as lineage_exc:
                lineage_status = "degraded"
                lineage_error = str(lineage_exc)
                logger.error(
                    "Branch %s: promotion lineage write failed during recovery: %s",
                    bid,
                    lineage_exc,
                )
            _mark_promotion_integrity_status(
                branch,
                status="recovery_pending",
                promotion_event_id=promotion_event_id,
                champion_version=promote_plan.new_champion_version,
                failed_phase=exc.phase,
                completed_phases=exc.completed_phases,
                lineage_status=lineage_status,
                error=str(exc.original),
                lineage_error=lineage_error,
            )
            self.persist_branch_state(bid)
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=Decision.PROMOTE,
                reason=(
                    "promotion_commit_recovery_pending: "
                    f"phase={exc.phase}; lineage_status={lineage_status}"
                ),
                failure_stage="promotion_commit",
                failure_category="promotion_recovery",
                failure_detail=str(exc.original),
                scheduler_audit_metadata={
                    "promotion_integrity_status": "recovery_pending",
                    "promotion_failed_phase": exc.phase,
                    "promotion_event_id": promotion_event_id,
                    "promotion_lineage_status": lineage_status,
                },
            )
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
                failure_stage="promotion_commit",
                failure_category="infra",
                failure_detail=str(exc),
            )
        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=self.branch_patches.get(bid),
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=Decision.PROMOTE,
            decision_reason_codes=decision_reason_codes,
        )
        try:
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
                strict=True,
            )
        except Exception as exc:
            logger.error("Branch %s: promotion lineage write failed: %s", bid, exc)
            _mark_promotion_integrity_status(
                branch,
                status="lineage_degraded",
                promotion_event_id=promotion_event_id,
                champion_version=promote_plan.new_champion_version,
                failed_phase="record_lineage",
                completed_phases=(),
                lineage_status="degraded",
                error=str(exc),
            )
            self.persist_branch_state(bid)
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=Decision.PROMOTE,
                reason=f"promotion_lineage_degraded: {exc}",
                failure_stage="promotion_lineage",
                failure_category="promotion_recovery",
                failure_detail=str(exc),
                scheduler_audit_metadata={
                    "promotion_integrity_status": "lineage_degraded",
                    "promotion_event_id": promotion_event_id,
                    "promotion_lineage_status": "degraded",
                },
            )
        self.persist_branch_state(bid)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=Decision.PROMOTE,
            reason="decision=promote",
        )

    def _abandon(
        self,
        *,
        branch: Branch,
        h_record: HypothesisRecord,
        lifecycle_action: DecisionLifecycleAction,
        decision_reason_codes: Optional[tuple[str, ...]],
        counts_toward_hard_abandon: bool,
    ) -> None:
        bid = branch.branch_id
        accounting_kind = (
            "hard_terminal_abandon"
            if counts_toward_hard_abandon
            else "soft_lifecycle_archive"
        )
        _record_abandon_accounting(
            branch,
            lifecycle_action=lifecycle_action,
            decision_reason_codes=decision_reason_codes,
            counts_toward_hard_abandon=counts_toward_hard_abandon,
            accounting_kind=accounting_kind,
        )
        if counts_toward_hard_abandon:
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


def _should_record_formal_candidate_artifact(
    *,
    patch: PatchProposal | None,
    protocol_result: Optional[ProtocolResult],
    canary_result: CanaryResult,
    contract_result: ContractResult,
    verification_result: VerificationResult,
) -> bool:
    if patch is None or protocol_result is None:
        return False
    if not (
        contract_result.passed
        and verification_result.passed
        and canary_result.passed
    ):
        return False
    if getattr(protocol_result, "stats", None) is None:
        return False
    return _stage_value(protocol_result) == "screening"


def _should_reconcile_formal_candidate_artifact(
    *,
    protocol_result: Optional[ProtocolResult],
) -> bool:
    if protocol_result is None:
        return False
    if getattr(protocol_result, "stats", None) is None:
        return False
    return _stage_value(protocol_result) == "screening"


def _with_protocol_accounting(
    result: StepResult,
    protocol_result: Optional[ProtocolResult],
) -> StepResult:
    if protocol_result is None:
        return result
    stage = _stage_value(protocol_result)
    if stage not in {"screening", "validation", "frozen"}:
        return result
    formal_evaluated = (
        getattr(protocol_result, "stats", None) is not None
        and screened_experiment_effective(protocol_result)
    )
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated
    return result


def _soft_lifecycle_bookkeeping(
    *,
    lifecycle_action: DecisionLifecycleAction,
    decision_reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema": "scion.lifecycle_bookkeeping.v1",
        "role": "screening_result_lifecycle_annotation",
        "attached_to_attempt_kind": "screening",
        "legacy_attempt_kind": "branch_lifecycle_policy",
        "legacy_decision_layer_source": "lifecycle_policy",
        "decision_layer_source": "stage_decision",
        "lifecycle_action": lifecycle_action or "archive_lineage",
        "reason_codes": list(decision_reason_codes or ()),
    }


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
    positive_low_signal_continue = _positive_low_signal_continue(
        decision_reason_codes
    )
    if _screening_quality_regressed(stats) and not positive_low_signal_continue:
        return False
    if stats.median_delta is not None and stats.median_delta < 0:
        return False
    if stats.candidate_failed_pairs > 0:
        return False
    runtime_confident = _screening_runtime_evidence_confident(stats)
    if (
        runtime_confident
        and stats.runtime_ratio_median is not None
        and stats.runtime_ratio_median > 1.10
    ):
        return False
    if (
        runtime_confident
        and stats.runtime_regression_rate is not None
        and stats.runtime_regression_rate >= 0.90
    ):
        return False
    lifecycle_codes = {
        SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        SCREENING_MARGINAL_SIGNAL_CONTINUE,
        SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        SCREENING_WEAK_SIGNAL_CONTINUE,
        SCREENING_ZERO_WIN_STREAK_CONTINUE,
    }
    reason_set = set(decision_reason_codes or ())
    if lifecycle_codes & reason_set:
        return True
    return False


def _fresh_runtime_replay_required(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Optional[tuple[str, ...]],
) -> bool:
    if protocol_result is None:
        return False
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return False
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, dict):
        summary = {}
    marker = summary.get("fresh_runtime_followup")
    marker_required = (
        bool(marker.get("fresh_runtime_required") or marker.get("followup_required"))
        if isinstance(marker, dict)
        else False
    )
    marker_pending = (
        bool(marker.get("fresh_runtime_pending"))
        if isinstance(marker, dict)
        else bool(summary.get("fresh_runtime_pending"))
    )
    reason_set = {str(code).strip().upper() for code in decision_reason_codes or ()}
    status = str(
        getattr(protocol_result, "runtime_evidence_status", "")
        or getattr(
            getattr(protocol_result, "stats", None),
            "runtime_evidence_status",
            "",
        )
        or ""
    ).strip().lower()
    return bool(
        (marker_required and marker_pending)
        or bool(summary.get("fresh_runtime_required"))
        or status in {"fresh_champion_required", "fresh_required"}
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_set
        or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_set
    )


def _mark_promotion_integrity_status(
    branch: Branch,
    *,
    status: str,
    promotion_event_id: str,
    champion_version: int,
    failed_phase: str,
    completed_phases: Iterable[str],
    lineage_status: str,
    error: str,
    lineage_error: str = "",
) -> None:
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    marker = {
        "status": status,
        "promotion_event_id": promotion_event_id,
        "champion_version": champion_version,
        "failed_phase": failed_phase,
        "completed_phases": list(completed_phases),
        "lineage_status": lineage_status,
        "recovery_required": True,
        "error": error,
    }
    if lineage_error:
        marker["lineage_error"] = lineage_error
    summary["promotion_integrity"] = marker
    branch.branch_evidence_summary = summary


def _sync_terminal_branch_evidence(
    branch: Branch,
    *,
    hypothesis: HypothesisProposal,
    patch: PatchProposal | None,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Iterable[str] | None,
    lifecycle_action: DecisionLifecycleAction,
    lifecycle_policy_evidence: dict[str, object] | None = None,
) -> None:
    """Keep abandoned branch rows useful when read without campaign_summary."""

    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (decision_reason_codes or ())
            if str(code).strip()
        )
    )
    branch.branch_mechanism_ids = _merge_mechanism_ids(
        getattr(branch, "branch_mechanism_ids", ()) or (),
        _proposal_mechanism_ids(hypothesis, patch),
    )
    feedback = None
    if protocol_result is not None and _stage_value(protocol_result) == "screening":
        feedback = screening_feedback_summary(
            protocol_result,
            decision_reason_codes=reason_codes,
        )
        _update_branch_screening_evidence_summary(
            branch,
            protocol_result=protocol_result,
            screening_feedback=feedback,
            decision_reason_codes=reason_codes,
        )
        branch.last_screening_feedback_tier = (
            getattr(branch, "last_screening_feedback_tier", None)
            or feedback.tier
        )
        branch.last_telemetry_outcome = (
            getattr(branch, "last_telemetry_outcome", None)
            or feedback.effect_status
            or feedback.activation_status
        )

    prior_status = str(getattr(branch, "branch_code_status", "") or "")
    if prior_status in {"", "clean"}:
        branch.branch_code_status = _terminal_branch_code_status(
            protocol_result,
            reason_codes,
            lifecycle_action=lifecycle_action,
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

    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    if (
        protocol_result is not None
        and getattr(protocol_result, "stats", None) is not None
    ):
        _merge_protocol_evidence_summary(summary, protocol_result)
    if feedback is not None:
        summary.setdefault("tier", feedback.tier)
        summary.setdefault("runtime_evidence_confidence", feedback.runtime_confidence)
        summary.setdefault(
            "phase_activation_summary",
            {
                "stage": "screening",
                "activation_status": feedback.activation_status,
                "effect_status": feedback.effect_status,
                "opportunity_status": feedback.opportunity_status,
                "telemetry_outcome": getattr(branch, "last_telemetry_outcome", None),
            },
        )
    summary.update(
        {
            "terminal_status": BranchState.ABANDONED.value,
            "terminal_reason": reason_codes[0] if reason_codes else "decision_abandon",
            "terminal_reason_codes": list(reason_codes),
            "decision_reason_codes": list(reason_codes),
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "mechanism_ids": list(getattr(branch, "branch_mechanism_ids", ()) or ()),
        }
    )
    _record_abandon_accounting(
        branch,
        lifecycle_action=lifecycle_action,
        decision_reason_codes=reason_codes,
        counts_toward_hard_abandon=_counts_toward_hard_abandon(lifecycle_action),
        accounting_kind=(
            "hard_terminal_abandon"
            if _counts_toward_hard_abandon(lifecycle_action)
            else "soft_lifecycle_archive"
        ),
        summary=summary,
    )
    branch.branch_evidence_summary = summary

    block = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    terminal_reason = (
        block.get("reason")
        or (reason_codes[0] if reason_codes else "decision_abandon")
    )
    block.update(
        {
            "reason": terminal_reason,
            "terminal_status": BranchState.ABANDONED.value,
            "terminal_reason_codes": list(reason_codes),
            "decision_reason_codes": list(reason_codes),
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "mechanism_ids": list(getattr(branch, "branch_mechanism_ids", ()) or ()),
        }
    )
    _record_abandon_accounting(
        branch,
        lifecycle_action=lifecycle_action,
        decision_reason_codes=reason_codes,
        counts_toward_hard_abandon=_counts_toward_hard_abandon(lifecycle_action),
        accounting_kind=(
            "hard_terminal_abandon"
            if _counts_toward_hard_abandon(lifecycle_action)
            else "soft_lifecycle_archive"
        ),
        summary=block,
    )
    branch.last_branch_lifecycle_policy_block = block
    _attach_lifecycle_policy_evidence(branch, lifecycle_policy_evidence)


def _attach_lifecycle_policy_evidence(
    branch: Branch,
    evidence: dict[str, object] | None,
) -> None:
    if not isinstance(evidence, dict) or not evidence:
        return
    block = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    if not block and str(evidence.get("action") or "") == "retain_head":
        return
    block["lifecycle_policy_evidence"] = dict(evidence)
    thresholds = evidence.get("thresholds")
    counters = evidence.get("counters")
    if isinstance(thresholds, dict):
        block["lifecycle_policy_thresholds"] = dict(thresholds)
    if isinstance(counters, dict):
        block["lifecycle_policy_counters"] = dict(counters)
    branch.last_branch_lifecycle_policy_block = block


def _proposal_mechanism_ids(
    hypothesis: HypothesisProposal,
    patch: PatchProposal | None,
) -> tuple[str, ...]:
    ids: list[str] = []
    ids.extend(mechanism_ids_for_repair(hypothesis))
    ids.extend(mechanism_ids_for_repair(patch))
    return tuple(dict.fromkeys(item for item in ids if item))


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")


def _terminal_branch_code_status(
    protocol_result: Optional[ProtocolResult],
    reason_codes: tuple[str, ...],
    *,
    lifecycle_action: DecisionLifecycleAction = "",
) -> str:
    if _effective_lifecycle_action(lifecycle_action, reason_codes) == "archive_lineage":
        return "discarded"
    if protocol_result is None or getattr(protocol_result, "stats", None) is None:
        return "abandoned_terminal"
    stats = protocol_result.stats
    if (
        int(getattr(stats, "losses", 0) or 0)
        > int(getattr(stats, "wins", 0) or 0)
        or float(getattr(stats, "median_delta", 0.0) or 0.0) < 0.0
    ):
        return "quality_regression"
    return "discarded"


def _effective_lifecycle_action(
    lifecycle_action: str | None,
    decision_reason_codes: Optional[tuple[str, ...]],
) -> DecisionLifecycleAction:
    if lifecycle_action == "soft_abandon":
        return "archive_lineage"
    if lifecycle_action in {
        "retain_head",
        "retain_checkpoint",
        "rollback_to_checkpoint",
        "park_lineage",
        "archive_lineage",
    }:
        return lifecycle_action  # type: ignore[return-value]
    return ""


def _counts_toward_hard_abandon(
    lifecycle_action: DecisionLifecycleAction,
) -> bool:
    return lifecycle_action not in {"archive_lineage", "park_lineage"}


def _record_abandon_accounting(
    branch: Branch,
    *,
    lifecycle_action: DecisionLifecycleAction,
    decision_reason_codes: Optional[tuple[str, ...]],
    counts_toward_hard_abandon: bool,
    accounting_kind: str,
    summary: dict | None = None,
) -> None:
    target = summary
    if target is None:
        target = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    reason_codes = tuple(decision_reason_codes or ())
    accounting = {
        "schema_version": "abandon_accounting.v1",
        "kind": accounting_kind,
        "counts_toward_hard_abandon": counts_toward_hard_abandon,
        "lifecycle_action": lifecycle_action or "decision_abandon",
        "decision_reason_codes": list(reason_codes),
    }
    target["abandon_accounting"] = accounting
    target["abandon_accounting_kind"] = accounting_kind
    target["counts_toward_hard_abandon"] = counts_toward_hard_abandon
    if summary is None:
        branch.branch_evidence_summary = target


def _merge_protocol_evidence_summary(
    summary: dict,
    protocol_result: ProtocolResult,
) -> None:
    stats = protocol_result.stats
    summary.setdefault("stage", _stage_value(protocol_result))
    summary.setdefault("tier", _terminal_evidence_tier(protocol_result))
    for key, value in {
        "wins": int(getattr(stats, "wins", 0) or 0),
        "losses": int(getattr(stats, "losses", 0) or 0),
        "ties": int(getattr(stats, "ties", 0) or 0),
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
        "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
        "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
        "runtime_pairs": int(getattr(stats, "runtime_pairs", 0) or 0),
    }.items():
        if value is not None:
            summary.setdefault(key, value)
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(
        protocol_result
    )
    if runtime_aggregate_exclusion:
        summary.setdefault(
            "runtime_aggregate_exclusion",
            runtime_aggregate_exclusion,
        )


def _terminal_evidence_tier(protocol_result: ProtocolResult) -> str:
    stats = protocol_result.stats
    wins = int(getattr(stats, "wins", 0) or 0)
    losses = int(getattr(stats, "losses", 0) or 0)
    median_delta = float(getattr(stats, "median_delta", 0.0) or 0.0)
    if losses > wins or median_delta < 0.0:
        return "regression"
    if wins > losses:
        return (
            "weak_positive"
            if protocol_result.gate_outcome == "pass"
            else "marginal"
        )
    return "no_effect" if wins == 0 and losses == 0 else "marginal"


def _positive_low_signal_continue(
    decision_reason_codes: Optional[tuple[str, ...]],
) -> bool:
    reason_set = set(decision_reason_codes or ())
    return bool(
        reason_set
        & {
            SCREENING_MARGINAL_SIGNAL_CONTINUE,
            SCREENING_WEAK_SIGNAL_CONTINUE,
        }
    )


def _retained_screening_status(
    *,
    preserve_low_signal_branch: bool,
    tier: str,
) -> str:
    if not preserve_low_signal_branch:
        return "rejected"
    if tier == "no_effect":
        return "screening_no_effect"
    if tier == "weak_positive":
        return "screening_weak_positive_retained"
    if tier == "marginal":
        return "screening_marginal_retained"
    return "screening_retained_for_branch_followup"


def _screening_signal_label(
    *,
    preserve_low_signal_branch: bool,
    screening_feedback: object | None,
    decision_reason_codes: Optional[tuple[str, ...]],
) -> str:
    if not preserve_low_signal_branch:
        return "screening did not retain the branch"
    tier = str(getattr(screening_feedback, "tier", "") or "")
    if tier == "weak_positive":
        return "weak-positive screening signal"
    if tier == "marginal":
        return "marginal mixed screening signal"
    if tier == "no_effect":
        return "neutral no-effect screening signal"
    if tier == "runtime_regression":
        return "runtime-regression screening diagnostic"
    if tier == "inactive":
        return "inactive screening diagnostic"
    reason_set = set(decision_reason_codes or ())
    if SCREENING_NEUTRAL_SIGNAL_CONTINUE in reason_set:
        return "neutral no-effect screening signal"
    if SCREENING_ZERO_WIN_STREAK_CONTINUE in reason_set:
        return "zero-win screening signal"
    if SCREENING_TELEMETRY_DIAGNOSTIC_RETRY in reason_set:
        return "screening telemetry diagnostic retry"
    return "low-signal screening result"


def _is_regressed_weak_positive_followup(
    branch: Branch,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Optional[tuple[str, ...]],
) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if status != "active_weak_positive" and tier != "weak_positive":
        return False
    if protocol_result is None:
        return False
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return False
    stats = protocol_result.stats
    if stats is None:
        return False
    reason_set = set(decision_reason_codes or ())
    if reason_set & {
        SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
        SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,
        SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
    }:
        return True
    return _screening_quality_regressed(stats)


def _screening_quality_regressed(stats: EvalStats) -> bool:
    wins = max(0, int(getattr(stats, "wins", 0) or 0))
    losses = max(0, int(getattr(stats, "losses", 0) or 0))
    median_delta = getattr(stats, "median_delta", None)
    if median_delta is not None and median_delta < 0:
        return True
    if wins > 0 and losses >= wins + 2:
        return True
    ci_low = getattr(stats, "ci_low", None)
    ci_high = getattr(stats, "ci_high", None)
    if ci_low is not None and ci_high is not None and ci_low < 0 and ci_high <= 0:
        return True
    return False


def _screening_runtime_evidence_confident(stats: EvalStats) -> bool:
    runtime_pairs = int(getattr(stats, "runtime_pairs", 0) or 0)
    if runtime_pairs >= 4:
        return True
    runtime_ratio = getattr(stats, "runtime_ratio_median", None)
    runtime_delta = getattr(stats, "runtime_delta_median_ms", None)
    regression_rate = getattr(stats, "runtime_regression_rate", None)
    return bool(
        runtime_ratio is not None
        and runtime_ratio >= 1.50
        and runtime_delta is not None
        and runtime_delta >= 100.0
        and regression_rate is not None
        and regression_rate >= 0.90
    )


def _merge_mechanism_ids(
    existing: tuple[str, ...],
    proposed: tuple[str, ...],
) -> tuple[str, ...]:
    ids = [
        str(item).strip()
        for item in (*tuple(existing or ()), *tuple(proposed or ()))
        if str(item).strip()
    ]
    return tuple(dict.fromkeys(ids))


def _telemetry_repair_stage(
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Optional[tuple[str, ...]],
) -> str | None:
    reason_set = set(decision_reason_codes or ())
    if VALIDATION_TELEMETRY_REPAIRABLE in reason_set:
        return "validation"
    if SCREENING_TELEMETRY_REPAIRABLE in reason_set:
        return "screening"
    if TELEMETRY_VALIDATION_REPAIRABLE not in reason_set:
        return None
    if protocol_result is not None:
        stage = getattr(protocol_result.stage, "value", protocol_result.stage)
        if stage in ("screening", "validation"):
            return str(stage)
    return "screening"
