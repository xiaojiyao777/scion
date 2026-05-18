"""Failure recovery lifecycle service for campaign branches."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.failure.router import FailureRouter

logger = logging.getLogger(__name__)


class BudgetLike(Protocol):
    used: int


class HypothesisStoreLike(Protocol):
    def save(self, record: HypothesisRecord) -> Any:
        ...


class BranchStoreLike(Protocol):
    def save(self, branch: Branch) -> Any:
        ...


class RegistryLike(Protocol):
    def record_event(self, event: dict[str, Any]) -> Any:
        ...


@dataclass
class FailureLifecycleService:
    """Route failures and apply branch recovery side effects."""

    failure_router: FailureRouter
    budget: BudgetLike
    failure_streak: MutableMapping[str, int]
    total_failures: MutableMapping[str, int]
    branch_controller: BranchController
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    hypothesis_store: HypothesisStoreLike
    branch_store: BranchStoreLike | None
    registry: RegistryLike | None
    campaign_id: str
    get_champion: Callable[[], ChampionState | None]
    record_hard_abandon: Callable[[str, str], None]
    clock: Callable[[], datetime] = datetime.now
    status_heartbeat: Callable[[str, Branch, FailureEvent | None], None] | None = None

    @classmethod
    def from_owner(cls, owner: Any) -> "FailureLifecycleService":
        """Build from a CampaignManager-like object.

        Kept for backward-compatible tests that bind CampaignManager methods to a
        small stub instead of constructing a full manager.
        """
        def _status_heartbeat(
            event_kind: str,
            _branch: Branch,
            _failure: FailureEvent | None,
        ) -> None:
            write_status = getattr(owner, "_write_status", None)
            if not callable(write_status):
                return
            try:
                write_status()
            except Exception:
                logger.debug(
                    "Status heartbeat after %s failed",
                    event_kind,
                    exc_info=True,
                )

        return cls(
            failure_router=owner._failure_router,
            budget=owner._budget,
            failure_streak=owner._failure_streak,
            total_failures=owner._total_failures,
            branch_controller=owner._branch_ctrl,
            branch_hypotheses=owner._branch_hypotheses,
            branch_patches=owner._branch_patches,
            hypothesis_store=owner._hyp_store,
            branch_store=getattr(owner, "_branch_store", None),
            registry=getattr(owner, "_registry", None),
            campaign_id=getattr(owner, "_campaign_id", ""),
            get_champion=lambda: getattr(owner, "_champion", None),
            record_hard_abandon=owner._record_hard_abandon,
            status_heartbeat=_status_heartbeat,
        )

    def handle_failure(
        self,
        branch: Branch,
        failure: FailureEvent,
        *,
        hypothesis_already_recorded: bool = False,
    ) -> None:
        """Route a failure and execute the selected recovery action."""
        fcode = failure.category
        self.failure_streak[fcode] = self.failure_streak.get(fcode, 0) + 1
        self.total_failures[fcode] = self.total_failures.get(fcode, 0) + 1

        action = self.failure_router.route(
            failure,
            branch,
            streak=self.failure_streak[fcode],
            total=self.total_failures[fcode],
        )
        branch.retry_count += 1
        branch.failure_codes.append(failure.category.upper())
        logger.debug(
            "Branch %s: failure=%s streak=%d -> action=%s (budget=%s)",
            branch.branch_id,
            failure.category,
            self.failure_streak[fcode],
            action.action,
            action.consumes_budget,
        )
        if action.consumes_budget:
            self.budget.used += 1
        if action.writes_hypothesis_memory and not hypothesis_already_recorded:
            self._write_hypothesis_memory(branch)

        bid = branch.branch_id
        if action.action == "retry_llm":
            self._retry_llm(branch)
        elif action.action == "retry_infra":
            self._retry_infra(branch)
        elif action.action == "discard":
            self._discard(branch)
        elif action.action == "abandon":
            self._abandon(branch, "failure_action_abandon")
        elif action.action == "infra_suspected":
            self._infra_suspected(branch, fcode)
        elif action.action == "abandon_fast":
            self._abandon_fast(branch, fcode)
        elif action.action == "fail_closed":
            self._fail_closed(branch, fcode)

        self._persist_branch_state(bid)
        self._emit_status_heartbeat("failure_handled", branch, failure)

    def tick_blocked_branches(self) -> None:
        """Advance blocked infra branches and auto-unblock after three rounds."""
        for branch in self.branch_controller.get_active_branches():
            if branch.state != BranchState.BLOCKED_INFRA:
                continue
            branch.blocked_rounds += 1
            if branch.blocked_rounds >= 3:
                logger.info(
                    "Branch %s: auto-unblocking after %d blocked rounds",
                    branch.branch_id,
                    branch.blocked_rounds,
                )
                try:
                    self.branch_controller.unblock_infra(branch.branch_id)
                except StateTransitionError as exc:
                    logger.debug(
                        "Branch %s: unblock_infra skipped: %s",
                        branch.branch_id,
                        exc,
                    )
                branch.blocked_rounds = 0
                branch.consecutive_llm_retries = 0
                self._persist_branch_state(branch.branch_id)
                self._emit_status_heartbeat("branch_unblocked", branch, None)

    def _write_hypothesis_memory(self, branch: Branch) -> None:
        hyp = self.branch_hypotheses.get(branch.branch_id)
        if not hyp:
            return
        champion = self.get_champion()
        record = HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=branch.branch_id,
            change_locus=hyp.change_locus,
            action=hyp.action,
            status="blacklisted",
            target_file=hyp.target_file,
            hypothesis_text=hyp.hypothesis_text,
            base_champion_version=champion.version if champion else 0,
            predicted_direction=hyp.predicted_direction,
            target_objectives=hyp.target_objectives,
            protected_objectives=hyp.protected_objectives,
            novelty_signature=dict(hyp.novelty_signature or {}),
            mechanism_changes=tuple(hyp.mechanism_changes or ()),
        )
        self.hypothesis_store.save(record)

    def _retry_llm(self, branch: Branch) -> None:
        bid = branch.branch_id
        branch.consecutive_llm_retries += 1
        if branch.consecutive_llm_retries >= 3:
            logger.info(
                "Branch %s: retry_llm exhausted (%d consecutive) - downgrading to discard",
                bid,
                branch.consecutive_llm_retries,
            )
            branch.consecutive_llm_retries = 0
            branch.pending_retry = False
            self.branch_patches.pop(bid, None)
            branch.current_code_hash = branch.last_clean_code_hash
            if branch.state not in (BranchState.ABANDONED, BranchState.PROMOTED):
                branch.state = BranchState.EXPLORE
                branch.updated_at = self.clock()
        else:
            branch.pending_retry = True

    def _retry_infra(self, branch: Branch) -> None:
        bid = branch.branch_id
        branch.consecutive_llm_retries = 0
        branch.pending_retry = False
        branch.infra_block_count += 1
        if branch.infra_block_count >= 2:
            logger.warning(
                "Branch %s: permanent infra failure (block #%d) - abandoning",
                bid,
                branch.infra_block_count,
            )
            try:
                self.branch_controller.apply_decision(bid, Decision.ABANDON)
                self.record_hard_abandon(bid, "infra_permanent")
            except StateTransitionError:
                pass
        else:
            logger.info("Branch %s: infra failure - blocking for 3 rounds", bid)
            try:
                self.branch_controller.block_infra(bid)
                branch.blocked_rounds = 0
            except StateTransitionError as exc:
                logger.debug("Branch %s: block_infra skipped: %s", bid, exc)

    def _discard(self, branch: Branch) -> None:
        bid = branch.branch_id
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        self.branch_patches.pop(bid, None)
        branch.current_code_hash = branch.last_clean_code_hash
        if branch.state not in (
            BranchState.ABANDONED,
            BranchState.PROMOTED,
            BranchState.STALE,
            BranchState.STALE_WEIGHT_UPDATE,
        ):
            branch.state = BranchState.EXPLORE
            branch.updated_at = self.clock()

    def _abandon(self, branch: Branch, reason: str) -> None:
        bid = branch.branch_id
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        try:
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, reason)
        except StateTransitionError:
            pass

    def _infra_suspected(self, branch: Branch, failure_code: str) -> None:
        bid = branch.branch_id
        logger.warning(
            "Branch %s: infra_suspected after %d consecutive '%s' failures - blocking",
            bid,
            self.failure_streak[failure_code],
            failure_code,
        )
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        self._record_failure_event(
            branch_id=bid,
            event_kind="infra_suspected",
            failure_code=failure_code,
            extra={
                "streak": self.failure_streak[failure_code],
                "suggested_action": "check_environment",
            },
        )
        try:
            self.branch_controller.block_infra(bid)
            branch.blocked_rounds = 0
        except StateTransitionError as exc:
            logger.debug(
                "Branch %s: block_infra (infra_suspected) skipped: %s",
                bid,
                exc,
            )

    def _abandon_fast(self, branch: Branch, failure_code: str) -> None:
        bid = branch.branch_id
        logger.warning(
            "Branch %s: abandon_fast after %d consecutive '%s' failures",
            bid,
            self.failure_streak[failure_code],
            failure_code,
        )
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        self._record_failure_event(
            branch_id=bid,
            event_kind="abandon_fast",
            failure_code=failure_code,
            extra={"streak": self.failure_streak[failure_code]},
        )
        try:
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "failure_action_abandon_fast")
        except StateTransitionError:
            pass

    def _fail_closed(self, branch: Branch, failure_code: str) -> None:
        bid = branch.branch_id
        logger.warning(
            "Branch %s: fail_closed for deterministic control failure '%s'",
            bid,
            failure_code,
        )
        branch.pending_retry = False
        branch.consecutive_llm_retries = 0
        self._record_failure_event(
            branch_id=bid,
            event_kind="framework_control_fail_closed",
            failure_code=failure_code,
            extra={"streak": self.failure_streak[failure_code]},
        )
        try:
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, f"{failure_code}_fail_closed")
        except StateTransitionError:
            pass

    def _emit_status_heartbeat(
        self,
        event_kind: str,
        branch: Branch,
        failure: FailureEvent | None,
    ) -> None:
        if self.status_heartbeat is None:
            return
        try:
            self.status_heartbeat(event_kind, branch, failure)
        except Exception:
            logger.debug(
                "Status heartbeat after %s failed",
                event_kind,
                exc_info=True,
            )

    def _record_failure_event(
        self,
        *,
        branch_id: str,
        event_kind: str,
        failure_code: str,
        extra: dict[str, Any],
    ) -> None:
        if self.registry is None:
            return
        try:
            self.registry.record_event(
                {
                    "campaign_id": self.campaign_id,
                    "branch_id": branch_id,
                    "timestamp": self.clock().isoformat(),
                    "event_kind": event_kind,
                    "failure_code": failure_code,
                    **extra,
                }
            )
        except Exception:
            pass

    def _persist_branch_state(self, branch_id: str) -> None:
        if self.branch_store is None:
            return
        try:
            branch = self.branch_controller.get_branch(branch_id)
            if branch:
                self.branch_store.save(branch)
        except Exception as exc:
            logger.debug("BranchStore.save (failure) failed: %s", exc)
