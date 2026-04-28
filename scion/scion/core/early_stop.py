"""EarlyStopController — combines saturation and stagnation signals for campaign early-stop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

from scion.core.stagnation import StagnationSignal
from scion.proposal.saturation import SaturationSignal


@dataclass(frozen=True)
class EarlyStopDecision:
    stop: bool
    reason: str
    rule: Literal[
        "all_bounded", "budget_efficiency", "diminishing_returns",
        "override", "continue",
    ]


class EarlyStopController:
    """Decides whether a campaign should early-stop based on combined signals.

    Rules (checked in order):
    1. force_continue override → never stop
    2. All objectives at known lower bounds → stop (mathematical certainty)
    3. Idle ratio exceeded → stop (budget waste detection)
    4. No promotions in window + stagnation plateau → stop (diminishing returns)
    5. Otherwise → continue
    """

    def __init__(
        self,
        *,
        force_continue: bool = False,
        max_idle_ratio: float = 0.6,
        stagnation_window: int = 25,
    ) -> None:
        self._force_continue = force_continue
        self._max_idle_ratio = max_idle_ratio
        self._stagnation_window = stagnation_window

    def should_early_stop(
        self,
        saturation_signals: List[SaturationSignal],
        stagnation_signals: List[StagnationSignal],
        *,
        total_rounds: int = 0,
        rounds_since_last_promote: int = 0,
    ) -> EarlyStopDecision:
        # Rule 1: override
        if self._force_continue:
            return EarlyStopDecision(
                stop=False, reason="force_continue override active", rule="override",
            )

        # Rule 2: all objectives at known lower bounds
        if saturation_signals:
            all_bounded = all(
                s.saturation_type == "hard" for s in saturation_signals
            )
            if all_bounded:
                return EarlyStopDecision(
                    stop=True,
                    reason="all objectives at known lower bounds",
                    rule="all_bounded",
                )

        # Rule 3: budget efficiency — too many idle rounds since last promote
        if total_rounds >= self._stagnation_window and rounds_since_last_promote > 0:
            idle_ratio = rounds_since_last_promote / total_rounds
            if idle_ratio > self._max_idle_ratio:
                return EarlyStopDecision(
                    stop=True,
                    reason=f"idle ratio {idle_ratio:.1%} exceeds {self._max_idle_ratio:.0%} "
                           f"({rounds_since_last_promote}/{total_rounds} rounds since last promote)",
                    rule="budget_efficiency",
                )

        # Rule 4: diminishing returns — stagnation window exhausted + plateau
        if rounds_since_last_promote >= self._stagnation_window:
            has_plateau = any(s.kind == "plateau" for s in stagnation_signals)
            if has_plateau:
                return EarlyStopDecision(
                    stop=True,
                    reason=f"no promotion in {rounds_since_last_promote} rounds with stagnation plateau",
                    rule="diminishing_returns",
                )

        return EarlyStopDecision(
            stop=False, reason="campaign progressing", rule="continue",
        )
