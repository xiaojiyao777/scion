"""Branch-step execution boundary for CampaignManager."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional

from scion.core.branch import BranchController, StateTransitionError
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    ContractResult,
    Decision,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.scheduler import (
    Scheduler,
    branch_active_slot_release_reason,
    branch_counts_toward_active_slots,
    active_slot_capacity_block_metadata,
    reclaim_active_slot_for_new_branch,
    reconcile_active_slot_overflow,
)
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
)
from scion.core.step_result import StepResult
from scion.core.frozen_budget import FROZEN_BUDGET_EXHAUSTED
from scion.core.verification_call import run_verification_gate

logger = logging.getLogger(__name__)


@dataclass
class BranchStepRunner:
    """Own branch dispatch, eval-only execution, and stale reconciliation."""

    branch_controller: BranchController
    scheduler: Scheduler
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_store: Any
    branch_workspaces: MutableMapping[str, str]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    experiment_protocol_provider: Callable[[], Any]
    contract_gate: Any
    verification_gate: Any
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    tick_blocked_branches: Callable[[], None]
    persist_branch_state: Callable[[str], None]
    record_hard_abandon: Callable[[str, str], None]
    setup_workspace: Callable[..., Optional[str]]
    apply_patch: Callable[..., Any]
    record_verification_pass: Callable[[Branch, str], None]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        tuple[Decision, Any, Any],
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    record_step: Callable[[StepRecord], None]
    decision_reason_codes_for: Callable[[str, Any], Optional[tuple[str, ...]]]
    run_explore_step: Callable[[Branch], StepResult]
    run_eval_step_callback: Callable[[Branch], StepResult]
    run_reconcile_step_callback: Callable[[Branch], StepResult]
    increment_round: Callable[[], int]
    increment_rounds_since_last_promote: Callable[[], None]
    hypothesis_store: Any
    record_scheduler_result: Optional[Callable[[StepResult], None]] = None

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        self.drain_weight_opt_events()
        if self.should_stop():
            return StepResult(
                action="stopped",
                stopped=True,
                reason=self.get_last_stop_reason() or "termination condition met",
            )

        self.tick_blocked_branches()
        max_active_branches = _scheduler_max_active_branches(self.scheduler)
        active_slot_reconciliations: list[dict[str, Any]] = []

        active = self.branch_controller.get_active_branches()
        if max_active_branches is not None:
            reconciliation = reconcile_active_slot_overflow(
                active,
                max_active_branches=max_active_branches,
            )
            if reconciliation.changed:
                self._persist_active_slot_reconciliation(reconciliation)
                active_slot_reconciliations.append(
                    reconciliation.as_audit_metadata()
                )
                active = self.branch_controller.get_active_branches()

        sched = self.scheduler.select_next(active)
        if sched.action == "at_capacity" and max_active_branches is not None:
            reconciliation = reclaim_active_slot_for_new_branch(
                active,
                max_active_branches=max_active_branches,
            )
            if reconciliation.changed:
                self._persist_active_slot_reconciliation(reconciliation)
                active_slot_reconciliations.append(
                    reconciliation.as_audit_metadata()
                )
                active = self.branch_controller.get_active_branches()
                sched = self.scheduler.select_next(active)

        def finalize(
            result: StepResult,
            *,
            capacity_block: dict[str, Any] | None = None,
        ) -> StepResult:
            return _finalize_scheduler_result(
                _attach_active_slot_audit(
                    result,
                    active_slot_reconciliations,
                    capacity_block=capacity_block,
                ),
                sched,
                self.record_scheduler_result,
            )

        if sched.action == "at_capacity":
            capacity_block = (
                active_slot_capacity_block_metadata(
                    active,
                    max_active_branches=max_active_branches,
                )
                if max_active_branches is not None
                else None
            )
            return finalize(
                StepResult(action="skip", reason="max_active_branches reached"),
                capacity_block=capacity_block,
            )

        if sched.action == "create_new":
            with self.champion_lock:
                champion = self.get_champion()
            branch = self.branch_controller.create_branch(champion)
            logger.info("Created new branch %s", branch.branch_id)
            try:
                self.branch_store.save(branch)
            except Exception as exc:
                logger.debug("BranchStore.save (create) failed: %s", exc)
            result = self.run_explore_step(branch)
            result.action = "create_branch"
            return finalize(result)

        branch = sched.branch
        assert branch is not None

        if branch.state in (BranchState.READY_VALIDATE, BranchState.READY_FROZEN):
            try:
                self.branch_controller.schedule_branch(branch.branch_id)
                self.persist_branch_state(branch.branch_id)
            except StateTransitionError as exc:
                logger.error("schedule_branch failed: %s", exc)
                return finalize(
                    StepResult(
                        action="skip",
                        branch_id=branch.branch_id,
                        reason=str(exc),
                    )
                )

        branch = self.branch_controller.get_branch(branch.branch_id)

        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return finalize(self.run_reconcile_step_callback(branch))

        if branch.state == BranchState.EXPLORE:
            return finalize(self.run_explore_step(branch))

        if branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        ):
            try:
                return finalize(self.run_eval_step_callback(branch))
            except RuntimeError as exc:
                return finalize(self._handle_eval_runtime_error(branch, exc))

        logger.warning(
            "Branch %s in unexpected state %s - skipping",
            branch.branch_id,
            branch.state.value,
        )
        return finalize(
            StepResult(
                action="skip",
                branch_id=branch.branch_id,
                reason=f"unhandled state {branch.state.value}",
            )
        )

    def _persist_active_slot_reconciliation(self, reconciliation: Any) -> None:
        for branch_id in getattr(reconciliation, "parked_branch_ids", ()) or ():
            try:
                self.persist_branch_state(str(branch_id))
            except Exception as exc:  # pragma: no cover - persistence is best-effort
                logger.debug(
                    "Branch %s: active-slot reconciliation persist failed: %s",
                    branch_id,
                    exc,
                )

    def run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for validation/frozen branches."""
        bid = branch.branch_id
        logger.debug(
            "_run_eval_step start bid=%s state=%s workspaces=%s",
            bid,
            branch.state.value,
            list(self.branch_workspaces.keys()),
        )
        workspace = self.branch_workspaces.get(bid)
        if workspace is None:
            logger.warning("Branch %s: no workspace for eval step - abandoning", bid)
            self._reject_current_hypothesis(bid)
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "eval_workspace_missing")
            return StepResult(action="validate", branch_id=bid, reason="workspace not found")

        hypothesis = self.branch_hypotheses.get(bid)
        if hypothesis is None:
            logger.warning("Branch %s: no hypothesis for eval step - abandoning", bid)
            self._reject_current_hypothesis(bid)
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "eval_hypothesis_missing")
            return StepResult(action="validate", branch_id=bid, reason="hypothesis not found")

        patch = self.branch_patches.get(bid)
        verification_result = VerificationResult(passed=True, checks=())
        action_label = self._eval_action_label(branch)

        h_record = self.branch_current_hypothesis.get(bid)
        if h_record is None:
            raise RuntimeError(
                f"Branch {bid}: no canonical hypothesis record - cannot proceed with eval"
            )

        contract_result = ContractResult(passed=True, checks=())
        decision, protocol_result, canary_result = self.evaluate(
            branch,
            workspace,
            hypothesis,
        )

        round_num = self.increment_round()
        if action_label == "explore":
            self.increment_rounds_since_last_promote()
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
        )
        failure_stage, failure_detail = _eval_failure_detail(protocol_result)
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=patch,
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                counts_toward_max_rounds=result.counts_toward_max_rounds,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
            )
        )
        return result

    def run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a stale branch on the new champion."""
        bid = branch.branch_id
        patch = self.branch_patches.get(bid)
        h_record = self.branch_current_hypothesis.get(bid)

        def cleanup() -> None:
            if h_record is not None:
                try:
                    self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
                except Exception:
                    pass
                self.branch_current_hypothesis.pop(bid, None)

        def abandon_stale(reason: str) -> StepResult:
            cleanup()
            self.branch_controller.reconcile_stale(
                bid,
                success=False,
                new_champion=self.get_champion(),
            )
            self.persist_branch_state(bid)
            self.record_hard_abandon(bid, reason)
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                counts_toward_max_rounds=False,
                attempt_kind="reconcile_lifecycle",
            )

        if patch is None:
            logger.info("Branch %s: no patch to reconcile - abandoning stale branch", bid)
            return abandon_stale("no patch to reconcile")

        hypothesis = self.branch_hypotheses.get(bid)
        contract_result = self.contract_gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
        )
        if not contract_result.passed:
            logger.info(
                "Branch %s: reconcile patch failed contract gate: %s",
                bid,
                contract_result.failure_reason,
            )
            return abandon_stale(
                f"reconcile contract failed: {contract_result.failure_reason}"
            )

        workspace = self.setup_workspace(branch, force_champion=True)
        if workspace is None:
            return abandon_stale("workspace setup failed")

        try:
            applied = self.apply_patch(
                branch,
                workspace,
                patch,
                remember_patch=False,
            )
            code_hash = applied.code_hash
        except Exception as exc:
            logger.info("Branch %s: reconcile apply_patch failed: %s", bid, exc)
            return abandon_stale(f"apply_patch failed: {exc}")

        champion_workspace = self.get_champion().code_snapshot_path
        verification_result = run_verification_gate(
            self.verification_gate,
            workspace,
            champion_workspace,
            patch,
            hypothesis=hypothesis,
        )
        if not verification_result.passed:
            logger.info(
                "Branch %s: reconcile verification failed: %s",
                bid,
                verification_result.first_failure,
            )
            return abandon_stale(
                f"reconcile verification failed: {verification_result.first_failure}"
            )

        self.record_verification_pass(branch, code_hash)

        if self.experiment_protocol_provider() is None:
            logger.info(
                "Branch %s: no experiment protocol for reconcile re-screening - abandoning stale branch",
                bid,
            )
            return abandon_stale("no experiment protocol for re-screening")

        h_record = self.branch_current_hypothesis.get(bid)
        if hypothesis is None or h_record is None:
            logger.info(
                "Branch %s: missing hypothesis metadata for reconcile - abandoning stale branch",
                bid,
            )
            return abandon_stale("missing hypothesis metadata for reconcile")

        self.branch_controller.reconcile_stale(
            bid,
            success=True,
            new_champion=self.get_champion(),
        )
        self.persist_branch_state(bid)
        branch = self.branch_controller.get_branch(bid)
        if branch is None:
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason="branch disappeared after reconcile",
                counts_toward_max_rounds=False,
                attempt_kind="reconcile_lifecycle",
            )

        round_num = self.increment_round()
        self.increment_rounds_since_last_promote()
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
            contract_result=contract_result,
            verification_result=verification_result,
            action_label="reconcile",
        )
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=self.branch_patches.get(bid, patch),
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision,
                failure_stage=None,
                failure_detail=None,
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                counts_toward_max_rounds=result.counts_toward_max_rounds,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
            )
        )
        return result

    def _handle_eval_runtime_error(
        self,
        branch: Branch,
        exc: RuntimeError,
    ) -> StepResult:
        logger.error("Branch %s: eval step aborted - %s", branch.branch_id, exc)
        bid = branch.branch_id
        self._reject_current_hypothesis(bid)
        self.branch_controller.apply_decision(branch.branch_id, Decision.ABANDON)
        self.persist_branch_state(branch.branch_id)
        self.record_hard_abandon(branch.branch_id, "eval_runtime_error")
        return StepResult(action="validate", branch_id=branch.branch_id, reason=str(exc))

    def _reject_current_hypothesis(self, branch_id: str) -> None:
        h_record = self.branch_current_hypothesis.get(branch_id)
        if h_record is not None:
            try:
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            except Exception:
                pass
            self.branch_current_hypothesis.pop(branch_id, None)

    @staticmethod
    def _eval_action_label(branch: Branch) -> str:
        if branch.state == BranchState.EXPLORE_EXPAND:
            return "explore"
        if branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
            return "validate"
        return "frozen"


def _eval_failure_detail(
    protocol_result: Any | None,
) -> tuple[str | None, str | None]:
    if protocol_result is None:
        return None, None
    reason_codes = {
        str(code).lower()
        for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if FROZEN_BUDGET_EXHAUSTED in reason_codes:
        return "frozen_budget", FROZEN_BUDGET_EXHAUSTED
    return None, None


def _scheduler_max_active_branches(scheduler: Any) -> int | None:
    value = getattr(scheduler, "max_active_branches", None)
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _attach_active_slot_audit(
    result: StepResult,
    reconciliations: list[dict[str, Any]],
    *,
    capacity_block: dict[str, Any] | None = None,
) -> StepResult:
    if not reconciliations and capacity_block is None:
        return result
    audit_metadata = dict(getattr(result, "scheduler_audit_metadata", None) or {})
    if reconciliations:
        audit_metadata["active_slot_reconciliations"] = list(reconciliations)
        audit_metadata["active_slot_reconciliation"] = dict(reconciliations[-1])
    if capacity_block is not None:
        audit_metadata["active_slot_hard_cap"] = dict(capacity_block)
    result.scheduler_audit_metadata = audit_metadata
    return result


def _with_scheduler_metadata(result: StepResult, sched: Any) -> StepResult:
    result.scheduler_slot = str(getattr(sched, "slot", "") or "")
    result.scheduler_reason = str(getattr(sched, "reason", "") or "")
    scheduler_action = str(getattr(sched, "action", "") or "")
    scheduled_branch = getattr(sched, "branch", None)
    scheduled_branch_id = str(getattr(scheduled_branch, "branch_id", "") or "")
    audit_metadata = dict(getattr(result, "scheduler_audit_metadata", None) or {})
    scheduler_audit = getattr(sched, "audit_metadata", None)
    if isinstance(scheduler_audit, Mapping):
        for key, value in scheduler_audit.items():
            audit_metadata.setdefault(str(key), value)
    if scheduler_action:
        audit_metadata.setdefault("scheduler_action", scheduler_action)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_action",
            scheduler_action,
        )
    if result.scheduler_slot:
        audit_metadata.setdefault("scheduler_slot", result.scheduler_slot)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_slot",
            result.scheduler_slot,
        )
    if result.scheduler_reason:
        audit_metadata.setdefault("scheduler_reason", result.scheduler_reason)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_reason",
            result.scheduler_reason,
        )
    if scheduled_branch_id:
        audit_metadata.setdefault(
            "pre_finalizer_selected_branch_id",
            scheduled_branch_id,
        )
    if result.scheduler_slot:
        audit_metadata.setdefault(
            "scheduler_slot_semantics",
            "pre_finalizer_scheduler_preference",
        )
    aligned_reason = _scheduler_aligned_result_reason(
        result.reason,
        actual_branch_action=(
            "explore_new_clean_fork"
            if (
                scheduler_action == "create_new"
                and result.scheduler_slot == "explore_new"
            )
            else ""
        ),
        scheduler_slot=result.scheduler_slot,
    )
    if scheduler_action == "create_new" and result.scheduler_slot == "explore_new":
        audit_metadata.update(
            {
                "clean_fork_selected": True,
                "clean_fork_reason": result.scheduler_reason,
                "same_branch_refinement_not_selected_reason": (
                    result.scheduler_reason
                    or "scheduler_selected_clean_exploration_branch"
                ),
                "actual_branch_action": "explore_new_clean_fork",
                "post_finalizer_actual_branch_action": "explore_new_clean_fork",
                "post_finalizer_next_proposal_policy": "clean_fork_selected",
            }
        )
    elif scheduler_action == "run_existing" and scheduled_branch is not None:
        branch_id = str(
            getattr(scheduled_branch, "branch_id", "") or result.branch_id or ""
        )
        actual_action = _post_finalizer_actual_branch_action(
            result,
            scheduled_branch,
        )
        post_metadata = _post_finalizer_branch_metadata(
            scheduled_branch,
            actual_branch_action=actual_action,
        )
        audit_metadata.update(
            {
                "same_branch_refinement_selected": (
                    actual_action == "continue_same_branch"
                ),
                "pre_finalizer_same_branch_refinement_selected": True,
                "refined_branch_id": branch_id,
                "actual_branch_action": actual_action,
                "post_finalizer_actual_branch_action": actual_action,
                **post_metadata,
            }
        )
        aligned_reason = _scheduler_aligned_result_reason(
            result.reason,
            actual_branch_action=actual_action,
            scheduler_slot=result.scheduler_slot,
        )
        if result.action == "soft_abandon":
            audit_metadata["post_refine_abandon_reason"] = aligned_reason
        elif actual_action != "continue_same_branch":
            audit_metadata["post_refine_release_reason"] = aligned_reason
        else:
            audit_metadata["post_refine_decision_reason"] = aligned_reason
    audit_metadata.setdefault(
        "same_mechanism_clean_fork_justification",
        _same_mechanism_clean_fork_justification(audit_metadata),
    )
    result.scheduler_audit_metadata = audit_metadata
    result.reason = aligned_reason
    return result


def _same_mechanism_clean_fork_justification(
    audit_metadata: dict[str, Any],
) -> dict[str, Any]:
    selected_policy = str(
        audit_metadata.get("post_finalizer_next_proposal_policy")
        or audit_metadata.get("scheduler_action")
        or ""
    )
    clean_fork_selected = bool(audit_metadata.get("clean_fork_selected"))
    not_selected_reason = str(
        audit_metadata.get("same_branch_refinement_not_selected_reason") or ""
    )
    clean_fork_reason = str(audit_metadata.get("clean_fork_reason") or "")
    active_branch_cap_context = {
        "scheduler_slot": str(
            audit_metadata.get("pre_finalizer_scheduler_slot")
            or audit_metadata.get("scheduler_slot")
            or ""
        ),
        "scheduler_reason": str(
            audit_metadata.get("pre_finalizer_scheduler_reason")
            or audit_metadata.get("scheduler_reason")
            or ""
        ),
        "pre_finalizer_scheduler_action": str(
            audit_metadata.get("pre_finalizer_scheduler_action")
            or audit_metadata.get("scheduler_action")
            or ""
        ),
    }
    active_slot_hard_cap = audit_metadata.get("active_slot_hard_cap")
    if isinstance(active_slot_hard_cap, dict):
        active_branch_cap_context["active_slot_hard_cap"] = dict(
            active_slot_hard_cap
        )
    active_slot_reconciliation = audit_metadata.get("active_slot_reconciliation")
    if isinstance(active_slot_reconciliation, dict):
        active_branch_cap_context["active_slot_reconciliation"] = dict(
            active_slot_reconciliation
        )
    if not clean_fork_selected:
        reason = "not_applicable"
    elif not_selected_reason == "clean_fork_required_for_new_mechanism":
        reason = "new_mechanism_requires_clean_fork"
    elif not_selected_reason:
        reason = "clean_fork_selected_instead_of_same_branch"
    else:
        reason = "no_active_same_mechanism_branch"
    return {
        "reason": reason,
        "selected_policy": selected_policy,
        "clean_fork_reason": clean_fork_reason,
        "same_branch_refinement_not_selected_reason": not_selected_reason,
        "active_branch_cap_context": active_branch_cap_context,
    }


def _post_finalizer_actual_branch_action(
    result: StepResult,
    branch: Branch,
) -> str:
    if result.action == "soft_abandon":
        return "soft_abandon"
    release_reason = branch_active_slot_release_reason(branch)
    if release_reason:
        return f"{release_reason}_released"
    if not branch_counts_toward_active_slots(branch):
        return "inactive_after_finalizer"
    return "continue_same_branch"


def _post_finalizer_branch_metadata(
    branch: Branch,
    *,
    actual_branch_action: str,
) -> dict[str, Any]:
    release_reason = branch_active_slot_release_reason(branch)
    counts_toward_active_slots = branch_counts_toward_active_slots(branch)
    metadata: dict[str, Any] = {
        "post_finalizer_branch_id": str(getattr(branch, "branch_id", "") or ""),
        "post_finalizer_branch_state": _branch_state_value(branch),
        "post_finalizer_branch_code_status": str(
            getattr(branch, "branch_code_status", "") or ""
        ),
        "post_finalizer_counts_toward_active_slots": counts_toward_active_slots,
        "post_finalizer_next_proposal_policy": (
            "same_branch_eligible"
            if actual_branch_action == "continue_same_branch"
            else "same_branch_not_selected"
            if actual_branch_action == "soft_abandon"
            else "clean_fork_or_other_branch_required"
        ),
    }
    if release_reason:
        metadata["post_finalizer_active_slot_release_reason"] = release_reason
    lifecycle_action = _post_finalizer_lifecycle_action(
        branch,
        release_reason=release_reason,
    )
    if lifecycle_action:
        metadata["post_finalizer_lifecycle_action"] = lifecycle_action
    lifecycle_codes = _branch_lifecycle_action_reason_codes(branch)
    if lifecycle_codes:
        metadata["post_finalizer_lifecycle_action_reason_codes"] = list(
            lifecycle_codes
        )
    return metadata


def _post_finalizer_lifecycle_action(
    branch: Branch,
    *,
    release_reason: str,
) -> str:
    reason_set = set(_branch_lifecycle_action_reason_codes(branch))
    if BRANCH_LIFECYCLE_ARCHIVE_LINEAGE in reason_set:
        return "archive_lineage"
    if BRANCH_LIFECYCLE_PARK_LINEAGE in reason_set:
        return "park_lineage"
    if BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT in reason_set:
        return "rollback_to_checkpoint"
    if BRANCH_LIFECYCLE_RETAIN_CHECKPOINT in reason_set:
        return "retain_checkpoint"
    if release_reason == "parked_lineage":
        return "park_lineage"
    if release_reason == "retained_checkpoint_no_effect_current_head":
        return "retain_checkpoint"
    return ""


def _branch_lifecycle_action_reason_codes(branch: Branch) -> tuple[str, ...]:
    block = getattr(branch, "last_branch_lifecycle_policy_block", {}) or {}
    if not isinstance(block, dict):
        return ()
    codes = block.get("lifecycle_action_reason_codes")
    if isinstance(codes, str):
        return (codes,) if codes else ()
    if not isinstance(codes, (list, tuple, set)):
        return ()
    return tuple(dict.fromkeys(str(code) for code in codes if str(code)))


def _branch_state_value(branch: Branch) -> str:
    state = getattr(branch, "state", "")
    return str(getattr(state, "value", state) or "")


def _scheduler_aligned_result_reason(
    reason: str,
    *,
    actual_branch_action: str,
    scheduler_slot: str,
) -> str:
    text = str(reason or "")
    stale_phrase = "improve the same branch"
    if stale_phrase not in text:
        return text
    if actual_branch_action == "explore_new_clean_fork":
        replacement = "create a clean fork"
    elif actual_branch_action.endswith("_released"):
        replacement = "release the branch slot"
    elif scheduler_slot == "repair_diagnostic":
        replacement = "repair/refine the same branch"
    else:
        replacement = "refine the same branch"
    return text.replace(stale_phrase, replacement)


def _finalize_scheduler_result(
    result: StepResult,
    sched: Any,
    record_scheduler_result: Optional[Callable[[StepResult], None]] = None,
) -> StepResult:
    result = _with_scheduler_metadata(result, sched)
    if record_scheduler_result is not None:
        try:
            record_scheduler_result(result)
        except Exception as exc:  # pragma: no cover - persistence must not stop a step
            logger.debug("record_scheduler_result failed: %s", exc)
    return result
