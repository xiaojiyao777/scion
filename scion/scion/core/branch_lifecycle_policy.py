"""Branch lifecycle policy for low-signal screening results."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from scion.core.models import DecisionFeatures


BranchLifecycleAction = Literal[
    "retain_head",
    "retain_checkpoint",
    "rollback_to_checkpoint",
    "park_lineage",
    "archive_lineage",
    # Backward-compatible values for older callers/tests.
    "keep_exploring",
    "soft_abandon",
]

SCREENING_WEAK_SIGNAL_CONTINUE = "SCREENING_WEAK_SIGNAL_CONTINUE"
SCREENING_MARGINAL_SIGNAL_CONTINUE = "SCREENING_MARGINAL_SIGNAL_CONTINUE"
SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL = (
    "SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL"
)
SCREENING_NEUTRAL_SIGNAL_CONTINUE = "SCREENING_NEUTRAL_SIGNAL_CONTINUE"
SCREENING_ZERO_WIN_STREAK_CONTINUE = "SCREENING_ZERO_WIN_STREAK_CONTINUE"
SCREENING_ZERO_WIN_STREAK_EXHAUSTED = "SCREENING_ZERO_WIN_STREAK_EXHAUSTED"
SCREENING_ROLLBACK_BUDGET_EXHAUSTED = "SCREENING_ROLLBACK_BUDGET_EXHAUSTED"
SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED = (
    "SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED"
)
SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED = (
    "SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED"
)
SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED = (
    "SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED"
)
SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT = (
    "SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT"
)
SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN = (
    "SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN"
)
SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP = (
    "SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP"
)
SCREENING_SOFT_ABANDON_NON_POSITIVE_CI = (
    "SCREENING_SOFT_ABANDON_NON_POSITIVE_CI"
)
SCREENING_SOFT_ABANDON_NEGATIVE_DELTA = "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA"
SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN = "SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN"
SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE = (
    "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE"
)
SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE = (
    "SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE"
)
SCREENING_STALE_RESCREEN_FAIL = "SCREENING_STALE_RESCREEN_FAIL"
SCREENING_TELEMETRY_DIAGNOSTIC_RETRY = "SCREENING_TELEMETRY_DIAGNOSTIC_RETRY"
SCREENING_RUNTIME_SATURATION_DIAGNOSTIC = (
    "SCREENING_RUNTIME_SATURATION_DIAGNOSTIC"
)
SCREENING_RUNTIME_SATURATION_REROUTE = "SCREENING_RUNTIME_SATURATION_REROUTE"
SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC = (
    "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC"
)
SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE = (
    "SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE"
)
VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY = "VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY"
TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED = (
    "TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED"
)
TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA = "TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA"
TELEMETRY_DIAGNOSTIC_RUNTIME_SLOWDOWN = (
    "TELEMETRY_DIAGNOSTIC_RUNTIME_SLOWDOWN"
)
TELEMETRY_DIAGNOSTIC_RUNTIME_REGRESSION_RATE = (
    "TELEMETRY_DIAGNOSTIC_RUNTIME_REGRESSION_RATE"
)
TELEMETRY_DIAGNOSTIC_CANDIDATE_RUNTIME_FAILURE = (
    "TELEMETRY_DIAGNOSTIC_CANDIDATE_RUNTIME_FAILURE"
)
BRANCH_LIFECYCLE_RETAIN_HEAD = "BRANCH_LIFECYCLE_RETAIN_HEAD"
BRANCH_LIFECYCLE_RETAIN_CHECKPOINT = "BRANCH_LIFECYCLE_RETAIN_CHECKPOINT"
BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT = (
    "BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT"
)
BRANCH_LIFECYCLE_PARK_LINEAGE = "BRANCH_LIFECYCLE_PARK_LINEAGE"
BRANCH_LIFECYCLE_ARCHIVE_LINEAGE = "BRANCH_LIFECYCLE_ARCHIVE_LINEAGE"

_RUNTIME_CONFIDENCE_MIN_PAIRS = 4
_RUNTIME_SEVERE_SLOW_RATIO = 1.50
_RUNTIME_SEVERE_SLOW_DELTA_MS = 100.0


@dataclass(frozen=True)
class BranchLifecycleDecision:
    action: BranchLifecycleAction
    reason_codes: tuple[str, ...]
    next_zero_win_streak: int
    next_telemetry_diagnostic_streak: int = 0
    next_marginal_no_effect_streak: int = 0
    next_no_effect_diagnostic_followups: int = 0
    next_signal_signature: str = ""
    next_signal_signature_repeat_count: int = 0

    @property
    def soft_abandon(self) -> bool:
        return self.action in {"soft_abandon", "park_lineage", "archive_lineage"}

    @property
    def action_reason_code(self) -> str:
        return _action_reason_code(self.action)


@dataclass(frozen=True)
class BranchLifecyclePolicy:
    """Classify low-win screening branches without problem-specific semantics."""

    low_win_rate_threshold: float = 0.5
    zero_win_streak_limit: int = 3
    no_effect_followup_limit: int = 2
    marginal_no_effect_streak_limit: int = 2
    repeated_signal_signature_limit: int = 2
    rollback_budget_limit: int = 2
    soft_runtime_ratio_threshold: float = 1.10
    high_runtime_regression_rate: float = 0.90
    telemetry_diagnostic_streak_limit: int = 3
    diagnostic_zero_win_streak_limit: int = 2

    def decide(
        self,
        features: DecisionFeatures,
        *,
        current_zero_win_streak: int = 0,
        current_telemetry_diagnostic_streak: int = 0,
        current_marginal_no_effect_streak: int = 0,
        current_no_effect_diagnostic_followups: int = 0,
        last_signal_signature: str | None = None,
        current_signal_signature_repeat_count: int = 0,
        rollback_count: int = 0,
        branch_code_status: str = "",
        branch_screening_tier: str = "",
        has_checkpoint: bool = False,
    ) -> BranchLifecycleDecision:
        if features.telemetry_validation_repairable:
            return self._decide_telemetry_diagnostic(
                features,
                current_telemetry_diagnostic_streak=(
                    current_telemetry_diagnostic_streak
                ),
                branch_code_status=branch_code_status,
                branch_screening_tier=branch_screening_tier,
                has_checkpoint=has_checkpoint,
            )

        if not self._eligible_low_win_screening(features):
            return BranchLifecycleDecision(
                action="retain_head",
                reason_codes=(),
                next_zero_win_streak=current_zero_win_streak,
                next_telemetry_diagnostic_streak=0,
            )

        wins = max(0, int(features.wins or 0))
        losses = max(0, int(features.losses or 0))
        ties = max(0, int(features.ties or 0))
        pair_wins = max(0, int(getattr(features, "pair_wins", 0) or 0))
        pair_losses = max(0, int(getattr(features, "pair_losses", 0) or 0))
        next_zero_win_streak = 0 if wins > 0 else current_zero_win_streak + 1
        prior_evidence_tier = _branch_evidence_tier(
            branch_code_status,
            branch_screening_tier,
        )
        signal_signature = decision_features_signal_signature(features)
        previous_signature = str(last_signal_signature or "")
        next_signature_repeat_count = (
            max(0, int(current_signal_signature_repeat_count or 0)) + 1
            if previous_signature and previous_signature == signal_signature
            else 1
        )
        current_signal_tier = _screening_signal_tier(
            features,
            wins=wins,
            losses=losses,
            pair_wins=pair_wins,
            pair_losses=pair_losses,
            weak_positive=self._clear_weak_positive_case_signal(
                features,
                wins=wins,
                losses=losses,
            ),
        )
        next_marginal_no_effect_streak = (
            max(0, int(current_marginal_no_effect_streak or 0)) + 1
            if current_signal_tier in {"marginal", "no_effect"}
            else 0
        )
        prior_no_effect_followups = max(
            0,
            int(current_no_effect_diagnostic_followups or 0),
        )
        if prior_evidence_tier == "no_effect" and prior_no_effect_followups == 0:
            prior_no_effect_followups = 1
        next_no_effect_followups = (
            prior_no_effect_followups + 1
            if current_signal_tier == "no_effect"
            else 0
        )

        def build(
            *,
            action: BranchLifecycleAction,
            reason_codes: tuple[str, ...],
            zero_win_streak: int = next_zero_win_streak,
            telemetry_streak: int = 0,
        ) -> BranchLifecycleDecision:
            return BranchLifecycleDecision(
                action=action,
                reason_codes=reason_codes,
                next_zero_win_streak=zero_win_streak,
                next_telemetry_diagnostic_streak=telemetry_streak,
                next_marginal_no_effect_streak=next_marginal_no_effect_streak,
                next_no_effect_diagnostic_followups=next_no_effect_followups,
                next_signal_signature=signal_signature,
                next_signal_signature_repeat_count=next_signature_repeat_count,
            )

        if features.stale:
            return build(
                action="archive_lineage",
                reason_codes=(SCREENING_STALE_RESCREEN_FAIL,),
            )

        soft_reasons = self._soft_abandon_reasons(features, wins=wins, losses=losses)
        if (
            wins > 0
            and not prior_evidence_tier
            and set(soft_reasons) == {SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP}
        ):
            soft_reasons = ()
        if self._rollback_budget_exhausted(
            rollback_count=rollback_count,
            has_checkpoint=has_checkpoint,
        ):
            return build(
                action="park_lineage",
                reason_codes=tuple(
                    dict.fromkeys(
                        (
                            SCREENING_ROLLBACK_BUDGET_EXHAUSTED,
                            *soft_reasons,
                        )
                    )
                ),
            )
        if soft_reasons:
            action = self._regression_action(
                features,
                reason_codes=soft_reasons,
                branch_code_status=branch_code_status,
                branch_screening_tier=branch_screening_tier,
                has_checkpoint=has_checkpoint,
                rollback_count=rollback_count,
            )
            return build(
                action=action,
                reason_codes=soft_reasons,
            )

        diagnostic_reasons = self._low_signal_diagnostic_reasons(features)
        diagnostic_reroute_reasons = self._low_signal_diagnostic_reroute_reasons(
            features
        )
        if (
            current_signal_tier == "no_effect"
            and next_no_effect_followups >= self.no_effect_followup_limit
        ):
            return build(
                action="park_lineage",
                reason_codes=(SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED,),
            )
        if (
            current_signal_tier == "no_effect"
            and has_checkpoint
            and prior_evidence_tier == "weak_positive"
        ):
            return build(
                action="retain_checkpoint",
                reason_codes=(SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT,),
            )
        if (
            current_signal_tier in {"marginal", "no_effect"}
            and next_marginal_no_effect_streak
            >= self.marginal_no_effect_streak_limit
            and next_signature_repeat_count >= self.repeated_signal_signature_limit
        ):
            return build(
                action="park_lineage",
                reason_codes=(
                    SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED,
                    SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED,
                ),
            )
        if (
            wins == 0
            and diagnostic_reroute_reasons
            and next_zero_win_streak >= self.diagnostic_zero_win_streak_limit
        ):
            return build(
                action="park_lineage",
                reason_codes=diagnostic_reroute_reasons,
            )

        if wins == 0 and next_zero_win_streak >= self.zero_win_streak_limit:
            return build(
                action="park_lineage",
                reason_codes=(SCREENING_ZERO_WIN_STREAK_EXHAUSTED,),
            )

        if wins > 0 and self._clear_weak_positive_case_signal(
            features,
            wins=wins,
            losses=losses,
        ):
            return build(
                action="retain_head",
                reason_codes=(SCREENING_WEAK_SIGNAL_CONTINUE,),
                zero_win_streak=0,
            )
        if wins > 0:
            return build(
                action="retain_head",
                reason_codes=(SCREENING_MARGINAL_SIGNAL_CONTINUE,),
                zero_win_streak=0,
            )

        if pair_wins > 0:
            return build(
                action="retain_head",
                reason_codes=(
                    SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
                    *diagnostic_reasons,
                ),
                zero_win_streak=(
                    next_zero_win_streak if diagnostic_reasons else 0
                ),
            )

        reason = (
            SCREENING_NEUTRAL_SIGNAL_CONTINUE
            if self._mostly_ties(features, ties=ties, losses=losses)
            else SCREENING_ZERO_WIN_STREAK_CONTINUE
        )
        return build(
            action="retain_head",
            reason_codes=(reason, *diagnostic_reasons),
        )

    def _decide_telemetry_diagnostic(
        self,
        features: DecisionFeatures,
        *,
        current_telemetry_diagnostic_streak: int,
        branch_code_status: str = "",
        branch_screening_tier: str = "",
        has_checkpoint: bool = False,
    ) -> BranchLifecycleDecision:
        next_streak = max(0, current_telemetry_diagnostic_streak) + 1
        severe_reasons = self._telemetry_diagnostic_abandon_reasons(features)
        if severe_reasons:
            return BranchLifecycleDecision(
                action="archive_lineage",
                reason_codes=severe_reasons,
                next_zero_win_streak=0,
                next_telemetry_diagnostic_streak=next_streak,
            )
        if next_streak >= self.telemetry_diagnostic_streak_limit:
            return BranchLifecycleDecision(
                action=(
                    "retain_checkpoint"
                    if has_checkpoint
                    and _branch_evidence_tier(
                        branch_code_status,
                        branch_screening_tier,
                    )
                    == "weak_positive"
                    else "park_lineage"
                ),
                reason_codes=(TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,),
                next_zero_win_streak=0,
                next_telemetry_diagnostic_streak=next_streak,
            )
        reason = (
            VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY
            if features.stage == "validation"
            else SCREENING_TELEMETRY_DIAGNOSTIC_RETRY
        )
        return BranchLifecycleDecision(
            action="retain_head",
            reason_codes=(reason,),
            next_zero_win_streak=0,
            next_telemetry_diagnostic_streak=next_streak,
        )

    def _eligible_low_win_screening(self, features: DecisionFeatures) -> bool:
        return (
            features.stage == "screening"
            and features.win_rate is not None
            and features.win_rate < self.low_win_rate_threshold
            and not features.telemetry_validation_repairable
        )

    def _clear_weak_positive_case_signal(
        self,
        features: DecisionFeatures,
        *,
        wins: int,
        losses: int,
    ) -> bool:
        if wins <= losses:
            return False
        ci_low = getattr(features, "ci_low", None)
        ci_high = getattr(features, "ci_high", None)
        if ci_low is not None and ci_high is not None and ci_low < 0 < ci_high:
            return False
        return True

    def _soft_abandon_reasons(
        self,
        features: DecisionFeatures,
        *,
        wins: int,
        losses: int,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if losses > 0 and wins == 0:
            reasons.append(SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN)
        if wins > 0 and losses >= wins + 2:
            reasons.append(SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP)
        if (
            features.ci_low is not None
            and features.ci_high is not None
            and features.ci_low < 0
            and features.ci_high <= 0
        ):
            reasons.append(SCREENING_SOFT_ABANDON_NON_POSITIVE_CI)
        if features.candidate_failed_pairs > 0:
            reasons.append(SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE)
        if features.median_delta is not None and features.median_delta < 0:
            reasons.append(SCREENING_SOFT_ABANDON_NEGATIVE_DELTA)
        if (
            features.runtime_ratio_median is not None
            and features.runtime_ratio_median > self.soft_runtime_ratio_threshold
            and self._runtime_evidence_confident(features)
        ):
            reasons.append(SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN)
        if (
            features.runtime_regression_rate is not None
            and features.runtime_regression_rate >= self.high_runtime_regression_rate
            and self._runtime_evidence_confident(features)
        ):
            reasons.append(SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE)
        return tuple(dict.fromkeys(reasons))

    def _telemetry_diagnostic_abandon_reasons(
        self,
        features: DecisionFeatures,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if features.candidate_failed_pairs > 0:
            reasons.append(TELEMETRY_DIAGNOSTIC_CANDIDATE_RUNTIME_FAILURE)
        return tuple(dict.fromkeys(reasons))

    def _regression_action(
        self,
        features: DecisionFeatures,
        *,
        reason_codes: tuple[str, ...],
        branch_code_status: str,
        branch_screening_tier: str,
        has_checkpoint: bool,
        rollback_count: int,
    ) -> BranchLifecycleAction:
        reason_set = set(reason_codes)
        if (
            SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE in reason_set
            or features.candidate_failed_pairs > 0
        ):
            return "archive_lineage"
        tier = _branch_evidence_tier(branch_code_status, branch_screening_tier)
        if tier == "weak_positive" and has_checkpoint:
            if self._rollback_budget_exhausted(
                rollback_count=rollback_count,
                has_checkpoint=has_checkpoint,
            ):
                return "park_lineage"
            return "rollback_to_checkpoint"
        if tier in {"marginal", "no_effect"}:
            return "park_lineage"
        return "archive_lineage"

    def _rollback_budget_exhausted(
        self,
        *,
        rollback_count: int,
        has_checkpoint: bool,
    ) -> bool:
        return (
            has_checkpoint
            and max(0, int(rollback_count or 0)) >= self.rollback_budget_limit
        )

    @staticmethod
    def _low_signal_diagnostic_reasons(
        features: DecisionFeatures,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if features.runtime_budget_saturation_diagnostic:
            reasons.append(SCREENING_RUNTIME_SATURATION_DIAGNOSTIC)
        if features.telemetry_effect_zero_diagnostic:
            reasons.append(SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC)
        return tuple(reasons)

    @staticmethod
    def _low_signal_diagnostic_reroute_reasons(
        features: DecisionFeatures,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if features.runtime_budget_saturation_diagnostic:
            reasons.append(SCREENING_RUNTIME_SATURATION_REROUTE)
        if features.telemetry_effect_zero_diagnostic:
            reasons.append(SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE)
        return tuple(reasons)

    @staticmethod
    def _mostly_ties(
        features: DecisionFeatures,
        *,
        ties: int,
        losses: int,
    ) -> bool:
        observed = features.valid_pairs or features.attempted_pairs or features.n_cases
        if observed <= 0:
            observed = ties + losses
        if observed <= 0:
            return False
        return ties / observed >= 0.5

    @staticmethod
    def _runtime_evidence_confident(features: DecisionFeatures) -> bool:
        confidence = str(
            getattr(features, "runtime_evidence_confidence", "") or ""
        ).lower()
        if (
            confidence.startswith("low")
            or "cached" in confidence
            or confidence in {"missing", "unknown"}
        ):
            return False
        runtime_pairs = int(features.runtime_pairs or 0)
        if runtime_pairs >= _RUNTIME_CONFIDENCE_MIN_PAIRS:
            return True
        severe_ratio = (
            features.runtime_ratio_median is not None
            and features.runtime_ratio_median >= _RUNTIME_SEVERE_SLOW_RATIO
        )
        severe_delta = (
            features.runtime_delta_median_ms is not None
            and features.runtime_delta_median_ms >= _RUNTIME_SEVERE_SLOW_DELTA_MS
        )
        severe_rate = (
            features.runtime_regression_rate is not None
            and features.runtime_regression_rate >= 0.90
        )
        return bool(severe_ratio and severe_delta and severe_rate)


def decision_features_signal_signature(features: DecisionFeatures) -> str:
    """Return a generic evidence signature for lifecycle loop detection."""

    wins = max(0, int(getattr(features, "wins", 0) or 0))
    losses = max(0, int(getattr(features, "losses", 0) or 0))
    ties = max(0, int(getattr(features, "ties", 0) or 0))
    pair_wins = max(0, int(getattr(features, "pair_wins", 0) or 0))
    pair_losses = max(0, int(getattr(features, "pair_losses", 0) or 0))
    effect_status = generic_effect_status(
        wins=wins,
        losses=losses,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        median_delta=getattr(features, "median_delta", None),
        telemetry_effect_zero=bool(
            getattr(features, "telemetry_effect_zero_diagnostic", False)
        ),
        runtime_budget_saturation=bool(
            getattr(features, "runtime_budget_saturation_diagnostic", False)
        ),
        candidate_failed_pairs=max(
            0,
            int(getattr(features, "candidate_failed_pairs", 0) or 0),
        ),
    )
    return generic_evidence_signature(
        wins=wins,
        losses=losses,
        ties=ties,
        median_delta=getattr(features, "median_delta", None),
        ci_low=getattr(features, "ci_low", None),
        ci_high=getattr(features, "ci_high", None),
        runtime_ratio_median=getattr(features, "runtime_ratio_median", None),
        runtime_delta_median_ms=getattr(features, "runtime_delta_median_ms", None),
        runtime_regression_rate=getattr(features, "runtime_regression_rate", None),
        runtime_pairs=max(0, int(getattr(features, "runtime_pairs", 0) or 0)),
        effect_status=effect_status,
    )


def generic_evidence_signature(
    *,
    wins: int,
    losses: int,
    ties: int,
    median_delta: float | None,
    ci_low: float | None,
    ci_high: float | None,
    runtime_ratio_median: float | None,
    runtime_delta_median_ms: float | None,
    runtime_regression_rate: float | None,
    runtime_pairs: int,
    effect_status: str,
) -> str:
    """Compact generic lifecycle signature; intentionally domain-neutral."""

    parts = (
        f"wins={max(0, int(wins or 0))}",
        f"losses={max(0, int(losses or 0))}",
        f"ties={max(0, int(ties or 0))}",
        f"median_delta={_float_token(median_delta)}",
        f"ci_low={_float_token(ci_low)}",
        f"ci_high={_float_token(ci_high)}",
        f"runtime_ratio_median={_float_token(runtime_ratio_median)}",
        f"runtime_delta_median_ms={_float_token(runtime_delta_median_ms)}",
        f"runtime_regression_rate={_float_token(runtime_regression_rate)}",
        f"runtime_pairs={max(0, int(runtime_pairs or 0))}",
        f"effect_status={_status_token(effect_status)}",
    )
    return ";".join(parts)


def generic_effect_status(
    *,
    wins: int,
    losses: int,
    pair_wins: int,
    pair_losses: int,
    median_delta: float | None,
    telemetry_effect_zero: bool = False,
    runtime_budget_saturation: bool = False,
    candidate_failed_pairs: int = 0,
) -> str:
    if candidate_failed_pairs > 0:
        return "candidate_runtime_failure"
    if telemetry_effect_zero:
        return "telemetry_effect_zero"
    if wins > 0 or pair_wins > 0 or _positive_float(median_delta):
        return "objective_positive"
    if losses > 0 or pair_losses > 0 or _negative_float(median_delta):
        return "objective_negative"
    if runtime_budget_saturation:
        return "runtime_budget_no_objective_effect"
    return "no_objective_effect"


def _screening_signal_tier(
    features: DecisionFeatures,
    *,
    wins: int,
    losses: int,
    pair_wins: int,
    pair_losses: int,
    weak_positive: bool,
) -> str:
    if weak_positive:
        return "weak_positive"
    if wins > 0 or pair_wins > 0:
        return "marginal"
    if _no_objective_effect(
        features,
        wins=wins,
        losses=losses,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
    ):
        return "no_effect"
    if losses > 0 or pair_losses > 0:
        return "regression"
    return "uncertain"


def _no_objective_effect(
    features: DecisionFeatures,
    *,
    wins: int,
    losses: int,
    pair_wins: int,
    pair_losses: int,
) -> bool:
    if wins or losses or pair_wins or pair_losses:
        return False
    median_delta = getattr(features, "median_delta", None)
    return median_delta is None or abs(float(median_delta)) <= 1e-12


def _float_token(value: float | None) -> str:
    if value is None:
        return "none"
    number = float(value)
    if not isfinite(number):
        return "nonfinite"
    return f"{number:.6g}"


def _status_token(value: str) -> str:
    token = str(value or "unknown").strip().lower()
    return token if token.replace("_", "").isalnum() else "unknown"


def _positive_float(value: float | None) -> bool:
    return value is not None and float(value) > 1e-12


def _negative_float(value: float | None) -> bool:
    return value is not None and float(value) < -1e-12


def _branch_evidence_tier(
    branch_code_status: str,
    branch_screening_tier: str,
) -> str:
    status = str(branch_code_status or "")
    tier = str(branch_screening_tier or "")
    if tier in {"weak_positive", "marginal", "no_effect"}:
        return tier
    if status == "active_weak_positive":
        return "weak_positive"
    if status == "active_marginal":
        return "marginal"
    if status == "active_no_effect":
        return "no_effect"
    return ""


def _action_reason_code(action: BranchLifecycleAction) -> str:
    return {
        "retain_head": BRANCH_LIFECYCLE_RETAIN_HEAD,
        "retain_checkpoint": BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
        "rollback_to_checkpoint": BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
        "park_lineage": BRANCH_LIFECYCLE_PARK_LINEAGE,
        "archive_lineage": BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
        "keep_exploring": BRANCH_LIFECYCLE_RETAIN_HEAD,
        "soft_abandon": BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    }[action]


__all__ = [
    "BranchLifecycleDecision",
    "BranchLifecyclePolicy",
    "BRANCH_LIFECYCLE_ARCHIVE_LINEAGE",
    "BRANCH_LIFECYCLE_PARK_LINEAGE",
    "BRANCH_LIFECYCLE_RETAIN_CHECKPOINT",
    "BRANCH_LIFECYCLE_RETAIN_HEAD",
    "BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT",
    "decision_features_signal_signature",
    "generic_effect_status",
    "generic_evidence_signature",
    "SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL",
    "SCREENING_MARGINAL_NO_EFFECT_LOOP_EXHAUSTED",
    "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
    "SCREENING_NO_EFFECT_AFTER_RETAINED_CHECKPOINT",
    "SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED",
    "SCREENING_REPEATED_SIGNAL_SIGNATURE_EXHAUSTED",
    "SCREENING_ROLLBACK_BUDGET_EXHAUSTED",
    "SCREENING_SOFT_ABANDON_CANDIDATE_RUNTIME_FAILURE",
    "SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP",
    "SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN",
    "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",
    "SCREENING_SOFT_ABANDON_NON_POSITIVE_CI",
    "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE",
    "SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN",
    "SCREENING_STALE_RESCREEN_FAIL",
    "SCREENING_RUNTIME_SATURATION_DIAGNOSTIC",
    "SCREENING_RUNTIME_SATURATION_REROUTE",
    "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
    "SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE",
    "SCREENING_TELEMETRY_DIAGNOSTIC_RETRY",
    "SCREENING_WEAK_SIGNAL_CONTINUE",
    "SCREENING_ZERO_WIN_STREAK_CONTINUE",
    "SCREENING_ZERO_WIN_STREAK_EXHAUSTED",
    "TELEMETRY_DIAGNOSTIC_CANDIDATE_RUNTIME_FAILURE",
    "TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA",
    "TELEMETRY_DIAGNOSTIC_RUNTIME_REGRESSION_RATE",
    "TELEMETRY_DIAGNOSTIC_RUNTIME_SLOWDOWN",
    "TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED",
    "VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY",
]
