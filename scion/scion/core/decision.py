from __future__ import annotations

from scion.config.problem import ProtocolConfig
from scion.core.models import Decision, DecisionFeatures, DecisionOutcome


_PROTOCOL_ACTIONS = {
    "screening": {
        "pass": Decision.QUEUE_VALIDATE,
        "fail": Decision.CONTINUE_EXPLORE,
        "unclear": Decision.CONTINUE_EXPLORE,
        "expand": Decision.EXPAND_SCREENING,
        "continue": Decision.CONTINUE_EXPLORE,
    },
    "validation": {
        "pass": Decision.QUEUE_FROZEN,
        "fail": Decision.ABANDON,
        "unclear": Decision.CONTINUE_EXPLORE,
        "expand": Decision.EXPAND_VALIDATION,
        "continue": Decision.CONTINUE_EXPLORE,
    },
    "frozen": {
        "pass": Decision.PROMOTE,
        "fail": Decision.ABANDON,
        "unclear": Decision.CONTINUE_EXPLORE,
        "expand": Decision.ABANDON,
        "continue": Decision.CONTINUE_EXPLORE,
    },
}


class DecisionEngine:
    """Map trusted Protocol verdicts and hard-safety facts to branch actions.

    Scientific thresholds, confidence intervals, runtime comparisons, and
    statistical expansion policy belong to Protocol. Numeric aggregates remain
    ordinary Decision inputs but do not participate in this mapping.
    """

    def __init__(self, config: ProtocolConfig) -> None:
        # Retain the public constructor shape while making the ownership boundary
        # explicit: ProtocolConfig is not consulted by Decision.
        del config

    def decide(self, features: DecisionFeatures) -> DecisionOutcome:
        from scion.core.features import _validate_no_free_text

        _validate_no_free_text(features)

        hard_safety = self._hard_safety_outcome(features)
        if hard_safety is not None:
            return hard_safety

        gate_outcome = features.protocol_gate_outcome
        if gate_outcome is None:
            fallback = (
                Decision.CONTINUE_EXPLORE
                if features.stage == "screening"
                else Decision.ABANDON
            )
            return self._out(
                features,
                fallback,
                ("MISSING_PROTOCOL_GATE_OUTCOME",),
            )

        decision = _PROTOCOL_ACTIONS[features.stage][gate_outcome]
        reason_codes = features.protocol_reason_codes or (
            f"{features.stage.upper()}_PROTOCOL_{gate_outcome.upper()}",
        )
        return self._out(features, decision, reason_codes)

    def _hard_safety_outcome(
        self,
        features: DecisionFeatures,
    ) -> DecisionOutcome | None:
        if not features.contract_passed:
            return self._out(features, Decision.ABANDON, ("CONTRACT_FAILED",))
        if not features.verification_passed:
            return self._out(features, Decision.ABANDON, ("VERIFICATION_FAILED",))
        if not features.canary_passed:
            return self._out(features, Decision.ABANDON, ("CANARY_FAILED",))
        if features.runtime_guard_timeout:
            return self._out(features, Decision.ABANDON, ("RUNTIME_GUARD_TIMEOUT",))
        if features.runtime_guard_passed is False:
            return self._out(features, Decision.ABANDON, ("RUNTIME_GUARD_FAILED",))
        # Candidate failures that occur only inside a pair where the champion
        # also failed are not candidate-only safety evidence.  A separate
        # candidate-side incident in another pair remains a hard failure.
        candidate_only_failed_pairs = max(
            0,
            features.candidate_failed_pairs - features.bilateral_failed_pairs,
        )
        if candidate_only_failed_pairs > 0:
            return self._out(
                features,
                Decision.ABANDON,
                ("CANDIDATE_RUNTIME_FAILURE",),
            )
        if features.stage == "screening" and features.champion_failed_pairs > 0:
            return self._out(
                features,
                Decision.CONTINUE_EXPLORE,
                ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",),
            )
        if features.stage in ("validation", "frozen") and features.failed_pairs > 0:
            return self._out(
                features,
                Decision.ABANDON,
                ("INCOMPLETE_RUNTIME_EVIDENCE",),
            )
        return None

    def _out(
        self,
        features: DecisionFeatures,
        decision: Decision,
        reason_codes: tuple[str, ...],
    ) -> DecisionOutcome:
        return DecisionOutcome(
            decision=decision,
            reason_codes=tuple(reason_codes),
        )
