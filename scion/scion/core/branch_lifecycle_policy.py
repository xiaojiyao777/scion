"""Branch lifecycle policy for low-signal screening results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scion.core.models import DecisionFeatures


BranchLifecycleAction = Literal["keep_exploring", "soft_abandon"]

SCREENING_WEAK_SIGNAL_CONTINUE = "SCREENING_WEAK_SIGNAL_CONTINUE"
SCREENING_NEUTRAL_SIGNAL_CONTINUE = "SCREENING_NEUTRAL_SIGNAL_CONTINUE"
SCREENING_ZERO_WIN_STREAK_CONTINUE = "SCREENING_ZERO_WIN_STREAK_CONTINUE"
SCREENING_ZERO_WIN_STREAK_EXHAUSTED = "SCREENING_ZERO_WIN_STREAK_EXHAUSTED"
SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN = (
    "SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN"
)
SCREENING_SOFT_ABANDON_NEGATIVE_DELTA = "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA"
SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN = "SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN"
SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE = (
    "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE"
)
SCREENING_STALE_RESCREEN_FAIL = "SCREENING_STALE_RESCREEN_FAIL"


@dataclass(frozen=True)
class BranchLifecycleDecision:
    action: BranchLifecycleAction
    reason_codes: tuple[str, ...]
    next_zero_win_streak: int

    @property
    def soft_abandon(self) -> bool:
        return self.action == "soft_abandon"


@dataclass(frozen=True)
class BranchLifecyclePolicy:
    """Classify low-win screening branches without problem-specific semantics."""

    low_win_rate_threshold: float = 0.3
    zero_win_streak_limit: int = 3
    soft_runtime_ratio_threshold: float = 1.10
    high_runtime_regression_rate: float = 0.90

    def decide(
        self,
        features: DecisionFeatures,
        *,
        current_zero_win_streak: int = 0,
    ) -> BranchLifecycleDecision:
        if not self._eligible_low_win_screening(features):
            return BranchLifecycleDecision(
                action="keep_exploring",
                reason_codes=(),
                next_zero_win_streak=current_zero_win_streak,
            )

        wins = max(0, int(features.wins or 0))
        losses = max(0, int(features.losses or 0))
        ties = max(0, int(features.ties or 0))
        next_zero_win_streak = 0 if wins > 0 else current_zero_win_streak + 1

        if features.stale:
            return BranchLifecycleDecision(
                action="soft_abandon",
                reason_codes=(SCREENING_STALE_RESCREEN_FAIL,),
                next_zero_win_streak=next_zero_win_streak,
            )

        soft_reasons = self._soft_abandon_reasons(features, wins=wins, losses=losses)
        if soft_reasons:
            return BranchLifecycleDecision(
                action="soft_abandon",
                reason_codes=soft_reasons,
                next_zero_win_streak=next_zero_win_streak,
            )

        if wins == 0 and next_zero_win_streak >= self.zero_win_streak_limit:
            return BranchLifecycleDecision(
                action="soft_abandon",
                reason_codes=(SCREENING_ZERO_WIN_STREAK_EXHAUSTED,),
                next_zero_win_streak=next_zero_win_streak,
            )

        if wins > 0:
            return BranchLifecycleDecision(
                action="keep_exploring",
                reason_codes=(SCREENING_WEAK_SIGNAL_CONTINUE,),
                next_zero_win_streak=0,
            )

        reason = (
            SCREENING_NEUTRAL_SIGNAL_CONTINUE
            if self._mostly_ties(features, ties=ties, losses=losses)
            else SCREENING_ZERO_WIN_STREAK_CONTINUE
        )
        return BranchLifecycleDecision(
            action="keep_exploring",
            reason_codes=(reason,),
            next_zero_win_streak=next_zero_win_streak,
        )

    def _eligible_low_win_screening(self, features: DecisionFeatures) -> bool:
        return (
            features.stage == "screening"
            and features.win_rate is not None
            and features.win_rate < self.low_win_rate_threshold
            and not features.telemetry_validation_repairable
        )

    def _soft_abandon_reasons(
        self,
        features: DecisionFeatures,
        *,
        wins: int,
        losses: int,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if losses > 0 and wins == 0:
            reasons.append(SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN)
        if features.median_delta is not None and features.median_delta < 0:
            reasons.append(SCREENING_SOFT_ABANDON_NEGATIVE_DELTA)
        if (
            features.runtime_ratio_median is not None
            and features.runtime_ratio_median > self.soft_runtime_ratio_threshold
        ):
            reasons.append(SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN)
        if (
            features.runtime_regression_rate is not None
            and features.runtime_regression_rate >= self.high_runtime_regression_rate
        ):
            reasons.append(SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE)
        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _mostly_ties(
        features: DecisionFeatures,
        *,
        ties: int,
        losses: int,
    ) -> bool:
        observed = features.valid_pairs or features.attempted_pairs or features.n_cases
        if observed <= 0:
            observed = ties + losses
        if observed <= 0:
            return False
        return ties / observed >= 0.5


__all__ = [
    "BranchLifecycleDecision",
    "BranchLifecyclePolicy",
    "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
    "SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN",
    "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",
    "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE",
    "SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN",
    "SCREENING_STALE_RESCREEN_FAIL",
    "SCREENING_WEAK_SIGNAL_CONTINUE",
    "SCREENING_ZERO_WIN_STREAK_CONTINUE",
    "SCREENING_ZERO_WIN_STREAK_EXHAUSTED",
]
