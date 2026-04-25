from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Tuple

from scion.core.models import EvalStats
from scion.config.problem import ProtocolConfig


@dataclass(frozen=True)
class GateResult:
    outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: Tuple[str, ...]


def screening_gate(stats: EvalStats, config: ProtocolConfig) -> GateResult:
    """
    Screening gate:
    - pass:   win_rate >= threshold AND median_delta >= min_practical_delta
    - expand: 0.5 <= win_rate < threshold  (promising, needs more data)
    - fail:   win_rate < 0.5
    - unclear: win_rate >= threshold but delta too small
    """
    wr = stats.win_rate
    threshold = config.screening_win_rate_threshold

    if wr >= threshold and stats.median_delta >= config.min_practical_delta:
        return GateResult(outcome="pass", reason_codes=("SCREENING_PASS",))
    elif wr < 0.5:
        return GateResult(outcome="fail", reason_codes=("SCREENING_FAIL_WIN_RATE",))
    elif wr < threshold:
        return GateResult(outcome="expand", reason_codes=("SCREENING_EXPAND",))
    else:
        # win_rate >= threshold but practical delta too small
        return GateResult(outcome="unclear", reason_codes=("SCREENING_DELTA_TOO_SMALL",))


def validation_gate(stats: EvalStats, config: ProtocolConfig) -> GateResult:
    """
    Validation gate:
    - pass:   win_rate >= threshold AND ci_low >= 0
    - expand: win_rate >= threshold AND ci_low < 0 (CI straddles 0)
    - fail:   ci_high < 0 (statistically negative)
    - fail:   win_rate < threshold
    """
    wr = stats.win_rate
    threshold = config.validation_win_rate_threshold

    if stats.statistical_status is not None:
        if wr >= threshold and stats.statistical_status == "positive":
            return GateResult(outcome="pass", reason_codes=("VALIDATION_PASS_HIERARCHICAL",))
        if stats.statistical_status == "negative":
            return GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_HIERARCHICAL_NEGATIVE",))
        if wr >= threshold and stats.statistical_status == "uncertain":
            return GateResult(outcome="expand", reason_codes=("VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",))
        return GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_NO_HIERARCHICAL_GAIN",))

    if wr >= threshold and stats.ci_low >= 0:
        return GateResult(outcome="pass", reason_codes=("VALIDATION_PASS",))
    elif stats.ci_high < 0:
        return GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_CI_NEGATIVE",))
    elif wr >= threshold and stats.ci_low < 0:
        return GateResult(outcome="expand", reason_codes=("VALIDATION_EXPAND",))
    else:
        return GateResult(outcome="fail", reason_codes=("VALIDATION_FAIL_WIN_RATE",))


def frozen_gate(stats: EvalStats, config: ProtocolConfig) -> GateResult:
    """
    Frozen holdout gate (conservative — promote only when statistically positive):
    - pass: ci_low >= 0
    - fail: anything else (including CI straddling 0)
    """
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
