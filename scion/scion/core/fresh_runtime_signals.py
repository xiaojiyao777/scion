"""Structured fresh-runtime follow-up signal detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FreshRuntimeOpportunitySignal:
    has_actionable_loss_signal: bool
    source_codes: tuple[str, ...] = ()
    ignored_text_diagnostics: bool = False
    decision_features_excluded: bool = True

    def as_metadata(self) -> dict[str, Any]:
        return {
            "schema_version": "fresh_runtime_opportunity_signal.v1",
            "has_actionable_loss_signal": self.has_actionable_loss_signal,
            "source_codes": list(self.source_codes),
            "ignored_text_diagnostics": self.ignored_text_diagnostics,
            "decision_features_excluded": self.decision_features_excluded,
        }


def fresh_runtime_actionable_loss_signal(
    summary: Mapping[str, Any],
    reason_codes: Iterable[str] = (),
) -> FreshRuntimeOpportunitySignal:
    """Return whether structured evidence supports a fresh-runtime loss follow-up."""

    source_codes: list[str] = []
    ignored_text_diagnostics = bool(
        _string_tuple(summary.get("opportunity_diagnostics"))
    )
    phase = summary.get("phase_activation_summary")
    if isinstance(phase, Mapping):
        activation = _lower_text(phase.get("activation_status"))
        effect = _lower_text(phase.get("effect_status"))
        objective = _lower_text(phase.get("objective_effect_status"))
        telemetry = _lower_text(phase.get("telemetry_outcome"))
        if activation == "observed":
            source_codes.append("phase_activation_summary.activation_observed")
        if effect not in {"", "unknown", "no_objective_effect"}:
            source_codes.append("phase_activation_summary.effect_status")
        if objective not in {"", "unknown", "zero", "no_effect"}:
            source_codes.append("phase_activation_summary.objective_effect_status")
        if telemetry not in {"", "unknown"}:
            source_codes.append("phase_activation_summary.telemetry_outcome")

    for code in _reason_codes(summary, reason_codes):
        if "DIAGNOSTIC" in code:
            source_codes.append("reason_code.diagnostic")
        if "TELEMETRY" in code:
            source_codes.append("reason_code.telemetry")

    deduped_source_codes = tuple(dict.fromkeys(source_codes))
    return FreshRuntimeOpportunitySignal(
        has_actionable_loss_signal=bool(deduped_source_codes),
        source_codes=deduped_source_codes,
        ignored_text_diagnostics=ignored_text_diagnostics,
    )


def fresh_runtime_replay_trigger(
    summary: Mapping[str, Any],
    marker_payload: Mapping[str, Any] | None = None,
    reason_codes: Iterable[str] = (),
) -> str:
    """Return a replay trigger supported by current structured summary evidence."""

    marker = marker_payload if isinstance(marker_payload, Mapping) else {}
    requested = str(marker.get("trigger") or "").strip()
    pair_trigger = _pair_level_win_no_loss(summary)
    loss_trigger = _actionable_loss_replay(summary, reason_codes)

    if requested == "pair_level_win_no_loss":
        return requested if pair_trigger else ""
    if requested == "actionable_loss_diagnostic":
        return requested if loss_trigger else ""
    if pair_trigger:
        return "pair_level_win_no_loss"
    if loss_trigger:
        return "actionable_loss_diagnostic"
    return ""


def _reason_codes(
    summary: Mapping[str, Any],
    reason_codes: Iterable[str],
) -> tuple[str, ...]:
    values: list[Any] = list(reason_codes or ())
    for key in (
        "reason_codes",
        "decision_reason_codes",
        "why_not_promoted_reason_codes",
        "gate_observation_reason_codes",
    ):
        values.extend(_string_tuple(summary.get(key)))
    return tuple(
        dict.fromkeys(
            str(value).strip().upper()
            for value in values
            if str(value).strip()
        )
    )


def _pair_level_win_no_loss(summary: Mapping[str, Any]) -> bool:
    pair_wins = _nonnegative_int(summary.get("pair_wins"))
    pair_losses = _nonnegative_int(summary.get("pair_losses"))
    return pair_wins > 0 and pair_losses == 0


def _actionable_loss_replay(
    summary: Mapping[str, Any],
    reason_codes: Iterable[str],
) -> bool:
    losses = _nonnegative_int(summary.get("losses"))
    pair_losses = _nonnegative_int(summary.get("pair_losses"))
    if losses <= 0 and pair_losses <= 0:
        return False
    return fresh_runtime_actionable_loss_signal(
        summary,
        reason_codes,
    ).has_actionable_loss_signal


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(
            text
            for text in (str(item).strip() for item in value)
            if text
        )
    text = str(value).strip()
    return (text,) if text else ()


__all__ = [
    "FreshRuntimeOpportunitySignal",
    "fresh_runtime_actionable_loss_signal",
    "fresh_runtime_replay_trigger",
]
