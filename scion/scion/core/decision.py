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
            # Win rate passes gate but median delta is negative at screening.
            # Screening cases are deterministic — expanding with the same cases
            # produces no new info. Validation's bootstrap CI on diverse cases is
            # the proper adjudicator (w16-optimization deep-fix principle).
            #
            # No expand_count cap here: A1's prior cap used branch.expand_count
            # which leaked screening_expand history into SPND decisions on later
            # candidates (post-T3 this is split into screening_expand_count, so the
            # counter cross-contamination is gone — and the rate-limit itself
            # wasn't supported by data: F experiment showed SPND candidates often
            # pass validation+frozen legitimately via lex ordering).
            # Budget protection now lives at: A2 (idle counter excludes val/frozen),
            # A3 (stagnation_window=25), v3 §11.5 (frozen uses per campaign: 3),
            # and the new T2 validation-layer md guard below.
            return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_PASS_NEGATIVE_DELTA"])
        elif wr >= 0.5 and wr < threshold:
            # Check if already expanded too many times (max 3 screening expands per candidate)
            if features.screening_expand_count >= 3:
                # Borderline candidates (wr close to threshold) may still be worth validating,
                # but only if median_delta is non-negative. Cost-regressive candidates
                # (md < 0) that leak through this path burn val/frozen budget and typically
                # fail frozen on ci_low<0 — reject them here instead.
                if wr >= threshold - 0.05 and (md is None or md >= 0):
                    return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_EXPAND_EXHAUSTED_BORDERLINE"])
                if wr >= threshold - 0.05 and md is not None and md < 0:
                    return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA"])
                return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_EXPAND_EXHAUSTED"])
            return self._out(features, Decision.EXPAND_SCREENING, ["SCREENING_EXPAND"])
        elif wr < 0.5:
            return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_FAIL_WIN_RATE"])
        else:
            return self._out(features, Decision.CONTINUE_EXPLORE, ["SCREENING_UNCLEAR"])

    def _decide_validation(self, features: DecisionFeatures) -> DecisionOutcome:
        wr = features.win_rate
        md = features.median_delta
        ci_low = features.ci_low
        ci_high = features.ci_high
        stat = features.statistical_status
        threshold = self.config.validation_win_rate_threshold

        if wr is None or ci_low is None:
            return self._out(features, Decision.ABANDON, ["NO_VALIDATION_STATS"])

        if stat is not None:
            if wr >= threshold and stat == "positive":
                return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_PASS_HIERARCHICAL"])
            if stat == "negative":
                return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_HIERARCHICAL_NEGATIVE"])
            if stat == "tie":
                return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_NO_HIERARCHICAL_GAIN"])
            if wr >= threshold and stat == "uncertain":
                if features.validation_expand_count >= 1:
                    if md is not None and md < 0:
                        return self._out(features, Decision.ABANDON, ["VALIDATION_EXPAND_EXHAUSTED_FAIL"])
                    return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS"])
                return self._out(features, Decision.EXPAND_VALIDATION, ["VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN"])
            return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_WIN_RATE"])

        if wr >= threshold and ci_low >= 0:
            return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_PASS"])
        elif ci_high is not None and ci_high < 0:
            return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_CI_NEGATIVE"])
        elif wr >= threshold and ci_low < 0:
            # Max 1 validation expand per v3 §11.5
            if features.validation_expand_count >= 1:
                # After val_expand, ci_low still < 0. Use md as tiebreaker
                # (v3 §8.6 validation gate: wr AND md AND ci_low). md at validation
                # is bootstrap-aggregated over diverse cases — more reliable than
                # screening's deterministic-cases md.
                if md is not None and md < 0:
                    # Triple negative: wr passes but ci_low<0 AND md<0 → genuinely
                    # cost-regressive at validation layer. Don't burn frozen slot.
                    return self._out(features, Decision.ABANDON, ["VALIDATION_EXPAND_EXHAUSTED_FAIL"])
                # md>=0 (or unknown): give frozen the final judgment.
                return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS"])
            return self._out(features, Decision.EXPAND_VALIDATION, ["VALIDATION_EXPAND"])
        else:
            return self._out(features, Decision.ABANDON, ["VALIDATION_FAIL_WIN_RATE"])

    def _decide_frozen(self, features: DecisionFeatures) -> DecisionOutcome:
        ci_low = features.ci_low
        stat = features.statistical_status

        if ci_low is None:
            return self._out(features, Decision.ABANDON, ["NO_FROZEN_STATS"])

        if stat is not None:
            if stat == "positive":
                return self._out(features, Decision.PROMOTE, ["FROZEN_PASS_HIERARCHICAL"])
            if stat == "negative":
                return self._out(features, Decision.ABANDON, ["FROZEN_FAIL_HIERARCHICAL_NEGATIVE"])
            if stat == "tie":
                return self._out(features, Decision.ABANDON, ["FROZEN_FAIL_NO_HIERARCHICAL_GAIN"])
            return self._out(features, Decision.ABANDON, ["FROZEN_FAIL_HIERARCHICAL_UNCERTAIN"])

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
