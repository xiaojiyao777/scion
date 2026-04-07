from __future__ import annotations
from typing import List

from scion.core.models import Decision, DecisionFeatures, DecisionOutcome
from scion.config.problem import ProtocolConfig


class DecisionEngine:
    """
    Pure deterministic decision engine.
    Input: DecisionFeatures (no free text).
    Output: DecisionOutcome with Decision + reason codes.
    """

    def __init__(self, config: ProtocolConfig) -> None:
        self.config = config

    def decide(self, features: DecisionFeatures) -> DecisionOutcome:
        # Pre-flight safety checks
        if not features.contract_passed:
            return self._out(features, Decision.ABANDON, ["CONTRACT_FAILED"])

        if not features.verification_passed:
            return self._out(features, Decision.ABANDON, ["VERIFICATION_FAILED"])

        if not features.canary_passed:
            return self._out(features, Decision.ABANDON, ["CANARY_FAILED"])

        if features.budget_remaining_ratio <= 0.0:
            return self._out(features, Decision.ABANDON, ["BUDGET_EXHAUSTED"])

        stage = features.stage
        if stage == "screening":
            return self._decide_screening(features)
        elif stage == "validation":
            return self._decide_validation(features)
        elif stage == "frozen":
            return self._decide_frozen(features)
        return self._out(features, Decision.ABANDON, ["UNKNOWN_STAGE"])

    # ------------------------------------------------------------------
    # Per-stage sub-decisions
    # ------------------------------------------------------------------

    def _decide_screening(self, features: DecisionFeatures) -> DecisionOutcome:
        wr = features.win_rate
        md = features.median_delta
        threshold = self.config.screening_win_rate_threshold
        min_delta = self.config.min_practical_delta

        if wr is None:
            # No stats yet (pre-protocol call) — continue exploring
            return self._out(features, Decision.CONTINUE_EXPLORE, ["NO_SCREENING_STATS"])

        if wr >= threshold and md is not None and md >= min_delta:
            return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_PASS"])
        elif wr >= threshold and (md is None or md >= 0):
            # High win_rate, non-negative delta (ties drag median to 0)
            # → pass to validation which has more diverse instances
            return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_PASS_MARGINAL_DELTA"])
        elif wr >= threshold and md is not None and md < 0:
            # High win_rate but negative median — expand to confirm
            return self._out(features, Decision.EXPAND_SCREENING, ["SCREENING_EXPAND_DELTA"])
        elif wr >= 0.5 and wr < threshold:
            # Check if already expanded too many times (max 3 expands)
            if features.recent_retry_count >= 3:
                if wr >= threshold - 0.05:  # Close enough, try validation
                    return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_EXPAND_EXHAUSTED_BORDERLINE"])
                return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_EXPAND_EXHAUSTED"])
            return self._out(features, Decision.EXPAND_SCREENING, ["SCREENING_EXPAND"])
        elif wr < 0.5:
            return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_FAIL_WIN_RATE"])
        else:
            return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_UNCLEAR"])

    def _decide_validation(self, features: DecisionFeatures) -> DecisionOutcome:
        wr = features.win_rate
        ci_low = features.ci_low
        ci_high = features.ci_high
        threshold = self.config.validation_win_rate_threshold

        if wr is None or ci_low is None:
            return self._out(features, Decision.ABANDON, ["NO_VALIDATION_STATS"])

        if wr >= threshold and ci_low >= 0:
            return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_PASS"])
        elif ci_high is not None and ci_high < 0:
            return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_CI_NEGATIVE"])
        elif wr >= threshold and ci_low < 0:
            return self._out(features, Decision.EXPAND_VALIDATION, ["VALIDATION_EXPAND"])
        else:
            return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_WIN_RATE"])

    def _decide_frozen(self, features: DecisionFeatures) -> DecisionOutcome:
        ci_low = features.ci_low

        if ci_low is None:
            return self._out(features, Decision.ABANDON, ["NO_FROZEN_STATS"])

        if ci_low >= 0:
            return self._out(features, Decision.PROMOTE, ["FROZEN_PASS"])
        return self._out(features, Decision.ABANDON, ["FROZEN_FAIL"])

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _out(
        self,
        features: DecisionFeatures,
        decision: Decision,
        reason_codes: List[str],
    ) -> DecisionOutcome:
        return DecisionOutcome(
            decision=decision,
            reason_codes=tuple(reason_codes),
            features_snapshot=features,
        )
