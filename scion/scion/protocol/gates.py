from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from scion.config.problem import ProtocolConfig
from scion.core.models import EvalStats


@dataclass(frozen=True)
class GateResult:
    outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: tuple[str, ...]


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
    gate_config = config.gates.screening
    case_quality_pass = _case_quality_pass(
        stats,
        gate_config,
        legacy_win_rate_min=threshold,
    )
    ci_low_pass = (
        gate_config.bootstrap_ci_low_min is None
        or stats.ci_low >= gate_config.bootstrap_ci_low_min
    )

    if stats.protected_objective_regressions:
        return GateResult(
            outcome="fail",
            reason_codes=("SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION",),
        )

    if case_quality_pass and stats.median_delta >= practical_delta and ci_low_pass:
        if config.screening.require_expanded_for_pass and not expanded:
            gate = GateResult(
                outcome="expand",
                reason_codes=("SCREENING_EXPAND_REQUIRED_FOR_PASS",),
            )
        else:
            gate = GateResult(outcome="pass", reason_codes=("SCREENING_PASS",))
    elif _initial_quality_expansion_pass(
        stats,
        config,
        expanded=expanded,
    ):
        gate = GateResult(
            outcome="expand",
            reason_codes=("SCREENING_EXPAND_INITIAL_QUALITY",),
        )
    elif _initial_screening_sparse_no_loss_signal(
        stats,
        config,
        expanded=expanded,
    ):
        gate = GateResult(
            outcome="expand",
            reason_codes=("SCREENING_EXPAND_SPARSE_NO_LOSS",),
        )
    elif stats.ci_high < 0:
        gate = GateResult(outcome="fail", reason_codes=("SCREENING_FAIL_WIN_RATE",))
    elif _uses_case_quality(gate_config) and not case_quality_pass:
        gate = GateResult(
            outcome="fail",
            reason_codes=("SCREENING_FAIL_CASE_QUALITY",),
        )
    elif not _uses_case_quality(gate_config) and wr < 0.5:
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


def _uses_case_quality(gate_config: Any) -> bool:
    """Return whether the atomic case-distribution rule is configured."""

    return any(
        getattr(gate_config, field, None) is not None
        for field in ("min_net_case_score", "max_case_loss_rate")
    )


def _case_quality_pass(
    stats: EvalStats,
    gate_config: Any,
    *,
    legacy_win_rate_min: float,
) -> bool:
    """Evaluate either legacy win rate or opt-in case-distribution quality."""

    if not _uses_case_quality(gate_config):
        return stats.win_rate >= legacy_win_rate_min
    if stats.n_cases <= 0:
        return False

    net_score = (stats.wins - stats.losses) / stats.n_cases
    loss_rate = stats.losses / stats.n_cases
    return (
        net_score >= gate_config.min_net_case_score
        and loss_rate <= gate_config.max_case_loss_rate
    )


def _initial_quality_expansion_pass(
    stats: EvalStats,
    config: ProtocolConfig,
    *,
    expanded: bool,
) -> bool:
    """Expand promising initial evidence without advancing it."""

    threshold = config.gates.screening.initial_quality_expansion
    if expanded or threshold is None or stats.candidate_failed_pairs:
        return False
    if not _case_quality_pass(stats, threshold, legacy_win_rate_min=1.0):
        return False
    return (
        not threshold.require_ci_high_at_practical_delta
        or stats.ci_high >= config.screening_min_practical_delta
    )


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
    threshold = config.validation_win_rate_threshold
    practical_delta = config.validation_min_practical_delta
    gate_config = config.gates.validation
    ci_low_min = gate_config.bootstrap_ci_low_min
    if stats.protected_objective_regressions:
        return GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_FAIL_PROTECTED_OBJECTIVE_REGRESSION",),
        )
    case_quality_pass = _case_quality_pass(
        stats,
        gate_config,
        legacy_win_rate_min=threshold,
    )
    case_effect_pass = (
        case_quality_pass
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
    elif _uses_case_quality(gate_config) and not case_quality_pass:
        gate = GateResult(
            outcome="fail",
            reason_codes=("VALIDATION_FAIL_CASE_QUALITY",),
        )
    elif case_quality_pass or _initial_validation_expand_is_reachable(
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
    gate_config = config.gates.frozen
    case_quality_pass = _case_quality_pass(
        stats,
        gate_config,
        legacy_win_rate_min=config.validation_win_rate_threshold,
    )
    case_effect_pass = (
        case_quality_pass
        and stats.median_delta >= config.validation_min_practical_delta
        and stats.ci_low >= gate_config.bootstrap_ci_low_min
    )

    if case_effect_pass:
        return GateResult(outcome="pass", reason_codes=("FROZEN_PASS",))
    elif stats.ci_high < 0:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_CI_NEGATIVE",))
    elif _uses_case_quality(gate_config) and not case_quality_pass:
        return GateResult(
            outcome="fail",
            reason_codes=("FROZEN_FAIL_CASE_QUALITY",),
        )
    else:
        return GateResult(outcome="fail", reason_codes=("FROZEN_FAIL_UNCLEAR",))
