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
    rule: Literal["all_hard", "saturated_stagnant", "override", "continue"]


class EarlyStopController:
    """Decides whether a campaign should early-stop based on combined signals.

    Rules (checked in order):
    1. force_continue override → never stop
    2. All objectives hard-saturated → stop
    3. All objectives high-saturated (hard or soft) AND stagnation plateau → stop
    4. Otherwise → continue
    """

    def __init__(self, *, force_continue: bool = False) -> None:
        self._force_continue = force_continue

    def should_early_stop(
        self,
        saturation_signals: List[SaturationSignal],
        stagnation_signals: List[StagnationSignal],
    ) -> EarlyStopDecision:
        if self._force_continue:
            return EarlyStopDecision(
                stop=False, reason="force_continue override active", rule="override",
            )

        if not saturation_signals:
            return EarlyStopDecision(
                stop=False, reason="no saturation data", rule="continue",
            )

        all_hard = all(s.saturation_type == "hard" for s in saturation_signals)
        if all_hard:
            return EarlyStopDecision(
                stop=True,
                reason="all objectives at absolute minimum",
                rule="all_hard",
            )

        all_high = all(s.saturation_level == "high" for s in saturation_signals)
        has_plateau = any(s.kind == "plateau" for s in stagnation_signals)
        if all_high and has_plateau:
            return EarlyStopDecision(
                stop=True,
                reason="all objectives high-saturated with stagnation plateau",
                rule="saturated_stagnant",
            )

        return EarlyStopDecision(
            stop=False, reason="objectives not fully saturated", rule="continue",
        )
