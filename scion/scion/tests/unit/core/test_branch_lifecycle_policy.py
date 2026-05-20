from __future__ import annotations

import uuid

from scion.core.branch_lifecycle_policy import (
    BranchLifecyclePolicy,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN,
    SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,
    SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE,
    SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN,
    SCREENING_STALE_RESCREEN_FAIL,
    SCREENING_WEAK_SIGNAL_CONTINUE,
    SCREENING_ZERO_WIN_STREAK_EXHAUSTED,
)
from scion.core.models import DecisionFeatures


def _features(**overrides) -> DecisionFeatures:
    data = {
        "branch_id": str(uuid.uuid4()),
        "hypothesis_action": "modify",
        "stage": "screening",
        "contract_passed": True,
        "verification_passed": True,
        "canary_passed": True,
        "n_cases": 8,
        "wins": 1,
        "losses": 0,
        "ties": 7,
        "win_rate": 0.125,
        "median_delta": 0.0,
        "ci_low": 0.0,
        "ci_high": 0.0,
        "stale": False,
        "recent_retry_count": 0,
        "recent_failure_codes": (),
        "budget_remaining_ratio": 1.0,
        "runtime_guard_passed": True,
        "runtime_ratio_median": 1.001,
        "runtime_regression_rate": 0.56,
        "valid_pairs": 8,
    }
    data.update(overrides)
    return DecisionFeatures(**data)


def test_weak_positive_low_win_screening_keeps_branch() -> None:
    decision = BranchLifecyclePolicy().decide(_features())

    assert decision.action == "keep_exploring"
    assert decision.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert decision.next_zero_win_streak == 0


def test_loss_without_wins_soft_abandons_low_signal_branch() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(wins=0, losses=1, ties=7, win_rate=0.0),
    )

    assert decision.action == "soft_abandon"
    assert SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN in decision.reason_codes


def test_negative_delta_and_runtime_slowdown_soft_abandon() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            wins=0,
            losses=7,
            ties=1,
            win_rate=0.0,
            median_delta=-10.25,
            runtime_ratio_median=1.187,
            runtime_regression_rate=0.958,
        ),
    )

    assert decision.action == "soft_abandon"
    assert decision.reason_codes == (
        SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN,
        SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,
        SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN,
        SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE,
    )


def test_neutral_all_tie_branch_survives_until_zero_win_streak_limit() -> None:
    policy = BranchLifecyclePolicy()

    keep = policy.decide(
        _features(wins=0, losses=0, ties=8, win_rate=0.0),
        current_zero_win_streak=0,
    )
    exhausted = policy.decide(
        _features(wins=0, losses=0, ties=8, win_rate=0.0),
        current_zero_win_streak=2,
    )

    assert keep.action == "keep_exploring"
    assert keep.reason_codes == (SCREENING_NEUTRAL_SIGNAL_CONTINUE,)
    assert keep.next_zero_win_streak == 1
    assert exhausted.action == "soft_abandon"
    assert exhausted.reason_codes == (SCREENING_ZERO_WIN_STREAK_EXHAUSTED,)


def test_stale_rescreen_low_win_remains_abandon_for_reconcile() -> None:
    decision = BranchLifecyclePolicy().decide(_features(stale=True))

    assert decision.action == "soft_abandon"
    assert decision.reason_codes == (SCREENING_STALE_RESCREEN_FAIL,)
