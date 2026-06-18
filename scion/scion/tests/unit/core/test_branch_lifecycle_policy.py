from __future__ import annotations

import uuid

from scion.core.branch_lifecycle_policy import (
    BranchLifecyclePolicy,
    decision_features_signal_signature,
    SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
    SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED,
    SCREENING_MARGINAL_SIGNAL_CONTINUE,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT,
    SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED,
    SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED,
    SCREENING_ROLLBACK_BUDGET_EXHAUSTED,
    SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE,
    SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN,
    SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,
    SCREENING_SOFT_ABANDON_NON_POSITIVE_CI,
    SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE,
    SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN,
    SCREENING_STALE_RESCREEN_FAIL,
    SCREENING_RUNTIME_SATURATION_DIAGNOSTIC,
    SCREENING_RUNTIME_SATURATION_REROUTE,
    SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_EXHAUSTED,
    SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,
    SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,
    SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE,
    SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    SCREENING_WEAK_SIGNAL_CONTINUE,
    SCREENING_ZERO_WIN_STREAK_EXHAUSTED,
    TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA,
    TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,
    VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY,
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
        "runtime_pairs": 8,
        "valid_pairs": 8,
    }
    data.update(overrides)
    return DecisionFeatures(**data)


def test_weak_positive_low_win_screening_keeps_branch() -> None:
    decision = BranchLifecyclePolicy().decide(_features())

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert decision.next_zero_win_streak == 0


def test_win_skewed_weak_positive_keeps_branch_despite_low_gate_rate() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=4,
            losses=1,
            ties=7,
            win_rate=1 / 3,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=4.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert decision.next_zero_win_streak == 0


def test_loss_without_wins_soft_abandons_low_signal_branch() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(wins=0, losses=1, ties=7, win_rate=0.0),
    )

    assert decision.action == "archive_lineage"
    assert SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN in decision.reason_codes


def test_loss_heavy_low_win_screening_does_not_keep_as_weak_positive() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=1,
            losses=5,
            ties=6,
            win_rate=1 / 12,
            ci_low=-4.0,
            ci_high=0.0,
            median_delta=0.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )

    assert decision.action == "archive_lineage"
    assert SCREENING_WEAK_SIGNAL_CONTINUE not in decision.reason_codes
    assert SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP in decision.reason_codes
    assert SCREENING_SOFT_ABANDON_NON_POSITIVE_CI in decision.reason_codes


def test_low_runtime_confidence_does_not_drive_runtime_soft_abandon() -> None:
    high_confidence = BranchLifecyclePolicy().decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            runtime_ratio_median=1.60,
            runtime_delta_median_ms=150.0,
            runtime_regression_rate=0.95,
            runtime_pairs=8,
            runtime_evidence_confidence="sufficient",
        ),
    )
    low_confidence = BranchLifecyclePolicy().decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            runtime_ratio_median=1.60,
            runtime_delta_median_ms=150.0,
            runtime_regression_rate=0.95,
            runtime_pairs=8,
            runtime_evidence_confidence="low_cached_champion",
        ),
    )

    assert SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN in high_confidence.reason_codes
    assert SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE in (
        high_confidence.reason_codes
    )
    assert SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN not in (
        low_confidence.reason_codes
    )
    assert SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE not in (
        low_confidence.reason_codes
    )


def test_report_only_runtime_regression_rate_does_not_soft_abandon() -> None:
    features = _features(
        n_cases=10,
        wins=4,
        losses=0,
        ties=6,
        win_rate=0.4,
        median_delta=0.0,
        valid_pairs=10,
        runtime_pairs=10,
        runtime_ratio_median=1.0,
        runtime_regression_rate=0.95,
        runtime_evidence_confidence="sufficient",
    )

    actionable = BranchLifecyclePolicy().decide(features)
    report_only_policy = BranchLifecyclePolicy(
        runtime_regression_rate_actionable=False
    )
    report_only = report_only_policy.decide(features)

    assert actionable.action == "archive_lineage"
    assert SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE in (
        actionable.reason_codes
    )
    assert report_only.action == "retain_head"
    assert report_only.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE not in (
        report_only.reason_codes
    )
    assert (
        report_only_policy.evidence_metadata(features, report_only)["thresholds"][
            "runtime_regression_rate_actionable"
        ]
        is False
    )


