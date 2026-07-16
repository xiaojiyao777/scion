from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Tuple

from scion.core.models import EvalStats
from scion.config.problem import ProtocolConfig


@dataclass(frozen=True)
class GateResult:
    outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: Tuple[str, ...]


def screening_gate(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool = False,
) -> GateResult:
    """
    Screening gate:
    - pass:   win_rate >= threshold AND median_delta >= min_practical_delta
    - pass:   win_rate >= threshold AND median_delta is non-negative but below
              min_practical_delta (diagnostic validation candidate)
    - expand: 0.5 <= win_rate < threshold, or low-SNR trajectory-divergent
              evidence with non-negative/tie-heavy signal
    - fail:   negative/loss-heavy low-SNR evidence or win_rate < 0.5
    - unclear: win_rate >= threshold but median_delta is negative
    """
    wr = stats.win_rate
    threshold = config.screening_win_rate_threshold

    if _runtime_regression(stats, config):
        return GateResult(outcome="fail", reason_codes=("RUNTIME_REGRESSION",))
    if _runtime_tie_fresh_champion_required(stats, config):
        return GateResult(
            outcome="unclear",
            reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        )
    if wr >= threshold and stats.median_delta >= config.screening_min_practical_delta:
        gate = GateResult(outcome="pass", reason_codes=("SCREENING_PASS",))
    elif _runtime_tie_improvement(stats, config):
        gate = GateResult(
            outcome="pass",
            reason_codes=("SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT",),
        )
    elif _trajectory_divergent_low_snr_expand(stats, config):
        gate = GateResult(
            outcome="expand",
            reason_codes=("SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT",),
        )
    elif wr < 0.5:
        gate = GateResult(outcome="fail", reason_codes=("SCREENING_FAIL_WIN_RATE",))
    elif wr < threshold:
        gate = GateResult(outcome="expand", reason_codes=("SCREENING_EXPAND",))
    elif stats.median_delta >= 0:
        gate = GateResult(
            outcome="pass",
            reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
        )
    else:
        gate = GateResult(
            outcome="unclear",
            reason_codes=("SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT",),
        )
    if expanded and gate.outcome == "expand":
        return _expanded_screening_gate(stats, config, initial_gate=gate)
    return gate


def validation_gate(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool = False,
) -> GateResult:
    """
    Validation gate:
    - pass:   win_rate >= threshold AND ci_low >= 0
    - expand: win_rate >= threshold AND ci_low < 0 (CI straddles 0)
    - expand: initial hierarchical uncertainty with no case losses when the
              preregistered expanded sample can still reach the win threshold
    - fail:   ci_high < 0 (statistically negative)
    - fail:   win_rate < threshold
    """
    wr = stats.win_rate
    threshold = config.validation_win_rate_threshold

    if _runtime_regression(stats, config):
        return GateResult(outcome="fail", reason_codes=("RUNTIME_REGRESSION",))
    if _runtime_tie_fresh_champion_required(stats, config):
        return GateResult(
            outcome="unclear",
            reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        )
    if _runtime_tie_improvement(stats, config):
        return GateResult(
            outcome="pass",
            reason_codes=("VALIDATION_PASS_RUNTIME_TIE_IMPROVEMENT",),
        )

    if stats.statistical_status is not None:
        if stats.statistical_status == "positive":
            if wr >= threshold:
                gate = GateResult(
                    outcome="pass",
                    reason_codes=("VALIDATION_PASS_HIERARCHICAL",),
                )
            else:
                gate = GateResult(
                    outcome="fail",
                    reason_codes=("VALIDATION_FAIL_WIN_RATE",),
                )
        elif stats.statistical_status == "negative":
            gate = GateResult(
                outcome="fail",
                reason_codes=("VALIDATION_FAIL_HIERARCHICAL_NEGATIVE",),
            )
        elif stats.statistical_status == "uncertain":
            if wr >= threshold or _initial_validation_expand_is_reachable(
                stats,
                config,
                expanded=expanded,
            ):
                gate = GateResult(
                    outcome="expand",
                    reason_codes=("VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",),
                )
            else:
                gate = GateResult(
                    outcome="fail",
                    reason_codes=("VALIDATION_FAIL_WIN_RATE",),
                )
        else:
            gate = GateResult(
                outcome="fail",
                reason_codes=("VALIDATION_FAIL_NO_HIERARCHICAL_GAIN",),
            )
    elif wr >= threshold and stats.ci_low >= 0:
        gate = GateResult(outcome="pass", reason_codes=("VALIDATION_PASS",))
    elif stats.ci_high < 0:
        gate = GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_CI_NEGATIVE",))
    elif wr >= threshold and stats.ci_low < 0:
        gate = GateResult(outcome="expand", reason_codes=("VALIDATION_EXPAND",))
    else:
        gate = GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_WIN_RATE",))
    if expanded and gate.outcome == "expand":
        if stats.median_delta < 0:
            return GateResult(
                outcome="fail",
                reason_codes=("VALIDATION_EXPAND_EXHAUSTED_FAIL",),
            )
        return GateResult(
            outcome="pass",
            reason_codes=("VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS",),
        )
    return gate


