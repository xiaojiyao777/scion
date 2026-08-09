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

    if wr >= threshold and stats.median_delta >= practical_delta:
        gate = GateResult(outcome="pass", reason_codes=("SCREENING_PASS",))
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
    case_effect_pass = (
        wr >= threshold
        and stats.median_delta >= practical_delta
        and stats.ci_low >= ci_low_min
    )

    if stats.statistical_status is not None:
        if stats.statistical_status == "positive":
            if case_effect_pass:
                gate = GateResult(
                    outcome="pass",
                    reason_codes=("VALIDATION_PASS_HIERARCHICAL",),
                )
            else:
                gate = GateResult(
                    outcome="expand",
                    reason_codes=("VALIDATION_EXPAND_PRACTICAL_EFFECT",),
                )
        elif stats.statistical_status == "negative":
            gate = GateResult(
                outcome="fail",
                reason_codes=("VALIDATION_FAIL_HIERARCHICAL_NEGATIVE",),
            )
        elif stats.statistical_status == "uncertain":
            if stats.ci_high < practical_delta:
                gate = GateResult(
                    outcome="fail",
                    reason_codes=("VALIDATION_FAIL_BELOW_PRACTICAL_EFFECT",),
                )
            elif wr >= threshold or _initial_validation_expand_is_reachable(
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
    elif case_effect_pass:
        gate = GateResult(outcome="pass", reason_codes=("VALIDATION_PASS",))
    elif stats.ci_high < practical_delta:
        gate = GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_FAIL_BELOW_PRACTICAL_EFFECT",),
        )
    elif wr >= threshold:
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
    case_effect_pass = (
        stats.win_rate >= config.validation_win_rate_threshold
        and stats.median_delta >= config.validation_min_practical_delta
        and stats.ci_low >= config.gates.frozen.bootstrap_ci_low_min
    )

    if stats.statistical_status is not None:
        if stats.statistical_status == "positive" and case_effect_pass:
            return GateResult(outcome="pass", reason_codes=("FROZEN_PASS_HIERARCHICAL",))
        if stats.statistical_status == "negative":
            return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_HIERARCHICAL_NEGATIVE",))
        if stats.statistical_status == "tie":
            return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_NO_HIERARCHICAL_GAIN",))
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_HIERARCHICAL_UNCERTAIN",))

    if case_effect_pass:
        return GateResult(outcome="pass", reason_codes=("FROZEN_PASS",))
    elif stats.ci_high < 0:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_CI_NEGATIVE",))
    else:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_UNCLEAR",))