def test_balanced_mixed_screening_signal_is_marginal_not_weak_positive() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=3,
            losses=3,
            ties=6,
            win_rate=0.25,
            median_delta=0.0,
            ci_low=-0.5,
            ci_high=0.5,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_MARGINAL_SIGNAL_CONTINUE,)
    assert SCREENING_WEAK_SIGNAL_CONTINUE not in decision.reason_codes
    assert decision.next_zero_win_streak == 0


def test_pair_level_wins_without_case_gate_keep_branch_as_weak_positive() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
            valid_pairs=16,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,)
    assert decision.next_zero_win_streak == 0


def test_pair_level_wins_with_runtime_saturation_preserve_reroute_streak() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
            valid_pairs=16,
            runtime_budget_saturation_diagnostic=True,
        ),
        current_zero_win_streak=0,
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (
        SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        SCREENING_RUNTIME_SATURATION_DIAGNOSTIC,
    )
    assert decision.next_zero_win_streak == 1


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

    assert decision.action == "archive_lineage"
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

    assert keep.action == "retain_head"
    assert keep.reason_codes == (SCREENING_NEUTRAL_SIGNAL_CONTINUE,)
    assert keep.next_zero_win_streak == 1
    assert exhausted.action == "park_lineage"
    assert exhausted.reason_codes == (SCREENING_ZERO_WIN_STREAK_EXHAUSTED,)


def test_runtime_saturation_diagnostic_reroutes_before_generic_zero_win_limit() -> None:
    policy = BranchLifecyclePolicy()

    keep = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            runtime_budget_saturation_diagnostic=True,
        ),
        current_zero_win_streak=0,
    )
    reroute = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            runtime_budget_saturation_diagnostic=True,
        ),
        current_zero_win_streak=1,
    )

    assert keep.action == "retain_head"
    assert keep.reason_codes == (
        SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        SCREENING_RUNTIME_SATURATION_DIAGNOSTIC,
    )
    assert keep.next_zero_win_streak == 1
    assert reroute.action == "park_lineage"
    assert reroute.reason_codes == (SCREENING_RUNTIME_SATURATION_REROUTE,)
    assert reroute.next_zero_win_streak == 2


def test_low_runtime_evidence_pair_signal_exhausts_before_generic_zero_win_limit() -> None:
    policy = BranchLifecyclePolicy()

    keep = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
            valid_pairs=16,
            runtime_evidence_confidence="low_cached_champion",
        ),
        current_zero_win_streak=0,
    )
    reroute = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
            valid_pairs=16,
            runtime_evidence_confidence="low_cached_champion",
        ),
        current_zero_win_streak=1,
    )

    assert keep.action == "retain_head"
    assert keep.reason_codes == (
        SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,
    )
    assert keep.next_zero_win_streak == 1
    assert reroute.action == "park_lineage"
    assert reroute.reason_codes == (
        SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_EXHAUSTED,
    )
    assert reroute.next_zero_win_streak == 2


def test_effect_zero_diagnostic_reroutes_without_hard_validation_failure() -> None:
    policy = BranchLifecyclePolicy()

    keep = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            telemetry_effect_zero_diagnostic=True,
            telemetry_validation_repairable=False,
        ),
        current_zero_win_streak=0,
    )
    reroute = policy.decide(
        _features(
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            telemetry_effect_zero_diagnostic=True,
            telemetry_validation_repairable=False,
        ),
        current_zero_win_streak=1,
    )

    assert keep.action == "retain_head"
    assert keep.reason_codes == (
        SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,
    )
    assert reroute.action == "park_lineage"
    assert reroute.reason_codes == (SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE,)


def test_stale_rescreen_low_win_remains_abandon_for_reconcile() -> None:
    decision = BranchLifecyclePolicy().decide(_features(stale=True))

    assert decision.action == "archive_lineage"
    assert decision.reason_codes == (SCREENING_STALE_RESCREEN_FAIL,)


