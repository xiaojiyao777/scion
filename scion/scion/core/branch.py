from __future__ import annotations
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from scion.core.models import (
    Branch, BranchState, ChampionState, Decision, ExperimentStage,
)


class StateTransitionError(Exception):
    pass


_ACTIVE_STATES = frozenset({
    BranchState.EXPLORE,
    BranchState.EXPLORE_EXPAND,
    BranchState.READY_VALIDATE,
    BranchState.VALIDATING,
    BranchState.VALIDATING_EXPAND,
    BranchState.READY_FROZEN,
    BranchState.FROZEN_TESTING,
})

# Maps (Decision, current_state) → new_state
# ABANDON is allowed from any state
_DECISION_TRANSITIONS: Dict[Decision, Dict[BranchState, BranchState]] = {
    Decision.CONTINUE_EXPLORE: {
        BranchState.EXPLORE: BranchState.EXPLORE,
        BranchState.NEW: BranchState.EXPLORE,
        # Expand screening didn't yield a strong enough win_rate — fall back to
        # a fresh explore iteration on the same branch.
        BranchState.EXPLORE_EXPAND: BranchState.EXPLORE,
    },
    Decision.EXPAND_SCREENING: {
        BranchState.EXPLORE: BranchState.EXPLORE_EXPAND,
        BranchState.NEW: BranchState.EXPLORE_EXPAND,
        BranchState.EXPLORE_EXPAND: BranchState.EXPLORE_EXPAND,  # self-loop: keep expanding
    },
    Decision.QUEUE_VALIDATE: {
        BranchState.EXPLORE: BranchState.READY_VALIDATE,
        BranchState.NEW: BranchState.READY_VALIDATE,
        BranchState.EXPLORE_EXPAND: BranchState.READY_VALIDATE,
    },
    Decision.EXPAND_VALIDATION: {
        BranchState.VALIDATING: BranchState.VALIDATING_EXPAND,
        # Note: VALIDATING_EXPAND + EXPAND_VALIDATION is intentionally unmapped.
        # DecisionEngine._decide_validation enforces validation_expand_count >= 1 →
        # QUEUE_FROZEN (VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS) or ABANDON
        # (VALIDATION_EXPAND_EXHAUSTED_FAIL), so this (state, decision) combination
        # cannot be produced in practice. If the guard is ever loosened, add
        # VALIDATING_EXPAND: VALIDATING_EXPAND here (self-loop, mirroring
        # EXPLORE_EXPAND) and set a validation_expand_count cap elsewhere.
    },
    Decision.QUEUE_FROZEN: {
        BranchState.VALIDATING: BranchState.READY_FROZEN,
        BranchState.VALIDATING_EXPAND: BranchState.READY_FROZEN,
    },
    Decision.PROMOTE: {
        BranchState.FROZEN_TESTING: BranchState.PROMOTED,
    },
}


