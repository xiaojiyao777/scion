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
    """Apply the preregistered case-level screening rule."""
    wr = stats.win_rate
    threshold = config.screening_win_rate_threshold
    practical_delta = config.screening_min_practical_delta

    if stats.protected_objective_regressions:
        return GateResult(
            outcome="fail",
            reason_codes=("SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION",),
        )

    if wr >= threshold and stats.median_delta >= practical_delta:
        if config.screening.require_expanded_for_pass and not expanded:
            gate = GateResult(
                outcome="expand",
                reason_codes=("SCREENING_EXPAND_REQUIRED_FOR_PASS",),
            )
        else:
            gate = GateResult(outcome="pass", reason_codes=("SCREENING_PASS",))
    elif _initial_screening_sparse_no_loss_signal(
        stats,
        config,
        expanded=expanded,
    ):
        gate = GateResult(
            outcome="expand",
            reason_codes=("SCREENING_EXPAND_SPARSE_NO_LOSS",),
        )
    elif wr < 0.5 or stats.ci_high < 0:
        gate = GateResult(outcome="fail", reason_codes=("SCREENING_FAIL_WIN_RATE",))
    else:
        gate = GateResult(
            outcome="expand",
            reason_codes=("SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN",),
        )
    if expanded and gate.outcome == "expand":
        return GateResult(
            outcome="unclear",
            reason_codes=("SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN",),
        )
    return gate


def _initial_screening_sparse_no_loss_signal(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool,
) -> bool:
    """Measure one sparse practical signal more fully without advancing it."""

    return (
        not expanded
        and stats.wins > 0
        and stats.losses == 0
        and stats.candidate_failed_pairs == 0
        and stats.median_delta >= config.screening_min_practical_delta
        and stats.ci_high >= config.screening_min_practical_delta
    )


def validation_gate(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool = False,
) -> GateResult:
    """Apply case win-rate, practical-effect, and confidence requirements."""
    wr = stats.win_rate
    threshold = config.validation_win_rate_threshold
    practical_delta = config.validation_min_practical_delta
    ci_low_min = config.gates.validation.bootstrap_ci_low_min
    if stats.protected_objective_regressions:
        return GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_FAIL_PROTECTED_OBJECTIVE_REGRESSION",),
        )
    case_effect_pass = (
        wr >= threshold
        and stats.median_delta >= practical_delta
        and stats.ci_low >= ci_low_min
    )

    if case_effect_pass:
        gate = GateResult(outcome="pass", reason_codes=("VALIDATION_PASS",))
    elif stats.ci_high < practical_delta:
        gate = GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_FAIL_BELOW_PRACTICAL_EFFECT",),
        )
    elif wr >= threshold or _initial_validation_expand_is_reachable(
        stats,
        config,
        expanded=expanded,
    ):
        gate = GateResult(outcome="expand", reason_codes=("VALIDATION_EXPAND",))
    else:
        gate = GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_WIN_RATE",))
    if gate.outcome == "expand" and (
        expanded or config.validation.expand_to <= stats.n_cases
    ):
        return GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_EXPAND_EXHAUSTED_INSUFFICIENT_EVIDENCE",),
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
    """Promote only case-level effects satisfying the declared holdout rule."""
    if stats.protected_objective_regressions:
        return GateResult(
            outcome="fail",
            reason_codes=("FROZEN_FAIL_PROTECTED_OBJECTIVE_REGRESSION",),
        )
    case_effect_pass = (
        stats.win_rate >= config.validation_win_rate_threshold
        and stats.median_delta >= config.validation_min_practical_delta
        and stats.ci_low >= config.gates.frozen.bootstrap_ci_low_min
    )

    if case_effect_pass:
        return GateResult(outcome="pass", reason_codes=("FROZEN_PASS",))
    elif stats.ci_high < 0:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_CI_NEGATIVE",))
    else:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_UNCLEAR",))