def test_low_mid_win_negative_delta_soft_abandons() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=10,
            wins=4,
            losses=3,
            ties=3,
            win_rate=0.4,
            median_delta=-0.01,
            valid_pairs=10,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )

    assert decision.action == "archive_lineage"
    assert decision.reason_codes == (SCREENING_SOFT_ABANDON_NEGATIVE_DELTA,)


def test_low_mid_win_runtime_slowdown_soft_abandons() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=10,
            wins=4,
            losses=0,
            ties=6,
            win_rate=0.4,
            median_delta=0.0,
            valid_pairs=10,
            runtime_ratio_median=1.2,
            runtime_regression_rate=0.95,
        ),
    )

    assert decision.action == "archive_lineage"
    assert decision.reason_codes == (
        SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN,
        SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE,
    )


def test_two_case_runtime_noise_is_diagnostic_not_soft_abandon() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=2,
            wins=0,
            losses=0,
            ties=2,
            win_rate=0.0,
            median_delta=0.0,
            valid_pairs=2,
            runtime_pairs=2,
            runtime_delta_median_ms=29.0,
            runtime_ratio_median=1.18,
            runtime_regression_rate=1.0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_NEUTRAL_SIGNAL_CONTINUE,)


def test_low_mid_weak_positive_mostly_tie_non_regressive_keeps_branch() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=10,
            wins=4,
            losses=0,
            ties=6,
            win_rate=0.4,
            median_delta=0.0,
            valid_pairs=10,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
            candidate_failed_pairs=0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert decision.next_zero_win_streak == 0


def test_low_mid_positive_case_balance_keeps_weak_positive() -> None:
    policy = BranchLifecyclePolicy()

    three_two = policy.decide(
        _features(
            n_cases=12,
            wins=3,
            losses=2,
            ties=7,
            win_rate=0.25,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=1.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )
    four_one = policy.decide(
        _features(
            n_cases=12,
            wins=4,
            losses=1,
            ties=7,
            win_rate=1 / 3,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=5.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
    )

    assert three_two.action == "retain_head"
    assert three_two.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)
    assert four_one.action == "retain_head"
    assert four_one.reason_codes == (SCREENING_WEAK_SIGNAL_CONTINUE,)


def test_low_mid_candidate_runtime_failures_soft_abandon() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=10,
            wins=4,
            losses=0,
            ties=6,
            win_rate=0.4,
            median_delta=0.0,
            valid_pairs=10,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
            candidate_failed_pairs=1,
        ),
    )

    assert decision.action == "archive_lineage"
    assert decision.reason_codes == (
        SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE,
    )


def test_weak_positive_regression_with_checkpoint_rolls_back() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=1,
            losses=5,
            ties=6,
            win_rate=1 / 12,
            ci_low=-4.0,
            ci_high=0.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        branch_code_status="active_weak_positive",
        branch_screening_tier="weak_positive",
        has_checkpoint=True,
    )

    assert decision.action == "rollback_to_checkpoint"
    assert decision.soft_abandon is False
    assert SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP in decision.reason_codes


def test_rollback_budget_exhausted_parks_weak_positive_checkpoint() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=1,
            losses=5,
            ties=6,
            win_rate=1 / 12,
            ci_low=-4.0,
            ci_high=0.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        branch_code_status="active_weak_positive",
        branch_screening_tier="weak_positive",
        has_checkpoint=True,
        rollback_count=2,
    )

    assert decision.action == "park_lineage"
    assert SCREENING_ROLLBACK_BUDGET_EXHAUSTED in decision.reason_codes
    assert SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP in decision.reason_codes


def test_marginal_failed_followup_parks_lineage() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=12,
            wins=1,
            losses=5,
            ties=6,
            win_rate=1 / 12,
            ci_low=-4.0,
            ci_high=0.0,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
        has_checkpoint=True,
    )

    assert decision.action == "park_lineage"
    assert decision.soft_abandon is True


