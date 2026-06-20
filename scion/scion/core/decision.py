from __future__ import annotations
from typing import List

from scion.core.branch_lifecycle_policy import (
    BranchLifecycleDecision,
    BranchLifecyclePolicy,
)
from scion.core.models import (
    Decision,
    DecisionFeatures,
    DecisionLifecycleAction,
    DecisionOutcome,
)
from scion.core.telemetry_validation import (
    FROZEN_TELEMETRY_FAILED,
    SCREENING_TELEMETRY_FAILED,
    SCREENING_TELEMETRY_REPAIRABLE,
    TELEMETRY_VALIDATION_REPAIRABLE,
    VALIDATION_TELEMETRY_FAILED,
    VALIDATION_TELEMETRY_REPAIRABLE,
)
from scion.config.problem import ProtocolConfig


class DecisionEngine:
    """
    Pure deterministic decision engine.
    Input: DecisionFeatures (no free text).
    Output: DecisionOutcome with Decision + reason codes.
    """

    def __init__(
        self,
        config: ProtocolConfig,
        *,
        lifecycle_policy: BranchLifecyclePolicy | None = None,
    ) -> None:
        self.config = config
        self.lifecycle_policy = lifecycle_policy or _lifecycle_policy_for_config(
            config
        )

    def decide(self, features: DecisionFeatures) -> DecisionOutcome:
        from scion.core.features import _validate_no_free_text

        _validate_no_free_text(features)

        # Pre-flight safety checks
        if not features.contract_passed:
            return self._out(features, Decision.ABANDON, ["CONTRACT_FAILED"])

        if not features.verification_passed:
            return self._out(features, Decision.ABANDON, ["VERIFICATION_FAILED"])

        if not features.canary_passed:
            return self._out(features, Decision.ABANDON, ["CANARY_FAILED"])

        runtime_veto = self._runtime_veto(features)
        if runtime_veto is not None:
            return runtime_veto

        if features.runtime_evidence_status == "fresh_champion_required":
            return self._out(
                features,
                Decision.CONTINUE_EXPLORE,
                ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
            )

        if features.telemetry_validation_repairable:
            if features.stage == "validation":
                outcome = self._out(
                    features,
                    Decision.VALIDATION_REPAIR_REQUIRED,
                    [
                        VALIDATION_TELEMETRY_REPAIRABLE,
                        TELEMETRY_VALIDATION_REPAIRABLE,
                    ],
                )
                return self._apply_lifecycle_policy(features, outcome)
            elif features.stage == "screening":
                reason_codes = [
                    TELEMETRY_VALIDATION_REPAIRABLE,
                    SCREENING_TELEMETRY_REPAIRABLE,
                ]
            else:
                return self._out(
                    features,
                    Decision.ABANDON,
                    [FROZEN_TELEMETRY_FAILED],
                )
            outcome = self._out(
                features,
                Decision.CONTINUE_EXPLORE,
                reason_codes,
            )
            return self._apply_lifecycle_policy(features, outcome)

        if features.telemetry_guard_failed:
            return self._out(
                features,
                Decision.ABANDON,
                [_telemetry_failed_reason_code(features.stage)],
            )

        stage = features.stage
        if stage == "screening":
            outcome = self._decide_screening(features)
        elif stage == "validation":
            outcome = self._decide_validation(features)
        elif stage == "frozen":
            outcome = self._decide_frozen(features)
        else:
            return self._out(features, Decision.ABANDON, ["UNKNOWN_STAGE"])
        return self._apply_lifecycle_policy(features, outcome)

    # ------------------------------------------------------------------
    # Per-stage sub-decisions
    # ------------------------------------------------------------------

    def _decide_screening(self, features: DecisionFeatures) -> DecisionOutcome:
        wr = features.win_rate
        md = features.median_delta
        threshold = self.config.screening_win_rate_threshold
        min_delta = self.config.screening_min_practical_delta

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
            # v3 screening requires both win rate and practical effect evidence.
            # A high win rate with negative median effect stays in exploration by
            # default unless a problem-owned protocol explicitly models it.
            return self._out(
                features,
                Decision.CONTINUE_EXPLORE,
                ["SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT"],
            )
        elif self._runtime_tie_improvement(features):
            return self._out(features, Decision.QUEUE_VALIDATE, ["SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT"])
        elif self._trajectory_divergent_low_snr_expand(features):
            if features.screening_expand_count >= 1:
                borderline = self._expanded_borderline_advance_status(features)
                if borderline == "pair_signal_pass":
                    return self._out(
                        features,
                        Decision.QUEUE_VALIDATE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS",
                            "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE",
                        ],
                    )
                if borderline == "negative_delta":
                    return self._out(
                        features,
                        Decision.CONTINUE_EXPLORE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA",
                            "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
                        ],
                    )
                if borderline == "negative_ci_low":
                    return self._out(
                        features,
                        Decision.CONTINUE_EXPLORE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW",
                            "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
                        ],
                    )
                return self._out(
                    features,
                    Decision.CONTINUE_EXPLORE,
                    ["SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE"],
                )
            return self._out(
                features,
                Decision.EXPAND_SCREENING,
                ["SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT"],
            )
        elif wr >= 0.5 and wr < threshold:
            # v3 §11.5: screening expansion is one pre-registered statistical
            # expand per candidate, not a repeatable retry loop.
            if features.screening_expand_count >= 1:
                borderline = self._expanded_borderline_advance_status(features)
                if borderline == "pass":
                    return self._out(
                        features,
                        Decision.QUEUE_VALIDATE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS",
                            "SCREENING_BELOW_WIN_RATE_MIN_ALLOWED_BY_POLICY",
                        ],
                    )
                if borderline == "negative_delta":
                    return self._out(
                        features,
                        Decision.CONTINUE_EXPLORE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA",
                            "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
                        ],
                    )
                if borderline == "negative_ci_low":
                    return self._out(
                        features,
                        Decision.CONTINUE_EXPLORE,
                        [
                            "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW",
                            "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
                        ],
                    )
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

        if self._runtime_tie_improvement(features):
            return self._out(features, Decision.QUEUE_FROZEN, ["VALIDATION_PASS_RUNTIME_TIE_IMPROVEMENT"])

        if features.protocol_gate_outcome == "fail":
            return self._out(features, Decision.ABANDON, ["VALIDATION_PROTOCOL_GATE_FAIL"])

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

        if self._runtime_tie_improvement(features):
            return self._out(features, Decision.PROMOTE, ["FROZEN_PASS_RUNTIME_TIE_IMPROVEMENT"])

        if (
            features.protocol_gate_outcome is not None
            and features.protocol_gate_outcome != "pass"
        ):
            return self._out(features, Decision.ABANDON, ["FROZEN_PROTOCOL_GATE_NOT_PASS"])

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

    def _runtime_veto(self, features: DecisionFeatures) -> DecisionOutcome | None:
        """Default framework-level algorithm-efficiency guard.

        Runtime is a first-class optimization signal, not just evidence text.
        Candidate timeouts/crashes always veto. Large median slowdowns veto at
        every stage so objective-only improvements cannot consume validation or
        frozen budget, and cannot promote.
        """
        if features.runtime_guard_timeout:
            return self._out(features, Decision.ABANDON, ["RUNTIME_GUARD_TIMEOUT"])

        if features.runtime_guard_passed is False:
            return self._out(features, Decision.ABANDON, ["RUNTIME_GUARD_FAILED"])

        # Normal DecisionEngine flow preempts lifecycle candidate-runtime
        # classifications so runtime failures have one authoritative reason.
        if features.candidate_failed_pairs > 0:
            return self._out(features, Decision.ABANDON, ["CANDIDATE_RUNTIME_FAILURE"])

        if features.stage == "screening" and features.champion_failed_pairs > 0:
            return self._out(
                features,
                Decision.CONTINUE_EXPLORE,
                ["SCREENING_PARTIAL_CHAMPION_EVIDENCE"],
            )

        if (
            features.runtime_ratio_median is not None
            and features.runtime_ratio_median > self.config.max_runtime_ratio
        ):
            return self._out(features, Decision.ABANDON, ["RUNTIME_REGRESSION"])

        if (
            features.stage in ("validation", "frozen")
            and features.failed_pairs > 0
        ):
            return self._out(features, Decision.ABANDON, ["INCOMPLETE_RUNTIME_EVIDENCE"])

        return None

    def _runtime_tie_improvement(self, features: DecisionFeatures) -> bool:
        """Treat runtime as positive evidence only when quality is non-regressive."""
        if features.candidate_failed_pairs > 0 or features.failed_pairs > 0:
            return False
        if features.runtime_ratio_median is None:
            return False
        if features.runtime_pairs < self.config.runtime.tie_min_runtime_pairs:
            return False
        if features.runtime_ratio_median > self.config.runtime.tie_speedup_ratio:
            return False
        if (
            features.runtime_delta_median_ms is not None
            and features.runtime_delta_median_ms >= 0
        ):
            return False
        if features.statistical_status is not None:
            if features.statistical_status != "tie":
                return False
            return features.ci_low is None or features.ci_low >= 0
        if features.median_delta is None or features.median_delta < 0:
            return False
        if features.stage in ("validation", "frozen") and features.ci_low is not None:
            return features.ci_low >= 0
        return features.median_delta == 0

    def _expanded_borderline_advance_status(
        self,
        features: DecisionFeatures,
    ) -> str:
        policy = self.config.gates.screening.expanded_borderline_advance
        if not policy.enabled:
            return "disabled"
        if features.win_rate is None:
            return "outside_window"

        threshold = self.config.screening_win_rate_threshold
        lower_bound = max(0.0, threshold - policy.win_rate_window)
        if not (lower_bound <= features.win_rate < threshold):
            pair_signal = self._expanded_pair_level_signal_status(features)
            if pair_signal != "disabled":
                return pair_signal
            return "outside_window"

        if policy.require_median_delta_nonnegative:
            if features.median_delta is None or features.median_delta < 0:
                return "negative_delta"
        if policy.require_ci_low_nonnegative:
            if features.ci_low is None or features.ci_low < 0:
                return "negative_ci_low"
        return "pass"

    def _expanded_pair_level_signal_status(
        self,
        features: DecisionFeatures,
    ) -> str:
        policy = self.config.gates.screening.expanded_borderline_advance
        if not policy.allow_pair_level_signal:
            return "disabled"
        if policy.require_median_delta_nonnegative:
            if features.median_delta is None or features.median_delta < 0:
                return "negative_delta"
        if policy.require_ci_low_nonnegative:
            if features.ci_low is None or features.ci_low < 0:
                return "negative_ci_low"
        pair_wins = max(0, int(features.pair_wins or 0))
        pair_losses = max(0, int(features.pair_losses or 0))
        pair_ties = max(0, int(features.pair_ties or 0))
        pair_total = pair_wins + pair_losses + pair_ties
        if pair_total <= 0 or pair_total < policy.min_pair_total:
            return "outside_window"
        if pair_wins < policy.min_pair_wins:
            return "outside_window"
        pair_win_rate = pair_wins / pair_total
        if pair_win_rate < policy.pair_win_rate_min:
            return "outside_window"
        if policy.max_pair_loss_rate is not None:
            if pair_losses / pair_total > policy.max_pair_loss_rate:
                return "outside_window"
        if policy.pair_non_tie_win_rate_min is not None:
            pair_non_tie_total = pair_wins + pair_losses
            if pair_non_tie_total <= 0:
                return "outside_window"
            pair_non_tie_win_rate = pair_wins / pair_non_tie_total
            if pair_non_tie_win_rate < policy.pair_non_tie_win_rate_min:
                return "outside_window"
        if (pair_wins - pair_losses) < policy.min_pair_win_loss_margin:
            return "outside_window"
        return "pair_signal_pass"

    def _trajectory_divergent_low_snr_expand(
        self,
        features: DecisionFeatures,
    ) -> bool:
        if getattr(self.config, "pairing_validity", "trajectory_stable") != (
            "trajectory_divergent"
        ):
            return False
        if features.stage != "screening":
            return False
        if features.win_rate is None:
            return False
        if features.win_rate >= self.config.screening_win_rate_threshold:
            return False
        if features.candidate_failed_pairs > 0 or features.failed_pairs > 0:
            return False
        if features.runtime_guard_timeout or features.runtime_guard_passed is False:
            return False
        if (
            _runtime_regression_rate_actionable(self.config)
            and features.runtime_ratio_median is not None
            and features.runtime_ratio_median > self.config.max_runtime_ratio
        ):
            return False
        if (
            _runtime_regression_rate_actionable(self.config)
            and features.runtime_regression_rate is not None
            and features.runtime_regression_rate >= 0.90
        ):
            return False
        if features.statistical_status == "negative":
            return False
        if features.median_delta is not None and features.median_delta < 0:
            return features.screening_expand_count >= 1
        if features.ci_high is not None and features.ci_high < 0:
            return False

        wins, losses, ties = _screening_signal_counts(features)
        observed = wins + losses + ties
        if observed <= 0:
            return False
        if _loss_heavy(wins=wins, losses=losses, observed=observed):
            return False
        high_tie = ties / observed >= 0.50
        tie_dominant_nonnegative = high_tie and wins >= losses
        weak_nonnegative = wins > 0 and wins >= losses
        return tie_dominant_nonnegative or weak_nonnegative

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
            stage_decision=decision,
            final_decision=decision,
            decision_layer_source="stage_decision",
        )

    def _apply_lifecycle_policy(
        self,
        features: DecisionFeatures,
        outcome: DecisionOutcome,
    ) -> DecisionOutcome:
        if outcome.decision not in (
            Decision.CONTINUE_EXPLORE,
            Decision.VALIDATION_REPAIR_REQUIRED,
        ):
            return outcome
        if not (
            features.telemetry_validation_repairable
            or (
                features.stage == "screening"
                and features.win_rate is not None
            )
        ):
            return outcome

        lifecycle = self.lifecycle_policy.decide(features)
        lifecycle_action = _decision_lifecycle_action(lifecycle.action)
        lifecycle_codes = _lifecycle_reason_codes(lifecycle)
        lifecycle_evidence = self.lifecycle_policy.evidence_metadata(
            features,
            lifecycle,
        )
        if not lifecycle_codes:
            return DecisionOutcome(
                decision=outcome.decision,
                reason_codes=outcome.reason_codes,
                features_snapshot=features,
                stage_decision=outcome.stage_decision,
                final_decision=outcome.decision,
                lifecycle_action=lifecycle_action,
                lifecycle_reason_codes=(),
                decision_layer_source=outcome.decision_layer_source,
                lifecycle_policy_evidence=lifecycle_evidence,
            )
        reason_codes = _merge_reason_codes(outcome.reason_codes, lifecycle_codes)
        if lifecycle.action in {"archive_lineage", "soft_abandon"}:
            lifecycle_evidence = {
                **lifecycle_evidence,
                "bookkeeping_role": "screening_result_lifecycle_annotation",
                "legacy_decision_layer_source": "lifecycle_policy",
            }
            return DecisionOutcome(
                decision=Decision.ABANDON,
                reason_codes=reason_codes,
                features_snapshot=features,
                stage_decision=outcome.decision,
                final_decision=Decision.ABANDON,
                lifecycle_action=lifecycle_action,
                lifecycle_reason_codes=lifecycle_codes,
                decision_layer_source=outcome.decision_layer_source,
                lifecycle_policy_evidence=lifecycle_evidence,
            )
        return DecisionOutcome(
            decision=outcome.decision,
            reason_codes=reason_codes,
            features_snapshot=features,
            stage_decision=outcome.stage_decision,
            final_decision=outcome.decision,
            lifecycle_action=lifecycle_action,
            lifecycle_reason_codes=lifecycle_codes,
            decision_layer_source=outcome.decision_layer_source,
            lifecycle_policy_evidence=lifecycle_evidence,
        )


