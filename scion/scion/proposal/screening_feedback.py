"""Screening feedback tiering for proposal guidance.

The tier is a prompt/lifecycle signal only. It is derived from screening-stage
aggregate summaries and must not be consumed by promotion decisions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from scion.core.models import ExperimentStage, ProtocolResult
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    telemetry_decision_details,
    telemetry_failure_categories,
)

ScreeningFeedbackTier = Literal[
    "invalid",
    "inactive",
    "weak_positive",
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
    runtime_pairs: int
    activation_status: str
    effect_status: str
    why_not_promoted: str
    allowed_followup_variants: tuple[str, ...]
    repeat_unchanged_allowed: bool
    reason_codes: tuple[str, ...] = ()
    runtime_confidence: str = "unknown"
    opportunity_status: str = "unknown"
    opportunity_diagnostics: tuple[str, ...] = ()
    mechanism_evidence: Mapping[str, Any] = field(default_factory=dict)
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
            "why_not_promoted": self.why_not_promoted,
            "allowed_followup_variants": list(self.allowed_followup_variants),
            "repeat_unchanged_allowed": self.repeat_unchanged_allowed,
            "reason_codes": list(self.reason_codes),
            "feedback_digest": self.feedback_digest,
            "promotion_boundary": "unchanged_decision_features_and_gates",
        }

    def runtime_summary_payload(self) -> dict[str, Any]:
        return {
            "runtime_ratio_median": self.runtime_ratio_median,
            "runtime_delta_median_ms": self.runtime_delta_median_ms,
            "runtime_regression_rate": self.runtime_regression_rate,
            "runtime_pairs": self.runtime_pairs,
        }


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
    quality_negative = (
        (median_delta is not None and median_delta < -_EPS)
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
    )
    runtime_confidence = _runtime_confidence(
        runtime_ratio=runtime_ratio,
        runtime_delta=runtime_delta,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=runtime_pairs,
    )
    mechanism_evidence = _mechanism_evidence(protocol)
    opportunity_diagnostics = _opportunity_diagnostics(
        protocol,
        mechanism_evidence=mechanism_evidence,
        no_objective_effect=no_objective_effect,
    )
    opportunity_status = (
        "opportunity_poor"
        if opportunity_diagnostics
        and any("opportunity" in item or "not evaluated" in item for item in opportunity_diagnostics)
        else "low_confidence"
        if opportunity_diagnostics
        else "unknown"
    )

    if invalid:
        tier: ScreeningFeedbackTier = "invalid"
    elif protocol.gate_outcome == "pass":
        tier = "promotable"
    elif quality_negative:
        tier = "quality_regression"
    elif objective_positive:
        tier = "weak_positive"
    elif activation_status == "not_observed":
        tier = "inactive"
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
        runtime_pairs=runtime_pairs,
        activation_status=activation_status,
        effect_status=effect_status,
        why_not_promoted=why,
        allowed_followup_variants=variants,
        repeat_unchanged_allowed=repeat_unchanged,
        reason_codes=reason_codes,
        runtime_confidence=runtime_confidence,
        opportunity_status=opportunity_status,
        opportunity_diagnostics=opportunity_diagnostics,
        mechanism_evidence=mechanism_evidence,
    )
    return _with_digest(summary)


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
    runtime_pairs: int = 0,
    activation_status: str = "unknown",
    effect_status: str = "uncertain",
    why_not_promoted: str = "",
    allowed_followup_variants: tuple[str, ...] = (),
    repeat_unchanged_allowed: bool = True,
    reason_codes: tuple[str, ...] = (),
    runtime_confidence: str = "unknown",
    opportunity_status: str = "unknown",
    opportunity_diagnostics: tuple[str, ...] = (),
    mechanism_evidence: Mapping[str, Any] | None = None,
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
        runtime_pairs=runtime_pairs,
        activation_status=activation_status,
        effect_status=effect_status,
        why_not_promoted=why_not_promoted,
        allowed_followup_variants=allowed_followup_variants,
        repeat_unchanged_allowed=repeat_unchanged_allowed,
        reason_codes=reason_codes,
        runtime_confidence=runtime_confidence,
        opportunity_status=opportunity_status,
        opportunity_diagnostics=opportunity_diagnostics,
        mechanism_evidence=mechanism_evidence or {},
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
) -> bool:
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


def _mechanism_evidence(protocol: ProtocolResult) -> dict[str, Any]:
    guard = _telemetry_guard(protocol)
    diagnostics = guard.get("mechanism_diagnostics") if guard else None
    if not isinstance(diagnostics, list):
        return {}
    mechanisms: list[dict[str, Any]] = []
    hook_ids: list[str] = []
    primary_ids: list[str] = []
    for item in diagnostics:
        if not isinstance(item, Mapping):
            continue
        mechanism = str(item.get("mechanism") or "").strip()
        if not mechanism:
            continue
        entry = {
            "mechanism": mechanism,
            "role": "wrapper_hook" if _looks_like_wrapper_hook(mechanism) else "primary",
            "activation_status": item.get("activation_status"),
            "runtime_status": item.get("runtime_status"),
            "effect_status": item.get("effect_status"),
            "diagnostic_kind": item.get("diagnostic_kind"),
            "telemetry_outcome": item.get("telemetry_outcome"),
        }
        mechanisms.append(entry)
        if entry["role"] == "wrapper_hook":
            hook_ids.append(mechanism)
        else:
            primary_ids.append(mechanism)
    primary = primary_ids[0] if primary_ids else (mechanisms[0]["mechanism"] if mechanisms else "")
    hook_activation_observed = any(
        item.get("role") == "wrapper_hook"
        and str(item.get("activation_status") or "") == "observed"
        for item in mechanisms
    )
    primary_entry = next(
        (item for item in mechanisms if item.get("mechanism") == primary),
        {},
    )
    return {
        "declared_mechanism_count": len(mechanisms),
        "primary_mechanism": primary,
        "wrapper_hook_mechanisms": hook_ids,
        "hook_activation_observed": hook_activation_observed,
        "primary_activation_status": primary_entry.get("activation_status"),
        "primary_effect_status": primary_entry.get("effect_status"),
        "primary_diagnostic_kind": primary_entry.get("diagnostic_kind"),
        "mechanisms": mechanisms,
    }


def _opportunity_diagnostics(
    protocol: ProtocolResult,
    *,
    mechanism_evidence: Mapping[str, Any],
    no_objective_effect: bool,
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    guard = _telemetry_guard(protocol)
    if guard is not None:
        for key in ("mechanism_opportunity_diagnostics", "opportunity_diagnostics"):
            raw_items = guard.get(key)
            if not isinstance(raw_items, list):
                continue
            for raw in raw_items:
                text = str(raw.get("summary") if isinstance(raw, Mapping) else raw)
                text = text.strip()
                if text and text not in diagnostics:
                    diagnostics.append(text)
    primary = str(mechanism_evidence.get("primary_mechanism") or "").strip()
    primary_activation = str(
        mechanism_evidence.get("primary_activation_status") or ""
    ).strip()
    primary_kind = str(mechanism_evidence.get("primary_diagnostic_kind") or "").strip()
    if (
        primary
        and mechanism_evidence.get("hook_activation_observed")
        and primary_activation in {"missing", "zero", ""}
    ):
        diagnostics.append(
            "wrapper hook activated, but primary mechanism was not evaluated "
            "with mechanism-local evidence in this screening set"
        )
    if primary_kind == "not_evaluated/not_triggered":
        diagnostics.append(
            "primary mechanism not evaluated or trigger did not fire in current screening"
        )
    stats = protocol.stats
    case_total = _safe_int(getattr(stats, "n_cases", 0))
    all_case_ties = (
        case_total > 0
        and _safe_int(getattr(stats, "ties", 0)) == case_total
        and _safe_int(getattr(stats, "wins", 0)) == 0
        and _safe_int(getattr(stats, "losses", 0)) == 0
    )
    if no_objective_effect and all_case_ties and case_total <= 2:
        diagnostics.append(
            "all screening cases tied on a tiny sample; opportunity and runtime "
            "diagnostics are low confidence"
        )
    runtime_budget = (
        protocol.candidate_surface_runtime_summary or {}
        if isinstance(protocol.candidate_surface_runtime_summary, Mapping)
        else {}
    )
    budget_payload = runtime_budget.get("runtime_budget_diagnostic")
    if isinstance(budget_payload, Mapping):
        code = str(budget_payload.get("code") or "").lower()
        if no_objective_effect and all_case_ties and "saturation" in code:
            diagnostics.append(
                "all screening cases tied while runtime budget is saturated; "
                "current screening has low confidence for this mechanism class"
            )
    return tuple(dict.fromkeys(diagnostics))


def _telemetry_guard(protocol: ProtocolResult) -> Mapping[str, Any] | None:
    summary = protocol.candidate_surface_runtime_summary or {}
    if not isinstance(summary, Mapping):
        return None
    guard = summary.get("telemetry_guard")
    return guard if isinstance(guard, Mapping) else None


def _looks_like_wrapper_hook(mechanism: str) -> bool:
    text = mechanism.lower()
    return (
        "hook" in text
        or text.startswith("scheduler_")
        or text.startswith("wrapper_")
        or text.endswith("_wrapper")
    )


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
    if tier == "no_effect":
        return primary or "active screening produced no case-level or pair-level effect"
    if tier == "quality_regression":
        return primary or "objective quality regressed or losses dominated"
    if tier == "runtime_regression":
        return primary or "no objective effect and runtime regressed"
    return primary or f"screening outcome remained {gate_outcome}"


def _allowed_followup_variants(tier: ScreeningFeedbackTier) -> tuple[str, ...]:
    if tier in {"weak_positive", "no_effect"}:
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