def test_loss_heavy_marginal_pair_followup_parks_rerun_shape() -> None:
    shape = {
        "n_cases": 6,
        "wins": 1,
        "losses": 2,
        "ties": 3,
        "win_rate": 1 / 6,
        "pair_wins": 3,
        "pair_losses": 4,
        "pair_ties": 5,
        "median_delta": 0.0,
        "ci_low": -1.0,
        "ci_high": 1.0,
        "valid_pairs": 12,
        "runtime_pairs": 12,
        "runtime_ratio_median": 1.0,
        "runtime_regression_rate": 0.0,
    }
    policy = BranchLifecyclePolicy()

    prior_evidence = policy.decide(
        _features(**shape, lifecycle_prior_evidence_tier="marginal")
    )
    active_marginal = policy.decide(
        _features(**shape),
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )
    screening_tier = policy.decide(
        _features(**shape),
        branch_screening_tier="no_effect",
    )
    marginal_streak = policy.decide(
        _features(**shape),
        current_marginal_no_effect_streak=1,
    )

    assert prior_evidence.action == "park_lineage"
    assert prior_evidence.reason_codes == (
        SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    )
    assert active_marginal.action == "park_lineage"
    assert active_marginal.reason_codes == (
        SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    )
    assert screening_tier.action == "park_lineage"
    assert screening_tier.reason_codes == (
        SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    )
    assert marginal_streak.action == "park_lineage"
    assert marginal_streak.reason_codes == (
        SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP,
    )


def test_pair_positive_marginal_followup_preserves_branch_depth() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            n_cases=6,
            wins=2,
            losses=0,
            ties=4,
            win_rate=1 / 3,
            pair_wins=6,
            pair_losses=2,
            pair_ties=4,
            median_delta=0.0,
            ci_low=-0.5,
            ci_high=0.5,
            valid_pairs=12,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
            lifecycle_prior_evidence_tier="marginal",
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_MARGINAL_SIGNAL_CONTINUE,)
    assert SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP not in decision.reason_codes


def test_repeated_marginal_signature_parks_lineage() -> None:
    features = _features(
        n_cases=12,
        wins=3,
        losses=3,
        ties=6,
        win_rate=0.25,
        median_delta=0.0,
        ci_low=-0.5,
        ci_high=0.5,
        valid_pairs=12,
        runtime_pairs=12,
        runtime_ratio_median=1.0,
        runtime_regression_rate=0.0,
    )
    signature = decision_features_signal_signature(features)

    decision = BranchLifecyclePolicy().decide(
        features,
        current_marginal_no_effect_streak=1,
        last_signal_signature=signature,
        current_signal_signature_repeat_count=1,
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )

    assert decision.action == "park_lineage"
    assert decision.reason_codes == (
        SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED,
        SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED,
    )
    assert decision.next_marginal_no_effect_streak == 2
    assert decision.next_signal_signature_repeat_count == 2


def test_relaxed_low_snr_policy_allows_multiple_marginal_followups() -> None:
    features = _features(
        n_cases=12,
        wins=3,
        losses=3,
        ties=6,
        win_rate=0.25,
        median_delta=0.0,
        ci_low=-0.5,
        ci_high=0.5,
        valid_pairs=12,
        runtime_pairs=12,
        runtime_ratio_median=1.0,
        runtime_regression_rate=0.0,
    )
    signature = decision_features_signal_signature(features)
    policy = BranchLifecyclePolicy(
        zero_win_streak_limit=5,
        no_effect_followup_limit=3,
        marginal_no_effect_streak_limit=3,
        repeated_signal_signature_limit=3,
    )

    keep = policy.decide(
        features,
        current_marginal_no_effect_streak=1,
        last_signal_signature=signature,
        current_signal_signature_repeat_count=1,
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )
    exhausted = policy.decide(
        features,
        current_marginal_no_effect_streak=2,
        last_signal_signature=signature,
        current_signal_signature_repeat_count=2,
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )

    assert keep.action == "retain_head"
    assert keep.reason_codes == (SCREENING_MARGINAL_SIGNAL_CONTINUE,)
    assert keep.next_marginal_no_effect_streak == 2
    assert exhausted.action == "park_lineage"
    assert exhausted.reason_codes == (
        SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED,
        SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED,
    )
    assert exhausted.next_marginal_no_effect_streak == 3


