from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from scion.core.models import Branch, BranchState


@dataclass
class TerminationConfig:
    max_experiments: int = 1000
    max_wall_clock_hours: float = 24.0
    stagnation_limit: int = 10  # consecutive abandoned branches
    soft_stagnation_limit: int = 15  # consecutive T4 soft-abandoned → force diversify


@dataclass
class CampaignState:
    n_experiments: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    recent_abandoned_count: int = 0
    active_branches: List[Branch] = field(default_factory=list)
    can_create_new: bool = True
    early_stop_detected: bool = False
    early_stop_reason: str = ""


_ACTIVE_STATES = frozenset({
    BranchState.EXPLORE,
    BranchState.EXPLORE_EXPAND,
    BranchState.READY_VALIDATE,
    BranchState.VALIDATING,
    BranchState.VALIDATING_EXPAND,
    BranchState.READY_FROZEN,
    BranchState.FROZEN_TESTING,
    BranchState.STALE,
    BranchState.STALE_WEIGHT_UPDATE,
    BranchState.BLOCKED_INFRA,
})


class TerminationChecker:
    """
    Checks campaign termination conditions:
    1. max_experiments reached
    2. max_wall_clock_hours exceeded
    3. stagnation: N consecutive abandoned branches
    4. no active branches and cannot create new ones
    """

    def __init__(self, config: TerminationConfig | None = None) -> None:
        self.config = config or TerminationConfig()

    def should_stop(self, campaign_state: CampaignState) -> bool:
        return (
            self._max_experiments_reached(campaign_state)
            or self._wall_clock_exceeded(campaign_state)
            or self._stagnation_detected(campaign_state)
            or self._no_progress_possible(campaign_state)
            or self._early_stop_detected(campaign_state)
        )

    # ------------------------------------------------------------------
    # Individual conditions (testable in isolation)
    # ------------------------------------------------------------------

    def _max_experiments_reached(self, state: CampaignState) -> bool:
        return state.n_experiments >= self.config.max_experiments

    def _wall_clock_exceeded(self, state: CampaignState) -> bool:
        elapsed_hours = (datetime.now() - state.start_time).total_seconds() / 3600.0
        return elapsed_hours >= self.config.max_wall_clock_hours

    def _stagnation_detected(self, state: CampaignState) -> bool:
        return state.recent_abandoned_count >= self.config.stagnation_limit

    def _no_progress_possible(self, state: CampaignState) -> bool:
        has_active = any(b.state in _ACTIVE_STATES for b in state.active_branches)
        return not has_active and not state.can_create_new

    def _early_stop_detected(self, state: CampaignState) -> bool:
        return state.early_stop_detected
