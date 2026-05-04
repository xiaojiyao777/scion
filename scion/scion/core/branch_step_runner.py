"""Branch-step execution boundary for CampaignManager."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, MutableMapping, Optional

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
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.core.frozen_budget import FROZEN_BUDGET_EXHAUSTED

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
        active = self.branch_controller.get_active_branches()
        sched = self.scheduler.select_next(active)

        if sched.action == "at_capacity":
            return StepResult(action="skip", reason="max_active_branches reached")

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
            return result

        branch = sched.branch
        assert branch is not None

        if branch.state in (BranchState.READY_VALIDATE, BranchState.READY_FROZEN):
            try:
                self.branch_controller.schedule_branch(branch.branch_id)
                self.persist_branch_state(branch.branch_id)
            except StateTransitionError as exc:
                logger.error("schedule_branch failed: %s", exc)
                return StepResult(
                    action="skip",
                    branch_id=branch.branch_id,
                    reason=str(exc),
                )

        branch = self.branch_controller.get_branch(branch.branch_id)

        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return self.run_reconcile_step_callback(branch)

        if branch.state == BranchState.EXPLORE:
            return self.run_explore_step(branch)

        if branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        ):
            try:
                return self.run_eval_step_callback(branch)
            except RuntimeError as exc:
                return self._handle_eval_runtime_error(branch, exc)

        logger.warning(
            "Branch %s in unexpected state %s - skipping",
            branch.branch_id,
            branch.state.value,
        )
        return StepResult(
            action="skip",
            branch_id=branch.branch_id,
            reason=f"unhandled state {branch.state.value}",
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
            return StepResult(action="reconcile", branch_id=bid, reason=reason)

        if patch is None:
            logger.info("Branch %s: no patch to reconcile - abandoning stale branch", bid)
            return abandon_stale("no patch to reconcile")

        hypothesis = self.branch_hypotheses.get(bid)
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

        contract_result = self.contract_gate.validate_patch(patch)
        if not contract_result.passed:
            logger.info(
                "Branch %s: reconcile patch failed contract gate: %s",
                bid,
                contract_result.failure_reason,
            )
            return abandon_stale(
                f"reconcile contract failed: {contract_result.failure_reason}"
            )

        champion_workspace = self.get_champion().code_snapshot_path
        verification_result = self.verification_gate.run(
            workspace,
            champion_workspace,
            patch,
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