def _initial_validation_expand_is_reachable(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool,
) -> bool:
    """Allow one no-loss uncertain expand only when the win gate is reachable."""
    if expanded or stats.losses != 0 or stats.wins <= 0:
        return False

    expanded_n_cases = config.validation.expand_to
    remaining_cases = expanded_n_cases - stats.n_cases
    if remaining_cases <= 0:
        return False

    maximum_wins = stats.wins + remaining_cases
    maximum_win_rate = maximum_wins / expanded_n_cases
    return maximum_win_rate >= config.validation_win_rate_threshold


def frozen_gate(stats: EvalStats, config: ProtocolConfig) -> GateResult:
    """
    Frozen holdout gate (conservative — promote only when statistically positive):
    - pass: ci_low >= 0
    - fail: anything else (including CI straddling 0)
    """
    if _runtime_regression(stats, config):
        return GateResult(outcome="fail", reason_codes=("RUNTIME_REGRESSION",))
    if _runtime_tie_fresh_champion_required(stats, config):
        return GateResult(
            outcome="unclear",
            reason_codes=("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",),
        )

    if _runtime_tie_improvement(stats, config):
        return GateResult(
            outcome="pass",
            reason_codes=("FROZEN_PASS_RUNTIME_TIE_IMPROVEMENT",),
        )

    if stats.statistical_status is not None:
        if stats.statistical_status == "positive":
            return GateResult(outcome="pass", reason_codes=("FROZEN_PASS_HIERARCHICAL",))
        if stats.statistical_status == "negative":
            return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_HIERARCHICAL_NEGATIVE",))
        if stats.statistical_status == "tie":
            return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_NO_HIERARCHICAL_GAIN",))
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_HIERARCHICAL_UNCERTAIN",))

    if stats.ci_low >= 0:
        return GateResult(outcome="pass", reason_codes=("FROZEN_PASS",))
    elif stats.ci_high < 0:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_CI_NEGATIVE",))
    else:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_UNCLEAR",))


def _expanded_screening_gate(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    initial_gate: GateResult,
) -> GateResult:
    status = _expanded_borderline_advance_status(stats, config)
    if status == "pair_signal_pass":
        return GateResult(
            outcome="pass",
            reason_codes=(
                "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS",
                "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE",
            ),
        )
    if status == "pass":
        return GateResult(
            outcome="pass",
            reason_codes=(
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS",
                "SCREENING_BELOW_WIN_RATE_MIN_ALLOWED_BY_POLICY",
            ),
        )
    if status == "negative_delta":
        return GateResult(
            outcome="fail",
            reason_codes=(
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA",
                "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
            ),
        )
    if status == "negative_ci_low":
        return GateResult(
            outcome="fail",
            reason_codes=(
                "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW",
                "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
            ),
        )
    if "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT" in initial_gate.reason_codes:
        return GateResult(
            outcome="unclear",
            reason_codes=("SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE",),
        )
    return GateResult(
        outcome="unclear",
        reason_codes=("SCREENING_EXPAND_EXHAUSTED",),
    )


def _expanded_borderline_advance_status(
    stats: EvalStats,
    config: ProtocolConfig,
) -> str:
    policy = config.gates.screening.expanded_borderline_advance
    if not policy.enabled:
        return "disabled"

    threshold = config.screening_win_rate_threshold
    lower_bound = max(0.0, threshold - policy.win_rate_window)
    if not (lower_bound <= stats.win_rate < threshold):
        pair_signal = _expanded_pair_level_signal_status(stats, config)
        if pair_signal != "disabled":
            return pair_signal
        return "outside_window"

    if policy.require_median_delta_nonnegative and stats.median_delta < 0:
        return "negative_delta"
    if policy.require_ci_low_nonnegative and stats.ci_low < 0:
        return "negative_ci_low"
    return "pass"