def _telemetry_failed_reason_code(stage: str) -> str:
    if stage == "frozen":
        return FROZEN_TELEMETRY_FAILED
    if stage == "validation":
        return VALIDATION_TELEMETRY_FAILED
    return SCREENING_TELEMETRY_FAILED


def _lifecycle_reason_codes(
    lifecycle: BranchLifecycleDecision,
) -> tuple[str, ...]:
    if lifecycle.action in {"retain_head", "keep_exploring"}:
        return tuple(lifecycle.reason_codes or ())
    return tuple(
        dict.fromkeys(
            (
                lifecycle.action_reason_code,
                *tuple(lifecycle.reason_codes or ()),
            )
        )
    )


def _decision_lifecycle_action(action: str) -> DecisionLifecycleAction:
    if action == "keep_exploring":
        return "retain_head"
    if action == "soft_abandon":
        return "archive_lineage"
    if action in {
        "retain_head",
        "retain_checkpoint",
        "rollback_to_checkpoint",
        "park_lineage",
        "archive_lineage",
    }:
        return action  # type: ignore[return-value]
    return ""


def _merge_reason_codes(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*first, *second]))


def _lifecycle_policy_for_config(config: ProtocolConfig) -> BranchLifecyclePolicy:
    runtime_regression_rate_actionable = _runtime_regression_rate_actionable(config)
    if getattr(config, "pairing_validity", "trajectory_stable") != (
        "trajectory_divergent"
    ):
        return BranchLifecyclePolicy(
            runtime_regression_rate_actionable=(
                runtime_regression_rate_actionable
            ),
        )
    return BranchLifecyclePolicy(
        open_ended_low_signal_followup=True,
        zero_win_streak_limit=5,
        no_effect_followup_limit=3,
        marginal_no_effect_streak_limit=3,
        repeated_signal_signature_limit=3,
        diagnostic_zero_win_streak_limit=3,
        runtime_regression_rate_actionable=runtime_regression_rate_actionable,
    )


def _runtime_regression_rate_actionable(config: ProtocolConfig) -> bool:
    return getattr(config.runtime, "runtime_model", "comparative") != (
        "budget_exhausting"
    )


def _screening_signal_counts(features: DecisionFeatures) -> tuple[int, int, int]:
    pair_total = (
        int(features.pair_wins or 0)
        + int(features.pair_losses or 0)
        + int(features.pair_ties or 0)
    )
    if pair_total > 0:
        return (
            max(0, int(features.pair_wins or 0)),
            max(0, int(features.pair_losses or 0)),
            max(0, int(features.pair_ties or 0)),
        )
    return (
        max(0, int(features.wins or 0)),
        max(0, int(features.losses or 0)),
        max(0, int(features.ties or 0)),
    )


def _loss_heavy(*, wins: int, losses: int, observed: int) -> bool:
    if observed <= 0:
        return False
    if wins == 0 and losses > 0:
        return True
    return losses > wins and losses / observed >= 0.50