class BranchController:
    def __init__(self) -> None:
        self._branches: Dict[str, Branch] = {}
        # Stores previous state for BLOCKED_INFRA recovery
        self._pre_infra_state: Dict[str, BranchState] = {}

    def create_branch(self, champion: ChampionState) -> Branch:
        branch_id = str(uuid.uuid4())
        branch = Branch(
            branch_id=branch_id,
            state=BranchState.EXPLORE,
            base_champion_id=champion.version,
            base_champion_hash=champion.code_snapshot_hash,
        )
        self._branches[branch_id] = branch
        return branch

    def apply_decision(self, branch_id: str, decision: Decision) -> None:
        """Apply a Decision to a branch, performing the appropriate state transition."""
        branch = self._get(branch_id)

        if decision == Decision.ABANDON:
            branch.state = BranchState.ABANDONED
            branch.updated_at = datetime.now()
            return

        transitions = _DECISION_TRANSITIONS.get(decision, {})
        new_state = transitions.get(branch.state)
        if new_state is None:
            raise StateTransitionError(
                f"Invalid transition: state={branch.state.value} + decision={decision.value}"
            )
        branch.state = new_state
        branch.updated_at = datetime.now()

    def schedule_branch(self, branch_id: str) -> None:
        """
        Advance a READY_* branch to its running state (called by the scheduler
        when it selects a branch for execution).
        Also handles EXPLORE_EXPAND → EXPLORE and VALIDATING_EXPAND → VALIDATING
        when the expansion run completes.
        """
        branch = self._get(branch_id)
        transitions = {
            BranchState.READY_VALIDATE: BranchState.VALIDATING,
            BranchState.READY_FROZEN: BranchState.FROZEN_TESTING,
            BranchState.EXPLORE_EXPAND: BranchState.EXPLORE,
            BranchState.VALIDATING_EXPAND: BranchState.VALIDATING,
        }
        new_state = transitions.get(branch.state)
        if new_state is None:
            raise StateTransitionError(
                f"Cannot schedule branch in state {branch.state.value}"
            )
        branch.state = new_state
        branch.updated_at = datetime.now()

    def mark_all_stale(self, new_champion_id: int) -> List[str]:
        """
        Mark every active branch STALE after a champion change.
        FROZEN_TESTING branches are excluded — they have already passed
        screening + validation and should be allowed to complete.
        Returns the list of affected branch_ids.
        """
        affected: List[str] = []
        for branch in self._branches.values():
            if branch.state in _ACTIVE_STATES and branch.state != BranchState.FROZEN_TESTING:
                branch.state = BranchState.STALE
                branch.updated_at = datetime.now()
                affected.append(branch.branch_id)
        return affected

    def mark_stale_for_weight_update(self, champion_version: int) -> List[str]:
        """Mark branches stale after a weight-opt update (stage-aware).

        Only screening/explore branches are marked STALE_WEIGHT_UPDATE.
        Validation and frozen branches continue with old weights — they will
        be re-evaluated on next promotion cycle.
        """
        _SCREENING_STATES = frozenset({
            BranchState.EXPLORE,
            BranchState.EXPLORE_EXPAND,
            BranchState.NEW,
        })
        affected: List[str] = []
        for branch in self._branches.values():
            if branch.state in _SCREENING_STATES:
                branch.state = BranchState.STALE_WEIGHT_UPDATE
                branch.updated_at = datetime.now()
                affected.append(branch.branch_id)
        return affected

    def reconcile_stale(
        self, branch_id: str, success: bool, new_champion: ChampionState
    ) -> None:
        """
        Complete stale reconcile: if reconcile succeeded → EXPLORE (on new champion),
        else → ABANDONED.
        """
        branch = self._get(branch_id)
        if branch.state not in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            raise StateTransitionError(
                f"Branch {branch_id} is not STALE (state={branch.state.value})"
            )
        if success:
            branch.state = BranchState.EXPLORE
            branch.base_champion_id = new_champion.version
            branch.base_champion_hash = new_champion.code_snapshot_hash
        else:
            branch.state = BranchState.ABANDONED
        branch.updated_at = datetime.now()

    def is_blocked(self, branch_id: str) -> bool:
        """Return True if the branch is in BLOCKED_INFRA state."""
        return self._get(branch_id).state == BranchState.BLOCKED_INFRA

    def block_infra(self, branch_id: str) -> None:
        """Transition an active branch to BLOCKED_INFRA, saving prior state."""
        branch = self._get(branch_id)
        if branch.state not in _ACTIVE_STATES:
            raise StateTransitionError(
                f"Cannot block_infra from state {branch.state.value}"
            )
        self._pre_infra_state[branch_id] = branch.state
        branch.state = BranchState.BLOCKED_INFRA
        branch.updated_at = datetime.now()

    def unblock_infra(self, branch_id: str) -> None:
        """Restore a BLOCKED_INFRA branch to its previous state."""
        branch = self._get(branch_id)
        if branch.state != BranchState.BLOCKED_INFRA:
            raise StateTransitionError(
                f"Branch {branch_id} is not BLOCKED_INFRA"
            )
        prev = self._pre_infra_state.pop(branch_id, BranchState.EXPLORE)
        branch.state = prev
        branch.updated_at = datetime.now()

    def get_code_base(self, branch_id: str) -> str:
        """
        Return the code-base identifier for the branch (§4.5):
        - "champion"          if branch is STALE, or current_code_hash is None,
                              or last_clean_code_hash is None (never passed verification)
        - "branch_workspace"  if both hashes are set — caller should reuse the
                              existing branch workspace rather than copying from champion
        """
        branch = self._get(branch_id)
        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return "champion"
        if branch.current_code_hash is None:
            return "champion"
        if branch.last_clean_code_hash is None:
            return "champion"
        return "branch_workspace"

    def record_verification_result(
        self, branch_id: str, passed: bool, code_hash: str
    ) -> None:
        """Record the outcome of a verification run, updating code hashes."""
        branch = self._get(branch_id)
        branch.current_code_hash = code_hash
        if passed:
            branch.last_clean_code_hash = code_hash
        branch.updated_at = datetime.now()

    def record_candidate_code(self, branch_id: str, code_hash: str) -> None:
        """Record that a candidate patch has been applied (before verification).

        Only updates current_code_hash. last_clean_code_hash is NOT updated
        until verification actually passes (call record_verification_pass).
        """
        branch = self._get(branch_id)
        branch.current_code_hash = code_hash
        branch.updated_at = datetime.now()

    def record_verification_pass(self, branch_id: str, code_hash: str) -> None:
        """Record that verification passed for the current candidate code.

        Updates both current_code_hash and last_clean_code_hash. Call this
        only after VerificationGate.run() returns passed=True.
        """
        branch = self._get(branch_id)
        branch.current_code_hash = code_hash
        branch.last_clean_code_hash = code_hash
        branch.updated_at = datetime.now()

    def next_stage(self, branch_id: str) -> ExperimentStage:
        """Determine the next experiment stage based on branch state."""
        branch = self._get(branch_id)
        if branch.state in (BranchState.EXPLORE, BranchState.EXPLORE_EXPAND):
            return ExperimentStage.SCREENING
        elif branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
            return ExperimentStage.VALIDATION
        elif branch.state == BranchState.FROZEN_TESTING:
            return ExperimentStage.FROZEN
        raise StateTransitionError(
            f"Cannot determine next_stage for state {branch.state.value}"
        )

    def get_active_branches(self) -> List[Branch]:
        """Return all branches that are not in terminal states."""
        terminal = {BranchState.PROMOTED, BranchState.ABANDONED}
        return [b for b in self._branches.values() if b.state not in terminal]

    def get_branch(self, branch_id: str) -> Branch:
        return self._get(branch_id)

    def _get(self, branch_id: str) -> Branch:
        b = self._branches.get(branch_id)
        if b is None:
            raise KeyError(f"Branch not found: {branch_id}")
        return b
