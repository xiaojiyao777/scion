"""Screening feedback tiering for proposal guidance.

The tier is a prompt/lifecycle signal only. It is derived from screening-stage
aggregate summaries and must not be consumed by promotion decisions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from scion.core.branch_lifecycle_policy import SCREENING_MARGINAL_SIGNAL_CONTINUE
from scion.core.models import ExperimentStage, ProtocolResult
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    opportunity_diagnostics_for_protocol,
    opportunity_status_for_diagnostics,
    runtime_confidence_for_protocol,
)
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    telemetry_decision_details,
    telemetry_failure_categories,
)
from scion.proposal.runtime_aggregate_feedback import (
    BUDGET_EXHAUSTING_RUNTIME_INTERPRETATION,
    runtime_aggregate_feedback_payload,
    runtime_model_from_protocol,
)

ScreeningFeedbackTier = Literal[
    "invalid",
    "inactive",
    "weak_positive",
    "marginal",
    "no_effect",
    "quality_regression",
    "runtime_regression",
    "promotable",
    "uncertain",
]

_EPS = 1e-12
_RUNTIME_SLOW_DELTA_MS = 5.0
_RUNTIME_SLOW_RATIO = 1.10
_RUNTIME_REGRESSION_RATE = 0.90
_RUNTIME_CONFIDENCE_MIN_PAIRS = 4
_RUNTIME_SEVERE_SLOW_RATIO = 1.50
_RUNTIME_SEVERE_SLOW_DELTA_MS = 100.0
_SCREENING_MARGINAL_PASS_CODES = frozenset(
    {
        "SCREENING_PASS_MARGINAL_DELTA",
        "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE",
        "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS",
    }
)


@dataclass(frozen=True)
class ScreeningFeedbackSummary:
    tier: ScreeningFeedbackTier
    case_wins: int
    case_losses: int
    case_ties: int
    pair_wins: int
    pair_losses: int
    pair_ties: int
    median_delta: float | None
    runtime_ratio_median: float | None
    runtime_delta_median_ms: float | None
    runtime_regression_rate: float | None
    runtime_model: str
    runtime_regression_rate_interpretation: str | None
    runtime_pairs: int
    activation_status: str
    effect_status: str
    why_not_promoted: str
    allowed_followup_variants: tuple[str, ...]
    repeat_unchanged_allowed: bool
    reason_codes: tuple[str, ...] = ()
    gate_observation_reason_codes: tuple[str, ...] = ()
    lifecycle_action_reason_codes: tuple[str, ...] = ()
    runtime_confidence: str = "unknown"
    opportunity_status: str = "unknown"
    opportunity_diagnostics: tuple[str, ...] = ()
    mechanism_evidence: Mapping[str, Any] = field(default_factory=dict)
    phase_causal_summary: Mapping[str, Any] = field(default_factory=dict)
    feedback_digest: str = ""

    @property
    def pair_total(self) -> int:
        return self.pair_wins + self.pair_losses + self.pair_ties

    @property
    def case_total(self) -> int:
        return self.case_wins + self.case_losses + self.case_ties

    def to_payload(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "case_summary": {
                "wins": self.case_wins,
                "losses": self.case_losses,
                "ties": self.case_ties,
                "total": self.case_total,
            },
            "pair_summary": {
                "wins": self.pair_wins,
                "losses": self.pair_losses,
                "ties": self.pair_ties,
                "total": self.pair_total,
            },
            "median_delta": self.median_delta,
            "runtime_summary": self.runtime_summary_payload(),
            "activation_status": self.activation_status,
            "effect_status": self.effect_status,
            "runtime_confidence": self.runtime_confidence,
            "opportunity_status": self.opportunity_status,
            "opportunity_diagnostics": list(self.opportunity_diagnostics),
            "mechanism_evidence": dict(self.mechanism_evidence or {}),
            "phase_causal_summary": dict(self.phase_causal_summary or {}),
            "why_not_promoted": self.why_not_promoted,
            "allowed_followup_variants": list(self.allowed_followup_variants),
            "repeat_unchanged_allowed": self.repeat_unchanged_allowed,
            "reason_codes": list(self.reason_codes),
            "gate_observation_reason_codes": list(
                self.gate_observation_reason_codes
            ),
            "lifecycle_action_reason_codes": list(
                self.lifecycle_action_reason_codes
            ),
            "feedback_digest": self.feedback_digest,
            "promotion_boundary": "unchanged_decision_features_and_gates",
        }

    def runtime_summary_payload(self) -> dict[str, Any]:
        return runtime_aggregate_feedback_payload(
            runtime_ratio_median=self.runtime_ratio_median,
            runtime_delta_median_ms=self.runtime_delta_median_ms,
            runtime_regression_rate=self.runtime_regression_rate,
            runtime_model=self.runtime_model,
            runtime_regression_rate_interpretation=(
                self.runtime_regression_rate_interpretation
            ),
            runtime_pairs=self.runtime_pairs,
        )


def screening_feedback_summary(
    protocol: ProtocolResult | None,
    *,
    decision_reason_codes: tuple[str, ...] = (),
) -> ScreeningFeedbackSummary:
    """Return the generic screening feedback tier for a protocol result."""

    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        return _summary(
            tier="uncertain",
            why_not_promoted="no screening result available",
        )

    stats = protocol.stats
    case_wins = _safe_int(getattr(stats, "wins", 0))
    case_losses = _safe_int(getattr(stats, "losses", 0))
    case_ties = _safe_int(getattr(stats, "ties", 0))
    pair_wins, pair_losses, pair_ties = _pair_counts(protocol)
    median_delta = _optional_float(getattr(stats, "median_delta", None))
    runtime_ratio = _optional_float(getattr(stats, "runtime_ratio_median", None))
    runtime_delta = _optional_float(getattr(stats, "runtime_delta_median_ms", None))
    runtime_regression_rate = _optional_float(
        getattr(stats, "runtime_regression_rate", None)
    )
    runtime_pairs = _safe_int(getattr(stats, "runtime_pairs", 0))
    runtime_model = runtime_model_from_protocol(protocol)
    runtime_regression_rate_interpretation = (
        BUDGET_EXHAUSTING_RUNTIME_INTERPRETATION
        if runtime_model == "budget_exhausting"
        else None
    )
    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (
                tuple(decision_reason_codes or ())
                + tuple(getattr(protocol, "reason_codes", ()) or ())
            )
            if str(code).strip()
        )
    )
    reason_code_groups = classify_reason_codes(
        reason_codes,
        protocol_reason_codes=getattr(protocol, "reason_codes", ()) or (),
    )
    activation_status = _activation_status(protocol)
    effect_status = _effect_status(
        case_wins=case_wins,
        case_losses=case_losses,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        median_delta=median_delta,
    )

    invalid = _has_candidate_execution_failure(protocol)
    objective_positive = case_wins > 0 or pair_wins > 0
    case_marginal_positive = (
        case_wins > 0
        and (
            case_wins <= case_losses
            or _confidence_interval_crosses_negative(stats)
        )
    )
    quality_non_positive_ci = (
        getattr(stats, "ci_low", None) is not None
        and getattr(stats, "ci_high", None) is not None
        and float(getattr(stats, "ci_low")) < -_EPS
        and float(getattr(stats, "ci_high")) <= _EPS
    )
    lifecycle_marginal_continue = SCREENING_MARGINAL_SIGNAL_CONTINUE in reason_codes
    loss_heavy_positive = case_wins > 0 and case_losses >= case_wins + 2
    quality_negative = (
        (median_delta is not None and median_delta < -_EPS)
        or quality_non_positive_ci
        or (loss_heavy_positive and not lifecycle_marginal_continue)
        or (case_losses > 0 and case_wins == 0)
        or (pair_losses > 0 and pair_wins == 0 and case_wins == 0)
    )
    no_objective_effect = (
        case_wins == 0
        and case_losses == 0
        and pair_wins == 0
        and pair_losses == 0
        and (median_delta is None or abs(median_delta) <= _EPS)
    )
    runtime_slowdown = _runtime_slowdown(
        runtime_ratio=runtime_ratio,
        runtime_delta=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=runtime_pairs,
        runtime_model=runtime_model,
    )
    runtime_confidence = runtime_confidence_for_protocol(
        protocol,
        runtime_ratio=runtime_ratio,
        runtime_delta=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=runtime_pairs,
    )
    mechanism_evidence = mechanism_evidence_for_protocol(protocol)
    opportunity_diagnostics = opportunity_diagnostics_for_protocol(
        protocol,
        mechanism_evidence=mechanism_evidence,
        no_objective_effect=no_objective_effect,
    )
    opportunity_status = opportunity_status_for_diagnostics(
        opportunity_diagnostics,
        existing=str(getattr(protocol, "opportunity_status", "") or ""),
    )

    marginal_diagnostic_pass = _is_marginal_diagnostic_screening_pass(
        protocol,
        reason_codes=reason_codes,
    )

    if invalid:
        tier: ScreeningFeedbackTier = "invalid"
    elif quality_negative:
        tier = "quality_regression"
    elif marginal_diagnostic_pass:
        tier = "marginal"
    elif protocol.gate_outcome == "pass":
        tier = "promotable"
    elif activation_status == "not_observed":
        tier = "inactive"
    elif case_marginal_positive:
        tier = "marginal"
    elif objective_positive:
        tier = "weak_positive"
    elif no_objective_effect and runtime_slowdown:
        tier = "runtime_regression"
    elif no_objective_effect:
        tier = "no_effect"
    else:
        tier = "uncertain"

    why = _why_not_promoted(
        tier=tier,
        reason_codes=reason_codes,
        gate_outcome=protocol.gate_outcome,
    )
    variants = _allowed_followup_variants(tier)
    repeat_unchanged = tier in {"promotable", "uncertain"}
    summary = _summary(
        tier=tier,
        case_wins=case_wins,
        case_losses=case_losses,
        case_ties=case_ties,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        pair_ties=pair_ties,
        median_delta=median_delta,
        runtime_ratio_median=runtime_ratio,
        runtime_delta_median_ms=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_model=runtime_model,
        runtime_regression_rate_interpretation=(
            runtime_regression_rate_interpretation
        ),
        runtime_pairs=runtime_pairs,
        activation_status=activation_status,
        effect_status=effect_status,
        why_not_promoted=why,
        allowed_followup_variants=variants,
        repeat_unchanged_allowed=repeat_unchanged,
        reason_codes=reason_codes,
        gate_observation_reason_codes=(
            reason_code_groups.gate_observation_reason_codes
        ),
        lifecycle_action_reason_codes=(
            reason_code_groups.lifecycle_action_reason_codes
        ),
        runtime_confidence=runtime_confidence,
        opportunity_status=opportunity_status,
        opportunity_diagnostics=opportunity_diagnostics,
        mechanism_evidence=mechanism_evidence,
        phase_causal_summary=_phase_causal_summary(
            tier=tier,
            gate_outcome=protocol.gate_outcome,
            case_wins=case_wins,
            case_losses=case_losses,
            case_ties=case_ties,
            pair_wins=pair_wins,
            pair_losses=pair_losses,
            pair_ties=pair_ties,
            median_delta=median_delta,
            runtime_confidence=runtime_confidence,
            activation_status=activation_status,
            effect_status=effect_status,
            opportunity_status=opportunity_status,
            mechanism_evidence=mechanism_evidence,
            runtime_ratio=runtime_ratio,
            runtime_delta=runtime_delta,
            runtime_regression_rate=runtime_regression_rate,
            runtime_model=runtime_model,
            runtime_regression_rate_interpretation=(
                runtime_regression_rate_interpretation
            ),
        ),
    )
    return _with_digest(summary)


def _confidence_interval_crosses_negative(stats: Any) -> bool:
    ci_low = getattr(stats, "ci_low", None)
    ci_high = getattr(stats, "ci_high", None)
    if ci_low is None or ci_high is None:
        return False
    return float(ci_low) < -_EPS and float(ci_high) > _EPS


def _summary(
    *,
    tier: ScreeningFeedbackTier,
    case_wins: int = 0,
    case_losses: int = 0,
    case_ties: int = 0,
    pair_wins: int = 0,
    pair_losses: int = 0,
    pair_ties: int = 0,
    median_delta: float | None = None,
    runtime_ratio_median: float | None = None,
    runtime_delta_median_ms: float | None = None,
    runtime_regression_rate: float | None = None,
    runtime_model: str = "",
    runtime_regression_rate_interpretation: str | None = None,
    runtime_pairs: int = 0,
    activation_status: str = "unknown",
    effect_status: str = "uncertain",
    why_not_promoted: str = "",
    allowed_followup_variants: tuple[str, ...] = (),
    repeat_unchanged_allowed: bool = True,
    reason_codes: tuple[str, ...] = (),
    gate_observation_reason_codes: tuple[str, ...] = (),
    lifecycle_action_reason_codes: tuple[str, ...] = (),
    runtime_confidence: str = "unknown",
    opportunity_status: str = "unknown",
    opportunity_diagnostics: tuple[str, ...] = (),
    mechanism_evidence: Mapping[str, Any] | None = None,
    phase_causal_summary: Mapping[str, Any] | None = None,
) -> ScreeningFeedbackSummary:
    return ScreeningFeedbackSummary(
        tier=tier,
        case_wins=case_wins,
        case_losses=case_losses,
        case_ties=case_ties,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        pair_ties=pair_ties,
        median_delta=median_delta,
        runtime_ratio_median=runtime_ratio_median,
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_regression_rate=runtime_regression_rate,
        runtime_model=runtime_model,
        runtime_regression_rate_interpretation=(
            runtime_regression_rate_interpretation
        ),
        runtime_pairs=runtime_pairs,
        activation_status=activation_status,
        effect_status=effect_status,
        why_not_promoted=why_not_promoted,
        allowed_followup_variants=allowed_followup_variants,
        repeat_unchanged_allowed=repeat_unchanged_allowed,
        reason_codes=reason_codes,
        gate_observation_reason_codes=gate_observation_reason_codes,
        lifecycle_action_reason_codes=lifecycle_action_reason_codes,
        runtime_confidence=runtime_confidence,
        opportunity_status=opportunity_status,
        opportunity_diagnostics=opportunity_diagnostics,
        mechanism_evidence=mechanism_evidence or {},
        phase_causal_summary=phase_causal_summary or {},
    )


def _with_digest(summary: ScreeningFeedbackSummary) -> ScreeningFeedbackSummary:
    payload = summary.to_payload()
    payload.pop("feedback_digest", None)
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return ScreeningFeedbackSummary(
        **{
            **summary.__dict__,
            "feedback_digest": f"screening-feedback:{digest}",
        }
    )


def _pair_counts(protocol: ProtocolResult) -> tuple[int, int, int]:
    wins = losses = ties = 0
    for feedback in protocol.pair_feedback or ():
        comparison = str(getattr(feedback, "comparison", "") or "")
        if comparison == "win":
            wins += 1
        elif comparison == "loss":
            losses += 1
        else:
            ties += 1
    return wins, losses, ties


def _activation_status(protocol: ProtocolResult) -> str:
    mechanism_evidence = mechanism_evidence_for_protocol(protocol)
    primary_activation = str(
        mechanism_evidence.get("primary_activation_status") or ""
    ).strip().lower()
    primary_kind = str(
        mechanism_evidence.get("primary_diagnostic_kind") or ""
    ).strip().lower()
    if primary_activation in {"observed", "positive", "activation_observed"}:
        return "observed"
    if (
        primary_activation in {"missing", "inactive", "not_observed", "zero"}
        or primary_kind == "not_evaluated/not_triggered"
    ) and not bool(mechanism_evidence.get("hook_activation_observed")):
        return "not_observed"
    if formal_telemetry_guard_failed(protocol):
        categories = set(telemetry_failure_categories(protocol))
        details = telemetry_decision_details(protocol)
        if categories.intersection({"activation", "activity"}):
            if any(_detail_counter(detail, "candidate_positive") <= 0 for detail in details):
                return "not_observed"
    if _safe_int(getattr(protocol, "candidate_operator_attempts", 0)) > 0:
        return "observed"
    if _safe_int(getattr(protocol, "candidate_operator_accepted", 0)) > 0:
        return "observed"
    if _telemetry_guard_passed(protocol):
        return "observed"
    return "unknown"


def _effect_status(
    *,
    case_wins: int,
    case_losses: int,
    pair_wins: int,
    pair_losses: int,
    median_delta: float | None,
) -> str:
    if case_wins > 0:
        return "case_level_positive_signal"
    if pair_wins > 0:
        return "pair_level_positive_signal"
    if median_delta is not None and median_delta < -_EPS:
        return "quality_negative_signal"
    if case_losses > 0 or pair_losses > 0:
        return "loss_signal"
    if median_delta is None or abs(median_delta) <= _EPS:
        return "no_objective_effect"
    return "uncertain"


def _has_candidate_execution_failure(protocol: ProtocolResult) -> bool:
    stats = protocol.stats
    if _safe_int(getattr(stats, "candidate_failed_pairs", 0)) > 0:
        return True
    if (
        _safe_int(getattr(stats, "valid_pairs", 0)) == 0
        and _safe_int(getattr(stats, "failed_pairs", 0)) > 0
    ):
        return True
    categories = getattr(protocol, "candidate_runtime_failure_categories", {}) or {}
    if isinstance(categories, Mapping):
        return any(_safe_int(value) > 0 for value in categories.values())
    return False


def _runtime_slowdown(
    *,
    runtime_ratio: float | None,
    runtime_delta: float | None,
    runtime_regression_rate: float | None,
    runtime_pairs: int,
    runtime_model: str,
) -> bool:
    if runtime_model == "budget_exhausting":
        return False
    confidence = _runtime_confidence(
        runtime_ratio=runtime_ratio,
        runtime_delta=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=runtime_pairs,
    )
    if confidence != "sufficient":
        return False
    if runtime_ratio is not None and runtime_ratio > _RUNTIME_SLOW_RATIO:
        return True
    if runtime_delta is not None and runtime_delta >= _RUNTIME_SLOW_DELTA_MS:
        return True
    if (
        runtime_regression_rate is not None
        and runtime_regression_rate >= _RUNTIME_REGRESSION_RATE
    ):
        return True
    return False


def _runtime_confidence(
    *,
    runtime_ratio: float | None,
    runtime_delta: float | None,
    runtime_regression_rate: float | None,
    runtime_pairs: int,
) -> str:
    if runtime_pairs <= 0:
        return "missing"
    if runtime_pairs >= _RUNTIME_CONFIDENCE_MIN_PAIRS:
        return "sufficient"
    severe_ratio = (
        runtime_ratio is not None and runtime_ratio >= _RUNTIME_SEVERE_SLOW_RATIO
    )
    severe_delta = (
        runtime_delta is not None and runtime_delta >= _RUNTIME_SEVERE_SLOW_DELTA_MS
    )
    severe_rate = (
        runtime_regression_rate is not None
        and runtime_regression_rate >= _RUNTIME_REGRESSION_RATE
    )
    if severe_ratio and severe_delta and severe_rate:
        return "sufficient"
    return "low_sample_diagnostic"


def _why_not_promoted(
    *,
    tier: ScreeningFeedbackTier,
    reason_codes: tuple[str, ...],
    gate_outcome: str,
) -> str:
    primary = _primary_reason(reason_codes)
    if tier == "promotable":
        return "screening gate passed"
    if tier == "invalid":
        return primary or "candidate execution failed during screening"
    if tier == "inactive":
        return primary or "mechanism activity or activation was not observed"
    if tier == "weak_positive":
        return (
            (primary + "; " if primary else "")
            + "weak_positive is not promotable; screening gate remains authoritative"
        )
    if tier == "marginal":
        return (
            (primary + "; " if primary else "")
            + "marginal mixed signal is not a weak-positive exploit signal"
        )
    if tier == "no_effect":
        return primary or "active screening produced no case-level or pair-level effect"
    if tier == "quality_regression":
        return primary or "objective quality regressed or losses dominated"
    if tier == "runtime_regression":
        return primary or "no objective effect and runtime regressed"
    return primary or f"screening outcome remained {gate_outcome}"


def _is_marginal_diagnostic_screening_pass(
    protocol: ProtocolResult,
    *,
    reason_codes: tuple[str, ...],
) -> bool:
    if getattr(protocol, "stage", None) != ExperimentStage.SCREENING:
        return False
    if str(getattr(protocol, "gate_outcome", "") or "") != "pass":
        return False
    return any(code in _SCREENING_MARGINAL_PASS_CODES for code in reason_codes)


def _phase_causal_summary(
    *,
    tier: ScreeningFeedbackTier,
    gate_outcome: str,
    case_wins: int,
    case_losses: int,
    case_ties: int,
    pair_wins: int,
    pair_losses: int,
    pair_ties: int,
    median_delta: float | None,
    runtime_confidence: str,
    activation_status: str,
    effect_status: str,
    opportunity_status: str,
    mechanism_evidence: Mapping[str, Any],
    runtime_ratio: float | None,
    runtime_delta: float | None,
    runtime_regression_rate: float | None,
    runtime_model: str,
    runtime_regression_rate_interpretation: str | None,
) -> dict[str, Any]:
    """Return bounded proposal-only causal feedback for screening evidence."""

    activation_evidence_status = str(
        mechanism_evidence.get("activation_evidence_status") or "unknown"
    )
    objective_effect_status = str(
        mechanism_evidence.get("objective_effect_status") or "unknown"
    )
    primary_activation_status = str(
        mechanism_evidence.get("primary_activation_status") or ""
    ).strip()
    primary_effect_status = str(
        mechanism_evidence.get("primary_effect_status") or ""
    ).strip()
    phase_positive = _phase_positive(
        activation_status=activation_status,
        effect_status=effect_status,
        activation_evidence_status=activation_evidence_status,
        objective_effect_status=objective_effect_status,
        primary_activation_status=primary_activation_status,
        primary_effect_status=primary_effect_status,
    )
    objective_loss = _objective_loss_signal(
        case_losses=case_losses,
        pair_losses=pair_losses,
        median_delta=median_delta,
    )
    no_objective_effect = _objective_no_effect(
        case_wins=case_wins,
        case_losses=case_losses,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        median_delta=median_delta,
    )
    pair_win_case_tie = (
        pair_wins > 0
        and case_wins == 0
        and case_losses == 0
        and case_ties > 0
    )
    if activation_status == "not_observed":
        classification = "activation_not_observed"
        summary = "activation was not observed in formal screening telemetry"
        interpretation = (
            "repair activation path, instrumentation, or choose a different "
            "trigger; do not manufacture positive counters"
        )
    elif phase_positive and objective_loss:
        classification = "phase_positive_final_objective_loss"
        summary = (
            "phase telemetry was positive, but final objective evidence had a "
            "loss signal"
        )
        interpretation = (
            "local phase activation/effect did not translate into reliable final "
            "objective improvement"
        )
    elif phase_positive and pair_win_case_tie:
        classification = "phase_positive_pair_win_case_tie"
        summary = (
            "phase telemetry was positive and pair-level evidence had a win, "
            "but case-level evidence remained tied"
        )
        interpretation = (
            "treat as weak branch-local signal; refine trigger, schedule, or "
            "composition instead of repeating unchanged"
        )
    elif phase_positive and no_objective_effect:
        classification = "zero_effect_activation"
        summary = (
            "activation or phase telemetry was observed, but objective effect was "
            "zero in screening"
        )
        interpretation = (
            "mechanism activity alone was insufficient; change the causal path to "
            "objective effect"
        )
    elif pair_wins > 0 or case_wins > 0:
        classification = "objective_positive_without_phase_detail"
        summary = "objective evidence had positive signal without clear phase detail"
        interpretation = "preserve the positive direction while improving observability"
    elif no_objective_effect:
        classification = "no_objective_effect"
        summary = "screening produced no case-level or pair-level objective effect"
        interpretation = "change mechanism family, trigger, schedule, or composition"
    else:
        classification = "uncertain_causal_signal"
        summary = "screening evidence did not isolate a clear phase-to-objective cause"
        interpretation = "use bounded follow-up diagnostics before reusing the idea"

    runtime_evidence = runtime_aggregate_feedback_payload(
        runtime_ratio_median=runtime_ratio,
        runtime_delta_median_ms=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_model=runtime_model,
        runtime_regression_rate_interpretation=(
            runtime_regression_rate_interpretation
        ),
    )
    runtime_evidence = {
        "runtime_confidence": runtime_confidence,
        **runtime_evidence,
    }
    return {
        "schema_version": "phase_causal_summary.v1",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "stage": "screening",
        "classification": classification,
        "summary": summary,
        "interpretation": interpretation,
        "phase_evidence": {
            "phase_positive": phase_positive,
            "activation_status": activation_status,
            "effect_status": effect_status,
            "activation_evidence_status": activation_evidence_status,
            "objective_effect_status": objective_effect_status,
            "primary_activation_status": primary_activation_status or None,
            "primary_effect_status": primary_effect_status or None,
        },
        "objective_evidence": {
            "case_wins": case_wins,
            "case_losses": case_losses,
            "case_ties": case_ties,
            "pair_wins": pair_wins,
            "pair_losses": pair_losses,
            "pair_ties": pair_ties,
            "median_delta": median_delta,
            "gate_outcome": gate_outcome,
            "tier": tier,
        },
        "runtime_evidence": runtime_evidence,
        "opportunity_status": opportunity_status,
    }


def _phase_positive(
    *,
    activation_status: str,
    effect_status: str,
    activation_evidence_status: str,
    objective_effect_status: str,
    primary_activation_status: str,
    primary_effect_status: str,
) -> bool:
    positive_values = {"observed", "positive", "activation_observed"}
    if activation_status == "observed":
        return True
    if activation_evidence_status in positive_values:
        return True
    if primary_activation_status in positive_values:
        return True
    if effect_status in {
        "case_level_positive_signal",
        "pair_level_positive_signal",
    }:
        return True
    if objective_effect_status in {"observed", "positive"}:
        return True
    return primary_effect_status in positive_values


def _objective_loss_signal(
    *,
    case_losses: int,
    pair_losses: int,
    median_delta: float | None,
) -> bool:
    if case_losses > 0 or pair_losses > 0:
        return True
    return median_delta is not None and median_delta < -_EPS


def _objective_no_effect(
    *,
    case_wins: int,
    case_losses: int,
    pair_wins: int,
    pair_losses: int,
    median_delta: float | None,
) -> bool:
    return (
        case_wins == 0
        and case_losses == 0
        and pair_wins == 0
        and pair_losses == 0
        and (median_delta is None or abs(median_delta) <= _EPS)
    )


def _allowed_followup_variants(tier: ScreeningFeedbackTier) -> tuple[str, ...]:
    if tier in {"weak_positive", "marginal", "no_effect"}:
        return ("trigger", "schedule", "threshold", "composition")
    if tier == "runtime_regression":
        return ("runtime_bound", "trigger", "schedule")
    if tier == "quality_regression":
        return ("quality_guard", "trigger", "composition")
    if tier == "inactive":
        return ("activation_path", "wiring", "telemetry")
    if tier == "invalid":
        return ("repair",)
    return ()


def _primary_reason(reason_codes: tuple[str, ...]) -> str:
    cleaned = [str(code).strip() for code in reason_codes if str(code).strip()]
    if not cleaned:
        return ""
    for code in cleaned:
        upper = code.upper()
        if upper.startswith("SCREENING_FAIL") or "WIN_RATE" in upper:
            return code
    return cleaned[0]


def _telemetry_guard_passed(protocol: ProtocolResult) -> bool:
    summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(summary, Mapping):
        return False
    guard = summary.get("telemetry_guard")
    return isinstance(guard, Mapping) and bool(guard.get("passed", False))


def _detail_counter(detail: Mapping[str, Any], key: str) -> int:
    return _safe_int(detail.get(key))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "ScreeningFeedbackSummary",
    "ScreeningFeedbackTier",
    "screening_feedback_summary",
]
