"""Failure recovery lifecycle service for campaign branches."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.models import (
    Branch,
    BranchState,
    FailureEvent,
    HypothesisProposal,
    PatchProposal,
)
from scion.failure.router import FailureRouter

logger = logging.getLogger(__name__)


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
    failure_streak: MutableMapping[str, int]
    total_failures: MutableMapping[str, int]
    branch_controller: BranchController
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_store: BranchStoreLike | None
    registry: RegistryLike | None
    campaign_id: str
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
            failure_streak=owner._failure_streak,
            total_failures=owner._total_failures,
            branch_controller=owner._branch_ctrl,
            branch_hypotheses=owner._branch_hypotheses,
            branch_patches=owner._branch_patches,
            branch_store=getattr(owner, "_branch_store", None),
            registry=getattr(owner, "_registry", None),
            campaign_id=getattr(owner, "_campaign_id", ""),
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

        action = self.failure_router.route(failure, branch)
        branch.failure_codes.append(failure.category.upper())
        logger.debug(
            "Branch %s: failure=%s -> action=%s outcome=%s",
            branch.branch_id,
            failure.category,
            action.action,
            action.execution_outcome.value,
        )
        del hypothesis_already_recorded

        bid = branch.branch_id
        if action.action == "block_infra":
            self._block_infra(branch)
        else:
            self._discard(branch)

        self._persist_branch_state(bid)
        self._emit_status_heartbeat("failure_handled", branch, failure)

    def operator_resume_infra(
        self,
        branch_id: str,
        *,
        operator_reason: str,
        operator_ack: str,
        failed_attempt_id: str | None = None,
    ) -> bool:
        """Explicitly resume one infra-blocked branch after durable operator ack.

        The append-only operator event is committed before the branch becomes
        schedulable. If the branch-state write fails, the in-memory transition
        is rolled back to BLOCKED_INFRA and the error is surfaced.
        """

        reason = str(operator_reason or "").strip()
        ack = str(operator_ack or "").strip()
        if not reason:
            raise ValueError("operator_reason is required to resume BLOCKED_INFRA")
        if not ack:
            raise ValueError("operator_ack is required to resume BLOCKED_INFRA")
        branch = self.branch_controller.get_branch(branch_id)
        if branch is None:
            raise KeyError(branch_id)
        if branch.state != BranchState.BLOCKED_INFRA:
            raise StateTransitionError(
                f"Branch {branch_id} is not BLOCKED_INFRA"
            )
        if self.registry is None:
            raise RuntimeError("operator infra resume requires an append-only registry")
        if self.branch_store is None:
            raise RuntimeError("operator infra resume requires durable branch state")

        event = {
            "event_id": str(uuid.uuid4()),
            "campaign_id": self.campaign_id,
            "branch_id": branch_id,
            "timestamp": self.clock().isoformat(),
            "event_kind": "operator_resume_infra",
            "stage": "operator_control",
            "audit_payload_json": json.dumps(
                {
                    "schema_version": "operator-resume-infra.v1",
                    "operator_reason": reason,
                    "operator_ack": ack,
                    "failed_attempt_id": (
                        str(failed_attempt_id).strip()
                        if failed_attempt_id is not None
                        and str(failed_attempt_id).strip()
                        else None
                    ),
                    "state_before": BranchState.BLOCKED_INFRA.value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
        # This write must succeed while the branch is still blocked.
        self.registry.record_event(event)

        self.branch_controller.resume_infra_after_operator_event(branch_id)
        try:
            self.branch_store.save(branch)
        except Exception:
            # Restore the exact safety property even though the append-only
            # operator request remains available for audit.
            if branch.state != BranchState.BLOCKED_INFRA:
                self.branch_controller.block_infra(branch_id)
            try:
                self.branch_store.save(branch)
            except Exception:
                pass
            raise
        self._emit_status_heartbeat("operator_resume_infra", branch, None)
        return True

    def _block_infra(self, branch: Branch) -> None:
        bid = branch.branch_id
        branch.infra_block_count += 1
        logger.info("Branch %s: infra failure - awaiting explicit operator resume", bid)
        if branch.state != BranchState.BLOCKED_INFRA:
            try:
                self.branch_controller.block_infra(bid)
            except (KeyError, StateTransitionError) as exc:
                logger.debug("Branch %s: block_infra skipped: %s", bid, exc)

    def _discard(self, branch: Branch) -> None:
        bid = branch.branch_id
        self.branch_hypotheses.pop(bid, None)
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

    def _persist_branch_state(self, branch_id: str) -> None:
        if self.branch_store is None:
            return
        branch = self.branch_controller.get_branch(branch_id)
        if branch:
            self.branch_store.save(branch)
