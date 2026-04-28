"""PlateauController — early-stop + idle counter + forced-locus diversification.

Extracted from CampaignManager (v0.3 §B1 per optimization-design doc).
Holds responsibilities related to "when should the campaign stop" and "should
the next branch be pushed into a different operator locus":

  - idle-round tracking (`_rounds_since_last_promote`)
  - EarlyStopController wrapper
  - forced-locus holder (set by soft-stagnation, consumed on next branch creation)

Does NOT hold (left in CampaignManager for now — v0.3 minimum extraction):
  - stagnation detection (_run_stagnation_check / diagnosis)
  - soft-stagnation accumulator (_check_soft_stagnation — reads from
    _soft_abandon_streak which the main loop manages)

v1.0 Phase 1 will extend this to own the stagnation pipeline as well.
"""
from __future__ import annotations

from typing import List, Optional

from scion.core.early_stop import EarlyStopController, EarlyStopDecision
from scion.core.stagnation import StagnationSignal
from scion.proposal.saturation import SaturationSignal


class PlateauController:
    """Owns idle-round accounting and early-stop decisioning."""

    def __init__(
        self,
        *,
        early_stop: Optional[EarlyStopController] = None,
    ) -> None:
        self._early_stop = early_stop or EarlyStopController()
        self._rounds_since_last_promote: int = 0
        self._forced_next_locus: Optional[str] = None

    # ------------------------------------------------------------------
    # Idle counter
    # ------------------------------------------------------------------

    @property
    def rounds_since_last_promote(self) -> int:
        return self._rounds_since_last_promote

    def on_explore_step(self) -> None:
        """Explore step generates a new hypothesis — counts as idle.

        v0.3 A2: an EXPLORE step (new hypothesis at screening) is 'idle' because
        no promotion was produced. The counter is reset by `on_promote()`.
        """
        self._rounds_since_last_promote += 1

    def on_eval_step(self, action_label: str) -> None:
        """Eval step increments idle only for screening-expand self-loops.

        Per v0.3 A2 regression fix: branches that reach VALIDATING or FROZEN_TESTING
        are productive activity even when they ultimately fail — don't penalise
        them with idle accounting that would trigger budget_efficiency early-stop.
        """
        if action_label == "explore":
            self._rounds_since_last_promote += 1

    def on_promote(self) -> None:
        """Called when a candidate is promoted — reset idle counter."""
        self._rounds_since_last_promote = 0

    # ------------------------------------------------------------------
    # Forced locus
    # ------------------------------------------------------------------

    def set_forced_locus(self, locus: Optional[str]) -> None:
        self._forced_next_locus = locus

    @property
    def forced_next_locus(self) -> Optional[str]:
        return self._forced_next_locus

    def consume_forced_locus(self) -> Optional[str]:
        """Consume and return forced locus (one-shot). Returns None if unset."""
        forced = self._forced_next_locus
        if forced is not None:
            self._forced_next_locus = None
        return forced

    # ------------------------------------------------------------------
    # Early-stop
    # ------------------------------------------------------------------

    def should_early_stop(
        self,
        saturation_signals: List[SaturationSignal],
        stagnation_signals: List[StagnationSignal],
        *,
        total_rounds: int = 0,
    ) -> EarlyStopDecision:
        return self._early_stop.should_early_stop(
            saturation_signals,
            stagnation_signals,
            total_rounds=total_rounds,
            rounds_since_last_promote=self._rounds_since_last_promote,
        )

    @property
    def early_stop(self) -> EarlyStopController:
        """Access the underlying controller (read-only use only)."""
        return self._early_stop