def test_report_only_runtime_regression_rate_does_not_fragment_signal_signature() -> None:
    first_features = _features(
        n_cases=12,
        wins=3,
        losses=3,
        ties=6,
        win_rate=0.25,
        median_delta=0.0,
        ci_low=-0.5,
        ci_high=0.5,
        valid_pairs=12,
        runtime_pairs=12,
        runtime_ratio_median=1.0,
        runtime_regression_rate=0.10,
    )
    second_features = _features(
        n_cases=12,
        wins=3,
        losses=3,
        ties=6,
        win_rate=0.25,
        median_delta=0.0,
        ci_low=-0.5,
        ci_high=0.5,
        valid_pairs=12,
        runtime_pairs=12,
        runtime_ratio_median=1.0,
        runtime_regression_rate=0.95,
    )
    policy = BranchLifecyclePolicy(
        runtime_regression_rate_actionable=False,
        marginal_no_effect_streak_limit=2,
        repeated_signal_signature_limit=2,
    )

    first = policy.decide(
        first_features,
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )
    second = policy.decide(
        second_features,
        current_marginal_no_effect_streak=first.next_marginal_no_effect_streak,
        last_signal_signature=first.next_signal_signature,
        current_signal_signature_repeat_count=(
            first.next_signal_signature_repeat_count
        ),
        branch_code_status="active_marginal",
        branch_screening_tier="marginal",
    )

    assert first.next_signal_signature == second.next_signal_signature
    assert second.action == "park_lineage"
    assert second.reason_codes == (
        SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED,
        SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED,
    )


def test_no_effect_exhausted_parks_instead_of_archiving() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(wins=0, losses=0, ties=8, win_rate=0.0),
        current_zero_win_streak=2,
        branch_code_status="active_no_effect",
        branch_screening_tier="no_effect",
        has_checkpoint=True,
    )

    assert decision.action == "park_lineage"
    assert decision.reason_codes == (SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED,)


def test_no_effect_after_weak_checkpoint_retain_checkpoint_not_head() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(wins=0, losses=0, ties=12, win_rate=0.0),
        branch_code_status="active_weak_positive",
        branch_screening_tier="weak_positive",
        has_checkpoint=True,
    )

    assert decision.action == "retain_checkpoint"
    assert decision.reason_codes == (
        SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT,
    )


def test_no_effect_followup_budget_allows_only_one_diagnostic_retry() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(wins=0, losses=0, ties=8, win_rate=0.0),
        current_no_effect_diagnostic_followups=1,
        branch_code_status="active_no_effect",
        branch_screening_tier="no_effect",
    )

    assert decision.action == "park_lineage"
    assert decision.reason_codes == (SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED,)
    assert decision.next_no_effect_diagnostic_followups == 2


def test_screening_telemetry_diagnostic_retries_before_streak_limit() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            telemetry_validation_repairable=True,
            telemetry_guard_failed=True,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
        ),
        current_telemetry_diagnostic_streak=1,
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,)
    assert decision.next_telemetry_diagnostic_streak == 2


def test_telemetry_diagnostic_streak_exhaustion_soft_abandons() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            telemetry_validation_repairable=True,
            telemetry_guard_failed=True,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
        ),
        current_telemetry_diagnostic_streak=2,
    )

    assert decision.action == "park_lineage"
    assert decision.reason_codes == (TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,)
    assert decision.next_telemetry_diagnostic_streak == 3


def test_telemetry_diagnostic_quality_regression_still_retries_before_streak_limit() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            telemetry_validation_repairable=True,
            telemetry_guard_failed=True,
            wins=2,
            losses=4,
            ties=2,
            win_rate=0.25,
            median_delta=-1.0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,)
    assert decision.next_telemetry_diagnostic_streak == 1


def test_validation_telemetry_diagnostic_uses_stage_retry_reason() -> None:
    decision = BranchLifecyclePolicy().decide(
        _features(
            stage="validation",
            telemetry_validation_repairable=True,
            telemetry_guard_failed=True,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
        ),
    )

    assert decision.action == "retain_head"
    assert decision.reason_codes == (VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY,)