def _expanded_pair_level_signal_status(
    stats: EvalStats,
    config: ProtocolConfig,
) -> str:
    policy = config.gates.screening.expanded_borderline_advance
    if not policy.allow_pair_level_signal:
        return "disabled"
    if policy.require_median_delta_nonnegative and stats.median_delta < 0:
        return "negative_delta"
    if policy.require_ci_low_nonnegative and stats.ci_low < 0:
        return "negative_ci_low"
    pair_wins = max(0, int(stats.pair_wins or 0))
    pair_losses = max(0, int(stats.pair_losses or 0))
    pair_ties = max(0, int(stats.pair_ties or 0))
    pair_total = pair_wins + pair_losses + pair_ties
    if pair_total <= 0 or pair_total < policy.min_pair_total:
        return "outside_window"
    if pair_wins < policy.min_pair_wins:
        return "outside_window"
    if pair_wins / pair_total < policy.pair_win_rate_min:
        return "outside_window"
    if (
        policy.max_pair_loss_rate is not None
        and pair_losses / pair_total > policy.max_pair_loss_rate
    ):
        return "outside_window"
    if policy.pair_non_tie_win_rate_min is not None:
        non_tie_total = pair_wins + pair_losses
        if non_tie_total <= 0:
            return "outside_window"
        if pair_wins / non_tie_total < policy.pair_non_tie_win_rate_min:
            return "outside_window"
    if pair_wins - pair_losses < policy.min_pair_win_loss_margin:
        return "outside_window"
    return "pair_signal_pass"


def _runtime_regression(stats: EvalStats, config: ProtocolConfig) -> bool:
    if getattr(config.runtime, "runtime_model", "comparative") == "budget_exhausting":
        return False
    return (
        stats.runtime_ratio_median is not None
        and stats.runtime_ratio_median > config.max_runtime_ratio
    )


def _runtime_tie_improvement(stats: EvalStats, config: ProtocolConfig) -> bool:
    if stats.candidate_failed_pairs > 0 or stats.failed_pairs > 0:
        return False
    if stats.runtime_ratio_median is None:
        return False
    if stats.runtime_pairs < config.runtime.tie_min_runtime_pairs:
        return False
    if stats.runtime_ratio_median > config.runtime.tie_speedup_ratio:
        return False
    if stats.runtime_delta_median_ms is not None and stats.runtime_delta_median_ms >= 0:
        return False
    if stats.statistical_status is not None:
        return stats.statistical_status == "tie" and stats.ci_low >= 0
    if stats.median_delta < 0:
        return False
    return stats.ci_low >= 0


def _runtime_tie_fresh_champion_required(
    stats: EvalStats,
    config: ProtocolConfig,
) -> bool:
    if getattr(config.runtime, "runtime_model", "comparative") == "budget_exhausting":
        return False
    if config.runtime.champion_runtime_policy != "fresh_required_for_runtime_tie":
        return False
    if stats.champion_cached_runtime_pairs <= 0:
        return False
    if stats.runtime_pairs >= config.runtime.tie_min_runtime_pairs:
        return False
    if stats.candidate_failed_pairs > 0 or stats.failed_pairs > 0:
        return False
    if stats.losses > 0 or stats.median_delta < 0 or stats.ci_low < 0:
        return False
    if stats.wins > 0:
        return False
    return stats.n_cases > 0 and stats.ties > 0


def _trajectory_divergent_low_snr_expand(
    stats: EvalStats,
    config: ProtocolConfig,
) -> bool:
    if getattr(config, "pairing_validity", "trajectory_stable") != (
        "trajectory_divergent"
    ):
        return False
    if stats.win_rate >= config.screening_win_rate_threshold:
        return False
    if stats.candidate_failed_pairs > 0 or stats.failed_pairs > 0:
        return False
    budget_exhausting = (
        getattr(config.runtime, "runtime_model", "comparative") == "budget_exhausting"
    )
    if (
        not budget_exhausting
        and stats.runtime_ratio_median is not None
        and stats.runtime_ratio_median > config.max_runtime_ratio
    ):
        return False
    if (
        not budget_exhausting
        and stats.runtime_regression_rate is not None
        and stats.runtime_regression_rate >= 0.90
    ):
        return False
    if stats.statistical_status == "negative":
        return False
    if stats.median_delta < 0:
        return False
    if stats.ci_high < 0:
        return False

    wins, losses, ties = _screening_signal_counts(stats)
    observed = wins + losses + ties
    if observed <= 0:
        return False
    if _loss_heavy(wins=wins, losses=losses, observed=observed):
        return False
    high_tie = ties / observed >= 0.50
    tie_dominant_nonnegative = high_tie and wins >= losses
    weak_nonnegative = wins > 0 and wins >= losses
    return tie_dominant_nonnegative or weak_nonnegative


def _screening_signal_counts(stats: EvalStats) -> tuple[int, int, int]:
    pair_total = int(stats.pair_wins or 0) + int(stats.pair_losses or 0) + int(
        stats.pair_ties or 0
    )
    if pair_total > 0:
        return (
            max(0, int(stats.pair_wins or 0)),
            max(0, int(stats.pair_losses or 0)),
            max(0, int(stats.pair_ties or 0)),
        )
    return (
        max(0, int(stats.wins or 0)),
        max(0, int(stats.losses or 0)),
        max(0, int(stats.ties or 0)),
    )


def _loss_heavy(*, wins: int, losses: int, observed: int) -> bool:
    if observed <= 0:
        return False
    if wins == 0 and losses > 0:
        return True
    return losses > wins and losses / observed >= 0.50
